# -*- coding: utf-8 -*-
"""GUI launcher wrapper for the desktop optimizer center."""

from __future__ import annotations

import os
import runpy
import time
import traceback
from pathlib import Path


def _boot_log_path() -> Path:
    try:
        if os.name == "nt":
            base = Path(
                os.environ.get("LOCALAPPDATA")
                or os.environ.get("APPDATA")
                or str(Path.home() / "AppData" / "Local")
            )
            return base / "UnifiedPneumoApp" / "logs" / "desktop_optimizer_center_bootstrap.log"
        return Path.home() / ".unified_pneumoapp" / "logs" / "desktop_optimizer_center_bootstrap.log"
    except Exception:
        return Path("desktop_optimizer_center_bootstrap.log")


def _boot_log(message: str) -> None:
    try:
        path = _boot_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def _msgbox(title: str, message: str) -> None:
    try:
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000010)
        else:
            print(title)
            print(message)
    except Exception:
        pass


def _main() -> None:
    target = Path(__file__).with_name("START_DESKTOP_OPTIMIZER_CENTER.py")
    _boot_log(f"START_DESKTOP_OPTIMIZER_CENTER.pyw launching {target}")
    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        _boot_log("FATAL exception in desktop optimizer center wrapper:\n" + tb)
        _msgbox(
            "Desktop Optimizer Center crashed",
            "Лаунчер desktop optimizer center завершился с ошибкой.\n\n"
            f"Bootstrap log: {_boot_log_path()}\n\n"
            "Скопируйте лог и пришлите разработчику.",
        )
        raise


if __name__ == "__main__":
    _main()
