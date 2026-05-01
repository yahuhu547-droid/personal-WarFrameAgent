from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from ..chat import ChatAgent
from ..market import fetch_orders_async, best_sellers, best_buyers
from ..memory import AgentMemory, PriceAlert, MEMORY_PATH
from ..monitor import PriceMonitor, AlertNotification
from ..names import display_item_name
from ..price_history import PriceHistoryDB

app = FastAPI(title="Warframe Trading Agent API")

chat_agent = ChatAgent()
monitor = PriceMonitor()
price_db = PriceHistoryDB()
ws_connections: list[WebSocket] = []


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class MemoryResponse(BaseModel):
    favorites: list[str]
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
        favorites=[display_item_name(item_id) for item_id in memory.favorite_items],
        alerts=[
            {"item": display_item_name(a.item_id), "direction": a.direction, "price": a.price}
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
async def get_history(item_id: str) -> JSONResponse:
    snapshots = price_db.recent(item_id, limit=50)
    return JSONResponse({
        "item_id": item_id,
        "snapshots": [
            {
                "timestamp": s.timestamp,
                "sell_price": s.sell_price,
                "buy_price": s.buy_price,
            }
            for s in snapshots
        ]
    })


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
    from ..market import fetch_orders, best_sellers, best_buyers
    from ..names import display_item_name

    results = []
    for item_name in items[:3]:  # 最多对比3个
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


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data).get("message", "")
            reply = await asyncio.to_thread(chat_agent.answer, message)
            await websocket.send_json({"reply": reply})
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
    setup_monitor()


@app.on_event("shutdown")
async def shutdown_event():
    monitor.stop()


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="root")
