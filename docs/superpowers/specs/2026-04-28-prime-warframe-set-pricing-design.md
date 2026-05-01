# Prime Warframe Set Pricing Design

## Goal
Add intelligent pricing for Prime Warframe sets and individual parts in the chat agent. The agent should understand player questions about a specific part, a full set, lowest seller prices, highest buyer prices, and whether buying/selling as a set or as parts is better.

## Supported Scope
This iteration supports Prime Warframes only. Regular non-Prime Warframes are out of scope because most regular warframe acquisition paths are not player-tradeable in the same market structure.

## Player Questions
The agent should handle questions like:
- `伏特p机体多少钱`
- `伏特p一套现在多少钱`
- `Mesa Prime 一套最低成本`
- `犀牛p最高有人收多少`
- `伏特p拆件买划算还是整套买划算`

## Warframe Set Structure
A Prime Warframe set consists of:
- Set item: `<base>_prime_set`
- Main blueprint: `<base>_prime_blueprint`
- Chassis: `<base>_prime_chassis_blueprint`
- Neuroptics: `<base>_prime_neuroptics_blueprint`
- Systems: `<base>_prime_systems_blueprint`

Example: `volt_prime_set`, `volt_prime_blueprint`, `volt_prime_chassis_blueprint`, `volt_prime_neuroptics_blueprint`, `volt_prime_systems_blueprint`.

## Query Intent
The module should classify:
- Part query: mentions `蓝图`, `机体`, `系统`, `头`, `头部`, `神经光元`, `chassis`, `systems`, `neuroptics`, `bp`.
- Full set query: mentions `一套`, `整套`, `总价`, `set`, `成本`, `拆件`, or asks a warframe name without a specific part.
- Price side:
  - Lowest seller focus: `最低`, `买`, `入手`, `成本`, `卖多少` from buyer perspective.
  - Highest buyer focus: `最高`, `收`, `有人收`, `出`, `卖给别人`.
  - Default: show both.

## Output Requirements
For a set query, include:
- Three-part set name.
- Direct set lowest sell price and highest buy price.
- Part-by-part lowest sell prices and total.
- Part-by-part highest buy prices and total.
- A short veteran-player recommendation comparing direct set vs parts.

For a part query, include:
- Three-part part name.
- Lowest sell price.
- Highest buy price.
- Direct whisper commands.

## Integration
`ChatAgent.answer()` should detect Prime Warframe set questions before generic item lookup. If detected, it should build deterministic market context and then either return it directly or pass it to the model. This iteration returns deterministic pricing text to avoid model confusion with multiple part IDs.

## Data Sources
Use `data/items_full.json` to discover available Prime Warframe sets and parts. Use manual aliases for common Chinese shorthand such as `伏特p` and `犀牛p`; add generated matching for English names from the full item data.

## Success Criteria
- `伏特p机体多少钱` resolves to `volt_prime_chassis_blueprint`.
- `伏特p一套现在多少钱` queries set plus four parts.
- Output compares direct set price against parts total.
- Unit tests pass.
