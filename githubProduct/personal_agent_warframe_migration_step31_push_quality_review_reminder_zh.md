# Step 31：推送质量面板复盘提醒入口

## 本次借鉴点

- Step 29 已经把推送质量聚合展示出来，本步把 `pending_count` 和低复盘样本变成行动入口：提醒用户补充真实结果，而不是让系统自行判断。
- `push_quality` 是聚合数据，没有具体 OPID，所以不能直接复盘。入口只预填自然语言草稿，用户必须补 OPID 和实际利润并发送，之后仍走已有“确认复盘”二次确认。
- 不生成 `/review done ...`，因为显式命令会直接写入；自然语言入口会先返回确认提示。

## 已完成

- `warframe_agent/web/static/js/sidebar.js`
  - 新增 `shouldShowPushQualityReviewReminder(...)`：`pending_count > 0` 或 `reviewed_count < 5` 时显示提醒。
  - 新增 `safePushQualityTemplateField(...)`：只允许短安全标识符，拒绝 `<`、`/w`、profile、warframe.market、token、secret、whisper、raw。
  - 新增 `buildPushQualityReviewTemplate(...)`：生成 `OP______ 实际赚__p，结果 good/bad/neutral，帮我复盘...` 草稿。
  - 新增 `renderPushQualityReviewReminder(...)`：在质量卡片里显示 `复盘提醒`、待复盘/样本提示和“填入复盘模板”按钮。
  - 新增 `fillPushQualityReviewTemplateFromButton(...)`：只填入 `#chat-input` 并聚焦，不发送、不调用 API。

- `tests/test_web_ui_playwright.py`
  - 推送质量 mock 增加敏感字段，确认入口不使用 profile URL、market URL、`/w`、玩家名或 raw metadata。
  - 面板测试覆盖“复盘提醒”和按钮预填草稿。
  - 断言预填草稿含来源/策略，但不含 `QualityLeak`、`/w QualityLeak` 或 `<img`。
  - 断言点击按钮后 `state["chat_messages"] == []`，证明没有自动发送。
  - 静态契约确认 helper 存在，并确认模板构建函数中没有 `/review done`。

## 行为边界

- 本步不是自动复盘，也不新增写入端点。
- 入口只使用聚合字段 `item_name/source/strategy/pending_count/reviewed_count`，并经过安全过滤。
- 用户仍需要补 OPID 与实际利润；发送后由 ChatAgent 自然语言复盘入口创建待确认状态，用户再回复“确认复盘”才写入。
- `pending_count` 继续表示“等待用户复盘”，不是负面质量。

## 准备继续学习的清单

- 可继续在 Web 面板中增加 source/strategy 对比排序，帮助用户发现可靠策略。
- 可补充负向质量状态测试，覆盖 `需谨慎` 的视觉与文案。
- 若未来要从具体 push-history 直接复盘，需要先安全暴露 OPID；当前聚合质量面板不能假装知道具体机会。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed
# GREEN: 1 passed

.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_trading_memory_panel_renders_tabs_safely_and_read_only --basetemp .pytest-tmp -p no:cacheprovider
# 普通沙箱：Web server did not become ready
# 非沙箱：1 passed
```
