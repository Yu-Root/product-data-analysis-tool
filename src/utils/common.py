import re
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


def format_duration(duration_ms: int) -> str:
    total_seconds = max(0, int(duration_ms // 1000))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_price(price_str: str) -> float:
    if not price_str:
        return 0.0
    nums = re.findall(r'[\d,.]+', price_str)
    if nums:
        try:
            return float(nums[0].replace(',', ''))
        except:
            pass
    return 0.0


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def get_timestamp_str() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")
