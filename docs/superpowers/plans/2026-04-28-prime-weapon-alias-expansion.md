# Prime Weapon Alias Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate safe colloquial aliases for all Prime weapons so Chinese shorthand like `斯特朗p枪管` resolves correctly.

**Architecture:** Extend the item data builder with conservative shorthand generation and ambiguity filtering. Keep runtime resolution unchanged except for consuming richer generated aliases.

**Tech Stack:** Python 3.7-compatible annotations, standard library `unittest`, local `data/items_full.json`, JSON alias generation.

---

### Task 1: Alias Generation Tests

**Files:**
- Modify: `tests/test_item_data_builder.py`
- Create: `tests/test_alias_conflicts.py`

- [ ] **Step 1: Write failing tests for safe Prime weapon shorthand aliases**
- [ ] **Step 2: Run tests for RED**
- [ ] **Step 3: Assert ambiguous shorthand is skipped**

### Task 2: Builder Implementation

**Files:**
- Modify: `tools/build_item_data.py`

- [ ] **Step 1: Add conservative shorthand generator for Prime weapon groups**
- [ ] **Step 2: Add ambiguity filtering and diagnostics output**
- [ ] **Step 3: Run tests for GREEN**

### Task 3: Runtime Verification

**Files:**
- Modify: `tests/test_generated_alias_resolver.py`

- [ ] **Step 1: Add resolver regression for shorthand weapon aliases**
- [ ] **Step 2: Run targeted tests**

### Task 4: Full Verification

**Files:**
- All changed files

- [ ] **Step 1: Rebuild item data**
- [ ] **Step 2: Run full test suite**
- [ ] **Step 3: Manually verify a real query such as `斯特朗p枪管多少钱`**
