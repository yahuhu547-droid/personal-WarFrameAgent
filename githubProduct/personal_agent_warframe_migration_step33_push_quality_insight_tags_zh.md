# Step 33：推送质量策略摘要标签

## 本次借鉴点

- Step 32 已经让推送质量可以排序，本步继续把聚合记录压缩成更容易扫读的策略摘要。
- 摘要标签不是新决策逻辑，只是把已有聚合字段转换成 UI 提示：`样本不足`、`待补复盘`、`稳定盈利`、`高误报`、`观察中`。
- 标签只基于数字聚合字段，不读取 raw metadata、玩家名、profile URL、market URL、`/w`、whisper 或 token。

## 已完成

- `warframe_agent/web/static/js/sidebar.js`
  - 新增 `getPushQualityInsightTags(record)`。
  - 新增 `renderPushQualityInsightTags(record)`。
  - 在 `renderPushQuality(records)` 的统计 chips 后、复盘提醒前渲染摘要标签。
  - 规则：
    - `reviewed_count < 5`：`样本不足`。
    - `pending_count > 0`：`待补复盘`。
    - `reviewed_count >= 5` 且好评率高、误报率低、利润偏差非负：`稳定盈利`。
    - 有复盘样本且误报高、好评低或坏结果明显更多：`高误报`。
    - 其他：`观察中`。

- `tests/test_web_ui_playwright.py`
  - 推送质量 mock 增加 `arcane_observe`，覆盖 `观察中` 分支。
  - 面板测试覆盖 `样本不足`、`待补复盘`、`稳定盈利`、`高误报`、`观察中`。
  - 静态契约确认 helper 和标签文案存在。
  - 静态契约截取 `getPushQualityInsightTags(...)`，确认其中不引用 `metadata`、`profile_url`、`market_url`、`whisper`、`player_name` 或 `/w`。

## 行为边界

- 不改后端 API、不新增字段、不新增写入端点。
- 不影响主动推送排序、推送质量排序或复盘确认链路。
- 摘要标签只使用 `reviewed_count`、`pending_count`、`good_rate`、`false_positive_rate`、`avg_profit_delta`、`good_count`、`bad_count`。
- `待补复盘` 表示需要用户补结果，不代表坏质量。

## 准备继续学习的清单

- 可以把 `高误报` / `稳定盈利` 做成筛选器，但仍应保持前端只读或后端只读查询。
- 可以安全暴露 push-history 的 OPID 后，再做具体机会复盘入口。
- 可以给推送质量面板增加“摘要说明”文档，但避免在 UI 里塞教程文字。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed
# GREEN: 1 passed

.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_trading_memory_panel_renders_tabs_safely_and_read_only --basetemp .pytest-tmp -p no:cacheprovider
# 普通沙箱：Web server did not become ready
# 非沙箱：1 passed
```
