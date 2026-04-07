#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_npz_bundle.py

Offline inspection for a single NPZ bundle.

Goals:
- show the same canonical visual / anim diagnostics that Compare UI and Qt viewer use;
- avoid silent loss of current-vs-pointer token mismatches when a bundle is moved/extracted;
- provide one small JSON/Markdown summary for manual triage.

Example:
  python -m pneumo_solver_ui.tools.inspect_npz_bundle --npz workspace/exports/anim_latest.npz --print_summary
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np

from pneumo_solver_ui.compare_ui import load_npz_bundle, detect_time_col, extract_time_vector


def _table_summary(df) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        'rows': int(len(df)) if df is not None else 0,
        'cols': int(len(getattr(df, 'columns', []))) if df is not None else 0,
        'time_col': '',
        't0': None,
        't1': None,
        'dt_median': None,
    }
    if df is None or getattr(df, 'empty', True):
        return out
    time_col = detect_time_col(df)
    out['time_col'] = str(time_col or '')
    if time_col:
        try:
            t = np.asarray(extract_time_vector(df, time_col), dtype=float)
            if t.ndim == 1 and t.size:
                out['t0'] = float(t[0])
                out['t1'] = float(t[-1])
                if t.size >= 2:
                    dt = np.diff(t)
                    if dt.size:
                        out['dt_median'] = float(np.median(dt))
        except Exception:
            pass
    return out


def inspect_npz_bundle(npz_path: str | Path) -> Dict[str, Any]:
    p = Path(str(npz_path)).expanduser().resolve()
    bun = load_npz_bundle(p)
    tables = dict(bun.get('tables') or {})
    meta = dict(bun.get('meta') or {})
    visual = dict(bun.get('visual_contract') or {})
    anim = dict(bun.get('anim_diagnostics') or {})

    out: Dict[str, Any] = {
        'schema': 'inspect_npz_bundle',
        'schema_version': '1.0.0',
        'npz_path': str(p),
        'meta_preview': {
            'test_name': meta.get('test_name') or meta.get('имя_теста') or '',
            'release': meta.get('release') or meta.get('app_release') or '',
            'mode': meta.get('mode') or '',
        },
        'tables': {name: _table_summary(df) for name, df in tables.items()},
        'visual_contract': {
            'geometry_contract_ok': bool(visual.get('geometry_contract_ok')),
            'road_complete': bool(visual.get('road_complete')),
            'road_source': str(visual.get('road_source') or ''),
            'solver_points_complete': bool(visual.get('solver_points_complete')),
            'road_overlay_text': str(visual.get('road_overlay_text') or ''),
            'solver_points_overlay_text': str(visual.get('solver_points_overlay_text') or ''),
        },
        'anim_diagnostics': {
            'bundle_visual_cache_token': str(anim.get('bundle_visual_cache_token') or ''),
            'bundle_visual_reload_inputs': list(anim.get('bundle_visual_reload_inputs') or []),
            'pointer_visual_cache_token': str(anim.get('pointer_visual_cache_token') or ''),
            'pointer_visual_reload_inputs': list(anim.get('pointer_visual_reload_inputs') or []),
            'bundle_vs_pointer_token_match': anim.get('bundle_vs_pointer_token_match'),
            'bundle_vs_pointer_reload_inputs_match': anim.get('bundle_vs_pointer_reload_inputs_match'),
            'bundle_vs_pointer_npz_path_match': anim.get('bundle_vs_pointer_npz_path_match'),
            'local_pointer_json': str(anim.get('local_pointer_json') or ''),
            'global_pointer_json': str(anim.get('global_pointer_json') or ''),
            'triage_diagnostics_json': str(anim.get('triage_diagnostics_json') or ''),
            'pointer_sources_present': list(anim.get('pointer_sources_present') or []),
            'issues': list(anim.get('issues') or []),
        },
    }
    return out


def render_inspect_npz_bundle_md(rep: Dict[str, Any]) -> str:
    meta = dict(rep.get('meta_preview') or {})
    visual = dict(rep.get('visual_contract') or {})
    anim = dict(rep.get('anim_diagnostics') or {})
    tables = dict(rep.get('tables') or {})

    lines = [
        '# NPZ bundle inspection',
        '',
        f"NPZ: `{rep.get('npz_path', '')}`",
        '',
        '## Meta preview',
        '',
        f"- test_name: `{meta.get('test_name', '')}`",
        f"- release: `{meta.get('release', '')}`",
        f"- mode: `{meta.get('mode', '')}`",
        '',
        '## Visual contract',
        '',
        f"- geometry_contract_ok: `{visual.get('geometry_contract_ok')}`",
        f"- road_complete: `{visual.get('road_complete')}`",
        f"- road_source: `{visual.get('road_source', '')}`",
        f"- solver_points_complete: `{visual.get('solver_points_complete')}`",
    ]
    if str(visual.get('road_overlay_text') or '').strip():
        lines.append(f"- road_overlay_text: `{visual.get('road_overlay_text')}`")
    if str(visual.get('solver_points_overlay_text') or '').strip():
        lines.append(f"- solver_points_overlay_text: `{visual.get('solver_points_overlay_text')}`")

    lines += [
        '',
        '## Anim diagnostics',
        '',
        f"- current token: `{anim.get('bundle_visual_cache_token', '')}`",
        f"- current inputs: `{list(anim.get('bundle_visual_reload_inputs') or [])}`",
        f"- pointer token: `{anim.get('pointer_visual_cache_token', '')}`",
        f"- pointer inputs: `{list(anim.get('pointer_visual_reload_inputs') or [])}`",
        f"- token match: `{anim.get('bundle_vs_pointer_token_match')}`",
        f"- reload inputs match: `{anim.get('bundle_vs_pointer_reload_inputs_match')}`",
        f"- npz path match: `{anim.get('bundle_vs_pointer_npz_path_match')}`",
        f"- local_pointer_json: `{anim.get('local_pointer_json', '')}`",
        f"- global_pointer_json: `{anim.get('global_pointer_json', '')}`",
        f"- triage_diagnostics_json: `{anim.get('triage_diagnostics_json', '')}`",
        f"- pointer_sources_present: `{list(anim.get('pointer_sources_present') or [])}`",
        '',
        '## Tables',
        '',
    ]

    for name, info in sorted(tables.items()):
        lines += [
            f"### {name}",
            '',
            f"- rows: `{info.get('rows')}`",
            f"- cols: `{info.get('cols')}`",
            f"- time_col: `{info.get('time_col', '')}`",
            f"- t0: `{info.get('t0')}`",
            f"- t1: `{info.get('t1')}`",
            f"- dt_median: `{info.get('dt_median')}`",
            '',
        ]

    issues = list(anim.get('issues') or [])
    if issues:
        lines += ['## Issues', ''] + [f'- {str(msg)}' for msg in issues] + ['']
    return '\n'.join(lines).rstrip() + '\n'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True, help='Path to an NPZ bundle')
    ap.add_argument('--out_json', default='', help='Optional output JSON path')
    ap.add_argument('--out_md', default='', help='Optional output Markdown path')
    ap.add_argument('--print_summary', action='store_true', help='Print JSON summary to stdout')
    ns = ap.parse_args()

    rep = inspect_npz_bundle(ns.npz)
    if ns.out_json:
        p = Path(ns.out_json).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    if ns.out_md:
        p = Path(ns.out_md).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_inspect_npz_bundle_md(rep), encoding='utf-8')
    if ns.print_summary or (not ns.out_json and not ns.out_md):
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
