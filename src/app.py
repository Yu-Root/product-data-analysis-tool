import json
import time
import csv
import io
import threading
from datetime import datetime
from typing import Dict

from flask import Flask, render_template, request, send_file, url_for, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from src.config import (
    OUTPUT_DIR,
    TEMPLATES_DIR,
    STATIC_DIR,
    HISTORY_FILE,
    PRICE_HISTORY_FILE,
    MERGED_ITEMS_FILE,
    CACHE_TTL_SECONDS,
    MAX_HISTORY_SHOW,
    FLASK_HOST,
    FLASK_PORT,
)
from src.utils import (
    format_duration,
    deduplicate_rows,
    export_csv,
    export_json,
    append_history,
    read_history,
    delete_single_history_item,
    generate_price_chart,
)
from src.services import scrape, export_excel, TaskManager

app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1, x_proto=1, x_host=1)

SCRAPE_CACHE: Dict[str, Dict] = {}
task_manager = TaskManager(OUTPUT_DIR)


@app.get("/")
def index():
    return render_template("index.html", rows=[], history=read_history(MAX_HISTORY_SHOW, OUTPUT_DIR))


@app.post("/upload-keywords")
def upload_keywords():
    if 'file' not in request.files:
        return jsonify({"error": "未找到文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400
    
    keywords = []
    try:
        if file.filename.endswith('.txt'):
            content = file.read().decode('utf-8')
            for line in content.splitlines():
                line = line.strip()
                if line:
                    keywords.append(line)
        elif file.filename.endswith('.csv'):
            content = file.read().decode('utf-8')
            reader = csv.reader(io.StringIO(content))
            for row in reader:
                if row and row[0].strip():
                    keywords.append(row[0].strip())
    except Exception as e:
        return jsonify({"error": f"文件解析失败: {str(e)}"}), 400
    
    return jsonify({"keywords": keywords})


@app.post("/create-task")
def create_task():
    data = request.get_json()
    keywords = data.get('keywords', [])
    if not keywords or len(keywords) == 0:
        return jsonify({"error": "关键词列表不能为空"}), 400
    
    task_id = task_manager.create_task(keywords)
    thread = threading.Thread(target=task_manager.run_task_worker, args=(task_id,), daemon=True)
    thread.start()
    
    return jsonify({"task_id": task_id})


@app.get("/api/tasks")
def get_tasks():
    return jsonify(task_manager.get_all_tasks())


@app.post("/api/tasks/<task_id>/cancel")
def cancel_task(task_id):
    if task_manager.cancel_task(task_id):
        return jsonify({"success": True})
    return jsonify({"error": "任务不存在"}), 404


@app.post("/generate")
def generate():
    start = time.time()
    keyword = (request.form.get("keyword") or "").strip()
    if not keyword:
        return render_template("index.html", error="请输入关键词", rows=[], history=read_history(MAX_HISTORY_SHOW, OUTPUT_DIR))
    
    cache_hit = False
    try:
        now = time.time()
        cache_item = SCRAPE_CACHE.get(keyword)
        if cache_item and (now - cache_item["ts"] <= CACHE_TTL_SECONDS):
            rows = cache_item["rows"]
            cache_hit = True
        else:
            rows = scrape(keyword)
            rows = deduplicate_rows(rows)
            SCRAPE_CACHE[keyword] = {"ts": now, "rows": rows}
    except Exception as exc:
        return render_template("index.html", error=f"抓取失败: {exc}", keyword=keyword, rows=[], history=read_history(MAX_HISTORY_SHOW, OUTPUT_DIR))
    
    if not rows:
        return render_template("index.html", keyword=keyword, rows=[], no_data=True, history=read_history(MAX_HISTORY_SHOW, OUTPUT_DIR))
    
    output_excel = export_excel(rows, keyword, OUTPUT_DIR)
    output_csv = export_csv(rows, keyword, OUTPUT_DIR)
    output_json = export_json(rows, keyword, OUTPUT_DIR)
    duration_ms = int((time.time() - start) * 1000)
    source = "cache" if cache_hit else "fresh"
    append_history(keyword, len(rows), output_excel.name, source, duration_ms)
    
    return render_template(
        "index.html",
        keyword=keyword,
        total=len(rows),
        rows=rows,
        download_url=url_for("download", filename=output_excel.name),
        download_url_csv=url_for("download", filename=output_csv.name),
        download_url_json=url_for("download", filename=output_json.name),
        file_name=output_excel.name,
        cache_hit=cache_hit,
        duration_ms=duration_ms,
        duration_text=format_duration(duration_ms),
        history=read_history(MAX_HISTORY_SHOW, OUTPUT_DIR),
    )


@app.get("/api/price-history")
def get_price_history():
    product_code = request.args.get('product_code', '')
    if not PRICE_HISTORY_FILE.exists():
        return jsonify([])
    
    lines = PRICE_HISTORY_FILE.read_text(encoding='utf-8').splitlines()
    history_data = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            if not product_code or item.get('product_code') == product_code:
                history_data.append(item)
        except:
            continue
    
    return jsonify(history_data)


@app.post("/api/price-history/add")
def add_price_record():
    data = request.get_json()
    product_code = (data.get('product_code') or '').strip()
    product_name = (data.get('product_name') or '').strip()
    price = (data.get('price') or '').strip()
    
    if not product_code or not price:
        return jsonify({"error": "参数不完整"}), 400
    
    record = {
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'product_code': product_code,
        'product_name': product_name,
        'price': price
    }
    
    with PRICE_HISTORY_FILE.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    return jsonify({"success": True})


@app.get("/api/price-chart")
def get_price_chart():
    product_code = request.args.get('product_code', '')
    product_name = request.args.get('product_name', '商品')
    if not PRICE_HISTORY_FILE.exists():
        return "暂无价格历史数据", 404
    
    lines = PRICE_HISTORY_FILE.read_text(encoding='utf-8').splitlines()
    history_data = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            if item.get('product_code') == product_code:
                history_data.append(item)
        except:
            continue
    
    if len(history_data) < 2:
        return "需要至少2条数据生成图表", 400
    
    chart_path = generate_price_chart(product_name, history_data, OUTPUT_DIR)
    return send_file(chart_path, mimetype='image/png')


@app.post("/api/merge-items")
def merge_items():
    data = request.get_json()
    items = data.get('items', [])
    merged_name = data.get('merged_name', '合并商品')
    
    if len(items) < 2:
        return jsonify({"error": "请选择至少2个商品进行合并"}), 400
    
    merged_record = {
        'id': f"merged_{int(time.time())}",
        'merged_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'merged_name': merged_name,
        'items': items
    }
    
    existing = []
    if MERGED_ITEMS_FILE.exists():
        try:
            with open(MERGED_ITEMS_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            existing = []
    
    existing.append(merged_record)
    with MERGED_ITEMS_FILE.open('w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    return jsonify({"success": True, "merged_record": merged_record})


@app.post("/clear-cache")
def clear_cache():
    SCRAPE_CACHE.clear()
    return render_template("index.html", rows=[], history=read_history(MAX_HISTORY_SHOW, OUTPUT_DIR), message="缓存已清空")


@app.post("/clear-history")
def clear_history():
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    return render_template("index.html", rows=[], history=[], message="生成记录已清空")


@app.post("/clear-history-and-files")
def clear_history_and_files():
    deleted = 0
    missing = 0
    if HISTORY_FILE.exists():
        lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            file_name = (record.get("file_name") or "").strip()
            if not file_name:
                continue
            target = OUTPUT_DIR / file_name
            if target.exists() and target.is_file():
                target.unlink()
                deleted += 1
            else:
                missing += 1
        HISTORY_FILE.unlink()
    return render_template(
        "index.html",
        rows=[],
        history=[],
        message=f"记录已清空，已删除文件 {deleted} 个，缺失 {missing} 个",
    )


@app.post("/delete-history-item")
def delete_history_item():
    keyword = (request.form.get("keyword") or "").strip()
    record_time = (request.form.get("record_time") or "").strip()
    file_name = (request.form.get("file_name") or "").strip()
    
    if not HISTORY_FILE.exists():
        return render_template("index.html", rows=[], history=[], message="记录文件不存在")
    
    success = delete_single_history_item(keyword, record_time, file_name)
    msg = "单条记录已删除" if success else "未找到要删除的记录"
    return render_template("index.html", rows=[], history=read_history(MAX_HISTORY_SHOW, OUTPUT_DIR), message=msg)


@app.get("/download/<path:filename>")
def download(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return "文件不存在", 404
    return send_file(file_path, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
