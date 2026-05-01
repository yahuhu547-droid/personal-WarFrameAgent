# Warframe Trading Agent Design

## Goal
Build a local terminal Warframe trading agent that accepts Chinese item names, resolves them to warframe.market item identifiers, queries current orders, and produces both interactive results and a daily Markdown market report.

## Scope
The first version supports local terminal usage only. It covers single-item lookup and a daily report for three core categories: arcanes, Prime warframe parts, and popular mods. It does not include a GUI, browser automation, account login, scheduled Windows tasks, or full-site crawling.

## User Flow
Run `python .\main.py` from `F:\giteeProject\warframe`. The menu offers single item lookup, daily report generation, dictionary rebuild, and quit. Single lookup asks for a Chinese or English item name and prints the best five online sellers and best five online buyers.

## Data Sources
Local game export JSON lives at `C:\Users\ASUSYBT4-P325\Downloads\warframe-public-export-senpai`. The agent reads Chinese and English files for relic/arcanes, upgrades, and warframes. Manual aliases live in `data/item_aliases.json`. Daily tracked items live in `data/watchlist.json`. Market data comes from `https://api.warframe.market/v1/items/{item_id}/orders`.

## Resolution Strategy
Item resolution tries manual aliases first, then a generated dictionary cache, then a local Ollama fallback using `qwen2.5:1.5b`. LLM results are normalized and validated by requesting the market API before use.

## Order Strategy
For sellers, use online in-game `sell` orders sorted by lowest platinum price. For buyers, use online in-game `buy` orders sorted by highest platinum price. Each result includes price, quantity, user, status, reputation, and the in-game whisper command equivalent to the warframe.market Buy/Sell button.

## Reporting
Daily reports write to `reports/daily-YYYY-MM-DD.md` and also print a terminal summary. Each item row includes best sell price, best buy price, spread, and top seller/buyer snippets.

## Error Handling
If local dictionary data is missing, the agent still runs with manual aliases and LLM fallback. If Ollama is unavailable, it reports the exact fallback failure and asks the user to input a market id or add an alias. If market requests fail, the item is marked as failed without stopping the whole report.
