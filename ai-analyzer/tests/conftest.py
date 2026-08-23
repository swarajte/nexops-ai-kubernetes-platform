import os
import tempfile

os.environ["WATCH_ENABLED"] = "false"
_fd, _db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ.setdefault("SQLITE_PATH", _db)
