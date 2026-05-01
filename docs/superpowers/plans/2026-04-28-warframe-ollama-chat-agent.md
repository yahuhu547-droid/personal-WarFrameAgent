# Warframe Ollama Chat Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a custom Ollama model builder and project-powered conversational Warframe trading assistant.

**Architecture:** Add focused modules for item display names and chat orchestration. Keep market lookup, dictionary resolution, and report generation reusable. Add a tools script that generates an Ollama Modelfile from local aliases and watchlist data.

**Tech Stack:** Python 3.14, standard library `unittest`, `requests`, `ollama`, warframe.market V2 orders API, Ollama Modelfile.

---

### Task 1: Item Display Names

**Files:**
- Create: `warframe_agent/names.py`
- Create: `tests/test_names.py`

- [ ] **Step 1: Write failing tests for display names**

Create tests proving `arcane_energize` renders as `充沛赋能 / Arcane Energize / arcane_energize`, aliases prefer useful Chinese names, and unknown ids still render with English title plus id.

- [ ] **Step 2: Run name tests for RED**

Run: `python -m unittest tests.test_names -v`
Expected: FAIL because `warframe_agent.names` does not exist.

- [ ] **Step 3: Implement name helpers**

Create `preferred_chinese_name(item_id)`, `english_name(item_id)`, and `display_item_name(item_id)` using `data/item_aliases.json` reverse mapping.

- [ ] **Step 4: Run name tests for GREEN**

Run: `python -m unittest tests.test_names -v`
Expected: PASS.

### Task 2: Chat Context And Fallback Answers

**Files:**
- Create: `warframe_agent/chat.py`
- Create: `tests/test_chat.py`

- [ ] **Step 1: Write failing tests for chat context**

Test that chat context includes three-part names, sell price, buy price, spread, arcane full-rank cost, and whisper command from injected fake market data.

- [ ] **Step 2: Run chat tests for RED**

Run: `python -m unittest tests.test_chat -v`
Expected: FAIL because `warframe_agent.chat` does not exist.

- [ ] **Step 3: Implement chat module**

Create `ChatAgent` with injected resolver, order fetcher, and model caller. Implement `answer(message)`, `build_item_context(item_id, orders)`, `fallback_answer(message, contexts)`, and watchlist scanning.

- [ ] **Step 4: Run chat tests for GREEN**

Run: `python -m unittest tests.test_chat -v`
Expected: PASS.

### Task 3: Terminal Chat Menu

**Files:**
- Modify: `main.py`
- Test: `tests/test_chat.py`

- [ ] **Step 1: Add test for exit commands**

Test that `is_chat_exit` returns true for `q`, `quit`, and `退出`, and false for normal questions.

- [ ] **Step 2: Implement menu item**

Add `4. 对话式交易助手`, `handle_chat(agent)`, and a loop that reads user messages until exit.

- [ ] **Step 3: Verify startup**

Run: `'q' | python .\main.py`
Expected: menu includes option 4 and exits with code 0.

### Task 4: Ollama Modelfile Builder

**Files:**
- Create: `tools/build_ollama_model.py`
- Create: `tests/test_model_builder.py`

- [ ] **Step 1: Write failing tests for Modelfile generation**

Test generated text includes `FROM qwen2.5:1.5b`, veteran-player Chinese system prompt, aliases, watchlist ids, and three-part naming rule.

- [ ] **Step 2: Run builder tests for RED**

Run: `python -m unittest tests.test_model_builder -v`
Expected: FAIL because script functions do not exist.

- [ ] **Step 3: Implement builder**

Create pure function `build_modelfile(alias_path, watchlist_path, model_name)` and CLI `main()` writing `Modelfile.generated`.

- [ ] **Step 4: Generate Modelfile**

Run: `python tools/build_ollama_model.py`
Expected: `Modelfile.generated` exists and prints `ollama create warframe-agent -f Modelfile.generated`.

### Task 5: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run all unit tests**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 2: Verify Python 3.14 Ollama connectivity**

Run: `C:\Users\ASUSYBT4-P325\AppData\Local\Programs\Python\Python314\python.exe -c "import ollama; print(ollama.generate(model='qwen2.5:1.5b', prompt='只回答OK')['response'].strip())"`
Expected: output includes `OK`.

- [ ] **Step 3: Verify generated custom model command path**

Run: `python tools/build_ollama_model.py`
Expected: command instructions print successfully.
