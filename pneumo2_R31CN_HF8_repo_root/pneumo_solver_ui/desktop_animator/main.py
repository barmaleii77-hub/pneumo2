# -*- coding: utf-8 -*-
"""Desktop Animator entrypoint.

Examples:
  # Follow latest export from Streamlit UI
  python -m pneumo_solver_ui.desktop_animator.main --follow

  # Open a specific NPZ
  python -m pneumo_solver_ui.desktop_animator.main --npz path\to\file.npz

The app is meant to be used together with the Streamlit UI:
- UI exports anim_latest.npz + anim_latest.json pointer
- Desktop app watches the pointer and hot-reloads
"""

from __future__ import annotations

import argparse
import os
import sys

# Diagnostics/logging bootstrap (ABSOLUTE LAW: everything must be logged).
from pneumo_solver_ui.diag.bootstrap import bootstrap as _diag_bootstrap
_diag_bootstrap("DesktopAnimator")
from pathlib import Path
from pneumo_solver_ui.desktop_animator.pointer_paths import default_anim_pointer_path


def _default_pointer() -> Path:
    return default_anim_pointer_path(Path(__file__).resolve().parents[2])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pneumo-desktop-animator")
    ap.add_argument("--npz", type=str, default="", help="Путь к NPZ-файлу анимационной выгрузки")
    ap.add_argument("--follow", action="store_true", help="Следить за указателем anim_latest.json")
    ap.add_argument(
        "--analysis-context",
        type=str,
        default=os.environ.get("PNEUMO_ANALYSIS_CONTEXT_PATH", ""),
        help="Путь к frozen HO-008 analysis_context.json",
    )
    ap.add_argument(
        "--pointer",
        type=str,
        default="",
        help="Путь к JSON-указателю anim_latest",
    )
    ap.add_argument("--no-gl", action="store_true", help="Отключить 3D OpenGL вид")
    ap.add_argument("--theme", type=str, default="dark", choices=["dark", "light"], help="Тема интерфейса")

    args = ap.parse_args(argv)

    pointer_path = Path(args.pointer).expanduser().resolve() if args.pointer else _default_pointer()
    npz_path = Path(args.npz).expanduser().resolve() if args.npz else None
    analysis_context_path = (
        Path(args.analysis_context).expanduser().resolve()
        if str(args.analysis_context).strip()
        else None
    )

    try:
        from .app import run_app
    except Exception as e:
        print("Не удалось импортировать Desktop Animator.")
        print("Проверьте requirements_desktop_animator.txt")
        print(e)
        return 2

    return int(run_app(
        npz_path=npz_path,
        follow=bool(args.follow),
        pointer_path=pointer_path,
        analysis_context_path=analysis_context_path,
        theme=str(args.theme),
        enable_gl=not bool(args.no_gl),
    ))


if __name__ == "__main__":
    raise SystemExit(main())
