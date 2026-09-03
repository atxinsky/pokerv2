"""读取项目目录 .env，不覆盖已有环境变量。"""

from __future__ import annotations

import os
from pathlib import Path

_LOADED = False


def load_dotenv() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    roots = [Path.cwd(), Path(__file__).resolve().parent.parent]
    for root in roots:
        p = root / ".env"
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break
