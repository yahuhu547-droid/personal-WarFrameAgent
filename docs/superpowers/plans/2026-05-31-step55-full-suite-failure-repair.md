# Step 55 Full Suite Failure Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 8 failures found in Step 54 so the previously failing targeted tests pass, and record whether the full suite is clean afterward.

**Architecture:** Treat the failures as two independent slices. Backend/chat fixes preserve the newer deterministic production path while keeping injected `model_call` tests and custom LLM usage on the prompt path. Frontend fixes harden chat rendering and WebSocket send timing without adding new UI controls or high-privilege runtime features.

**Tech Stack:** Python `.venv`, pytest, FastAPI / uvicorn, Playwright, vanilla JavaScript, PowerShell.

---

## File Structure

- Modify: `warframe_agent/chat.py`
  - Gate deterministic market-analysis fallback so injected `model_call` can still exercise prompt construction and memory injection.
- Modify: `tests/test_router.py`
  - Align the plan aggregation test with Step 35+ plan review rules by using non-sensitive plan args, while still verifying result redaction and context budgeting.
- Modify: `warframe_agent/web/static/js/chat.js`
  - Strip unsafe inline HTML fragments before Markdown rendering.
  - Wait briefly for a connecting WebSocket to open before falling back to REST.
- Modify: `docs/superpowers/plans/2026-05-31-step55-full-suite-failure-repair.md`
  - Track execution results.
- Create: `githubProduct/personal_agent_warframe_migration_step55_full_suite_failure_repair_zh.md`
  - Final repair report.
- Modify: `AGENTS.md`
  - Append Step 55 progress, failures fixed, and verification summary.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Append Step 55 implementation note.
- Modify: `md/rebuilt/10-learning-route-audit.md`
  - Append Step 55 route verification note.

## Task 55.1: Reproduce the 8 failures

- [x] **Step 1: Run the targeted failing tests before editing**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_alias_priority.py::ChatAliasPriorityTests::test_manual_alias_key_overrides_generated_duplicate_key tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_generated_alias_substring_is_detected tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_memory_alert_is_added_to_prompt tests\test_chat_rag_fallback.py::ChatRagFallbackTests::test_chat_uses_rag_result_when_alias_lookup_fails tests\test_short_name_regression.py::ShortNameRegressionTests::test_short_chinese_name_inside_sentence_is_resolved tests\test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step55-red -p no:cacheprovider
```

Expected: reproduce the Step 54 failures. If ordinary sandbox blocks Playwright or Web API startup, run the same command in the writable environment and record the exact result.

Result: ordinary sandbox reproduced the 6 non-UI failures and hit the known Playwright setup limit for the 2 UI tests: `6 failed, 2 errors`. Writable Playwright rerun was rejected by the local quota/approval layer, so UI red/green verification must be completed later in a writable environment.

## Task 55.2: Repair chat prompt-path tests without weakening production direct answers

- [x] **Step 1: Update `ChatAgent.answer`**

In `warframe_agent/chat.py`, change the market-analysis deterministic branch so it only bypasses LLM when using the default `call_ollama_chat`. The target shape is:

```python
        if _classify_chat_mode(message).mode == "market_analysis" and self.model_call is call_ollama_chat:
            result = fallback_answer(message, contexts)
            if auto_trade_note:
                result += "\n\n" + auto_trade_note
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, result, contexts)
            return result
```

Expected: injected `model_call` tests can inspect prompts and return custom answers, while the default app still uses the deterministic answer for ordinary market-analysis queries.

Result: implemented with an additional guard so pure injected-model market analysis uses the prompt path, while mixed price + guide/video wording still uses deterministic price mode to preserve the existing Bilibili-priority contract.

- [x] **Step 2: Run chat-targeted tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_alias_priority.py::ChatAliasPriorityTests::test_manual_alias_key_overrides_generated_duplicate_key tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_generated_alias_substring_is_detected tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_memory_alert_is_added_to_prompt tests\test_chat_rag_fallback.py::ChatRagFallbackTests::test_chat_uses_rag_result_when_alias_lookup_fails tests\test_short_name_regression.py::ShortNameRegressionTests::test_short_chinese_name_inside_sentence_is_resolved -q --basetemp .pytest-tmp-step55-chat -p no:cacheprovider
```

Expected: all five chat tests pass.

Result: targeted chat tests passed with `5 passed`. Broader chat regression passed with `79 passed`.

## Task 55.3: Align plan aggregation test with current safety policy

- [x] **Step 1: Update only the outdated test payload**

In `tests/test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context`, replace the sensitive plan args with safe equivalents:

```python
                    '{"tool":"query_price","args":{"item_name":"充沛","source":"unit-test"},"purpose":"查充沛"},'
                    '{"tool":"price_trend","args":{"item_name":"充沛","window":"7d"},"purpose":"查趋势"}'
```

Keep the long tool result containing `token=secret-token` so the test still verifies result redaction and budgeting. Update the forbidden list to remove values that are no longer present in the safe plan payload:

```python
        for forbidden in ["secret-token", "PLAN_TAIL_SENTINEL"]:
            self.assertNotIn(forbidden, tool_content)
```

Expected: the test matches Step 35+ behavior where plans containing sensitive argument keys are blocked rather than executed.

Result: updated only the outdated test payload and forbidden list; production plan review remains unchanged.

- [x] **Step 2: Run router-targeted tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context tests\test_plan.py -q --basetemp .pytest-tmp-step55-router -p no:cacheprovider
```

Expected: the updated router test and plan safety tests pass.

Result: router / plan / tool context regression passed with `37 passed`; broader router run passed with `101 passed`.

## Task 55.4: Repair chat rendering XSS text leak

- [x] **Step 1: Add a minimal unsafe inline HTML stripper**

In `warframe_agent/web/static/js/chat.js`, before `renderMarkdown`, add:

```javascript
function stripUnsafeInlineHtml(text) {
    return String(text || '')
        .replace(/<\s*(script|style|iframe|object|embed|img)\b[^>]*>/gi, '')
        .replace(/<\s*\/\s*(script|style|iframe|object|embed)\s*>/gi, '');
}
```

Then call it inside `renderMarkdown`:

```javascript
function renderMarkdown(text) {
    const safeText = stripUnsafeInlineHtml(text);
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        try {
            const html = marked.parse(safeText);
            return DOMPurify.sanitize(html, {
                FORBID_TAGS: ['img'],
                FORBID_ATTR: ['onerror', 'onload', 'onclick', 'data-xss']
            });
        } catch (e) {
            return escapeHtml(safeText);
        }
    }
    return escapeHtml(safeText).replace(/\n/g, '<br>');
}
```

Expected: unsafe HTML fragments do not survive as escaped attribute text, while normal text and `/w ...` whisper commands still render.

Result: implemented `stripUnsafeInlineHtml(...)`, added `data-xss` to forbidden attributes, and `node --check warframe_agent\web\static\js\chat.js` exited 0.

- [x] **Step 2: Run XSS target test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step55-xss -p no:cacheprovider
```

Expected: the XSS target test passes in a writable environment.

Result: ordinary sandbox still errors before assertions with `RuntimeError: Web server did not become ready`; writable rerun was blocked by quota/approval. The production patch is in place, but Playwright green verification remains pending.

## Task 55.5: Repair WebSocket connecting-state fallback race

- [x] **Step 1: Add a short open wait helper**

In `warframe_agent/web/static/js/chat.js`, after `ensureChatWs`, add:

```javascript
function waitForChatWsOpen(ws, timeoutMs = 300) {
    return new Promise(resolve => {
        const started = Date.now();
        const check = () => {
            if (!ws || ws.readyState === WebSocket.OPEN) {
                resolve(Boolean(ws && ws.readyState === WebSocket.OPEN));
                return;
            }
            if (ws.readyState === WebSocket.CLOSED || Date.now() - started >= timeoutMs) {
                resolve(false);
                return;
            }
            setTimeout(check, 10);
        };
        check();
    });
}
```

Then in `handleSend`, after `const ws = ensureChatWs();`, wait if it is still connecting:

```javascript
        if (ws.readyState === WebSocket.CONNECTING) {
            await waitForChatWsOpen(ws);
        }
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ message }));
        } else {
            // existing REST fallback
        }
```

Expected: the mocked WebSocket has a chance to open and deliver `status:error`, while permanently pending WebSockets still fall back to REST.

Result: implemented `waitForChatWsOpen(...)` plus `chatWsState(...)` / `isChatWsOpen(...)` helpers so both native WebSocket constants and tests' numeric mock states work.

- [x] **Step 2: Run WebSocket and REST fallback tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_rest_error_is_rendered_without_undefined_reply -q --basetemp .pytest-tmp-step55-ws -p no:cacheprovider
```

Expected: both WebSocket error and REST fallback tests pass.

Result: ordinary sandbox still errors before assertions with `RuntimeError: Web server did not become ready`; writable rerun was blocked by quota/approval. The production patch is in place, but Playwright green verification remains pending.

## Task 55.6: Final verification and documentation sync

- [ ] **Step 1: Run combined targeted verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_alias_priority.py::ChatAliasPriorityTests::test_manual_alias_key_overrides_generated_duplicate_key tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_generated_alias_substring_is_detected tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_memory_alert_is_added_to_prompt tests\test_chat_rag_fallback.py::ChatRagFallbackTests::test_chat_uses_rag_result_when_alias_lookup_fails tests\test_short_name_regression.py::ShortNameRegressionTests::test_short_chinese_name_inside_sentence_is_resolved tests\test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step55-targeted -p no:cacheprovider
```

Expected: all 8 previously failing tests pass.

Result: the 6 non-UI previously failing tests passed with `6 passed`. The 2 UI tests could not be verified in this session because the web server fixture cannot become ready in ordinary sandbox and writable rerun was rejected by quota/approval.

- [ ] **Step 2: Run full suite in writable environment**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step55-full -p no:cacheprovider
```

Expected: record exact pass/fail count. Do not claim full project green unless this command exits 0.

Result: not run in writable environment because the same writable pytest approval was rejected by the local quota/approval layer. Do not claim full project green.

- [x] **Step 3: Run syntax and diff checks**

Run:

```powershell
node --check warframe_agent\web\static\js\chat.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\chat.py warframe_agent\web\static\js\chat.js tests\test_router.py docs\superpowers\plans\2026-05-31-step55-full-suite-failure-repair.md githubProduct\personal_agent_warframe_migration_step55_full_suite_failure_repair_zh.md AGENTS.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md
```

Expected: JS check exits 0, AST prints `AST OK`, and `git diff --check` exits 0.

Result: `node --check warframe_agent\web\static\js\chat.js` exited 0; AST check printed `AST OK`; final `git diff --check` exited 0 with only LF/CRLF warnings.

- [x] **Step 4: Write Step 55 report and update AGENTS/rebuilt**

Create `githubProduct/personal_agent_warframe_migration_step55_full_suite_failure_repair_zh.md`, then append Step 55 to `AGENTS.md`, `md/rebuilt/09-personal-agent-foundation.md`, and `md/rebuilt/10-learning-route-audit.md`.

Expected: docs record root causes, files changed, exact verification output, and any remaining failures.

Result: Step 55 report, `AGENTS.md`, and `md/rebuilt` docs were updated. Step 55 remains `75% / 待评估` because Playwright and full-suite writable verification are blocked.

## Safety Boundary

- Do not install packages or download files.
- Do not upload to GitHub.
- Do not revert unrelated dirty worktree changes.
- Do not enable Browser/GUI executor, shell executor, service recovery, arbitrary trigger platform, plugin install, connector enablement, webhook/DM command entry, or real voice capability.
- Keep changes limited to the 8 Step 54 failures and required documentation sync.
