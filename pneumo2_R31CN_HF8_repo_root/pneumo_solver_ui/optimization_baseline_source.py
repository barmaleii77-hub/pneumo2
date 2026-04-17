from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional

from pneumo_solver_ui.name_sanitize import sanitize_id
from pneumo_solver_ui.desktop_suite_snapshot import (
    VALIDATED_SUITE_SNAPSHOT_FILENAME,
    VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION,
    WS_SUITE_HANDOFF_ID,
)

from pneumo_solver_ui.workspace_contract import resolve_effective_workspace_dir

BASELINE_SOURCE_KIND_SCOPED = "scoped"
BASELINE_SOURCE_KIND_GLOBAL = "global"
BASELINE_SOURCE_KIND_NONE = "none"

ACTIVE_BASELINE_CONTRACT_SCHEMA_VERSION = "active_baseline_contract_v1"
ACTIVE_BASELINE_CONTRACT_FILENAME = "active_baseline_contract.json"
BASELINE_HISTORY_FILENAME = "baseline_history.jsonl"
BASELINE_HISTORY_ITEM_SCHEMA_VERSION = "baseline_history_item_v1"
WS_BASELINE_HANDOFF_ID = "HO-006"
WS_BASELINE_SOURCE_WORKSPACE = "WS-BASELINE"
WS_BASELINE_TARGET_WORKSPACE = "WS-OPTIMIZATION"
BASELINE_HISTORICAL_BANNER_ID = "BANNER-HIST-001"
BASELINE_MISMATCH_BANNER_ID = "BANNER-HIST-002"
BASELINE_MISSING_BANNER_ID = "BANNER-HIST-003"
BASELINE_STALE_BANNER_ID = "BANNER-BASELINE-STALE-001"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _file_sha256(path: Path | str | None) -> str:
    if path is None:
        return ""
    try:
        candidate = Path(path)
        if not candidate.exists() or not candidate.is_file():
            return ""
        digest = hashlib.sha256()
        with candidate.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return ""



def workspace_baseline_dir(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir).resolve() / "baselines"
    root = Path(repo_root) if repo_root is not None else _repo_root()
    effective_workspace = resolve_effective_workspace_dir(
        root,
        env=dict(env) if env is not None else None,
    )
    return effective_workspace / "baselines"


def baseline_problem_scope_dir(baseline_dir: Path | str, problem_hash: str | None) -> Path:
    token = sanitize_id(str(problem_hash or "").strip()) or "unknown_problem"
    return Path(baseline_dir) / "by_problem" / f"p_{token}"


def baseline_source_label(source_kind: str) -> str:
    kind = str(source_kind or "").strip().lower()
    if kind == BASELINE_SOURCE_KIND_SCOPED:
        return "scoped baseline"
    if kind == BASELINE_SOURCE_KIND_GLOBAL:
        return "global baseline fallback"
    return "default_base.json only"


def baseline_source_short_label(source_kind: str) -> str:
    kind = str(source_kind or "").strip().lower()
    if kind == BASELINE_SOURCE_KIND_SCOPED:
        return "scoped"
    if kind == BASELINE_SOURCE_KIND_GLOBAL:
        return "global"
    return "default-only"


def resolve_workspace_baseline_source(
    problem_hash: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    env_map = env if env is not None else os.environ
    current_problem_hash = str(
        problem_hash
        if problem_hash is not None
        else env_map.get("PNEUMO_OPT_PROBLEM_HASH", "")
    ).strip()
    current_baseline_dir = (
        Path(baseline_dir).resolve()
        if baseline_dir is not None
        else workspace_baseline_dir(
            env=env_map,
            workspace_dir=workspace_dir,
            repo_root=repo_root,
        )
    )
    scope_dir = baseline_problem_scope_dir(current_baseline_dir, current_problem_hash)
    scoped_path = scope_dir / "baseline_best.json"
    global_path = current_baseline_dir / "baseline_best.json"

    selected_path: Optional[Path] = None
    source_kind = BASELINE_SOURCE_KIND_NONE
    if current_problem_hash and scoped_path.exists():
        source_kind = BASELINE_SOURCE_KIND_SCOPED
        selected_path = scoped_path
    elif global_path.exists():
        source_kind = BASELINE_SOURCE_KIND_GLOBAL
        selected_path = global_path

    return {
        "version": "baseline_source_v1",
        "problem_hash": current_problem_hash,
        "source_kind": source_kind,
        "source_label": baseline_source_label(source_kind),
        "baseline_path": str(selected_path) if selected_path is not None else "",
        "baseline_dir": str(current_baseline_dir),
        "workspace_dir": str(current_baseline_dir.parent),
        "scope_dir": str(scope_dir),
        "scope_token": scope_dir.name.removeprefix("p_"),
    }


def resolve_workspace_baseline_override_path(
    problem_hash: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Optional[Path]:
    payload = resolve_workspace_baseline_source(
        problem_hash=problem_hash,
        env=env,
        workspace_dir=workspace_dir,
        baseline_dir=baseline_dir,
        repo_root=repo_root,
    )
    raw_path = str(payload.get("baseline_path") or "").strip()
    if not raw_path:
        return None
    return Path(raw_path)


def baseline_suite_handoff_snapshot_path(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    root = Path(repo_root) if repo_root is not None else _repo_root()
    effective_workspace = (
        Path(workspace_dir).resolve()
        if workspace_dir is not None
        else resolve_effective_workspace_dir(
            root,
            env=dict(env) if env is not None else None,
        )
    )
    return (effective_workspace / "handoffs" / "WS-SUITE" / VALIDATED_SUITE_SNAPSHOT_FILENAME).resolve()


def resolve_baseline_suite_handoff(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
) -> dict[str, Any]:
    """Read the WS-SUITE -> WS-BASELINE HO-005 snapshot without rebinding it."""

    path = baseline_suite_handoff_snapshot_path(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
    )
    base_payload: dict[str, Any] = {
        "version": "baseline_suite_handoff_v1",
        "handoff_id": WS_SUITE_HANDOFF_ID,
        "source_workspace": "WS-SUITE",
        "target_workspace": "WS-BASELINE",
        "snapshot_path": str(path),
        "suite_snapshot_hash": "",
        "state": "missing",
        "baseline_can_consume": False,
        "banner": (
            "HO-005 validated_suite_snapshot не найден. "
            "Baseline должен получить frozen suite snapshot из WS-SUITE."
        ),
    }
    if not path.exists():
        return base_payload

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            **base_payload,
            "state": "invalid",
            "banner": f"HO-005 validated_suite_snapshot не читается: {exc}",
        }
    if not isinstance(raw, dict):
        return {
            **base_payload,
            "state": "invalid",
            "banner": "HO-005 validated_suite_snapshot должен быть JSON object.",
        }
    if str(raw.get("schema_version") or "") != VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION:
        return {
            **base_payload,
            "state": "invalid",
            "banner": "HO-005 validated_suite_snapshot имеет неподдерживаемую schema_version.",
        }

    suite_hash = str(raw.get("suite_snapshot_hash") or "").strip()
    validated = bool(raw.get("validated", False))
    if current_suite_snapshot_hash and suite_hash != str(current_suite_snapshot_hash):
        ctx = _suite_context_fields(raw)
        return {
            **base_payload,
            "suite_snapshot_hash": suite_hash,
            "inputs_snapshot_hash": ctx["inputs_snapshot_hash"],
            "ring_source_hash": ctx["ring_source_hash"],
            "created_at_utc": str(raw.get("created_at_utc") or ""),
            "state": "stale",
            "banner": "HO-005 suite_snapshot_hash устарел относительно текущего WS-SUITE context.",
        }
    ctx = _suite_context_fields(raw)
    return {
        **base_payload,
        "suite_snapshot_hash": suite_hash,
        "inputs_snapshot_hash": ctx["inputs_snapshot_hash"],
        "ring_source_hash": ctx["ring_source_hash"],
        "created_at_utc": str(raw.get("created_at_utc") or ""),
        "state": "current" if validated else "invalid",
        "baseline_can_consume": bool(validated),
        "banner": (
            "HO-005 validated_suite_snapshot актуален для baseline."
            if validated
            else "HO-005 snapshot найден, но validation не пройдена."
        ),
    }




def _suite_context_fields(suite_snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot = dict(suite_snapshot or {})
    upstream_refs = dict(snapshot.get("upstream_refs") or {})
    inputs = dict(upstream_refs.get("inputs") or {})
    ring = dict(upstream_refs.get("ring") or {})
    return {
        "suite_snapshot_hash": str(snapshot.get("suite_snapshot_hash") or "").strip(),
        "inputs_snapshot_hash": str(inputs.get("snapshot_hash") or "").strip(),
        "ring_source_hash": str(ring.get("source_hash") or "").strip(),
        "suite_validated": bool(snapshot.get("validated", False)),
        "suite_context_label": str(snapshot.get("context_label") or "").strip(),
        "suite_snapshot_ref": str(snapshot.get("suite_source_path") or "").strip(),
    }



def _active_baseline_contract_core(contract: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(contract or {})
    return {
        "schema_version": str(payload.get("schema_version") or ""),
        "source_workspace": str(payload.get("source_workspace") or ""),
        "target_workspace": str(payload.get("target_workspace") or ""),
        "handoff_id": str(payload.get("handoff_id") or ""),
        "frozen": bool(payload.get("frozen", False)),
        "baseline": dict(payload.get("baseline") or {}),
        "suite_snapshot_hash": str(payload.get("suite_snapshot_hash") or "").strip(),
        "inputs_snapshot_hash": str(payload.get("inputs_snapshot_hash") or "").strip(),
        "ring_source_hash": str(payload.get("ring_source_hash") or "").strip(),
        "suite_validated": bool(payload.get("suite_validated", False)),
        "suite_context_label": str(payload.get("suite_context_label") or "").strip(),
        "suite_snapshot_ref": str(payload.get("suite_snapshot_ref") or "").strip(),
        "policy": dict(payload.get("policy") or {}),
        "note": str(payload.get("note") or "").strip(),
    }



def describe_active_baseline_state(
    contract: Mapping[str, Any] | None,
    *,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        return {
            "state": "missing",
            "is_stale": True,
            "optimizer_can_consume": False,
            "banner_id": BASELINE_MISSING_BANNER_ID,
            "stale_reasons": ["missing_active_baseline_contract"],
            "banner": (
                "HO-006 active_baseline_contract не найден. "
                "Оптимизация не должна молча подставлять baseline_best.json."
            ),
        }

    payload = dict(contract)
    if str(payload.get("schema_version") or "") != ACTIVE_BASELINE_CONTRACT_SCHEMA_VERSION:
        return {
            "state": "invalid",
            "is_stale": True,
            "optimizer_can_consume": False,
            "banner_id": BASELINE_MISSING_BANNER_ID,
            "stale_reasons": ["unsupported_active_baseline_schema"],
            "banner": "active_baseline_contract имеет неподдерживаемую схему; silent rebinding запрещён.",
        }
    if str(payload.get("handoff_id") or "") != WS_BASELINE_HANDOFF_ID:
        return {
            "state": "invalid",
            "is_stale": True,
            "optimizer_can_consume": False,
            "banner_id": BASELINE_MISSING_BANNER_ID,
            "stale_reasons": ["wrong_baseline_handoff_id"],
            "banner": "active_baseline_contract должен быть HO-006 для передачи WS-BASELINE -> WS-OPTIMIZATION.",
        }
    expected_hash = _sha256_payload(_active_baseline_contract_core(payload))
    stored_hash = str(payload.get("active_baseline_hash") or "").strip()
    if stored_hash != expected_hash:
        return {
            "state": "invalid",
            "is_stale": True,
            "optimizer_can_consume": False,
            "banner_id": BASELINE_MISSING_BANNER_ID,
            "stale_reasons": ["active_baseline_hash_mismatch"],
            "banner": "active_baseline_hash не совпадает с frozen payload; используйте review/adopt/restore.",
        }
    if not bool(payload.get("suite_validated", False)):
        return {
            "state": "invalid",
            "is_stale": True,
            "optimizer_can_consume": False,
            "banner_id": BASELINE_MISSING_BANNER_ID,
            "active_baseline_hash": stored_hash,
            "suite_snapshot_hash": str(payload.get("suite_snapshot_hash") or ""),
            "stale_reasons": ["suite_snapshot_not_validated"],
            "banner": (
                "active_baseline_contract ссылается на невалидированный suite snapshot; "
                "сначала нужен HO-005 review/adopt."
            ),
        }

    stale_reasons: list[str] = []
    if current_suite_snapshot_hash and str(payload.get("suite_snapshot_hash") or "") != str(current_suite_snapshot_hash):
        stale_reasons.append("suite_snapshot_hash_changed")
    if current_inputs_snapshot_hash and str(payload.get("inputs_snapshot_hash") or "") != str(current_inputs_snapshot_hash):
        stale_reasons.append("inputs_snapshot_hash_changed")
    if current_ring_source_hash and str(payload.get("ring_source_hash") or "") != str(current_ring_source_hash):
        stale_reasons.append("ring_source_hash_changed")

    if stale_reasons:
        return {
            "state": "stale",
            "is_stale": True,
            "optimizer_can_consume": False,
            "banner_id": BASELINE_STALE_BANNER_ID,
            "active_baseline_hash": stored_hash,
            "suite_snapshot_hash": str(payload.get("suite_snapshot_hash") or ""),
            "stale_reasons": stale_reasons,
            "banner": (
                "active_baseline_contract устарел для текущего контекста: "
                + ", ".join(stale_reasons)
                + ". Review/adopt/restore требуется явно; silent rebinding запрещён."
            ),
        }

    return {
        "state": "current",
        "is_stale": False,
        "optimizer_can_consume": True,
        "banner_id": "",
        "active_baseline_hash": stored_hash,
        "suite_snapshot_hash": str(payload.get("suite_snapshot_hash") or ""),
        "inputs_snapshot_hash": str(payload.get("inputs_snapshot_hash") or ""),
        "ring_source_hash": str(payload.get("ring_source_hash") or ""),
        "stale_reasons": [],
        "banner": f"HO-006 active baseline актуален: {stored_hash[:12]}.",
    }



def _contract_from_history_or_contract(value: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(value or {})
    nested = payload.get("contract")
    if isinstance(nested, Mapping):
        return dict(nested)
    return payload


def _baseline_compare_value(payload: Mapping[str, Any], field: str) -> str:
    data = dict(payload or {})
    if field == "policy_mode":
        if "policy_mode" in data:
            return str(data.get("policy_mode") or "").strip()
        policy = dict(data.get("policy") or {})
        return str(policy.get("mode") or "").strip()
    return str(data.get(field) or "").strip()


def compare_active_and_historical_baseline(
    active_contract: Mapping[str, Any] | None,
    historical_item: Mapping[str, Any] | None,
) -> dict[str, Any]:
    active = _contract_from_history_or_contract(active_contract)
    historical = _contract_from_history_or_contract(historical_item)
    if not active or not historical:
        return {
            "state": "missing",
            "banner_id": BASELINE_MISSING_BANNER_ID,
            "silent_rebinding_allowed": False,
            "mismatch_fields": tuple(),
            "banner": "Для сравнения active/historical baseline не хватает contract payload.",
        }

    context_fields = ("suite_snapshot_hash", "inputs_snapshot_hash", "policy_mode")
    mismatch_fields = tuple(
        field
        for field in context_fields
        if _baseline_compare_value(active, field) != _baseline_compare_value(historical, field)
    )
    same_hash = _baseline_compare_value(active, "active_baseline_hash") == _baseline_compare_value(
        historical,
        "active_baseline_hash",
    )
    if mismatch_fields:
        return {
            "state": "historical_mismatch",
            "banner_id": BASELINE_MISMATCH_BANNER_ID,
            "silent_rebinding_allowed": False,
            "requires_explicit_action": True,
            "required_action": "review_and_adopt_explicitly",
            "mismatch_fields": mismatch_fields,
            "banner": (
                "Исторический baseline собран на другом контексте: "
                + ", ".join(mismatch_fields)
                + ". Silent rebinding запрещён."
            ),
        }
    if same_hash:
        return {
            "state": "active",
            "banner_id": "",
            "silent_rebinding_allowed": False,
            "requires_explicit_action": False,
            "mismatch_fields": tuple(),
            "banner": "Выбранный baseline совпадает с active_baseline_contract.",
        }
    return {
        "state": "historical_same_context",
        "banner_id": BASELINE_HISTORICAL_BANNER_ID,
        "silent_rebinding_allowed": False,
        "requires_explicit_action": True,
        "required_action": "restore_or_adopt_explicitly",
        "mismatch_fields": tuple(),
        "banner": (
            "Открыт исторический baseline из того же контекста. "
            "Restore/adopt возможен только явным действием пользователя."
        ),
    }



def baseline_source_artifact_path(run_dir: Path | str) -> Path:
    return Path(run_dir) / "baseline_source.json"


def write_baseline_source_artifact(run_dir: Path | str, payload: Mapping[str, Any]) -> Path:
    path = baseline_source_artifact_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload or {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def read_baseline_source_artifact(run_dir: Path | str) -> dict[str, Any]:
    path = baseline_source_artifact_path(run_dir)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


__all__ = [
    "BASELINE_SOURCE_KIND_GLOBAL",
    "BASELINE_SOURCE_KIND_NONE",
    "BASELINE_SOURCE_KIND_SCOPED",
    "baseline_problem_scope_dir",
    "baseline_source_artifact_path",
    "baseline_source_label",
    "baseline_source_short_label",
    "baseline_suite_handoff_snapshot_path",
    "compare_active_and_historical_baseline",
    "describe_active_baseline_state",
    "read_baseline_source_artifact",
    "resolve_baseline_suite_handoff",
    "resolve_workspace_baseline_override_path",
    "resolve_workspace_baseline_source",
    "workspace_baseline_dir",
    "write_baseline_source_artifact",
]
