from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pneumo_solver_ui.desktop_results_model import (
    DesktopResultsArtifact,
    DesktopResultsOverviewRow,
    DesktopResultsSessionHandoff,
    DesktopResultsSnapshot,
)
from pneumo_solver_ui.desktop_shell.external_launch import (
    python_gui_exe,
    spawn_module,
    track_spawned_process,
)
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary
from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_DIAG_SIDECAR_JSON,
    build_anim_operator_recommendations,
    format_anim_dashboard_brief_lines,
    load_latest_send_bundle_anim_dashboard,
)


def _safe_read_json_dict(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _safe_read_json_any(path: Path | None) -> Any:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _existing_path(raw: Any) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        path = Path(text).expanduser().resolve()
    except Exception:
        path = Path(text).expanduser()
    return path if path.exists() else None


def _latest_child_dir(root: Path) -> Path | None:
    if not root.exists() or not root.is_dir():
        return None
    dirs = [item for item in root.iterdir() if item.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda item: item.stat().st_mtime)


def _latest_send_bundle_zip(out_dir: Path) -> Path | None:
    latest_txt = out_dir / "latest_send_bundle_path.txt"
    if latest_txt.exists():
        try:
            pointed = Path(
                latest_txt.read_text(encoding="utf-8", errors="replace").strip()
            ).expanduser().resolve()
            if pointed.exists():
                return pointed
        except Exception:
            pass
    latest_zip = out_dir / "latest_send_bundle.zip"
    if latest_zip.exists():
        return latest_zip.resolve()
    zips = [item for item in out_dir.glob("*.zip") if item.is_file()]
    if not zips:
        return None
    return max(zips, key=lambda item: item.stat().st_mtime).resolve()


def _append_artifact(
    items: list[DesktopResultsArtifact],
    *,
    key: str,
    title: str,
    category: str,
    path: Path | None,
    detail: str = "",
) -> None:
    if path is None or not path.exists():
        return
    items.append(
        DesktopResultsArtifact(
            key=key,
            title=title,
            category=category,
            path=path.resolve(),
            detail=detail,
        )
    )


def _validation_status(
    *,
    ok: bool | None,
    error_count: int,
    warning_count: int,
) -> str:
    if ok is None:
        return "MISSING"
    if not ok or error_count > 0:
        return "FAIL"
    if warning_count > 0:
        return "WARN"
    return "PASS"


def _triage_status(
    *,
    has_report: bool,
    critical_count: int,
    warn_count: int,
    red_flag_count: int,
) -> str:
    if not has_report:
        return "MISSING"
    if critical_count > 0:
        return "CRITICAL"
    if warn_count > 0 or red_flag_count > 0:
        return "WARN"
    return "READY"


def _short_text(text: Any, *, limit: int = 220) -> str:
    raw = " ".join(str(text or "").split())
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 1)].rstrip() + "..."


def _same_suffix(path: Path, suffix: str) -> bool:
    return path.suffix.lower() == str(suffix).lower()


def _candidate_npz_for_pointer(path: Path) -> Path | None:
    if not _same_suffix(path, ".json"):
        return None
    if path.name.endswith(".desktop_mnemo_events.json"):
        base_name = path.name[: -len(".desktop_mnemo_events.json")] + ".npz"
        candidate = path.with_name(base_name)
        return candidate if candidate.exists() else None
    candidate = path.with_suffix(".npz")
    return candidate if candidate.exists() else None


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _dedupe_text_items(items: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return tuple(out)


def _suggested_next_step(
    *,
    validation_status: str,
    validation_errors: tuple[str, ...],
    validation_warnings: tuple[str, ...],
    triage_status: str,
    triage_red_flags: tuple[str, ...],
    triage_recommendations: tuple[str, ...],
    optimizer_scope_gate: str,
    optimizer_scope_gate_reason: str,
    anim_recommendations: tuple[str, ...],
    latest_npz_path: Path | None,
    latest_pointer_json_path: Path | None,
    latest_zip_path: Path | None,
) -> tuple[str, str, str, str]:
    gate = str(optimizer_scope_gate or "").strip().upper()
    gate_reason = str(optimizer_scope_gate_reason or "").strip()

    if validation_status == "FAIL":
        detail = validation_errors[0] if validation_errors else gate_reason or "Validation reported blocking errors."
        return (
            "Сначала разберите отчёт проверки, потом переходите дальше.",
            detail,
            "open_artifact",
            "validation_json",
        )

    if triage_status == "CRITICAL":
        action = (
            triage_recommendations[0]
            if triage_recommendations
            else (
                "Open Desktop Animator follow and inspect the latest critical event flow."
                if latest_pointer_json_path is not None
                else "Open Compare Viewer on the latest NPZ and inspect the critical result."
            )
        )
        detail = triage_red_flags[0] if triage_red_flags else "Triage report marked critical findings."
        if latest_pointer_json_path is not None:
            return action, detail, "open_animator_follow", "latest_pointer"
        if latest_npz_path is not None:
            return action, detail, "open_compare_viewer", "latest_npz"
        return action, detail, "open_artifact", "triage_json"

    if gate and gate not in {"PASS", "OK", "READY"}:
        return (
            "Перед отправкой проверьте шлюз оптимизации.",
            gate_reason or f"release_gate={gate}",
            "open_artifact",
            "validation_json",
        )

    if validation_status == "WARN":
        detail = validation_warnings[0] if validation_warnings else "Validation emitted warnings that need operator review."
        return (
            "Сначала проверьте предупреждения, затем переходите к сравнению или визуализации.",
            detail,
            "open_artifact",
            "validation_json",
        )

    if triage_status == "WARN":
        action = (
            triage_recommendations[0]
            if triage_recommendations
            else "Review triage warnings before closing validation."
        )
        detail = triage_red_flags[0] if triage_red_flags else "Triage report contains warnings/red flags."
        return action, detail, "open_artifact", "triage_json"

    if triage_recommendations:
        return (
            triage_recommendations[0],
            "Latest triage report suggests this as the next operator check.",
            "open_artifact",
            "triage_json",
        )

    if anim_recommendations:
        if latest_pointer_json_path is not None:
            return (
                anim_recommendations[0],
                "Диагностика визуализации рекомендует именно этот следующий шаг.",
                "open_animator_follow",
                "latest_pointer",
            )
        if latest_npz_path is not None:
            return (
                anim_recommendations[0],
                "Диагностика визуализации рекомендует именно этот следующий шаг.",
                "open_compare_viewer",
                "latest_npz",
            )
        return (
            anim_recommendations[0],
            "Диагностика визуализации рекомендует именно этот следующий шаг.",
            "open_artifact",
            "anim_diag_json",
        )

    if latest_npz_path is not None:
        return (
            "Откройте сравнение по последнему NPZ.",
            latest_npz_path.name,
            "open_compare_viewer",
            "latest_npz",
        )

    if latest_pointer_json_path is not None:
        return (
            "Откройте аниматор в режиме сопровождения.",
            latest_pointer_json_path.name,
            "open_animator_follow",
            "latest_pointer",
        )

    if latest_zip_path is not None:
        return (
            "Откройте центр отправки и проверьте свежие материалы пакета.",
            latest_zip_path.name,
            "open_send_center",
            "send_bundle_zip",
        )

    return (
        "Сначала запустите диагностику или соберите пакет отправки.",
        "Свежие артефакты проверки и результатов пока не появились.",
        "open_diagnostics_gui",
        "",
    )


class DesktopResultsRuntime:
    def __init__(self, *, repo_root: Path, python_executable: str) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_executable = str(python_executable)
        self.send_bundles_dir = self.repo_root / "send_bundles"
        self.autotest_runs_dir = self.repo_root / "pneumo_solver_ui" / "autotest_runs"
        self.diagnostics_runs_dir = self.repo_root / "diagnostics_runs"

    def snapshot(self) -> DesktopResultsSnapshot:
        out_dir = self.send_bundles_dir
        validation_json_path = _existing_path(out_dir / "latest_send_bundle_validation.json")
        validation_md_path = _existing_path(out_dir / "latest_send_bundle_validation.md")
        triage_json_path = _existing_path(out_dir / "latest_triage_report.json")
        triage_md_path = _existing_path(out_dir / "latest_triage_report.md")
        dashboard_html_path = _existing_path(out_dir / "latest_dashboard.html")
        anim_diag_json_path = _existing_path(out_dir / ANIM_DIAG_SIDECAR_JSON)
        latest_zip_path = _latest_send_bundle_zip(out_dir) if out_dir.exists() else None

        validation_payload = _safe_read_json_dict(validation_json_path)
        triage_payload = _safe_read_json_dict(triage_json_path)
        optimizer_scope_gate = dict(validation_payload.get("optimizer_scope_gate") or {})

        anim_dashboard = dict(load_latest_send_bundle_anim_dashboard(out_dir) or {})
        anim_summary_lines = tuple(
            str(line) for line in format_anim_dashboard_brief_lines(anim_dashboard)
        )
        anim_operator_recommendations = tuple(
            str(line)
            for line in build_anim_operator_recommendations(anim_dashboard)
            if str(line).strip()
        )
        triage_operator_recommendations = tuple(
            str(line)
            for line in (triage_payload.get("operator_recommendations") or [])
            if str(line).strip()
        )
        operator_recommendations = _dedupe_text_items(
            list(triage_operator_recommendations) + list(anim_operator_recommendations)
        )

        anim_diag = dict(collect_anim_latest_diagnostics_summary(include_meta=True) or {})
        latest_npz_path = _existing_path(anim_diag.get("anim_latest_npz_path"))
        latest_pointer_json_path = _existing_path(anim_diag.get("anim_latest_pointer_json"))
        latest_mnemo_event_log_path = _existing_path(
            anim_diag.get("anim_latest_mnemo_event_log_path")
        )

        latest_autotest_run_dir = _latest_child_dir(self.autotest_runs_dir)
        latest_diagnostics_run_dir = _latest_child_dir(self.diagnostics_runs_dir)

        items: list[DesktopResultsArtifact] = []
        _append_artifact(items, key="send_bundle_zip", title="Последний ZIP пакета отправки", category="bundle", path=latest_zip_path)
        _append_artifact(items, key="validation_json", title="Проверка в JSON", category="validation", path=validation_json_path)
        _append_artifact(items, key="validation_md", title="Проверка в Markdown", category="validation", path=validation_md_path)
        _append_artifact(items, key="triage_json", title="Разбор замечаний в JSON", category="triage", path=triage_json_path)
        _append_artifact(items, key="triage_md", title="Разбор замечаний в Markdown", category="triage", path=triage_md_path)
        _append_artifact(items, key="dashboard_html", title="Сводная HTML-страница", category="results", path=dashboard_html_path)
        _append_artifact(items, key="anim_diag_json", title="Диагностика визуализации в JSON", category="anim_latest", path=anim_diag_json_path)
        _append_artifact(items, key="latest_npz", title="Последний NPZ анимации", category="results", path=latest_npz_path)
        _append_artifact(items, key="latest_pointer", title="Последний указатель анимации", category="results", path=latest_pointer_json_path)
        _append_artifact(items, key="mnemo_event_log", title="Журнал событий мнемосхемы", category="results", path=latest_mnemo_event_log_path)
        _append_artifact(items, key="autotest_run", title="Последний каталог автотеста", category="runs", path=latest_autotest_run_dir)
        _append_artifact(items, key="diagnostics_run", title="Последний каталог диагностики", category="runs", path=latest_diagnostics_run_dir)

        validation_status = _validation_status(
            ok=validation_payload.get("ok")
            if isinstance(validation_payload.get("ok"), bool)
            else None,
            error_count=len(validation_payload.get("errors") or []),
            warning_count=len(validation_payload.get("warnings") or []),
        )
        triage_severity = dict(triage_payload.get("severity_counts") or {})
        triage_critical_count = _to_int(triage_severity.get("critical"))
        triage_warn_count = _to_int(triage_severity.get("warn"))
        triage_info_count = _to_int(triage_severity.get("info"))
        triage_red_flags = tuple(
            str(item)
            for item in (triage_payload.get("red_flags") or [])
            if str(item).strip()
        )
        triage_status = _triage_status(
            has_report=triage_json_path is not None or triage_md_path is not None,
            critical_count=triage_critical_count,
            warn_count=triage_warn_count,
            red_flag_count=len(triage_red_flags),
        )
        validation_errors = tuple(
            str(item)
            for item in (validation_payload.get("errors") or [])
            if str(item).strip()
        )
        validation_warnings = tuple(
            str(item)
            for item in (validation_payload.get("warnings") or [])
            if str(item).strip()
        )
        (
            suggested_next_step,
            suggested_next_detail,
            suggested_next_action_key,
            suggested_next_artifact_key,
        ) = _suggested_next_step(
            validation_status=validation_status,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            triage_status=triage_status,
            triage_red_flags=triage_red_flags,
            triage_recommendations=triage_operator_recommendations,
            optimizer_scope_gate=str(optimizer_scope_gate.get("release_gate") or ""),
            optimizer_scope_gate_reason=str(
                optimizer_scope_gate.get("release_gate_reason") or ""
            ),
            anim_recommendations=anim_operator_recommendations,
            latest_npz_path=latest_npz_path,
            latest_pointer_json_path=latest_pointer_json_path,
            latest_zip_path=latest_zip_path,
        )
        overview_rows: list[DesktopResultsOverviewRow] = [
            DesktopResultsOverviewRow(
                key="send_bundle_validation",
                title="Проверка пакета отправки",
                status=validation_status,
                detail=(
                    f"errors={len(validation_payload.get('errors') or [])} | "
                    f"warnings={len(validation_payload.get('warnings') or [])}"
                ),
                next_action="Открыть отчёт проверки" if validation_json_path is not None else "Сначала запустить диагностику",
                evidence_path=validation_json_path or validation_md_path,
                action_key="open_artifact",
                artifact_key="validation_json" if validation_json_path is not None else "validation_md",
            ),
            DesktopResultsOverviewRow(
                key="triage_report",
                title="Разбор замечаний",
                status=triage_status,
                detail=(
                    f"critical={triage_critical_count} | "
                    f"warn={triage_warn_count} | "
                    f"info={triage_info_count} | "
                    f"red_flags={len(triage_red_flags)}"
                ),
                next_action=(
                    triage_operator_recommendations[0]
                    if triage_operator_recommendations
                    else (
                        "Inspect red flags"
                        if triage_red_flags
                        else "Open triage report"
                    )
                )
                if triage_json_path is not None or triage_md_path is not None
                else "Generate triage report",
                evidence_path=triage_json_path or triage_md_path,
                action_key="open_artifact" if triage_json_path is not None or triage_md_path is not None else "open_diagnostics_gui",
                artifact_key="triage_json" if triage_json_path is not None else "triage_md",
            ),
            DesktopResultsOverviewRow(
                key="optimizer_scope_gate",
                title="Шлюз области оптимизации",
                status=str(optimizer_scope_gate.get("release_gate") or "n/a"),
                detail=str(optimizer_scope_gate.get("release_gate_reason") or "No optimizer scope gate in latest validation."),
                next_action="Проверить предупреждения" if validation_json_path is not None else "",
                evidence_path=validation_json_path,
                action_key="open_artifact",
                artifact_key="validation_json" if validation_json_path is not None else "validation_md",
            ),
            DesktopResultsOverviewRow(
                key="anim_latest_results",
                title="Последний результат анимации",
                status="READY" if latest_npz_path is not None else "MISSING",
                detail=str(latest_npz_path.name if latest_npz_path is not None else "anim_latest NPZ is not available."),
                next_action="Открыть сравнение" if latest_npz_path is not None else "Запустить автотест или диагностику",
                evidence_path=latest_npz_path,
                action_key="open_compare_viewer" if latest_npz_path is not None else "open_diagnostics_gui",
                artifact_key="latest_npz",
            ),
            DesktopResultsOverviewRow(
                key="animator_pointer",
                title="Указатель аниматора",
                status="READY" if latest_pointer_json_path is not None else "MISSING",
                detail=str(
                    latest_pointer_json_path.name
                    if latest_pointer_json_path is not None
                    else "anim_latest pointer is not available."
                ),
                next_action="Открыть аниматор" if latest_pointer_json_path is not None else "Сформировать указатель anim_latest",
                evidence_path=latest_pointer_json_path,
                action_key="open_animator_follow" if latest_pointer_json_path is not None else "open_diagnostics_gui",
                artifact_key="latest_pointer",
            ),
            DesktopResultsOverviewRow(
                key="mnemo_event_log",
                title="Журнал событий мнемосхемы",
                status="READY" if latest_mnemo_event_log_path is not None else "MISSING",
                detail=str(
                    latest_mnemo_event_log_path.name
                    if latest_mnemo_event_log_path is not None
                    else "Event log not found for latest result."
                ),
                next_action="Посмотреть свежие события" if latest_mnemo_event_log_path is not None else "Открыть мнемосхему и выгрузить журнал",
                evidence_path=latest_mnemo_event_log_path,
                action_key="open_artifact" if latest_mnemo_event_log_path is not None else "open_diagnostics_gui",
                artifact_key="mnemo_event_log",
            ),
            DesktopResultsOverviewRow(
                key="bundle_sidecars",
                title="Материалы пакета",
                status=(
                    "READY"
                    if latest_zip_path is not None and triage_md_path is not None and dashboard_html_path is not None
                    else "PARTIAL"
                ),
                detail=(
                    f"zip={'yes' if latest_zip_path is not None else 'no'} | "
                    f"triage={'yes' if triage_md_path is not None else 'no'} | "
                    f"dashboard={'yes' if dashboard_html_path is not None else 'no'}"
                ),
                next_action="Открыть центр отправки" if latest_zip_path is not None else "Собрать пакет отправки",
                evidence_path=latest_zip_path or triage_md_path or dashboard_html_path,
                action_key="open_send_center" if latest_zip_path is not None else "open_send_bundles",
                artifact_key=(
                    "send_bundle_zip"
                    if latest_zip_path is not None
                    else ("triage_md" if triage_md_path is not None else "dashboard_html")
                ),
            ),
        ]

        return DesktopResultsSnapshot(
            latest_zip_path=latest_zip_path,
            latest_validation_json_path=validation_json_path,
            latest_validation_md_path=validation_md_path,
            latest_triage_json_path=triage_json_path,
            latest_triage_md_path=triage_md_path,
            latest_dashboard_html_path=dashboard_html_path,
            latest_anim_diag_json_path=anim_diag_json_path,
            latest_npz_path=latest_npz_path,
            latest_pointer_json_path=latest_pointer_json_path,
            latest_mnemo_event_log_path=latest_mnemo_event_log_path,
            latest_autotest_run_dir=latest_autotest_run_dir,
            latest_diagnostics_run_dir=latest_diagnostics_run_dir,
            validation_ok=validation_payload.get("ok")
            if isinstance(validation_payload.get("ok"), bool)
            else None,
            validation_error_count=len(validation_payload.get("errors") or []),
            validation_warning_count=len(validation_payload.get("warnings") or []),
            triage_critical_count=triage_critical_count,
            triage_warn_count=triage_warn_count,
            triage_info_count=triage_info_count,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            triage_red_flags=triage_red_flags,
            optimizer_scope_gate=str(optimizer_scope_gate.get("release_gate") or ""),
            optimizer_scope_gate_reason=str(
                optimizer_scope_gate.get("release_gate_reason") or ""
            ),
            optimizer_scope_release_risk=optimizer_scope_gate.get("release_risk")
            if isinstance(optimizer_scope_gate.get("release_risk"), bool)
            else None,
            anim_summary_lines=anim_summary_lines,
            operator_recommendations=operator_recommendations,
            mnemo_current_mode=str(
                anim_diag.get("anim_latest_mnemo_event_log_current_mode") or ""
            ),
            mnemo_recent_titles=tuple(
                str(item)
                for item in (anim_diag.get("anim_latest_mnemo_event_log_recent_titles") or [])
                if str(item).strip()
            ),
            suggested_next_step=suggested_next_step,
            suggested_next_detail=suggested_next_detail,
            suggested_next_action_key=suggested_next_action_key,
            suggested_next_artifact_key=suggested_next_artifact_key,
            validation_overview_rows=tuple(overview_rows),
            recent_artifacts=tuple(items),
        )

    def artifact_by_key(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact_key: str,
    ) -> DesktopResultsArtifact | None:
        target = str(artifact_key or "").strip()
        if not target:
            return None
        items = {item.key: item for item in snapshot.recent_artifacts}
        if target in items:
            return items[target]
        fallbacks = {
            "validation_json": "validation_md",
            "validation_md": "validation_json",
            "triage_json": "triage_md",
            "triage_md": "triage_json",
        }
        fallback_key = fallbacks.get(target, "")
        return items.get(fallback_key) if fallback_key else None

    def artifact_for_path(
        self,
        snapshot: DesktopResultsSnapshot,
        path: Path | None,
    ) -> DesktopResultsArtifact | None:
        if path is None:
            return None
        try:
            target = path.resolve()
        except Exception:
            target = path
        for artifact in snapshot.recent_artifacts:
            if artifact.path == target:
                return artifact
        return None

    def preferred_artifact_by_key(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact_key: str,
        *,
        handoff: DesktopResultsSessionHandoff | None = None,
    ) -> DesktopResultsArtifact | None:
        target = str(artifact_key or "").strip()
        if not target:
            return None
        session_items = {item.key: item for item in self.session_artifacts(snapshot, handoff)}
        fallbacks = {
            "validation_json": "validation_md",
            "validation_md": "validation_json",
            "triage_json": "triage_md",
            "triage_md": "triage_json",
        }
        candidates = [target]
        if not target.startswith("session_"):
            candidates.append(f"session_{target}")
        fallback_key = fallbacks.get(target, "")
        if fallback_key:
            candidates.append(fallback_key)
            candidates.append(f"session_{fallback_key}")
        for candidate in candidates:
            if candidate in session_items:
                return session_items[candidate]
        return self.artifact_by_key(snapshot, target)

    def preferred_artifact_for_path(
        self,
        snapshot: DesktopResultsSnapshot,
        path: Path | None,
        *,
        handoff: DesktopResultsSessionHandoff | None = None,
    ) -> DesktopResultsArtifact | None:
        if path is None:
            return None
        try:
            target = path.resolve()
        except Exception:
            target = path
        for artifact in self.session_artifacts(snapshot, handoff):
            if artifact.path == target:
                return artifact
        return self.artifact_for_path(snapshot, path)

    def overview_evidence_artifact(
        self,
        snapshot: DesktopResultsSnapshot,
        row: DesktopResultsOverviewRow | None,
    ) -> DesktopResultsArtifact | None:
        if row is None:
            return None
        artifact = self.artifact_by_key(snapshot, row.artifact_key)
        if artifact is not None:
            return artifact
        return self.artifact_for_path(snapshot, row.evidence_path)

    def preferred_overview_evidence_artifact(
        self,
        snapshot: DesktopResultsSnapshot,
        row: DesktopResultsOverviewRow | None,
        *,
        handoff: DesktopResultsSessionHandoff | None = None,
    ) -> DesktopResultsArtifact | None:
        if row is None:
            return None
        artifact = self.preferred_artifact_by_key(
            snapshot,
            row.artifact_key,
            handoff=handoff,
        )
        if artifact is not None:
            return artifact
        return self.preferred_artifact_for_path(
            snapshot,
            row.evidence_path,
            handoff=handoff,
        )

    def session_artifacts(
        self,
        snapshot: DesktopResultsSnapshot,
        handoff: DesktopResultsSessionHandoff | None,
    ) -> tuple[DesktopResultsArtifact, ...]:
        if handoff is None:
            return ()

        items: list[DesktopResultsArtifact] = []

        def append_current(
            key: str,
            title: str,
            path: Path | None,
            *,
            category: str,
            detail: str = "Закреплено из последней локальной точки передачи.",
        ) -> None:
            _append_artifact(
                items,
                key=key,
                title=title,
                category=category,
                path=path,
                detail=detail,
            )

        append_current(
            "session_send_bundle_zip",
            "ZIP текущего прогона",
            handoff.zip_path,
            category="bundle",
        )
        append_current(
            "session_autotest_run",
            "Каталог автотеста текущего прогона",
            handoff.autotest_run_dir,
            category="runs",
        )
        append_current(
            "session_diagnostics_run",
            "Каталог диагностики текущего прогона",
            handoff.diagnostics_run_dir,
            category="runs",
        )

        pinned_map = (
            ("validation_json", "Проверка текущего прогона в JSON"),
            ("validation_md", "Проверка текущего прогона в Markdown"),
            ("triage_json", "Разбор замечаний текущего прогона в JSON"),
            ("triage_md", "Разбор замечаний текущего прогона в Markdown"),
            ("dashboard_html", "HTML-сводка текущего прогона"),
            ("anim_diag_json", "Диагностика анимации текущего прогона"),
            ("latest_npz", "NPZ текущего прогона"),
            ("latest_pointer", "Указатель аниматора текущего прогона"),
            ("mnemo_event_log", "Журнал мнемосхемы текущего прогона"),
        )
        for artifact_key, title in pinned_map:
            artifact = self.artifact_by_key(snapshot, artifact_key)
            if artifact is None:
                continue
            items.append(
                DesktopResultsArtifact(
                    key=f"session_{artifact.key}",
                    title=title,
                    category=artifact.category,
                    path=artifact.path,
                    detail="Pinned from latest local run handoff.",
                )
            )
        return tuple(items)

    def compare_viewer_path(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ) -> Path | None:
        if artifact is not None:
            if _same_suffix(artifact.path, ".npz"):
                return artifact.path
            derived = _candidate_npz_for_pointer(artifact.path)
            if derived is not None:
                return derived
        return snapshot.latest_npz_path

    def animator_target_paths(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ) -> tuple[Path | None, Path | None]:
        npz_path = snapshot.latest_npz_path
        pointer_path = snapshot.latest_pointer_json_path
        if artifact is None:
            return npz_path, pointer_path

        if _same_suffix(artifact.path, ".npz"):
            npz_path = artifact.path
            candidate_pointer = artifact.path.with_suffix(".json")
            if candidate_pointer.exists():
                pointer_path = candidate_pointer
            return npz_path, pointer_path

        if artifact.path.name.endswith(".desktop_mnemo_events.json"):
            npz_candidate = _candidate_npz_for_pointer(artifact.path)
            if npz_candidate is not None:
                npz_path = npz_candidate
            return npz_path, pointer_path

        if _same_suffix(artifact.path, ".json") and artifact.category in {
            "results",
            "anim_latest",
        }:
            pointer_path = artifact.path
            npz_candidate = _candidate_npz_for_pointer(artifact.path)
            if npz_candidate is not None:
                npz_path = npz_candidate
            return npz_path, pointer_path

        return npz_path, pointer_path

    def compare_viewer_args(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ) -> list[str]:
        npz_path = self.compare_viewer_path(snapshot, artifact=artifact)
        if npz_path is None:
            return []
        return [str(npz_path)]

    def animator_args(
        self,
        snapshot: DesktopResultsSnapshot,
        *,
        follow: bool,
        artifact: DesktopResultsArtifact | None = None,
    ) -> list[str]:
        npz_path, pointer_path = self.animator_target_paths(snapshot, artifact=artifact)
        if follow:
            if pointer_path is not None:
                return ["--pointer", str(pointer_path)]
            if npz_path is not None:
                return ["--npz", str(npz_path), "--no-follow"]
            return []
        args: list[str] = []
        if npz_path is not None:
            args.extend(["--npz", str(npz_path)])
        if pointer_path is not None:
            args.extend(["--pointer", str(pointer_path)])
        args.append("--no-follow")
        return args

    def launch_compare_viewer(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ):
        return spawn_module(
            "pneumo_solver_ui.qt_compare_viewer",
            args=self.compare_viewer_args(snapshot, artifact=artifact),
        )

    def launch_animator(
        self,
        snapshot: DesktopResultsSnapshot,
        *,
        follow: bool,
        artifact: DesktopResultsArtifact | None = None,
    ):
        return spawn_module(
            "pneumo_solver_ui.desktop_animator.app",
            args=self.animator_args(snapshot, follow=follow, artifact=artifact),
        )

    def launch_full_diagnostics_gui(self):
        return spawn_module("pneumo_solver_ui.tools.run_full_diagnostics_gui")

    def launch_send_results_gui(self, *, env: dict[str, str] | None = None):
        if not env:
            return spawn_module("pneumo_solver_ui.tools.send_results_gui")
        cmd = [python_gui_exe(), "-m", "pneumo_solver_ui.tools.send_results_gui"]
        kwargs: dict[str, object] = {
            "cwd": str(self.repo_root),
            "env": dict(env),
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(cmd, **kwargs)
        return track_spawned_process(proc)

    def artifact_preview_lines(self, artifact: DesktopResultsArtifact) -> tuple[str, ...]:
        path = artifact.path
        if not path.exists():
            return ("Артефакт отсутствует на диске.",)

        if path.is_dir():
            children = sorted(path.iterdir(), key=lambda item: item.name.lower())
            lines = [f"Directory entries: {len(children)}"]
            for child in children[:6]:
                label = child.name + ("/" if child.is_dir() else "")
                lines.append(label)
            return tuple(lines)

        suffix = path.suffix.lower()
        if suffix == ".json":
            obj = _safe_read_json_any(path)
            if isinstance(obj, dict):
                if artifact.key == "validation_json":
                    errors = [str(item) for item in (obj.get("errors") or []) if str(item).strip()]
                    warnings = [str(item) for item in (obj.get("warnings") or []) if str(item).strip()]
                    gate = dict(obj.get("optimizer_scope_gate") or {})
                    lines = [
                        f"ok={obj.get('ok')}",
                        f"errors={len(errors)}",
                        f"warnings={len(warnings)}",
                    ]
                    if gate:
                        lines.append(f"optimizer_gate={gate.get('release_gate') or 'n/a'}")
                        if gate.get("release_gate_reason"):
                            lines.append(_short_text(gate.get("release_gate_reason")))
                    for item in errors[:3]:
                        lines.append("error: " + _short_text(item))
                    for item in warnings[:3]:
                        lines.append("warning: " + _short_text(item))
                    return tuple(lines)

                if artifact.key == "triage_json":
                    severity = dict(obj.get("severity_counts") or {})
                    red_flags = [str(item) for item in (obj.get("red_flags") or []) if str(item).strip()]
                    recommendations = [
                        str(item)
                        for item in (obj.get("operator_recommendations") or [])
                        if str(item).strip()
                    ]
                    dist = dict(obj.get("dist_progress") or {})
                    lines = [
                        "severity_counts=" + _short_text(severity),
                        f"red_flags={len(red_flags)}",
                    ]
                    if dist:
                        lines.append(
                            _short_text(
                                f"dist_progress: status={dist.get('status')} completed={dist.get('completed')} in_flight={dist.get('in_flight')}"
                            )
                        )
                    for item in red_flags[:3]:
                        lines.append("red_flag: " + _short_text(item))
                    for item in recommendations[:2]:
                        lines.append("next: " + _short_text(item))
                    return tuple(lines)

                if artifact.key in {"anim_diag_json", "latest_pointer"}:
                    token = obj.get("anim_latest_visual_cache_token") or obj.get("visual_cache_token")
                    reload_inputs = obj.get("anim_latest_visual_reload_inputs") or obj.get("visual_reload_inputs")
                    npz_path = obj.get("anim_latest_npz_path") or obj.get("npz_path")
                    lines = []
                    if token:
                        lines.append(f"token={token}")
                    if reload_inputs:
                        lines.append("reload_inputs=" + _short_text(reload_inputs))
                    if npz_path:
                        lines.append("npz=" + _short_text(Path(str(npz_path)).name))
                    if obj.get("anim_latest_mnemo_event_log_current_mode"):
                        lines.append(
                            "mnemo_mode="
                            + _short_text(obj.get("anim_latest_mnemo_event_log_current_mode"))
                        )
                    if obj.get("updated_utc") or obj.get("anim_latest_updated_utc"):
                        lines.append(
                            "updated="
                            + _short_text(obj.get("updated_utc") or obj.get("anim_latest_updated_utc"))
                        )
                    return tuple(lines[:6] or ["JSON preview available."])

                if artifact.key == "mnemo_event_log":
                    recent_events = obj.get("recent_events") or []
                    titles = []
                    if isinstance(recent_events, list):
                        for item in recent_events[:3]:
                            if isinstance(item, dict) and str(item.get("title") or "").strip():
                                titles.append(str(item.get("title")))
                    lines = [
                        f"mode={obj.get('current_mode') or '—'}",
                        f"event_count={obj.get('event_count')}",
                        f"active_latch={obj.get('active_latch_count')}",
                        f"acknowledged_latch={obj.get('acknowledged_latch_count')}",
                    ]
                    for item in titles:
                        lines.append("recent: " + _short_text(item))
                    return tuple(lines)

                keys = sorted(str(key) for key in obj.keys())[:8]
                return ("json_keys=" + ", ".join(keys),)
            return ("Предпросмотр JSON недоступен.",)

        if suffix in {".md", ".txt", ".html"}:
            try:
                raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                return ("Текстовый предпросмотр недоступен.",)
            lines = [_short_text(line) for line in raw_lines if str(line).strip()]
            return tuple(lines[:8] or ["Текстовый файл пуст."])

        if suffix == ".npz":
            try:
                size_bytes = int(path.stat().st_size)
            except Exception:
                size_bytes = 0
            return (
                f"NPZ-пакет: {path.name}",
                f"size_bytes={size_bytes}",
                "Для подробного разбора откройте сравнение или аниматор.",
            )

        try:
            size_bytes = int(path.stat().st_size)
        except Exception:
            size_bytes = 0
        return (
            f"Файл: {path.name}",
            f"size_bytes={size_bytes}",
        )


__all__ = ["DesktopResultsRuntime"]
