import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
EXPORT_DIR = DATA_DIR / "export"
ALIAS_PATH = DATA_DIR / "item_aliases.json"
GENERATED_ALIAS_PATH = DATA_DIR / "generated_aliases.json"
ITEMS_FULL_PATH = DATA_DIR / "items_full.json"
RAG_ITEMS_PATH = DATA_DIR / "rag_items.jsonl"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
AGENT_MEMORY_PATH = DATA_DIR / "agent_memory.json"
DICTIONARY_CACHE_PATH = DATA_DIR / "item_dictionary_cache.json"
MODEL_NAME = "warframe-agent"
ROUTER_MODEL_NAME = "qwen3:8b"
MARKET_API_BASE = "https://api.warframe.market/v2"
REQUEST_TIMEOUT_SECONDS = 15
TOP_ORDER_LIMIT = 5

# API 缓存
ORDER_CACHE_TTL = 60        # 订单缓存 TTL（秒）
STATS_CACHE_TTL = 300       # 统计数据缓存 TTL（秒）
CACHE_MAX_SIZE = 200        # 缓存最大条目数

# 外部云端模型
CLOUD_API_BASE = os.getenv("CLOUD_API_BASE", "https://gpt-agent.cc/v1")
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gpt-5.5")
CLOUD_MAX_TOKENS = 2048

# 模型路由策略: "auto" | "local" | "cloud"
MODEL_ROUTING = os.getenv("MODEL_ROUTING", "auto")

# 复杂度阈值：超过此值自动切换到云端
COMPLEXITY_THRESHOLD = 3  # 分数越高越复杂

# 多轮对话
CONTEXT_WINDOW = 6          # LLM 上下文中包含的最近对话轮数
MAX_HISTORY_MESSAGES = 20   # session 存储的消息硬上限

# 主动智能
TREND_THRESHOLD_PERCENT = 15    # 趋势变化百分比阈值
ANOMALY_THRESHOLD_PERCENT = 30  # 异常变化百分比阈值（触发建议）
PROACTIVE_SUGGESTION_LIMIT = 5  # 最近建议注入 LLM 的条数

# 语义 RAG
EMBEDDING_MODEL = "nomic-embed-text"      # Ollama embedding 模型
EMBEDDING_CACHE_PATH = DATA_DIR / "rag_embeddings.npz"
EMBEDDING_ENABLED = True                  # 是否启用语义搜索

# 推理规划
MAX_TOOL_ITERATIONS = 3                   # ReAct 循环最大轮数
REACT_MODEL = "qwen3:8b"                 # ReAct 推理模型

# 深层智能
PATTERN_DISCOVERY_INTERVAL = 12   # 模式发现周期（每 N 次扫描，≈1 小时）
GOAL_GENERATION_INTERVAL = 6      # 目标生成周期（每 N 次扫描，≈30 分钟）
DYNAMIC_PLAN_MAX_ITERATIONS = 3   # 动态执行最大轮数
DYNAMIC_PLAN_TIMEOUT_SECONDS = 120  # 动态执行超时

# 知识库 + 规则引擎
PUSH_CONFIG_PATH = DATA_DIR / "push_config.json"
FEISHU_CONFIG_PATH = DATA_DIR / "feishu_config.json"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.json"
KNOWLEDGE_UPDATE_INTERVAL = 3      # 每 N 次扫描更新知识库
EVENT_REFRESH_INTERVAL = 1800      # 游戏事件刷新间隔（秒）
MAX_AUTO_GOALS = 3                 # 自动目标上限
DEFAULT_VOLATILITY_HIGH = 50       # 默认高波动率阈值（被 AdaptiveThresholds 覆盖）
DEFAULT_VOLATILITY_LOW = 20        # 默认低波动率阈值
DEFAULT_ROI_THRESHOLD = 30         # 默认 ROI 阈值
DEFAULT_MIN_PROFIT = 5             # 默认最小利润

EXPORT_FILE_PAIRS = [
    ("ExportRelicArcane_zh.json", "ExportRelicArcane_en.json"),
    ("ExportUpgrades_zh.json", "ExportUpgrades_en.json"),
    ("ExportWarframes_zh.json", "ExportWarframes_en.json"),
    ("ExportWeapons_zh.json", "ExportWeapons_en.json"),
]

# 多模型预筛选配置（共用同一个 API endpoint，通过 model 参数切换）
SCOUT_MODELS = {
    "mod_flipper": os.getenv("SCOUT_MOD_MODEL", "kimi-k2.6"),
    "set_profit":  os.getenv("SCOUT_SET_MODEL", "glm-5.1"),
    "investment":  os.getenv("SCOUT_INV_MODEL", "gpt-5.5"),
}
SCOUT_CACHE_TTL = 600  # 预筛选结果缓存 10 分钟
SCOUT_MAX_CANDIDATES = {
    "mod_flipper": 10,
    "set_profit": 5,
    "investment": 8,
}
