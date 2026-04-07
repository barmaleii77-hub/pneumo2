from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

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


def _normalize_reload_inputs(raw: Any) -> List[str]:
    if raw in (None, ""):
        return []
    if isinstance(raw, (list, tuple, set)):
        out: List[str] = []
        for item in raw:
            s = str(item).strip()
            if s and s not in out:
                out.append(s)
        return out
    s = str(raw).strip()
    return [s] if s else []


def _short_token(token: str, n: int = 12) -> str:
    token = str(token or '').strip()
    if not token:
        return '—'
    return token[:n] + ('…' if len(token) > n else '')


def _norm_path(s: Any) -> str:
    txt = str(s or '').strip().replace('\\', '/').rstrip('/')
    return txt.lower()


def _same_path(a: Any, b: Any) -> bool | None:
    aa = _norm_path(a)
    bb = _norm_path(b)
    if not aa or not bb:
        return None
    return aa == bb


def _search_workspace_global_pointer(npz_path: Path) -> Path | None:
    # Prefer the nearest explicit workspace ancestor.
    for anc in [npz_path.parent, *npz_path.parents]:
        try:
            if anc.name == 'workspace':
                cand = anc / '_pointers' / 'anim_latest.json'
                if cand.exists():
                    return cand.resolve()
        except Exception:
            continue
    # Fallback: common extracted layouts may have workspace as a child.
    for anc in [npz_path.parent, *npz_path.parents]:
        try:
            cand = anc / 'workspace' / '_pointers' / 'anim_latest.json'
            if cand.exists():
                return cand.resolve()
        except Exception:
            continue
    return None


def _search_triage_sidecar(npz_path: Path) -> Path | None:
    for anc in [npz_path.parent, *npz_path.parents]:
        try:
            cand = anc / 'triage' / 'latest_anim_pointer_diagnostics.json'
            if cand.exists():
                return cand.resolve()
        except Exception:
            continue
    return None


def _extract_snapshot(
    obj: Mapping[str, Any],
    *,
    source: str,
    path: Path | None = None,
    global_pointer: Path | None = None,
) -> Dict[str, Any]:
    raw = dict(obj or {})
    is_flat = any(str(k).startswith('anim_latest_') for k in raw.keys())
    src = raw
    available = bool(raw.get('anim_latest_available') if is_flat else raw.get('available'))

    snap: Dict[str, Any] = {
        'source': str(source),
        'available': bool(
            available
            or raw.get('pointer_json')
            or raw.get('anim_latest_pointer_json')
            or raw.get('npz_path')
            or raw.get('anim_latest_npz_path')
            or raw.get('visual_cache_token')
            or raw.get('anim_latest_visual_cache_token')
        ),
        'pointer_json': str(raw.get('anim_latest_pointer_json') if is_flat else raw.get('pointer_json') or (str(path) if path else '')),
        'global_pointer_json': str(raw.get('anim_latest_global_pointer_json') if is_flat else raw.get('global_pointer_json') or (str(global_pointer) if global_pointer else '')),
        'npz_path': str(raw.get('anim_latest_npz_path') if is_flat else raw.get('npz_path') or ''),
        'visual_cache_token': str(raw.get('anim_latest_visual_cache_token') if is_flat else raw.get('visual_cache_token') or ''),
        'visual_reload_inputs': _normalize_reload_inputs(raw.get('anim_latest_visual_reload_inputs') if is_flat else raw.get('visual_reload_inputs')),
        'visual_cache_dependencies': dict(raw.get('anim_latest_visual_cache_dependencies') if is_flat else raw.get('visual_cache_dependencies') or {}),
        'updated_utc': str(raw.get('anim_latest_updated_utc') if is_flat else raw.get('updated_utc') or raw.get('updated_at') or ''),
        'meta': dict(raw.get('anim_latest_meta') if is_flat else raw.get('meta') or {}),
        'issues': [str(x) for x in list(raw.get('issues') or []) if str(x).strip()],
    }
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
    bundle_inputs = _normalize_reload_inputs(bundle_diag.get('inputs'))
    bundle_deps = dict(bundle_diag.get('visual_cache_dependencies') or {})

    local_pointer = p.with_name('anim_latest.json') if p.name.lower() == 'anim_latest.npz' else None
    if local_pointer is not None:
        try:
            local_pointer = local_pointer.resolve()
        except Exception:
            local_pointer = local_pointer
    global_pointer = _search_workspace_global_pointer(p)
    triage_sidecar = _search_triage_sidecar(p)

    sources: Dict[str, Dict[str, Any]] = {}
    for key, src_path in (
        ('local_pointer', local_pointer),
        ('global_pointer', global_pointer),
        ('triage_diagnostics', triage_sidecar),
    ):
        obj = _read_json(src_path)
        if isinstance(obj, dict):
            snap = _extract_snapshot(obj, source=key, path=src_path, global_pointer=global_pointer)
            if key == 'global_pointer':
                snap['global_pointer_json'] = str(src_path)
            if key == 'triage_diagnostics':
                snap['triage_json'] = str(src_path)
            sources[key] = snap

    pointer_snap: Dict[str, Any] = {}
    for key in ('local_pointer', 'global_pointer', 'triage_diagnostics'):
        snap = sources.get(key)
        if isinstance(snap, dict) and (snap.get('visual_cache_token') or snap.get('available')):
            pointer_snap = dict(snap)
            break

    token_map = {k: str(v.get('visual_cache_token') or '') for k, v in sources.items() if str(v.get('visual_cache_token') or '')}
    reload_map = {k: tuple(_normalize_reload_inputs(v.get('visual_reload_inputs'))) for k, v in sources.items() if _normalize_reload_inputs(v.get('visual_reload_inputs'))}
    npz_map = {k: str(v.get('npz_path') or '') for k, v in sources.items() if str(v.get('npz_path') or '')}

    issues: List[str] = []
    if not sources:
        issues.append('adjacent anim_latest pointer diagnostics not found; using current bundle token only')
    if len(set(token_map.values())) > 1:
        issues.append('pointer visual_cache_token mismatch between local/global/triage sources')
    if len(set(reload_map.values())) > 1:
        issues.append('pointer visual_reload_inputs mismatch between local/global/triage sources')
    if len(set(npz_map.values())) > 1:
        issues.append('pointer npz_path mismatch between local/global/triage sources')

    for snap in sources.values():
        for msg in list(snap.get('issues') or []):
            smsg = str(msg).strip()
            if smsg and smsg not in issues:
                issues.append(smsg)

    pointer_token = str(pointer_snap.get('visual_cache_token') or '')
    pointer_inputs = _normalize_reload_inputs(pointer_snap.get('visual_reload_inputs'))
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
        'pointer_sources_present': list(sources.keys()),
        'pointer_sources': {k: dict(v) for k, v in sources.items()},
        'bundle_vs_pointer_token_match': None if not pointer_token else (bundle_token == pointer_token),
        'bundle_vs_pointer_reload_inputs_match': None if not pointer_inputs else (tuple(bundle_inputs) == tuple(pointer_inputs)),
        'bundle_vs_pointer_npz_path_match': path_match,
        'pointer_sources_token_sync_ok': None if len(token_map) <= 1 else (len(set(token_map.values())) == 1),
        'pointer_sources_reload_inputs_sync_ok': None if len(reload_map) <= 1 else (len(set(reload_map.values())) == 1),
        'pointer_sources_npz_path_sync_ok': None if len(npz_map) <= 1 else (len(set(npz_map.values())) == 1),
        'issues': issues,
    }
    return out


def format_anim_diagnostics_lines(diag: Mapping[str, Any] | None, *, label: str = '') -> List[str]:
    d = dict(diag or {})
    lines: List[str] = []
    if label:
        lines.append(f'Run: {label}')
    lines.append(f"Current token: {_short_token(str(d.get('bundle_visual_cache_token') or ''))}")
    lines.append(f"Current inputs: {', '.join(_normalize_reload_inputs(d.get('bundle_visual_reload_inputs'))) or '—'}")
    lines.append(f"Pointer token: {_short_token(str(d.get('pointer_visual_cache_token') or ''))}")
    lines.append(f"Pointer inputs: {', '.join(_normalize_reload_inputs(d.get('pointer_visual_reload_inputs'))) or '—'}")
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
