# -*- coding: utf-8 -*-
"""
tools/svg_autotrace_cli.py

CLI утилита для офлайн-анализа SVG схемы и (опционально) генерации mapping JSON.

Зачем:
- быстро получить `svg_analysis.json` (nodes/edges/polylines/texts) из SVG без UI
- при наличии списка имён веток (edge_names) — построить черновой mapping.edges (auto)

Примеры:

  python tools/svg_autotrace_cli.py --svg assets/pneumo_scheme.svg --out out_autotrace

  python tools/svg_autotrace_cli.py --svg assets/pneumo_scheme.svg --edge-file assets/edge_names.txt --out out_autotrace

  python tools/svg_autotrace_cli.py --svg assets/pneumo_scheme.svg --edge-file assets/edge_names.txt --tol-merge 2.1 --label-dist 30 --simplify 1.0 --out out_autotrace

Выход:
  out_autotrace/svg_analysis.json
  out_autotrace/components_bbox.json
  (+ если задан --edge-file)
  out_autotrace/auto_mapping.json
  out_autotrace/auto_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# allow running from project root without installation
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from pneumo_solver_ui import svg_autotrace
except Exception as e:
    raise SystemExit(f"ERROR: cannot import pneumo_solver_ui.svg_autotrace: {e}")


def _read_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        out.append(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", required=True, help="Путь к .svg")
    ap.add_argument("--out", required=True, help="Папка вывода")

    ap.add_argument("--edge-file", default="", help="Текстовый файл со списком edge_names (по 1 имени в строке). Если не задан — auto_mapping не строится.")
    ap.add_argument("--node-file", default="", help="Текстовый файл со списком node_names (опционально).")

    ap.add_argument("--tol-merge", type=float, default=2.1, help="Слияние близких endpoints (px)")
    ap.add_argument("--label-dist", type=float, default=80.0, help="Макс. дистанция label->polyline (px) для auto mapping")
    ap.add_argument("--name-thr", type=float, default=0.75, help="Порог похожести имён для auto mapping (0..1)")
    ap.add_argument("--simplify", type=float, default=1.0, help="Упрощение полилиний (RDP epsilon, px). 0=выкл.")
    ap.add_argument("--snap-max", type=float, default=40.0, help="Макс. дистанция (px) для привязки узла к графу")
    ap.add_argument("--prefer-junction", action="store_true", help="При привязке узлов предпочитать узлы-стыки (degree!=2)")

    args = ap.parse_args()

    svg_path = Path(args.svg)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    svg_text = svg_path.read_text(encoding="utf-8", errors="ignore")

    analysis = svg_autotrace.extract_polylines(svg_text, tol_merge=args.tol_merge)
    (out_dir / "svg_analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    comps = svg_autotrace.detect_component_bboxes(svg_text)
    (out_dir / "components_bbox.json").write_text(json.dumps(comps, ensure_ascii=False, indent=2), encoding="utf-8")

    edge_names: list[str] = []
    node_names: list[str] = []
    if args.edge_file:
        edge_names = _read_names(Path(args.edge_file))
    if args.node_file:
        node_names = _read_names(Path(args.node_file))

    if edge_names:
        mapping, report = svg_autotrace.auto_build_mapping_from_svg(
            svg_text=svg_text,
            edge_names=edge_names,
            node_names=node_names if node_names else None,
            tol_merge=args.tol_merge,
            max_label_dist=args.label_dist,
            min_name_score=args.name_thr,
            simplify_epsilon=args.simplify,
            snap_nodes_to_graph=True,
            prefer_junctions=bool(args.prefer_junction),
            node_snap_max_dist=args.snap_max,
        )
        (out_dir / "auto_mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "auto_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK")
    print(" -", out_dir / "svg_analysis.json")
    print(" -", out_dir / "components_bbox.json")
    if edge_names:
        print(" -", out_dir / "auto_mapping.json")
        print(" -", out_dir / "auto_report.json")
    else:
        print(" - (skip auto_mapping: no --edge-file)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
