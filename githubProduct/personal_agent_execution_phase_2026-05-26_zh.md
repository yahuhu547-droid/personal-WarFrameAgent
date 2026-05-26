# 个人 Agent 学习执行阶段记录

日期：2026-05-26

## GitHub 上传

已按 SSH 远端上传到：

```text
git@github.com:yahuhu547-droid/personal-WarFrameAgent.git
```

本轮推送：

- 远端：`personal`
- 分支：`main`
- 本地提交：`b307aa6 docs: add personal agent study setup`
- 推送命令：`git push personal codex-personal-agent-foundation:main`

本次提交采用白名单方式，只提交学习文档、本地环境脚本和 OpenManus 本地 requirements。未提交：

- `githubProduct` 下下载的第三方仓库源码
- `.venv`、cache、Python 工具链、Playwright 浏览器缓存
- OpenManus 本地 `config.toml`
- `.claude` 本地配置
- 个人记忆数据和草稿数据

## OpenManus 无 LLM 结构探针

已在项目内 venv 执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. 'F:\giteeProject\warframe\githubProduct\local_agent_env.ps1'
$venvPy = 'F:\giteeProject\warframe\githubProduct\OpenManus\.venv-py312\Scripts\python.exe'
Set-Location 'F:\giteeProject\warframe\githubProduct\OpenManus'
& $venvPy -c "from app.agent.manus import Manus; a=Manus(); print('mro=' + ' -> '.join([c.__name__ for c in Manus.__mro__])); print('tools=' + ','.join([t.name for t in a.available_tools.tools])); print('max_steps=' + str(a.max_steps)); print('special_tools=' + ','.join(a.special_tool_names))"
```

关键输出：

- `mro=Manus -> ToolCallAgent -> ReActAgent -> BaseAgent -> BaseModel -> ABC -> object`
- `tools=python_execute,browser_use,str_replace_editor,ask_human,terminate`
- `max_steps=20`
- `special_tools=terminate`

结论：OpenManus 最小结构探针已通过；仍未执行 `main.py`，因为真实任务需要真实 LLM API key。

## OpenManus 主闭环梳理

子代理只读梳理了：

- `OpenManus\app\agent\base.py`
- `OpenManus\app\agent\react.py`
- `OpenManus\app\agent\toolcall.py`
- `OpenManus\app\agent\manus.py`
- `OpenManus\app\tool\tool_collection.py`
- `OpenManus\app\tool\browser_use_tool.py`

主链路：

1. 用户请求进入 `BaseAgent.run(request)`。
2. `run()` 写入 user message，并切换状态到 `RUNNING`。
3. 主循环最多执行 `max_steps` 轮。
4. 每轮调用 `step()`。
5. `ReActAgent.step()` 拆成 `think()` 和 `act()`。
6. `Manus.think()` 初始化 MCP，并按需注入浏览器上下文。
7. `ToolCallAgent.think()` 调用 `llm.ask_tool()`，传入历史消息、system prompt 和 `available_tools.to_params()`。
8. LLM 返回 assistant message 和 tool calls。
9. `ToolCallAgent.act()` 遍历 tool calls。
10. `execute_tool()` 解析 JSON 参数，并通过 `ToolCollection.execute(name, input)` 执行工具。
11. 工具 observation 写回 memory。
12. 如果执行到 `Terminate`，状态切到 `FINISHED`，主循环结束并 cleanup。

最值得迁移到 WarFrameAgent 的 3 个抽象：

1. `BaseAgent.run + step`：状态机、memory、最大步数、cleanup、卡死检测。
2. `ReActAgent.think / act`：把决策和执行拆开。
3. `ToolCollection + BaseTool`：模型 tool call 到本地能力执行的桥。

## CowAgent 本地写入边界

子代理只读审计了 CowAgent。当前 `CowAgent\config.json` 不存在，启动会读 `config-template.json`。

默认可能写入：

- 当前工作目录：`run.log`
- 用户目录：`~/cow`
- 用户目录：`~/.cow/.env`
- 用户目录：`~/.cow/browser_profile`
- 用户目录：`~/.weixin_cow_credentials.json`
- CowAgent 项目根：`user_datas.pkl`
- 临时目录：`tmp/`、工作区 `tmp/`、系统临时目录

因此现在不应直接执行：

- `python app.py`
- `python app.py --cmd`
- `run.sh`
- `scripts/start.sh`
- `docker compose up`
- `cow start/restart/update`
- 微信扫码登录、浏览器工具、bash/write/edit 工具烟测

建议后续把本地运行数据统一迁移到：

```text
F:\giteeProject\warframe\githubProduct\CowAgent-data
```

建议 `config.json` 覆盖字段：

```json
{
  "agent_workspace": "F:\\giteeProject\\warframe\\githubProduct\\CowAgent-data",
  "appdata_dir": "F:\\giteeProject\\warframe\\githubProduct\\CowAgent-data\\appdata",
  "weixin_credentials_path": "F:\\giteeProject\\warframe\\githubProduct\\CowAgent-data\\.weixin_cow_credentials.json",
  "web_password": "请设置一个密码",
  "tools": {
    "browser": {
      "user_data_dir": "F:\\giteeProject\\warframe\\githubProduct\\CowAgent-data\\.cow\\browser_profile"
    }
  }
}
```

还要注意：CowAgent 的 `~/.cow/.env` 有硬编码路径。无代码修改的临时方案是在启动进程前设置：

```powershell
$env:USERPROFILE='F:\giteeProject\warframe\githubProduct\CowAgent-data'
$env:HOME='F:\giteeProject\warframe\githubProduct\CowAgent-data'
```

更稳的方案是后续改 CowAgent 相关路径读取逻辑，但这属于第三方参考项目改造，暂不执行。

## 下一步低风险任务

1. 在 WarFrameAgent 自身代码里评估是否已有 `ToolRegistry` / `ToolRouter` 可承接 OpenManus 的 `ToolCollection` 思路。
2. 只读梳理 WarFrameAgent 当前聊天/工具/记忆主链路，找出最小可迁移位置。
3. 再决定是否新建一个 `BaseAgent` 风格的轻量抽象，而不是直接复制 OpenManus。
