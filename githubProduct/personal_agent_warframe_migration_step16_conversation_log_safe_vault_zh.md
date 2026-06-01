# Step 16：Conversation Log 默认安全写入

## 本次借鉴点

- 个人 Agent 的长期存储要分层：用户可见回复可以包含复制用私聊和 market 链接，但普通长期日志不应保存 raw 玩家名、profile、`/w`、token 或原始工具参数。
- 安全边界应尽量前移到写入点。与其只在 Web API 查询时过滤，不如让 `conversation_logs.jsonl` 文件本身默认只保存安全摘要。
- ChatAgent 的即时体验和长期学习材料可以不同：即时回答保留可执行交易信息，长期日志保留摘要、工具名、上下文 item_id 和脱敏后的统计字段。

## 已完成

- `warframe_agent/conversation_log.py`
  - `log_conversation(...)` 写入前会复制一份安全版 `ConversationEntry`，不改变调用方收到的用户可见文本。
  - `user_message` 与 `assistant_reply` 持久化为 `summary:v1 role=...` 格式。
  - 写入时会过滤或替换 `/w` 私聊、warframe.market 链接、玩家标签、token/secret/Authorization/Bearer/cookie/app_secret/chat_id 等敏感文本。
  - `tool_calls` 会跳过 `message_context`、`prompt`、`raw_arguments`、`content`、`display_content`、`model_context`、`result_summary`、`final_answer` 等 raw 字段，敏感 key 值写为 `[REDACTED]`。
  - `contexts` 只保留安全 item_id 风格字符串。
- `tests/test_conversation_log.py`
  - 新增写入前安全化的单元测试。
- `tests/test_chat.py`
  - 新增直接市场回答日志安全集成测试，确认用户仍能看到 `/w Seller`，但普通长期日志不保存它。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_conversation_log.py -q --basetemp .pytest_tmp_step16_conv
# 12 passed

.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "direct_market_answer_conversation_log_uses_safe_summary or records_sanitized_user_query_summary or answer_stream_records_one_sanitized_user_query_summary or router_tool_path_records_safe_tool_names_only or chat_uses_memory_recall_safe_summary_only" -q
# 5 passed

.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "conversation_log or tool_calls_do_not_leak" -q
# 2 passed
```

## 后续可继续

- Scout 推送质量评估：记录安全的机会命中率、误报原因和复盘结果。
- 聊天模式分层：让视频攻略、交易执行、价格分析、长期计划有更明确的本地路由。
