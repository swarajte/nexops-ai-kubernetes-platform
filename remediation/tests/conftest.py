import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["WATCH_NAMESPACE"] = "nexops"
os.environ["SQLITE_PATH"] = str(ROOT / ".test-remediations.db")
