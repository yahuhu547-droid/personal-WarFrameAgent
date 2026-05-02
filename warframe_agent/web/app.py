from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from ..chat import ChatAgent, build_item_context_result
from ..dictionary import normalize_lookup_key, normalize_market_id
from ..market import fetch_orders_async, best_sellers, best_buyers
from ..memory import AgentMemory, PriceAlert, MEMORY_PATH
from ..monitor import PriceMonitor, AlertNotification
from ..names import display_item_name
from ..price_history import PriceHistoryDB
from ..formatter import build_whisper

app = FastAPI(title="Warframe Trading Agent API")

chat_agent = ChatAgent()
monitor = PriceMonitor()
price_db = PriceHistoryDB()
ws_connections: list[WebSocket] = []

# 自定义别名存储
CUSTOM_ALIASES_PATH = Path(__file__).parent.parent.parent / "data" / "custom_aliases.json"


def load_custom_aliases() -> dict[str, str]:
    if not CUSTOM_ALIASES_PATH.exists():
        return {}
    try:
        with CUSTOM_ALIASES_PATH.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_custom_aliases(aliases: dict[str, str]) -> None:
    CUSTOM_ALIASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CUSTOM_ALIASES_PATH.open("w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)


def inject_custom_aliases() -> None:
    """将自定义别名注入到 ChatAgent 的 resolver 中"""
    aliases = load_custom_aliases()
    for name, item_id in aliases.items():
        key = normalize_lookup_key(name)
        if key and item_id:
            chat_agent.resolver.aliases[key] = normalize_market_id(item_id)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class MemoryResponse(BaseModel):
    favorites: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    preferences: dict[str, Any]


class FavoriteRequest(BaseModel):
    item_id: str


class AlertRequest(BaseModel):
    item_id: str
    direction: str
    price: int


class PreferenceRequest(BaseModel):
    key: str
    value: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = await asyncio.to_thread(chat_agent.answer, request.message)
    return ChatResponse(reply=reply)


@app.get("/api/memory", response_model=MemoryResponse)
async def get_memory() -> MemoryResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    prefs = memory.preferences
    if hasattr(prefs, 'platform'):
        prefs_dict = {
            "platform": prefs.platform,
            "crossplay": prefs.crossplay,
            "max_results": prefs.max_results,
        }
    else:
        prefs_dict = prefs
    return MemoryResponse(
        favorites=[
            {"display": display_item_name(item_id), "item_id": item_id}
            for item_id in memory.favorite_items
        ],
        alerts=[
            {"item": display_item_name(a.item_id), "item_id": a.item_id, "direction": a.direction, "price": a.price}
            for a in memory.price_alerts
        ],
        preferences=prefs_dict,
    )


@app.post("/api/fav")
async def add_favorite(request: FavoriteRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.add_favorite(request.item_id)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.delete("/api/fav")
async def remove_favorite(request: FavoriteRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.remove_favorite(request.item_id)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.post("/api/alert")
async def add_alert(request: AlertRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    alert = PriceAlert(item_id=request.item_id, direction=request.direction, price=request.price)
    memory = memory.add_alert(alert)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.delete("/api/alert")
async def remove_alert(request: AlertRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    alert = PriceAlert(item_id=request.item_id, direction=request.direction, price=request.price)
    memory = memory.remove_alert(alert)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.post("/api/pref")
async def set_preference(request: PreferenceRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.set_preference(request.key, request.value)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.get("/api/history/{item_id}")
async def get_history(item_id: str, range: str = "all") -> JSONResponse:
    range_map = {"24h": 24, "7d": 168, "30d": 720, "all": 0}
    hours = range_map.get(range, 0)
    if hours > 0:
        snapshots = price_db.recent_since(item_id, hours=hours)
    else:
        snapshots = price_db.recent(item_id, limit=50)
    return JSONResponse({
        "item_id": item_id,
        "range": range,
        "snapshots": [
            {
                "timestamp": s.timestamp,
                "sell_price": s.sell_price,
                "buy_price": s.buy_price,
            }
            for s in snapshots
        ]
    })


@app.get("/api/favorites_prices")
async def get_favorites_prices() -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    results = []
    for item_id in memory.favorite_items:
        try:
            orders = await fetch_orders_async(item_id)
            sellers = best_sellers(orders, limit=1)
            buyers = best_buyers(orders, limit=1)
            results.append({
                "item_id": item_id,
                "sell_price": sellers[0].platinum if sellers else None,
                "buy_price": buyers[0].platinum if buyers else None,
            })
        except Exception:
            results.append({"item_id": item_id, "sell_price": None, "buy_price": None})
    return JSONResponse({"items": results})


@app.get("/api/item_detail/{item_id}")
async def get_item_detail(item_id: str) -> JSONResponse:
    try:
        orders = await fetch_orders_async(item_id)
        ctx = build_item_context_result(item_id, orders)
        result = {
            "item_id": item_id,
            "display": display_item_name(item_id),
            "sell_price": ctx.best_sell_price,
            "buy_price": ctx.best_buy_price,
            "spread": (ctx.best_sell_price - ctx.best_buy_price) if ctx.best_sell_price and ctx.best_buy_price else None,
        }
        if ctx.best_seller:
            result["seller"] = {
                "name": ctx.best_seller.user_name,
                "price": ctx.best_seller.platinum,
                "reputation": ctx.best_seller.reputation,
            }
        if ctx.best_buyer:
            result["buyer"] = {
                "name": ctx.best_buyer.user_name,
                "price": ctx.best_buyer.platinum,
                "reputation": ctx.best_buyer.reputation,
            }
        whisper_sell = build_whisper(ctx.best_seller.user_name, item_id, ctx.best_seller.platinum, 'sell') if ctx.best_seller else None
        whisper_buy = build_whisper(ctx.best_buyer.user_name, item_id, ctx.best_buyer.platinum, 'buy') if ctx.best_buyer else None
        result["whisper_sell"] = whisper_sell
        result["whisper_buy"] = whisper_buy
        if item_id.startswith("arcane_") and ctx.best_sell_price:
            result["max_level_cost"] = ctx.best_sell_price * 21
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"item_id": item_id, "error": str(e)}, status_code=404)


@app.get("/api/report")
async def get_report() -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    report_lines = []
    report_lines.append(f"# Warframe 每日价格报告")
    report_lines.append(f"关注物品: {len(memory.favorite_items)} 个")
    report_lines.append("")
    for item_id in memory.favorite_items:
        try:
            orders = await fetch_orders_async(item_id)
            ctx = build_item_context_result(item_id, orders)
            sell = f"{ctx.best_sell_price}p" if ctx.best_sell_price else "暂无"
            buy = f"{ctx.best_buy_price}p" if ctx.best_buy_price else "暂无"
            spread = f"{ctx.best_sell_price - ctx.best_buy_price}p" if ctx.best_sell_price and ctx.best_buy_price else "-"
            report_lines.append(f"- {display_item_name(item_id)}: 卖 {sell} / 收 {buy} / 差 {spread}")
        except Exception:
            report_lines.append(f"- {display_item_name(item_id)}: 查询失败")
    return JSONResponse({"report": "\n".join(report_lines)})


@app.get("/api/suggest")
async def suggest_items(q: str = "") -> JSONResponse:
    if not q or len(q) < 1:
        return JSONResponse({"suggestions": []})

    q_lower = q.lower()
    suggestions = set()

    # 从别名和字典中搜索
    resolver = chat_agent.resolver

    # 搜索别名
    for name, item_id in resolver.aliases.items():
        if q_lower in name.lower():
            suggestions.add(name)
            if len(suggestions) >= 10:
                break

    # 搜索字典
    if len(suggestions) < 10:
        for name, item_id in resolver.dictionary.items():
            if q_lower in name.lower():
                suggestions.add(name)
                if len(suggestions) >= 10:
                    break

    return JSONResponse({"suggestions": sorted(list(suggestions))[:10]})


@app.post("/api/compare")
async def compare_items(items: list[str]) -> JSONResponse:
    results = []
    for item_name in items[:3]:
        try:
            result = chat_agent.resolver.resolve(item_name)
            orders = await fetch_orders_async(result.item_id)
            sellers = best_sellers(orders, limit=1)
            buyers = best_buyers(orders, limit=1)
            results.append({
                "name": display_item_name(result.item_id),
                "item_id": result.item_id,
                "sell_price": sellers[0].platinum if sellers else None,
                "buy_price": buyers[0].platinum if buyers else None,
            })
        except Exception as e:
            results.append({"name": item_name, "error": str(e)})
    return JSONResponse({"items": results})


@app.get("/api/aliases")
async def get_aliases() -> JSONResponse:
    aliases = load_custom_aliases()
    return JSONResponse({"aliases": [
        {"name": k, "item_id": v, "display": display_item_name(v)}
        for k, v in aliases.items()
    ]})


@app.post("/api/aliases")
async def add_alias(request: dict) -> JSONResponse:
    name = request.get("name", "").strip()
    item_id = request.get("item_id", "").strip()
    if not name or not item_id:
        return JSONResponse({"error": "名称和物品ID不能为空"}, status_code=400)
    aliases = load_custom_aliases()
    aliases[name] = item_id
    save_custom_aliases(aliases)
    inject_custom_aliases()
    return JSONResponse({"status": "ok", "name": name, "item_id": item_id})


@app.delete("/api/aliases")
async def remove_alias(request: dict) -> JSONResponse:
    name = request.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "名称不能为空"}, status_code=400)
    aliases = load_custom_aliases()
    if name in aliases:
        del aliases[name]
        save_custom_aliases(aliases)
        inject_custom_aliases()
    return JSONResponse({"status": "ok"})


@app.get("/api/search_items")
async def search_items(q: str = "") -> JSONResponse:
    """根据物品名搜索候选列表（用于别名绑定）"""
    if not q or len(q) < 1:
        return JSONResponse({"items": []})

    q_lower = q.lower()
    seen_ids = set()
    results = []

    # 搜索字典（中文名/英文名 → item_id）
    for name_key, item_id in chat_agent.resolver.dictionary.items():
        if q_lower in name_key:
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                results.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                })
                if len(results) >= 10:
                    break

    # 搜索已有的别名
    if len(results) < 10:
        for name_key, item_id in chat_agent.resolver.aliases.items():
            if q_lower in name_key and item_id not in seen_ids:
                seen_ids.add(item_id)
                results.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                })
                if len(results) >= 10:
                    break

    # 搜索生成的别名
    if len(results) < 10:
        for name_key, item_id in chat_agent.resolver.generated_aliases.items():
            if q_lower in name_key and item_id not in seen_ids:
                seen_ids.add(item_id)
                results.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                })
                if len(results) >= 10:
                    break

    return JSONResponse({"items": results})


@app.get("/api/resolve/{name}")
async def resolve_item(name: str) -> JSONResponse:
    """尝试解析物品名，返回结果或候选建议"""
    try:
        result = chat_agent.resolver.resolve(name)
        return JSONResponse({
            "found": True,
            "item_id": result.item_id,
            "source": result.source,
            "display": display_item_name(result.item_id)
        })
    except (LookupError, ValueError):
        # 搜索相似物品作为候选
        suggestions = []
        q_lower = name.lower()
        for alias_name, alias_id in chat_agent.resolver.aliases.items():
            if q_lower in alias_name or alias_name in q_lower:
                suggestions.append({"name": alias_name, "item_id": alias_id})
                if len(suggestions) >= 5:
                    break
        return JSONResponse({
            "found": False,
            "suggestions": suggestions
        })


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data).get("message", "")
            await websocket.send_json({"status": "processing"})
            reply = await asyncio.to_thread(chat_agent.answer, message)
            chunk_size = 3
            for i in range(0, len(reply), chunk_size):
                await websocket.send_json({"token": reply[i:i+chunk_size]})
                await asyncio.sleep(0.015)
            await websocket.send_json({"done": True, "reply": reply})
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    await websocket.accept()
    ws_connections.append(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_connections.remove(websocket)


async def broadcast_alert(notification: AlertNotification):
    message = {
        "type": "alert",
        "item": notification.item_display,
        "direction": notification.alert.direction,
        "price": notification.alert.price,
        "current_price": notification.current_price,
    }
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            pass


def setup_monitor():
    def on_alert_callback(notification: AlertNotification):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_alert(notification), loop)
        except Exception:
            pass

    global monitor
    monitor = PriceMonitor(on_alert=on_alert_callback)
    monitor.start()


@app.on_event("startup")
async def startup_event():
    inject_custom_aliases()
    setup_monitor()


@app.on_event("shutdown")
async def shutdown_event():
    monitor.stop()


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="root")
