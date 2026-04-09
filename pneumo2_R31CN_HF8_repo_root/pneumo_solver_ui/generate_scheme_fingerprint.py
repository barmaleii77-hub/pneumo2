# -*- coding: utf-8 -*-
"""generate_scheme_fingerprint.py

Генератор эталонного отпечатка (fingerprint) топологии схемы.

Запуск (из папки pneumo_solver_ui):
    python generate_scheme_fingerprint.py

По умолчанию:
- берёт default_base.json
- строит сеть через model_pneumo_v9_doublewishbone_camozzi.build_network_full()
- пишет scheme_fingerprint.json рядом

Опции:
    python generate_scheme_fingerprint.py --model model_pneumo_v9_doublewishbone_camozzi.py --out scheme_fingerprint.json

"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys
from pneumo_solver_ui.module_loading import load_python_module_from_path


HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="model_pneumo_v9_doublewishbone_camozzi.py", help="Model .py file to import")
    ap.add_argument("--out", default="scheme_fingerprint.json", help="Output JSON file")
    ap.add_argument("--base", default="default_base.json", help="Params JSON (only to build network)")
    args = ap.parse_args()

    model_path = (HERE / args.model).resolve()
    out_path = (HERE / args.out).resolve()
    base_path = (HERE / args.base).resolve()

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not base_path.exists():
        raise FileNotFoundError(base_path)

    params = json.loads(base_path.read_text(encoding="utf-8"))

    model = load_python_module_from_path(model_path, "_model_for_fp")
    from scheme_integrity import canonicalize_scheme, fingerprint_scheme

    nodes, node_index, edges, B = model.build_network_full(params)

    canonical = canonicalize_scheme(nodes, edges)
    fp = fingerprint_scheme(canonical)

    payload = {
        "algo": "sha256",
        "fingerprint": fp,
        "canonical": canonical,
        "meta": {
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model_file": str(model_path.name),
            "base_params": str(base_path.name),
            "note": "Topology lock for pneumatic network. If you change scheme intentionally, regenerate.",
        }
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", out_path)
    print("fingerprint:", fp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
