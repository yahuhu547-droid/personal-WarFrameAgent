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
WHISPER_TEXT = "/w EvilPlayer Hi! I want to buy your item for 10 platinum."


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
        "trading_memory_requests": [],
        "trading_memory_empty": False,
        "trading_memory_error_endpoint": "",
        "runtime_status": "ok",
        "runtime_error": False,
    }

    page.add_init_script("""
        window.__xssHits = [];
        window.__xssPayload = String.raw`<img src=x onerror="window.__xssHits.push('chat')" data-xss="chat">`;
        window.__whisperPayload = String.raw`/w EvilPlayer Hi! I want to buy your item for 10 platinum.`;
        window.__lastCopiedText = null;
        window.__lastWsPayload = null;
        Object.defineProperty(navigator, 'clipboard', {
            value: {
                writeText: async (text) => {
                    window.__lastCopiedText = text;
                }
            },
            configurable: true
        });
        window.Chart = class MockChart {
            constructor() {}
            destroy() {}
        };
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
                    const reply = message.includes('xss regression')
                        ? `**安全回复** ${window.__xssPayload}\\n\\n${window.__whisperPayload}`
                        : `模拟查价回复: ${message}`;
                    this.onmessage && this.onmessage({ data: JSON.stringify({ reply }) });
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
        if msg.type == "error" and "Failed to load resource" not in msg.text
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
        if url.endswith("/api/runtime/status") and method == "GET":
            if state["runtime_error"]:
                json_response(route, {"status": "error", "error": "runtime status unavailable"})
            else:
                scheduler_running = state["runtime_status"] != "degraded"
                json_response(route, {
                    "status": state["runtime_status"],
                    "web": {"started_at": 1760000000.0, "uptime_seconds": 321},
                    "scheduler": {
                        "running": scheduler_running,
                        "has_scheduler": True,
                        "total": 2,
                        "jobs": [
                            {
                                "job_id": "scan_favorites",
                                "name": "收藏扫描",
                                "enabled": True,
                                "running": False,
                                "last_success": True,
                                "last_duration_ms": 12.5,
                                "last_error_summary": None,
                                "safety_level": "read_only",
                                "external_side_effect": False,
                            },
                            {
                                "job_id": "daily_report",
                                "name": "每日报告",
                                "enabled": True,
                                "running": False,
                                "last_success": False,
                                "last_duration_ms": 3.2,
                                "last_error_summary": "[REDACTED]",
                                "safety_level": "external_side_effect",
                                "external_side_effect": True,
                            },
                        ],
                    },
                    "daily_report": {"enabled": True, "report_time": "12:30", "last_report_date": "2026-05-18"},
                    "feishu": {"enabled": True, "configured": True, "managed_running": scheduler_running},
                    "wxpusher": {"enabled": True, "configured": True, "available": True, "uid_count": 1},
                    "background_tasks": {
                        "total": 2,
                        "running": 1,
                        "error": 1,
                        "done": 0,
                        "tasks": [
                            {"task_id": "scan-1", "status": "running", "age_seconds": 9, "result_count": 0},
                            {"task_id": "goal-1", "status": "error", "age_seconds": 20, "goal_id": "goal-a", "error_summary": "[REDACTED]"},
                        ],
                    },
                    "recent_tool_calls": {
                        "count": 1,
                        "items": [
                            {"tool_name": "query_price", "ok": True, "duration_ms": 8.5, "args_summary": {"item_name": "arcane_energize"}, "error_summary": "", "tool_timestamp": "tool-time"},
                        ],
                    },
                })
        elif "/api/tool-calls/history" in url and method == "GET":
            json_response(route, {
                "count": 2,
                "items": [
                    {"tool_name": "query_price", "ok": True, "duration_ms": 8.5, "args_summary": {"item_name": "arcane_energize"}, "tool_timestamp": "tool-time-1", "contexts": ["arcane_energize"]},
                    {"tool_name": "query_events", "ok": False, "duration_ms": 30, "args_summary": {"source": XSS_TEXT}, "error_summary": "[REDACTED]", "tool_timestamp": "tool-time-2"},
                ],
            })
        elif "/api/tool-calls/stats" in url and method == "GET":
            json_response(route, {
                "total_calls": 3,
                "success_count": 2,
                "failure_count": 1,
                "unknown_count": 0,
                "success_rate": 0.6667,
                "duration_ms": {"count": 3, "avg": 16.2, "min": 8.5, "max": 30},
                "by_tool": {
                    "query_price": {"total_calls": 2, "success_count": 2, "failure_count": 0, "unknown_count": 0, "success_rate": 1.0, "duration_ms": {"count": 2, "avg": 9.3, "min": 8.5, "max": 10.1}},
                    "query_events": {"total_calls": 1, "success_count": 0, "failure_count": 1, "unknown_count": 0, "success_rate": 0.0, "duration_ms": {"count": 1, "avg": 30, "min": 30, "max": 30}},
                },
                "top_tools": [{"tool_name": "query_price", "total_calls": 2}, {"tool_name": "query_events", "total_calls": 1}],
            })
        elif url.endswith("/api/memory") and method == "GET":
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
            message = json.loads(request.post_data or "{}").get("message", "")
            state["chat_messages"].append(message)
            reply = f"**安全回复** {XSS_TEXT}\n\n{WHISPER_TEXT}" if "xss regression" in message else "模拟查价回复"
            json_response(route, {"reply": reply})
        elif "/api/relic/drops/Lith/B1" in url and method == "GET":
            json_response(route, {
                "tier": "Lith",
                "relicName": "B1",
                "displayName": "Lith B1",
                "vaultStatus": "未入库",
                "rewardsByState": {
                    "Intact": [
                        {"itemName": XSS_TEXT, "rarity": "Rare", "rarityZh": XSS_TEXT, "chance": 2.0},
                        {"itemName": "Braton Prime Blueprint", "rarity": "Common", "rarityZh": "常规", "chance": 25.33},
                    ]
                },
                "states": ["Intact"],
                "stateLabels": {"Intact": "完好"},
            })
        elif "/api/relic/value/Lith/B1" in url and method == "GET":
            json_response(route, {
                "tier": "Lith",
                "relicName": "B1",
                "displayName": "Lith B1",
                "vaultStatus": "available",
                "expectedPlatinum": 1.27,
                "expectedDucats": 3.8,
                "summaryRecommendation": XSS_TEXT,
                "topPlatinumReward": "braton_prime_blueprint",
                "topDucatEfficiencyReward": "braton_prime_blueprint",
                "rewards": [
                    {
                        "itemName": XSS_TEXT,
                        "marketId": "braton_prime_blueprint",
                        "rarity": "Common",
                        "dropRate": 0.2533,
                        "lowestSellPrice": 8,
                        "highestBuyPrice": 5,
                        "valuationPrice": 5,
                        "valuationSource": "highest_buy",
                        "ducatValue": 15,
                        "ducatsPerPlat": 1.88,
                        "expectedPlatinum": 1.27,
                        "expectedDucats": 3.8,
                        "recommendation": XSS_TEXT,
                        "warnings": [XSS_TEXT],
                    }
                ],
            })
        elif "/api/relic/sources/Lith%20B1" in url and method == "GET":
            json_response(route, {"relicName": "Lith B1", "sources": [], "total": 0})
        elif "/api/mod_flipper" in url and method == "GET":
            json_response(route, {"status": "done", "total": 1, "results": [{
                "item_id": "arcane_energize",
                "display_name": "Arcane Energize",
                "r0_buy_price": 106,
                "r10_sell_price": 150,
                "flip_profit": 44,
                "roi_pct": 41.5,
                "endo_cost": 1280,
                "plat_per_1k_endo": 34.38,
                "volume_48h": 20,
                "max_rank": 5,
                "market_url": "https://warframe.market/items/arcane_energize",
                "trade_plan": {
                    "source": "arcane_flip",
                    "strategy": "arcane_r0_to_r5",
                    "display_strategy": "买 21 个 R0 -> 合成 R5 -> 卖出",
                    "item_id": "arcane_energize",
                    "required_quantity": 21,
                    "total_cost": 106,
                    "total_revenue": 150,
                    "profit": 44,
                    "roi_pct": 41.5,
                    "buy_steps": [
                        {"label": "买入 R0", "player": "CheapBulk", "unit_price": 4, "quantity": 10, "subtotal": 40, "rank": 0, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/CheapBulk", "whisper": "/w CheapBulk buy 10"},
                        {"label": "买入 R0", "player": "NextBulk", "unit_price": 6, "quantity": 11, "subtotal": 66, "rank": 0, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/NextBulk", "whisper": "/w NextBulk buy 11"}
                    ],
                    "sell_steps": [
                        {"label": "出售 R5", "player": "Rank5Buyer", "unit_price": 150, "quantity": 1, "subtotal": 150, "rank": 5, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/Rank5Buyer", "whisper": "/w Rank5Buyer sell r5"}
                    ],
                    "safe_summary": {"source": "arcane_flip", "strategy": "arcane_r0_to_r5", "profit": 44}
                }
            }]})
        elif "/api/set_profit" in url and method == "GET":
            json_response(route, {"status": "done", "total": 1, "results": [{
                "base_id": "rhino_prime",
                "display_name": "Rhino Prime",
                "best_strategy": "买部件→卖套装",
                "best_profit": 25,
                "best_cost": 70,
                "best_revenue": 95,
                "roi_pct": 35.7,
                "liquidity_score": 42.0,
                "risk_level": "medium",
                "risk_score": 35.0,
                "opportunity_score": 48.4,
                "supply_count": 4,
                "demand_count": 1,
                "set_sell_price": 95,
                "parts_sell_total": 70,
                "volume_48h": 10,
                "market_url": "https://warframe.market/items/rhino_prime_set",
                "set_seller": {"player": "SetSeller_UI", "price": 90},
                "set_buyer": {"player": "SetBuyer_UI", "price": 95},
                "part_details": [{"name": "蓝图", "market_url": "https://warframe.market/items/rhino_prime_blueprint"}],
                "trade_plan": {
                    "source": "set_profit",
                    "strategy": "buy_parts_sell_set",
                    "display_strategy": "买部件 -> 卖整套",
                    "item_id": "rhino_prime_set",
                    "required_quantity": 4,
                    "total_cost": 70,
                    "total_revenue": 95,
                    "profit": 25,
                    "roi_pct": 35.7,
                    "buy_steps": [
                        {"label": "买入部件：蓝图", "player": "BpSeller_UI", "unit_price": 10, "quantity": 1, "subtotal": 10, "market_url": "https://warframe.market/items/rhino_prime_blueprint", "profile_url": "https://warframe.market/profile/BpSeller_UI", "whisper": "/w BpSeller_UI buy bp"}
                    ],
                    "sell_steps": [
                        {"label": "出售整套", "player": "SetBuyer_UI", "unit_price": 95, "quantity": 1, "subtotal": 95, "market_url": "https://warframe.market/items/rhino_prime_set", "profile_url": "https://warframe.market/profile/SetBuyer_UI", "whisper": "/w SetBuyer_UI sell set"}
                    ],
                    "safe_summary": {"source": "set_profit", "strategy": "buy_parts_sell_set", "profit": 25}
                }
            }]})
        elif "/api/investment" in url and method == "GET":
            json_response(route, {"status": "done", "total": 1, "results": [{
                "base_id": "rhino_prime",
                "display_name": "Rhino Prime",
                "strategy": "buy_parts_sell_set",
                "buy_cost": 70,
                "sell_price": 95,
                "profit_per_set": 25,
                "roi_pct": 35.7,
                "sets_affordable": 7,
                "total_profit": 175,
                "volume_48h": 10,
                "risk_level": "medium",
                "set_item_id": "rhino_prime_set",
                "part_details": [],
                "trade_plan": {
                    "source": "investment",
                    "strategy": "buy_parts_sell_set",
                    "display_strategy": "买部件 -> 卖整套",
                    "item_id": "rhino_prime_set",
                    "required_quantity": 4,
                    "total_cost": 70,
                    "total_revenue": 95,
                    "profit": 25,
                    "roi_pct": 35.7,
                    "buy_steps": [{"label": "买入部件：蓝图", "player": "InvSeller_UI", "unit_price": 10, "quantity": 1, "subtotal": 10, "market_url": "https://warframe.market/items/rhino_prime_blueprint", "profile_url": "https://warframe.market/profile/InvSeller_UI", "whisper": "/w InvSeller_UI buy"}],
                    "sell_steps": [{"label": "出售整套", "player": "InvBuyer_UI", "unit_price": 95, "quantity": 1, "subtotal": 95, "market_url": "https://warframe.market/items/rhino_prime_set", "profile_url": "https://warframe.market/profile/InvBuyer_UI", "whisper": "/w InvBuyer_UI sell"}],
                    "safe_summary": {"source": "investment", "strategy": "buy_parts_sell_set", "profit": 25}
                }
            }]})
        elif "/api/suggest" in url and method == "GET":
            json_response(route, {"suggestions": [XSS_TEXT]})
        elif "/api/item_detail/" in url and method == "GET":
            json_response(route, {
                "item_id": "arcane_energize",
                "display": XSS_TEXT,
                "sell_price": 45,
                "buy_price": 40,
                "spread": 5,
                "seller": {"name": XSS_TEXT, "reputation": 1},
                "buyer": {"name": XSS_TEXT, "reputation": 2},
                "whisper_sell": WHISPER_TEXT,
                "whisper_buy": "/w Buyer Hi! I want to sell this item for 40 platinum.",
            })
        elif "/api/history/arcane_energize" in url and method == "GET":
            json_response(route, {"snapshots": [
                {"timestamp": "2026-05-18T10:00:00", "sell_price": 45, "buy_price": 40},
                {"timestamp": "2026-05-18T11:00:00", "sell_price": 47, "buy_price": 41},
            ]})
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
        elif "/api/memory/recall" in url:
            state["trading_memory_requests"].append({"method": method, "url": url})
            json_response(route, {
                "count": 1,
                "query_summary": {"item_name": "arcane_energize", "intent": "price_check", "tool_names": ["query_price"]},
                "score_breakdown": {"count": 1, "max_score": 0.84, "weights": {"relevance": 0.6, "recency": 0.2, "salience": 0.2}},
                "items": [
                    {
                        "source": "market_snapshot",
                        "record_id": 1,
                        "timestamp": "2026-05-18T10:00:00",
                        "item_name": XSS_TEXT,
                        "score": 0.84,
                        "relevance": 0.7,
                        "recency": 1.0,
                        "salience": 0.5,
                        "summary": {"sell_price": 45, "buy_price": 38, "source": XSS_TEXT},
                        "trace": {"item_match": True, "intent_match": True, "tool_match": ["query_price"], "recency": 1.0, "salience_reason": XSS_TEXT},
                    }
                ],
            })
        elif "/api/trading-memory/" in url:
            state["trading_memory_requests"].append({"method": method, "url": url})
            if state["trading_memory_error_endpoint"] and state["trading_memory_error_endpoint"] in url:
                route.fulfill(
                    status=500,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    body=json.dumps({"detail": "mock trading memory failure"}),
                )
            elif "market-snapshots" in url:
                json_response(route, {
                    "market_snapshots": [] if state["trading_memory_empty"] else [
                        {
                            "id": 1,
                            "timestamp": "2026-05-18T10:00:00",
                            "item_name": XSS_TEXT,
                            "source": XSS_TEXT,
                            "item_id": "arcane_energize",
                            "sell_price": 45,
                            "buy_price": 38,
                            "spread": 7,
                        }
                    ],
                    "count": 0 if state["trading_memory_empty"] else 1,
                })
            elif "recommendations" in url:
                json_response(route, {
                    "recommendations": [] if state["trading_memory_empty"] else [
                        {
                            "id": 2,
                            "timestamp": "2026-05-18T11:00:00",
                            "item_name": XSS_TEXT,
                            "recommendation_type": "baro",
                            "reason": XSS_TEXT,
                            "source": XSS_TEXT,
                            "event_type": "baro",
                            "event_description": XSS_TEXT,
                            "display_name": XSS_TEXT,
                            "market_id": "primed_flow",
                            "best_buy_price": 80,
                            "best_sell_price": 120,
                            "ducat_cost": 350,
                            "credit_cost": 100000,
                            "rank": 5,
                            "max_rank": 10,
                            "item_kind": "mod",
                        }
                    ],
                    "count": 0 if state["trading_memory_empty"] else 1,
                })
            elif "push-history" in url:
                json_response(route, {
                    "push_history": [] if state["trading_memory_empty"] else [
                        {
                            "id": 3,
                            "timestamp": "2026-05-18T12:00:00",
                            "push_type": "opportunity",
                            "item_name": XSS_TEXT,
                            "message": XSS_TEXT,
                            "source": XSS_TEXT,
                            "item_id": "arcane_energize",
                            "item_display": XSS_TEXT,
                            "priority": 4,
                            "action_suggestion": XSS_TEXT,
                            "suggestion_type": "buy",
                            "event_type": "prime_vault",
                            "event_description": XSS_TEXT,
                            "items_affected": [XSS_TEXT, "arcane_energize"],
                        }
                    ],
                    "count": 0 if state["trading_memory_empty"] else 1,
                })
            else:
                json_response(route, {})
        elif "/api/history/compare" in url and method == "POST":
            json_response(route, {"items": {
                "arcane_energize": {
                    "display": XSS_TEXT,
                    "snapshots": [
                        {"timestamp": "2026-05-18T10:00:00", "sell_price": 45},
                        {"timestamp": "2026-05-18T11:00:00", "sell_price": 47},
                    ],
                },
                "safe_item": {
                    "display": "Safe Item",
                    "snapshots": [
                        {"timestamp": "2026-05-18T10:00:00", "sell_price": 20},
                        {"timestamp": "2026-05-18T11:00:00", "sell_price": 22},
                    ],
                },
            }})
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


def test_trading_memory_panel_renders_tabs_safely_and_read_only(page_with_api):
    page, state = page_with_api
    open_app(page)

    page.locator("#more-menu-btn").click()
    page.locator("#trading-memory-btn").click()

    content = page.locator("#detail-content")
    expect(content).to_contain_text("长期交易记忆")
    expect(content).to_contain_text("市场快照")
    expect(content).to_contain_text("45p")
    expect(content).to_contain_text("38p")
    expect(content).to_contain_text("7p")

    page.locator("#trading-memory-tab-recommendations").click()
    expect(content).to_contain_text("推荐记录")
    expect(content).to_contain_text("baro")
    expect(content).to_contain_text("120p")
    expect(content).to_contain_text("350 杜卡德")

    page.locator("#trading-memory-tab-push-history").click()
    expect(content).to_contain_text("推送历史")
    expect(content).to_contain_text("opportunity")
    expect(content).to_contain_text("优先级 4")
    expect(content).to_contain_text("arcane_energize")

    expect(page.locator("#detail-content img[data-xss='payload']")).to_have_count(0)
    assert page.evaluate("window.__xssHits") == []
    assert state["trading_memory_requests"]
    assert all(request["method"] == "GET" for request in state["trading_memory_requests"])
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_trade_opportunity_panels_render_actionable_trade_plans(page_with_api):
    page, state = page_with_api
    open_app(page)

    page.locator("#more-menu-btn").click()
    page.locator("#mod-flip-btn").click()
    content = page.locator("#detail-content")
    expect(content).to_contain_text("买 21 个 R0")
    expect(content).to_contain_text("CheapBulk")
    expect(content).to_contain_text("4p × 10 = 40p")
    expect(content).to_contain_text("NextBulk")
    expect(content).to_contain_text("6p × 11 = 66p")
    content.locator(".copy-whisper-btn").first.click()
    assert page.evaluate("window.__lastCopiedText") == "/w CheapBulk buy 10"

    page.locator("#more-menu-btn").click()
    page.locator("#set-profit-btn").click()
    expect(content).to_contain_text("买部件 -> 卖整套")
    expect(content).to_contain_text("ROI: 35.7%")
    expect(content).to_contain_text("机会分: 48.4")
    expect(content).to_contain_text("流动性: 42")
    expect(content).to_contain_text("风险: medium")
    expect(content).to_contain_text("BpSeller_UI")
    expect(content).to_contain_text("SetBuyer_UI")
    expect(content).not_to_contain_text("SetSeller_UI")
    link_hrefs = content.locator(".trade-plan-card a").evaluate_all("nodes => nodes.map(a => a.href)")
    assert link_hrefs
    assert all(href.startswith("https://warframe.market/items/") or href.startswith("https://warframe.market/profile/") for href in link_hrefs)

    page.locator("#more-menu-btn").click()
    page.locator("#investment-btn").click()
    expect(content).to_contain_text("InvSeller_UI")
    expect(content).to_contain_text("InvBuyer_UI")

    expect(content.locator("img[data-xss='payload']")).to_have_count(0)
    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_websocket_proactive_push_renders_actionable_trade_plan(page_with_api):
    page, state = page_with_api
    open_app(page)
    page.wait_for_load_state("domcontentloaded")
    assert page.evaluate("typeof window.handleNotificationMessage") == "function"
    assert page.evaluate("typeof window.renderTradePlanCard") == "function"
    page.evaluate("""
        window.handleNotificationMessage({
            type: 'proactive_push',
            item_id: 'arcane_energize',
            item_display: 'Arcane Energize',
            push_type: 'opportunity',
            priority: 2,
            message: '利润 45p',
            action_suggestion: 'watch',
            trade_plan: {
                display_strategy: '买 21 个 R0 -> 合成 R5 -> 卖出',
                item_id: 'arcane_energize',
                required_quantity: 21,
                total_cost: 105,
                total_revenue: 150,
                profit: 45,
                roi_pct: 42.9,
                buy_steps: [{
                    label: '买入 R0', player: 'SellerWS_UI', unit_price: 5, quantity: 21, subtotal: 105,
                    market_url: 'https://warframe.market/items/arcane_energize',
                    profile_url: 'https://warframe.market/profile/SellerWS_UI',
                    whisper: '/w SellerWS_UI Hi! I want to buy.'
                }],
                sell_steps: [{
                    label: '出售 R5', player: 'BuyerWS_UI', unit_price: 150, quantity: 1, subtotal: 150,
                    market_url: 'https://warframe.market/items/arcane_energize',
                    profile_url: 'https://warframe.market/profile/BuyerWS_UI',
                    whisper: '/w BuyerWS_UI Hi! I want to sell.'
                }]
            }
        });
    """)

    chat = page.locator("#chat-messages")
    expect(chat).to_contain_text("买 21 个 R0")
    expect(chat).to_contain_text("SellerWS_UI")
    expect(chat).to_contain_text("5p × 21 = 105p")
    expect(chat).to_contain_text("BuyerWS_UI")
    chat.locator(".copy-whisper-btn").first.click()
    assert page.evaluate("window.__lastCopiedText") == "/w SellerWS_UI Hi! I want to buy."
    links = chat.locator(".trade-plan-card a").evaluate_all("nodes => nodes.map(a => a.href)")
    assert links
    assert all(href.startswith("https://warframe.market/items/") or href.startswith("https://warframe.market/profile/") for href in links)
    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_runtime_panel_renders_jobs_tasks_and_safe_state(page_with_api):
    page, state = page_with_api
    open_app(page)

    page.locator(".status-indicator").click()
    content = page.locator("#detail-content")
    expect(content).to_contain_text("运行态详情")
    expect(content).to_contain_text("收藏扫描")
    expect(content).to_contain_text("每日报告")
    expect(content).to_contain_text("external_side_effect")
    expect(content).to_contain_text("scan-1")
    expect(content).to_contain_text("goal-1")
    expect(content).to_contain_text("WxPusher")
    expect(content).to_contain_text("Feishu")
    expect(content).to_contain_text("最近工具调用")
    expect(content).to_contain_text("query_price")
    expect(content).to_contain_text("arcane_energize")

    rendered = content.text_content()
    for forbidden in ["secret-token", "Bearer abc", "app_secret", "chat_id", "UID_SECRET", "AT_SECRET"]:
        assert forbidden not in rendered
    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_tool_observability_panel_renders_history_stats_and_filters_safely(page_with_api):
    page, state = page_with_api
    open_app(page)

    page.locator("#more-menu-btn").click()
    page.locator("#tool-observability-btn").click()
    content = page.locator("#detail-content")
    expect(content).to_contain_text("工具观测")
    expect(content).to_contain_text("query_price")
    expect(content).to_contain_text("query_events")
    expect(content).to_contain_text("成功率")
    expect(content).to_contain_text("0.6667")
    expect(content).to_contain_text("调用历史")
    expect(content.locator("img[data-xss='payload']")).to_have_count(0)

    page.locator("#tool-observability-name-filter").fill("query_price")
    page.locator("#tool-observability-ok-filter").select_option("true")
    page.locator("#tool-observability-refresh-btn").click()
    page.wait_for_timeout(200)
    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_runtime_panel_handles_error_state(page_with_api):
    page, state = page_with_api
    state["runtime_error"] = True
    open_app(page)

    page.locator(".status-indicator").click()
    content = page.locator("#detail-content")
    expect(content).to_contain_text("运行态详情")
    expect(content).to_contain_text("runtime status unavailable")
    expect(content).to_contain_text("暂无任务状态")

    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_relic_detail_renders_value_analysis_and_escapes_xss(page_with_api):
    page, state = page_with_api
    open_app(page)

    page.evaluate("showRelicDrops('Lith', 'B1')")
    content = page.locator("#detail-content")

    expect(content).to_contain_text("遗物掉落")
    expect(content).to_contain_text("价值分析")
    expect(content).to_contain_text("EV 1.27p")
    expect(content).to_contain_text("最佳白金")
    expect(content).to_contain_text("掉落来源")
    expect(content.locator("img[data-xss='payload']")).to_have_count(0)
    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_memory_trace_panel_escapes_xss_payload(page_with_api):
    page, state = page_with_api
    open_app(page)

    page.locator("#more-menu-btn").click()
    page.locator("#trading-memory-btn").click()
    page.locator("#trading-memory-tab-recall-trace").click()
    page.locator("#memory-recall-query-filter").fill("充沛机会")
    page.locator("#memory-recall-item-filter").fill("arcane_energize")
    page.locator("#trading-memory-refresh-btn").click()

    content = page.locator("#detail-content")
    expect(content).to_contain_text("召回 Trace")
    expect(content).to_contain_text("arcane_energize")
    expect(content).to_contain_text("item_match")
    expect(content).to_contain_text("sell_price")
    expect(content.locator("img[data-xss='payload']")).to_have_count(0)
    last_url = state["trading_memory_requests"][-1]["url"]
    assert "/api/memory/recall" in last_url
    assert "query=" in last_url
    assert "item_name=arcane_energize" in last_url
    assert "limit=100" not in last_url
    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


def test_sidebar_static_contracts_match_warframe_player_context():
    sidebar_script = Path("warframe_agent/web/static/js/sidebar.js").read_text(encoding="utf-8")
    chart_script = Path("warframe_agent/web/static/js/chart.js").read_text(encoding="utf-8")
    combined = sidebar_script + "\n" + chart_script

    assert "'Meso': '前纪 (Meso)'" in sidebar_script
    assert "'Neo': '中纪 (Neo)'" in sidebar_script
    assert "虚空光体（Void Traces）" in sidebar_script
    assert "虚空之尘" not in sidebar_script
    anomaly_fn = sidebar_script[sidebar_script.index("async function showPriceAnomalies") : sidebar_script.index("document.getElementById('anomaly-btn')")]
    assert "openDetailPanel" in anomaly_fn
    assert "getPanelVersion" in anomaly_fn
    assert "泛刷多个奖励可分带不同遗物" in sidebar_script
    assert "定向刷某个稀有奖励时，建议 4 人同带对应光辉遗物" in sidebar_script
    assert "copyWhisperMessage('seller'" not in combined
    assert "copyWhisperMessage(" not in combined
    assert "`/w ${sellerName}" not in combined
    assert "copyProvidedWhisperMessage('${jsWhisperSell}')" in chart_script
    assert "const deviation = Number(item.deviation || 0);" in sidebar_script
    assert "const anomalyType = item.type ||" in sidebar_script
    assert "deviation_pct" not in sidebar_script
    assert "item.market_url" in sidebar_script
    assert "买入卖家" in sidebar_script
    assert "满级买家" in sidebar_script
    assert "整套市场" in sidebar_script
    assert "part_details.map" in sidebar_script



def test_chat_response_whisper_compare_and_chart_are_xss_safe(page_with_api):
    page, state = page_with_api
    open_app(page)

    page.locator("#chat-input").fill("xss regression")
    page.locator("#send-btn").click()
    agent_message = page.locator(".message.agent[data-query]").last
    expect(agent_message).to_contain_text("安全回复")
    expect(agent_message.locator("img[data-xss='chat']")).to_have_count(0)
    assert "data-xss" not in agent_message.evaluate("node => node.innerHTML")

    whisper = agent_message.locator(".whisper-command").first
    expect(whisper).to_contain_text(WHISPER_TEXT)
    whisper.locator(".whisper-copy-btn").click()
    expect(whisper.locator(".whisper-copy-btn")).to_have_text("已复制 ✓")
    assert page.evaluate("window.__lastCopiedText") == WHISPER_TEXT

    page.locator("#compare-btn").click()
    first_input = page.locator(".compare-item-input").first
    first_input.fill("arcane")
    expect(page.locator("#compare-suggestions-0 .suggestion-item")).to_have_count(1)
    expect(page.locator("#compare-suggestions-0 img[data-xss='payload']")).to_have_count(0)
    expect(page.locator("#compare-suggestions-0 .suggestion-item")).to_contain_text(XSS_TEXT)

    page.evaluate("""
        () => {
            window.compareItemIds = ['arcane_energize', 'safe_item'];
            window.renderCompareUI();
        }
    """)
    page.get_by_role("button", name="对比", exact=True).click()
    expect(page.locator("#compare-legend .compare-legend-item")).to_have_count(2)
    expect(page.locator("#compare-legend img[data-xss='payload']")).to_have_count(0)
    expect(page.locator("#compare-legend .compare-legend-item").first).to_contain_text(XSS_TEXT)

    page.evaluate("window.showPriceChart('arcane_energize', '7d')")
    expect(page.locator("#detail-content .item-detail-name")).to_contain_text(XSS_TEXT)
    expect(page.locator("#detail-content img[data-xss='payload']")).to_have_count(0)
    expect(page.locator("#detail-content .chart-legend .legend-item")).to_have_count(2)

    assert page.evaluate("window.__xssHits") == []
    assert state["console_errors"] == []
    assert state["page_errors"] == []


    page, state = page_with_api
    open_app(page)

    page.locator("#more-menu-btn").click()
    page.locator("#trading-memory-btn").click()
    expect(page.locator("#detail-content")).to_contain_text("市场快照")

    state["trading_memory_requests"].clear()
    state["trading_memory_empty"] = True
    page.locator("#trading-memory-item-filter").fill("arcane energize")
    page.locator("#trading-memory-since-filter").select_option("7d")
    page.locator("#trading-memory-limit-filter").select_option("25")
    page.locator("#trading-memory-type-filter").fill("price_monitor.scan")
    page.locator("#trading-memory-refresh-btn").click()

    expect(page.locator("#detail-content")).to_contain_text("暂无市场快照")
    last_url = state["trading_memory_requests"][-1]["url"]
    assert "item_name=arcane+energize" in last_url or "item_name=arcane%20energize" in last_url
    assert "source=price_monitor.scan" in last_url
    assert "limit=25" in last_url
    assert "since=" in last_url
    assert "undefined" not in last_url
    assert "null" not in last_url

    page.locator("#trading-memory-tab-recommendations").click()
    page.locator("#trading-memory-type-filter").fill("baro")
    page.locator("#trading-memory-refresh-btn").click()
    assert "recommendation_type=baro" in state["trading_memory_requests"][-1]["url"]

    page.locator("#trading-memory-tab-push-history").click()
    page.locator("#trading-memory-type-filter").fill("opportunity")
    page.locator("#trading-memory-refresh-btn").click()
    assert "push_type=opportunity" in state["trading_memory_requests"][-1]["url"]

    state["trading_memory_empty"] = False
    state["trading_memory_error_endpoint"] = "push-history"
    page.locator("#trading-memory-refresh-btn").click()
    expect(page.locator("#detail-content")).to_contain_text("加载推送历史失败")

    assert state["console_errors"] == []
    assert state["page_errors"] == []
