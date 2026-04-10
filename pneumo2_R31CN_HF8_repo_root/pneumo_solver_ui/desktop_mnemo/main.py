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
    ap.add_argument("--startup-preset", type=str, default="", help="Optional launcher preset key for onboarding banner")
    ap.add_argument("--startup-title", type=str, default="", help="Optional onboarding title shown inside the desktop window")
    ap.add_argument("--startup-reason", type=str, default="", help="Optional onboarding reason shown inside the desktop window")
    ap.add_argument(
        "--startup-view-mode",
        type=str,
        default="",
        help="Optional one-off startup view override: focus or overview",
    )
    ap.add_argument("--startup-time-s", type=float, default=None, help="Optional one-off startup seek time in seconds")
    ap.add_argument(
        "--startup-time-label",
        type=str,
        default="",
        help="Optional human-readable startup time label for onboarding banner",
    )
    ap.add_argument(
        "--startup-edge",
        type=str,
        default="",
        help="Optional startup edge selection inferred from Desktop Mnemo event-log",
    )
    ap.add_argument(
        "--startup-node",
        type=str,
        default="",
        help="Optional startup node selection inferred from Desktop Mnemo event-log",
    )
    ap.add_argument(
        "--startup-event-title",
        type=str,
        default="",
        help="Optional startup event title used to focus the event-memory dock",
    )
    ap.add_argument(
        "--startup-time-ref-npz",
        type=str,
        default="",
        help="Optional NPZ path that startup-time hint belongs to; used to avoid applying it to the wrong dataset",
    )
    ap.add_argument(
        "--startup-check",
        action="append",
        default=[],
        help="Repeatable onboarding checklist item shown inside the desktop window",
    )

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
            startup_preset=str(args.startup_preset or ""),
            startup_title=str(args.startup_title or ""),
            startup_reason=str(args.startup_reason or ""),
            startup_view_mode=str(args.startup_view_mode or ""),
            startup_time_s=(float(args.startup_time_s) if args.startup_time_s is not None else None),
            startup_time_label=str(args.startup_time_label or ""),
            startup_edge=str(args.startup_edge or ""),
            startup_node=str(args.startup_node or ""),
            startup_event_title=str(args.startup_event_title or ""),
            startup_time_ref_npz=str(args.startup_time_ref_npz or ""),
            startup_checklist=list(args.startup_check or []),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
