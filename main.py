import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(src_path.parent))

from src.app import app
from src.config import FLASK_HOST, FLASK_PORT

if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
