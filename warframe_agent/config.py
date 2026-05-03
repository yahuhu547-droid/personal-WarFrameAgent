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

EXPORT_FILE_PAIRS = [
    ("ExportRelicArcane_zh.json", "ExportRelicArcane_en.json"),
    ("ExportUpgrades_zh.json", "ExportUpgrades_en.json"),
    ("ExportWarframes_zh.json", "ExportWarframes_en.json"),
]
