from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src"
OUTPUT_DIR = SRC_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATES_DIR = SRC_DIR / "templates"
STATIC_DIR = SRC_DIR / "static"

HISTORY_FILE = OUTPUT_DIR / "generation_history.jsonl"
PRICE_HISTORY_FILE = OUTPUT_DIR / "price_history.jsonl"
TASK_FILE = OUTPUT_DIR / "tasks.json"
MERGED_ITEMS_FILE = OUTPUT_DIR / "merged_items.json"

CACHE_TTL_SECONDS = 900
MAX_HISTORY_SHOW = 100

ANTI_BOT_MARKERS: List[str] = [
    "temporary connection issue",
    "a temporary connection issue occurred",
    "잠시 연결에 문제가 발생했습니다",
    "但刚才出现了短暂的连接问题",
    "连接问题",
]

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
