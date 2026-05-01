# Warframe Ollama Chat Agent Design

## Goal
Add two complementary ways to use this project as a personalized Warframe trading assistant:

1. A custom Ollama model named `warframe-agent` that can be launched with `ollama run warframe-agent` for Chinese Warframe market Q&A and item-name assistance.
2. A project-powered chat mode inside `main.py` that reads local project files, resolves Chinese item names, queries live warframe.market orders, and feeds structured context to the local `qwen2.5:1.5b` model for conversational Chinese answers.

## User Outcomes
- The user can ask natural Chinese questions such as `充沛现在能不能买？`, `川流p多少钱出合适？`, or `帮我看今天哪些赋能值得倒`.
- Responses use veteran-player trading language, not raw tables only.
- Item names are shown in a consistent three-part format: `中文名 / English Name / market_id`.
- Arcane responses include rank/max-rank awareness, especially the common `21 个满级` cost estimate.
- Market answers include lowest sell price, highest buy price, spread, quantity, and ready-to-copy whisper commands when live data is available.

## Approach A: Custom Ollama Model
Create a generated Ollama Modelfile from local project data.

### Files
- `tools/build_ollama_model.py`: reads aliases and watchlist, then writes `Modelfile.generated`.
- `Modelfile.generated`: generated file based on `qwen2.5:1.5b`.

### Behavior
The generated model uses:
- `FROM qwen2.5:1.5b`
- A `SYSTEM` prompt describing the assistant as a veteran Chinese Warframe trading helper.
- Local alias/watchlist snippets embedded as static knowledge.
- Naming rules requiring `中文名 / English Name / market_id` when an item is identified.

### Usage
```powershell
python tools/build_ollama_model.py
ollama create warframe-agent -f Modelfile.generated
ollama run warframe-agent
```

### Limitation
This mode cannot call project Python code or warframe.market by itself. It is best for item-name Q&A, trading advice style, and offline helper conversations.

## Approach B: Project Chat Mode
Add a conversational mode to the existing terminal app.

### Files
- `warframe_agent/names.py`: maps `market_id` to preferred Chinese name and display English name.
- `warframe_agent/chat.py`: extracts item candidates, gathers market context, calls Ollama, and returns a Chinese answer.
- `main.py`: adds menu option `4. 对话式交易助手`.

### Behavior
For each user message:
1. Detect likely item names from aliases and direct market ids.
2. Resolve each detected item via `ItemResolver`.
3. Query live orders via `fetch_orders`.
4. Compute top sellers, top buyers, spread, and arcane full-rank cost when relevant.
5. Build a compact Chinese context block.
6. Ask `qwen2.5:1.5b` to answer conversationally.
7. If Ollama fails, return a deterministic fallback summary based on market data.

### Conversation Commands
- `q`, `quit`, `退出`: exit chat mode.
- `watchlist` or `关注列表`: scan the configured watchlist and summarize opportunities.

## Veteran Player Features Included In This Iteration
- Chinese aliases and player shorthand recognition.
- Three-part item display names.
- Lowest seller, highest buyer, and spread calculation.
- Arcane full-rank estimate using 21 copies.
- Direct whisper command output.
- Watchlist opportunity scan using simple spread-based labels.
- Graceful fallback when Ollama or market requests fail.

## Out Of Scope For This Iteration
- Historical price tracking.
- Automatic trading or browser automation.
- Account login.
- Full Prime set decomposition.
- Long-term memory fine-tuning of the base model.

## Success Criteria
- `python -m unittest discover -s tests -v` passes.
- `python tools/build_ollama_model.py` creates `Modelfile.generated`.
- `ollama create warframe-agent -f Modelfile.generated` can be run by the user.
- `main.py` menu includes chat mode.
- Chat mode can answer a known alias such as `充沛赋能现在能买吗？` with Chinese name, English name, market id, live spread, and whisper command when network is available.
