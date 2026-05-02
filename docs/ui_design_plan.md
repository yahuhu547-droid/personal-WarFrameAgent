# Warframe 交易助手 Web UI 设计计划

## 设计理念

### 核心概念："Tenno 科技终端"

将 Warframe 交易助手打造成一个 **Tenno 科技终端**，让用户感觉自己在使用一套来自 Warframe 世界的高科技交易系统。

### 设计风格

- **主风格**：未来科幻工业风 + 军事终端感
- **参考元素**：
  - Warframe 游戏 UI 的金色/橙色强调色
  - Corpus 财团的高科技感
  - Tenno 盔甲的几何线条
  - 星际战舰的控制台界面

### 色彩方案

#### 主色调
- **背景色**：深空黑 (`#070a14`) + 暗蓝 (`#0c1020`)
- **主强调色**：Tenno 金 (`#d4a737`) - 用于标题、重要元素
- **次强调色**：能量蓝 (`#4a9eff`) - 用于交互元素
- **成功色**：生命绿 (`#4ade80`) - 用于上涨、成功状态
- **警告色**：能量橙 (`#f59e0b`) - 用于提醒
- **错误色**：警报红 (`#ef4444`) - 用于下跌、错误状态

#### 渐变效果
- **金色渐变**：`linear-gradient(135deg, #d4a737, #b8860b)`
- **蓝色渐变**：`linear-gradient(135deg, #4a9eff, #2563eb)`
- **背景渐变**：`linear-gradient(180deg, #070a14, #0c1020, #070a14)`

### 字体方案

#### 主字体
- **显示字体**：使用 Google Fonts 的科幻风格字体
  - 首选：`Orbitron` - 未来感强，适合标题
  - 备选：`Rajdhani` - 科技感，适合正文
- **代码字体**：`JetBrains Mono` - 清晰易读，适合价格数据

#### 字体层次
- **标题**：Orbitron, 16-24px, 大写，金色
- **正文**：Rajdhani, 14-16px, 灰色
- **数据**：JetBrains Mono, 12-14px, 亮色
- **标签**：Rajdhani, 12px, 大写，次级灰色

### 视觉效果

#### 1. 扫描线效果
```css
/* 模拟终端扫描线 */
.scanlines::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.1) 2px,
    rgba(0, 0, 0, 0.1) 4px
  );
  pointer-events: none;
  z-index: 10;
}
```

#### 2. 光效边框
```css
/* 金色发光边框 */
.glow-border {
  border: 1px solid rgba(212, 167, 55, 0.3);
  box-shadow: 
    0 0 10px rgba(212, 167, 55, 0.1),
    inset 0 0 10px rgba(212, 167, 55, 0.05);
}

/* 蓝色发光边框 */
.glow-border-blue {
  border: 1px solid rgba(74, 158, 255, 0.3);
  box-shadow: 
    0 0 10px rgba(74, 158, 255, 0.1),
    inset 0 0 10px rgba(74, 158, 255, 0.05);
}
```

#### 3. 几何装饰
```css
/* Warframe 风格的几何装饰 */
.deco-corner::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 20px;
  height: 20px;
  border-left: 2px solid #d4a737;
  border-top: 2px solid #d4a737;
}

.deco-corner::after {
  content: '';
  position: absolute;
  bottom: 0;
  right: 0;
  width: 20px;
  height: 20px;
  border-right: 2px solid #d4a737;
  border-bottom: 2px solid #d4a737;
}
```

#### 4. 背景纹理
```css
/* 暗纹背景 */
.dark-texture {
  background-image: 
    radial-gradient(circle at 20% 80%, rgba(212, 167, 55, 0.03) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(74, 158, 255, 0.03) 0%, transparent 50%),
    linear-gradient(180deg, rgba(0, 0, 0, 0.2) 0%, transparent 50%, rgba(0, 0, 0, 0.2) 100%);
}
```

### 动画设计

#### 1. 页面加载动画
```css
/* 元素逐个出现 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-in {
  animation: fadeInUp 0.6s ease-out forwards;
  opacity: 0;
}

/* 依次延迟 */
.delay-1 { animation-delay: 0.1s; }
.delay-2 { animation-delay: 0.2s; }
.delay-3 { animation-delay: 0.3s; }
.delay-4 { animation-delay: 0.4s; }
```

#### 2. 交互反馈动画
```css
/* 按钮点击效果 */
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(74, 158, 255, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(74, 158, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(74, 158, 255, 0); }
}

.btn-click {
  animation: pulse 0.6s ease-out;
}

/* 消息出现动画 */
@keyframes messageIn {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.message {
  animation: messageIn 0.4s ease-out;
}
```

#### 3. 价格变化动画
```css
/* 价格上涨 */
@keyframes priceUp {
  0% { background-color: transparent; }
  50% { background-color: rgba(74, 222, 128, 0.2); }
  100% { background-color: transparent; }
}

/* 价格下跌 */
@keyframes priceDown {
  0% { background-color: transparent; }
  50% { background-color: rgba(239, 68, 68, 0.2); }
  100% { background-color: transparent; }
}

.price-up {
  animation: priceUp 1s ease-out;
  color: #4ade80;
}

.price-down {
  animation: priceDown 1s ease-out;
  color: #ef4444;
}
```

### 布局优化

#### 1. 侧边栏设计
- **宽度**：300px（增加 20px）
- **背景**：深色渐变 + 暗纹
- **分隔线**：金色细线
- **列表项**：带几何装饰的卡片
- **图标**：使用 Warframe 风格的图标符号

#### 2. 主聊天区域
- **消息气泡**：带金色边框的圆角卡片
- **用户消息**：右侧对齐，蓝色渐变背景
- **Agent 消息**：左侧对齐，深色背景 + 金色边框
- **输入框**：带发光效果的输入框
- **发送按钮**：金色渐变 + 脉冲动画

#### 3. 详情面板
- **宽度**：400px（增加 40px）
- **标题**：大写字母 + 金色下划线
- **数据展示**：带图标的表格
- **图表**：使用 Warframe 配色的 Chart.js

### 细节设计

#### 1. 滚动条样式
```css
/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: #0c1020;
}

::-webkit-scrollbar-thumb {
  background: rgba(212, 167, 55, 0.3);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(212, 167, 55, 0.5);
}
```

#### 2. 选中状态
```css
/* 选中高亮 */
::selection {
  background: rgba(74, 158, 255, 0.3);
  color: #e0e0e0;
}
```

#### 3. 焦点状态
```css
/* 输入框焦点 */
#chat-input:focus {
  border-color: #d4a737;
  box-shadow: 
    0 0 0 2px rgba(212, 167, 55, 0.2),
    0 0 20px rgba(212, 167, 55, 0.1);
}
```

### 响应式设计

#### 移动端适配
```css
@media (max-width: 768px) {
  .container {
    flex-direction: column;
  }
  
  .sidebar {
    width: 100%;
    height: auto;
    max-height: 200px;
  }
  
  .detail-panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    z-index: 1000;
  }
  
  .chat-area {
    min-height: 60vh;
  }
}
```

### 交互设计

#### 1. 搜索建议下拉
- **背景**：深色半透明
- **边框**：金色发光边框
- **选中项**：蓝色高亮
- **动画**：从上往下滑入

#### 2. 模态弹窗
- **背景**：模糊 + 暗色遮罩
- **弹窗**：带几何装饰的卡片
- **动画**：缩放 + 淡入
- **关闭按钮**：X 图标 + 旋转动画

#### 3. 加载状态
- **加载动画**：Warframe 风格的旋转图标
- **骨架屏**：带闪烁效果的占位符
- **进度条**：金色渐变进度条

### 音效设计（可选）

- **消息发送**：轻快的点击音
- **价格提醒**：Warframe 风格的提示音
- **错误提示**：低沉的警告音
- **成功操作**：清脆的确认音

### 实现优先级

#### Phase 1：基础样式（必须）
- [x] 色彩方案实现
- [x] 字体引入和应用
- [x] 基础布局优化
- [x] 组件样式统一

#### Phase 2：视觉效果（推荐）
- [ ] 扫描线效果
- [ ] 光效边框
- [ ] 几何装饰
- [ ] 背景纹理

#### Phase 3：动画效果（推荐）
- [ ] 页面加载动画
- [ ] 交互反馈动画
- [ ] 价格变化动画
- [ ] 消息出现动画

#### Phase 4：细节优化（可选）
- [ ] 自定义滚动条
- [ ] 响应式适配
- [ ] 音效集成
- [ ] 性能优化

### 设计验证

#### 可用性测试
- [ ] 文字清晰易读
- [ ] 操作反馈及时
- [ ] 颜色对比度达标
- [ ] 动画不卡顿

#### 性能测试
- [ ] 页面加载时间 < 2s
- [ ] 动画帧率 > 60fps
- [ ] 内存占用合理
- [ ] 移动端流畅

### 设计资源

#### 字体
- Google Fonts: Orbitron, Rajdhani, JetBrains Mono
- 本地字体：无

#### 图标
- 自定义 SVG 图标
- Unicode 符号
- CSS 绘制的几何图形

#### 颜色
- 主色板：10 种颜色
- 渐变：5 种渐变
- 透明度：5 种透明度等级

### 设计规范

#### 命名规范
- 类名：kebab-case
- 变量：camelCase
- 常量：UPPER_SNAKE_CASE

#### 文件组织
```
/static/css/
  ├── style.css          # 主样式
  ├── variables.css      # CSS 变量
  ├── animations.css     # 动画定义
  ├── components.css     # 组件样式
  └── responsive.css     # 响应式样式
```

#### 注释规范
- 每个组件前添加注释
- 颜色值添加说明
- 动画效果添加描述

### 设计迭代

#### 版本历史
- v1.0：基础样式实现
- v1.1：添加视觉效果
- v1.2：优化动画效果
- v2.0：重新设计布局

#### 反馈收集
- 用户反馈渠道
- A/B 测试方案
- 数据分析指标

### 设计总结

通过以上设计，我们将 Warframe 交易助手打造成一个：
- **视觉独特**：具有 Warframe 游戏风格
- **交互流畅**：丰富的动画和过渡效果
- **信息清晰**：层次分明，易于阅读
- **体验沉浸**：让用户感觉自己在使用 Tenno 科技终端

这套设计不仅提升了用户体验，还让应用在众多交易工具中脱颖而出，成为真正属于 Warframe 玩家的专属工具。
