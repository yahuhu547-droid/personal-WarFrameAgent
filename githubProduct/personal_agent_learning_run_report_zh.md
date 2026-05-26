# 个人 Agent 项目学习运行报告

生成日期：2026-05-25

执行方式：按 `personal_agent_learning_execution_plan_zh.md` 派发子代理并行研读。当前阶段执行的是第一轮“安全运行计划”：只读分析、定位入口、评估运行成本和迁移价值；没有安装依赖、没有启动服务、没有修改 8 个上游项目源码。

## 总览

| 项目 | 学习优先级 | 运行优先级 | 当前结论 | 适合学习 |
| --- | --- | --- | --- | --- |
| OpenManus | A | 先跑 | 代码紧凑，单 Agent 闭环最清楚 | ReAct、tool calling、browser-use、MCP、planning flow |
| CowAgent | A | 第二批跑 | 中文个人 Agent 主架构最完整 | channel、tools、skills、memory、scheduler、MCP、Web 控制台 |
| EchoBot | A | 先读后跑 | 三层人格化架构很贴近个人助手 | Decision / Roleplay / Agent、异步任务、安全开关 |
| OpenClaw | A | 先读后跑 | 多渠道常驻助手和插件生态完整 | Gateway、channels、extensions、skills、memory、安全默认值 |
| OpenHuman | A- | 先读 | 记忆系统强，但依赖重 | Memory Tree、本地优先知识库、Obsidian vault、channels |
| LangManus | B | 先读 | 多 Agent 状态流样板 | coordinator、planner、supervisor、specialists、SSE 事件 |
| Open-AutoGLM | B | 暂缓运行 | 手机 GUI Agent 值得拆，但需要设备和模型 | 截图、VLM、动作 DSL、ADB/HDC、人类接管 |
| Suna / Kortix | B | 暂缓运行 | 重型持久沙盒平台，适合后期拆模块 | sandbox、skills、triggers、channels、24/7 runtime |

## 项目研读结果

### 1. OpenManus

**定位：** 轻量通用个人 Agent 框架，核心是 `BaseAgent -> ReActAgent -> ToolCallAgent -> Manus` 的单 Agent 工具调用闭环。

**关键入口：**
- `OpenManus\main.py`
- `OpenManus\app\agent\base.py`
- `OpenManus\app\agent\react.py`
- `OpenManus\app\agent\toolcall.py`
- `OpenManus\app\agent\manus.py`
- `OpenManus\app\tool\tool_collection.py`
- `OpenManus\app\tool\browser_use_tool.py`
- `OpenManus\app\flow\planning.py`
- `OpenManus\app\config.py`
- `OpenManus\config\config.example.toml`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenManus
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements.txt
copy config\config.example.toml config\config.toml
python main.py
```

**可借鉴点：**
- 主闭环清楚：用户输入 -> `agent.run()` -> step loop -> `think` -> `act` -> tool result -> terminate。
- `ToolCollection` 同时负责工具 schema 暴露和工具分发，适合迁移到自己的工具层。
- 主工具组合克制：Python、Browser、File Editor、AskHuman、Terminate，足够做最小 demo。
- Browser 工具会把当前页面状态和截图回灌给 Agent，这个设计很适合做网页任务助手。
- `max_steps`、`max_observe`、重复响应检测、cleanup 等边界控制值得复用。

**风险/代价：** 需要 LLM API key；`browser-use`、Playwright、crawl/search、MCP、Python 执行和文件编辑会扩大权限面。

**下一步最小安全命令：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenManus
python --version
```

### 2. CowAgent

**定位：** 中文友好的个人常驻 Agent Harness，多渠道输入，Agent Core 负责任务规划、工具调用、技能、记忆、调度和 MCP。

**关键入口：**
- `CowAgent\README.md`
- `CowAgent\docs\zh\README.md`
- `CowAgent\app.py`
- `CowAgent\cli\cli.py`
- `CowAgent\config-template.json`
- `CowAgent\bridge\agent_bridge.py`
- `CowAgent\bridge\agent_initializer.py`
- `CowAgent\channel`
- `CowAgent\agent\tools`
- `CowAgent\agent\memory`
- `CowAgent\agent\tools\scheduler`
- `CowAgent\agent\tools\mcp`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\CowAgent
pip install -r requirements.txt
pip install -e .
copy config-template.json config.json
cow start
```

**可借鉴点：**
- `channel_factory.py` 把 Web、微信、飞书、钉钉、企微、QQ、终端等收敛到统一 Channel 生命周期。
- `AgentInitializer` 集中装配 workspace、env、memory、tools、scheduler、skills、prompt。
- `agent/tools` 把文件、终端、浏览器、搜索、memory、scheduler、MCP 等做成可组合工具层。
- `skills/` 与用户目录 `~/cow/skills/` 分离，便于内置技能和用户技能共存。
- scheduler 是 Agent 工具，定时任务可以由自然语言创建，再由后台服务执行。
- MCP 支持后台 warmup 和热重载，适合学习外部工具生态接入。

**风险/代价：** 需要模型 API key；IM 通道需要平台凭据；`bash`、文件读写、浏览器、MCP 都有本地权限风险；长期运行会产生 `~/cow` 状态目录。

**下一步最小安全命令：**
```powershell
cd F:\giteeProject\warframe\githubProduct\CowAgent
python --version
Test-Path .\config.json
```

### 3. EchoBot

**定位：** 人格化陪伴 + 后台生产力 Agent。最值得学的是 Decision / Roleplay / Agent 三层拆分。

**关键入口：**
- `EchoBot\echobot\__main__.py`
- `EchoBot\echobot\cli\main.py`
- `EchoBot\echobot\cli\app.py`
- `EchoBot\echobot\app\create_app.py`
- `EchoBot\echobot\runtime\bootstrap.py`
- `EchoBot\echobot\orchestration\decision.py`
- `EchoBot\echobot\orchestration\roleplay.py`
- `EchoBot\echobot\orchestration\coordinator.py`
- `EchoBot\echobot\agent.py`
- `EchoBot\echobot\skill_support\registry.py`
- `EchoBot\echobot\memory`
- `EchoBot\echobot\channels`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\EchoBot
pip install -r requirements.txt
copy .env.example .env
python -m echobot app
```

**可借鉴点：**
- Decision 先判断意图，避免每轮都把人格设定和工具列表塞进大模型。
- Roleplay 负责即时角色回复，Agent Core 负责慢速后台任务。
- Coordinator 支持先回应“已开始”，再异步执行任务，完成后再包装结果。
- `auto`、`chat_only`、`force_agent` 三种会话模式适合个人助手切换“陪伴/生产力”。
- `file_write_enabled`、`cron_mutation_enabled`、`web_private_network_enabled` 这类安全开关值得复用。
- Live2D/语音/UI 层和核心 Agent 解耦，可以单独学习交互设计。

**风险/代价：** 依赖较重；默认权限里有 `danger-full-access` 风险，真实运行前应改成 `read-only` 或 `workspace-write`；语音模型可能下载权重；QQ/Telegram 需要平台 token。

**下一步最小安全命令：**
```powershell
cd F:\giteeProject\warframe\githubProduct\EchoBot
python --version
python -m echobot --help
```

### 4. OpenClaw

**定位：** 本地优先、多渠道、常驻个人 AI 助手。Gateway 是控制面，extensions/channels/skills/memory 是生态层。

**关键入口：**
- `OpenClaw\README.md`
- `OpenClaw\package.json`
- `OpenClaw\openclaw.mjs`
- `OpenClaw\src\entry.ts`
- `OpenClaw\src\gateway`
- `OpenClaw\src\channels`
- `OpenClaw\src\plugins`
- `OpenClaw\src\memory`
- `OpenClaw\extensions`
- `OpenClaw\skills`
- `OpenClaw\apps`
- `OpenClaw\docker-compose.yml`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenClaw
pnpm install
pnpm openclaw setup
pnpm ui:build
pnpm gateway:watch
```

**可借鉴点：**
- Gateway 把 sessions、channels、tools、events、nodes 收束成常驻助理控制面。
- `src/channels` 做核心协议，`extensions/*` 做平台适配器，边界很清楚。
- skill 使用 `SKILL.md`，workspace 路径可设计为用户可读可改。
- memory 有核心层和 `memory-core`、`memory-lancedb`、`memory-wiki` 等可替换后端。
- DM pairing、allowlist、sandbox、Docker compose 的 `cap_drop` / `no-new-privileges` 安全默认值值得学。
- 可按渠道、账号、peer 路由到隔离 agent，适合“工作/生活/项目”分域。

**风险/代价：** monorepo 很大；多渠道需要 token/OAuth/账号配对；Windows 推荐 WSL2；main session 工具可能直接跑在宿主机上，需要认真配置 sandbox。

**下一步最小安全命令：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenClaw
node -v
```

### 5. OpenHuman

**定位：** 桌面优先个人 AI Agent，核心卖点是本地优先长期记忆、Memory Tree、Obsidian 风格 Markdown vault、channels 和桌面 UI。

**关键入口：**
- `OpenHuman\README.md`
- `OpenHuman\app`
- `OpenHuman\app\src-tauri`
- `OpenHuman\src\openhuman\agent\README.md`
- `OpenHuman\src\openhuman\memory\README.md`
- `OpenHuman\src\openhuman\memory_tree\README.md`
- `OpenHuman\src\openhuman\memory_store\README.md`
- `OpenHuman\src\openhuman\skills\README.md`
- `OpenHuman\src\openhuman\channels\README.md`
- `OpenHuman\gitbooks\developing\architecture.md`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenHuman
pnpm dev
pnpm --filter openhuman-app dev:app:win
cargo run --manifest-path Cargo.toml --bin openhuman-core
```

**可借鉴点：**
- `memory/` 做编排，`memory_store/` 做持久化，`memory_tree/` 做通用树机制，分层清楚。
- 正文落地为 Markdown，SQLite 存路径、hash、索引、向量、元数据，便于用户检查和迁移。
- Obsidian vault 兼容，长期记忆不是黑盒。
- AgentBuilder、session runtime、subagent runner、tool dispatcher、triage pipeline 边界清晰。
- Skills 采用 `SKILL.md` 发现和注入，支持不同 scope。
- Channels trait 化，适合把 Slack/Discord/Telegram/Web/CLI 统一成 Agent 输入输出层。

**风险/代价：** Node 24、pnpm、Rust 1.93、Tauri、CEF、CMake、Ninja、平台构建链都可能需要；默认体验依赖托管服务；个人数据接入涉及 OAuth 和隐私。

**下一步最小安全命令：**
```powershell
Get-Content -Raw F:\giteeProject\warframe\githubProduct\OpenHuman\CONTRIBUTING.md
```

### 6. LangManus

**定位：** 基于 LangGraph 的多 Agent 自动化框架，用 coordinator/planner/supervisor 调度 researcher、coder、browser、reporter。

**关键入口：**
- `langmanus\main.py`
- `langmanus\server.py`
- `langmanus\src\api\app.py`
- `langmanus\src\graph\builder.py`
- `langmanus\src\graph\nodes.py`
- `langmanus\src\graph\types.py`
- `langmanus\src\agents\agents.py`
- `langmanus\src\tools\browser.py`
- `langmanus\src\prompts`
- `langmanus\.env.example`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\langmanus
uv python install 3.12
uv venv --python 3.12
.venv\Scripts\activate
uv sync
copy .env.example .env
uv run main.py
```

**可借鉴点：**
- coordinator 只负责寒暄/拒绝/转交，不承担复杂推理。
- planner 产出完整计划，supervisor 做逐步路由。
- 角色提示词外置在 `src/prompts/*.md`，改行为不用改核心代码。
- 工具权限按角色拆开：researcher 搜索，coder Python/bash，browser 网页交互。
- API SSE 把 workflow、agent、LLM、tool 生命周期事件统一流出，适合前端展示执行过程。
- reporter 被约束为只基于已有信息写报告，减少最终总结胡编。

**风险/代价：** 需要 LLM API key、Tavily/Jina 可选服务、browser-use 和浏览器环境；coder 的 bash/Python REPL 必须加权限隔离。

**下一步最小安全命令：**
```powershell
Get-Content F:\giteeProject\warframe\githubProduct\langmanus\.env.example
```

### 7. Open-AutoGLM

**定位：** 手机 GUI Agent：截图 -> 当前 App 信息 -> 视觉语言模型 -> 动作 DSL -> ADB/HDC/iOS 执行 -> 新截图，直到完成。

**关键入口：**
- `Open-AutoGLM\main.py`
- `Open-AutoGLM\phone_agent\agent.py`
- `Open-AutoGLM\phone_agent\model\client.py`
- `Open-AutoGLM\phone_agent\actions\handler.py`
- `Open-AutoGLM\phone_agent\device_factory.py`
- `Open-AutoGLM\phone_agent\adb`
- `Open-AutoGLM\phone_agent\hdc`
- `Open-AutoGLM\phone_agent\xctest`
- `Open-AutoGLM\phone_agent\config`
- `Open-AutoGLM\README_coding_agent.md`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\Open-AutoGLM
python main.py --base-url http://localhost:8000/v1 --model "autoglm-phone-9b-multilingual" "Open Maps and search for nearby coffee shops"
python main.py --list-apps
```

**可借鉴点：**
- 屏幕感知闭环非常清楚，适合抽成 GUI Agent 最小骨架。
- 动作 DSL 简洁：`do(action="Tap", element=[x,y])`、`finish(message="...")`。
- 坐标归一化到 0-999，再映射到实际像素，适配不同分辨率。
- ADB/HDC 通过 `DeviceFactory` 抽象，Android 和 HarmonyOS 共用主循环。
- `Take_over` 用于支付、登录、验证码等敏感场景，必须保留人类接管。
- 中文 App 包名、提示词和输入策略集中在 `config/apps*.py` 与 `prompts_zh.py`。

**风险/代价：** 需要真实设备、USB 调试、安全设置、ADB Keyboard 或 iOS WebDriverAgent；模型服务可能需要 GPU 或第三方 API；坐标视觉自动化对弹窗、广告、网络波动敏感。

**下一步最小安全命令：**
```powershell
cd F:\giteeProject\warframe\githubProduct\Open-AutoGLM
rg --files phone_agent
rg -n "do\(action|Take_over|ADB Keyboard|screenshot|uiInput|ModelConfig" phone_agent README_en.md README_coding_agent.md
```

### 8. Suna / Kortix

**定位：** 持久 Linux 云电脑 + OpenCode Agent + 企业工作流。它把文件系统、密钥、浏览器、数据库、触发器、技能和多端入口放进长期运行的沙盒机器。

**关键入口：**
- `suna\README.md`
- `suna\package.json`
- `suna\pnpm-workspace.yaml`
- `suna\scripts\compose\docker-compose.yml`
- `suna\core\docker\docker-compose.yml`
- `suna\core\startup.sh`
- `suna\apps\api\src\index.ts`
- `suna\apps\web`
- `suna\apps\desktop`
- `suna\apps\mobile`
- `suna\core\kortix-master\opencode\skills`
- `suna\core\kortix-master\triggers\README.md`

**本地运行路径：**
```powershell
cd F:\giteeProject\warframe\githubProduct\suna
pnpm dev
pnpm dev:web
pnpm dev:api
pnpm dev:core
```

**可借鉴点：**
- `/workspace`、`/persistent`、`/ephemeral` 三层持久化模型适合长期 Agent。
- 沙盒容器收纳 noVNC、SSH、OpenCode、浏览器流、静态站点、Docker-in-Docker。
- skills 分通用工作技能和系统能力，说明能力描述和 runtime 可以解耦。
- `.kortix/triggers.yaml -> TriggerStore -> Cron/Webhook -> prompt|command|http` 的触发器设计适合 24/7 助手。
- API 聚合边界清楚：billing、platform、sandbox-proxy、tunnel、secrets、integrations、queue。
- Web、mobile、desktop 都围绕同一台 sandbox/session/files/tools 展开。

**风险/代价：** 运行成本高，需要 Docker privileged、Bun、pnpm、Next、Supabase、LLM provider、外部集成；安全面大，包括密钥、SSH、浏览器 profile、Docker-in-Docker、webhook、tunnel。

**下一步最小安全命令：**
```powershell
docker compose -f F:\giteeProject\warframe\githubProduct\suna\core\docker\docker-compose.yml config
```

若 Docker 不可用，退一步：
```powershell
rg --files F:\giteeProject\warframe\githubProduct\suna\core\kortix-master\opencode\skills
```

## 优先级矩阵

**先跑 demo：**
- OpenManus：最适合先跑，因为主链路短、结构清楚、能最快看到 Agent 工具调用闭环。
- CowAgent：第二个跑，验证中文个人 Agent 主架构和 Web 控制台。

**先读架构：**
- EchoBot：重点读三层分流、异步任务、安全开关。
- OpenClaw：重点读 Gateway、channel/extension/plugin/skill/memory 边界。
- OpenHuman：重点读 memory tree、memory store、Markdown vault。
- LangManus：重点读 LangGraph 状态流和 supervisor 路由。

**暂缓运行：**
- Open-AutoGLM：等有真实设备、模型服务和权限边界后再跑。
- Suna / Kortix：等确定需要持久沙盒和 24/7 运行后再跑。

## 个人 Agent 建议蓝图

第一版个人 Agent 不要一次复刻所有大系统。建议蓝图：

1. **入口层：** 先做 Web + Terminal，参考 CowAgent channel 抽象；IM 通道后置。
2. **Agent Core：** 用 OpenManus 的 `BaseAgent -> ReAct -> ToolCall` 做最小闭环。
3. **规划层：** 先单 Agent，复杂任务再借鉴 LangManus 的 planner/supervisor。
4. **工具层：** 文件、搜索、浏览器、终端、AskHuman、Terminate；参考 OpenManus 和 CowAgent。
5. **记忆层：** 参考 OpenHuman/CowAgent，先做 Markdown + SQLite 元数据，再加向量检索。
6. **技能层：** 采用 `SKILL.md`，参考 OpenClaw、CowAgent、EchoBot。
7. **人格层：** 参考 EchoBot，把“即时人格回复”和“后台任务执行”拆开。
8. **安全层：** 默认 read-only，文件写入、shell、浏览器私网访问、定时任务都加开关。
9. **长期运行：** 等核心稳定后，再参考 Suna 的 persistent workspace 和 triggers。
10. **GUI/手机自动化：** 等工具权限成熟后，再参考 Open-AutoGLM 加入 VLM + 动作 DSL。

## 下一阶段可执行命令清单

**低风险，只读检查：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenManus
python --version
Get-Content .\config\config.example.toml -TotalCount 80
```

```powershell
cd F:\giteeProject\warframe\githubProduct\CowAgent
python --version
Test-Path .\config.json
Get-Content .\config-template.json -TotalCount 80
```

```powershell
cd F:\giteeProject\warframe\githubProduct\EchoBot
python --version
python -m echobot --help
```

**中风险，会安装依赖但不启动长驻服务：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenManus
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements.txt
```

**高风险，会启动 Agent 或写配置：**
```powershell
cd F:\giteeProject\warframe\githubProduct\OpenManus
copy config\config.example.toml config\config.toml
python main.py
```

```powershell
cd F:\giteeProject\warframe\githubProduct\CowAgent
copy config-template.json config.json
cow start
```

**暂缓执行：**
- `openclaw onboard`：会改本机 OpenClaw 配置状态。
- `irm ... | iex` 或 `curl ... | bash`：远程脚本执行，不作为学习第一步。
- Open-AutoGLM 真机控制命令：会操作设备。
- Suna/Kortix 沙盒启动：涉及 privileged Docker、密钥、网络代理和多服务。

## 本轮完成标准核对

- 8 个项目均已由子代理只读研读。
- 已输出入口、运行前置、可借鉴点、风险和优先级。
- 已生成本报告。
- 未安装依赖，未启动服务，未修改 8 个上游项目源码。
