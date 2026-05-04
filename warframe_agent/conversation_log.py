from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from . import config

LOG_PATH = config.DATA_DIR / "conversation_logs.jsonl"


@dataclass
class ConversationEntry:
    user_message: str
    assistant_reply: str
    tool_calls: list[dict] | None = None
    contexts: list[str] | None = None
    timestamp: str = ""
    rating: int | None = None  # 1-5, None = unrated
    session_id: str = ""


def log_conversation(entry: ConversationEntry) -> None:
    """追加一条对话记录到 JSONL 文件。"""
    if not entry.timestamp:
        entry.timestamp = datetime.now().isoformat()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def load_conversations(limit: int = 0) -> list[ConversationEntry]:
    """加载对话记录。limit=0 表示全部。"""
    if not LOG_PATH.exists():
        return []
    entries = []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            entries.append(ConversationEntry(**data))
    if limit > 0:
        entries = entries[-limit:]
    return entries
