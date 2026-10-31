"""รีโหลดโมดูลใน core/* อัตโนมัติเมื่อไฟล์ถูกแก้ไข เพื่อไม่ต้องปิด-เปิด Streamlit ใหม่"""
from __future__ import annotations

import importlib
from pathlib import Path
import sys

_MTIMES: dict[str, float] = {}
_ORDER = ("core.db", "core.loader", "core.pipeline", "core.metrics", "core.export", "core.ui")


def ensure_fresh() -> None:
    core_dir = Path(__file__).resolve().parent
    need_reload = False
    for mod_name in _ORDER:
        short = mod_name.split(".")[1]
        fpath = core_dir / f"{short}.py"
        if not fpath.exists():
            continue
        mtime = fpath.stat().st_mtime
        if mod_name in sys.modules:
            if _MTIMES.get(mod_name) != mtime:
                need_reload = True
        _MTIMES[mod_name] = mtime

    if need_reload:
        for mod_name in _ORDER:
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
