# Scout Push Quality Priority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Step 17 的 Scout 推送质量聚合结果温和接入主动推送发送顺序，让历史复盘更好的同优先级机会更早出现。

**Architecture:** 不改 Scout 预筛选、ROI/收益扫描、个人偏好过滤、冷却去重和硬阈值。只在 `PriceMonitor._run_proactive_push(...)` 生成 `high_priority` 后读取一次 `TradingMemoryDB.summarize_push_quality(...)`，对同 `priority` 的交易机会做稳定 tie-break，并把安全聚合提示写入 `push.data`/推送历史 metadata。

**Tech Stack:** Python dataclasses, existing `TradingMemoryDB`, pytest.

---

### Task 1: 推送质量排序红测

**Files:**
- Modify: `tests/test_proactive_push.py`

- [x] **Step 1: 添加足够样本时同优先级质量排序测试**

在 `test_run_proactive_push_deduplicates_before_limit` 附近添加辅助函数和测试：

```python
def _seed_push_quality(db, item_name: str, *, source: str, strategy: str, good: bool, count: int = 5) -> None:
    for idx in range(count):
        db.record_push(
            "opportunity",
            f"{item_name} history {idx}",
            item_name=item_name,
            metadata={
                "source": "rule_proactive_push",
                "opportunity_source": source,
                "suggestion_type": "opportunity",
                "strategy": strategy,
                "profile_url": "https://warframe.market/profile/UnsafeHistory",
                "whisper": "/w UnsafeHistory hi",
            },
        )
        db.record_opportunity_outcome(
            f"OPQ{idx}{item_name[:4]}",
            item_name,
            source,
            strategy,
            "completed" if good else "rejected",
            50,
            65 if good else 0,
            "good" if good else "bad",
            {"profile_url": "https://warframe.market/profile/UnsafeHistory"},
        )
```

测试用两个 `priority=2` 的机会，低质量在原始顺序前，高质量在后；期望发送顺序变成高质量、低质量，且两条都发送。

- [x] **Step 2: 添加低样本保持原顺序测试**

复用 `_seed_push_quality(..., count=2)`，断言低样本不会改变原始发送顺序，也不会写入 `push_quality_score`。

- [x] **Step 3: 运行红测**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_proactive_push.py -k "push_quality" --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL，因为主动推送尚未读取质量聚合并排序。

### Task 2: 温和质量排序实现

**Files:**
- Modify: `warframe_agent/monitor.py`

- [x] **Step 1: 增加安全 metadata key 和阈值常量**

新增常量：

```python
PUSH_QUALITY_HISTORY_LIMIT = 200
PUSH_QUALITY_MIN_SENT_COUNT = 5
PUSH_QUALITY_MIN_REVIEWED_COUNT = 5
```

并把 `push_quality_score`, `push_quality_reason`, `push_quality_reviewed_count`, `push_quality_good_rate`, `push_quality_false_positive_rate` 加入 `_PROACTIVE_SAFE_DATA_KEYS`。

- [x] **Step 2: 增加质量信号 helper**

新增 helper：从聚合 signals 构建 `(item, source, strategy)` lookup；对建议提取 source/strategy 候选；将足够样本转换为 `score=-1/0/1` 和安全原因。

- [x] **Step 3: 在 `_run_proactive_push` 中应用排序**

在 `high_priority = _unique_suggestions(...)` 后调用新 helper。helper 只重排相同 `priority` 的建议位置，不跨 priority 移动，不过滤任何机会。

- [x] **Step 4: 运行绿测**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_proactive_push.py -k "push_quality" --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: PASS。

### Task 3: 学习清单同步

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step28_scout_push_quality_priority_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: 新增 Step 28 学习记录**

记录学习借鉴点：质量反馈只做二级排序、低样本中性、聚合安全字段、不绕过用户偏好/冷却/ROI 排序。

- [x] **Step 2: 更新 rebuilt 总结**

在 Step 17 后续项或学习进度中补充 Step 28 已完成，并列出新的行为边界。

### Task 4: 回归验证

**Files:**
- Verify only

- [x] **Step 1: 运行主动推送和交易记忆相关测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_proactive_push.py -k "push_quality" --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed, 1 passed, 23 deselected
# GREEN: 2 passed, 23 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_proactive_push.py -k "not scan_cycle" --basetemp .pytest-tmp -p no:cacheprovider
# 24 passed, 1 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_trading_memory.py -k "push_quality or opportunity_outcome" --basetemp .pytest-tmp -p no:cacheprovider
# 6 passed, 14 deselected

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```

Note: broader `tests\test_proactive_push.py tests\test_trading_memory.py -k "push_quality or proactive_push or opportunity_outcome"` also exposed one pre-existing sandbox SQLite WAL failure in `test_scan_cycle_does_not_emit_duplicate_goal_opportunity_channel`; this plan verified the new quality behavior and proactive push suite except that environment-sensitive scan cycle test.

- [x] **Step 2: 检查差异**

Run:

```powershell
git diff --check -- warframe_agent\monitor.py tests\test_proactive_push.py docs\superpowers\plans\2026-05-27-scout-push-quality-priority.md githubProduct\personal_agent_warframe_migration_step28_scout_push_quality_priority_zh.md md\rebuilt\09-personal-agent-foundation.md
```

Result: exit code 0，仅提示 `monitor.py` 和 `test_proactive_push.py` 下次 Git 触碰时 LF 会替换为 CRLF。不提交 GitHub。
