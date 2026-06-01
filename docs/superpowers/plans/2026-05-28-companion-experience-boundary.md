# Companion Experience Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 EchoBot / OpenHuman / OpenClaw 的语音、Live2D、陪伴式交互经验，收束为 Warframe Agent 可检查的只读体验边界和安全策略快照。

**Architecture:** 新增一个独立 `companion_experience` 模块，只负责分类用户输入是否属于文本陪伴、语音/录音/Live2D、后台陪伴任务或交易动作请求。`safety_policy` 只聚合只读策略快照和 capability，不注册 executor，不修改 `ChatAgent` 主链路。

**Tech Stack:** Python dataclass-free dict helpers, pytest, FastAPI runtime status existing safety policy path.

---

## Completion Definition

- 用户可见结果：`/api/runtime/status.safety_policy` 中出现 `companion_experience_policy` 和 `voice_companion_experience` capability，明确语音、录音、麦克风、Live2D、后台监听均未启用。
- 数据流：用户文本只进入 deterministic classifier；策略快照只返回聚合决策和 allowlist，不返回原始消息、玩家名、profile URL、私聊命令或 token。
- 验证手段：先写失败测试，再实现；目标测试通过；AST 和 diff 检查通过。
- 不做内容：不下载模型，不安装依赖，不接入平台 token，不调用真实语音服务，不录音，不开启后台监听，不新增前端控制按钮。

## File Map

- Create: `warframe_agent/companion_experience.py`
  - 负责 `classify_companion_experience_request(...)` 和 `build_companion_experience_policy()`。
- Create: `tests/test_companion_experience.py`
  - 覆盖文本陪伴、语音/Live2D/录音、后台任务、交易动作、敏感信息不泄漏。
- Modify: `warframe_agent/safety_policy.py`
  - 聚合 `companion_experience_policy`，新增 `voice_companion_experience` capability 和 guardrail。
- Modify: `tests/test_tool_registry.py`
  - 断言 runtime safety policy 包含陪伴/语音边界且不泄漏工具和消息细节。
- Modify: `tests/test_web_api.py`
  - 断言 `/api/runtime/status` 返回同样的只读策略。
- Create: `githubProduct/personal_agent_warframe_migration_step39_companion_experience_boundary_zh.md`
  - 记录来源项目、借鉴点、实现边界、验证结果。
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
  - 追加 Step 39 路线状态。
- Modify: `md/rebuilt/04-web-api-reference.md`
  - 同步 runtime status 字段。
- Modify: `md/rebuilt/06-tools-models-safety.md`
  - 同步语音/陪伴体验安全边界。
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - 同步个人 Agent 基础能力路线。
- Modify: `md/rebuilt/10-learning-route-audit.md`
  - 同步剩余队列状态。
- Modify: `AGENTS.md`
  - 同步当前进度、验证摘要、下一步计划。

### Task 1: Companion Experience Classifier

**Files:**
- Create: `tests/test_companion_experience.py`
- Create: `warframe_agent/companion_experience.py`

- [x] **Step 1: Write failing tests**

Write tests for these behaviors:

```python
def test_text_companion_request_is_allowed_without_voice_runtime():
    decision = classify_companion_experience_request("陪我聊聊今天刷图怎么不累")
    assert decision["category"] == "text_companion"
    assert decision["decision"] == "allow_text_only"
    assert decision["blocked"] is False
    assert decision["voice_runtime_required"] is False
```

```python
def test_voice_live2d_recording_requests_are_blocked_until_designed():
    for message in ["开麦克风听我说话", "给我语音回复", "启动 Live2D 桌宠"]:
        decision = classify_companion_experience_request(message)
        assert decision["decision"] == "blocked_unavailable_runtime"
        assert decision["blocked"] is True
        assert decision["requires_human_confirmation"] is True
```

```python
def test_background_companion_tasks_require_existing_confirmation_flow():
    decision = classify_companion_experience_request("一边陪我刷图一边后台盯价提醒")
    assert decision["category"] == "background_task_companion"
    assert decision["decision"] == "requires_existing_confirmation_flow"
    assert decision["blocked"] is False
    assert decision["requires_human_confirmation"] is True
```

```python
def test_trade_or_private_message_companion_requests_are_blocked():
    decision = classify_companion_experience_request("陪我直接私聊卖家并下单 /w SecretSeller hi")
    assert decision["category"] == "trade_action"
    assert decision["decision"] == "blocked_sensitive_action"
    assert decision["blocked"] is True
```

```python
def test_companion_policy_snapshot_is_aggregate_only():
    policy = build_companion_experience_policy()
    assert policy["default_mode"] == "text_only"
    assert policy["voice_enabled"] is False
    assert policy["live2d_enabled"] is False
    assert policy["background_listening_enabled"] is False
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_companion_experience.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: fail with `ModuleNotFoundError: No module named 'warframe_agent.companion_experience'`.

- [x] **Step 3: Implement minimal module**

Create:

```python
POLICY_VERSION = "2026-05-28.companion-experience-v1"

def classify_companion_experience_request(message: str) -> dict[str, Any]:
    ...

def build_companion_experience_policy() -> dict[str, Any]:
    ...
```

The implementation must:

- Use deterministic keyword checks.
- Return only category, decision, booleans, reason codes and sanitized tags.
- Avoid returning raw message content.
- Treat Warframe in-game companion/pet words as `gameplay_companion`, not voice/陪伴 UX.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_companion_experience.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: `5 passed` or more if extra focused cases are added.

### Task 2: Runtime Safety Policy Integration

**Files:**
- Modify: `tests/test_tool_registry.py`
- Modify: `tests/test_web_api.py`
- Modify: `warframe_agent/safety_policy.py`

- [x] **Step 1: Write failing runtime policy tests**

Add assertions:

```python
companion_policy = policy["companion_experience_policy"]
assert companion_policy["default_mode"] == "text_only"
assert companion_policy["voice_enabled"] is False
assert companion_policy["live2d_enabled"] is False
assert companion_policy["background_listening_enabled"] is False
assert "voice_companion_experience" in policy["capabilities"]
assert policy["capabilities"]["voice_companion_experience"]["default"] == "disabled"
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: fail with missing `companion_experience_policy` or `voice_companion_experience`. Web API may require a writable run environment because of existing SQLite WAL constraints.

- [x] **Step 3: Implement policy integration**

Modify `safety_policy.py` to:

- Import `build_companion_experience_policy`.
- Add `voice_companion_experience` capability as unavailable / disabled / explicit-enable only.
- Add `companion_experience_policy`.
- Add guardrail that voice, Live2D, microphone, recording and background listening are not exposed.

- [ ] **Step 4: Run runtime tests to verify GREEN**

Note: `tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` is green. `tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` still needs a writable runtime environment because the ordinary sandbox fails while opening SQLite WAL, and the escalation retry was blocked by a local Codex login token refresh failure.

Run the two commands from Step 2 again. If the Web API command fails from SQLite WAL permission, rerun it with approved escalation.

### Task 3: Documentation And Route Ledger Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step39_companion_experience_boundary_zh.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `AGENTS.md`

- [x] **Step 1: Write Step 39 migration note**

Record source projects, borrowed ideas, Warframe mapping, explicit non-goals, files changed and verification.

- [x] **Step 2: Append route ledger**

Append a dated Step 39 section and mark the main remaining learning queue covered. Keep Step 35 controlled confirmation chain as optional future branch.

- [x] **Step 3: Sync rebuilt docs**

Update runtime status, safety model, foundation and route audit docs so context survives future compaction.

- [x] **Step 4: Update AGENTS.md**

Add Step 39 progress row, verification summary and next step.

### Task 4: Final Verification

**Files:**
- All touched files from Tasks 1-3.

- [ ] **Step 1: Run focused tests**

Note: focused unit and runtime policy tests are green. The Web API focused command still fails during collection in the ordinary sandbox with `sqlite3.OperationalError: unable to open database file` from SQLite WAL setup; escalation retry was not available because the local Codex token refresh failed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_companion_experience.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

- [x] **Step 2: Run syntax checks**

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/companion_experience.py','warframe_agent/safety_policy.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

- [x] **Step 3: Run whitespace diff check**

```powershell
git diff --check -- warframe_agent/companion_experience.py warframe_agent/safety_policy.py tests/test_companion_experience.py tests/test_tool_registry.py tests/test_web_api.py githubProduct/personal_agent_warframe_migration_step39_companion_experience_boundary_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/04-web-api-reference.md md/rebuilt/06-tools-models-safety.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md AGENTS.md
```

Expected: exit code 0, allowing only existing Git line-ending warnings.
