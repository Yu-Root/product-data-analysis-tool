from pathlib import Path
from datetime import datetime
from typing import Dict, List
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .common import parse_price, sanitize_filename, get_timestamp_str


def generate_price_chart(product_name: str, price_history_data: List[Dict], output_dir: Path) -> Path:
    plt.figure(figsize=(12, 6))
    dates = [datetime.strptime(p['time'], "%Y-%m-%d %H:%M:%S") for p in price_history_data]
    prices = [parse_price(p['price']) for p in price_history_data]
    
    plt.plot(dates, prices, marker='o', linewidth=2, markersize=8, color='#0b63ce')
    plt.title(f'{product_name} - 价格历史趋势', fontsize=14, pad=20)
    plt.xlabel('时间', fontsize=12)
    plt.ylabel('价格 (USD)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    ts = get_timestamp_str()
    safe_name = sanitize_filename(product_name)
    output = output_dir / f"price_chart_{safe_name}_{ts}.png"
    plt.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    return output
