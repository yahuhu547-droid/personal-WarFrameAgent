# Step 37 可检查 Memory Vault 索引

生成日期：2026-05-28

## 来源项目

- OpenHuman：借鉴“个人记忆应可持续累积、可检查、可被后续会话复用”的方向。
- CowAgent：借鉴“把对话、任务结果和工具事实沉淀成后续 Agent 可查询材料”的做法。

## 借鉴点

本步没有复制完整 Obsidian / Markdown vault，也没有引入向量数据库。实际吸收的是更小的一层能力：

- 将已有安全记忆源聚合成统一索引。
- 给人和 Agent 都能读的 Markdown 预览。
- 每条索引保留来源、时间、物品、标题、摘要和标签。
- 所有字段经过 allowlist 和敏感信息过滤。

## Warframe 映射

新增 `warframe_agent/memory_vault.py`，把下列来源转换为只读 `MemoryVaultEntry`：

- `user_query`
- `market_snapshot`
- `recommendation`
- `push_history`
- `opportunity_outcome`
- `conversation_log`

新增 Web API：

```text
GET /api/memory/vault
```

返回结构包括：

- `generated_at`
- `total`
- `source_counts`
- `entries`
- `markdown_preview`

## 安全边界

本步只做只读聚合，不新增写入链路，不调用云端模型，不读取 `.env`，不新增依赖，不启用 Browser / GUI 自动化。

Vault 输出不得包含：

- 原始用户消息。
- 原始助手回复。
- raw tool arguments / raw result。
- 玩家名、seller、buyer、player。
- `/w` 私聊命令。
- Warframe Market profile URL。
- token、secret、Authorization、cookie、app_secret、chat_id。
- prompt injection 角色标记。

对话日志进入 vault 时只保留上下文数量、工具数量、工具名和安全 session id，不导出 `user_message` 或 `assistant_reply` 字段。

## 已实现文件

- `warframe_agent/memory_vault.py`
- `warframe_agent/web/app.py`
- `tests/test_memory_vault.py`
- `tests/test_web_api.py`
- `docs/superpowers/plans/2026-05-28-memory-vault-index.md`

## 验证结果

TDD 红测：

- `tests/test_memory_vault.py` 初次运行因 `ModuleNotFoundError: No module named 'warframe_agent.memory_vault'` 按预期失败。
- `tests/test_web_api.py -k "memory_vault"` 在可写运行环境中按预期返回 `404 != 200`。

Green 验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_memory_vault.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`3 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_memory_recall.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`5 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "memory_vault or memory_recall_api_returns_safe_trace" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`2 passed, 70 deselected`

备注：普通沙箱导入 Web app 时仍会遇到既有 SQLite WAL 数据库文件权限限制；Web API 目标测试已在可写运行环境中补跑。

## 当前结论

Step 37 回到了剩余学习队列中的“可检查知识库与记忆 vault”方向，没有继续偏向 Scout UI 微调。当前实现是一个保守的只读索引层，先让记忆材料可检查、可审计，并且覆盖角色前缀与 `ignore previous instructions` 这类注入短语清洗；后续再考虑是否需要 Markdown 文件导出、搜索 UI 或更强召回。

下一步更适合继续：

- Browser / GUI Agent 安全边界评估。
- 语音和陪伴式体验评估。
- Step 35 分支的“软拦截 -> 用户确认 -> 受控执行”确认链路。
