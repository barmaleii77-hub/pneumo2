from __future__ import annotations

"""Workspace directory contract helpers.

Goals:
- keep launcher/session bootstrap and diagnostics aligned on the same folder set;
- resolve the *effective* workspace honestly (session override first, repo-local fallback second);
- avoid silent drift between launcher creation, selfcheck expectations and send-bundle validation.
"""

import os
from pathlib import Path
from typing import Iterable, Sequence

REQUIRED_WORKSPACE_DIRS: tuple[str, ...] = (
    'exports',
    'uploads',
    'road_profiles',
    'maneuvers',
    'opt_runs',
    'ui_state',
)

OPTIONAL_WORKSPACE_DIRS: tuple[str, ...] = (
    '_pointers',
    'baselines',
    'opt_archive',
    'osc',
)

V32_WORKSPACE_IDS: tuple[str, ...] = (
    'WS-SHELL',
    'WS-PROJECT',
    'WS-INPUTS',
    'WS-RING',
    'WS-SUITE',
    'WS-BASELINE',
    'WS-OPTIMIZATION',
    'WS-ANALYSIS',
    'WS-ANIMATOR',
    'WS-DIAGNOSTICS',
    'WS-SETTINGS',
    'WS-TOOLS',
)

V32_HANDOFF_IDS: tuple[str, ...] = (
    'HO-001',
    'HO-002',
    'HO-003',
    'HO-004',
    'HO-005',
    'HO-006',
    'HO-007',
    'HO-008',
    'HO-009',
    'HO-010',
)

V32_WORKSPACE_REFERENCE_DIR = Path('docs') / 'context' / 'gui_spec_imports' / 'v32_connector_reconciled'


def repo_local_workspace_dir(repo_root: Path | str) -> Path:
    repo_root = Path(repo_root)
    return (repo_root / 'pneumo_solver_ui' / 'workspace').resolve()


def resolve_effective_workspace_dir(repo_root: Path | str, *, env: dict[str, str] | None = None) -> Path:
    env_map = env or os.environ
    raw = str(env_map.get('PNEUMO_WORKSPACE_DIR') or '').strip()
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw)
    return repo_local_workspace_dir(repo_root)


def required_workspace_dirs() -> tuple[str, ...]:
    return REQUIRED_WORKSPACE_DIRS


def optional_workspace_dirs() -> tuple[str, ...]:
    return OPTIONAL_WORKSPACE_DIRS


def v32_workspace_ids() -> tuple[str, ...]:
    return V32_WORKSPACE_IDS


def v32_handoff_ids() -> tuple[str, ...]:
    return V32_HANDOFF_IDS


def v32_workspace_reference_paths(repo_root: Path | str) -> dict[str, str]:
    root = Path(repo_root)
    base = root / V32_WORKSPACE_REFERENCE_DIR
    return {
        'readme': str(base / 'README.md'),
        'workstreams': str(base / 'PARALLEL_CHAT_WORKSTREAMS.md'),
        'release_gate_acceptance_map': str(base / 'RELEASE_GATE_ACCEPTANCE_MAP.md'),
    }


def iter_workspace_contract_dirs(*, include_optional: bool = True) -> Iterable[str]:
    yield from REQUIRED_WORKSPACE_DIRS
    if include_optional:
        yield from OPTIONAL_WORKSPACE_DIRS


def ensure_workspace_contract_dirs(workspace_dir: Path | str, *, include_optional: bool = True) -> list[Path]:
    ws = Path(workspace_dir)
    created: list[Path] = []
    ws.mkdir(parents=True, exist_ok=True)
    for name in iter_workspace_contract_dirs(include_optional=include_optional):
        p = ws / str(name)
        p.mkdir(parents=True, exist_ok=True)
        created.append(p)
    return created


def missing_workspace_contract_dirs(workspace_dir: Path | str, *, include_optional: bool = False) -> list[str]:
    ws = Path(workspace_dir)
    names: Sequence[str] = tuple(iter_workspace_contract_dirs(include_optional=include_optional))
    return [str(name) for name in names if not (ws / str(name)).exists()]
