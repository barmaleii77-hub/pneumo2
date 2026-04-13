# -*- coding: utf-8 -*-
"""Root launcher for the desktop ring scenario editor."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE = "pneumo_solver_ui.tools.desktop_ring_scenario_editor"


def main() -> int:
    os.chdir(str(ROOT))
    runpy.run_module(MODULE, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
