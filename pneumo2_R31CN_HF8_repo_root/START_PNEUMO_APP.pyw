# -*- coding: utf-8 -*-
"""GUI launcher wrapper.

This .pyw file intentionally delegates *all* logic to START_PNEUMO_APP.py.

It also provides a *minimal* safety net:
- .pyw has no console, so unhandled exceptions can look like a "silent" crash.
- We always write a bootstrap log to %LOCALAPPDATA%\\UnifiedPneumoApp\\logs.
- We show a user-friendly MessageBox with the path to that log.

Rationale:
- Keeping two separate launcher implementations (.py and .pyw) is a silent source of drift.
- Drift already caused real regressions (e.g. broken shared-venv locking / pyvenv.cfg race).
- Having a single source of truth enforces the project "absolute law": no hidden aliases,
  no duplicated logic that can diverge.
"""

from __future__ import annotations

import os
import runpy
import sys
import time
import traceback
from pathlib import Path


def _boot_log_path() -> Path:
    """Return best-effort bootstrap log path.

    Must never raise. This is used for early failures when normal logging is not ready.
    """
    try:
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Local"))

            # Microsoft Store Python may transparently redirect %LOCALAPPDATA% into package LocalCache.
            # Use physical path so bootstrap logs are discoverable and consistent with the launcher.
            exe_l = str(Path(sys.executable)).lower()
            if ("\\microsoft\\windowsapps\\" in exe_l) and ("pythonsoftwarefoundation.python" in exe_l):
                parts = list(Path(sys.executable).parts)
                pkg = None
                for i, p in enumerate(parts):
                    if p.lower() == "windowsapps" and i + 1 < len(parts):
                        pkg = parts[i + 1]
                        break
                if pkg:
                    candidate = base / "Packages" / pkg / "LocalCache" / "Local"
                    if candidate.exists():
                        base = candidate

            return base / "UnifiedPneumoApp" / "logs" / "launcher_bootstrap.log"
        return Path.home() / ".unified_pneumoapp" / "logs" / "launcher_bootstrap.log"
    except Exception:
        return Path("launcher_bootstrap.log")


def _boot_log(msg: str) -> None:
    try:
        p = _boot_log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _msgbox(title: str, message: str) -> None:
    """Show message box without depending on Tkinter."""
    try:
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000010)  # MB_ICONERROR
        else:
            print(title)
            print(message)
    except Exception:
        pass


def _main() -> None:
    target = Path(__file__).with_name("START_PNEUMO_APP.py")
    _boot_log(f"START_PNEUMO_APP.pyw launching {target} (exe={sys.executable})")
    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        _boot_log("FATAL exception in .pyw wrapper:\n" + tb)
        p = _boot_log_path()
        _msgbox(
            "PneumoApp Launcher crashed",
            "Лаунчер упал до запуска GUI.\n\n"
            f"Bootstrap log: {p}\n\n"
            "Скопируйте лог и пришлите разработчику.",
        )
        raise


if __name__ == "__main__":
    _main()
