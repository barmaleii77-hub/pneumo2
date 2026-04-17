from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class AnalysisContextSnapshot:
    path: Path
    exists: bool
    status: str
    ready_for_animator: bool
    selected_npz_path: Path | None = None
    selected_npz_exists: bool = False
    analysis_context_hash: str = ""
    animator_link_contract_hash: str = ""
    lineage: Mapping[str, Any] = field(default_factory=dict)
    blocking_states: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _resolve_path(raw: Any, *, base_dir: Path, repo_root: Path | None) -> Path | None:
    text = _text(raw)
    if not text:
        return None
    try:
        path = Path(text).expanduser()
        if not path.is_absolute():
            root = Path(repo_root).expanduser() if repo_root is not None else base_dir
            path = root / path
        return path.resolve()
    except Exception:
        return None


def _first_path_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def load_analysis_context(
    path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> AnalysisContextSnapshot:
    resolved = Path(path).expanduser()
    try:
        resolved = resolved.resolve()
    except Exception:
        pass
    root = Path(repo_root).expanduser().resolve() if repo_root is not None else None

    if not resolved.exists():
        return AnalysisContextSnapshot(
            path=resolved,
            exists=False,
            status="BLOCKED",
            ready_for_animator=False,
            blocking_states=("missing analysis_context.json",),
        )

    try:
        obj = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        return AnalysisContextSnapshot(
            path=resolved,
            exists=True,
            status="BLOCKED",
            ready_for_animator=False,
            blocking_states=(f"invalid analysis_context.json: {type(exc).__name__}",),
        )
    payload = _as_dict(obj)
    link = _as_dict(payload.get("animator_link_contract"))
    pointer = _as_dict(
        payload.get("selected_result_artifact_pointer")
        or link.get("selected_result_artifact_pointer")
    )
    selected_npz = _resolve_path(
        _first_path_text(
            payload.get("selected_npz_path"),
            payload.get("npz_path"),
            pointer.get("path"),
            link.get("selected_npz_path"),
            link.get("npz_path"),
        ),
        base_dir=resolved.parent,
        repo_root=root,
    )
    selected_npz_exists = bool(selected_npz is not None and selected_npz.exists())

    blocking: list[str] = [
        _text(item)
        for item in list(payload.get("blocking_states") or ()) + list(link.get("blocking_states") or ())
        if _text(item)
    ]
    warnings: list[str] = [
        _text(item)
        for item in list(payload.get("warnings") or ()) + list(link.get("warnings") or ())
        if _text(item)
    ]
    if selected_npz is None:
        blocking.append("missing selected_npz_path")
    elif not selected_npz_exists:
        warnings.append("selected_npz_path unavailable")

    ready_state = _text(payload.get("ready_state") or payload.get("analysis_context_ready_state") or link.get("ready_state"))
    if ready_state.lower() == "blocked":
        blocking.append("analysis context blocked")

    lineage = {
        "run_id": _text(payload.get("run_id") or link.get("run_id")),
        "objective_contract_hash": _text(
            payload.get("objective_contract_hash") or link.get("objective_contract_hash")
        ),
        "suite_snapshot_hash": _text(payload.get("suite_snapshot_hash") or link.get("suite_snapshot_hash")),
        "problem_hash": _text(payload.get("problem_hash") or link.get("problem_hash")),
    }
    ready = bool(selected_npz_exists and not blocking)
    status = "READY" if ready else ("DEGRADED" if selected_npz is not None and not blocking else "BLOCKED")
    return AnalysisContextSnapshot(
        path=resolved,
        exists=True,
        status=status,
        ready_for_animator=ready,
        selected_npz_path=selected_npz,
        selected_npz_exists=selected_npz_exists,
        analysis_context_hash=_text(payload.get("analysis_context_hash")),
        animator_link_contract_hash=_text(
            payload.get("animator_link_contract_hash") or link.get("animator_link_contract_hash")
        ),
        lineage=lineage,
        blocking_states=tuple(dict.fromkeys(blocking)),
        warnings=tuple(dict.fromkeys(warnings)),
        payload=payload,
    )


def format_analysis_context_banner(snapshot: AnalysisContextSnapshot | None) -> str:
    if snapshot is None:
        return ""
    lineage = dict(snapshot.lineage or {})
    run_id = _text(lineage.get("run_id")) or "-"
    link_hash = _text(snapshot.animator_link_contract_hash)
    hash_label = link_hash[:12] if link_hash else "-"
    if snapshot.ready_for_animator and snapshot.selected_npz_path is not None:
        return f"HO-008 {snapshot.status}: run={run_id} npz={snapshot.selected_npz_path.name} link={hash_label}"
    reason = ", ".join(snapshot.blocking_states or snapshot.warnings or ("analysis context unavailable",))
    return f"HO-008 {snapshot.status}: run={run_id} {reason}"


__all__ = [
    "AnalysisContextSnapshot",
    "format_analysis_context_banner",
    "load_analysis_context",
]
