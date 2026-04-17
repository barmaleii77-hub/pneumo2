from __future__ import annotations

"""Runtime facade for WS-SUITE and the HO-005 validated suite handoff."""

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from pneumo_solver_ui.desktop_input_model import (
    DESKTOP_INPUT_SNAPSHOT_FILENAME,
    default_suite_json_path,
    repo_root as desktop_repo_root,
)
from pneumo_solver_ui.desktop_suite_snapshot import (
    SUITE_ROW_REF_KEYS,
    VALIDATED_SUITE_SNAPSHOT_FILENAME,
    build_validated_suite_snapshot,
    describe_suite_snapshot_state,
    load_suite_rows,
    resolve_suite_inputs_handoff,
)


DESKTOP_SUITE_OVERRIDES_SCHEMA_VERSION = "desktop_suite_overrides_v1"
DESKTOP_SUITE_OVERRIDES_FILENAME = "desktop_suite_overrides.json"


def _repo_root(repo_root: Path | str | None = None) -> Path:
    return Path(repo_root).resolve() if repo_root is not None else desktop_repo_root()


def _workspace_dir(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir).resolve()
    return (_repo_root(repo_root) / "workspace").resolve()


def desktop_suite_overrides_path(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    return (_workspace_dir(workspace_dir=workspace_dir, repo_root=repo_root) / "ui_state" / DESKTOP_SUITE_OVERRIDES_FILENAME).resolve()


def desktop_suite_handoff_path(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    return (
        _workspace_dir(workspace_dir=workspace_dir, repo_root=repo_root)
        / "handoffs"
        / "WS-SUITE"
        / VALIDATED_SUITE_SNAPSHOT_FILENAME
    ).resolve()


def desktop_suite_handoff_dir(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    return desktop_suite_handoff_path(workspace_dir=workspace_dir, repo_root=repo_root).parent


def desktop_inputs_snapshot_path(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    return (
        _workspace_dir(workspace_dir=workspace_dir, repo_root=repo_root)
        / "handoffs"
        / "WS-INPUTS"
        / DESKTOP_INPUT_SNAPSHOT_FILENAME
    ).resolve()


def _read_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_json_object(path: Path | str) -> dict[str, Any]:
    raw = _read_json(path)
    return dict(raw) if isinstance(raw, Mapping) else {}


def _write_json(path: Path | str, payload: Mapping[str, Any]) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def normalize_desktop_suite_overrides(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(overrides or {})
    return {
        "schema_version": DESKTOP_SUITE_OVERRIDES_SCHEMA_VERSION,
        "source_workspace": "WS-SUITE",
        "global": dict(payload.get("global") or {}),
        "by_name": dict(payload.get("by_name") or {}),
        "by_id": dict(payload.get("by_id") or {}),
    }


def load_desktop_suite_overrides(
    *,
    path: Path | str | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    target = Path(path).resolve() if path is not None else desktop_suite_overrides_path(workspace_dir=workspace_dir, repo_root=repo_root)
    if not target.exists():
        return normalize_desktop_suite_overrides()
    raw = _read_json_object(target)
    if str(raw.get("schema_version") or "") not in {"", DESKTOP_SUITE_OVERRIDES_SCHEMA_VERSION}:
        raise ValueError(f"Unsupported desktop suite overrides schema: {target}")
    return normalize_desktop_suite_overrides(raw)


def save_desktop_suite_overrides(
    overrides: Mapping[str, Any],
    *,
    path: Path | str | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    target = Path(path).resolve() if path is not None else desktop_suite_overrides_path(workspace_dir=workspace_dir, repo_root=repo_root)
    return _write_json(target, normalize_desktop_suite_overrides(overrides))


def reset_desktop_suite_overrides(
    *,
    path: Path | str | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    return save_desktop_suite_overrides(
        normalize_desktop_suite_overrides(),
        path=path,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
    )


def build_run_setup_suite_overrides(
    *,
    runtime_policy: str = "",
    cache_policy: str = "",
    export_csv: bool | None = None,
    export_npz: bool | None = None,
    record_full: bool | None = None,
) -> dict[str, Any]:
    global_patch: dict[str, Any] = {}
    if runtime_policy:
        global_patch["runtime_policy"] = str(runtime_policy).strip()
    if cache_policy:
        global_patch["cache_policy"] = str(cache_policy).strip()
    if export_csv is not None:
        global_patch["export_csv"] = bool(export_csv)
    if export_npz is not None:
        global_patch["export_npz"] = bool(export_npz)
    if record_full is not None:
        global_patch["record_full"] = bool(record_full)
    return normalize_desktop_suite_overrides({"global": global_patch})


def load_default_suite_rows() -> list[dict[str, Any]]:
    return load_suite_rows(default_suite_json_path())


def _row_enabled(row: Mapping[str, Any]) -> bool:
    value = row.get("включен", row.get("enabled", True))
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"0", "false", "no", "off", "нет"}:
            return False
        if lowered in {"1", "true", "yes", "on", "да"}:
            return True
    return bool(value)


def _row_has_ring_refs(row: Mapping[str, Any]) -> bool:
    row_type = str(row.get("тип", row.get("type", "")) or "").strip().lower()
    if row_type in {"maneuver_csv", "road_profile_csv"}:
        return True
    return any(str(row.get(key) or "").strip() for key in SUITE_ROW_REF_KEYS)


def _resolve_relative(raw: Any, *, base_path: Path | str | None = None) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        return str(path.resolve())
    if base_path is not None:
        return str((Path(base_path).resolve().parent / path).resolve())
    return str(path)


def read_inputs_snapshot_context(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    path = desktop_inputs_snapshot_path(workspace_dir=workspace_dir, repo_root=repo_root)
    state = resolve_suite_inputs_handoff(snapshot_path=path)
    payload_hash = str(state.get("payload_hash") or "").strip()
    snapshot_hash = str(state.get("snapshot_hash") or "").strip()
    return {
        "state": str(state.get("state") or "missing"),
        "path": str(path),
        "snapshot_hash": snapshot_hash,
        "payload_hash": payload_hash,
        "handoff_id": "HO-003",
        "can_consume": bool(state.get("can_consume", False)),
        "stale_reasons": list(state.get("stale_reasons") or []),
        "banner": str(state.get("banner") or "").strip(),
    }


def _ring_hash_from_scenario(scenario_json: str) -> dict[str, Any]:
    path = Path(str(scenario_json or "").strip())
    if not path.exists() or not path.is_file():
        return {}
    try:
        spec = _read_json_object(path)
    except Exception:
        return {}
    lineage = spec.get("_lineage") if isinstance(spec.get("_lineage"), Mapping) else {}
    outputs = spec.get("_generated_outputs") if isinstance(spec.get("_generated_outputs"), Mapping) else {}
    return {
        "scenario_json": str(path.resolve()),
        "handoff_id": str(lineage.get("handoff_id") or "HO-004"),
        "source_workspace": "WS-RING",
        "ring_source_hash_sha256": str(lineage.get("ring_source_hash_sha256") or "").strip(),
        "ring_export_set_hash_sha256": str(lineage.get("ring_export_set_hash_sha256") or "").strip(),
        "meta_json": _resolve_relative(outputs.get("meta_json"), base_path=path),
        "ring_source_of_truth_json": _resolve_relative(outputs.get("ring_source_of_truth_json"), base_path=path),
    }


def resolve_ring_source_context(
    rows: Iterable[Mapping[str, Any]],
    *,
    suite_source_path: Path | str | None = None,
    suite_meta_path: Path | str | None = None,
) -> dict[str, Any]:
    normalized = [dict(row) for row in rows if isinstance(row, Mapping)]
    enabled_ring_rows = [row for row in normalized if _row_enabled(row) and _row_has_ring_refs(row)]
    required = bool(enabled_ring_rows)
    meta_candidates: list[Path] = []
    if suite_meta_path is not None:
        meta_candidates.append(Path(suite_meta_path).resolve())
    if suite_source_path is not None:
        source = Path(suite_source_path).resolve()
        meta_candidates.append(source.with_name("suite_auto_ring_meta.json"))

    source_ref: dict[str, Any] = {}
    for meta_path in meta_candidates:
        if not meta_path.exists():
            continue
        try:
            meta = _read_json_object(meta_path)
        except Exception:
            continue
        handoff = meta.get("handoff") if isinstance(meta.get("handoff"), Mapping) else {}
        lineage = meta.get("lineage") if isinstance(meta.get("lineage"), Mapping) else {}
        source_ref = dict(handoff or lineage or {})
        if source_ref:
            source_ref.setdefault("meta_json", str(meta_path))
        source_hash = str(
            source_ref.get("ring_source_hash_sha256")
            or source_ref.get("source_hash")
            or lineage.get("ring_source_hash_sha256")
            or ""
        ).strip()
        if source_hash:
            return {
                "state": "current",
                "required_by_suite": required,
                "source_hash": source_hash,
                "source_ref": source_ref,
                "banner": "WS-RING HO-004 hash найден в suite meta.",
            }

    for row in enabled_ring_rows:
        row_hash = str(row.get("ring_source_hash_sha256") or row.get("ring_source_hash") or "").strip()
        if row_hash:
            return {
                "state": "current",
                "required_by_suite": required,
                "source_hash": row_hash,
                "source_ref": {
                    key: row.get(key)
                    for key in (
                        "handoff_id",
                        "source_workspace",
                        "consumer_workspace",
                        "ring_source_hash_sha256",
                        "ring_source_of_truth_json",
                        "segment_meta_ref",
                        "scenario_json_path",
                        "road_csv_path",
                        "axay_csv_path",
                    )
                    if str(row.get(key) or "").strip()
                },
                "banner": "WS-RING HO-004 hash найден в строке suite.",
            }
        scenario_context = _ring_hash_from_scenario(str(row.get("scenario_json") or ""))
        scenario_hash = str(scenario_context.get("ring_source_hash_sha256") or "").strip()
        if scenario_hash:
            return {
                "state": "current",
                "required_by_suite": required,
                "source_hash": scenario_hash,
                "source_ref": scenario_context,
                "banner": "WS-RING HO-004 hash найден в scenario _lineage.",
            }

    return {
        "state": "missing" if required else "not_required",
        "required_by_suite": required,
        "source_hash": "",
        "source_ref": {},
        "banner": (
            "WS-RING HO-004 hash не найден для ring-backed строк suite."
            if required
            else "В выбранном наборе нет ring-backed строк, HO-004 hash не требуется."
        ),
    }


def _upstream_errors(
    *,
    inputs_context: Mapping[str, Any],
    ring_context: Mapping[str, Any],
    require_inputs_snapshot: bool,
    require_ring_hash_for_ring_refs: bool,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if require_inputs_snapshot and not str(inputs_context.get("payload_hash") or "").strip():
        errors.append(
            {
                "source_workspace": "WS-INPUTS",
                "handoff_id": "HO-003",
                "key": "inputs_snapshot.payload_hash",
                "path": str(inputs_context.get("path") or ""),
                "reason": str(inputs_context.get("state") or "missing"),
            }
        )
    if (
        require_ring_hash_for_ring_refs
        and bool(ring_context.get("required_by_suite", False))
        and not str(ring_context.get("source_hash") or "").strip()
    ):
        errors.append(
            {
                "source_workspace": "WS-RING",
                "handoff_id": "HO-004",
                "key": "ring_source_hash_sha256",
                "path": str(ring_context.get("source_ref") or ""),
                "reason": str(ring_context.get("state") or "missing"),
            }
        )
    return errors


def build_desktop_suite_snapshot_context(
    rows: Iterable[Mapping[str, Any]],
    *,
    suite_source_path: Path | str | None = None,
    suite_meta_path: Path | str | None = None,
    overrides: Mapping[str, Any] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    context_label: str = "run_setup",
    require_inputs_snapshot: bool = True,
    require_ring_hash_for_ring_refs: bool = True,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    inputs_context = read_inputs_snapshot_context(workspace_dir=workspace_dir, repo_root=repo_root)
    ring_context = resolve_ring_source_context(
        normalized_rows,
        suite_source_path=suite_source_path,
        suite_meta_path=suite_meta_path,
    )
    upstream_errors = _upstream_errors(
        inputs_context=inputs_context,
        ring_context=ring_context,
        require_inputs_snapshot=require_inputs_snapshot,
        require_ring_hash_for_ring_refs=require_ring_hash_for_ring_refs,
    )
    snapshot = build_validated_suite_snapshot(
        normalized_rows,
        suite_source_path=suite_source_path,
        inputs_snapshot_ref=inputs_context.get("path") or "",
        inputs_snapshot_hash=str(inputs_context.get("payload_hash") or ""),
        ring_source_ref=dict(ring_context.get("source_ref") or {}),
        ring_source_hash=str(ring_context.get("source_hash") or ""),
        overrides=overrides,
        upstream_ref_errors=upstream_errors,
        created_at_utc=created_at_utc,
        repo_root=repo_root,
        context_label=context_label,
    )
    handoff_path = desktop_suite_handoff_path(workspace_dir=workspace_dir, repo_root=repo_root)
    existing_snapshot: dict[str, Any] | None = None
    if handoff_path.exists():
        try:
            existing_snapshot = _read_json_object(handoff_path)
        except Exception:
            existing_snapshot = {}
    existing_state = describe_suite_snapshot_state(
        existing_snapshot if existing_snapshot else None,
        current_inputs_snapshot_hash=str(inputs_context.get("payload_hash") or ""),
        current_ring_source_hash=str(ring_context.get("source_hash") or ""),
        current_suite_snapshot_hash=str(snapshot.get("suite_snapshot_hash") or ""),
    )
    return {
        "snapshot": snapshot,
        "state": describe_suite_snapshot_state(
            snapshot,
            current_inputs_snapshot_hash=str(inputs_context.get("payload_hash") or ""),
            current_ring_source_hash=str(ring_context.get("source_hash") or ""),
            current_suite_snapshot_hash=str(snapshot.get("suite_snapshot_hash") or ""),
        ),
        "existing_state": existing_state,
        "inputs_context": inputs_context,
        "ring_context": ring_context,
        "handoff_path": str(handoff_path),
        "overrides_path": str(desktop_suite_overrides_path(workspace_dir=workspace_dir, repo_root=repo_root)),
    }


def write_desktop_suite_handoff_snapshot(
    rows: Iterable[Mapping[str, Any]],
    *,
    suite_source_path: Path | str | None = None,
    suite_meta_path: Path | str | None = None,
    overrides: Mapping[str, Any] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    context_label: str = "run_setup",
    require_inputs_snapshot: bool = True,
    require_ring_hash_for_ring_refs: bool = True,
) -> dict[str, Any]:
    context = build_desktop_suite_snapshot_context(
        rows,
        suite_source_path=suite_source_path,
        suite_meta_path=suite_meta_path,
        overrides=overrides,
        workspace_dir=workspace_dir,
        repo_root=repo_root,
        context_label=context_label,
        require_inputs_snapshot=require_inputs_snapshot,
        require_ring_hash_for_ring_refs=require_ring_hash_for_ring_refs,
    )
    target = Path(str(context["handoff_path"]))
    _write_json(target, dict(context["snapshot"]))
    context["written_path"] = str(target)
    context["existing_state"] = describe_suite_snapshot_state(
        dict(context["snapshot"]),
        current_inputs_snapshot_hash=str(context["inputs_context"].get("payload_hash") or ""),
        current_ring_source_hash=str(context["ring_context"].get("source_hash") or ""),
        current_suite_snapshot_hash=str(context["snapshot"].get("suite_snapshot_hash") or ""),
    )
    return context


def read_desktop_suite_handoff_state(
    *,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
    current_suite_snapshot_hash: str = "",
) -> dict[str, Any]:
    target = desktop_suite_handoff_path(workspace_dir=workspace_dir, repo_root=repo_root)
    if not target.exists():
        return {
            "path": str(target),
            **describe_suite_snapshot_state(None),
        }
    try:
        snapshot = _read_json_object(target)
    except Exception as exc:
        return {
            "path": str(target),
            "state": "invalid",
            "is_stale": True,
            "handoff_ready": False,
            "stale_reasons": ["unreadable_validated_suite_snapshot"],
            "banner": f"validated_suite_snapshot не читается: {exc}",
        }
    return {
        "path": str(target),
        "suite_snapshot_hash": str(snapshot.get("suite_snapshot_hash") or ""),
        "preview": dict(snapshot.get("preview") or {}),
        "validation": dict(snapshot.get("validation") or {}),
        **describe_suite_snapshot_state(
            snapshot,
            current_inputs_snapshot_hash=current_inputs_snapshot_hash,
            current_ring_source_hash=current_ring_source_hash,
            current_suite_snapshot_hash=current_suite_snapshot_hash,
        ),
    }


def format_desktop_suite_status_lines(context: Mapping[str, Any]) -> tuple[str, ...]:
    snapshot = dict(context.get("snapshot") or {})
    preview = dict(snapshot.get("preview") or {})
    validation = dict(snapshot.get("validation") or {})
    existing_state = dict(context.get("existing_state") or {})
    current_state = dict(context.get("state") or {})
    inputs_context = dict(context.get("inputs_context") or {})
    handoff_path = str(context.get("handoff_path") or "")
    suite_hash = str(snapshot.get("suite_snapshot_hash") or "")
    input_hash = str(inputs_context.get("payload_hash") or "")
    return (
        (
            f"HO-003 inputs_snapshot: {inputs_context.get('state') or 'missing'} | "
            f"payload_hash={input_hash[:12] or '—'} | "
            f"can_consume={bool(inputs_context.get('can_consume', False))}"
        ),
        str(inputs_context.get("banner") or "").strip(),
        f"HO-005 validated_suite_snapshot: {existing_state.get('state') or current_state.get('state') or 'missing'}",
        (
            f"suite_snapshot_hash={suite_hash[:12] or '—'} | "
            f"rows={int(preview.get('row_count', 0) or 0)} | "
            f"enabled={int(preview.get('enabled_count', 0) or 0)} | "
            f"missing_refs={int(validation.get('blocking_missing_ref_count', 0) or 0)} | "
            f"upstream_errors={int(validation.get('upstream_ref_error_count', 0) or 0)}"
        ),
        str(existing_state.get("banner") or current_state.get("banner") or "").strip(),
        f"validated_suite_snapshot.json: {handoff_path}",
    )


__all__ = [
    "DESKTOP_SUITE_OVERRIDES_FILENAME",
    "DESKTOP_SUITE_OVERRIDES_SCHEMA_VERSION",
    "build_desktop_suite_snapshot_context",
    "build_run_setup_suite_overrides",
    "desktop_inputs_snapshot_path",
    "desktop_suite_handoff_dir",
    "desktop_suite_handoff_path",
    "desktop_suite_overrides_path",
    "format_desktop_suite_status_lines",
    "load_default_suite_rows",
    "load_desktop_suite_overrides",
    "normalize_desktop_suite_overrides",
    "read_desktop_suite_handoff_state",
    "read_inputs_snapshot_context",
    "reset_desktop_suite_overrides",
    "resolve_ring_source_context",
    "save_desktop_suite_overrides",
    "write_desktop_suite_handoff_snapshot",
]
