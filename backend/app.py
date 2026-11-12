"""Start ClimateInsight with ``python -m backend.app`` from the project root.

The original ``python backend/app.py`` and ``cd backend; python app.py``
launch styles remain supported. HTTP handlers live in backend.api.routes.
"""

import os
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.routes import app


def main():
    # Port 5000 is taken by the AirPlay Receiver on macOS, hence 5001.
    import uvicorn
    dev = os.getenv("DEV", "0") == "1"
    uvicorn.run(
        "backend.api.routes:app",
        host="127.0.0.1" if dev else os.getenv("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5001")),
        reload=dev,
        log_level="debug" if dev else "info",
    )


if __name__ == "__main__":
    main()
