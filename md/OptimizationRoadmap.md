# 优化与改善路线图

> 基于对全部 32 个源码文件的审计，按优先级排列的问题清单和改善方案。

---

## 高优先级（影响稳定性/可观测性）

### 1. 静默异常吞掉 — 全项目约 50 处

**问题**：`except Exception: pass` 遍布全项目，故障无法诊断。

| 文件 | 静默 except 数量 | 最严重位置 |
|------|-----------------|-----------|
| `web/app.py` | ~35 | 几乎所有端点 |
| `monitor.py` | ~10 | `_run()` 主循环 |
| `chat.py` | ~8 | 工具执行 |
| `goals.py` | ~8 | 目标执行 |

**方案**：添加 `logging` 模块，至少 `logger.debug()` 记录异常信息。

### 2. rules.py 空值访问 bug

**问题**：`_anomaly_recommendation` 第 251 行，`thresholds` 为 `None` 时三元表达式短路失败，会抛 `AttributeError`。

**方案**：修复空值判断逻辑。

### 3. knowledge.py 数据无限增长

**问题**：`_items` 字典只增不减，`last_updated` 仅存储不检查，旧数据永不清理。

**方案**：增加 TTL 过期清理（30 天未更新则移除）。

### 4. monitor.py 扫描间隔固定

**问题**：300 秒固定间隔，无法根据市场活跃度自适应。`_load_items()` 每次重新读磁盘。

**方案**：`_load_items` 加缓存；间隔改为动态值。

### 5. price_history.py 无连接池、无清理

**问题**：每次操作新建 SQLite 连接再关闭，表无限增长。

**方案**：保持长连接；加定期清理（保留 30 天）。

### 6. scraper.py 双重加载 bug

**问题**：`scrape_wiki_page` 第 170-185 行，先请求页面获取 HTML 但未使用，再新建 page 重复加载同一 URL。

**方案**：复用第一次请求的结果。

### 7. market.py 无重试、缓存无上限

**问题**：`requests.get` 失败直接抛异常；`_cache` 字典无 LRU 淘汰，长期运行内存泄漏。

**方案**：加重试（tenacity 或简单循环）；缓存加 `maxsize`。

### 8. chat.js wsReconnectDelay 变量冲突

**问题**：`chat.js` 第 19 行和 `app.js` 第 170 行同名变量互相覆盖，WebSocket 重连延迟不可预测。

**方案**：使用模块作用域隔离。

---

## 中优先级（影响性能/代码质量）

### 9. _fetch_statistics 四处重复

**问题**：`mod_flipper.py`、`set_profit.py`、`investment.py`、`market.py` 中完全相同的函数副本。

**方案**：提取到 `market.py` 作为公共函数。

### 10. mod_flipper/set_profit 串行扫描

**问题**：逐个请求 API，40 个 Mod 约需 14 秒。`investment.py` 已有并发实现可复用。

**方案**：用 `ThreadPoolExecutor` 并发。

### 11. goals.py 无超时、无过期

**问题**：`execute_plan` 无时间限制，慢扫描器会无限阻塞。目标只增不减。

**方案**：加超时参数；增加目标 TTL 自动过期。

### 12. feedback.py 闭环断裂

**问题**：反馈结果仅用于策略屏蔽，未回流到 `compute_thresholds` 调整阈值。

**方案**：将反馈信号注入自适应阈值计算。

### 13. knowledge.py 字段语义错误

**问题**：`CategoryHealth.avg_roi` 实际存储的是波动率（`avg_roi=avg_vol`），命名误导。

**方案**：修正字段赋值或重命名。

### 14. web/app.py 拆分

**问题**：2573 行单体文件，5 个 broadcast 函数结构完全相同。

**方案**：提取通用 `_broadcast()`；按功能拆分为路由组。

### 15. app.js 动态 CSS 重复

**问题**：620 行 CSS 通过 JS 动态注入，与 `style.css` 大量重复。

**方案**：移入静态 CSS 文件。

### 16. chat.js 打字机性能

**问题**：逐字符 `innerHTML` 赋值，每次触发 DOM 重排，长消息卡顿。

**方案**：改为 `requestAnimationFrame` + `textContent` 分段追加。

### 17. sidebar.js XSS 风险

**问题**：内联 `onclick` 字符串拼接，若 itemId 含单引号可注入。

**方案**：改为 `addEventListener`。

### 18. app.py 错误响应不统一

**问题**：部分端点返回 `JSONResponse({"error": ...})`，部分抛 `HTTPException`，部分返回 200 + error 字段。

**方案**：统一为 `{"error": str, "code": int}` 格式 + 全局异常处理器。

### 19. app.js 粒子动画浪费 GPU

**问题**：页面不可见时 `requestAnimationFrame` 仍在运行。

**方案**：添加 `visibilitychange` 监听暂停。

---

## 低优先级（改善体验/可维护性）

### 20. rules.py 品类覆盖不全

**问题**：规则仅覆盖 mod/prime_set，遗漏 arcane、riven 等高价值品类。

**方案**：增加 arcane/riven 规则。

### 21. feedback.py 策略分类硬编码

**问题**：`_classify_strategy` 依赖字符串关键字匹配，无法处理新策略。

**方案**：改为枚举映射。

### 22. 类型注解缺失

**问题**：`web/app.py` 约 15 个端点函数缺少返回类型；`Any` 在多处使用。

**方案**：补充类型注解；用 `TypedDict` 替换 `dict[str, Any]`。

### 23. 测试覆盖缺口

**问题**：5 个模块完全无测试：`agent.py`、`config.py`、`conversation_log.py`、`llm.py`、`scraper.py`。

**方案**：优先为 `llm.py`、`scraper.py` 补充单元测试。

### 24. CSS 重复定义

**问题**：`variables.css` 和 `style.css` 重复 `@import` Google Fonts；`--glass-bg-light` 定义两次。

**方案**：仅在 `variables.css` 中导入字体；清理重复变量。

### 25. app.js 模态框重复

**问题**：三个模态框 HTML 结构高度雷同，模板字符串硬编码。

**方案**：提取通用 `createModal()` 工厂函数。

---

## 改善路线建议

```
第一阶段（稳定性）         第二阶段（性能）         第三阶段（体验）
─────────────────        ─────────────────       ─────────────────
1. 添加日志系统           9. 提取公共函数          20. 扩展规则品类
2. 修复空值 bug          10. 并发扫描             21. 策略分类重构
3. 知识库过期清理         11. 目标超时/过期        22. 类型注解
4. 监控器自适应间隔       12. 反馈闭环完善         23. 补充测试
5. 价格历史连接池         13. 字段语义修正         24. CSS 清理
6. 修复双重加载           14. 拆分 app.py          25. 模态框工厂
7. API 重试+缓存上限      15. 静态 CSS 整合
8. 修复变量冲突           16. 打字机优化
                          17. XSS 修复
                          18. 统一错误格式
                          19. 粒子动画暂停
```

---

## 量化指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 静默 except | ~50 处 | 0 处（全部加日志） |
| 重复代码 | ~400 行 | < 100 行 |
| 无测试模块 | 5/25 | 0/25 |
| API 扫描耗时 | ~14s（串行） | ~3s（并发） |
| 知识库条目 | 无限增长 | 自动过期 30 天 |
| 错误响应格式 | 3 种 | 1 种统一格式 |
