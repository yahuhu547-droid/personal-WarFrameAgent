# Opportunity Outcome Feedback Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Feed completed opportunity review outcomes back into personal opportunity scoring so future scan results learn from the user's recorded wins and misses.

**Architecture:** Keep scoring deterministic and side-effect free. `personal_profile.py` aggregates safe outcome statistics from `AgentMemory.trade_outcomes`; `personal_scoring.py` consumes only aggregate signals and never reads SQLite, raw orders, player names, profile URLs, whispers, or opportunity IDs.

**Tech Stack:** Python dataclasses, existing `AgentMemory` / `TradeOutcome`, pytest, Markdown docs under `md/rebuilt`.

---

## File Structure

- Modify `warframe_agent/personal_profile.py`
  - Add `OutcomeFeedbackSignal`.
  - Add `outcome_feedback` to `PersonalTradingProfile`.
  - Aggregate completed JSON `trade_outcomes` into category/source/strategy safe statistics.
  - Include aggregate count in safe profile summary without exposing raw outcome records.
- Modify `warframe_agent/personal_scoring.py`
  - Apply small bounded score adjustments from matching outcome feedback.
  - Add clear, safe reason labels such as `历史策略表现好` and `历史策略需谨慎`.
- Modify `tests/test_personal_profile.py`
  - Cover safe aggregation and leakage boundaries.
- Modify `tests/test_personal_scoring.py`
  - Cover good-history boost, bad-history penalty, and minimum sample threshold.
- Create `githubProduct/personal_agent_warframe_migration_step9_opportunity_outcome_feedback_zh.md`
  - Record the learning reference and implementation summary.
- Modify `md/rebuilt/05-data-memory.md`
  - Document aggregate outcome feedback in personal profile.
- Modify `md/rebuilt/07-operations-testing.md`
  - Add Step 9 focused verification commands and current sandbox caveat.
- Modify `md/rebuilt/09-personal-agent-foundation.md`
  - Append Step 9 completion note after verification.

## Task 1: Write Failing Tests

**Files:**
- Modify: `tests/test_personal_profile.py`
- Modify: `tests/test_personal_scoring.py`

- [ ] **Step 1: Add profile aggregation test**

Add a test that creates three profitable `TradeOutcome` entries for the same inferred source/category and asserts that the profile exposes only aggregate feedback:

```python
def test_personal_profile_aggregates_outcome_feedback_safely():
    memory = AgentMemory.default()
    for index in range(3):
        memory = memory.with_trade_outcome(
            TradeOutcome(
                outcome_id=f"secret-op-{index}",
                goal_id="goal",
                action="mod_flipper",
                item_id="arcane_energize",
                price=50,
                expected_profit=20,
                actual_profit=30,
                user_feedback="good",
                timestamp="2026-05-26T00:00:00+00:00",
            )
        )

    profile = build_personal_profile(memory)

    assert profile.outcome_feedback
    signal = profile.outcome_feedback[0]
    assert signal.count == 3
    assert signal.win_count == 3
    assert signal.avg_actual_profit == 30.0
    assert signal.category == "arcane"
    serialized = str(profile_safe_summary(profile))
    for forbidden in ["secret-op", "profile_url", "/w ", "token", "SellerName"]:
        assert forbidden not in serialized
```

- [ ] **Step 2: Add scoring tests**

Add three tests:

```python
def test_personal_fit_rewards_repeated_good_outcome_feedback():
    good_profile = build_personal_profile(_memory_with_outcomes("mod_flipper", "arcane_energize", "good", 35, count=3))
    neutral_profile = build_personal_profile(AgentMemory.default())

    good_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=45,
        roi_pct=35,
        risk_level="medium",
        profile=good_profile,
    )
    neutral_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=45,
        roi_pct=35,
        risk_level="medium",
        profile=neutral_profile,
    )

    assert good_score.personal_score > neutral_score.personal_score
    assert "历史策略表现好" in good_score.reasons
```

```python
def test_personal_fit_penalizes_repeated_bad_outcome_feedback():
    bad_profile = build_personal_profile(_memory_with_outcomes("set_profit", "gauss_prime_set", "bad", -15, count=3))
    neutral_profile = build_personal_profile(AgentMemory.default())

    bad_score = score_personal_fit(
        item_id="gauss_prime_set",
        source="set_profit",
        strategy="buy_parts_sell_set",
        total_cost=160,
        profit=25,
        roi_pct=15,
        risk_level="medium",
        profile=bad_profile,
    )
    neutral_score = score_personal_fit(
        item_id="gauss_prime_set",
        source="set_profit",
        strategy="buy_parts_sell_set",
        total_cost=160,
        profit=25,
        roi_pct=15,
        risk_level="medium",
        profile=neutral_profile,
    )

    assert bad_score.personal_score < neutral_score.personal_score
    assert "历史策略需谨慎" in bad_score.reasons
```

```python
def test_personal_fit_ignores_sparse_outcome_feedback():
    sparse_profile = build_personal_profile(_memory_with_outcomes("mod_flipper", "arcane_energize", "good", 35, count=1))
    neutral_profile = build_personal_profile(AgentMemory.default())

    sparse_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=45,
        roi_pct=35,
        risk_level="medium",
        profile=sparse_profile,
    )
    neutral_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=45,
        roi_pct=35,
        risk_level="medium",
        profile=neutral_profile,
    )

    assert sparse_score.personal_score == neutral_score.personal_score
    assert "历史策略表现好" not in sparse_score.reasons
```

- [ ] **Step 3: Run red tests**

Run:

```bash
python -m pytest tests/test_personal_profile.py -k "outcome_feedback" -q
python -m pytest tests/test_personal_scoring.py -k "outcome_feedback or sparse" -q
```

Expected: fail because `outcome_feedback` and feedback-aware scoring do not exist yet.

## Task 2: Implement Safe Outcome Feedback Aggregation

**Files:**
- Modify: `warframe_agent/personal_profile.py`

- [ ] **Step 1: Add aggregate dataclass**

Add:

```python
@dataclass(frozen=True)
class OutcomeFeedbackSignal:
    key: str
    source: str
    strategy: str
    category: str
    count: int
    win_count: int
    loss_count: int
    avg_actual_profit: float
    good_rate: float
```

- [ ] **Step 2: Add profile field**

Add `outcome_feedback: list[OutcomeFeedbackSignal] = field(default_factory=list)` to `PersonalTradingProfile`.

- [ ] **Step 3: Aggregate outcomes**

Implement helper functions:

```python
def _derive_outcome_feedback(memory: AgentMemory) -> list[OutcomeFeedbackSignal]:
    buckets: dict[tuple[str, str, str], dict[str, int]] = {}
    for outcome in memory.trade_outcomes:
        source = _infer_outcome_source(outcome)
        strategy = _infer_outcome_strategy(outcome)
        category = _infer_outcome_category(outcome.item_id, source, strategy)
        key = (source, strategy, category)
        bucket = buckets.setdefault(key, {"count": 0, "wins": 0, "losses": 0, "profit": 0})
        bucket["count"] += 1
        bucket["profit"] += int(outcome.actual_profit or 0)
        feedback = str(outcome.user_feedback or "").lower()
        if outcome.actual_profit > 0 and feedback != "bad":
            bucket["wins"] += 1
        if outcome.actual_profit < 0 or feedback == "bad":
            bucket["losses"] += 1
    signals = [...]
    return sorted(signals, key=lambda signal: (signal.count, abs(signal.avg_actual_profit)), reverse=True)[:12]
```

Use only safe identifiers derived from action/item/category, not `outcome_id`, `goal_id`, raw notes, player names, URLs, or whispers.

- [ ] **Step 4: Include safe summary count**

Add to `profile_safe_summary()`:

```python
"outcome_feedback": [
    {
        "source": signal.source,
        "strategy": signal.strategy,
        "category": signal.category,
        "count": signal.count,
        "win_count": signal.win_count,
        "loss_count": signal.loss_count,
        "avg_actual_profit": signal.avg_actual_profit,
        "good_rate": signal.good_rate,
    }
    for signal in profile.outcome_feedback[:10]
],
```

- [ ] **Step 5: Run profile test**

Run:

```bash
python -m pytest tests/test_personal_profile.py -k "outcome_feedback" -q
```

Expected: pass.

## Task 3: Implement Bounded Scoring Feedback

**Files:**
- Modify: `warframe_agent/personal_scoring.py`

- [ ] **Step 1: Match aggregate feedback**

Add a helper that selects matching feedback in this order:

```python
def _matching_feedback(profile: PersonalTradingProfile, source: str, strategy: str, category: str):
    for signal in profile.outcome_feedback:
        if signal.source == source and signal.strategy == strategy and signal.category == category:
            return signal
    for signal in profile.outcome_feedback:
        if signal.source == source and signal.category == category:
            return signal
    for signal in profile.outcome_feedback:
        if signal.category == category:
            return signal
    return None
```

- [ ] **Step 2: Apply conservative adjustment**

After the profit rule in `score_personal_fit()`, add:

```python
    feedback = _matching_feedback(profile, source, strategy, category)
    if feedback and feedback.count >= 3:
        if feedback.good_rate >= 0.67 and feedback.avg_actual_profit > 0:
            score += min(10.0, 4.0 + feedback.avg_actual_profit / 20.0)
            reasons.append("历史策略表现好")
        elif feedback.good_rate <= 0.34 or feedback.avg_actual_profit < 0:
            score -= min(12.0, 5.0 + abs(feedback.avg_actual_profit) / 15.0)
            reasons.append("历史策略需谨慎")
```

Keep the final score clamp and `reasons[:6]`.

- [ ] **Step 3: Run scoring tests**

Run:

```bash
python -m pytest tests/test_personal_scoring.py -k "outcome_feedback or sparse" -q
```

Expected: pass.

## Task 4: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step9_opportunity_outcome_feedback_zh.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [ ] **Step 1: Write migration learning note**

Document:

- What was borrowed from personal-agent learning: feedback loop, aggregate memory, safe scoring.
- What was intentionally not copied: raw trace memory, player-level order storage, autonomous external actions.
- Files changed and tests.

- [ ] **Step 2: Update rebuilt docs**

Add a short note that personal profile now derives aggregate outcome feedback from `AgentMemory.trade_outcomes`, and scoring uses only aggregate `source/strategy/category/count/win/loss/avg_profit` fields.

## Task 5: Verification and Review

**Files:**
- Read/verify: modified Python and docs.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py -q
python -m pytest tests/test_mod_flipper.py -k "personal_score" -q
python -m pytest tests/test_set_profit.py -k "personal_score" -q
python -m pytest tests/test_investment.py -k "personal_score" -q
```

- [ ] **Step 2: Run syntax checks**

Run:

```bash
python -B -c "import ast, pathlib; [ast.parse(path.read_text(encoding='utf-8')) for path in map(pathlib.Path, ['warframe_agent/personal_profile.py','warframe_agent/personal_scoring.py','tests/test_personal_profile.py','tests/test_personal_scoring.py'])]; print('AST OK')"
```

- [ ] **Step 3: Subagent review**

Ask a read-only subagent to review:

- No raw `outcome_id`, `goal_id`, player, profile URL, whisper, token, or raw order fields enter safe summaries or scoring reasons.
- Score adjustment is bounded and sample-thresholded.
- Docs match implementation and do not claim Web API tests passed if not run.

- [ ] **Step 4: Record verification**

Update `md/rebuilt/09-personal-agent-foundation.md` with exact tests that were run and any sandbox caveats. Do not commit or push.
