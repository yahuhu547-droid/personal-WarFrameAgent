# Prime Weapon Set And Missing Parts Design

## Goal
Extend the local Warframe trading agent so it can answer Prime weapon set questions and missing-parts questions in the same veteran-player style as Prime warframe pricing.

## Supported Questions
- `Lex Prime 一套多少钱`
- `Braton Prime 枪管多少钱`
- `Akbolto Prime 整套买和拆件买哪个划算`
- `我有伏特p蓝图和系统，还差多少钱补齐`
- `我有 Lex Prime 枪管和枪机，还差多少钱做一套`

## Scope
This iteration supports:
- Prime weapon set pricing
- Prime warframe missing-parts completion cost
- Prime weapon missing-parts completion cost
- Lowest seller, highest buyer, set vs parts comparison

This iteration does not yet support:
- Relic source recommendations
- Crafting time and Orokin cell/material advice
- Full mod build suggestions from set-price questions

## Data Model
Use `data/items_full.json` to discover Prime set groups.

A group is identified by a shared base prefix such as:
- `volt_prime_*`
- `lex_prime_*`
- `braton_prime_*`

Each group contains:
- one `_set` item when available
- one main `_blueprint` item
- multiple component items such as `chassis_blueprint`, `systems_blueprint`, `barrel`, `receiver`, `stock`, `blade`, `handle`, `link`, `disc`, `grip`, `string`, `upper_limb`, `lower_limb`

## Query Types
### 1. Full Set Pricing
Examples:
- `Lex Prime 一套多少钱`
- `伏特p整套最低多少`

Output should include:
- set direct lowest seller price
- set direct highest buyer price
- parts lowest seller total
- parts highest buyer total
- veteran-player recommendation

### 2. Single Part Pricing
Examples:
- `伏特p机体多少钱`
- `Lex Prime 枪管最高收多少`

Output should include:
- resolved part display name
- lowest seller price
- highest buyer price
- whisper commands

### 3. Missing Parts Completion Cost
Examples:
- `我有伏特p蓝图和系统，还差多少钱补齐`
- `我有 Lex Prime 枪管和枪机，还差多少钱做一套`

Output should include:
- detected owned parts
- missing parts list
- missing parts lowest seller total
- missing parts highest buyer total
- whether direct set purchase is cheaper than finishing parts manually

## Parsing Strategy
- Detect Prime base name from Chinese alias, English name, or full item data.
- Detect whether the user is asking about a set, a specific part, or a missing-parts completion calculation.
- For missing-parts questions, detect owned parts from the same message.
- Prefer deterministic pricing output over free-form model generation for set and parts questions.

## Architecture
- Keep `warframe_agent/warframes.py` but evolve it into a general Prime set pricing module.
- Add helpers for grouping base ids and detecting owned parts.
- Integrate into `ChatAgent.answer()` before generic item lookup and before model prompting.

## Success Criteria
- `Lex Prime 一套多少钱` returns set and parts totals.
- `Braton Prime 枪管多少钱` returns the barrel price path.
- `我有伏特p蓝图和系统，还差多少钱补齐` returns missing chassis and neuroptics with total cost.
- Unit tests pass.
