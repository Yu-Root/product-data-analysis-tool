import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from src.config import HISTORY_FILE
from .common import format_duration


def append_history(keyword: str, total: int, file_name: str, source: str, duration_ms: int, extra: Dict = None) -> None:
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keyword": keyword,
        "total": total,
        "file_name": file_name,
        "source": source,
        "duration_ms": duration_ms,
        "duration_text": format_duration(duration_ms),
    }
    if extra:
        record.update(extra)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_history(limit: int, output_dir: Path) -> List[Dict]:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding='utf-8').splitlines()
    records = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    from flask import url_for
    for r in records:
        file_name = r.get("file_name") or ""
        file_path = output_dir / file_name if file_name else None
        r["file_exists"] = bool(file_path and file_path.exists())
        r["download_url"] = url_for("download", filename=file_name) if file_name else ""
    return records


def delete_single_history_item(keyword: str, record_time: str, file_name: str) -> bool:
    if not HISTORY_FILE.exists():
        return False
    
    kept = []
    removed = 0
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        
        same = (
            (record.get("keyword") or "") == keyword
            and (record.get("time") or "") == record_time
            and (record.get("file_name") or "") == file_name
        )
        if same and removed == 0:
            removed += 1
            continue
        kept.append(json.dumps(record, ensure_ascii=False))
    
    HISTORY_FILE.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed > 0
