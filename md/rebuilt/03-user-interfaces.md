# 03. 用户入口与交互方式

本项目有四类主要用户入口：聊天 Agent、Web UI、飞书机器人、WxPusher 推送。

## 1. 聊天 Agent

核心入口是 `warframe_agent/chat.py` 中的 `ChatAgent`。

### 支持的交互类型

- 直接问价：例如某个物品当前最低卖价、最高收价、成交统计。
- Prime 查询：整套、部件、缺件、补齐成本、套装套利；套利结果包含 ROI、流动性、风险等级和机会分数。
- 紫卡查询：武器名、正负属性、无负、价格上限、分页追问；结果会显示属性评分、价格位置、置信度，并提示仅为当前挂牌参考、不代表真实成交价。
- Baro 查询：当前库存、推荐购买、某个条目的买家/卖家详情。
- 活动查询：虚空裂缝/裂隙/开核桃、虚空商人/奸商、入侵、虚空风暴、Prime 重生/返厂、开放世界周期；午夜电波、仲裁、突击、Darvo/每日特惠、扎里曼/赏金等当前数据源缺字段时返回“暂不支持”，不编造结果。
- 监控管理：收藏、价格提醒、关注列表、偏好、目标。
- 交易记录：记录买入/卖出、查询统计。
- 趋势和历史：价格趋势、异常、市场快照。
- 策略和计划：倒卖、投资、目标拆解、多步骤工具调用。
- 刷取路线：支持“某 Prime 部件去哪刷”“某遗物怎么刷”“哪个裂缝适合开这个核桃”等问法，返回推荐遗物、掉率、来源、当前同纪元裂缝、入库提示和期望收益线索。

### Slash Command 范围

| 命令 | 用途 |
|---|---|
| `/help` | 查看可用命令和示例。 |
| `/memory` | 查看长期记忆摘要。 |
| `/fav` | 管理收藏物品。 |
| `/alert` | 管理价格提醒。 |
| `/pref` | 设置交易偏好。 |
| `/push` | 暂停/开启交易机会推送，或设置交易机会检测范围。 |
| `/scan` | 执行扫描或查看扫描结果。 |
| `/goal` | 管理交易目标。 |
| `/fissure` | 查询或订阅虚空裂缝。 |
| `/cycle` | 查询或订阅开放世界周期。 |
| `/trade` | 记录或查询交易历史。 |
| `/relic` | 查询遗物和掉落；`/relic value Lith B1`、`/relic 估值 Lith B1` 可查看奖励价值、期望白金和期望杜卡德。 |
| `/strategy` | 运行策略模板。 |
| `/vault` | 查询 Prime Vault 相关信息。 |
| `/resurgence`、`/重生` | 查询 Prime Resurgence。 |

### 交易机会推送控制

聊天 Agent 支持确定性控制交易机会推送，不需要调用 LLM：

- `暂停交易机会`、`关闭机会推送`、`/push opportunity off`：暂停主动交易机会推送。
- `开启交易机会`、`恢复机会推送`、`/push opportunity on`：恢复主动交易机会推送。
- `交易机会只检测MOD`、`/push opportunity filter mod`：交易机会仅保留非赋能 MOD。
- `交易机会只检测赋能`、`/push opportunity filter arcane`：交易机会仅保留赋能。
- `交易机会检测全部`、`交易机会恢复全部`、`/push opportunity filter all`：恢复全部交易机会来源。

暂停/开启只影响主动交易机会，不影响价格提醒、关注扫描、裂缝/周期提醒和每日报告。范围过滤只影响交易机会检测和推送，不改变普通问价、收藏、提醒或日报逻辑。

## 2. Web UI

静态资源位于 `warframe_agent/web/static/`。

| 文件 | 职责 |
|---|---|
| `index.html` | 页面骨架和主要区域。 |
| `js/app.js` | 全局初始化和通用交互。 |
| `js/chat.js` | 聊天请求、流式/非流式回答展示。 |
| `js/chart.js` | 图表与价格历史展示。 |
| `js/sidebar.js` | 侧栏、面板、快捷入口。 |
| `css/style.css` | 主样式。 |
| `css/variables.css` | 主题变量。 |
| `css/animations.css` | 动画效果。 |
| `css/responsive.css` | 响应式布局。 |

### Web UI 主要区域

- 聊天窗口。
- 快捷查询按钮。
- 收藏和关注列表。
- 价格提醒。
- 推送配置。
- 飞书配置。
- 交易记忆面板：市场快照、推荐记录、推送历史和召回 Trace。
- 工具观测面板：从更多功能菜单打开，查看最近工具调用历史、成功率、耗时统计和按工具过滤结果。
- 交易机会面板：Mod/赋能翻转、Prime 套装利润和投资顾问优先渲染 `trade_plan` 卡片；赋能机会显示聚合买够满级所需 R0 的卖家 quantity、单价、小计和满级买家；Prime 多部件机会展示 ROI、机会分数、流动性和风险等级，只展示当前盈利策略需要的买卖路径，不混入另一条亏损路径；复制按钮只复制后端提供的 whisper。
- 主动交易机会 WebSocket：`proactive_push` 可携带 `trade_plan` 和 `safe_summary`；前端聊天区会把机会渲染为同样的可执行卡片，而不是只显示纯文本摘要。
- Dashboard / 图表。
- 运行态状态展示：侧栏状态点会轮询 `/api/runtime/status`，显示在线、检查中、部分异常或连接错误；点击状态点可打开运行态详情，查看 scheduler jobs、后台任务、最近工具调用、Feishu、WxPusher 和日报安全摘要。
- 价格历史、交易历史、推荐和扫描结果入口。

## 3. FastAPI Web 服务

Web 服务入口是 `warframe_agent/web/app.py`。

启动生命周期中会初始化：

- `ChatAgent`
- `PriceMonitor`
- `PriceHistoryDB`
- `TradeHistoryDB`
- `PushConfig`
- `WxPusher`
- `FeishuConfig`
- `FeishuBot`
- 物品别名、export/wiki/relic 缓存

API 详情见 `04-web-api-reference.md`。

## 4. 飞书机器人

实现文件：`warframe_agent/feishu.py`。

### 能力

- 使用飞书 WebSocket 长连接模式，不需要公网回调地址。
- 支持文本回复和卡片回复。
- 启动时清理旧 worker。
- worker 负责消息去重、过滤机器人自身消息、过滤启动前旧消息。
- 收到消息后转发给本地 `POST /api/chat`。
- 保存最近 chat_id，便于测试发送。
- 主动交易机会可用卡片展示 `trade_plan` 的策略、成本、收入、利润、ROI、买入步骤、卖出步骤、市场/profile 链接和后端生成的 whisper。

### 配置文件

- `data/feishu_config.json`
- `data/feishu_chat_id.txt`
- `data/feishu_worker.log`
- `data/feishu_worker.lock`
- `data/feishu_processed_ids.json`

### Web API 配置入口

- `GET /api/feishu/config`
- `POST /api/feishu/config`
- `POST /api/feishu/test`
- `GET /api/runtime/status` 可查看飞书 worker 是否运行、lock/log 元数据和调度状态；不会返回 `app_secret`、chat_id、token 或消息内容。

## 5. WxPusher 推送

实现文件：`warframe_agent/push.py`。

### 能力

- 发送文本和 Markdown。
- 生成二维码。
- 接收回调。
- 推送价格提醒、收藏扫描、事件订阅、机会推荐和每日报告。
- 交易机会使用 Markdown 展示 `trade_plan`，包含买入/卖出步骤、market/profile 链接和复制用 `/w` 命令。
- 格式化买家/卖家、价格和私聊命令。

### 配置文件

- `data/push_config.json`

### Web API 配置入口

- `GET /api/push/config`
- `POST /api/push/config`
- `POST /api/push/test`
- `GET /api/push/qrcode`
- `POST /api/push/callback`

## 6. 用户可见数据与模型上下文的区别

部分模块会维护两种输出：

| 输出类型 | 可包含 | 不应包含 |
|---|---|---|
| 用户展示 | 玩家名、profile 链接、`/w` 私聊命令、订单详情、交易机会的市场链接、买卖步骤、quantity、subtotal、total cost/revenue。 | API Key、内部 token。 |
| 模型上下文 | 价格、数量、趋势、统计、匿名化摘要、机会来源、策略、总成本、总收入、利润和 ROI；紫卡只含匿名属性、评分、价格位置和置信度。 | 玩家名、profile 链接、私聊命令、市场 URL、auction id、敏感字段。 |

运行态详情、工具观测和记忆 trace 面板只展示安全摘要，不显示密钥、chat_id、完整消息内容、profile 或模型不应见的私聊命令。Riven、Baro、专家分析尤其需要遵守这个边界。
