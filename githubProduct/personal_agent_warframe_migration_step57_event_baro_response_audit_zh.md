# Step 57 活动与虚空商人回复体检执行记录

## 任务定位

Step 57 是项目质量体检任务，不是旧 GitHub 个人 Agent 学习借鉴队列重启，也不是高权限能力启用。本步只检查并修复活动、虚空商人和相关跨意图问法的用户回复质量。

## 覆盖场景

- 泛活动问法：`现在有什么活动` 只返回运营限时活动。
- 具体事件问法：入侵、虚空风暴、Baro、Prime 重生不回退到泛活动。
- 虚空商人问法：状态、Mod / 赋能价格、库存式“带来了什么物品”。
- Baro 后续追问：买家 / 卖家链接和安全 session 上下文。
- 不支持事件：午夜电波、仲裁、突击、Darvo、扎里曼赏金明确说明数据源不支持。
- 跨意图保护：遗物收益、普通市场链接、限时活动和钢铁裂缝问法互不误抢。

## 发现的问题

| 问题 | 根因 | 处理 |
| --- | --- | --- |
| 虚空商人库存问法措辞不清 | `format_baro_report(...)` 只显示可分析 Mod / 赋能，但没有解释非交易库存不展示 | 增加“仅展示可分析的 Mod / 赋能”说明 |
| `热美亚裂缝现在有吗` 误入虚空裂缝 | 限时活动关键词和 `裂缝` 共享事件路由，优先级不够细 | 增加限时活动专用别名判定 |
| 具体限时活动混入其他活动 | `_handle_limited_event_query(...)` 不按原始问题过滤 | 按热美亚、兽之腹等标签过滤返回 |
| Baro 后续追问污染普通市场查询 | `_last_baro_recommendations` 对“链接 / 卖家”类消息过宽匹配 | 当新消息能解析为直接市场物品时，让路给普通市场查询 |
| `钢铁歼灭现在有吗` 需要走裂缝详情 | 任务类型 + 钢铁模式问法没有显式归入 `void_fissure` | 增加裂缝详情意图识别 |

## 修改范围

- `tests/test_chat_event_replies.py`
- `warframe_agent/chat.py`
- `warframe_agent/baro.py`
- `docs/superpowers/plans/2026-05-31-step57-event-baro-response-audit.md`
- `AGENTS.md`
- `md/rebuilt/09-personal-agent-foundation.md`
- `md/rebuilt/10-learning-route-audit.md`

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py::test_baro_followup_does_not_hijack_later_market_link_query tests\test_chat_event_replies.py::test_event_keywords_do_not_hijack_market_relic_or_video_intents -q --basetemp .pytest-tmp-step57-red-extra -p no:cacheprovider
```

修复前：`2 failed`。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py::test_baro_followup_does_not_hijack_later_market_link_query tests\test_chat_event_replies.py::test_event_keywords_do_not_hijack_market_relic_or_video_intents -q --basetemp .pytest-tmp-step57-green-extra -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py -q --basetemp .pytest-tmp-step57-event-replies-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_baro.py tests\test_events.py tests\test_tool_router.py tests\test_chat_event_replies.py -q --basetemp .pytest-tmp-step57-focused-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_chat_memory_commands.py -k "activity or event or baro or resurgence or fissure" -q --basetemp .pytest-tmp-step57-chat-broad-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/baro.py','warframe_agent/events.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
```

结果：

- 红测修复后：`2 passed`。
- Step57 回复矩阵：`10 passed`。
- Focused suites：`83 passed`。
- Chat broad regression：`18 passed, 114 deselected`。
- AST：`AST OK`。

## 子代理记录

本步使用过两个早期探索子代理，分别审查活动 / Baro 风险点；后续又尝试开启一个只读复核子代理，但该子代理因使用额度限制报错，没有产生可采纳结论。最终结论以主线程本地测试和复核为准。

## 安全边界

- 未安装依赖。
- 未下载文件。
- 未上传 GitHub。
- 未新增 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 未放宽 ToolRouter 安全策略，未新增高权限运行时能力。

## 剩余风险

- Step 55 记录的两个前端 Playwright 目标测试和完整 `pytest tests` 可写环境复跑仍未完成；本步没有改变该状态。
- 本步只修复聊天层问法和回复质量，不改变真实 World State 数据源覆盖面。
