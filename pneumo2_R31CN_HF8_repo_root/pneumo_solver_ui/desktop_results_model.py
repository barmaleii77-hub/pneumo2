from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_STATUS_LABELS: dict[str, str] = {
    "PASS": "норма",
    "FAIL": "ошибка",
    "WARN": "предупреждение",
    "READY": "готово",
    "MISSING": "нет данных",
    "BLOCKED": "заблокировано",
    "CRITICAL": "критично",
    "PARTIAL": "частично",
    "INFO": "справка",
    "CURRENT": "текущий",
    "HISTORICAL": "исторический",
    "STALE": "устарел",
    "UNKNOWN": "не определён",
}


def _status_label(value: object) -> str:
    raw = str(value or "").strip()
    return _STATUS_LABELS.get(raw.upper(), raw.lower() if raw else "нет данных")


def _bool_ru(value: bool | None) -> str:
    if value is None:
        return "нет данных"
    return "да" if bool(value) else "нет"


@dataclass(frozen=True)
class DesktopResultsArtifact:
    key: str
    title: str
    category: str
    path: Path
    detail: str = ""


@dataclass(frozen=True)
class DesktopResultsOverviewRow:
    key: str
    title: str
    status: str
    detail: str
    next_action: str = ""
    evidence_path: Path | None = None
    action_key: str = ""
    artifact_key: str = ""


@dataclass(frozen=True)
class DesktopResultsContextField:
    key: str
    title: str
    current_value: str = ""
    selected_value: str = ""
    status: str = "UNKNOWN"
    detail: str = ""


@dataclass(frozen=True)
class DesktopResultsSessionHandoff:
    summary: str = ""
    detail: str = ""
    step_lines: tuple[str, ...] = ()
    zip_path: Path | None = None
    autotest_run_dir: Path | None = None
    diagnostics_run_dir: Path | None = None


@dataclass(frozen=True)
class DesktopResultsSnapshot:
    latest_zip_path: Path | None
    latest_validation_json_path: Path | None
    latest_validation_md_path: Path | None
    latest_triage_json_path: Path | None
    latest_triage_md_path: Path | None
    latest_dashboard_html_path: Path | None
    latest_anim_diag_json_path: Path | None
    latest_npz_path: Path | None
    latest_pointer_json_path: Path | None
    latest_mnemo_event_log_path: Path | None
    latest_autotest_run_dir: Path | None
    latest_diagnostics_run_dir: Path | None
    validation_ok: bool | None
    validation_error_count: int
    validation_warning_count: int
    triage_critical_count: int
    triage_warn_count: int
    triage_info_count: int
    validation_errors: tuple[str, ...]
    validation_warnings: tuple[str, ...]
    triage_red_flags: tuple[str, ...]
    optimizer_scope_gate: str
    optimizer_scope_gate_reason: str
    optimizer_scope_release_risk: bool | None
    anim_summary_lines: tuple[str, ...]
    operator_recommendations: tuple[str, ...]
    mnemo_current_mode: str
    mnemo_recent_titles: tuple[str, ...]
    suggested_next_step: str
    suggested_next_detail: str
    validation_overview_rows: tuple[DesktopResultsOverviewRow, ...]
    recent_artifacts: tuple[DesktopResultsArtifact, ...]
    suggested_next_action_key: str = ""
    suggested_next_artifact_key: str = ""
    result_context_state: str = "UNKNOWN"
    result_context_banner: str = "Результаты расчёта пока не определены."
    result_context_detail: str = ""
    result_context_action: str = ""
    result_context_fields: tuple[DesktopResultsContextField, ...] = ()
    diagnostics_evidence_manifest_path: Path | None = None
    diagnostics_evidence_manifest_hash: str = ""
    diagnostics_evidence_manifest_status: str = "MISSING"
    latest_capture_export_manifest_path: Path | None = None
    latest_capture_export_manifest_status: str = "MISSING"
    latest_capture_export_manifest_handoff_id: str = ""
    latest_capture_hash: str = ""
    latest_optimizer_pointer_json_path: Path | None = None
    latest_optimizer_run_dir: Path | None = None
    selected_run_contract_path: Path | None = None
    selected_run_contract_hash: str = ""
    selected_run_contract_status: str = "MISSING"
    selected_run_contract_banner: str = "Данные выбранного оптимизационного прогона пока недоступны."


def format_validation_summary(snapshot: DesktopResultsSnapshot) -> str:
    if snapshot.validation_ok is None:
        return "Проверка: свежий отчёт пока не найден."
    status = "Норма" if snapshot.validation_ok else "Ошибка"
    return (
        f"Проверка: {status}; "
        f"ошибок: {int(snapshot.validation_error_count)}; "
        f"предупреждений: {int(snapshot.validation_warning_count)}"
    )


def format_optimizer_gate_summary(snapshot: DesktopResultsSnapshot) -> str:
    gate = str(snapshot.optimizer_scope_gate or "").strip() or "нет данных"
    risk = snapshot.optimizer_scope_release_risk
    if risk is None:
        return f"Оптимизация: {_status_label(gate)}"
    return f"Оптимизация: {_status_label(gate)}; риск для передачи: {_bool_ru(risk)}"


def format_triage_summary(snapshot: DesktopResultsSnapshot) -> str:
    return (
        "Разбор замечаний: "
        f"критичных: {int(snapshot.triage_critical_count)}; "
        f"предупреждений: {int(snapshot.triage_warn_count)}; "
        f"справочных: {int(snapshot.triage_info_count)}; "
        f"красных флагов: {len(snapshot.triage_red_flags)}"
    )


def format_npz_summary(snapshot: DesktopResultsSnapshot) -> str:
    if snapshot.latest_npz_path is None:
        return "Последний файл анимации: пока недоступен."
    return f"Последний файл анимации: {snapshot.latest_npz_path.name}"


def format_recent_runs_summary(snapshot: DesktopResultsSnapshot) -> str:
    autotest = snapshot.latest_autotest_run_dir.name if snapshot.latest_autotest_run_dir else "—"
    diagnostics = snapshot.latest_diagnostics_run_dir.name if snapshot.latest_diagnostics_run_dir else "—"
    return f"Последние прогоны: автотест: {autotest}; диагностика: {diagnostics}"


def format_result_context_summary(snapshot: DesktopResultsSnapshot) -> str:
    state = str(snapshot.result_context_state or "UNKNOWN").upper()
    labels = {
        "CURRENT": "актуальны",
        "HISTORICAL": "исторические",
        "STALE": "устарели",
        "MISSING": "нет данных",
        "UNKNOWN": "не определены",
    }
    return f"Результаты расчёта: {labels.get(state, state.lower())}"


__all__ = [
    "DesktopResultsArtifact",
    "DesktopResultsContextField",
    "DesktopResultsOverviewRow",
    "DesktopResultsSessionHandoff",
    "DesktopResultsSnapshot",
    "format_npz_summary",
    "format_optimizer_gate_summary",
    "format_recent_runs_summary",
    "format_result_context_summary",
    "format_triage_summary",
    "format_validation_summary",
]
