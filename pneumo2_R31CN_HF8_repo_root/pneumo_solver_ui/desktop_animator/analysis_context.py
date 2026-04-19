from __future__ import annotations

"""HO-008 analysis context consumer for Desktop Animator.

This module is intentionally Qt-free.  It validates the frozen
analysis-to-animator handoff and resolves the explicit artifact pointer that
WS-ANIMATOR is allowed to load.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .operator_text import format_analysis_context_banner as _format_operator_analysis_context_banner
from .truth_contract import file_sha256, stable_contract_hash


ANALYSIS_TO_ANIMATOR_HANDOFF_ID = "HO-008"
ANALYSIS_CONTEXT_SCHEMA = "analysis_context.v1"
ANIMATOR_LINK_CONTRACT_SCHEMA = "analysis_to_animator_link_contract.v1"
ANALYSIS_CONTEXT_FILENAME = "analysis_context.json"
ANALYSIS_CONTEXT_ENV = "PNEUMO_ANALYSIS_CONTEXT_PATH"
ANALYSIS_WORKSPACE_ID = "WS-ANALYSIS"
ANIMATOR_WORKSPACE_ID = "WS-ANIMATOR"

REQUIRED_ANIMATOR_LINK_FIELDS: tuple[str, ...] = (
    "run_id",
    "run_contract_hash",
    "selected_test_id",
    "selected_segment_id",
    "selected_time_window",
    "selected_result_artifact_pointer",
    "objective_contract_hash",
    "suite_snapshot_hash",
)


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return not bool(value)
    if isinstance(value, (list, tuple, set)):
        return not bool(value)
    return False


def _dedupe(items: list[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _payload_hash(payload: Mapping[str, Any], *, hash_key: str) -> str:
    clean = dict(payload or {})
    clean.pop(hash_key, None)
    return stable_contract_hash(clean)


def _resolve_path(raw: Any, *, base_dir: Path | None = None) -> Path | None:
    text = _text(raw)
    if not text:
        return None
    try:
        path = Path(text).expanduser()
    except Exception:
        return None
    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir) / path
    try:
        return path.resolve(strict=False)
    except Exception:
        return path


def _read_json_dict(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def default_analysis_context_path(repo_root: Path | str | None = None) -> Path:
    raw_env = os.environ.get(ANALYSIS_CONTEXT_ENV, "").strip()
    if raw_env:
        return Path(raw_env).expanduser().resolve(strict=False)
    raw_workspace = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if raw_workspace:
        workspace = Path(raw_workspace).expanduser().resolve(strict=False)
    elif repo_root is not None:
        workspace = Path(repo_root).expanduser().resolve(strict=False) / "pneumo_solver_ui" / "workspace"
    else:
        workspace = Path.cwd().resolve(strict=False) / "pneumo_solver_ui" / "workspace"
    return (workspace / "handoffs" / ANALYSIS_WORKSPACE_ID / ANALYSIS_CONTEXT_FILENAME).resolve(strict=False)


def _resolve_selected_npz(
    pointer: Mapping[str, Any],
    *,
    context_path: Path | None,
) -> tuple[Path | None, Path | None, tuple[str, ...]]:
    pointer_path = _resolve_path(pointer.get("path"), base_dir=context_path.parent if context_path else None)
    warnings: list[str] = []
    if pointer_path is None:
        return None, None, ()
    if not pointer_path.exists() or not pointer_path.is_file():
        return pointer_path, None, ()
    if pointer_path.suffix.lower() == ".npz":
        return pointer_path, pointer_path, ()
    if pointer_path.suffix.lower() == ".json":
        pointer_payload = _read_json_dict(pointer_path)
        raw_npz = (
            pointer_payload.get("npz_path")
            or pointer_payload.get("path")
            or pointer_payload.get("file")
        )
        npz_path = _resolve_path(raw_npz, base_dir=pointer_path.parent)
        if npz_path is not None and npz_path.exists() and npz_path.is_file() and npz_path.suffix.lower() == ".npz":
            return pointer_path, npz_path, ()
        warnings.append("selected result pointer json does not resolve to an existing npz")
    return pointer_path, None, tuple(warnings)


@dataclass(frozen=True)
class AnimatorAnalysisContextSnapshot:
    path: Path | None
    exists: bool
    status: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    analysis_context_hash: str = ""
    computed_analysis_context_hash: str = ""
    animator_link_contract_hash: str = ""
    selected_run_contract_hash: str = ""
    selected_result_artifact_pointer: Mapping[str, Any] = field(default_factory=dict)
    selected_result_artifact_path: Path | None = None
    selected_npz_path: Path | None = None
    animator_link_contract: Mapping[str, Any] = field(default_factory=dict)
    lineage: Mapping[str, Any] = field(default_factory=dict)
    blocking_states: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    mismatch_summary: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ready_for_animator(self) -> bool:
        return self.status == "READY" and self.selected_npz_path is not None

    def to_payload(self) -> dict[str, Any]:
        return {
            "path": str(self.path or ""),
            "exists": bool(self.exists),
            "status": self.status,
            "analysis_context_hash": self.analysis_context_hash,
            "computed_analysis_context_hash": self.computed_analysis_context_hash,
            "animator_link_contract_hash": self.animator_link_contract_hash,
            "selected_run_contract_hash": self.selected_run_contract_hash,
            "selected_result_artifact_pointer": dict(self.selected_result_artifact_pointer or {}),
            "selected_result_artifact_path": str(self.selected_result_artifact_path or ""),
            "selected_npz_path": str(self.selected_npz_path or ""),
            "lineage": dict(self.lineage or {}),
            "blocking_states": list(self.blocking_states),
            "warnings": list(self.warnings),
            "mismatch_summary": dict(self.mismatch_summary or {}),
        }


def _lineage_from_payload(payload: Mapping[str, Any], link: Mapping[str, Any]) -> dict[str, Any]:
    selected_context = _as_mapping(payload.get("selected_run_context"))
    return {
        "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
        "analysis_context_path": _text(payload.get("analysis_context_path")),
        "analysis_context_hash": _text(payload.get("analysis_context_hash")),
        "animator_link_contract_hash": _text(
            payload.get("animator_link_contract_hash")
            or link.get("animator_link_contract_hash")
        ),
        "selected_run_contract_hash": _text(payload.get("selected_run_contract_hash")),
        "run_id": _text(link.get("run_id") or selected_context.get("run_id")),
        "run_contract_hash": _text(link.get("run_contract_hash") or selected_context.get("run_contract_hash")),
        "selected_test_id": _text(link.get("selected_test_id")),
        "selected_segment_id": _text(link.get("selected_segment_id")),
        "selected_time_window": link.get("selected_time_window") or {},
        "selected_best_candidate_ref": _text(link.get("selected_best_candidate_ref")),
        "objective_contract_hash": _text(
            link.get("objective_contract_hash")
            or selected_context.get("objective_contract_hash")
        ),
        "suite_snapshot_hash": _text(
            link.get("suite_snapshot_hash")
            or selected_context.get("suite_snapshot_hash")
        ),
        "problem_hash": _text(link.get("problem_hash") or selected_context.get("problem_hash")),
        "hard_gate_key": _text(link.get("hard_gate_key") or selected_context.get("hard_gate_key")),
        "hard_gate_tolerance": link.get("hard_gate_tolerance", selected_context.get("hard_gate_tolerance", "")),
        "active_baseline_hash": _text(
            link.get("active_baseline_hash")
            or selected_context.get("active_baseline_hash")
        ),
    }


def load_analysis_context(
    path: Path | str | None = None,
    *,
    repo_root: Path | str | None = None,
) -> AnimatorAnalysisContextSnapshot:
    context_path = Path(path).expanduser().resolve(strict=False) if path is not None else default_analysis_context_path(repo_root)
    if not context_path.exists() or not context_path.is_file():
        blocking = ("missing analysis context",)
        return AnimatorAnalysisContextSnapshot(
            path=context_path,
            exists=False,
            status="MISSING",
            blocking_states=blocking,
            mismatch_summary={
                "scope": "analysis_to_animator_context",
                "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
                "status": "MISSING",
                "blocking_states": list(blocking),
            },
        )

    try:
        payload_obj = json.loads(context_path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        blocking = (f"invalid analysis context: {exc}",)
        return AnimatorAnalysisContextSnapshot(
            path=context_path,
            exists=True,
            status="INVALID",
            blocking_states=blocking,
            mismatch_summary={
                "scope": "analysis_to_animator_context",
                "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
                "status": "INVALID",
                "blocking_states": list(blocking),
            },
        )
    if not isinstance(payload_obj, Mapping):
        blocking = ("analysis context root is not an object",)
        return AnimatorAnalysisContextSnapshot(
            path=context_path,
            exists=True,
            status="INVALID",
            blocking_states=blocking,
            mismatch_summary={
                "scope": "analysis_to_animator_context",
                "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
                "status": "INVALID",
                "blocking_states": list(blocking),
            },
        )

    payload = dict(payload_obj)
    link = _as_mapping(payload.get("animator_link_contract"))
    pointer = _as_mapping(payload.get("selected_result_artifact_pointer") or link.get("selected_result_artifact_pointer"))
    blocking: list[str] = []
    warnings: list[str] = []

    if _text(payload.get("schema")) != ANALYSIS_CONTEXT_SCHEMA:
        blocking.append("analysis context schema mismatch")
    if _text(payload.get("handoff_id")) != ANALYSIS_TO_ANIMATOR_HANDOFF_ID:
        blocking.append("analysis context handoff_id mismatch")
    if _text(payload.get("producer_workspace")) not in {"", ANALYSIS_WORKSPACE_ID}:
        blocking.append("analysis context producer mismatch")
    if _text(payload.get("consumer_workspace")) not in {"", ANIMATOR_WORKSPACE_ID}:
        blocking.append("analysis context consumer mismatch")
    if not link:
        blocking.append("missing animator link contract")
    else:
        if _text(link.get("schema")) != ANIMATOR_LINK_CONTRACT_SCHEMA:
            blocking.append("animator link contract schema mismatch")
        if _text(link.get("handoff_id")) != ANALYSIS_TO_ANIMATOR_HANDOFF_ID:
            blocking.append("animator link contract handoff_id mismatch")
        if _text(link.get("producer_workspace")) not in {"", ANALYSIS_WORKSPACE_ID}:
            blocking.append("animator link producer mismatch")
        if _text(link.get("consumer_workspace")) not in {"", ANIMATOR_WORKSPACE_ID}:
            blocking.append("animator link consumer mismatch")
        for field_name in REQUIRED_ANIMATOR_LINK_FIELDS:
            if _is_missing(link.get(field_name)):
                blocking.append(f"missing {field_name}")
        if _is_missing(link.get("selected_best_candidate_ref")):
            warnings.append("selected_best_candidate_ref missing")

    stored_context_hash = _text(payload.get("analysis_context_hash"))
    computed_context_hash = _payload_hash(payload, hash_key="analysis_context_hash")
    if stored_context_hash and stored_context_hash != computed_context_hash:
        blocking.append("analysis context hash mismatch")

    stored_link_hash = _text(link.get("animator_link_contract_hash"))
    top_link_hash = _text(payload.get("animator_link_contract_hash"))
    computed_link_hash = _payload_hash(link, hash_key="animator_link_contract_hash") if link else ""
    if top_link_hash and stored_link_hash and top_link_hash != stored_link_hash:
        blocking.append("animator link hash mismatch")
    if stored_link_hash and computed_link_hash and stored_link_hash != computed_link_hash:
        blocking.append("animator link contract hash mismatch")

    if not pointer:
        blocking.append("missing selected result artifact pointer")
    artifact_path, selected_npz_path, pointer_warnings = _resolve_selected_npz(pointer, context_path=context_path)
    warnings.extend(pointer_warnings)
    if artifact_path is None:
        blocking.append("missing selected result artifact pointer path")
    elif not artifact_path.exists() or not artifact_path.is_file():
        blocking.append("selected result artifact pointer missing")
    elif selected_npz_path is None:
        blocking.append("selected result artifact is not animator-loadable")
    if artifact_path is not None and artifact_path.exists() and artifact_path.is_file():
        expected_sha = _text(pointer.get("sha256"))
        if expected_sha:
            actual_sha = file_sha256(artifact_path)
            if actual_sha and actual_sha != expected_sha:
                blocking.append("selected result artifact pointer sha256 mismatch")

    selected_context = _as_mapping(payload.get("selected_run_context"))
    selected_run_hash = _text(payload.get("selected_run_contract_hash"))
    link_run_hash = _text(link.get("run_contract_hash"))
    if selected_run_hash and link_run_hash and selected_run_hash != link_run_hash:
        blocking.append("selected run contract hash mismatch")
    for field_name in ("run_id", "objective_contract_hash", "suite_snapshot_hash", "problem_hash"):
        left = _text(selected_context.get(field_name))
        right = _text(link.get(field_name))
        if left and right and left != right:
            blocking.append(f"{field_name} mismatch")

    if bool(payload.get("diagnostics_bundle_finalized")):
        warnings.append("analysis context unexpectedly marks diagnostics bundle finalized")

    blocking_tuple = _dedupe(blocking)
    warnings_tuple = _dedupe(warnings)
    status = "BLOCKED" if blocking_tuple else ("DEGRADED" if warnings_tuple else "READY")
    lineage = _lineage_from_payload(payload, link)
    mismatch_summary = {
        "scope": "analysis_to_animator_context",
        "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
        "status": status,
        "analysis_context_path": str(context_path),
        "analysis_context_hash": stored_context_hash,
        "animator_link_contract_hash": top_link_hash or stored_link_hash,
        "selected_npz_path": str(selected_npz_path or ""),
        "blocking_states": list(blocking_tuple),
        "warnings": list(warnings_tuple),
    }

    return AnimatorAnalysisContextSnapshot(
        path=context_path,
        exists=True,
        status=status,
        payload=payload,
        analysis_context_hash=stored_context_hash or computed_context_hash,
        computed_analysis_context_hash=computed_context_hash,
        animator_link_contract_hash=top_link_hash or stored_link_hash,
        selected_run_contract_hash=selected_run_hash,
        selected_result_artifact_pointer=pointer,
        selected_result_artifact_path=artifact_path,
        selected_npz_path=selected_npz_path,
        animator_link_contract=link,
        lineage=lineage,
        blocking_states=blocking_tuple,
        warnings=warnings_tuple,
        mismatch_summary=mismatch_summary,
    )


def build_analysis_context_meta_refs(snapshot: AnimatorAnalysisContextSnapshot | None) -> dict[str, Any]:
    if snapshot is None or not snapshot.exists:
        return {}
    lineage = dict(snapshot.lineage or {})
    payload = dict(snapshot.payload or {})
    return {
        "analysis_context_path": str(snapshot.path or ""),
        "analysis_context_hash": snapshot.analysis_context_hash,
        "analysis_context_status": snapshot.status,
        "animator_link_contract_hash": snapshot.animator_link_contract_hash,
        "animator_link_contract_path": payload.get("animator_link_contract_path", ""),
        "selected_run_contract_hash": snapshot.selected_run_contract_hash,
        "selected_result_artifact_pointer": dict(snapshot.selected_result_artifact_pointer or {}),
        "selected_npz_path": str(snapshot.selected_npz_path or ""),
        "run_id": lineage.get("run_id", ""),
        "run_contract_hash": lineage.get("run_contract_hash", ""),
        "objective_contract_hash": lineage.get("objective_contract_hash", ""),
        "suite_snapshot_hash": lineage.get("suite_snapshot_hash", ""),
        "problem_hash": lineage.get("problem_hash", ""),
        "hard_gate_key": lineage.get("hard_gate_key", ""),
        "hard_gate_tolerance": lineage.get("hard_gate_tolerance", ""),
        "active_baseline_hash": lineage.get("active_baseline_hash", ""),
        "selected_test_id": lineage.get("selected_test_id", ""),
        "selected_segment_id": lineage.get("selected_segment_id", ""),
        "selected_time_window": lineage.get("selected_time_window", {}),
    }


def _short_hash(value: Any, *, length: int = 10) -> str:
    text = _text(value)
    return text[: max(1, int(length))] if text else "-"


def format_analysis_context_banner(snapshot: AnimatorAnalysisContextSnapshot | None) -> str:
    if snapshot is None:
        return "Связь с анализом: не загружена"
    return _format_operator_analysis_context_banner(
        exists=bool(snapshot.exists),
        status=snapshot.status,
        lineage=dict(snapshot.lineage or {}),
        analysis_context_hash=snapshot.analysis_context_hash,
        blocking_states=tuple(snapshot.blocking_states or ()),
        warnings=tuple(snapshot.warnings or ()),
    )


__all__ = [
    "ANALYSIS_CONTEXT_ENV",
    "ANALYSIS_CONTEXT_FILENAME",
    "ANALYSIS_CONTEXT_SCHEMA",
    "ANALYSIS_TO_ANIMATOR_HANDOFF_ID",
    "ANALYSIS_WORKSPACE_ID",
    "ANIMATOR_LINK_CONTRACT_SCHEMA",
    "ANIMATOR_WORKSPACE_ID",
    "AnimatorAnalysisContextSnapshot",
    "REQUIRED_ANIMATOR_LINK_FIELDS",
    "build_analysis_context_meta_refs",
    "default_analysis_context_path",
    "format_analysis_context_banner",
    "load_analysis_context",
]
