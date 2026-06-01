# Step 20 - `/goal set` 自然语言目标解析

## 背景

Step 19 已让自然语言 planning 模式只返回安全计划草案，并提示用户用 `/goal set ...` 显式创建跟踪目标。但当前 `/goal set` 只保存原始描述，并固定写入 `criteria={"budget": 500, "min_roi": 10}`。这会让“我一周赚 500p、预算 300p、低风险”这类句子无法进入后续计划、进度和复盘链路。

## 目标

让 `/goal set` 在不自动下单、不自动执行计划的前提下，把常见中文目标句解析成结构化 criteria：

- 目标利润：`target_profit` 和兼容进度使用的 `target_amount`
- 周期：`timeframe_days`
- 预算：`budget`
- 风险偏好：`risk`
- 最低 ROI：`min_roi`
- 当句子明确包含收益目标时，命令创建 `earn_platinum` 目标；普通描述仍保持旧的 `maximize_profit`。

## 非目标

- 不改 GoalTracker 的持久化格式。
- 不引入 LLM 解析目标，保持确定性、离线可测。
- 不让自然语言 planning 自动创建目标。
- 不改 Web 端目标创建 API。

## 实施计划

1. 在聊天命令层新增纯 helper，解析 `/goal set` 后的描述文本。
2. 先保留旧默认：未识别预算或 ROI 时仍使用 `budget=500`、`min_roi=10`。
3. 识别常见表达：
   - `一周/7天/七天/今天/明天/一个月`
   - `赚500p/盈利500p/利润500p/攒500白金`
   - `预算300p/本金300p`
   - `低风险/稳健/保守/中风险/高风险/激进`
   - `最低ROI 20%/ROI 20%`
4. `/goal set` 创建目标后，在回执里追加“已解析”摘要。
5. 用 fake GoalTracker 做命令集成测试，避免写真实 `data/goals.json`。
6. 更新 `githubProduct` 学习记录和 `md/rebuilt` 同步文档。

## 验证

- `.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "goal_set" -q --basetemp .pytest-tmp`
- `.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "planning_mode" -q --basetemp .pytest-tmp`
- `.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"`
