import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.config import TASK_FILE
from src.utils import deduplicate_rows, export_csv, export_json, append_history
from src.services.scraper import scrape, export_excel


class TaskManager:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.tasks: Dict[str, Dict] = {}
        self.task_lock = threading.Lock()
        self._load_tasks()

    def _load_tasks(self):
        if TASK_FILE.exists():
            try:
                with open(TASK_FILE, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
            except:
                self.tasks = {}

    def _save_tasks(self):
        with TASK_FILE.open('w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)

    def create_task(self, keywords: List[str]) -> str:
        task_id = f"task_{int(time.time() * 1000)}"
        with self.task_lock:
            self.tasks[task_id] = {
                'id': task_id,
                'keywords': keywords,
                'status': 'pending',
                'progress': 0,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'current_keyword': '',
                'result_count': 0,
                'files': {},
                'error': ''
            }
            self._save_tasks()
        return task_id

    def get_all_tasks(self) -> List[Dict]:
        with self.task_lock:
            return list(self.tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        with self.task_lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = 'canceled'
                self._save_tasks()
                return True
        return False

    def get_task_status(self, task_id: str) -> Dict | None:
        return self.tasks.get(task_id)

    def run_task_worker(self, task_id: str):
        try:
            with self.task_lock:
                self.tasks[task_id]['status'] = 'running'
                self.tasks[task_id]['progress'] = 0
                self._save_tasks()
            
            task_data = self.tasks[task_id]
            keywords = task_data['keywords']
            all_rows = []
            total_keywords = len(keywords)
            
            for idx, kw in enumerate(keywords):
                try:
                    rows = scrape(kw.strip())
                    all_rows.extend(rows)
                    with self.task_lock:
                        self.tasks[task_id]['progress'] = int(((idx + 1) / total_keywords) * 100)
                        self.tasks[task_id]['current_keyword'] = kw
                        self._save_tasks()
                except Exception as e:
                    print(f"Error scraping keyword {kw}: {e}")
                    continue
            
            all_rows = deduplicate_rows(all_rows)
            output_excel = export_excel(all_rows, f"批量_{len(keywords)}词", self.output_dir)
            output_csv = export_csv(all_rows, f"批量_{len(keywords)}词", self.output_dir)
            output_json = export_json(all_rows, f"批量_{len(keywords)}词", self.output_dir)
            
            with self.task_lock:
                self.tasks[task_id]['status'] = 'completed'
                self.tasks[task_id]['result_count'] = len(all_rows)
                self.tasks[task_id]['files'] = {
                    'excel': output_excel.name,
                    'csv': output_csv.name,
                    'json': output_json.name
                }
                self.tasks[task_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_tasks()
                
                append_history(
                    f"批量任务({len(keywords)}词)",
                    len(all_rows),
                    output_excel.name,
                    'batch',
                    0,
                    {'task_id': task_id}
                )
        except Exception as e:
            with self.task_lock:
                self.tasks[task_id]['status'] = 'failed'
                self.tasks[task_id]['error'] = str(e)
                self._save_tasks()
