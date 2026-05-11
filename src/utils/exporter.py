from pathlib import Path
from typing import Dict, List
import pandas as pd

from .common import sanitize_filename, get_timestamp_str


def export_csv(rows: List[Dict], base_name: str, output_dir: Path) -> Path:
    ts = get_timestamp_str()
    safe_name = sanitize_filename(base_name)
    output = output_dir / f"{safe_name}_{ts}.csv"
    df = pd.DataFrame(rows)
    df.to_csv(output, index=False, encoding='utf-8-sig')
    return output


def export_json(rows: List[Dict], base_name: str, output_dir: Path) -> Path:
    ts = get_timestamp_str()
    safe_name = sanitize_filename(base_name)
    output = output_dir / f"{safe_name}_{ts}.json"
    import json
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return output


def export_excel(rows: List[Dict], keyword: str, output_dir: Path) -> Path:
    ts = get_timestamp_str()
    safe_keyword = sanitize_filename(keyword)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"ssgdfs_{safe_keyword}_{ts}.xlsx"
    pd.DataFrame(rows).to_excel(output, index=False)
    return output
