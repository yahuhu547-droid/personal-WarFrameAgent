# Prime Weapon And Missing Parts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Prime weapon set pricing and missing-parts completion cost to the local Warframe trading agent.

**Architecture:** Reuse and expand `warframe_agent/warframes.py` into a general prime-set pricing engine for warframes and weapons. Integrate deterministic output into `ChatAgent` before generic model calls.

**Tech Stack:** Python 3.7-compatible annotations, standard library `unittest`, local `data/items_full.json`, existing market helpers.

---

### Task 1: Generalize Prime Set Parsing

**Files:**
- Modify: `warframe_agent/warframes.py`
- Create: `tests/test_prime_set_generalization.py`

- [ ] **Step 1: Write failing tests for Prime weapon set and part parsing**
- [ ] **Step 2: Run tests for RED**
- [ ] **Step 3: Implement generic set grouping and weapon part detection**
- [ ] **Step 4: Run tests for GREEN**

### Task 2: Add Missing Parts Cost Calculation

**Files:**
- Modify: `warframe_agent/warframes.py`
- Create: `tests/test_missing_parts.py`

- [ ] **Step 1: Write failing tests for owned-parts detection and missing-parts totals**
- [ ] **Step 2: Run tests for RED**
- [ ] **Step 3: Implement missing-parts pricing output**
- [ ] **Step 4: Run tests for GREEN**

### Task 3: Integrate Into Chat Flow

**Files:**
- Modify: `warframe_agent/chat.py`
- Modify: `tests/test_warframe_chat_integration.py`

- [ ] **Step 1: Add failing integration tests for weapon and missing-parts questions**
- [ ] **Step 2: Update chat integration to use generalized prime set pricing**
- [ ] **Step 3: Run tests to verify GREEN**

### Task 4: Verification

**Files:**
- All changed files

- [ ] **Step 1: Run full unit tests**
- [ ] **Step 2: Run manual smoke checks for weapon set and missing-parts questions**
