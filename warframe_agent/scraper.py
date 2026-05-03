"""Playwright 浏览器抓取模块 — 绕过 Cloudflare 获取 warframe.market 数据"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config


@dataclass
class ScrapedOrder:
    item_id: str
    order_type: str  # "sell" or "buy"
    platinum: int
    quantity: int
    user_name: str
    status: str
    reputation: int


@dataclass
class ScrapedRiven:
    weapon: str
    mod_name: str
    attributes: list[dict]
    price: int | None
    seller: str


_browser = None
_playwright = None


async def _get_browser():
    global _browser, _playwright
    if _browser and _browser.is_connected():
        return _browser
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("Playwright 未安装，运行: pip install playwright && playwright install chromium")
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=True)
    return _browser


async def close_browser():
    global _browser, _playwright
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


async def fetch_market_page(url: str, wait_selector: str = "body", timeout: int = 15000) -> str:
    """获取页面 HTML，绕过 Cloudflare"""
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout)
        await page.wait_for_selector(wait_selector, timeout=timeout)
        return await page.content()
    finally:
        await page.close()


async def fetch_market_api(url: str) -> dict | list | None:
    """通过浏览器上下文直接请求 warframe.market API（自动携带 cookies）"""
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        # 先访问主页面建立 session
        await page.goto("https://warframe.market", wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(1)
        # 再请求 API
        resp = await page.evaluate(f"""
            async () => {{
                const r = await fetch("{url}", {{
                    headers: {{
                        'Accept': 'application/json',
                        'Platform': 'pc',
                        'Language': 'zh'
                    }}
                }});
                if (!r.ok) return null;
                return await r.json();
            }}
        """)
        return resp
    except Exception:
        return None
    finally:
        await page.close()


async def scrape_orders(item_url_name: str) -> list[ScrapedOrder]:
    """抓取物品订单（通过浏览器绕过 Cloudflare）"""
    api_url = f"https://api.warframe.market/v1/items/{item_url_name}/orders"
    data = await fetch_market_api(api_url)
    if not data:
        return []

    orders = []
    for o in data.get("payload", {}).get("orders", []):
        user = o.get("user", {})
        orders.append(ScrapedOrder(
            item_id=item_url_name,
            order_type=o.get("order_type", ""),
            platinum=o.get("platinum", 0),
            quantity=o.get("quantity", 1),
            user_name=user.get("ingame_name", ""),
            status=user.get("status", ""),
            reputation=user.get("reputation", 0),
        ))
    return orders


async def scrape_riven_auctions(weapon_url_name: str = "") -> list[ScrapedRiven]:
    """抓取裂罅 Mod 拍卖数据"""
    if weapon_url_name:
        api_url = f"https://api.warframe.market/v1/auctions/search?type=riven&weapon_url_name={weapon_url_name}"
    else:
        api_url = "https://api.warframe.market/v1/auctions/search?type=riven"

    data = await fetch_market_api(api_url)
    if not data:
        return []

    rivens = []
    for item in data.get("payload", {}).get("auctions", [])[:20]:
        owner = item.get("owner", {})
        buyout = item.get("buyout_price")
        starting = item.get("starting_price")
        price = buyout or starting
        rivens.append(ScrapedRiven(
            weapon=item.get("item", {}).get("weapon_url_name", ""),
            mod_name=item.get("item", {}).get("name", ""),
            attributes=[
                {"stat": a.get("stat", ""), "value": a.get("value", 0)}
                for a in item.get("item", {}).get("attributes", [])
            ],
            price=price,
            seller=owner.get("ingame_name", ""),
        ))
    return rivens


async def scrape_item_statistics(item_url_name: str) -> dict | None:
    """抓取物品统计数据（48小时/90天价格）"""
    api_url = f"https://api.warframe.market/v1/items/{item_url_name}/statistics"
    data = await fetch_market_api(api_url)
    if not data:
        return None

    stats = data.get("payload", {}).get("statistics_closed", {})
    return {
        "48h": stats.get("48hours", []),
        "90d": stats.get("90days", []),
    }


async def scrape_wiki_page(url: str) -> str | None:
    """抓取 Wiki 页面内容"""
    try:
        html = await fetch_market_page(url, wait_selector="#mw-content-text")
        # 简单提取文本内容
        browser = await _get_browser()
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            text = await page.evaluate("""
                () => {
                    const content = document.getElementById('mw-content-text');
                    return content ? content.innerText : '';
                }
            """)
            return text
        finally:
            await page.close()
    except Exception:
        return None


def scrape_sync(coro):
    """同步包装器，用于非 async 环境"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ===== GitHub 搜索 =====

async def search_github_repos(query: str, limit: int = 10) -> list[dict]:
    """搜索 GitHub 仓库"""
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "per_page": limit},
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [
            {
                "name": item["full_name"],
                "description": item.get("description", ""),
                "stars": item.get("stargazers_count", 0),
                "url": item.get("html_url", ""),
                "language": item.get("language", ""),
            }
            for item in data.get("items", [])
        ]


async def fetch_github_file_raw(owner: str, repo: str, path: str) -> str | None:
    """获取 GitHub 仓库中的文件原始内容"""
    import httpx
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.text
    # 尝试 master 分支
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.text
    return None
