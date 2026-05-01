# Warframe Agent Next Phases Design

## Goal
稳步把当前项目从“热门物品交易助手”升级为“全量物品 + 长期记忆 + RAG 检索”的本地 Warframe 个人 Agent。

## Phase 1 Completed In This Iteration: Full Local Item Data
- Source: `https://api.warframe.market/v2/items`.
- Outputs:
  - `data/items_full.json`: 全量物品基础数据，包含 `item_id`, `zh_name`, `en_name`, `tags`, `search_terms`。
  - `data/generated_aliases.json`: 自动生成的别名表，供解析器识别简略中文、英文名和 market id。
  - `data/rag_items.jsonl`: 面向后续 RAG 的 JSONL 文档，每行一个物品。
- `ItemResolver` 解析顺序：手动别名 -> 全量生成别名 -> 本地导出字典 -> market id 归一化 -> Ollama fallback。

## Phase 2 Started: Long-Term Memory Agent
- Memory file: `data/agent_memory.json`.
- Stores:
  - Trading preferences: platform, crossplay, max result count.
  - Price alerts: item id, above/below, price threshold, note.
  - Favorite items.
  - Common questions.
- Chat prompt now includes preferences and triggered price alerts.
- Example: `arcane_energize` below 45p triggers `充沛低于45p提醒`.

## Phase 3 Started: Lightweight RAG Knowledge Base
- Current RAG base: `data/rag_items.jsonl` + `warframe_agent/rag.py` substring scorer.
- Purpose: when alias and resolver miss, search local item documents before giving up.
- Next upgrade path:
  1. Add richer documents from Warframe Wiki exports and local public export files.
  2. Add tokenized Chinese pinyin/abbreviation aliases.
  3. Add vector embeddings when a local embedding model is available.
  4. Store retrieved docs in chat prompt with source metadata.

## Immediate User-Facing Fix
The message `充沛现在价格怎么样` should no longer fail because:
- `data/item_aliases.json` includes `充沛 -> arcane_energize`.
- `ChatAgent` checks alias substrings inside full Chinese sentences.
- `ChatAgent` also checks generated aliases and RAG as fallback.
