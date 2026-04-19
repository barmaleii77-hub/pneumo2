"""Запуск классического модульного desktop-окна."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pneumo_solver_ui.desktop_shell.main_window import main as run_shell_main
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desktop_main_shell",
        description="Классическое Windows-окно для встроенных и внешних GUI-окон PneumoApp.",
    )
    parser.add_argument(
        "--open",
        dest="startup_tool_keys",
        action="append",
        default=[],
        metavar="KEY",
        help="Открыть GUI-окно по ключу реестра при запуске. Можно указать несколько раз.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Вывести доступные ключи GUI-окон и завершить работу.",
    )
    return parser


def format_tool_catalog() -> str:
    lines = ["GUI-окна рабочего места:"]
    for spec in build_desktop_shell_specs():
        lines.append(f"{spec.key}\t{spec.group}\t{spec.title}")
    return "\n".join(lines)


def resolve_startup_tool_keys(keys: Sequence[str]) -> tuple[str, ...]:
    allowed_keys = {spec.key for spec in build_desktop_shell_specs()}
    normalized = tuple(key.strip() for key in keys if key and key.strip())
    invalid = [key for key in normalized if key not in allowed_keys]
    if invalid:
        valid_keys = ", ".join(sorted(allowed_keys))
        invalid_keys = ", ".join(invalid)
        raise SystemExit(
            f"Неизвестный ключ GUI-окна: {invalid_keys}. "
            f"Доступные ключи: {valid_keys}"
        )
    return normalized


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_tools:
        print(format_tool_catalog())
        return 0

    startup_tool_keys = resolve_startup_tool_keys(args.startup_tool_keys)
    return run_shell_main(startup_tool_keys=startup_tool_keys)


if __name__ == "__main__":
    raise SystemExit(main())
