"""Launcher for the desktop main shell with a legacy fallback."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desktop_main_shell_qt",
        description="Windows desktop main shell for orchestrating PneumoApp GUI tools.",
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
        help="Run the historical shell instead of the current desktop shell.",
    )
    parser.add_argument(
        "--runtime-proof",
        metavar="DIR",
        help="Write a desktop main shell runtime evidence JSON/MD pair and exit without launching domain windows.",
    )
    parser.add_argument(
        "--runtime-proof-offscreen",
        action="store_true",
        help="Collect --runtime-proof using QT_QPA_PLATFORM=offscreen for CI/headless checks.",
    )
    parser.add_argument(
        "--runtime-proof-manual-results",
        metavar="JSON",
        help=(
            "Merge operator-confirmed Snap/DPI/second-monitor results into --runtime-proof. "
            "The JSON may contain a 'checks' object keyed by manual check id."
        ),
    )
    parser.add_argument(
        "--runtime-proof-manual-template",
        metavar="DIR",
        help="Write a fillable manual-results JSON template for Snap/DPI/second-monitor evidence and exit.",
    )
    parser.add_argument(
        "--runtime-proof-validate",
        metavar="JSON",
        help="Validate an existing desktop main shell runtime proof JSON and exit.",
    )
    parser.add_argument(
        "--runtime-proof-require-manual-pass",
        action="store_true",
        help="Make --runtime-proof-validate fail unless manual Snap/DPI/second-monitor checks are PASS.",
    )
    return parser


def format_tool_catalog() -> str:
    lines = ["Desktop shell tools:"]
    for spec in build_desktop_shell_specs():
        lines.append(
            "\t".join(
                (
                    spec.key,
                    spec.group,
                    spec.title,
                    spec.effective_runtime_kind,
                    spec.effective_source_of_truth_role,
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
    if args.runtime_proof_manual_template:
        from pneumo_solver_ui.desktop_qt_shell.runtime_proof import (
            write_qt_main_shell_manual_results_template,
        )

        result = write_qt_main_shell_manual_results_template(
            Path(args.runtime_proof_manual_template)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.runtime_proof_validate:
        from pneumo_solver_ui.desktop_qt_shell.runtime_proof import (
            validate_qt_main_shell_runtime_proof,
        )

        result = validate_qt_main_shell_runtime_proof(
            Path(args.runtime_proof_validate),
            require_manual_pass=bool(args.runtime_proof_require_manual_pass),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    if args.runtime_proof:
        from pneumo_solver_ui.desktop_qt_shell.runtime_proof import write_qt_main_shell_runtime_proof

        result = write_qt_main_shell_runtime_proof(
            Path(args.runtime_proof),
            offscreen=bool(args.runtime_proof_offscreen),
            manual_results_path=Path(args.runtime_proof_manual_results)
            if args.runtime_proof_manual_results
            else None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.legacy_tk_shell:
        return _run_legacy_shell(startup_tool_keys=startup_tool_keys)

    try:
        import PySide6  # noqa: F401
        from pneumo_solver_ui.desktop_qt_shell.main_window import main as run_qt_shell_main
    except Exception as exc:
        print(
            f"[desktop_main_shell_qt] current shell is unavailable, fallback to historical shell: {exc}",
            file=sys.stderr,
        )
        return _run_legacy_shell(startup_tool_keys=startup_tool_keys)

    return int(run_qt_shell_main(startup_tool_keys=startup_tool_keys))


if __name__ == "__main__":
    raise SystemExit(main())
