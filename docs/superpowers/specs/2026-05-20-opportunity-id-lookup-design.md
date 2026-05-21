# Opportunity ID Lookup Design

## Goal

Trading opportunity pushes should be lightweight but actionable. When a WxPusher trading opportunity includes an executable trade plan, the push will show a short opportunity ID. The user can type that ID in Feishu to receive the full market links, player profile links, and in-game whisper commands for that exact pushed opportunity.

## Scope

In scope:
- Generate short IDs for pushed trading opportunities that include a `trade_plan`.
- Store the full actionable trade plan snapshot behind the ID for a short time.
- Show the ID and Feishu lookup hint in WxPusher opportunity pushes.
- Let Feishu/chat resolve bare IDs and `/opp ID` or `/机会 ID` commands.
- Expire and clean old opportunity details automatically.
- Preserve the existing long-term memory safety boundary by keeping full player/link/whisper details out of long-term push history.

Out of scope:
- Generating IDs for opportunity pushes without a `trade_plan`.
- Re-querying warframe.market when an old ID is requested.
- Changing the underlying ROI or opportunity detection logic.
- Replacing the existing proactive push dedupe/cooldown behavior.

## Opportunity ID lifecycle

When the app is about to send a proactive trading opportunity push and `push.data.trade_plan` is present:

1. Create a short user-facing ID such as `OP8K3A2Q`.
2. Store the full trade plan snapshot with metadata:
   - item ID and display name
   - strategy
   - cost, revenue, profit, ROI, and risk
   - buy steps
   - sell steps
   - warframe.market item links
   - player profile links
   - in-game whisper commands
   - creation time and expiration time
3. Attach the ID to the outgoing WxPusher content and optional WebSocket/Feishu payloads.
4. Keep the ID valid for 48 hours.
5. Clean expired records when saving or querying opportunity details.

The lookup returns the pushed snapshot, not a fresh market scan. This keeps the Feishu reply consistent with the opportunity the user saw in WxPusher. The reply must still warn that market orders may change and should be verified live.

## Storage

Add a short-term opportunity detail store separate from long-term memory. A SQLite-backed store is preferred because the project already uses SQLite for trading memory and cleanup patterns.

Suggested schema:

```text
opportunity_details
- lookup_id TEXT PRIMARY KEY
- created_at TEXT NOT NULL
- expires_at TEXT NOT NULL
- item_id TEXT NOT NULL
- item_display TEXT NOT NULL
- plan_signature TEXT
- content_json TEXT NOT NULL
```

`content_json` stores only the data needed to render the Feishu lookup response. It intentionally contains actionable player/link/whisper details, so records should have a short TTL and should not be copied into long-term `push_history` metadata.

ID generation should avoid plain autoincrement IDs. Use a readable low-collision format with an `OP` prefix and uppercase base32/base36 characters. Lookup should require an exact ID match so a partial ID cannot return the wrong trade plan.

## WxPusher format

For opportunity pushes with a stored trade plan, add a visible ID block near the top:

```text
机会ID：OP8K3A2Q
在飞书输入 OP8K3A2Q 查看买卖双方链接、玩家主页和游戏内私聊命令。
该 ID 约 48 小时后过期；机会基于推送时快照，请以实时市场为准。
```

Then keep the existing opportunity summary or trade-plan Markdown below it. Pushes without a `trade_plan` should not show an ID.

## Feishu/chat lookup

Supported inputs:

```text
OP8K3A2Q
/opp OP8K3A2Q
/机会 OP8K3A2Q
```

If the ID exists and is not expired, return a complete execution plan:

```text
机会 OP8K3A2Q：Akbolto Prime

策略：拆件买入 → 完整套装订单卖出
说明：Set 订单不是单独物品，游戏内需交付全部对应部件。
成本：39p
目标收入：80p
预计利润：+35p
ROI：89.7%
风险：medium
有效期：剩余 47 小时

需要买入的部件：
1. Akbolto Prime Blueprint — 玩家A — 10p
   市场：https://warframe.market/items/akbolto_prime_blueprint
   玩家主页：https://warframe.market/profile/玩家A
   游戏内私聊：/w 玩家A Hi! I want to buy...

完整套装订单买家：
1. 买家D — 80p
   交付内容：Akbolto Prime Blueprint x1、Barrel x1、Link x1
   市场：https://warframe.market/items/akbolto_prime_set
   玩家主页：https://warframe.market/profile/买家D
   游戏内私聊：/w 买家D Hi! I want to sell...

提示：该机会基于推送时快照，订单可能变化，请以 warframe.market 实时状态为准。
```

If the strategy is the reverse direction, use explicit wording:
- `买入完整套装订单：需确认卖家能一次性交付全部部件`
- `拆分卖出部件：逐个匹配部件买家`

If the ID is missing or expired, return a clear message and do not fall through to normal item search:

```text
机会 ID OP8K3A2Q 不存在或已过期。请等待下一次推送，或重新运行相关扫描。
```

## Set order wording

Warframe.market Set listings represent bundle orders. In game, the player still trades the individual Prime parts in the trade window. The user-facing copy must not imply there is a separate in-game item named “the set”.

Use wording such as:
- `完整套装订单（需在游戏内交付全部对应部件）`
- `按 Set 买家需求，一次性交付完整部件组合`
- `交付内容：Blueprint x1、Barrel x1、Link x1`

Avoid wording that suggests the set is a single tradable in-game item.

## Cleanup

Default TTL: 48 hours.

Cleanup behavior:
- Run cleanup opportunistically on every store write.
- Run cleanup opportunistically on every lookup.
- Expired lookups return the missing/expired message.
- A later scheduler job may be added if needed, but read/write cleanup is enough for the first version.

## Safety and data boundaries

Long-term proactive push history should continue to store only safe summaries. It must not store player names, profile links, market links, or whisper commands. The short-term opportunity detail store is the only place where full actionable details are persisted for lookup, and it expires quickly.

All returned URLs should continue to use existing safe warframe.market URL helpers or equivalent validation.

## Tests

Add or update tests for:
- Opportunity detail store creates, reads, expires, and cleans records.
- Generated IDs use the expected `OP` format and exact-match lookup.
- WxPusher trade opportunity Markdown includes ID, Feishu lookup hint, and 48-hour expiry note.
- Chat/Feishu lookup supports bare IDs, `/opp ID`, and `/机会 ID`.
- Missing or expired IDs return an explicit not-found/expired response and do not trigger item search.
- Set-order responses explain that Set orders require delivering all component parts.
- Long-term proactive push history remains sanitized and does not store links, player names, or whispers.
