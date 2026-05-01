# Prime Warframe Set Pricing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add intelligent Prime Warframe set and part pricing to the local Warframe chat agent.

**Architecture:** Create a focused `warframe_agent/warframes.py` module for parsing warframe set questions, resolving set/part item ids, querying order summaries, and rendering deterministic Chinese pricing output. Integrate this module into `ChatAgent.answer()` before generic item lookup.

**Tech Stack:** Python 3.7-compatible typing via postponed annotations, standard library `unittest`, local `data/items_full.json`, existing market order helpers.

---

### Task 1: Parse Prime Warframe Questions

**Files:**
- Create: `warframe_agent/warframes.py`
- Create: `tests/test_warframe_sets.py`

- [ ] **Step 1: Write failing parser tests**

Test `伏特p机体多少钱` resolves as a chassis part query and `伏特p一套现在多少钱` resolves as a set query.

- [ ] **Step 2: Run tests for RED**

Run: `python -m unittest tests.test_warframe_sets -v`
Expected: fail because `warframe_agent.warframes` does not exist.

- [ ] **Step 3: Implement parser**

Implement `parse_warframe_query(message, items)` returning warframe base id, query type, and optional part key.

### Task 2: Price Set And Parts

**Files:**
- Modify: `warframe_agent/warframes.py`
- Test: `tests/test_warframe_sets.py`

- [ ] **Step 1: Write failing pricing tests**

Use fake orders to prove set direct price and parts total are calculated for lowest sellers and highest buyers.

- [ ] **Step 2: Implement pricing summaries**

Implement `price_warframe_query(message, order_fetcher)` and deterministic output rendering.

### Task 3: Chat Integration

**Files:**
- Modify: `warframe_agent/chat.py`
- Test: `tests/test_warframe_chat_integration.py`

- [ ] **Step 1: Write failing integration test**

Test `ChatAgent.answer("伏特p一套现在多少钱")` returns warframe set pricing and does not call the generic model path.

- [ ] **Step 2: Integrate before generic lookup**

Call warframe query detection at the start of `ChatAgent.answer()`.

### Task 4: Verification

**Files:**
- All changed files

- [ ] **Step 1: Run unit tests**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 2: Manual smoke test**

Run a Python one-liner using `ChatAgent().answer("伏特p一套现在多少钱")` with Python 3.14 and confirm output mentions set and parts.
