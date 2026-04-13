# -*- coding: utf-8 -*-
"""Root launcher for the classic desktop shell."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE = "pneumo_solver_ui.tools.desktop_main_shell"


def main() -> int:
    os.chdir(str(ROOT))
    runpy.run_module(MODULE, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
