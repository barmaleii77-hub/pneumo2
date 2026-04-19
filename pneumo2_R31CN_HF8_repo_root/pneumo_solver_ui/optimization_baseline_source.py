from __future__ import annotations

import json
import hashlib
import os
from datetime import UTC, datetime
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


def _utc_now_label() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _path_text(value: Path | str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return str(Path(text))
    except Exception:
        return text


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


def baseline_history_path(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    current_baseline_dir = (
        Path(baseline_dir).resolve()
        if baseline_dir is not None
        else workspace_baseline_dir(
            env=env,
            workspace_dir=workspace_dir,
            repo_root=repo_root,
        )
    )
    return current_baseline_dir / BASELINE_HISTORY_FILENAME


def active_baseline_contract_path(
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
    return (
        effective_workspace
        / "handoffs"
        / WS_BASELINE_SOURCE_WORKSPACE
        / ACTIVE_BASELINE_CONTRACT_FILENAME
    ).resolve()


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


def _baseline_context_label(field: str) -> str:
    labels = {
        "active_baseline_hash": "Опорный прогон",
        "suite_snapshot_hash": "Снимок набора испытаний",
        "inputs_snapshot_hash": "Исходные данные",
        "ring_source_hash": "Сценарий кольца",
        "policy_mode": "Режим расчёта",
    }
    return labels.get(str(field or "").strip(), str(field or "").strip())


def _baseline_context_labels(fields: tuple[str, ...] | list[str]) -> str:
    return ", ".join(_baseline_context_label(field) for field in fields if str(field or "").strip())


def _baseline_stale_reason_label(reason: str) -> str:
    labels = {
        "missing_active_baseline_contract": "активный опорный прогон не найден",
        "unsupported_active_baseline_schema": "неподдерживаемая схема активного опорного прогона",
        "wrong_baseline_handoff_id": "опорный прогон записан не для оптимизации",
        "active_baseline_hash_mismatch": "контрольная сумма опорного прогона не совпадает",
        "suite_snapshot_not_validated": "снимок набора испытаний не проверен",
        "suite_snapshot_hash_changed": "снимок набора испытаний изменился",
        "inputs_snapshot_hash_changed": "исходные данные изменились",
        "ring_source_hash_changed": "сценарий кольца изменился",
    }
    return labels.get(str(reason or "").strip(), str(reason or "").strip())


def _baseline_stale_reason_labels(reasons: tuple[str, ...] | list[str]) -> str:
    return ", ".join(
        _baseline_stale_reason_label(reason)
        for reason in reasons
        if str(reason or "").strip()
    )


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
    """Read the frozen suite snapshot used by the baseline stage."""

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
            "Снимок набора испытаний не найден. "
            "Краткий предпросмотр должен получить зафиксированный снимок набора."
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
            "banner": f"Снимок набора испытаний не читается: {exc}",
        }
    if not isinstance(raw, dict):
        return {
            **base_payload,
            "state": "invalid",
            "banner": "Снимок набора испытаний должен быть JSON-объектом.",
        }
    if str(raw.get("schema_version") or "") != VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION:
        return {
            **base_payload,
            "state": "invalid",
            "banner": "Снимок набора испытаний имеет неподдерживаемую версию схемы.",
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
            "banner": "Снимок набора испытаний устарел относительно текущего набора.",
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
            "Снимок набора испытаний актуален для краткого предпросмотра."
            if validated
            else "Снимок набора испытаний найден, но проверка не пройдена."
        ),
    }


def baseline_suite_handoff_launch_gate(
    *,
    launch_profile: str = "baseline",
    runtime_policy: str = "",
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
) -> dict[str, Any]:
    """Resolve whether a launch may proceed with the frozen suite snapshot."""

    profile = str(launch_profile or "baseline").strip().lower() or "baseline"
    policy = str(runtime_policy or "").strip().lower()
    handoff = resolve_baseline_suite_handoff(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
    )
    state = str(handoff.get("state") or "missing")
    baseline_ready = state == "current" and bool(handoff.get("baseline_can_consume", False))
    if profile != "baseline":
        return {
            **handoff,
            "launch_profile": profile,
            "runtime_policy": policy,
            "gate_required": False,
            "warning_only": True,
            "baseline_launch_allowed": True,
            "runtime_policy_can_bypass": True,
            "banner": (
                "Снимок набора испытаний не блокирует детальный и полный запуск. "
                + str(handoff.get("banner") or "").strip()
            ).strip(),
        }
    if baseline_ready:
        return {
            **handoff,
            "launch_profile": profile,
            "runtime_policy": policy,
            "gate_required": True,
            "warning_only": False,
            "baseline_launch_allowed": True,
            "runtime_policy_can_bypass": False,
        }
    return {
        **handoff,
        "launch_profile": profile,
        "runtime_policy": policy,
        "gate_required": True,
        "warning_only": False,
        "baseline_launch_allowed": False,
        "runtime_policy_can_bypass": False,
        "banner": (
            "Краткий предпросмотр заблокирован набором испытаний. Режим выполнения не может обойти "
            "отсутствующий, устаревший или некорректный снимок набора. "
            + str(handoff.get("banner") or "").strip()
        ).strip(),
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


def _baseline_artifact_hash(
    *,
    baseline_path: Path | str | None = None,
    baseline_payload: Mapping[str, Any] | None = None,
) -> str:
    if isinstance(baseline_payload, Mapping):
        return _sha256_payload(dict(baseline_payload))
    return _file_sha256(baseline_path)


def build_active_baseline_contract(
    *,
    suite_snapshot: Mapping[str, Any] | None,
    baseline_path: Path | str | None = None,
    baseline_payload: Mapping[str, Any] | None = None,
    baseline_score_payload: Mapping[str, Any] | None = None,
    baseline_meta: Mapping[str, Any] | None = None,
    source_run_dir: Path | str | None = None,
    policy_mode: str = "review_adopt",
    action: str = "adopt",
    note: str = "",
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Create the frozen active baseline contract consumed by optimization."""

    suite_ctx = _suite_context_fields(suite_snapshot)
    policy = {
        "mode": str(policy_mode or "review_adopt").strip() or "review_adopt",
        "action": str(action or "adopt").strip() or "adopt",
        "requires_explicit_review": True,
        "silent_rebinding_allowed": False,
        "review_actions": ["review", "adopt", "restore"],
    }
    baseline = {
        "baseline_path": _path_text(baseline_path),
        "baseline_payload_hash": _baseline_artifact_hash(
            baseline_path=baseline_path,
            baseline_payload=baseline_payload,
        ),
        "score_payload_hash": (
            _sha256_payload(dict(baseline_score_payload))
            if isinstance(baseline_score_payload, Mapping)
            else ""
        ),
        "baseline_meta_hash": (
            _sha256_payload(dict(baseline_meta))
            if isinstance(baseline_meta, Mapping)
            else ""
        ),
        "problem_hash": str((baseline_meta or {}).get("problem_hash") or "").strip()
        if isinstance(baseline_meta, Mapping)
        else "",
        "source_run_dir": _path_text(source_run_dir),
    }
    core = {
        "schema_version": ACTIVE_BASELINE_CONTRACT_SCHEMA_VERSION,
        "source_workspace": WS_BASELINE_SOURCE_WORKSPACE,
        "target_workspace": WS_BASELINE_TARGET_WORKSPACE,
        "handoff_id": WS_BASELINE_HANDOFF_ID,
        "frozen": True,
        "baseline": baseline,
        "suite_snapshot_hash": suite_ctx["suite_snapshot_hash"],
        "inputs_snapshot_hash": suite_ctx["inputs_snapshot_hash"],
        "ring_source_hash": suite_ctx["ring_source_hash"],
        "suite_validated": bool(suite_ctx["suite_validated"]),
        "suite_context_label": suite_ctx["suite_context_label"],
        "suite_snapshot_ref": suite_ctx["suite_snapshot_ref"],
        "policy": policy,
        "note": str(note or "").strip(),
    }
    active_hash = _sha256_payload(core)
    return {
        **core,
        "created_at_utc": str(created_at_utc or _utc_now_label()),
        "active_baseline_hash": active_hash,
        "history_id": f"baseline_{active_hash[:16]}",
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


def write_active_baseline_contract(
    contract: Mapping[str, Any],
    *,
    path: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    target = (
        Path(path)
        if path is not None
        else active_baseline_contract_path(
            env=env,
            workspace_dir=workspace_dir,
            repo_root=repo_root,
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(contract or {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def read_active_baseline_contract(
    *,
    path: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    source = (
        Path(path)
        if path is not None
        else active_baseline_contract_path(
            env=env,
            workspace_dir=workspace_dir,
            repo_root=repo_root,
        )
    )
    try:
        obj = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


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
                "Активный опорный прогон не найден. "
                "Оптимизация не должна молча подставлять запасной опорный прогон."
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
            "banner": (
                "Активный опорный прогон имеет неподдерживаемую схему; "
                "молчаливая подмена запрещена."
            ),
        }
    if str(payload.get("handoff_id") or "") != WS_BASELINE_HANDOFF_ID:
        return {
            "state": "invalid",
            "is_stale": True,
            "optimizer_can_consume": False,
            "banner_id": BASELINE_MISSING_BANNER_ID,
            "stale_reasons": ["wrong_baseline_handoff_id"],
            "banner": "Активный опорный прогон записан не для передачи в оптимизацию.",
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
            "banner": (
                "Контрольная сумма активного опорного прогона не совпадает с "
                "зафиксированными данными; используйте явное действие просмотра, "
                "принятия или восстановления."
            ),
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
                "Активный опорный прогон ссылается на непроверенный снимок набора "
                "испытаний; сначала зафиксируйте и проверьте набор."
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
                "Активный опорный прогон устарел для текущего контекста: "
                + _baseline_stale_reason_labels(stale_reasons)
                + ". Требуется явное действие пользователя; молчаливая подмена запрещена."
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
        "banner": f"Активный опорный прогон актуален: {stored_hash[:12]}.",
    }


def resolve_active_baseline_handoff(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
) -> dict[str, Any]:
    path = active_baseline_contract_path(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
    )
    base_payload: dict[str, Any] = {
        "version": "active_baseline_handoff_v1",
        "handoff_id": WS_BASELINE_HANDOFF_ID,
        "source_workspace": WS_BASELINE_SOURCE_WORKSPACE,
        "target_workspace": WS_BASELINE_TARGET_WORKSPACE,
        "contract_path": str(path),
        "active_baseline_hash": "",
        "suite_snapshot_hash": "",
        "state": "missing",
        "optimizer_can_consume": False,
        "silent_rebinding_allowed": False,
        "banner_id": BASELINE_MISSING_BANNER_ID,
        "banner": (
            "Активный опорный прогон не найден. "
            "Оптимизация не должна молча подставлять запасной опорный прогон."
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
            "banner": f"Файл активного опорного прогона не читается: {exc}",
        }
    if not isinstance(raw, dict):
        return {
            **base_payload,
            "state": "invalid",
            "banner": "Файл активного опорного прогона должен быть JSON-объектом.",
        }

    state = describe_active_baseline_state(
        raw,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
        current_ring_source_hash=current_ring_source_hash,
    )
    return {
        **base_payload,
        **state,
        "active_baseline_hash": str(raw.get("active_baseline_hash") or ""),
        "suite_snapshot_hash": str(raw.get("suite_snapshot_hash") or ""),
        "inputs_snapshot_hash": str(raw.get("inputs_snapshot_hash") or ""),
        "ring_source_hash": str(raw.get("ring_source_hash") or ""),
        "contract_path": str(path),
    }


def baseline_history_item_from_contract(
    contract: Mapping[str, Any],
    *,
    action: str = "adopt",
    actor: str = "",
    note: str = "",
    ts_utc: str | None = None,
) -> dict[str, Any]:
    payload = dict(contract or {})
    policy = dict(payload.get("policy") or {})
    baseline = dict(payload.get("baseline") or {})
    history_id = str(payload.get("history_id") or "").strip() or (
        f"baseline_{str(payload.get('active_baseline_hash') or '')[:16]}"
    )
    return {
        "schema_version": BASELINE_HISTORY_ITEM_SCHEMA_VERSION,
        "history_id": history_id,
        "ts_utc": str(ts_utc or _utc_now_label()),
        "action": str(action or "adopt").strip() or "adopt",
        "actor": str(actor or "").strip(),
        "note": str(note or "").strip(),
        "active_baseline_hash": str(payload.get("active_baseline_hash") or "").strip(),
        "suite_snapshot_hash": str(payload.get("suite_snapshot_hash") or "").strip(),
        "inputs_snapshot_hash": str(payload.get("inputs_snapshot_hash") or "").strip(),
        "ring_source_hash": str(payload.get("ring_source_hash") or "").strip(),
        "policy_mode": str(policy.get("mode") or "").strip(),
        "baseline_path": str(baseline.get("baseline_path") or "").strip(),
        "source_run_dir": str(baseline.get("source_run_dir") or "").strip(),
        "contract": payload,
    }


def append_baseline_history_item(
    item: Mapping[str, Any],
    *,
    path: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    target = (
        Path(path)
        if path is not None
        else baseline_history_path(
            env=env,
            workspace_dir=workspace_dir,
            baseline_dir=baseline_dir,
            repo_root=repo_root,
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(item or {}), ensure_ascii=False) + "\n")
    return target


def read_baseline_history(
    *,
    path: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    source = (
        Path(path)
        if path is not None
        else baseline_history_path(
            env=env,
            workspace_dir=workspace_dir,
            baseline_dir=baseline_dir,
            repo_root=repo_root,
        )
    )
    if not source.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in source.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(dict(obj))
    except Exception:
        return rows
    if limit is not None and int(limit) >= 0:
        return rows[-int(limit):]
    return rows


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
            "banner": "Для сравнения активного и исторического опорного прогона не хватает сохранённых данных.",
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
                "Исторический опорный прогон собран на другом контексте: "
                + _baseline_context_labels(mismatch_fields)
                + ". Молчаливая подмена запрещена."
            ),
        }
    if same_hash:
        return {
            "state": "active",
            "banner_id": "",
            "silent_rebinding_allowed": False,
            "requires_explicit_action": False,
            "mismatch_fields": tuple(),
            "banner": "Выбранный опорный прогон уже является активным.",
        }
    return {
        "state": "historical_same_context",
        "banner_id": BASELINE_HISTORICAL_BANNER_ID,
        "silent_rebinding_allowed": False,
        "requires_explicit_action": True,
        "required_action": "restore_or_adopt_explicitly",
        "mismatch_fields": tuple(),
        "banner": (
            "Открыт исторический опорный прогон из того же контекста. "
            "Восстановление или принятие возможно только явным действием пользователя."
        ),
    }


def baseline_review_adopt_restore_policy(
    candidate: Mapping[str, Any] | None,
    *,
    active_contract: Mapping[str, Any] | None = None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    action: str = "review",
    explicit: bool = False,
) -> dict[str, Any]:
    candidate_contract = _contract_from_history_or_contract(candidate)
    candidate_state = describe_active_baseline_state(
        candidate_contract if candidate_contract else None,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
    )
    compare_state = (
        compare_active_and_historical_baseline(active_contract, candidate_contract)
        if active_contract is not None and candidate_contract
        else {}
    )
    requested_action = str(action or "review").strip().lower() or "review"
    if requested_action not in {"review", "adopt", "restore"}:
        requested_action = "review"
    candidate_state_name = str(candidate_state.get("state") or "")
    candidate_invalid = candidate_state_name in {"missing", "invalid"}
    candidate_current = candidate_state_name == "current"
    requires_explicit = requested_action in {"adopt", "restore"} or bool(
        compare_state.get("requires_explicit_action", False)
    )
    can_apply = False
    if requested_action == "adopt":
        can_apply = bool(explicit) and candidate_current
    elif requested_action == "restore":
        can_apply = bool(explicit) and not candidate_invalid
    return {
        "action": requested_action,
        "allowed_actions": ("review", "adopt", "restore"),
        "candidate_state": candidate_state_name,
        "candidate_stale_reasons": tuple(str(item) for item in candidate_state.get("stale_reasons") or ()),
        "compare_state": str(compare_state.get("state") or ""),
        "can_apply": bool(can_apply),
        "requires_explicit_action": bool(requires_explicit),
        "silent_rebinding_allowed": False,
        "banner_id": str(compare_state.get("banner_id") or candidate_state.get("banner_id") or ""),
        "banner": str(compare_state.get("banner") or candidate_state.get("banner") or ""),
    }


def _history_row_payload(
    item: Mapping[str, Any],
    *,
    active_contract: Mapping[str, Any] | None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
    explicit_confirmation: bool = False,
) -> dict[str, Any]:
    row = dict(item or {})
    contract = _contract_from_history_or_contract(row)
    compare_state = (
        compare_active_and_historical_baseline(active_contract, contract)
        if active_contract is not None and contract
        else {}
    )
    review_policy = baseline_review_adopt_restore_policy(
        contract,
        active_contract=active_contract,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
        action="review",
        explicit=False,
    )
    adopt_policy = baseline_review_adopt_restore_policy(
        contract,
        active_contract=active_contract,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
        action="adopt",
        explicit=explicit_confirmation,
    )
    restore_policy = baseline_review_adopt_restore_policy(
        contract,
        active_contract=active_contract,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
        action="restore",
        explicit=explicit_confirmation,
    )
    baseline = dict(contract.get("baseline") or {})
    policy = dict(contract.get("policy") or {})
    return {
        "history_id": str(row.get("history_id") or contract.get("history_id") or ""),
        "ts_utc": str(row.get("ts_utc") or contract.get("created_at_utc") or ""),
        "created_at_utc": str(contract.get("created_at_utc") or row.get("ts_utc") or ""),
        "action": str(row.get("action") or policy.get("action") or ""),
        "actor": str(row.get("actor") or ""),
        "note": str(row.get("note") or contract.get("note") or ""),
        "active_baseline_hash": str(
            row.get("active_baseline_hash") or contract.get("active_baseline_hash") or ""
        ),
        "suite_snapshot_hash": str(row.get("suite_snapshot_hash") or contract.get("suite_snapshot_hash") or ""),
        "inputs_snapshot_hash": str(row.get("inputs_snapshot_hash") or contract.get("inputs_snapshot_hash") or ""),
        "ring_source_hash": str(row.get("ring_source_hash") or contract.get("ring_source_hash") or ""),
        "policy_mode": str(row.get("policy_mode") or policy.get("mode") or ""),
        "baseline_path": str(row.get("baseline_path") or baseline.get("baseline_path") or ""),
        "source_run_dir": str(row.get("source_run_dir") or baseline.get("source_run_dir") or ""),
        "compare_state": str(compare_state.get("state") or ""),
        "mismatch_fields": tuple(str(field) for field in compare_state.get("mismatch_fields") or ()),
        "banner_id": str(compare_state.get("banner_id") or review_policy.get("banner_id") or ""),
        "banner": str(compare_state.get("banner") or review_policy.get("banner") or ""),
        "silent_rebinding_allowed": False,
        "allowed_actions": {
            "review": {
                "enabled": bool(contract),
                "read_only": True,
                "requires_explicit_confirmation": False,
            },
            "adopt": {
                "enabled": bool(adopt_policy.get("can_apply", False)),
                "requires_explicit_confirmation": True,
                "candidate_state": str(adopt_policy.get("candidate_state") or ""),
            },
            "restore": {
                "enabled": bool(restore_policy.get("can_apply", False)),
                "requires_explicit_confirmation": True,
                "candidate_state": str(restore_policy.get("candidate_state") or ""),
            },
        },
    }


def build_baseline_center_surface(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
    selected_history_id: str = "",
    history_limit: int | None = 20,
    explicit_confirmation: bool = False,
) -> dict[str, Any]:
    """Build the WS-BASELINE workspace surface without mutating contracts."""

    suite_handoff = resolve_baseline_suite_handoff(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
    )
    suite_hash = str(current_suite_snapshot_hash or suite_handoff.get("suite_snapshot_hash") or "")
    inputs_hash = str(current_inputs_snapshot_hash or suite_handoff.get("inputs_snapshot_hash") or "")
    ring_hash = str(current_ring_source_hash or suite_handoff.get("ring_source_hash") or "")
    active_contract = read_active_baseline_contract(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
    )
    active_handoff = resolve_active_baseline_handoff(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
        current_suite_snapshot_hash=suite_hash,
        current_inputs_snapshot_hash=inputs_hash,
        current_ring_source_hash=ring_hash,
    )
    active_baseline = {
        "contract_path": str(active_handoff.get("contract_path") or ""),
        "state": str(active_handoff.get("state") or ""),
        "banner_id": str(active_handoff.get("banner_id") or ""),
        "banner": str(active_handoff.get("banner") or ""),
        "optimizer_baseline_can_consume": bool(active_handoff.get("optimizer_can_consume", False)),
        "active_baseline_hash": str(active_handoff.get("active_baseline_hash") or ""),
        "suite_snapshot_hash": str(active_handoff.get("suite_snapshot_hash") or ""),
        "inputs_snapshot_hash": str(active_handoff.get("inputs_snapshot_hash") or ""),
        "ring_source_hash": str(active_handoff.get("ring_source_hash") or ""),
        "policy_mode": str(dict(active_contract.get("policy") or {}).get("mode") or ""),
        "source_run_dir": str(dict(active_contract.get("baseline") or {}).get("source_run_dir") or ""),
        "baseline_path": str(dict(active_contract.get("baseline") or {}).get("baseline_path") or ""),
        "created_at_utc": str(active_contract.get("created_at_utc") or ""),
        "handoff_id": WS_BASELINE_HANDOFF_ID,
        "silent_rebinding_allowed": False,
    }
    history = read_baseline_history(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
        limit=history_limit,
    )
    history_rows = tuple(
        _history_row_payload(
            item,
            active_contract=active_contract if active_contract else None,
            current_suite_snapshot_hash=suite_hash,
            current_inputs_snapshot_hash=inputs_hash,
            current_ring_source_hash=ring_hash,
            explicit_confirmation=explicit_confirmation,
        )
        for item in reversed(history)
    )
    selected_id = str(selected_history_id or "").strip()
    selected_row = next((row for row in history_rows if str(row.get("history_id") or "") == selected_id), None)
    if selected_row is None and history_rows:
        selected_row = history_rows[0]
        selected_id = str(selected_row.get("history_id") or "")
    selected_contract = next(
        (
            _contract_from_history_or_contract(item)
            for item in reversed(history)
            if str(item.get("history_id") or "") == selected_id
        ),
        {},
    )
    review_policy = baseline_review_adopt_restore_policy(
        selected_contract,
        active_contract=active_contract if active_contract else None,
        current_suite_snapshot_hash=suite_hash,
        current_inputs_snapshot_hash=inputs_hash,
        action="review",
        explicit=False,
    )
    adopt_policy = baseline_review_adopt_restore_policy(
        selected_contract,
        active_contract=active_contract if active_contract else None,
        current_suite_snapshot_hash=suite_hash,
        current_inputs_snapshot_hash=inputs_hash,
        action="adopt",
        explicit=explicit_confirmation,
    )
    restore_policy = baseline_review_adopt_restore_policy(
        selected_contract,
        active_contract=active_contract if active_contract else None,
        current_suite_snapshot_hash=suite_hash,
        current_inputs_snapshot_hash=inputs_hash,
        action="restore",
        explicit=explicit_confirmation,
    )
    banner_id = str(active_baseline.get("banner_id") or "")
    banner = str(active_baseline.get("banner") or "")
    if selected_row is not None and str(selected_row.get("banner_id") or ""):
        banner_id = str(selected_row.get("banner_id") or "")
        banner = str(selected_row.get("banner") or "")
    return {
        "schema": "baseline_center_surface",
        "schema_version": "1.0.0",
        "workspace_id": WS_BASELINE_SOURCE_WORKSPACE,
        "pipeline": ("HO-005", "active_baseline_contract", WS_BASELINE_HANDOFF_ID),
        "suite_handoff": suite_handoff,
        "active_baseline": active_baseline,
        "history_path": str(
            baseline_history_path(env=env, workspace_dir=workspace_dir, repo_root=repo_root)
        ),
        "history_rows": history_rows,
        "selected_history_id": selected_id,
        "selected_history": selected_row or {},
        "mismatch_state": {
            "state": str((selected_row or {}).get("compare_state") or ""),
            "mismatch_fields": tuple(str(field) for field in (selected_row or {}).get("mismatch_fields") or ()),
        },
        "banner_state": {
            "banner_id": banner_id,
            "banner": banner,
            "active_state": str(active_baseline.get("state") or ""),
            "selected_compare_state": str((selected_row or {}).get("compare_state") or ""),
        },
        "action_strip": {
            "review": {
                "enabled": bool(selected_contract),
                "read_only": True,
                "policy": review_policy,
            },
            "adopt": {
                "enabled": bool(adopt_policy.get("can_apply", False)),
                "requires_explicit_confirmation": True,
                "policy": adopt_policy,
            },
            "restore": {
                "enabled": bool(restore_policy.get("can_apply", False)),
                "requires_explicit_confirmation": True,
                "policy": restore_policy,
            },
        },
        "silent_rebinding_allowed": False,
    }


def apply_baseline_center_action(
    *,
    action: str,
    candidate: Mapping[str, Any] | None = None,
    history_id: str = "",
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    explicit_confirmation: bool = False,
    actor: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Apply explicit baseline actions; review is always read-only."""

    requested_action = str(action or "review").strip().lower() or "review"
    if requested_action not in {"review", "adopt", "restore"}:
        requested_action = "review"
    active_contract = read_active_baseline_contract(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
    )
    candidate_contract = _contract_from_history_or_contract(candidate)
    selected_history_id = str(history_id or "").strip()
    if not candidate_contract and selected_history_id:
        for item in read_baseline_history(env=env, workspace_dir=workspace_dir, repo_root=repo_root):
            if str(item.get("history_id") or "") == selected_history_id:
                candidate_contract = _contract_from_history_or_contract(item)
                break
    suite_handoff = resolve_baseline_suite_handoff(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
    )
    suite_hash = str(current_suite_snapshot_hash or suite_handoff.get("suite_snapshot_hash") or "")
    inputs_hash = str(current_inputs_snapshot_hash or suite_handoff.get("inputs_snapshot_hash") or "")
    policy = baseline_review_adopt_restore_policy(
        candidate_contract,
        active_contract=active_contract if active_contract else None,
        current_suite_snapshot_hash=suite_hash,
        current_inputs_snapshot_hash=inputs_hash,
        action=requested_action,
        explicit=explicit_confirmation,
    )
    result = {
        "action": requested_action,
        "status": "review_only" if requested_action == "review" else "blocked",
        "policy": policy,
        "wrote_active_contract": False,
        "history_appended": False,
        "silent_rebinding_allowed": False,
        "contract_path": "",
        "history_path": "",
    }
    if requested_action == "review" or not bool(policy.get("can_apply", False)):
        return result

    contract_path = write_active_baseline_contract(
        candidate_contract,
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
    )
    history_item = baseline_history_item_from_contract(
        candidate_contract,
        action=requested_action,
        actor=actor,
        note=note,
    )
    history_path = append_baseline_history_item(
        history_item,
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
    )
    return {
        **result,
        "status": "applied",
        "wrote_active_contract": True,
        "history_appended": True,
        "contract_path": str(contract_path),
        "history_path": str(history_path),
        "active_baseline_hash": str(candidate_contract.get("active_baseline_hash") or ""),
    }


def baseline_center_evidence_payload(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    history_limit: int = 5,
) -> dict[str, Any]:
    surface = build_baseline_center_surface(
        env=env,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
        history_limit=history_limit,
    )
    history_rows = tuple(dict(row) for row in surface.get("history_rows") or ())
    relevant_rows = tuple(
        row
        for row in history_rows
        if str(row.get("compare_state") or "") in {"historical_mismatch", "historical_same_context"}
    )[: int(history_limit)]
    if not relevant_rows:
        relevant_rows = history_rows[: int(history_limit)]
    return {
        "schema": "baseline_center_evidence",
        "schema_version": "1.0.0",
        "workspace_id": WS_BASELINE_SOURCE_WORKSPACE,
        "handoff_ids": ("HO-005", WS_BASELINE_HANDOFF_ID),
        "active_contract_path": str(dict(surface.get("active_baseline") or {}).get("contract_path") or ""),
        "active_baseline": dict(surface.get("active_baseline") or {}),
        "history_path": str(surface.get("history_path") or ""),
        "history_excerpt": relevant_rows,
        "banner_state": dict(surface.get("banner_state") or {}),
        "mismatch_state": dict(surface.get("mismatch_state") or {}),
        "send_bundle_should_include": bool(
            str(dict(surface.get("active_baseline") or {}).get("state") or "") != "current"
            or any(str(row.get("compare_state") or "") == "historical_mismatch" for row in history_rows)
        ),
        "silent_rebinding_allowed": False,
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
    "ACTIVE_BASELINE_CONTRACT_FILENAME",
    "ACTIVE_BASELINE_CONTRACT_SCHEMA_VERSION",
    "BASELINE_HISTORY_FILENAME",
    "BASELINE_HISTORY_ITEM_SCHEMA_VERSION",
    "BASELINE_HISTORICAL_BANNER_ID",
    "BASELINE_MISMATCH_BANNER_ID",
    "BASELINE_MISSING_BANNER_ID",
    "BASELINE_SOURCE_KIND_GLOBAL",
    "BASELINE_SOURCE_KIND_NONE",
    "BASELINE_SOURCE_KIND_SCOPED",
    "BASELINE_STALE_BANNER_ID",
    "WS_BASELINE_HANDOFF_ID",
    "WS_BASELINE_SOURCE_WORKSPACE",
    "WS_BASELINE_TARGET_WORKSPACE",
    "active_baseline_contract_path",
    "append_baseline_history_item",
    "apply_baseline_center_action",
    "baseline_center_evidence_payload",
    "baseline_history_item_from_contract",
    "baseline_history_path",
    "baseline_problem_scope_dir",
    "baseline_review_adopt_restore_policy",
    "baseline_suite_handoff_launch_gate",
    "baseline_suite_handoff_snapshot_path",
    "baseline_source_artifact_path",
    "baseline_source_label",
    "baseline_source_short_label",
    "build_active_baseline_contract",
    "build_baseline_center_surface",
    "compare_active_and_historical_baseline",
    "describe_active_baseline_state",
    "read_active_baseline_contract",
    "read_baseline_history",
    "read_baseline_source_artifact",
    "resolve_active_baseline_handoff",
    "resolve_baseline_suite_handoff",
    "resolve_workspace_baseline_override_path",
    "resolve_workspace_baseline_source",
    "workspace_baseline_dir",
    "write_active_baseline_contract",
    "write_baseline_source_artifact",
]
