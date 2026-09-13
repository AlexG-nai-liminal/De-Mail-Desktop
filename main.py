"""Source and deployment entry point for de-Mail Desktop."""

import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from demail.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
