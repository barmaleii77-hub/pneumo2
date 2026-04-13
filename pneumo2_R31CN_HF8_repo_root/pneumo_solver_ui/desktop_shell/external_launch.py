from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def python_gui_exe() -> str:
    if os.name != "nt":
        return sys.executable

    try:
        exe = Path(sys.executable)
        if exe.name.lower() == "python.exe":
            pyw = exe.with_name("pythonw.exe")
            if pyw.exists():
                return str(pyw)
    except Exception:
        pass
    return sys.executable


def spawn_module(module: str, args: Sequence[str] | None = None) -> subprocess.Popen:
    cmd = [python_gui_exe(), "-m", module]
    if args:
        cmd.extend(str(item) for item in args)
    kwargs: dict[str, object] = {
        "cwd": str(repo_root()),
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(cmd, **kwargs)
