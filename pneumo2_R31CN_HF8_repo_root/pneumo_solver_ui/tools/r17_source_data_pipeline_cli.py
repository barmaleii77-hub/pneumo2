# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ..r17_source_data_pipeline import (
        dump_json,
        dump_report_csv,
        dump_report_md,
        dump_template_csv,
        issues_to_rows,
        load_json,
        load_manual_csv,
        merge_notes_to_rows,
        merge_partial_with_manual_rows,
        validate_merged_source_data,
    )
except Exception:  # pragma: no cover
    from r17_source_data_pipeline import (  # type: ignore
        dump_json,
        dump_report_csv,
        dump_report_md,
        dump_template_csv,
        issues_to_rows,
        load_json,
        load_manual_csv,
        merge_notes_to_rows,
        merge_partial_with_manual_rows,
        validate_merged_source_data,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="R17 canonical source-data pipeline CLI.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_template = sub.add_parser("template", help="Emit fillable canonical CSV template.")
    p_template.add_argument("output_csv")

    p_merge = sub.add_parser("merge", help="Merge partial R16-preserving JSON with manual canonical CSV and validate.")
    p_merge.add_argument("--partial-json", required=True)
    p_merge.add_argument("--manual-csv", required=True)
    p_merge.add_argument("--output-json", required=True)
    p_merge.add_argument("--allow-partial", action="store_true")
    p_merge.add_argument("--no-unknown-warnings", action="store_true")
    p_merge.add_argument("--report-csv")
    p_merge.add_argument("--report-md")

    ns = ap.parse_args()

    if ns.cmd == "template":
        out = Path(ns.output_csv)
        dump_template_csv(out)
        print(json.dumps({"ok": True, "output_csv": str(out)}, ensure_ascii=False, indent=2))
        return 0

    partial_json = Path(ns.partial_json)
    manual_csv = Path(ns.manual_csv)
    output_json = Path(ns.output_json)
    partial = load_json(partial_json)
    rows = load_manual_csv(manual_csv)
    merged, notes = merge_partial_with_manual_rows(partial, rows)
    dump_json(output_json, merged)
    issues = validate_merged_source_data(
        merged,
        allow_partial=bool(ns.allow_partial),
        warn_unknown_keys=not bool(ns.no_unknown_warnings),
    )
    payload = {
        "ok": not any(n.severity == "error" for n in notes) and not any(i.level == "error" for i in issues),
        "output_json": str(output_json),
        "merge_notes": [n.__dict__ for n in notes],
        "validation_issues": [i.__dict__ for i in issues],
    }
    if ns.report_csv:
        report_rows = merge_notes_to_rows(notes) + issues_to_rows(issues)
        dump_report_csv(Path(ns.report_csv), report_rows)
    if ns.report_md:
        dump_report_md(
            Path(ns.report_md),
            template_csv=None,
            partial_json=partial_json,
            manual_csv=manual_csv,
            output_json=output_json,
            notes=notes,
            issues=issues,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
