# -*- coding: utf-8 -*-
"""Desktop pneumatic mnemonic viewer entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from pneumo_solver_ui.desktop_animator.pointer_paths import default_anim_pointer_path


def _default_pointer() -> Path:
    return default_anim_pointer_path(Path(__file__).resolve().parents[2])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pneumo-desktop-mnemo")
    ap.add_argument("--npz", type=str, default="", help="Path to NPZ log file")
    ap.add_argument("--follow", action="store_true", help="Follow anim_latest.json pointer")
    ap.add_argument(
        "--pointer",
        type=str,
        default="",
        help="Pointer json path (default: current workspace global pointer, then session/local fallbacks)",
    )
    ap.add_argument("--theme", type=str, default="dark", choices=["dark", "light"], help="UI theme")

    args = ap.parse_args(argv)

    pointer_path = Path(args.pointer).expanduser().resolve() if args.pointer else _default_pointer()
    npz_path = Path(args.npz).expanduser().resolve() if args.npz else None

    try:
        from .app import run_app
    except Exception as exc:
        print("Failed to import Desktop Mnemo.")
        print("Install PySide6 and desktop animator dependencies first.")
        print(exc)
        return 2

    return int(
        run_app(
            npz_path=npz_path,
            follow=bool(args.follow),
            pointer_path=pointer_path,
            theme=str(args.theme),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
