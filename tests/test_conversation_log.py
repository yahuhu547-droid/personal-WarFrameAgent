import json

from warframe_agent.conversation_log import (
    ConversationEntry,
    load_conversations,
    log_conversation,
    query_tool_call_history,
    query_tool_call_stats,
)


def test_conversation_log_round_trips_tool_calls(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    tool_calls = [{
        "tool_name": "query_price",
        "args_summary": {"item_name": "充沛"},
        "ok": True,
        "error": None,
        "duration_ms": 1.23,
        "timestamp": "2026-05-17T00:00:00+00:00",
    }]
    log_conversation(ConversationEntry(
        user_message="充沛多少钱",
        assistant_reply="45p",
        tool_calls=tool_calls,
    ))

    raw = log_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["tool_calls"] == tool_calls

    entries = load_conversations()
    assert len(entries) == 1
    assert entries[0].tool_calls == tool_calls


def test_log_conversation_sanitizes_messages_contexts_and_tool_calls_before_persisting(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    entry = ConversationEntry(
        user_message="充沛最低卖家 token=secret-token /w Seller hi",
        assistant_reply=(
            "最低卖家: Seller，价格 5p\n"
            "购买私聊: /w Seller Hi! I want to buy.\n"
            "市场链接: https://warframe.market/items/arcane_energize\n"
            "profile: https://warframe.market/profile/Seller"
        ),
        contexts=["arcane_energize", "unsafe context token=secret-token"],
        tool_calls=[{
            "tool_name": "query_price",
            "args_summary": {
                "item_name": "arcane_energize",
                "token": "secret-token",
                "message_context": "raw user message",
            },
            "error": "Authorization: Bearer abc token=secret-token",
            "message_context": "raw user message",
        }],
    )

    log_conversation(entry)

    raw = log_path.read_text(encoding="utf-8")
    for forbidden in [
        "secret-token",
        "token=",
        "/w",
        "Seller",
        "warframe.market/profile",
        "warframe.market/items",
        "Bearer abc",
        "message_context",
        "raw user message",
    ]:
        assert forbidden not in raw
    data = json.loads(raw)
    assert data["contexts"] == ["arcane_energize"]
    assert data["tool_calls"][0]["args_summary"]["token"] == "[REDACTED]"
    assert "message_context" not in data["tool_calls"][0]["args_summary"]
    assert entry.user_message.startswith("充沛最低卖家")


def test_query_tool_call_history_returns_recent_flattened_tool_calls(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    log_conversation(ConversationEntry(
        user_message="你好",
        assistant_reply="你好",
        timestamp="2026-05-17T00:00:00",
    ))
    log_conversation(ConversationEntry(
        user_message="充沛多少钱",
        assistant_reply="45p",
        timestamp="2026-05-17T00:01:00",
        session_id="s1",
        contexts=["arcane_energize"],
        tool_calls=[{
            "tool_name": "query_price",
            "args_summary": {"item_name": "充沛"},
            "ok": True,
            "error": None,
            "duration_ms": 1.23,
            "timestamp": "2026-05-17T00:01:01+00:00",
        }],
    ))
    log_conversation(ConversationEntry(
        user_message="查活动和紫卡",
        assistant_reply="结果",
        timestamp="2026-05-17T00:02:00",
        session_id="s2",
        tool_calls=[
            {
                "tool_name": "query_events",
                "args_summary": {},
                "ok": True,
                "error": None,
                "duration_ms": 2.0,
                "timestamp": "2026-05-17T00:02:01+00:00",
            },
            {
                "tool_name": "riven_search",
                "args_summary": {"weapon": "绝路"},
                "ok": False,
                "error": "缺少参数",
                "duration_ms": 3.0,
                "timestamp": "2026-05-17T00:02:02+00:00",
            },
        ],
    ))

    history = query_tool_call_history()

    assert [record["tool_name"] for record in history] == ["riven_search", "query_events", "query_price"]
    assert history[0]["tool_timestamp"] == "2026-05-17T00:02:02+00:00"
    assert history[0]["conversation_timestamp"] == "2026-05-17T00:02:00"
    assert history[0]["session_id"] == "s2"
    assert history[2]["contexts"] == ["arcane_energize"]


def test_query_tool_call_history_filters_by_tool_name_ok_and_session_id(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    log_conversation(ConversationEntry(
        user_message="a",
        assistant_reply="a",
        session_id="s1",
        timestamp="2026-05-17T00:00:00",
        tool_calls=[{"tool_name": "query_price", "ok": True, "timestamp": "t1"}],
    ))
    log_conversation(ConversationEntry(
        user_message="b",
        assistant_reply="b",
        session_id="s2",
        timestamp="2026-05-17T00:01:00",
        tool_calls=[{"tool_name": "query_price", "ok": False, "timestamp": "t2"}],
    ))
    log_conversation(ConversationEntry(
        user_message="c",
        assistant_reply="c",
        session_id="s2",
        timestamp="2026-05-17T00:02:00",
        tool_calls=[{"tool_name": "query_events", "ok": True, "timestamp": "t3"}],
    ))

    assert [record["tool_timestamp"] for record in query_tool_call_history(tool_name="query_price")] == ["t2", "t1"]
    assert [record["tool_timestamp"] for record in query_tool_call_history(ok=True)] == ["t3", "t1"]
    assert [record["tool_timestamp"] for record in query_tool_call_history(session_id="s2")] == ["t3", "t2"]
    combined = query_tool_call_history(tool_name="query_price", ok=False, session_id="s2")
    assert len(combined) == 1
    assert combined[0]["tool_timestamp"] == "t2"


def test_query_tool_call_history_respects_limit(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    for index in range(5):
        log_conversation(ConversationEntry(
            user_message=str(index),
            assistant_reply=str(index),
            timestamp=f"2026-05-17T00:0{index}:00",
            tool_calls=[{"tool_name": "query_price", "ok": True, "timestamp": f"t{index}"}],
        ))

    assert [record["tool_timestamp"] for record in query_tool_call_history(limit=2)] == ["t4", "t3"]
    assert query_tool_call_history(limit=0) == []
    assert query_tool_call_history(limit=-1) == []


def test_query_tool_call_history_handles_missing_file_and_malformed_records(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    assert query_tool_call_history() == []

    log_path.write_text(
        "not-json\n"
        + json.dumps({
            "user_message": "bad",
            "assistant_reply": "bad",
            "tool_calls": "not-list",
        }, ensure_ascii=False) + "\n"
        + json.dumps({
            "user_message": "mixed",
            "assistant_reply": "mixed",
            "tool_calls": ["bad", {"tool_name": "query_price", "ok": True, "timestamp": "valid"}],
            "timestamp": "2026-05-17T00:00:00",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    history = query_tool_call_history()

    assert len(history) == 1
    assert history[0]["tool_timestamp"] == "valid"


def test_query_tool_call_history_excludes_unsafe_conversation_fields(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    log_conversation(ConversationEntry(
        user_message="secret user message",
        assistant_reply="secret assistant reply",
        tool_calls=[{
            "tool_name": "query_price",
            "args_summary": {"item_name": "充沛"},
            "ok": True,
            "error": None,
            "duration_ms": 1.0,
            "timestamp": "tool-time",
            "arguments": {"item_name": "raw"},
            "content": "raw result",
            "message_context": "secret user message",
            "prompt": "raw prompt",
        }],
    ))

    record = query_tool_call_history()[0]

    assert "user_message" not in record
    assert "assistant_reply" not in record
    assert "arguments" not in record
    assert "content" not in record
    assert "message_context" not in record
    assert "prompt" not in record


def empty_tool_stats():
    return {
        "total_calls": 0,
        "success_count": 0,
        "failure_count": 0,
        "unknown_count": 0,
        "success_rate": 0.0,
        "duration_ms": {
            "count": 0,
            "avg": None,
            "min": None,
            "max": None,
        },
        "by_tool": {},
        "top_tools": [],
    }


def test_query_tool_call_stats_returns_empty_stats_for_missing_file_and_zero_limit(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    assert query_tool_call_stats() == empty_tool_stats()

    log_conversation(ConversationEntry(
        user_message="充沛多少钱",
        assistant_reply="45p",
        tool_calls=[{"tool_name": "query_price", "ok": True, "duration_ms": 1.0}],
    ))

    assert query_tool_call_stats(limit=0) == empty_tool_stats()
    assert query_tool_call_stats(limit=-1) == empty_tool_stats()


def test_query_tool_call_stats_aggregates_counts_rates_and_durations(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    log_conversation(ConversationEntry(
        user_message="stats",
        assistant_reply="stats",
        tool_calls=[
            {"tool_name": "query_price", "ok": True, "duration_ms": 10.0},
            {"tool_name": "query_price", "ok": False, "duration_ms": 20.0},
            {"tool_name": "query_events", "ok": "unknown", "duration_ms": 30.0},
        ],
    ))

    stats = query_tool_call_stats()

    assert stats["total_calls"] == 3
    assert stats["success_count"] == 1
    assert stats["failure_count"] == 1
    assert stats["unknown_count"] == 1
    assert stats["success_rate"] == 0.3333
    assert stats["duration_ms"] == {
        "count": 3,
        "avg": 20.0,
        "min": 10.0,
        "max": 30.0,
    }


def test_query_tool_call_stats_groups_by_tool_and_top_tools(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    log_conversation(ConversationEntry(
        user_message="stats",
        assistant_reply="stats",
        tool_calls=[
            {"tool_name": "query_price", "ok": True, "duration_ms": 10.0},
            {"tool_name": "query_events", "ok": True, "duration_ms": 5.0},
            {"tool_name": "query_price", "ok": False, "duration_ms": 30.0},
            {"tool_name": "riven_search", "ok": True, "duration_ms": 15.0},
            {"tool_name": "query_events", "ok": False, "duration_ms": 25.0},
        ],
    ))

    stats = query_tool_call_stats()

    assert stats["by_tool"]["query_price"] == {
        "total_calls": 2,
        "success_count": 1,
        "failure_count": 1,
        "unknown_count": 0,
        "success_rate": 0.5,
        "duration_ms": {
            "count": 2,
            "avg": 20.0,
            "min": 10.0,
            "max": 30.0,
        },
    }
    assert stats["by_tool"]["query_events"]["total_calls"] == 2
    assert stats["top_tools"] == [
        {"tool_name": "query_events", "total_calls": 2},
        {"tool_name": "query_price", "total_calls": 2},
        {"tool_name": "riven_search", "total_calls": 1},
    ]


def test_query_tool_call_stats_filters_by_tool_name_session_id_and_limit(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    log_conversation(ConversationEntry(
        user_message="old",
        assistant_reply="old",
        session_id="s1",
        timestamp="2026-05-17T00:00:00",
        tool_calls=[{"tool_name": "query_price", "ok": True, "duration_ms": 10.0}],
    ))
    log_conversation(ConversationEntry(
        user_message="new",
        assistant_reply="new",
        session_id="s2",
        timestamp="2026-05-17T00:01:00",
        tool_calls=[
            {"tool_name": "query_price", "ok": False, "duration_ms": 20.0},
            {"tool_name": "query_events", "ok": True, "duration_ms": 30.0},
        ],
    ))

    price_stats = query_tool_call_stats(tool_name="query_price")
    assert price_stats["total_calls"] == 2
    assert set(price_stats["by_tool"]) == {"query_price"}

    session_stats = query_tool_call_stats(session_id="s2")
    assert session_stats["total_calls"] == 2
    assert session_stats["success_count"] == 1
    assert session_stats["failure_count"] == 1

    limited_stats = query_tool_call_stats(limit=1)
    assert limited_stats["total_calls"] == 1
    assert limited_stats["by_tool"]["query_events"]["total_calls"] == 1


def test_query_tool_call_stats_ignores_bad_duration_and_excludes_unsafe_fields(tmp_path, monkeypatch):
    import warframe_agent.conversation_log as conversation_log

    log_path = tmp_path / "conversation_logs.jsonl"
    monkeypatch.setattr(conversation_log, "LOG_PATH", log_path)

    log_conversation(ConversationEntry(
        user_message="secret user message",
        assistant_reply="secret assistant reply",
        contexts=["secret_context"],
        tool_calls=[
            {
                "tool_name": "query_price",
                "ok": True,
                "duration_ms": "bad",
                "args_summary": {"item_name": "充沛"},
                "arguments": {"item_name": "raw"},
                "content": "raw result",
                "error": "raw error",
                "message_context": "secret user message",
                "prompt": "raw prompt",
            },
            {"ok": None, "duration_ms": 12.0},
        ],
    ))

    stats = query_tool_call_stats()
    stats_text = json.dumps(stats, ensure_ascii=False)

    assert stats["total_calls"] == 2
    assert stats["unknown_count"] == 1
    assert stats["duration_ms"] == {"count": 1, "avg": 12.0, "min": 12.0, "max": 12.0}
    assert "unknown" in stats["by_tool"]
    for unsafe in (
        "args_summary",
        "arguments",
        "content",
        "raw error",
        "user_message",
        "secret user message",
        "assistant_reply",
        "secret assistant reply",
        "contexts",
        "secret_context",
        "prompt",
        "message_context",
    ):
        assert unsafe not in stats_text
