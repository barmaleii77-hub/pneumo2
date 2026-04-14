"""Launcher for the Qt-first desktop shell with legacy Tk fallback."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desktop_main_shell_qt",
        description="Qt-first Windows desktop shell for orchestrating native and managed-external GUI tools.",
    )
    parser.add_argument(
        "--open",
        dest="startup_tool_keys",
        action="append",
        default=[],
        metavar="KEY",
        help="Open a shell tool by registry key on startup. Can be repeated.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Print available shell tool keys and exit.",
    )
    parser.add_argument(
        "--legacy-tk-shell",
        action="store_true",
        help="Run the historical Tk shell instead of the new Qt shell.",
    )
    return parser


def format_tool_catalog() -> str:
    lines = ["Desktop shell tools (Qt shell catalog):"]
    for spec in build_desktop_shell_specs():
        lines.append(
            "\t".join(
                (
                    spec.key,
                    spec.group,
                    spec.title,
                    spec.effective_runtime_kind,
                    spec.effective_migration_status,
                )
            )
        )
    return "\n".join(lines)


def resolve_startup_tool_keys(keys: Sequence[str]) -> tuple[str, ...]:
    allowed_keys = {spec.key for spec in build_desktop_shell_specs()}
    normalized = tuple(key.strip() for key in keys if key and key.strip())
    invalid = [key for key in normalized if key not in allowed_keys]
    if invalid:
        valid_keys = ", ".join(sorted(allowed_keys))
        invalid_keys = ", ".join(invalid)
        raise SystemExit(
            f"Unknown desktop shell tool key(s): {invalid_keys}. "
            f"Available keys: {valid_keys}"
        )
    return normalized


def _run_legacy_shell(*, startup_tool_keys: tuple[str, ...]) -> int:
    from pneumo_solver_ui.tools import desktop_main_shell as legacy_shell

    return int(legacy_shell.main(startup_tool_keys))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_tools:
        print(format_tool_catalog())
        return 0

    startup_tool_keys = resolve_startup_tool_keys(args.startup_tool_keys)
    if args.legacy_tk_shell:
        return _run_legacy_shell(startup_tool_keys=startup_tool_keys)

    try:
        import PySide6  # noqa: F401
        from pneumo_solver_ui.desktop_qt_shell.main_window import main as run_qt_shell_main
    except Exception as exc:
        print(
            f"[desktop_main_shell_qt] Qt shell is unavailable, fallback to legacy Tk shell: {exc}",
            file=sys.stderr,
        )
        return _run_legacy_shell(startup_tool_keys=startup_tool_keys)

    return int(run_qt_shell_main(startup_tool_keys=startup_tool_keys))


if __name__ == "__main__":
    raise SystemExit(main())
