# -*- coding: utf-8 -*-
"""Root launcher for the Qt-first desktop shell."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from pneumo_solver_ui.root_launcher_bootstrap import ensure_root_launcher_runtime


ROOT = Path(__file__).resolve().parent
MODULE = "pneumo_solver_ui.tools.desktop_main_shell_qt"


def main(argv: Sequence[str] | None = None) -> int:
    args = tuple(argv) if argv is not None else tuple(sys.argv[1:])
    os.chdir(str(ROOT))
    handoff_rc = ensure_root_launcher_runtime(
        root=ROOT,
        script_path=Path(__file__),
        module=MODULE,
        argv=args,
    )
    if handoff_rc is not None:
        return int(handoff_rc)
    from pneumo_solver_ui.tools import desktop_main_shell_qt

    return int(desktop_main_shell_qt.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
