# -*- coding: utf-8 -*-
"""Root launcher for the desktop optimizer center."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE = "pneumo_solver_ui.tools.desktop_optimizer_center"


def main() -> int:
    os.chdir(str(ROOT))
    runpy.run_module(MODULE, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
