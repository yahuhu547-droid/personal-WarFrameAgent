# Conversation Log Safe Vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the long-lived conversation log store safe summaries by default instead of raw user/assistant text that may contain player names, profile URLs, whispers, tokens, or raw tool arguments.

**Architecture:** Keep `ConversationEntry` as the public write API, but sanitize a copy inside `log_conversation(...)` before JSONL persistence. Runtime/tool history queries already expose only filtered fields; this task moves the safety boundary earlier so the file itself is safe for ordinary long-term storage. No Git commit or push will be made per user instruction.

**Tech Stack:** Python dataclasses, JSONL persistence, pytest, existing `ChatAgent` and `conversation_log` tests.

---

## File Map

- Modify: `warframe_agent/conversation_log.py`
  - Add local sanitizers for stored conversation text, contexts, and tool call dictionaries.
  - Ensure `log_conversation(...)` persists a sanitized copy and does not mutate the caller object.
- Modify: `tests/test_conversation_log.py`
  - Add unit tests proving raw messages/tool args are sanitized before persistence.
- Modify: `tests/test_chat.py`
  - Add an integration test proving a direct market answer can still show `/w Seller` to the user while the persisted conversation log does not store Seller, `/w`, profile, token, or raw market URLs.
- Create: `githubProduct/personal_agent_warframe_migration_step16_conversation_log_safe_vault_zh.md`
  - Record the learning point and verification output.
- Modify: `md/rebuilt/05-data-memory.md`
  - Document the safe log boundary.
- Modify: `md/rebuilt/07-operations-testing.md`
  - Add target verification commands.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Mark Step 16 as completed.

## Task 1: Conversation Log Safe Persistence

**Files:**
- Test: `tests/test_conversation_log.py`
- Modify: `warframe_agent/conversation_log.py`

- [ ] **Step 1: Write the failing unit test**

Add:

```python
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
        "secret-token", "token=", "/w", "Seller", "warframe.market/profile",
        "warframe.market/items", "Bearer abc", "message_context", "raw user message",
    ]:
        assert forbidden not in raw
    data = json.loads(raw)
    assert data["contexts"] == ["arcane_energize"]
    assert data["tool_calls"][0]["args_summary"]["token"] == "[REDACTED]"
    assert "message_context" not in data["tool_calls"][0]["args_summary"]
    assert entry.user_message.startswith("充沛最低卖家")
```

- [ ] **Step 2: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_conversation_log.py::test_log_conversation_sanitizes_messages_contexts_and_tool_calls_before_persisting -q
```

Expected: FAIL because `log_conversation(...)` currently writes raw text.

- [ ] **Step 3: Implement minimal safe persistence**

In `warframe_agent/conversation_log.py`, add helper functions and call them from `log_conversation(...)`:

```python
safe_entry = _safe_conversation_entry(entry)
f.write(json.dumps(asdict(safe_entry), ensure_ascii=False) + "\n")
```

The helpers must redact `/w ...`, `warframe.market/profile`, `warframe.market/items`, token/secret/Authorization/Bearer/cookie/app_secret/chat_id patterns, player labels such as `最低卖家: Seller`, internal keys such as `message_context` and `prompt`, and unsafe context strings.

- [ ] **Step 4: Run green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_conversation_log.py::test_log_conversation_sanitizes_messages_contexts_and_tool_calls_before_persisting -q
```

Expected: PASS.

## Task 2: ChatAgent Direct Trade Log Integration

**Files:**
- Test: `tests/test_chat.py`
- Modify: `warframe_agent/conversation_log.py` if the unit implementation needs one more rule.

- [ ] **Step 1: Write the failing integration test**

Add:

```python
def test_direct_market_answer_conversation_log_uses_safe_summary(self):
    import warframe_agent.conversation_log as conversation_log

    with tempfile.TemporaryDirectory() as tmp:
        old_log_path = conversation_log.LOG_PATH
        conversation_log.LOG_PATH = Path(tmp) / "conversation_logs.jsonl"
        try:
            agent = ChatAgent(
                resolver=FakeResolver(),
                order_fetcher=lambda item_id: SAMPLE_ORDERS if item_id == "arcane_energize" else [],
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "agent_memory.json",
                warframe_items=PRIME_ITEMS,
            )
            answer = agent.answer("充沛 最便宜卖家 token=secret-token")
            raw = conversation_log.LOG_PATH.read_text(encoding="utf-8")
        finally:
            conversation_log.LOG_PATH = old_log_path

    self.assertIn("最低卖家: Seller", answer)
    self.assertIn("/w Seller", answer)
    for forbidden in ["Seller", "/w", "secret-token", "warframe.market/items", "token="]:
        self.assertNotIn(forbidden, raw)
```

- [ ] **Step 2: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_direct_market_answer_conversation_log_uses_safe_summary -q
```

Expected: FAIL before safe persistence is implemented.

- [ ] **Step 3: Run green**

Run after Task 1 implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_direct_market_answer_conversation_log_uses_safe_summary -q
```

Expected: PASS.

## Task 3: Docs And Verification

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step16_conversation_log_safe_vault_zh.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [ ] **Step 1: Update docs**

Document that `conversation_logs.jsonl` now stores safe summaries by default, while user-visible chat answers may still contain copyable whispers.

- [ ] **Step 2: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_conversation_log.py tests/test_chat.py -k "conversation_log or direct_market_answer_conversation_log_uses_safe_summary or records_sanitized_user_query_summary" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/conversation_log.py','tests/test_conversation_log.py','tests/test_chat.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\conversation_log.py tests\test_conversation_log.py tests\test_chat.py docs\superpowers\plans\2026-05-26-conversation-log-safe-vault.md githubProduct\personal_agent_warframe_migration_step16_conversation_log_safe_vault_zh.md md\rebuilt\05-data-memory.md md\rebuilt\07-operations-testing.md md\rebuilt\09-personal-agent-foundation.md
```

Expected: pytest passes, AST OK, and `git diff --check` has no errors apart from possible CRLF warnings.

## Result

- Red tests confirmed `conversation_logs.jsonl` previously persisted raw `Seller`, `/w`, market URLs, and token text from direct trade answers.
- `log_conversation(...)` now persists a sanitized copy of `ConversationEntry` with `summary:v1 role=...` messages, safe contexts, and filtered tool call dictionaries.
- Initial focused verification passed:
  - `tests/test_conversation_log.py`: `12 passed`
  - chat safety memory slice: `5 passed`
  - tool router conversation log slice: `2 passed`
