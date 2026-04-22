from __future__ import annotations

"""Native WS-BASELINE launch request preparation and execution bookkeeping.

The PySide shell owns the QProcess lifecycle, while this module owns the
machine-readable request, log and review-candidate artifacts.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from pneumo_solver_ui.desktop_input_model import (
    load_desktop_inputs_snapshot,
    save_base_payload,
)
from pneumo_solver_ui.desktop_run_setup_runtime import stable_run_hash
from pneumo_solver_ui.desktop_suite_snapshot import VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION
from pneumo_solver_ui.optimization_baseline_source import (
    append_baseline_history_item,
    baseline_suite_handoff_launch_gate,
    baseline_suite_handoff_snapshot_path,
    baseline_history_item_from_contract,
    build_active_baseline_contract,
)
from pneumo_solver_ui.workspace_contract import resolve_effective_workspace_dir


BASELINE_RUN_LAUNCH_REQUEST_SCHEMA_VERSION = "baseline_run_launch_request_v1"
BASELINE_RUN_LAUNCH_REQUEST_FILENAME = "baseline_run_launch_request.json"
BASELINE_RUN_PREPARED_INPUTS_FILENAME = "baseline_run_inputs.json"
BASELINE_RUN_PREPARED_SUITE_FILENAME = "baseline_run_suite.json"
WS_BASELINE_HANDOFF_ID = "HO-006"
DESKTOP_SINGLE_RUN_MODULE = "pneumo_solver_ui.tools.desktop_single_run"


def _repo_root(repo_root: Path | str | None = None) -> Path:
    return Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]


def _workspace_dir(root: Path, workspace_dir: Path | str | None = None) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir).expanduser().resolve()
    return resolve_effective_workspace_dir(root)


def baseline_run_handoff_dir(
    *,
    repo_root: Path | str | None = None,
    workspace_dir: Path | str | None = None,
) -> Path:
    root = _repo_root(repo_root)
    workspace = _workspace_dir(root, workspace_dir)
    return (workspace / "handoffs" / "WS-BASELINE").resolve()


def baseline_run_launch_request_path(
    *,
    repo_root: Path | str | None = None,
    workspace_dir: Path | str | None = None,
) -> Path:
    return (baseline_run_handoff_dir(repo_root=repo_root, workspace_dir=workspace_dir) / BASELINE_RUN_LAUNCH_REQUEST_FILENAME).resolve()


def read_baseline_run_launch_request(
    *,
    repo_root: Path | str | None = None,
    workspace_dir: Path | str | None = None,
) -> dict[str, Any]:
    path = baseline_run_launch_request_path(repo_root=repo_root, workspace_dir=workspace_dir)
    if not path.exists():
        return {}
    return _read_json_object(path)


def _utc_now_label() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _read_json_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"JSON object expected: {path}")
    return raw


def _resolve_ref_path(
    raw: Any,
    *,
    repo_root: Path,
    workspace_dir: Path,
) -> Path:
    text = str(raw or "").strip()
    if not text:
        return Path("")
    path = Path(text).expanduser()
    if path.is_absolute():
        return path.resolve()
    candidates = (
        workspace_dir / path,
        repo_root / path,
        repo_root / "pneumo_solver_ui" / path,
        Path.cwd() / path,
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return candidates[0].resolve()


def _row_enabled(row: Mapping[str, Any]) -> bool:
    value = row.get("включен", row.get("enabled", row.get("включено", True)))
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"0", "false", "no", "off", "нет"}:
            return False
        if lowered in {"1", "true", "yes", "on", "да"}:
            return True
    return bool(value)


def _row_name(row: Mapping[str, Any], index: int) -> str:
    for key in ("имя", "name", "id", "title"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return f"row_{index + 1}"


def _selected_suite_row(rows: list[dict[str, Any]]) -> tuple[int, dict[str, Any] | None]:
    for index, row in enumerate(rows):
        if _row_enabled(row):
            return index, row
    if rows:
        return 0, rows[0]
    return -1, None


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _safe_cache_policy(value: Any) -> str:
    policy = str(value or "reuse").strip().lower() or "reuse"
    return policy if policy in {"reuse", "refresh", "off"} else "reuse"


def _write_json(path: Path, payload: Any) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _load_request_payload(request: Mapping[str, Any] | Path | str) -> dict[str, Any]:
    if isinstance(request, Mapping):
        return dict(request)
    return _read_json_object(Path(request).expanduser().resolve())


def _request_path(request: Mapping[str, Any] | Path | str) -> Path:
    if isinstance(request, Mapping):
        raw = str(dict(request.get("paths") or {}).get("request") or "").strip()
        if raw:
            return Path(raw).expanduser().resolve()
    return Path(request).expanduser().resolve()


def _request_workspace_path(request: Mapping[str, Any]) -> Path | None:
    raw = str(dict(request.get("paths") or {}).get("workspace") or "").strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except Exception:
        return None


def _request_log_path(request: Mapping[str, Any]) -> Path:
    raw = str(dict(request.get("paths") or {}).get("log") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _request_path(request).with_suffix(".log")


def append_baseline_run_execution_log(
    request: Mapping[str, Any] | Path | str,
    text: str,
) -> Path:
    payload = _load_request_payload(request)
    target = _request_log_path(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(str(text or ""))
    return target


def mark_baseline_run_launch_request_started(
    request: Mapping[str, Any] | Path | str,
) -> dict[str, Any]:
    payload = _load_request_payload(request)
    now = _utc_now_label()
    payload["execution_status"] = "running"
    payload["started_at_utc"] = now
    payload["finished_at_utc"] = ""
    payload["returncode"] = None
    payload["process_log_path"] = str(_request_log_path(payload))
    _write_json(_request_path(payload), payload)
    append_baseline_run_execution_log(payload, f"[{now}] Запуск базового прогона начат.\n")
    return payload


def complete_baseline_run_launch_request(
    request: Mapping[str, Any] | Path | str,
    *,
    returncode: int,
    stdout_tail: str = "",
    stderr_tail: str = "",
    actor: str = "desktop_spec_shell",
) -> dict[str, Any]:
    payload = _load_request_payload(request)
    paths = dict(payload.get("paths") or {})
    request_path = _request_path(payload)
    workspace_dir = _request_workspace_path(payload)
    run_dir = Path(str(paths.get("run_dir") or "")).expanduser().resolve()
    suite_path = Path(str(paths.get("suite_snapshot") or "")).expanduser().resolve()
    summary_path = run_dir / "run_summary.json"
    now = _utc_now_label()
    ok = int(returncode) == 0

    payload["execution_status"] = "done" if ok else "failed"
    payload["finished_at_utc"] = now
    payload["returncode"] = int(returncode)
    payload["run_summary_path"] = str(summary_path) if summary_path.exists() else ""
    if stdout_tail:
        payload["stdout_tail"] = str(stdout_tail)[-4000:]
    if stderr_tail:
        payload["stderr_tail"] = str(stderr_tail)[-4000:]

    append_baseline_run_execution_log(
        payload,
        f"\n[{now}] Запуск завершён с кодом {int(returncode)}.\n",
    )

    if ok and summary_path.exists() and suite_path.exists():
        try:
            suite_snapshot = _read_json_object(suite_path)
            run_summary = _read_json_object(summary_path)
            baseline_meta = {
                "problem_hash": str(
                    run_summary.get("problem_hash")
                    or run_summary.get("cache_key")
                    or payload.get("request_id")
                    or ""
                ),
                "request_id": str(payload.get("request_id") or ""),
                "run_profile": str(run_summary.get("run_profile") or dict(payload.get("run_setup") or {}).get("launch_profile") or ""),
                "command_module": str(payload.get("command_module") or DESKTOP_SINGLE_RUN_MODULE),
            }
            contract = build_active_baseline_contract(
                suite_snapshot=suite_snapshot,
                baseline_path=summary_path,
                baseline_payload=run_summary,
                baseline_score_payload={
                    "ok": bool(run_summary.get("ok", True)),
                    "scenario_name": str(run_summary.get("scenario_name") or ""),
                    "dt_s": run_summary.get("dt_s"),
                    "t_end_s": run_summary.get("t_end_s"),
                },
                baseline_meta=baseline_meta,
                source_run_dir=run_dir,
                policy_mode="review_adopt",
                action="review",
                note="Native baseline run finished; explicit review/adopt is required.",
            )
            history_item = baseline_history_item_from_contract(
                contract,
                action="review",
                actor=actor,
                note="Native baseline run finished; explicit review/adopt is required.",
            )
            history_path = append_baseline_history_item(
                history_item,
                workspace_dir=workspace_dir,
            )
            payload["baseline_candidate"] = {
                "history_id": str(contract.get("history_id") or ""),
                "active_baseline_hash": str(contract.get("active_baseline_hash") or ""),
                "history_path": str(history_path),
                "requires_explicit_adopt": True,
            }
        except Exception as exc:
            payload["baseline_candidate_error"] = str(exc)

    _write_json(request_path, payload)
    return payload


def _build_desktop_single_run_command(
    *,
    python_executable: str,
    params_path: Path,
    suite_path: Path,
    selected_index: int,
    run_setup: Mapping[str, Any],
    run_dir: Path,
) -> list[str]:
    run_profile = str(run_setup.get("launch_profile") or "detail").strip() or "detail"
    cmd = [
        str(python_executable),
        "-m",
        DESKTOP_SINGLE_RUN_MODULE,
        "--params",
        str(params_path),
        "--test",
        str(suite_path),
        "--test_index",
        str(max(0, int(selected_index))),
        "--dt",
        str(_safe_float(run_setup.get("run_dt"), 0.003)),
        "--t_end",
        str(_safe_float(run_setup.get("run_t_end"), 1.6)),
        "--outdir",
        str(run_dir),
        "--cache_policy",
        _safe_cache_policy(run_setup.get("cache_policy")),
        "--run_profile",
        run_profile,
    ]
    if bool(run_setup.get("record_full", False)):
        cmd.append("--record_full")
    if bool(run_setup.get("export_npz", False)):
        cmd.append("--export_npz")
    if not bool(run_setup.get("export_csv", True)):
        cmd.append("--no_export_csv")
    return cmd


def prepare_baseline_run_launch_request(
    run_setup: Mapping[str, Any] | None = None,
    *,
    repo_root: Path | str | None = None,
    workspace_dir: Path | str | None = None,
    python_executable: str | None = None,
    checked: bool = False,
) -> dict[str, Any]:
    """Prepare a machine-readable WS-BASELINE request without launching it."""

    root = _repo_root(repo_root)
    workspace = _workspace_dir(root, workspace_dir)
    snapshot = dict(run_setup or {})
    launch_profile = str(snapshot.get("launch_profile") or "detail").strip() or "detail"
    runtime_policy = str(snapshot.get("runtime_policy") or "balanced").strip() or "balanced"
    request_dir = baseline_run_handoff_dir(repo_root=root, workspace_dir=workspace)
    request_path = request_dir / BASELINE_RUN_LAUNCH_REQUEST_FILENAME
    suite_path = baseline_suite_handoff_snapshot_path(repo_root=root, workspace_dir=workspace)
    created_at = _utc_now_label()
    request_id = f"baseline_run_{_stamp()}_{stable_run_hash({'run_setup': snapshot, 'suite_path': str(suite_path)})[:8]}"

    gate = baseline_suite_handoff_launch_gate(
        launch_profile=launch_profile,
        runtime_policy=runtime_policy,
        repo_root=root,
        workspace_dir=workspace,
    )
    blockers: list[str] = []
    suite_snapshot: dict[str, Any] = {}
    suite_rows: list[dict[str, Any]] = []
    inputs_snapshot: dict[str, Any] = {}
    inputs_path: Path | None = None

    if not suite_path.exists():
        blockers.append("нет зафиксированного набора испытаний")
    else:
        try:
            suite_snapshot = _read_json_object(suite_path)
            if str(suite_snapshot.get("schema_version") or "") != VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION:
                blockers.append("снимок набора имеет неподдерживаемую версию")
            if not bool(suite_snapshot.get("validated", False)):
                blockers.append("снимок набора не прошёл проверку")
            raw_rows = suite_snapshot.get("suite_rows")
            if not isinstance(raw_rows, list) or not raw_rows:
                blockers.append("в снимке набора нет строк испытаний")
            else:
                suite_rows = [dict(item) for item in raw_rows if isinstance(item, Mapping)]
                if not suite_rows:
                    blockers.append("в снимке набора нет пригодных строк испытаний")
        except Exception as exc:
            blockers.append(f"снимок набора не читается: {exc}")

    upstream_refs = dict(suite_snapshot.get("upstream_refs") or {})
    inputs_ref = dict(upstream_refs.get("inputs") or {})
    raw_inputs_path = str(inputs_ref.get("snapshot_ref") or "").strip()
    if not raw_inputs_path:
        blockers.append("нет ссылки на зафиксированные исходные данные")
    else:
        inputs_path = _resolve_ref_path(raw_inputs_path, repo_root=root, workspace_dir=workspace)
        if not inputs_path.exists():
            blockers.append("зафиксированные исходные данные не найдены")
        else:
            try:
                inputs_snapshot = load_desktop_inputs_snapshot(inputs_path)
            except Exception as exc:
                blockers.append(f"зафиксированные исходные данные не читаются: {exc}")

    selected_index, selected_row = _selected_suite_row(suite_rows)
    if selected_row is None:
        blockers.append("нет выбранного испытания для запуска")

    prepared_inputs_path = request_dir / BASELINE_RUN_PREPARED_INPUTS_FILENAME
    prepared_suite_path = request_dir / BASELINE_RUN_PREPARED_SUITE_FILENAME
    run_dir = (workspace / "desktop_runs" / request_id).resolve()
    log_path = (request_dir / "logs" / f"{request_id}.log").resolve()
    execution_ready = not blockers and bool(inputs_snapshot) and bool(suite_rows) and selected_row is not None

    command: list[str] = []
    if execution_ready:
        save_base_payload(prepared_inputs_path, dict(inputs_snapshot.get("inputs") or {}))
        _write_json(prepared_suite_path, suite_rows)
        command = _build_desktop_single_run_command(
            python_executable=str(python_executable or sys.executable),
            params_path=prepared_inputs_path,
            suite_path=prepared_suite_path,
            selected_index=selected_index,
            run_setup=snapshot,
            run_dir=run_dir,
        )

    payload: dict[str, Any] = {
        "schema_version": BASELINE_RUN_LAUNCH_REQUEST_SCHEMA_VERSION,
        "source_workspace": "WS-BASELINE",
        "handoff_id": WS_BASELINE_HANDOFF_ID,
        "created_at_utc": created_at,
        "request_id": request_id,
        "checked": bool(checked),
        "execution_ready": bool(execution_ready),
        "operator_blockers": blockers,
        "command_module": DESKTOP_SINGLE_RUN_MODULE,
        "command": command,
        "run_setup": snapshot,
        "gate": gate,
        "selected_test": {
            "index": selected_index,
            "name": _row_name(selected_row, selected_index) if selected_row is not None else "",
        },
        "paths": {
            "request": str(request_path),
            "workspace": str(workspace),
            "suite_snapshot": str(suite_path),
            "inputs_snapshot": str(inputs_path) if inputs_path is not None else "",
            "prepared_inputs": str(prepared_inputs_path) if execution_ready else "",
            "prepared_suite": str(prepared_suite_path) if execution_ready else "",
            "run_dir": str(run_dir) if execution_ready else "",
            "log": str(log_path),
        },
    }
    _write_json(request_path, payload)
    return payload


__all__ = [
    "BASELINE_RUN_LAUNCH_REQUEST_FILENAME",
    "BASELINE_RUN_LAUNCH_REQUEST_SCHEMA_VERSION",
    "BASELINE_RUN_PREPARED_INPUTS_FILENAME",
    "BASELINE_RUN_PREPARED_SUITE_FILENAME",
    "DESKTOP_SINGLE_RUN_MODULE",
    "WS_BASELINE_HANDOFF_ID",
    "append_baseline_run_execution_log",
    "baseline_run_handoff_dir",
    "baseline_run_launch_request_path",
    "complete_baseline_run_launch_request",
    "mark_baseline_run_launch_request_started",
    "prepare_baseline_run_launch_request",
    "read_baseline_run_launch_request",
]
