# Personal Agent Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Warframe domain assistant into a more personal trading Agent by adding explicit trading profile data, opportunity outcome review, and personal opportunity scoring.

**Execution status (2026-05-25):** Core foundation implemented. Post-review fixes completed for safe opportunity metadata filtering, invalid `/pref` handling, chat/web personal-profile scan wiring, scan-level personal sorting coverage, and regression tests. Verification passed for the non-Web targeted suite plus memory/recall/rules smoke tests; `tests/test_web_api.py` and some legacy push/goal smoke tests are blocked in the current sandbox by SQLite WAL database initialization and system temp directory permissions.

**Architecture:** Keep objective market facts and user-visible trade plans in existing modules, and add a small personal layer that consumes only safe summaries. `memory.py` stores explicit user preferences, `trading_memory.py` stores reviewed opportunity outcomes, and a new `personal_scoring.py` module computes personal fit without player names, profile links, whispers, raw orders, or API secrets.

**Tech Stack:** Python dataclasses, SQLite, FastAPI, existing `AgentMemory`, existing `TradingMemoryDB`, existing opportunity modules, pytest.

---

## Scope Split

This plan covers the first personal-Agent foundation:

- Explicit trading profile preferences.
- Derived profile summary from existing memory and outcomes.
- Opportunity outcome review storage.
- Personal opportunity scoring for Mod/Arcane flips, Prime set profit, and investment results.
- Chat/API entry points for profile and review.

This plan intentionally does not implement weekly reports, UI panels, or new visual dashboards. Those should be separate plans after this foundation lands and tests pass.

## File Structure

- Modify: `warframe_agent/memory.py`
  - Add explicit fields to `TradingPreferences`.
  - Persist new preference fields.
  - Add setters for risk, budget, preferred categories, and turnaround.
- Create: `warframe_agent/personal_profile.py`
  - Build a safe, derived profile summary from `AgentMemory`.
  - Format the profile for chat/API responses.
- Modify: `warframe_agent/trading_memory.py`
  - Add `opportunity_outcomes` table and safe read/write methods.
- Create: `warframe_agent/personal_scoring.py`
  - Compute personal fit scores from safe opportunity summaries and profile preferences.
- Modify: `warframe_agent/mod_flipper.py`
  - Add `personal_score` and `personal_reasons` to `ModFlipResult`.
- Modify: `warframe_agent/set_profit.py`
  - Add `personal_score` and `personal_reasons` to `SetProfitResult`.
- Modify: `warframe_agent/investment.py`
  - Add `personal_score` and `personal_reasons` to `PrimeInvestment`.
- Modify: `warframe_agent/chat.py`
  - Add `/profile` and `/review` deterministic commands.
  - Extend `/pref` to update personal preferences.
- Modify: `warframe_agent/web/app.py`
  - Add profile and opportunity review endpoints.
- Test: `tests/test_personal_profile.py`
- Test: `tests/test_trading_memory.py`
- Test: `tests/test_personal_scoring.py`
- Test: `tests/test_chat_memory_commands.py`
- Test: `tests/test_web_api.py`

---

### Task 1: Extend Trading Preferences For Personal Profile

**Files:**
- Modify: `warframe_agent/memory.py`
- Test: `tests/test_personal_profile.py`

- [ ] **Step 1: Write failing preference persistence tests**

Create `tests/test_personal_profile.py`:

```python
from warframe_agent.memory import AgentMemory, TradingPreferences


def test_trading_preferences_normalize_personal_fields():
    prefs = TradingPreferences(
        risk_appetite="HIGH",
        budget_min=40,
        budget_max=10,
        preferred_categories=["Arcane", "prime_set", "unknown", "mod"],
        max_turnaround_days=0,
        min_roi_pct=-5,
    )

    assert prefs.risk_appetite == "high"
    assert prefs.budget_min == 10
    assert prefs.budget_max == 40
    assert prefs.preferred_categories == ["arcane", "prime_set", "mod"]
    assert prefs.max_turnaround_days == 1
    assert prefs.min_roi_pct == 0


def test_agent_memory_persists_personal_preferences(tmp_path):
    path = tmp_path / "agent_memory.json"
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=25,
        budget_max=300,
        preferred_categories=["mod", "arcane"],
        max_turnaround_days=3,
        min_roi_pct=35,
    )

    memory.save(path)
    loaded = AgentMemory.load(path)

    assert loaded.preferences.risk_appetite == "low"
    assert loaded.preferences.budget_min == 25
    assert loaded.preferences.budget_max == 300
    assert loaded.preferences.preferred_categories == ["mod", "arcane"]
    assert loaded.preferences.max_turnaround_days == 3
    assert loaded.preferences.min_roi_pct == 35


def test_set_preference_accepts_personal_profile_keys():
    memory = AgentMemory.default()

    memory = memory.set_preference("risk", "high")
    memory = memory.set_preference("budget", "50-250")
    memory = memory.set_preference("categories", "mod, arcane")
    memory = memory.set_preference("turnaround", "4")
    memory = memory.set_preference("min_roi", "45")

    assert memory.preferences.risk_appetite == "high"
    assert memory.preferences.budget_min == 50
    assert memory.preferences.budget_max == 250
    assert memory.preferences.preferred_categories == ["mod", "arcane"]
    assert memory.preferences.max_turnaround_days == 4
    assert memory.preferences.min_roi_pct == 45
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_personal_profile.py -q
```

Expected: fails because `TradingPreferences` does not yet accept the new fields.

- [ ] **Step 3: Add normalization helpers in `memory.py`**

Add below `OPPORTUNITY_FILTERS`:

```python
RISK_APPETITES = {"low", "medium", "high"}
PROFILE_CATEGORIES = {"mod", "arcane", "prime_set", "prime_part", "riven", "baro"}


def normalize_risk_appetite(value: str | None) -> str:
    normalized = (value or "medium").strip().lower()
    return normalized if normalized in RISK_APPETITES else "medium"


def normalize_profile_categories(values: list[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = re.split(r"[,，/、\s]+", values)
    else:
        raw_values = values
    result = []
    for value in raw_values:
        normalized = str(value or "").strip().lower()
        if normalized in PROFILE_CATEGORIES and normalized not in result:
            result.append(normalized)
    return result


def normalize_budget_range(budget_min: int, budget_max: int) -> tuple[int, int]:
    low = max(0, int(budget_min or 0))
    high = max(0, int(budget_max or 0))
    if high and low > high:
        low, high = high, low
    return low, high


def parse_budget_range(value: str) -> tuple[int, int] | None:
    numbers = [int(match) for match in re.findall(r"\d+", value or "")]
    if not numbers:
        return None
    if len(numbers) == 1:
        return 0, numbers[0]
    return normalize_budget_range(numbers[0], numbers[1])
```

- [ ] **Step 4: Replace `TradingPreferences` with expanded dataclass**

Replace the current `TradingPreferences` class with:

```python
@dataclass(frozen=True)
class TradingPreferences:
    platform: str = "pc"
    crossplay: bool = True
    max_results: int = 5
    opportunity_filter: str = "all"
    risk_appetite: str = "medium"
    budget_min: int = 0
    budget_max: int = 0
    preferred_categories: list[str] = field(default_factory=list)
    max_turnaround_days: int = 7
    min_roi_pct: int = 0

    def __post_init__(self):
        object.__setattr__(self, "opportunity_filter", normalize_opportunity_filter(self.opportunity_filter))
        object.__setattr__(self, "risk_appetite", normalize_risk_appetite(self.risk_appetite))
        budget_min, budget_max = normalize_budget_range(self.budget_min, self.budget_max)
        object.__setattr__(self, "budget_min", budget_min)
        object.__setattr__(self, "budget_max", budget_max)
        object.__setattr__(self, "preferred_categories", normalize_profile_categories(self.preferred_categories))
        object.__setattr__(self, "max_turnaround_days", max(1, int(self.max_turnaround_days or 1)))
        object.__setattr__(self, "min_roi_pct", max(0, int(self.min_roi_pct or 0)))
```

- [ ] **Step 5: Persist new preference fields**

In `AgentMemory.to_dict()`, extend the `"preferences"` object:

```python
"risk_appetite": self.preferences.risk_appetite,
"budget_min": self.preferences.budget_min,
"budget_max": self.preferences.budget_max,
"preferred_categories": list(self.preferences.preferred_categories),
"max_turnaround_days": self.preferences.max_turnaround_days,
"min_roi_pct": self.preferences.min_roi_pct,
```

- [ ] **Step 6: Extend `with_updated_preferences`**

Replace the method signature and `TradingPreferences(...)` call with:

```python
def with_updated_preferences(
    self,
    *,
    platform: str | None = None,
    crossplay: bool | None = None,
    max_results: int | None = None,
    opportunity_filter: str | None = None,
    risk_appetite: str | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    preferred_categories: list[str] | str | None = None,
    max_turnaround_days: int | None = None,
    min_roi_pct: int | None = None,
) -> "AgentMemory":
    return replace(
        self,
        preferences=TradingPreferences(
            platform=self.preferences.platform if platform is None else platform,
            crossplay=self.preferences.crossplay if crossplay is None else crossplay,
            max_results=self.preferences.max_results if max_results is None else max_results,
            opportunity_filter=self.preferences.opportunity_filter if opportunity_filter is None else opportunity_filter,
            risk_appetite=self.preferences.risk_appetite if risk_appetite is None else risk_appetite,
            budget_min=self.preferences.budget_min if budget_min is None else budget_min,
            budget_max=self.preferences.budget_max if budget_max is None else budget_max,
            preferred_categories=self.preferences.preferred_categories if preferred_categories is None else preferred_categories,
            max_turnaround_days=self.preferences.max_turnaround_days if max_turnaround_days is None else max_turnaround_days,
            min_roi_pct=self.preferences.min_roi_pct if min_roi_pct is None else min_roi_pct,
        ),
    )
```

- [ ] **Step 7: Extend `set_preference`**

Add these branches before `return self`:

```python
if key in {"risk", "risk_appetite"}:
    return self.with_updated_preferences(risk_appetite=value)
if key in {"budget", "budget_range"}:
    parsed = parse_budget_range(value)
    if parsed is None:
        return self
    return self.with_updated_preferences(budget_min=parsed[0], budget_max=parsed[1])
if key in {"categories", "preferred_categories"}:
    return self.with_updated_preferences(preferred_categories=value)
if key in {"turnaround", "max_turnaround_days"}:
    try:
        return self.with_updated_preferences(max_turnaround_days=int(value))
    except ValueError:
        return self
if key in {"min_roi", "min_roi_pct"}:
    try:
        return self.with_updated_preferences(min_roi_pct=int(value))
    except ValueError:
        return self
```

- [ ] **Step 8: Run tests**

Run:

```bash
python -m pytest tests/test_personal_profile.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add warframe_agent/memory.py tests/test_personal_profile.py
git commit -m "feat: add personal trading preferences"
```

---

### Task 2: Add Safe Derived Profile Summary

**Files:**
- Create: `warframe_agent/personal_profile.py`
- Test: `tests/test_personal_profile.py`

- [ ] **Step 1: Add derived profile tests**

Append to `tests/test_personal_profile.py`:

```python
from warframe_agent.goals import TradeOutcome
from warframe_agent.personal_profile import build_personal_profile, format_personal_profile


def test_build_personal_profile_combines_explicit_and_derived_data():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=20,
        budget_max=200,
        preferred_categories=["arcane"],
        max_turnaround_days=2,
        min_roi_pct=25,
    )
    memory = memory.with_common_question("充沛赋能 能倒卖吗")
    memory = memory.with_common_question("高斯 prime 一套多少钱")
    memory = memory.with_trade_outcome(TradeOutcome(
        outcome_id="out1",
        goal_id="goal1",
        action="sold",
        item_id="arcane_energize",
        price=100,
        expected_profit=20,
        actual_profit=30,
        user_feedback="good",
        timestamp="2026-05-20T10:00:00+00:00",
    ))

    profile = build_personal_profile(memory)

    assert profile.risk_appetite == "low"
    assert profile.budget_label == "20-200p"
    assert profile.preferred_categories == ["arcane"]
    assert profile.derived_categories[0] in {"arcane", "prime_set"}
    assert profile.completed_outcome_count == 1
    assert profile.total_actual_profit == 30
    assert profile.win_rate == 1.0


def test_format_personal_profile_contains_no_player_or_whisper_data():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="medium",
        budget_min=0,
        budget_max=150,
        preferred_categories=["mod"],
    )

    text = format_personal_profile(build_personal_profile(memory))

    assert "风险偏好" in text
    assert "/w " not in text
    assert "profile" not in text.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_personal_profile.py::test_build_personal_profile_combines_explicit_and_derived_data tests/test_personal_profile.py::test_format_personal_profile_contains_no_player_or_whisper_data -q
```

Expected: fails because `personal_profile.py` does not exist.

- [ ] **Step 3: Create `personal_profile.py`**

Create `warframe_agent/personal_profile.py`:

```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .memory import AgentMemory, PROFILE_CATEGORIES


_CATEGORY_LABELS = {
    "mod": "MOD",
    "arcane": "赋能",
    "prime_set": "Prime 套装",
    "prime_part": "Prime 部件",
    "riven": "紫卡",
    "baro": "Baro",
}


@dataclass(frozen=True)
class PersonalTradingProfile:
    risk_appetite: str
    budget_min: int
    budget_max: int
    budget_label: str
    preferred_categories: list[str] = field(default_factory=list)
    derived_categories: list[str] = field(default_factory=list)
    max_turnaround_days: int = 7
    min_roi_pct: int = 0
    completed_outcome_count: int = 0
    total_actual_profit: int = 0
    win_rate: float = 0.0
    summary_lines: list[str] = field(default_factory=list)


def build_personal_profile(memory: AgentMemory) -> PersonalTradingProfile:
    prefs = memory.preferences
    outcomes = list(memory.trade_outcomes)
    wins = sum(1 for outcome in outcomes if outcome.actual_profit > 0)
    total_profit = sum(int(outcome.actual_profit or 0) for outcome in outcomes)
    derived_categories = _derive_categories(memory)
    budget_label = _format_budget(prefs.budget_min, prefs.budget_max)
    summary_lines = [
        f"风险偏好={prefs.risk_appetite}",
        f"预算={budget_label}",
        f"最低ROI={prefs.min_roi_pct}%",
        f"最长周转={prefs.max_turnaround_days}天",
    ]
    if prefs.preferred_categories:
        summary_lines.append("显式偏好=" + "、".join(_category_label(c) for c in prefs.preferred_categories))
    if derived_categories:
        summary_lines.append("行为偏好=" + "、".join(_category_label(c) for c in derived_categories[:3]))
    if outcomes:
        summary_lines.append(f"历史结果={wins}/{len(outcomes)}盈利，累计{total_profit}p")
    return PersonalTradingProfile(
        risk_appetite=prefs.risk_appetite,
        budget_min=prefs.budget_min,
        budget_max=prefs.budget_max,
        budget_label=budget_label,
        preferred_categories=list(prefs.preferred_categories),
        derived_categories=derived_categories,
        max_turnaround_days=prefs.max_turnaround_days,
        min_roi_pct=prefs.min_roi_pct,
        completed_outcome_count=len(outcomes),
        total_actual_profit=total_profit,
        win_rate=round(wins / len(outcomes), 3) if outcomes else 0.0,
        summary_lines=summary_lines,
    )


def format_personal_profile(profile: PersonalTradingProfile) -> str:
    category_text = "、".join(_category_label(c) for c in profile.preferred_categories) or "未设置"
    derived_text = "、".join(_category_label(c) for c in profile.derived_categories[:5]) or "暂无"
    lines = [
        "个人交易画像",
        f"- 风险偏好: {profile.risk_appetite}",
        f"- 预算区间: {profile.budget_label}",
        f"- 偏好品类: {category_text}",
        f"- 行为推断: {derived_text}",
        f"- 最低 ROI: {profile.min_roi_pct}%",
        f"- 可接受周转: {profile.max_turnaround_days} 天内",
        f"- 历史复盘: {profile.completed_outcome_count} 条，胜率 {profile.win_rate:.0%}，累计 {profile.total_actual_profit}p",
    ]
    return "\n".join(lines)


def profile_safe_summary(profile: PersonalTradingProfile) -> dict:
    return {
        "risk_appetite": profile.risk_appetite,
        "budget_min": profile.budget_min,
        "budget_max": profile.budget_max,
        "preferred_categories": list(profile.preferred_categories),
        "derived_categories": list(profile.derived_categories[:5]),
        "max_turnaround_days": profile.max_turnaround_days,
        "min_roi_pct": profile.min_roi_pct,
        "completed_outcome_count": profile.completed_outcome_count,
        "total_actual_profit": profile.total_actual_profit,
        "win_rate": profile.win_rate,
    }


def _derive_categories(memory: AgentMemory) -> list[str]:
    counter: Counter[str] = Counter()
    for category in memory.preferences.preferred_categories:
        counter[category] += 3
    if memory.user_profile:
        for category in memory.user_profile.favorite_categories:
            if category in PROFILE_CATEGORIES:
                counter[category] += 2
    for question in memory.common_questions:
        text = question.lower()
        if "赋能" in text or "arcane" in text:
            counter["arcane"] += 1
        if "prime" in text or "一套" in text:
            counter["prime_set"] += 1
        if "mod" in text or "卡片" in text:
            counter["mod"] += 1
        if "紫卡" in text or "riven" in text:
            counter["riven"] += 1
    for outcome in memory.trade_outcomes:
        item_id = outcome.item_id.lower()
        if "arcane" in item_id:
            counter["arcane"] += 2
        elif "prime" in item_id or item_id.endswith("_set"):
            counter["prime_set"] += 2
    return [category for category, _ in counter.most_common() if category in PROFILE_CATEGORIES]


def _format_budget(budget_min: int, budget_max: int) -> str:
    if budget_min and budget_max:
        return f"{budget_min}-{budget_max}p"
    if budget_max:
        return f"0-{budget_max}p"
    if budget_min:
        return f"{budget_min}p+"
    return "未设置"


def _category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, category)
```

- [ ] **Step 4: Run profile tests**

Run:

```bash
python -m pytest tests/test_personal_profile.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add warframe_agent/personal_profile.py tests/test_personal_profile.py
git commit -m "feat: derive safe personal trading profile"
```

---

### Task 3: Store Opportunity Outcome Reviews Safely

**Files:**
- Modify: `warframe_agent/trading_memory.py`
- Test: `tests/test_trading_memory.py`

- [ ] **Step 1: Add opportunity outcome tests**

Append to `tests/test_trading_memory.py`:

```python
def test_opportunity_outcome_review_roundtrip_is_sanitized(tmp_path):
    from warframe_agent.trading_memory import TradingMemoryDB

    db = TradingMemoryDB(tmp_path / "trading_memory.db")
    db.record_opportunity_outcome(
        opportunity_id="OPABC123",
        item_name="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        status="completed",
        expected_profit=40,
        actual_profit=35,
        user_feedback="good",
        metadata={
            "safe_summary": {"roi_pct": 25, "risk_level": "medium"},
            "player": "SellerName",
            "profile_url": "https://warframe.market/profile/SellerName",
            "whisper": "/w SellerName hello",
            "token": "secret",
        },
    )

    records = db.get_opportunity_outcomes(limit=10)

    assert len(records) == 1
    record = records[0]
    assert record.opportunity_id == "OPABC123"
    assert record.status == "completed"
    assert record.actual_profit == 35
    assert record.metadata == {"safe_summary": {"roi_pct": 25, "risk_level": "medium"}}


def test_opportunity_outcomes_filter_by_status_and_item(tmp_path):
    from warframe_agent.trading_memory import TradingMemoryDB

    db = TradingMemoryDB(tmp_path / "trading_memory.db")
    db.record_opportunity_outcome("OP1", "gauss_prime_set", "set_profit", "buy_parts_sell_set", "skipped", 20, 0, "ignored", {})
    db.record_opportunity_outcome("OP2", "arcane_energize", "mod_flipper", "arcane_rank0_to_max", "completed", 40, 50, "good", {})

    records = db.get_opportunity_outcomes(status="completed", item_name="arcane_energize", limit=5)

    assert [record.opportunity_id for record in records] == ["OP2"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_trading_memory.py::test_opportunity_outcome_review_roundtrip_is_sanitized tests/test_trading_memory.py::test_opportunity_outcomes_filter_by_status_and_item -q
```

Expected: fails because `opportunity_outcomes` storage is not implemented.

- [ ] **Step 3: Add dataclass to `trading_memory.py`**

Add after `PushHistoryMemory`:

```python
@dataclass(frozen=True)
class OpportunityOutcomeMemory:
    id: int
    timestamp: str
    opportunity_id: str
    item_name: str
    source: str
    strategy: str
    status: str
    expected_profit: int
    actual_profit: int
    user_feedback: str
    metadata: dict[str, Any]
```

- [ ] **Step 4: Create table and indexes**

Inside `_ensure_tables()`, after `push_history` table creation, add:

```python
conn.execute(
    "CREATE TABLE IF NOT EXISTS opportunity_outcomes ("
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "  timestamp TEXT NOT NULL,"
    "  opportunity_id TEXT NOT NULL,"
    "  item_name TEXT NOT NULL,"
    "  source TEXT NOT NULL,"
    "  strategy TEXT NOT NULL,"
    "  status TEXT NOT NULL,"
    "  expected_profit INTEGER NOT NULL,"
    "  actual_profit INTEGER NOT NULL,"
    "  user_feedback TEXT NOT NULL,"
    "  metadata_json TEXT NOT NULL"
    ")"
)
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_opportunity_outcomes_timestamp "
    "ON opportunity_outcomes (timestamp)"
)
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_opportunity_outcomes_status_timestamp "
    "ON opportunity_outcomes (status, timestamp)"
)
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_opportunity_outcomes_item_timestamp "
    "ON opportunity_outcomes (item_name, timestamp)"
)
```

- [ ] **Step 5: Add safe metadata sanitizer**

Add near existing sanitizer helpers:

```python
_OPPORTUNITY_OUTCOME_STATUSES = {"completed", "skipped", "failed", "expired", "watching"}
_OPPORTUNITY_FEEDBACK_VALUES = {"good", "bad", "ignored", "neutral"}


def _sanitize_opportunity_outcome_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    safe: dict[str, Any] = {}
    safe_summary = metadata.get("safe_summary")
    if isinstance(safe_summary, dict):
        allowed_keys = {
            "source",
            "strategy",
            "item_id",
            "required_quantity",
            "total_cost",
            "total_revenue",
            "profit",
            "roi_pct",
            "risk_level",
            "profit_bucket",
            "plan_signature",
        }
        safe["safe_summary"] = {
            str(key): value
            for key, value in safe_summary.items()
            if key in allowed_keys and isinstance(value, (str, int, float, bool, type(None)))
        }
    for key in ("personal_score", "market_score"):
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            safe[key] = round(float(value), 2)
    reasons = metadata.get("personal_reasons")
    if isinstance(reasons, list):
        safe["personal_reasons"] = [str(reason)[:120] for reason in reasons[:6]]
    return safe


def _normalize_outcome_status(status: str) -> str:
    normalized = (status or "watching").strip().lower()
    return normalized if normalized in _OPPORTUNITY_OUTCOME_STATUSES else "watching"


def _normalize_feedback(value: str) -> str:
    normalized = (value or "neutral").strip().lower()
    return normalized if normalized in _OPPORTUNITY_FEEDBACK_VALUES else "neutral"
```

- [ ] **Step 6: Add write/read methods**

Add methods to `TradingMemoryDB` after `record_push()`:

```python
def record_opportunity_outcome(
    self,
    opportunity_id: str,
    item_name: str,
    source: str,
    strategy: str,
    status: str,
    expected_profit: int,
    actual_profit: int,
    user_feedback: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    return self._insert(
        "INSERT INTO opportunity_outcomes "
        "(timestamp, opportunity_id, item_name, source, strategy, status, expected_profit, actual_profit, user_feedback, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(),
            str(opportunity_id or "")[:32],
            _safe_memory_identifier(item_name),
            _safe_memory_identifier(source),
            _safe_memory_identifier(strategy),
            _normalize_outcome_status(status),
            int(expected_profit or 0),
            int(actual_profit or 0),
            _normalize_feedback(user_feedback),
            _to_json(_sanitize_opportunity_outcome_metadata(metadata)),
        ),
    )


def get_opportunity_outcomes(
    self,
    status: str | None = None,
    item_name: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> list[OpportunityOutcomeMemory]:
    rows = self._select(
        "SELECT id, timestamp, opportunity_id, item_name, source, strategy, status, expected_profit, actual_profit, user_feedback, metadata_json "
        "FROM opportunity_outcomes",
        filters=[
            ("status = ?", _normalize_outcome_status(status) if status else None),
            ("item_name = ?", _safe_memory_identifier(item_name) if item_name else None),
            ("source = ?", _safe_memory_identifier(source) if source else None),
        ],
        order_by="timestamp DESC",
        limit=limit,
    )
    return [
        OpportunityOutcomeMemory(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            int(row[7]),
            int(row[8]),
            row[9],
            _from_json(row[10]),
        )
        for row in rows
    ]
```

- [ ] **Step 7: Include table in cleanup**

Where cleanup iterates over table names, include `"opportunity_outcomes"`:

```python
for table in ["user_queries", "market_snapshots", "recommendations", "push_history", "opportunity_outcomes"]:
```

- [ ] **Step 8: Run tests**

Run:

```bash
python -m pytest tests/test_trading_memory.py -q
```

Expected: all trading memory tests pass.

- [ ] **Step 9: Commit**

```bash
git add warframe_agent/trading_memory.py tests/test_trading_memory.py
git commit -m "feat: store safe opportunity outcome reviews"
```

---

### Task 4: Add Personal Opportunity Scoring

**Files:**
- Create: `warframe_agent/personal_scoring.py`
- Modify: `warframe_agent/mod_flipper.py`
- Modify: `warframe_agent/set_profit.py`
- Modify: `warframe_agent/investment.py`
- Test: `tests/test_personal_scoring.py`

- [ ] **Step 1: Write scoring tests**

Create `tests/test_personal_scoring.py`:

```python
from warframe_agent.memory import AgentMemory
from warframe_agent.personal_profile import build_personal_profile
from warframe_agent.personal_scoring import score_personal_fit


def test_personal_fit_rewards_budget_category_roi_and_risk_match():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=20,
        budget_max=200,
        preferred_categories=["arcane"],
        min_roi_pct=25,
    )
    profile = build_personal_profile(memory)

    score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=45,
        roi_pct=37.5,
        risk_level="low",
        profile=profile,
    )

    assert score.personal_score >= 80
    assert "预算匹配" in score.reasons
    assert "偏好品类匹配" in score.reasons
    assert "ROI 达标" in score.reasons
    assert "风险匹配" in score.reasons


def test_personal_fit_penalizes_budget_overrun_and_risk_mismatch():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=20,
        budget_max=100,
        preferred_categories=["mod"],
        min_roi_pct=50,
    )
    profile = build_personal_profile(memory)

    score = score_personal_fit(
        item_id="gauss_prime_set",
        source="set_profit",
        strategy="buy_set_sell_parts",
        total_cost=350,
        profit=20,
        roi_pct=6.0,
        risk_level="high",
        profile=profile,
    )

    assert score.personal_score <= 35
    assert "超出预算" in score.reasons
    assert "ROI 未达偏好" in score.reasons
    assert "风险偏高" in score.reasons
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_personal_scoring.py -q
```

Expected: fails because `personal_scoring.py` does not exist.

- [ ] **Step 3: Create `personal_scoring.py`**

Create `warframe_agent/personal_scoring.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from .personal_profile import PersonalTradingProfile


@dataclass(frozen=True)
class PersonalFitScore:
    personal_score: float
    reasons: list[str] = field(default_factory=list)
    category: str = "unknown"


def score_personal_fit(
    *,
    item_id: str,
    source: str,
    strategy: str,
    total_cost: int | float,
    profit: int | float,
    roi_pct: int | float,
    risk_level: str,
    profile: PersonalTradingProfile,
) -> PersonalFitScore:
    score = 50.0
    reasons: list[str] = []
    category = infer_opportunity_category(item_id=item_id, source=source, strategy=strategy)

    if profile.budget_max > 0:
        if total_cost > profile.budget_max:
            score -= 30.0
            reasons.append("超出预算")
        elif total_cost >= profile.budget_min:
            score += 18.0
            reasons.append("预算匹配")
    elif total_cost >= 0:
        score += 5.0

    preferred = set(profile.preferred_categories or profile.derived_categories)
    if preferred and category in preferred:
        score += 18.0
        reasons.append("偏好品类匹配")
    elif preferred:
        score -= 8.0

    if roi_pct >= profile.min_roi_pct:
        score += 14.0
        reasons.append("ROI 达标")
    else:
        score -= 16.0
        reasons.append("ROI 未达偏好")

    risk = (risk_level or "medium").lower()
    if _risk_matches(profile.risk_appetite, risk):
        score += 10.0
        reasons.append("风险匹配")
    elif profile.risk_appetite == "low" and risk == "high":
        score -= 22.0
        reasons.append("风险偏高")
    elif profile.risk_appetite == "high" and risk == "low":
        score -= 4.0

    if profit > 0:
        score += min(float(profit) / 10.0, 10.0)
    else:
        score -= 20.0

    return PersonalFitScore(
        personal_score=round(max(0.0, min(100.0, score)), 1),
        reasons=reasons[:6],
        category=category,
    )


def infer_opportunity_category(*, item_id: str, source: str, strategy: str) -> str:
    text = " ".join([item_id or "", source or "", strategy or ""]).lower()
    if "arcane" in text or "赋能" in text:
        return "arcane"
    if "mod" in text:
        return "mod"
    if "riven" in text or "紫卡" in text:
        return "riven"
    if "baro" in text:
        return "baro"
    if "set" in text or "prime" in text:
        return "prime_set"
    return "unknown"


def _risk_matches(appetite: str, risk: str) -> bool:
    if appetite == "high":
        return risk in {"medium", "high"}
    if appetite == "low":
        return risk == "low"
    return risk in {"low", "medium"}
```

- [ ] **Step 4: Run scoring tests**

Run:

```bash
python -m pytest tests/test_personal_scoring.py -q
```

Expected: all scoring tests pass.

- [ ] **Step 5: Add optional fields to result dataclasses**

In `ModFlipResult`, `SetProfitResult`, and `PrimeInvestment`, add:

```python
personal_score: float = 0.0
personal_reasons: list[str] | None = None
```

- [ ] **Step 6: Add model formatter fields**

Where model formatter lines are built for these result types, append:

```python
f"personal_score={result.personal_score}",
f"personal_reasons={','.join(result.personal_reasons or [])}",
```

- [ ] **Step 7: Keep existing scanners backward compatible**

Do not require callers to pass a profile yet. Existing scan functions should continue returning `personal_score=0.0` and `personal_reasons=None` until Task 5 wires memory into call sites.

- [ ] **Step 8: Run opportunity module tests**

Run:

```bash
python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_personal_scoring.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add warframe_agent/personal_scoring.py warframe_agent/mod_flipper.py warframe_agent/set_profit.py warframe_agent/investment.py tests/test_personal_scoring.py
git commit -m "feat: score opportunities against personal profile"
```

---

### Task 5: Wire Personal Scoring Into Scans And Push Metadata

**Files:**
- Modify: `warframe_agent/mod_flipper.py`
- Modify: `warframe_agent/set_profit.py`
- Modify: `warframe_agent/investment.py`
- Modify: `warframe_agent/monitor.py`
- Test: `tests/test_mod_flipper.py`
- Test: `tests/test_set_profit.py`
- Test: `tests/test_investment.py`
- Test: `tests/test_monitor.py`

- [ ] **Step 1: Add scan tests for personal score sorting**

Add a focused unit test to each module's test file. For `tests/test_set_profit.py`, use this pattern:

```python
def test_set_profit_result_can_carry_personal_score():
    from warframe_agent.set_profit import SetProfitResult

    result = SetProfitResult(
        set_name="Gauss Prime Set",
        strategy="buy_parts_sell_set",
        best_profit=20,
        best_cost=100,
        best_revenue=120,
        roi_pct=20,
        personal_score=88.5,
        personal_reasons=["预算匹配", "偏好品类匹配"],
    )

    assert result.personal_score == 88.5
    assert result.personal_reasons == ["预算匹配", "偏好品类匹配"]
```

For `tests/test_mod_flipper.py`, use:

```python
def test_mod_flip_result_can_carry_personal_score():
    from warframe_agent.mod_flipper import ModFlipResult

    result = ModFlipResult(
        item_id="arcane_energize",
        item_name="Arcane Energize",
        rank0_buy=5,
        max_rank_sell=180,
        endo_cost=0,
        credit_tax=0,
        flip_profit=40,
        roi_pct=25.0,
        volume_48h=20,
        value_score=50.0,
        required_quantity=21,
        personal_score=91.0,
        personal_reasons=["预算匹配"],
    )

    assert result.personal_score == 91.0
    assert result.personal_reasons == ["预算匹配"]
```

For `tests/test_investment.py`, use:

```python
def test_prime_investment_can_carry_personal_score():
    from warframe_agent.investment import PrimeInvestment

    result = PrimeInvestment(
        item_id="gauss_prime_set",
        item_name="Gauss Prime Set",
        buy_cost=100,
        expected_sell=130,
        profit=30,
        roi_pct=30.0,
        quantity=1,
        total_cost=100,
        total_profit=30,
        risk_level="low",
        recommendation="buy",
        personal_score=86.0,
        personal_reasons=["ROI 达标"],
    )

    assert result.personal_score == 86.0
    assert result.personal_reasons == ["ROI 达标"]
```

- [ ] **Step 2: Run tests to verify dataclass failure**

Run:

```bash
python -m pytest tests/test_mod_flipper.py::test_mod_flip_result_can_carry_personal_score tests/test_set_profit.py::test_set_profit_result_can_carry_personal_score tests/test_investment.py::test_prime_investment_can_carry_personal_score -q
```

Expected: fails if Task 4 dataclass fields were not added.

- [ ] **Step 3: Add optional profile parameter to scan functions**

In `scan_all_mod_flips`, `scan_all_set_profits`, and `scan_prime_investments`, add an optional keyword parameter:

```python
personal_profile=None,
```

Inside each internal `_analyze(...)` helper, after a profitable result is produced and before returning it, add module-specific scoring.

For `mod_flipper.py`:

```python
if result and personal_profile is not None:
    from dataclasses import replace
    from .personal_scoring import score_personal_fit

    fit = score_personal_fit(
        item_id=result.item_id,
        source="mod_flipper",
        strategy=(result.trade_plan or {}).get("strategy", "mod_rank0_to_max"),
        total_cost=(result.trade_plan or {}).get("total_cost", result.rank0_buy),
        profit=result.flip_profit,
        roi_pct=result.roi_pct,
        risk_level=(result.trade_plan or {}).get("risk_level", "medium"),
        profile=personal_profile,
    )
    result = replace(result, personal_score=fit.personal_score, personal_reasons=fit.reasons)
```

For `set_profit.py`:

```python
if result and personal_profile is not None:
    from dataclasses import replace
    from .personal_scoring import score_personal_fit

    fit = score_personal_fit(
        item_id=result.set_item_id or result.set_name,
        source="set_profit",
        strategy=result.strategy,
        total_cost=result.best_cost,
        profit=result.best_profit,
        roi_pct=result.roi_pct,
        risk_level=result.risk_level,
        profile=personal_profile,
    )
    result = replace(result, personal_score=fit.personal_score, personal_reasons=fit.reasons)
```

For `investment.py`:

```python
if result and personal_profile is not None:
    from dataclasses import replace
    from .personal_scoring import score_personal_fit

    fit = score_personal_fit(
        item_id=result.item_id,
        source="investment",
        strategy=(result.trade_plan or {}).get("strategy", "prime_investment"),
        total_cost=result.total_cost,
        profit=result.total_profit,
        roi_pct=result.roi_pct,
        risk_level=result.risk_level,
        profile=personal_profile,
    )
    result = replace(result, personal_score=fit.personal_score, personal_reasons=fit.reasons)
```

- [ ] **Step 4: Sort by personal score when profile exists**

In each scan function, after current sorting, add:

```python
if personal_profile is not None:
    results.sort(key=lambda r: (r.personal_score, getattr(r, "opportunity_score", 0), getattr(r, "flip_profit", 0), getattr(r, "roi_pct", 0)), reverse=True)
```

For `PrimeInvestment`, use:

```python
if personal_profile is not None:
    results.sort(key=lambda r: (r.personal_score, r.total_profit, r.roi_pct), reverse=True)
```

- [ ] **Step 5: Add personal score to proactive metadata**

In `monitor.py` `_safe_proactive_metadata_from_data`, allow:

```python
"personal_score",
"personal_reasons",
```

In `_trade_plan_safe_summary_from_data`, preserve these values if present:

```python
if "personal_score" in data:
    summary["personal_score"] = data.get("personal_score")
if "personal_reasons" in data:
    summary["personal_reasons"] = list(data.get("personal_reasons") or [])[:6]
```

- [ ] **Step 6: Run targeted tests**

Run:

```bash
python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_monitor.py tests/test_personal_scoring.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add warframe_agent/mod_flipper.py warframe_agent/set_profit.py warframe_agent/investment.py warframe_agent/monitor.py tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py
git commit -m "feat: apply personal scores to opportunity scans"
```

---

### Task 6: Add Chat Commands For Profile And Opportunity Review

**Files:**
- Modify: `warframe_agent/chat.py`
- Test: `tests/test_chat_memory_commands.py`

- [ ] **Step 1: Add chat command tests**

Append to `tests/test_chat_memory_commands.py`:

```python
from warframe_agent.chat import ChatAgent
from warframe_agent.memory import AgentMemory
from warframe_agent.trading_memory import TradingMemoryDB


def test_profile_command_shows_personal_profile(tmp_path):
    memory_path = tmp_path / "agent_memory.json"
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=20,
        budget_max=200,
        preferred_categories=["arcane"],
    )
    agent = ChatAgent(memory=memory, memory_path=memory_path)

    reply = agent.answer("/profile")

    assert "个人交易画像" in reply
    assert "风险偏好" in reply
    assert "20-200p" in reply


def test_profile_pref_commands_update_memory(tmp_path):
    memory_path = tmp_path / "agent_memory.json"
    agent = ChatAgent(memory=AgentMemory.default(), memory_path=memory_path)

    assert "已更新偏好" in agent.answer("/pref risk low")
    assert "已更新偏好" in agent.answer("/pref budget 30-150")
    assert "已更新偏好" in agent.answer("/pref categories mod,arcane")

    assert agent.memory.preferences.risk_appetite == "low"
    assert agent.memory.preferences.budget_min == 30
    assert agent.memory.preferences.budget_max == 150
    assert agent.memory.preferences.preferred_categories == ["mod", "arcane"]


def test_review_command_lists_safe_opportunity_outcomes(tmp_path):
    memory_path = tmp_path / "agent_memory.json"
    db = TradingMemoryDB(tmp_path / "trading_memory.db")
    db.record_opportunity_outcome(
        "OPABC123",
        "arcane_energize",
        "mod_flipper",
        "arcane_rank0_to_max",
        "completed",
        40,
        45,
        "good",
        {"safe_summary": {"roi_pct": 35, "risk_level": "low"}},
    )
    agent = ChatAgent(memory=AgentMemory.default(), memory_path=memory_path, trading_memory_db=db)

    reply = agent.answer("/review")

    assert "机会复盘" in reply
    assert "OPABC123" in reply
    assert "arcane_energize" in reply
    assert "/w " not in reply
    assert "profile" not in reply.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_chat_memory_commands.py::test_profile_command_shows_personal_profile tests/test_chat_memory_commands.py::test_profile_pref_commands_update_memory tests/test_chat_memory_commands.py::test_review_command_lists_safe_opportunity_outcomes -q
```

Expected: fails because `/profile`, `/review`, and new `/pref` keys are not wired.

- [ ] **Step 3: Add command routing**

In `_handle_agent_command`, add:

```python
if command in {"/profile", "/画像"}:
    return self._handle_profile_command()
if command in {"/review", "/复盘"}:
    return self._handle_review_command(tokens[1:])
```

- [ ] **Step 4: Add profile handler**

Add near `_handle_preference_command`:

```python
def _handle_profile_command(self) -> str:
    from .personal_profile import build_personal_profile, format_personal_profile

    profile = build_personal_profile(self.memory)
    return format_personal_profile(profile)
```

- [ ] **Step 5: Extend preference command text and setter**

In `_handle_preference_command`, update help text to include:

```python
"修改: /pref platform pc | /pref crossplay on | /pref max 5 | /pref risk low | /pref budget 30-150 | /pref categories mod,arcane | /pref turnaround 3 | /pref min_roi 30"
```

Add branches:

```python
if key in {"risk", "risk_appetite", "budget", "budget_range", "categories", "preferred_categories", "turnaround", "max_turnaround_days", "min_roi", "min_roi_pct"}:
    updated = self.memory.set_preference(key, value)
    if updated == self.memory:
        return "偏好格式不正确。示例: /pref risk low | /pref budget 30-150 | /pref categories mod,arcane"
    self.memory = updated
    self.memory.save(self.memory_path)
    return "已更新偏好。使用 /profile 可查看个人交易画像。"
```

- [ ] **Step 6: Add review formatter**

Add to `chat.py`:

```python
def _handle_review_command(self, args: list[str]) -> str:
    if not self.trading_memory_db:
        return "暂无机会复盘数据库。"
    status = args[0] if args else None
    records = self.trading_memory_db.get_opportunity_outcomes(status=status, limit=10)
    if not records:
        return "暂无机会复盘记录。"
    lines = ["机会复盘"]
    for record in records:
        roi = record.metadata.get("safe_summary", {}).get("roi_pct", "")
        risk = record.metadata.get("safe_summary", {}).get("risk_level", "")
        detail = f"- {record.opportunity_id} {record.item_name}: {record.status}，预期 {record.expected_profit}p，实际 {record.actual_profit}p，反馈 {record.user_feedback}"
        if roi != "":
            detail += f"，ROI {roi}%"
        if risk:
            detail += f"，风险 {risk}"
        lines.append(detail)
    return "\n".join(lines)
```

- [ ] **Step 7: Update `/help` output**

Add lines:

```python
"/profile 查看个人交易画像",
"/review [completed/skipped/failed] 查看机会复盘",
```

- [ ] **Step 8: Run chat tests**

Run:

```bash
python -m pytest tests/test_chat_memory_commands.py tests/test_personal_profile.py tests/test_trading_memory.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add warframe_agent/chat.py tests/test_chat_memory_commands.py
git commit -m "feat: add personal profile and review commands"
```

---

### Task 7: Add Web API Endpoints

**Files:**
- Modify: `warframe_agent/web/app.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Add Web API tests**

Append to `tests/test_web_api.py`:

```python
def test_profile_api_returns_safe_personal_profile(client):
    response = client.get("/api/profile")

    assert response.status_code == 200
    payload = response.json()
    assert "profile" in payload
    assert "risk_appetite" in payload["profile"]
    assert "profile_url" not in str(payload).lower()
    assert "/w " not in str(payload)


def test_profile_api_updates_personal_preferences(client):
    response = client.post("/api/profile/preferences", json={
        "risk_appetite": "low",
        "budget_min": 20,
        "budget_max": 180,
        "preferred_categories": ["mod", "arcane"],
        "max_turnaround_days": 3,
        "min_roi_pct": 30,
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["risk_appetite"] == "low"
    assert payload["profile"]["budget_max"] == 180
    assert payload["profile"]["preferred_categories"] == ["mod", "arcane"]


def test_opportunity_outcomes_api_returns_safe_records(client):
    response = client.get("/api/opportunity-outcomes")

    assert response.status_code == 200
    payload = response.json()
    assert "outcomes" in payload
    assert "profile_url" not in str(payload).lower()
    assert "/w " not in str(payload)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_web_api.py::TestWebAPI::test_profile_api_returns_safe_personal_profile tests/test_web_api.py::TestWebAPI::test_profile_api_updates_personal_preferences tests/test_web_api.py::TestWebAPI::test_opportunity_outcomes_api_returns_safe_records -q
```

If tests in this file are not class-scoped, run:

```bash
python -m pytest tests/test_web_api.py -k "profile_api or opportunity_outcomes_api" -q
```

Expected: fails because endpoints do not exist.

- [ ] **Step 3: Add request model**

In `web/app.py`, near other Pydantic request models, add:

```python
class ProfilePreferencesRequest(BaseModel):
    risk_appetite: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    preferred_categories: list[str] | None = None
    max_turnaround_days: int | None = None
    min_roi_pct: int | None = None

    model_config = ConfigDict(extra="forbid")
```

- [ ] **Step 4: Add serializer**

Add helper:

```python
def _serialize_personal_profile(memory: AgentMemory) -> dict[str, Any]:
    from ..personal_profile import build_personal_profile, profile_safe_summary

    return profile_safe_summary(build_personal_profile(memory))
```

- [ ] **Step 5: Add profile endpoints**

Add routes near memory endpoints:

```python
@app.get("/api/profile")
async def get_profile() -> JSONResponse:
    memory = await _load_memory_async()
    return JSONResponse({"profile": _serialize_personal_profile(memory)})


@app.post("/api/profile/preferences")
async def update_profile_preferences(request: ProfilePreferencesRequest) -> JSONResponse:
    memory = await _load_memory_async()
    memory = memory.with_updated_preferences(
        risk_appetite=request.risk_appetite,
        budget_min=request.budget_min,
        budget_max=request.budget_max,
        preferred_categories=request.preferred_categories,
        max_turnaround_days=request.max_turnaround_days,
        min_roi_pct=request.min_roi_pct,
    )
    await _save_memory_async(memory)
    return JSONResponse({"profile": _serialize_personal_profile(memory)})
```

- [ ] **Step 6: Add opportunity outcome serializer and endpoint**

Add:

```python
def _serialize_opportunity_outcome(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "timestamp": record.timestamp,
        "opportunity_id": record.opportunity_id,
        "item_name": record.item_name,
        "source": record.source,
        "strategy": record.strategy,
        "status": record.status,
        "expected_profit": record.expected_profit,
        "actual_profit": record.actual_profit,
        "user_feedback": record.user_feedback,
        "metadata": record.metadata,
    }


@app.get("/api/opportunity-outcomes")
async def get_opportunity_outcomes(
    status: str | None = Query(None),
    item_name: str | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> JSONResponse:
    records = await asyncio.to_thread(
        trading_memory_db.get_opportunity_outcomes,
        status=status,
        item_name=item_name,
        source=source,
        limit=limit,
    )
    return JSONResponse({"outcomes": [_serialize_opportunity_outcome(record) for record in records]})
```

- [ ] **Step 7: Run Web API tests**

Run:

```bash
python -m pytest tests/test_web_api.py tests/test_personal_profile.py tests/test_trading_memory.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add warframe_agent/web/app.py tests/test_web_api.py
git commit -m "feat: expose personal profile and opportunity review APIs"
```

---

### Task 8: Update Documentation And Run Verification

**Files:**
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`

- [ ] **Step 1: Update feature scope**

In `md/rebuilt/02-feature-scope.md`, under “倒卖、投资、扫描和主动智能”, add one row:

```markdown
| 个人化交易画像与机会评分 | 保存风险、预算、偏好品类、周转和最低 ROI；结合历史复盘生成个人画像，并为 Mod/赋能、Prime 套装和投资机会输出个人评分及原因。 | `warframe_agent/personal_profile.py`、`warframe_agent/personal_scoring.py`、`warframe_agent/memory.py`、`warframe_agent/trading_memory.py` | `tests/test_personal_profile.py`、`tests/test_personal_scoring.py`、`tests/test_trading_memory.py` |
```

- [ ] **Step 2: Update user interfaces**

In `md/rebuilt/03-user-interfaces.md`, add commands:

```markdown
| `/profile`、`/画像` | 查看个人交易画像，包括风险偏好、预算、偏好品类、行为推断、最低 ROI、周转和历史复盘摘要。 |
| `/review`、`/复盘` | 查看机会复盘记录；只显示安全摘要，不展示玩家名、profile 链接或 `/w` 私聊命令。 |
```

Add `/pref` examples:

```markdown
- `/pref risk low`
- `/pref budget 30-150`
- `/pref categories mod,arcane`
- `/pref turnaround 3`
- `/pref min_roi 30`
```

- [ ] **Step 3: Update API reference**

In `md/rebuilt/04-web-api-reference.md`, under “聊天和记忆”, add:

```markdown
| GET | `/api/profile` | 获取安全的个人交易画像摘要。 |
| POST | `/api/profile/preferences` | 更新风险、预算、偏好品类、周转和最低 ROI。 |
```

Under “价格历史、交易历史和交易记忆”, add:

```markdown
| GET | `/api/opportunity-outcomes` | 查询机会复盘记录，支持 status、item_name、source 和 limit 过滤；只返回安全元数据。 |
```

- [ ] **Step 4: Update data-memory doc**

In `md/rebuilt/05-data-memory.md`, add to Agent 长期记忆:

```markdown
- 个人交易画像偏好：风险、预算区间、偏好品类、可接受周转和最低 ROI。
```

Add to 交易记忆:

```markdown
| `opportunity_outcomes` | 机会复盘记录，保存 OP ID、来源、策略、状态、预期/实际利润、用户反馈和安全元数据。 |
```

- [ ] **Step 5: Update operations/testing doc**

In `md/rebuilt/07-operations-testing.md`, add recommended verification:

```bash
python -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py tests/test_trading_memory.py tests/test_chat_memory_commands.py tests/test_web_api.py -q
python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_monitor.py -q
```

- [ ] **Step 6: Run full targeted verification**

Run:

```bash
python -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py tests/test_trading_memory.py tests/test_chat_memory_commands.py tests/test_web_api.py -q
python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_monitor.py -q
```

Expected: both commands pass.

- [ ] **Step 7: Run broader smoke if dependencies are available**

Run:

```bash
python -m pytest tests/test_memory.py tests/test_memory_recall.py tests/test_proactive_push.py tests/test_enriched_monitor.py tests/test_rules.py tests/test_goals.py -q
```

Expected: all tests pass. If dependencies are missing, record the missing package and do not change production code to hide the environment problem.

- [ ] **Step 8: Commit docs**

```bash
git add md/rebuilt/02-feature-scope.md md/rebuilt/03-user-interfaces.md md/rebuilt/04-web-api-reference.md md/rebuilt/05-data-memory.md md/rebuilt/07-operations-testing.md
git commit -m "docs: document personal agent foundation"
```

---

## Self-Review

**Spec coverage:** The plan covers explicit profile preferences, derived profile summaries, opportunity outcome reviews, personal scoring, chat/API access, and documentation. Weekly reports, UI panels, and advanced coaching are intentionally split out.

**Placeholder scan:** No task uses unresolved placeholder wording. Every implementation step includes concrete file names, code blocks, commands, and expected outcomes.

**Type consistency:** New types are `PersonalTradingProfile`, `PersonalFitScore`, and `OpportunityOutcomeMemory`. Field names are consistently `personal_score`, `personal_reasons`, `risk_appetite`, `budget_min`, `budget_max`, `preferred_categories`, `max_turnaround_days`, and `min_roi_pct`.

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-05-25-personal-agent-foundation.md`.

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using `executing-plans`, batch execution with checkpoints.
