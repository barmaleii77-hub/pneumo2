# -*- coding: utf-8 -*-
"""Root launcher for the desktop control center.

This wrapper exists so operators can start the desktop control center from the
repository root, in the same style as START_PNEUMO_APP.*.
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE = "pneumo_solver_ui.tools.desktop_control_center"


def main() -> int:
    os.chdir(str(ROOT))
    runpy.run_module(MODULE, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
