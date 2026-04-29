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

EXPORT_FILE_PAIRS = [
    ("ExportRelicArcane_zh.json", "ExportRelicArcane_en.json"),
    ("ExportUpgrades_zh.json", "ExportUpgrades_en.json"),
    ("ExportWarframes_zh.json", "ExportWarframes_en.json"),
]
