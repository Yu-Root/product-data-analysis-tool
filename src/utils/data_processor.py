from typing import Dict, List


def deduplicate_rows(rows: List[Dict]) -> List[Dict]:
    seen = set()
    result = []
    for row in rows:
        key1 = (row.get("商品编码") or "").strip()
        key2 = (row.get("RefNO") or "").strip()
        key3 = (row.get("品牌") or "").strip() + "||" + (row.get("商品名") or "").strip()
        unique_key = f"{key1}|{key2}|{key3}"
        if unique_key not in seen:
            seen.add(unique_key)
            result.append(row)
    return result
