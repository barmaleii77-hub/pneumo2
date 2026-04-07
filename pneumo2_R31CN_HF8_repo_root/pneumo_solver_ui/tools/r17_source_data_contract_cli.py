# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from ..r17_source_data_contract import build_machine_schema, validate_source_data
except Exception:  # pragma: no cover - direct script execution fallback
    from r17_source_data_contract import build_machine_schema, validate_source_data  # type: ignore


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate canonical R17 source-data JSON.")
    ap.add_argument("json_path", nargs="?", help="Path to source-data JSON to validate.")
    ap.add_argument("--schema", action="store_true", help="Print machine-readable schema and exit.")
    ap.add_argument("--allow-partial", action="store_true", help="Do not require all R17 fields.")
    ap.add_argument("--no-unknown-warnings", action="store_true", help="Do not warn about non-canonical keys.")
    ns = ap.parse_args()

    if ns.schema:
        print(json.dumps(build_machine_schema(), ensure_ascii=False, indent=2))
        return 0

    if not ns.json_path:
        ap.error("json_path is required unless --schema is used")

    path = Path(ns.json_path)
    data = _load_json(path)
    result = validate_source_data(
        data,
        require_complete=not bool(ns.allow_partial),
        warn_unknown_keys=not bool(ns.no_unknown_warnings),
    )
    payload = {
        "ok": result.ok,
        "errors": [issue.__dict__ for issue in result.errors],
        "warnings": [issue.__dict__ for issue in result.warnings],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
