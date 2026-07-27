from __future__ import annotations

from pathlib import Path
import sys


PART3_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PART3_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from document_agent.web_app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
