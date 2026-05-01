# Prime Weapon Alias Expansion Design

## Goal
Automatically generate broad but conservative colloquial aliases for all Prime weapons so Chinese shorthand questions like `斯特朗p枪管多少钱` can be recognized without requiring the full English market name.

## Problem
Current full-item data already provides official Chinese names, but player shorthand is often shorter and noisier:
- `斯特朗p枪管`
- `雷克斯p枪机`
- `布莱顿p枪托`
- `双枪p枪管`

A naive generator could create too many ambiguous aliases and cause wrong item matches.

## Safety-First Strategy
Use a conservative layered strategy:

### Layer 1: Official generated aliases
Keep existing aliases from `data/generated_aliases.json` based on official Chinese and English names.

### Layer 2: Safe shorthand aliases for Prime weapons only
Generate additional aliases only when all of these are true:
- item belongs to a Prime weapon group
- the base Chinese weapon name can be extracted cleanly from `items_full.json`
- the part name is recognized from a fixed whitelist (`枪管`, `枪机`, `枪托`, `连接器`, `刀刃`, `刀柄`, `圆盘`, `弓身`, `弓弦`, `上弓臂`, `下弓臂`, `蓝图`)
- the generated shorthand alias is unique across all items

Examples:
- `斯特朗p枪管` -> `strun_prime_barrel`
- `雷克斯p枪机` -> `lex_prime_receiver`
- `布莱顿p枪托` -> `braton_prime_stock`

### Layer 3: Ambiguity filtering
Do not emit shorthand aliases when:
- the same shorthand would map to multiple item ids
- the shortened Chinese base name is too short (e.g. 1 character)
- the item group name contains punctuation or formatting that makes truncation unreliable

## Output Files
Extend `tools/build_item_data.py` to also generate:
- `data/generated_aliases.json` with safe shorthand aliases merged in
- optional diagnostics file `data/generated_alias_conflicts.json` listing skipped ambiguous aliases

## Runtime Behavior
`ItemResolver` continues using priority:
1. manual aliases `data/item_aliases.json`
2. generated aliases `data/generated_aliases.json`
3. local dictionary/export cache
4. normalized market id
5. LLM fallback

This keeps manual curated aliases higher priority than automatic shorthand.

## Success Criteria
- `斯特朗p枪管` resolves to the correct Prime weapon part when the alias is uniquely safe.
- Ambiguous shorthand aliases are skipped instead of guessed.
- Existing tests remain green.
- Add regression tests for safe weapon shorthand and ambiguity filtering.
