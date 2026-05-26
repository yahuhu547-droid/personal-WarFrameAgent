# 个人 Agent 项目学习执行状态

生成日期：2026-05-25

## 本轮已完成

- 已把包安装策略切到项目目录内：`F:\giteeProject\warframe\githubProduct\local-cache`。
- 已把 Python 3.12 安装到项目目录内：`F:\giteeProject\warframe\githubProduct\tools\python\cpython-3.12.13-windows-x86_64-none\python.exe`。
- 已为 OpenManus 创建本地虚拟环境：`F:\giteeProject\warframe\githubProduct\OpenManus\.venv-py312`。
- 已新增本地环境脚本：`F:\giteeProject\warframe\githubProduct\local_agent_env.ps1`。
- 已新增 OpenManus 本地依赖文件：
  - `F:\giteeProject\warframe\githubProduct\local_requirements\openmanus-minimal.txt`
  - `F:\giteeProject\warframe\githubProduct\local_requirements\openmanus-smoke.txt`
- 已新增 OpenManus 本地烟测配置：`F:\giteeProject\warframe\githubProduct\OpenManus\config\config.toml`。该文件被上游 `.gitignore` 忽略，里面只放占位 API key，不包含真实密钥。
- 已创建 OpenManus 工作区：`F:\giteeProject\warframe\githubProduct\OpenManus\workspace`。

## 实际运行结果

### OpenManus 依赖安装

上游 `requirements.txt` 直接安装失败，原因是依赖冲突：

- `pillow~=11.1.0`
- `crawl4ai~=0.6.3` 需要 `pillow~=10.4`

处理方式：

- 保留上游源码不改。
- 在 `local_requirements` 下创建学习用依赖文件。
- 用 `openmanus-smoke.txt` 先完成导入和架构学习需要的最小依赖。
- `browser-use` 精确锁定为 `0.1.40`，避免 pip 长时间回溯。
- 不显式 pin `boto3`，让 `daytona==0.21.8` 自己解析兼容版本。

安装结果：成功。

### OpenManus 烟测

已通过：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. 'F:\giteeProject\warframe\githubProduct\local_agent_env.ps1'
$venvPy = 'F:\giteeProject\warframe\githubProduct\OpenManus\.venv-py312\Scripts\python.exe'
& $venvPy -c "from app.agent.manus import Manus; from app.config import config; agent = Manus(); print('import=ok'); print('agent=' + agent.name); print('tools=' + ','.join([tool.name for tool in agent.available_tools.tools])); print('workspace=' + str(config.workspace_root))"
```

关键输出：

- `import=ok`
- `agent=Manus`
- `tools=python_execute,browser_use,str_replace_editor,ask_human,terminate`
- `workspace=F:\giteeProject\warframe\githubProduct\OpenManus\workspace`

已通过：

```powershell
& $venvPy -m pip check
```

关键输出：

- `No broken requirements found.`

已通过 AST 语法校验：

- `ast_parse=ok`

说明：`compileall` 因 Windows 下 `PYTHONPYCACHEPREFIX` 深层路径权限问题不适合本轮验证；环境脚本已改为 `PYTHONDONTWRITEBYTECODE=1`，避免写 pycache。

## 当前不继续运行 main.py 的原因

OpenManus 的 `main.py` 会进入真实 Agent 运行链路，需要真实 LLM API key。当前本地 `config.toml` 使用的是占位 key，只用于导入和实例化烟测，所以本轮没有执行真实任务，避免无效 API 调用和权限扩大。

## 下一轮准备学习清单

1. OpenManus 主链路
   - `BaseAgent -> ReActAgent -> ToolCallAgent -> Manus`
   - `think / act / run / cleanup`
   - `ToolCollection` 如何暴露 schema 和分发工具
   - `BrowserUseTool` 如何把浏览器状态反馈给 Agent

2. CowAgent 个人助手机制
   - channel 抽象
   - tools / skills / memory / scheduler / MCP
   - Web 控制台和 CLI 如何装配 Agent
   - 如何把默认写入路径改到项目目录内

3. EchoBot 人格化分层
   - Decision / Roleplay / Agent 三层拆分
   - 即时陪伴回复与后台任务执行分离
   - 文件写入、shell、定时任务、私网访问的安全开关

4. OpenClaw 常驻助手架构
   - Gateway
   - channels / extensions / plugins
   - skills / memory
   - `OPENCLAW_HOME`、state、workspace 如何迁移到项目目录内

5. OpenHuman 长期记忆
   - Memory Tree
   - Markdown / Obsidian vault
   - memory store 与 agent runtime 的边界

6. LangManus 多 Agent 状态流
   - coordinator / planner / supervisor / researcher / coder / browser / reporter
   - 什么时候值得上多 Agent，什么时候单 Agent 加工具更稳

7. 暂缓实跑
   - Open-AutoGLM：需要真实手机、ADB/HDC、模型服务。
   - Suna / Kortix：依赖重型 sandbox、Docker、长期服务和密钥管理。

## 后续执行建议

下一步优先读 OpenManus 的主链路源码，并用当前 `.venv-py312` 做只读级别的模块级实验。等提供真实 LLM API key 或本地 Ollama 模型后，再执行真实 `main.py` demo。
