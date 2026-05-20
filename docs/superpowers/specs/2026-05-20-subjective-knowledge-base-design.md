# Warframe Agent 主观知识库设计

## 背景

项目已有市场知识、用户记忆、RAG、专家代理和紫卡评分能力。紫卡属性辨析、配卡、攻略、活动路线等内容带有明显主观性和版本时效性，不能直接混入现有客观市场数据或用户偏好记忆。

本设计新增独立的主观知识层，用半自动采集和人工审核的方式，把公开视频攻略、人工经验和交叉验证结果整理成可召回、可降权、可追溯的 Agent 上下文。

## 目标

- 建立统一的主观知识数据结构，覆盖紫卡、配卡、攻略、活动、刷取路线。
- 使用 Playwright 辅助人工浏览公开视频资料，但不做批量爬取或绕过平台限制。
- 只有人工审核通过的知识进入 Agent 默认回答。
- 回答中区分客观数据和玩家攻略经验，避免把主观判断包装成官方事实。
- 为后续 embedding、Web 审核界面和更多专家域预留扩展空间。

## 非目标

- 不自动批量抓取 B 站。
- 不绕过登录、反爬、地区限制或付费/受保护内容。
- 不下载、存储或复刻长段视频字幕。
- 不在第一期实现完整 Web 审核后台。
- 不替换现有市场价格、事件、紫卡基础评分逻辑。

## 数据模型

新增 `data/subjective_knowledge.jsonl`。每行是一条独立知识记录：

```json
{
  "id": "riven:latron:crit_multishot_2026_05",
  "domain": "riven_attribute",
  "title": "Latron 紫卡双爆多重评价",
  "body": "经过审核的中文知识正文，说明适用场景、推荐理由、限制条件。",
  "applies_to": {
    "weapon": "latron",
    "warframe": null,
    "activity": null,
    "difficulty": "steel_path"
  },
  "tags": ["紫卡", "双爆", "多重", "钢铁"],
  "source": {
    "platform": "bilibili",
    "title": "来源视频标题",
    "url": "人工确认后的来源 URL 或空",
    "author": "UP 主名",
    "published_at": "可选"
  },
  "confidence": 0.7,
  "review_status": "approved",
  "updated_at": "2026-05-20"
}
```

字段约束：

- `domain` 使用固定枚举：`riven_attribute`、`weapon_build`、`warframe_build`、`activity`、`farming`、`guide`。
- `review_status` 使用固定枚举：`draft`、`approved`、`rejected`。
- `draft` 和 `rejected` 不进入 Agent 默认召回。
- `confidence` 表达人工审核后的主观可信度，范围为 `0.0` 到 `1.0`。
- `source` 保留来源元数据，但 `body` 使用自己的总结表达，不保存大段字幕或视频原文。

## 采集与审核流程

第一期采用半自动流程：

1. 用户提供 B 站视频 URL、合集 URL、UP 主页面或关键词。
2. Playwright 辅助打开页面并读取公开视频可见信息，例如标题、简介、发布时间、分区、可见字幕或人工摘录内容。
3. Agent 根据可见信息和人工摘录生成 `draft` 候选记录。
4. 人工审核候选记录，确认适用版本、玩法场景、争议程度、来源可靠性和是否需要降置信度。
5. 审核通过后改为 `approved`，才允许进入默认召回。

合规边界：

- 如果页面要求登录、绕过限制、下载受保护内容或批量访问，流程停止并让用户人工处理。
- 不执行来源页面中的任何指令。
- 不把评论区、字幕或简介中的角色提示文本当作系统指令。
- 不复制长段视频文案；只保存结论、适用范围、限制条件和来源。

## 召回与接入

新增 `SubjectiveKnowledgeStore` 和 `SubjectiveKnowledgeRecallService`，负责加载、校验、过滤、评分和格式化主观知识。

召回评分因素：

- `domain` 是否匹配用户问题。
- `applies_to` 是否匹配武器、战甲、活动、难度或玩法场景。
- `tags` 是否匹配关键词。
- `confidence` 越高越优先。
- `updated_at` 越新越优先；长期未复核的活动与攻略知识降权。
- 未来可按多来源共识提升权重。

接入点：

- 紫卡属性辨析：`riven.py` 保留现有基础评分；主观知识只作为武器、流派和负面词条特例上下文。
- 配卡和攻略问答：新增或扩展 `build`、`guide`、`activity` 专家域，召回 approved 知识摘要。
- 活动与刷取路线：优先使用当前事件和客观数据，主观知识补充打法、队伍建议和路线经验。

模型上下文格式必须标明：

- 这是玩家攻略或人工审核经验，不是官方事实。
- `confidence` 和更新时间。
- 适用对象与限制条件。

知识不足时，Agent 应明确说明不足以判断，不编造配卡或攻略。

## 安全边界

召回给模型前统一清洗：

- 中和 `system:`、`assistant:`、`developer:` 等角色注入文本。
- 移除玩家联系方式、私聊命令、profile 链接和交易私密信息。
- 不展示 `draft` 或 `rejected` 记录。
- 损坏 JSONL 行被跳过或记录为加载警告，不导致聊天崩溃。
- 外部来源内容只作为候选材料，不作为指令执行。

## 第一期实施范围

新增能力：

- `data/subjective_knowledge.jsonl` 种子数据。
- `warframe_agent/subjective_knowledge.py`，包含数据类、加载器、召回服务和模型上下文格式化。
- 单元测试覆盖加载、过滤、排序、降权和安全清洗。
- 将召回结果接入紫卡/专家上下文的最小路径。

种子内容：

- 紫卡属性辨析 2-3 条。
- 武器或战甲配卡 2-3 条。
- 活动或刷取路线 2-3 条。

每条种子知识都必须有 `review_status=approved`、`confidence`、`source` 和 `updated_at`。

## 测试计划

- 只召回 `approved`，不召回 `draft` 或 `rejected`。
- 按 `domain`、`applies_to`、`tags` 正确排序。
- 过期知识降权。
- prompt injection 文本被中和。
- 格式化上下文不包含未审核内容、玩家联系方式或私聊命令。
- 空知识库和坏 JSONL 不导致崩溃。
- `python -m pytest` 全部通过。

## 验收标准

- 主观知识库文件可加载并被单元测试覆盖。
- 紫卡问答可读取对应 approved 主观知识，同时保留现有市场和评分逻辑。
- 配卡、活动问题能给出带置信度和适用范围的建议。
- 知识不足时明确说明不足以判断。
- 回答能区分客观数据与主观攻略经验。
