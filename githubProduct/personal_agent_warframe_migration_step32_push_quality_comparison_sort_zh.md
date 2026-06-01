# Step 32：推送质量 source/strategy 对比排序

## 本次借鉴点

- Step 29-31 已经让推送质量可见、可提醒复盘，本步继续把聚合信号变成可比较的观察工具。
- 排序只在 Web 前端当前返回的安全聚合记录内完成，不新增后端 `sort` 参数，也不改变 `summarize_push_quality(...)` 的聚合逻辑。
- 用户可以按 `待复盘优先`、`表现最好`、`风险最高` 查看不同 source/strategy 的表现，辅助决定哪些策略值得继续观察或补复盘。

## 已完成

- `warframe_agent/web/static/js/sidebar.js`
  - 在 `推送质量` tab 的 filter 区新增 `#push-quality-sort-filter`。
  - 新增 `getPushQualitySortMode(...)`、`pushQualityNumber(...)`、`pushQualityName(...)` 和 `sortPushQualityRecords(...)`。
  - 排序模式：
    - `待复盘优先`：`pending_count` 降序、`reviewed_count` 升序、`sent_count` 降序。
    - `表现最好`：`good_rate` 降序、`false_positive_rate` 升序、`reviewed_count` 降序、`avg_profit_delta` 降序。
    - `风险最高`：`false_positive_rate` 降序、`bad_count` 降序、`good_rate` 升序、`reviewed_count` 降序。
  - `push-quality` 分支渲染前先本地排序，最后用 `item_name/source/strategy` 做稳定兜底。

- `tests/test_web_ui_playwright.py`
  - 推送质量 mock 扩展为 `arcane_pending`、`arcane_good`、`arcane_risky` 三类样本。
  - 面板测试覆盖默认 `待复盘优先`、切换 `表现最好`、切换 `风险最高` 后第一张卡片变化。
  - 断言 URL 不出现 `sort=`，确认排序没有变成后端参数。
  - 静态契约确认排序控件、helper 和三个排序文案存在。

## 行为边界

- 不改后端 API、不新增写入端点、不改变主动推送排序。
- 排序只使用聚合字段：`pending_count`、`reviewed_count`、`sent_count`、`good_rate`、`false_positive_rate`、`bad_count`、`avg_profit_delta`。
- 不展示 raw metadata、raw orders、玩家名、profile URL、market URL、`/w`、whisper 或 token。
- 前端排序只覆盖当前 API 返回的 `limit` 结果；若未来需要全库级 Top N，再考虑后端 sort。

## 准备继续学习的清单

- 可补充 `需谨慎` 和 `待复盘` 的独立视觉状态测试。
- 可在推送质量面板增加更清晰的策略摘要，例如“样本不足”“高误报”“稳定盈利”，但仍只基于聚合字段。
- 若要做具体机会复盘入口，需要先安全暴露 push-history 的 OPID，不能从聚合质量记录推断。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed
# GREEN: 1 passed

.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_trading_memory_panel_renders_tabs_safely_and_read_only --basetemp .pytest-tmp -p no:cacheprovider
# 普通沙箱：Web server did not become ready
# 非沙箱：1 passed
```
