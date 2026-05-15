from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, Request, expect, sync_playwright


APP_URL = "http://127.0.0.1:8000"
XSS_TEXT = '<img src=x onerror="window.__xssHits.push(\'payload\')" data-xss="payload">'


@pytest.fixture(scope="module")
def web_server():
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "warframe_agent.web.app:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                import urllib.request
                urllib.request.urlopen(APP_URL, timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Web server did not become ready")
        yield
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


@pytest.fixture
def page_with_api(web_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        try:
            yield from _configure_page(page)
        finally:
            browser.close()


def _configure_page(page: Page):
    state = {
        "chat_messages": [],
        "deleted_favorites": 0,
        "deleted_alerts": 0,
        "deleted_watches": 0,
        "console_errors": [],
        "page_errors": [],
    }

    page.add_init_script("""
        window.__xssHits = [];
        window.__lastWsPayload = null;
        window.WebSocket = class MockWebSocket {
            constructor() {
                this.readyState = 0;
                setTimeout(() => {
                    this.readyState = 1;
                    window.__mockWs = this;
                    this.onopen && this.onopen();
                }, 0);
            }
            send(payload) {
                window.__lastWsPayload = payload;
                const message = JSON.parse(payload).message;
                setTimeout(() => {
                    this.onmessage && this.onmessage({ data: JSON.stringify({ reply: `模拟查价回复: ${message}` }) });
                }, 20);
            }
            close() {
                this.readyState = 3;
                this.onclose && this.onclose();
            }
        };
    """)
    page.on(
        "console",
        lambda msg: state["console_errors"].append(msg.text)
        if msg.type == "error" and "404" not in msg.text
        else None,
    )
    page.on("pageerror", lambda err: state["page_errors"].append(str(err)))
    page.on("dialog", lambda dialog: dialog.accept())

    def json_response(route: Route, payload: dict) -> None:
        route.fulfill(
            status=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
            body=json.dumps(payload),
        )

    def route_api(route: Route, request: Request) -> None:
        url = request.url
        method = request.method
        if url.endswith("/api/memory") and method == "GET":
            json_response(route, {
                "favorites": [{"display": f"{XSS_TEXT} / English / Arcane Energize", "item_id": "arcane_energize"}],
                "alerts": [
                    {"item": XSS_TEXT, "item_id": "arcane_energize", "direction": "below", "price": 45, "note": XSS_TEXT},
                    {"item": "alert-2", "item_id": "alert-2", "direction": "above", "price": 46, "note": "note-2"},
                    {"item": "alert-3", "item_id": "alert-3", "direction": "below", "price": 47, "note": "note-3"},
                    {"item": "alert-4", "item_id": "alert-4", "direction": "above", "price": 48, "note": "note-4"},
                    {"item": "alert-5", "item_id": "alert-5", "direction": "below", "price": 49, "note": "note-5"},
                    {"item": "alert-6", "item_id": "alert-6", "direction": "above", "price": 50, "note": "note-6"},
                ],
                "preferences": {},
                "watchlist": [],
            })
        elif url.endswith("/api/favorites_prices") and method == "GET":
            json_response(route, {"items": [{"item_id": "arcane_energize", "sell_price": 45, "buy_price": 40}]})
        elif url.endswith("/api/watchlist") and method == "GET":
            json_response(route, {"watchlist": [{"item_id": "arcane_energize", "item_name": XSS_TEXT, "frequency": "daily", "time": "09:00", "content": "top3_buyers"}]})
        elif "/api/watchlist/" in url and method == "DELETE":
            state["deleted_watches"] += 1
            json_response(route, {"status": "ok"})
        elif url.endswith("/api/fav") and method == "DELETE":
            state["deleted_favorites"] += 1
            json_response(route, {"status": "ok"})
        elif url.endswith("/api/alert") and method == "DELETE":
            state["deleted_alerts"] += 1
            json_response(route, {"status": "ok"})
        elif url.endswith("/api/chat") and method == "POST":
            state["chat_messages"].append(json.loads(request.post_data or "{}").get("message", ""))
            json_response(route, {"reply": "模拟查价回复"})
        elif "/api/suggest" in url and method == "GET":
            json_response(route, {"suggestions": [XSS_TEXT]})
        elif url.endswith("/api/trades?limit=20") and method == "GET":
            json_response(route, {"trades": [{"id": 1, "item_id": "arcane_energize", "item_name": "充沛赋能", "trade_type": "buy", "price": 45, "player_name": "Buyer", "timestamp": "2026-05-01T10:00:00", "notes": "测试备注"}]})
        elif url.endswith("/api/trades/stats") and method == "GET":
            json_response(route, {"total_trades": 1, "buy_count": 1, "sell_count": 0, "total_spent": 45, "total_earned": 0, "net_profit": -45, "most_traded": []})
        elif "/api/trades/" in url and method == "DELETE":
            json_response(route, {"status": "ok"})
        elif url.endswith("/api/profit/calculate") and method == "POST":
            json_response(route, {"display": "充沛赋能", "sell_price": 120, "buy_price": 90, "total_cost": 70, "profit": {"sell_profit": 50, "sell_margin": 71.4, "buy_profit": 20, "buy_margin": 28.6}, "materials": [{"display": "材料A", "quantity": 1, "total_cost": 70}]})
        elif url.endswith("/api/report") and method == "GET":
            json_response(route, {"report": "今日报告：收藏价格稳定。"})
        elif "/api/history/compare" in url and method == "POST":
            json_response(route, {"items": []})
        elif "/api/" in url:
            json_response(route, {})
        elif url.startswith("ws://"):
            route.abort()
        else:
            route.continue_()

    page.route("**/*", route_api)
    yield page, state


def open_app(page: Page) -> None:
    page.goto(APP_URL, wait_until="networkidle")
    start = page.locator("#start-btn")
    if start.count() and start.first.is_visible():
        start.first.click()


def test_sidebar_user_paths_are_safe_and_work(page_with_api):
    page, state = page_with_api
    open_app(page)

    expect(page.locator("#favorites-list .favorite-item")).to_have_count(1)
    expect(page.locator("#alerts-list .alert-item")).to_have_count(5)
    expect(page.locator("#watchlist .watch-item")).to_have_count(1)

    expect(page.locator("#favorites-list img[data-xss='payload']")).to_have_count(0)
    expect(page.locator("#alerts-list img[data-xss='payload']")).to_have_count(0)
    expect(page.locator("#watchlist img[data-xss='payload']")).to_have_count(0)
    assert "<img src=x" in page.locator("#favorites-list .item-name").first.text_content()
    assert "<img src=x" in page.locator("#alerts-list .item-name").first.text_content()
    assert "<img src=x" in page.locator("#watchlist .item-name").first.text_content()

    page.locator("#favorites-list .favorite-item .action-btn").first.click()
    expect(page.locator("#chat-input")).to_have_value("arcane_energize")

    page.locator("#favorites-list .favorite-item .action-btn.danger").first.click()
    page.locator("#alerts-list .toggle-btn").click()
    expect(page.locator("#alerts-list .alert-item")).to_have_count(6)
    page.locator("#alerts-list .alert-item .action-btn.danger").first.click()
    page.locator("#watchlist .watch-item .action-btn.danger").first.click()

    assert state["deleted_favorites"] == 1
    assert state["deleted_alerts"] == 1
    assert state["deleted_watches"] == 1
    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_chat_and_more_menu_panels_still_work(page_with_api):
    page, state = page_with_api
    open_app(page)

    for _ in range(20):
        page.locator("#chat-input").fill("充沛多少钱")
        page.locator("#send-btn").click()
        page.wait_for_timeout(500)
        if page.locator(".message.agent[data-query]").count() > 0:
            break
    expect(page.locator(".message.agent[data-query]")).to_contain_text("模拟查价回复")

    page.locator("#more-menu-btn").click()
    expect(page.locator("#more-menu")).to_have_class("more-menu active")

    page.locator("#trade-history-btn").click()
    expect(page.locator("#detail-content")).to_contain_text("交易历史")
    expect(page.locator("#detail-content")).to_contain_text("充沛赋能")

    page.locator("#more-menu-btn").click()
    page.locator("#profit-calc-btn").click()
    expect(page.locator("#detail-content")).to_contain_text("利润计算器")
    page.locator("#profit-item-input").fill("充沛")
    expect(page.locator("#profit-item-suggestions .suggestion-item")).to_have_count(1)
    expect(page.locator("#profit-item-suggestions img[data-xss='payload']")).to_have_count(0)
    page.locator("#profit-item-suggestions .suggestion-item").click()
    expect(page.locator("#profit-item-input")).to_have_value(XSS_TEXT)

    material = page.locator("#profit-materials .profit-material-row").first
    material.locator('[data-type="name"]').fill("材料A")
    material.locator('[data-type="cost"]').fill("70")
    page.locator("button", has_text="计算利润").click()
    expect(page.locator("#profit-result")).to_contain_text("50")

    page.locator("#more-menu-btn").click()
    page.locator("#report-btn").click()
    expect(page.locator("#detail-content")).to_contain_text("今日报告")

    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []
