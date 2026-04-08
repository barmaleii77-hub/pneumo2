from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from pneumo_solver_ui.desktop_animator.pointer_paths import nearest_anim_pointer_candidates
from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_DIAG_JSON,
    choose_anim_snapshot,
    extract_anim_snapshot,
    normalize_reload_inputs,
)
from pneumo_solver_ui.visual_contract import build_visual_reload_diagnostics

LogFn = Callable[[str], None]


def _emit(msg: str, log: LogFn | None) -> None:
    if log is None:
        return
    try:
        log(msg)
    except Exception:
        pass


def _read_json(path: Path | None) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    try:
        if path.exists() and path.is_file():
            obj = json.loads(path.read_text(encoding='utf-8'))
            return dict(obj) if isinstance(obj, dict) else None
    except Exception:
        return None
    return None


def _short_token(token: str, n: int = 12) -> str:
    token = str(token or '').strip()
    if not token:
        return '—'
    return token[:n] + ('…' if len(token) > n else '')


def _normalize_pointer_inputs(raw: Any) -> List[str]:
    return list(dict.fromkeys(normalize_reload_inputs(raw)))


def _norm_path(s: Any) -> str:
    txt = str(s or '').strip().replace('\\', '/').rstrip('/')
    return txt.lower()


def _same_path(a: Any, b: Any) -> bool | None:
    aa = _norm_path(a)
    bb = _norm_path(b)
    if not aa or not bb:
        return None
    return aa == bb


def _search_triage_sidecar(npz_path: Path) -> Path | None:
    sidecar_parts = Path(ANIM_DIAG_JSON).parts
    for anc in [npz_path.parent, *npz_path.parents]:
        try:
            cand = anc.joinpath(*sidecar_parts)
            if cand.exists():
                return cand.resolve()
        except Exception:
            continue
    return None


def _extract_pointer_snapshot(
    obj: Mapping[str, Any],
    *,
    source: str,
    path: Path | None = None,
    global_pointer: Path | None = None,
) -> Dict[str, Any]:
    snap = dict(extract_anim_snapshot(dict(obj or {}), source=source) or {})
    snap['visual_reload_inputs'] = _normalize_pointer_inputs(snap.get('visual_reload_inputs'))
    if path is not None and not str(snap.get('pointer_json') or '').strip():
        snap['pointer_json'] = str(path)
    if global_pointer is not None and not str(snap.get('global_pointer_json') or '').strip():
        snap['global_pointer_json'] = str(global_pointer)
    snap['issues'] = [str(x) for x in list(snap.get('issues') or []) if str(x).strip()]
    return snap


def collect_npz_anim_diagnostics(
    npz_path: str | Path,
    meta: Mapping[str, Any] | None = None,
    *,
    context: str = 'npz bundle',
    log: LogFn | None = None,
) -> Dict[str, Any]:
    p = Path(str(npz_path)).expanduser().resolve()

    bundle_diag = build_visual_reload_diagnostics(
        p,
        meta=meta,
        context=f'{context} current bundle',
        log=log,
    )
    bundle_token = str(bundle_diag.get('visual_cache_token') or '')
    bundle_inputs = _normalize_pointer_inputs(bundle_diag.get('inputs'))
    bundle_deps = dict(bundle_diag.get('visual_cache_dependencies') or {})

    local_pointer: Path | None = None
    global_pointer: Path | None = None
    for cand in nearest_anim_pointer_candidates(p):
        try:
            cand = cand.resolve()
        except Exception:
            cand = cand
        if cand.parent.name == 'exports' and local_pointer is None:
            local_pointer = cand
        elif cand.parent.name == '_pointers' and global_pointer is None:
            global_pointer = cand
    triage_sidecar = _search_triage_sidecar(p)

    sources: Dict[str, Dict[str, Any]] = {}
    for key, src_path in (
        ('local_pointer', local_pointer),
        ('global_pointer', global_pointer),
        ('triage_diagnostics', triage_sidecar),
    ):
        obj = _read_json(src_path)
        if isinstance(obj, dict):
            snap = _extract_pointer_snapshot(obj, source=key, path=src_path, global_pointer=global_pointer)
            if key == 'global_pointer':
                snap['global_pointer_json'] = str(src_path)
            if key == 'triage_diagnostics':
                snap['triage_json'] = str(src_path)
            sources[key] = snap

    pointer_snap = choose_anim_snapshot(
        sources,
        preferred_order=('local_pointer', 'global_pointer', 'triage_diagnostics'),
    )

    issues: List[str] = []
    if not sources:
        issues.append('adjacent anim_latest pointer diagnostics not found; using current bundle token only')
    if pointer_snap.get('pointer_sync_ok') is False:
        issues.append('pointer visual_cache_token mismatch between local/global/triage sources')
    if pointer_snap.get('reload_inputs_sync_ok') is False:
        issues.append('pointer visual_reload_inputs mismatch between local/global/triage sources')
    if pointer_snap.get('npz_path_sync_ok') is False:
        issues.append('pointer npz_path mismatch between local/global/triage sources')

    for snap in sources.values():
        for msg in list(snap.get('issues') or []):
            smsg = str(msg).strip()
            if smsg and smsg not in issues:
                issues.append(smsg)

    pointer_token = str(pointer_snap.get('visual_cache_token') or '')
    pointer_inputs = _normalize_pointer_inputs(pointer_snap.get('visual_reload_inputs'))
    pointer_npz = str(pointer_snap.get('npz_path') or '')

    if pointer_token and bundle_token != pointer_token:
        issues.append('current bundle visual_cache_token differs from adjacent pointer snapshot')
    if pointer_inputs and tuple(bundle_inputs) != tuple(pointer_inputs):
        issues.append('current bundle visual_reload_inputs differ from adjacent pointer snapshot')
    path_match = _same_path(p, pointer_npz)
    if path_match is False:
        issues.append('current npz path differs from pointer npz_path')

    out: Dict[str, Any] = {
        'available': True,
        'npz_path': str(p),
        'bundle_visual_cache_token': bundle_token,
        'bundle_visual_reload_inputs': bundle_inputs,
        'bundle_visual_cache_dependencies': bundle_deps,
        'pointer_visual_cache_token': pointer_token,
        'pointer_visual_reload_inputs': pointer_inputs,
        'pointer_visual_cache_dependencies': dict(pointer_snap.get('visual_cache_dependencies') or {}),
        'local_pointer_json': str(local_pointer) if local_pointer is not None and local_pointer.exists() else '',
        'global_pointer_json': str(global_pointer) if global_pointer is not None and global_pointer.exists() else '',
        'triage_diagnostics_json': str(triage_sidecar) if triage_sidecar is not None and triage_sidecar.exists() else '',
        'pointer_npz_path': pointer_npz,
        'pointer_updated_utc': str(pointer_snap.get('updated_utc') or ''),
        'pointer_sources_present': list(pointer_snap.get('sources_present') or sources.keys()),
        'pointer_sources': {k: dict(v) for k, v in sources.items()},
        'bundle_vs_pointer_token_match': None if not pointer_token else (bundle_token == pointer_token),
        'bundle_vs_pointer_reload_inputs_match': None if not pointer_inputs else (tuple(bundle_inputs) == tuple(pointer_inputs)),
        'bundle_vs_pointer_npz_path_match': path_match,
        'pointer_sources_token_sync_ok': pointer_snap.get('pointer_sync_ok'),
        'pointer_sources_reload_inputs_sync_ok': pointer_snap.get('reload_inputs_sync_ok'),
        'pointer_sources_npz_path_sync_ok': pointer_snap.get('npz_path_sync_ok'),
        'issues': issues,
    }
    return out


def format_anim_diagnostics_lines(diag: Mapping[str, Any] | None, *, label: str = '') -> List[str]:
    d = dict(diag or {})
    lines: List[str] = []
    if label:
        lines.append(f'Run: {label}')
    lines.append(f"Current token: {_short_token(str(d.get('bundle_visual_cache_token') or ''))}")
    lines.append(f"Current inputs: {', '.join(_normalize_pointer_inputs(d.get('bundle_visual_reload_inputs'))) or '—'}")
    lines.append(f"Pointer token: {_short_token(str(d.get('pointer_visual_cache_token') or ''))}")
    lines.append(f"Pointer inputs: {', '.join(_normalize_pointer_inputs(d.get('pointer_visual_reload_inputs'))) or '—'}")
    lines.append(f"Token match: {d.get('bundle_vs_pointer_token_match')}")
    lines.append(f"Inputs match: {d.get('bundle_vs_pointer_reload_inputs_match')}")
    lines.append(f"Pointer path match: {d.get('bundle_vs_pointer_npz_path_match')}")
    lines.append(f"Sources: {', '.join(list(d.get('pointer_sources_present') or [])) or '—'}")
    lines.append(f"NPZ: {str(d.get('npz_path') or '')}")
    local_ptr = str(d.get('local_pointer_json') or '')
    if local_ptr:
        lines.append(f"Local pointer: {local_ptr}")
    global_ptr = str(d.get('global_pointer_json') or '')
    if global_ptr:
        lines.append(f"Global pointer: {global_ptr}")
    triage = str(d.get('triage_diagnostics_json') or '')
    if triage:
        lines.append(f"Triage diagnostics: {triage}")
    for msg in list(d.get('issues') or [])[:5]:
        lines.append(f"WARN: {msg}")
    return lines


__all__ = [
    'collect_npz_anim_diagnostics',
    'format_anim_diagnostics_lines',
]
