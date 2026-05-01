# Warframe Trading Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local terminal Warframe market agent with Chinese item resolution, warframe.market order lookup, whisper commands, and daily Markdown reports.

**Architecture:** Use small Python modules under `warframe_agent/`: configuration, dictionary resolution, Ollama fallback, market client, formatting, report generation, and orchestration. Keep `main.py` as a thin terminal entrypoint.

**Tech Stack:** Python 3.14, standard library `unittest`, `requests`, `ollama`, `pyperclip`, local Warframe export JSON, warframe.market orders API.

---

### Task 1: Project Layout And Fixtures

**Files:**
- Create: `warframe_agent/__init__.py`
- Create: `warframe_agent/config.py`
- Create: `data/item_aliases.json`
- Create: `data/watchlist.json`
- Create: `tests/test_dictionary.py`
- Create: `tests/test_market_formatter.py`

- [ ] **Step 1: Add tests for alias lookup and order sorting**

Create `tests/test_dictionary.py` with assertions that manual Chinese aliases resolve to market ids and unknown names return no direct match. Create `tests/test_market_formatter.py` with sample orders proving sell orders sort ascending and buy orders sort descending.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m unittest discover -s tests -v`
Expected: FAIL because `warframe_agent` modules do not exist yet.

- [ ] **Step 3: Add minimal config and data files**

Create default paths, model name, and initial alias/watchlist JSON for arcanes, Prime parts, and popular mods.

### Task 2: Dictionary And LLM Resolution

**Files:**
- Create: `warframe_agent/dictionary.py`
- Create: `warframe_agent/llm.py`
- Test: `tests/test_dictionary.py`

- [ ] **Step 1: Test resolver behavior**

Test exact alias resolution, normalized English-to-market-id conversion, and fallback invocation when no dictionary match exists.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m unittest tests.test_dictionary -v`
Expected: FAIL because resolver functions are missing.

- [ ] **Step 3: Implement resolver**

Load manual aliases, build a lightweight cache from local export JSON when available, normalize names, and use an injected fallback callable for LLM resolution.

### Task 3: Market Client And Formatting

**Files:**
- Create: `warframe_agent/market.py`
- Create: `warframe_agent/formatter.py`
- Test: `tests/test_market_formatter.py`

- [ ] **Step 1: Test order filtering and whisper command generation**

Use sample orders with sell and buy types, mixed statuses, prices, and quantities. Assert only `ingame` orders appear, sellers are cheapest first, buyers highest first, and whisper commands match warframe.market wording.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m unittest tests.test_market_formatter -v`
Expected: FAIL because market and formatter modules are missing.

- [ ] **Step 3: Implement client and formatter**

Add a request function for orders, sorting helpers, result dataclasses, and terminal/Markdown formatting.

### Task 4: Agent Orchestration And Reports

**Files:**
- Create: `warframe_agent/agent.py`
- Create: `warframe_agent/report.py`
- Modify: `main.py`

- [ ] **Step 1: Wire single lookup flow**

Resolve an item name, fetch orders, format top five sellers and buyers, copy the first seller whisper command when available, and print all commands.

- [ ] **Step 2: Wire daily report flow**

Read `data/watchlist.json`, query each tracked item, print terminal summary, and write `reports/daily-YYYY-MM-DD.md`.

- [ ] **Step 3: Verify end-to-end startup**

Run: `'q' | python .\main.py`
Expected: menu prints and exits with code 0.

### Task 5: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run unit tests**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 2: Verify Ollama connectivity**

Run: `python -c "import ollama; print(ollama.generate(model='qwen2.5:1.5b', prompt='只回答OK')['response'].strip())"`
Expected: output includes `OK`.

- [ ] **Step 3: Verify market flow manually**

Run: `python .\main.py`, choose single lookup, enter `充沛赋能`, and confirm seller/buyer tables print with whisper commands.
