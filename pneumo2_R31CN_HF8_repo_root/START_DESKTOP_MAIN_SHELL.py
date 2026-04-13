# -*- coding: utf-8 -*-
"""Root launcher for the classic desktop shell."""

from __future__ import annotations

import os
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path

from pneumo_solver_ui.root_launcher_bootstrap import ensure_root_launcher_runtime


ROOT = Path(__file__).resolve().parent
MODULE = "pneumo_solver_ui.tools.desktop_main_shell"


def main(argv: Sequence[str] | None = None) -> int:
    os.chdir(str(ROOT))
    handoff_rc = ensure_root_launcher_runtime(
        root=ROOT,
        script_path=Path(__file__),
        module=MODULE,
        argv=tuple(argv) if argv is not None else tuple(sys.argv[1:]),
    )
    if handoff_rc is not None:
        return int(handoff_rc)
    runpy.run_module(MODULE, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
