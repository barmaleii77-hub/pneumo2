#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight offline inspection for send-bundle ZIP files."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from pneumo_solver_ui.geometry_acceptance_contract import format_geometry_acceptance_summary_lines

from .health_report import collect_health_report
from .send_bundle_contract import build_anim_operator_recommendations, summarize_ring_closure
from .send_bundle_evidence import (
    ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
    ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
)


def _read_json_from_zip(zf: zipfile.ZipFile, name: str) -> Optional[Dict[str, Any]]:
    try:
        with zf.open(name, "r") as f:
            raw = f.read()
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        return dict(obj) if isinstance(obj, dict) else None
    except Exception:
        return None


def _geometry_acceptance_lines(geom: Dict[str, Any]) -> list[str]:
    lines = [
        f"- Состояние проверки: {geom.get('inspection_status') or 'missing'}",
        f"- Допуск геометрии: {geom.get('release_gate') or 'MISSING'}",
        f"- Причина допуска: {geom.get('release_gate_reason') or geom.get('error') or '—'}",
        f"- Данные получены из расчёта: {geom.get('producer_owned')}",
        f"- Без синтетической геометрии: {geom.get('no_synthetic_geometry')}",
    ]
    missing = [str(x) for x in (geom.get("missing_fields") or []) if str(x).strip()]
    if missing:
        lines.append(f"- Не хватает полей: {', '.join(missing[:8])}")
    warnings = [str(x) for x in (geom.get("warnings") or []) if str(x).strip()]
    for warning in warnings[:5]:
        lines.append(f"- Предупреждение: {warning}")
    try:
        formatted = [str(x) for x in format_geometry_acceptance_summary_lines(geom)]
        lines.extend(x for x in formatted if x not in lines)
    except Exception:
        pass
    return lines


def _sha256_file(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return ""


def inspect_send_bundle(zip_path: Path) -> Dict[str, Any]:
    zp = Path(zip_path).expanduser().resolve()
    rep = collect_health_report(zp)
    name_set = set()
    engineering_analysis_evidence: Dict[str, Any] = {}
    engineering_analysis_evidence_source = ""
    try:
        with zipfile.ZipFile(zp, "r") as zf:
            name_set = set(zf.namelist())
            for arcname in (
                ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
                ENGINEERING_ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
            ):
                if arcname not in name_set:
                    continue
                obj = _read_json_from_zip(zf, arcname)
                if obj is not None:
                    engineering_analysis_evidence = obj
                    engineering_analysis_evidence_source = arcname
                    break
    except Exception:
        name_set = set()

    signals = dict(rep.signals or {})
    meta = dict(signals.get("meta") or {})
    anim = dict(signals.get("anim_latest") or {})
    mnemo = dict(signals.get("mnemo_event_log") or {})
    ring_closure = dict(signals.get("ring_closure") or summarize_ring_closure(anim))
    optimizer_scope = dict(signals.get("optimizer_scope") or {})
    optimizer_scope_gate = dict(signals.get("optimizer_scope_gate") or {})
    latest_integrity_proof = dict(signals.get("latest_integrity_proof") or {})
    self_check_silent_warnings = dict(signals.get("self_check_silent_warnings") or {})
    operator_recommendations = [
        str(x)
        for x in (signals.get("operator_recommendations") or build_anim_operator_recommendations(anim))
        if str(x).strip()
    ]
    artifacts = dict(signals.get("artifacts") or {})
    evidence_manifest = dict(signals.get("evidence_manifest") or {})
    engineering_analysis_evidence = dict(signals.get("engineering_analysis_evidence") or {})
    geometry_acceptance = dict(rep.signals.get("geometry_acceptance") or {})
    summary: Dict[str, Any] = {
        "schema": "send_bundle_inspection",
        "schema_version": "1.2.0",
        "zip_path": str(zp),
        "zip_name": zp.name,
        "zip_sha256": _sha256_file(zp),
        "ok": bool(rep.ok),
        "release": meta.get("release") or "",
        "artifacts": artifacts,
        "evidence_manifest": evidence_manifest,
        "engineering_analysis_evidence": engineering_analysis_evidence,
        "anim_latest": anim,
        "mnemo_event_log": mnemo,
        "ring_closure": ring_closure,
        "optimizer_scope": optimizer_scope,
        "optimizer_scope_gate": optimizer_scope_gate,
        "latest_integrity_proof": latest_integrity_proof,
        "self_check_silent_warnings": self_check_silent_warnings,
        "operator_recommendations": operator_recommendations,
        "geometry_acceptance": geometry_acceptance,
        "geometry_acceptance_gate": str(geometry_acceptance.get("release_gate") or "MISSING") if geometry_acceptance else "MISSING",
        "geometry_acceptance_reason": str(geometry_acceptance.get("release_gate_reason") or "") if geometry_acceptance else "",
        "geometry_acceptance_inspection_status": str(geometry_acceptance.get("inspection_status") or "missing") if geometry_acceptance else "missing",
        "geometry_acceptance_missing_fields": list(geometry_acceptance.get("missing_fields") or []) if geometry_acceptance else [],
        "geometry_acceptance_warnings": list(geometry_acceptance.get("warnings") or []) if geometry_acceptance else [],
        "notes": list(rep.notes or []),
        "health_report": asdict(rep),
        "has_embedded_health_report": bool(artifacts.get("health_report_embedded")),
        "has_validation_report": bool(artifacts.get("validation_report")),
        "has_dashboard_report": bool(artifacts.get("dashboard_report")),
        "has_triage_report": bool(artifacts.get("triage_report")),
        "has_anim_diagnostics": bool(artifacts.get("anim_diagnostics")),
        "has_evidence_manifest": bool(artifacts.get("evidence_manifest")),
        "has_engineering_analysis_evidence": bool(artifacts.get("engineering_analysis_evidence")),
        "has_browser_perf_registry_snapshot": bool(artifacts.get("browser_perf_registry_snapshot")),
        "has_browser_perf_previous_snapshot": bool(artifacts.get("browser_perf_previous_snapshot")),
        "has_browser_perf_contract": bool(artifacts.get("browser_perf_contract")),
        "has_browser_perf_evidence_report": bool(artifacts.get("browser_perf_evidence_report")),
        "has_browser_perf_comparison_report": bool(artifacts.get("browser_perf_comparison_report")),
        "has_browser_perf_trace": bool(artifacts.get("browser_perf_trace")),
        "has_geometry_acceptance": bool(geometry_acceptance),
        "has_engineering_analysis_evidence": bool(engineering_analysis_evidence),
        "zip_entries": len(name_set),
    }
    if not bool(artifacts.get("health_report_embedded")):
        summary["notes"].insert(0, "отчёт состояния отсутствует в архиве; сводка восстановлена по содержимому архива")
    return summary


def render_inspection_md(summary: Dict[str, Any]) -> str:
    rep_obj = summary.get("health_report") or {}
    rep_signals = dict(rep_obj.get("signals") or {})
    anim = dict(summary.get("anim_latest") or {})
    evidence = dict(summary.get("evidence_manifest") or {})
    engineering = dict(summary.get("engineering_analysis_evidence") or {})
    mnemo = dict(summary.get("mnemo_event_log") or {})
    ring_closure = dict(summary.get("ring_closure") or {})
    optimizer_scope = dict(summary.get("optimizer_scope") or {})
    optimizer_scope_gate = dict(summary.get("optimizer_scope_gate") or {})
    latest_integrity_proof = dict(summary.get("latest_integrity_proof") or {})
    self_check_silent_warnings = dict(summary.get("self_check_silent_warnings") or {})
    engineering = dict(summary.get("engineering_analysis_evidence") or {})
    operator_recommendations = [str(x) for x in (summary.get("operator_recommendations") or []) if str(x).strip()]
    reload_inputs = list(anim.get("visual_reload_inputs") or [])
    lines = [
        "# Проверка архива проекта",
        "",
        f"- Архив: `{summary.get('zip_name') or ''}`",
        f"- ZIP SHA256: `{summary.get('zip_sha256') or '—'}`",
        f"- Успешно: **{bool(summary.get('ok'))}**",
        f"- Версия выпуска: {summary.get('release') or '—'}",
        f"- Отчёт состояния внутри архива: {summary.get('has_embedded_health_report')}",
        f"- Отчёт проверки: {summary.get('has_validation_report')}",
        f"- Сводный HTML-отчёт: {summary.get('has_dashboard_report')}",
        f"- Разбор замечаний: {summary.get('has_triage_report')}",
        f"- Данные последней анимации: {summary.get('has_anim_diagnostics')}",
        f"- Состав данных: {summary.get('has_evidence_manifest')}",
        f"- Данные инженерного анализа: {summary.get('has_engineering_analysis_evidence')}",
        f"- Снимок производительности анимации: {summary.get('has_browser_perf_registry_snapshot')}",
        f"- Предыдущий снимок производительности: {summary.get('has_browser_perf_previous_snapshot')}",
        f"- Условия проверки производительности: {summary.get('has_browser_perf_contract')}",
        f"- Отчёт производительности: {summary.get('has_browser_perf_evidence_report')}",
        f"- Сравнение производительности: {summary.get('has_browser_perf_comparison_report')}",
        f"- Трасса производительности: {summary.get('has_browser_perf_trace')}",
        f"- Проверка геометрии: {summary.get('has_geometry_acceptance')}",
        f"- Допуск геометрии: {summary.get('geometry_acceptance_gate') or 'MISSING'}",
        f"- Причина допуска геометрии: {summary.get('geometry_acceptance_reason') or '—'}",
    ]
    if latest_integrity_proof:
        lines += [
            "",
            "## Проверка актуального архива",
            f"- Состояние: `{latest_integrity_proof.get('status') or 'MISSING'}`",
            f"- SHA актуального архива: `{latest_integrity_proof.get('final_latest_zip_sha256') or '—'}`",
            f"- SHA исходного архива: `{latest_integrity_proof.get('final_original_zip_sha256') or '—'}`",
            f"- SHA-файл совпадает: {latest_integrity_proof.get('latest_sha_sidecar_matches')}",
            f"- Указатель ведёт на исходный архив: {latest_integrity_proof.get('latest_pointer_matches_original')}",
            f"- Область SHA состава данных: `{latest_integrity_proof.get('embedded_manifest_zip_sha256_scope') or '—'}`",
            f"- Этап состава данных: `{latest_integrity_proof.get('embedded_manifest_stage') or '—'}`",
            f"- Предупреждений источников данных: {latest_integrity_proof.get('producer_warning_count')}",
            f"- Есть предупреждающие разрывы: {latest_integrity_proof.get('warning_only_gaps_present')}",
            f"- Финальное закрытие не заявлено: {latest_integrity_proof.get('no_release_closure_claim')}",
        ]
        for warning in [str(x) for x in (latest_integrity_proof.get("warnings") or []) if str(x).strip()][:5]:
            lines.append(f"- Предупреждение: {warning}")
    if self_check_silent_warnings:
        lines += [
            "",
            "## Тихие предупреждения самопроверки",
            f"- Состояние: `{self_check_silent_warnings.get('status') or 'MISSING'}`",
            f"- Только снимок: {self_check_silent_warnings.get('snapshot_only')}",
            f"- Не закрывает предупреждения источников: {self_check_silent_warnings.get('does_not_close_producer_warnings')}",
            f"- Источник: `{self_check_silent_warnings.get('source_path') or '—'}`",
            f"- rc: {self_check_silent_warnings.get('rc')}",
            f"- Ошибок: {self_check_silent_warnings.get('fail_count')}",
            f"- Предупреждений: {self_check_silent_warnings.get('warn_count')}",
        ]
    if optimizer_scope:
        lines += [
            "",
            "## Оптимизация",
            f"- Состояние: {optimizer_scope.get('status') or '—'}",
            f"- Допуск области: `{optimizer_scope_gate.get('release_gate') or '—'}`",
            f"- Причина допуска: `{optimizer_scope_gate.get('release_gate_reason') or '—'}`",
            f"- Риск выпуска: `{optimizer_scope_gate.get('release_risk')}`",
            (
                f"- Ход расчёта: завершено={optimizer_scope.get('completed')} / выполняется={optimizer_scope.get('in_flight')} "
                f"/ из кэша={optimizer_scope.get('cached_hits')} / пропущено дублей={optimizer_scope.get('duplicates_skipped')}"
            ),
            f"- Область задачи: `{optimizer_scope.get('problem_hash_short') or optimizer_scope.get('problem_hash') or '—'}`",
            f"- Режим хэша: `{optimizer_scope.get('problem_hash_mode') or '—'}`",
        ]
        full_problem_hash = str(optimizer_scope.get("problem_hash") or "")
        short_problem_hash = str(optimizer_scope.get("problem_hash_short") or "")
        if full_problem_hash and short_problem_hash and full_problem_hash != short_problem_hash:
            lines.append(f"- Полный ключ области: `{full_problem_hash}`")
        lines.append(f"- Синхронизация области: `{optimizer_scope.get('scope_sync_ok')}`")
        for issue in list(optimizer_scope.get("issues") or [])[:5]:
            lines.append(f"- Замечание области: {issue}")
    if evidence:
        lines += [
            "",
            "## Состав данных",
            f"- Режим сбора: `{evidence.get('collection_mode') or '—'}`",
            f"- Причина запуска: `{evidence.get('trigger') or '—'}`",
            f"- Этап: `{evidence.get('finalization_stage') or '—'}`",
            f"- zip_sha256: `{evidence.get('zip_sha256') or '—'}`",
            f"- Не хватает обязательных данных PB002: `{evidence.get('pb002_missing_required_count')}`",
            f"- Не хватает обязательных данных: `{evidence.get('missing_required_count')}`",
            f"- Не хватает необязательных данных: `{evidence.get('missing_optional_count')}`",
        ]
        for warning in list(evidence.get("missing_warnings") or [])[:8]:
            lines.append(f"- Нет данных: {warning}")
    if engineering:
        lines += [
            "",
            "## Данные инженерного анализа",
            f"- Состояние: `{engineering.get('status') or 'MISSING'}`",
            f"- Готовность: `{engineering.get('readiness_status') or 'MISSING'}`",
            f"- Открытые вопросы: `{engineering.get('open_gap_status') or 'MISSING'}`",
            f"- Финальное закрытие не заявлено: `{engineering.get('no_release_closure_claim')}`",
            f"- Источник: `{engineering.get('source_path') or '—'}`",
            f"- Метка состава данных: `{engineering.get('evidence_manifest_hash') or '—'}`",
            f"- Влияние: `{engineering.get('influence_status') or '—'}`",
            f"- Калибровка: `{engineering.get('calibration_status') or '—'}`",
            f"- Строк чувствительности: `{engineering.get('sensitivity_row_count')}`",
            f"- Состояние проверенных данных: `{engineering.get('validated_artifacts_status') or '—'}`",
            f"- Обязательных данных: `{engineering.get('required_artifact_count')}`",
            f"- Готовых обязательных данных: `{engineering.get('ready_required_artifact_count')}`",
            f"- Не хватает обязательных данных: `{engineering.get('missing_required_artifact_count')}`",
            f"- Отсутствующие обязательные данные: `{', '.join(str(x) for x in (engineering.get('missing_required_artifact_keys') or [])) or '—'}`",
        ]
        open_gap_reasons = [
            str(item).strip()
            for item in (engineering.get("open_gap_reasons") or [])
            if str(item).strip()
        ]
        if open_gap_reasons:
            lines.append(f"- Причины открытых вопросов: `{', '.join(open_gap_reasons[:8])}`")
        requirements = dict(engineering.get("handoff_requirements") or {})
        if requirements:
            lines += [
                f"- Состояние передачи данных: `{requirements.get('contract_status') or '—'}`",
                f"- Обязательный файл передачи: `{requirements.get('required_contract_path') or '—'}`",
                f"- Не хватает полей передачи: `{', '.join(str(x) for x in (requirements.get('missing_fields') or [])) or '—'}`",
            ]
        readiness = dict(engineering.get("selected_run_candidate_readiness") or {})
        if readiness:
            lines += [
                f"- Кандидатов выбранного запуска: `{engineering.get('selected_run_candidate_count')}`",
                f"- Готовых кандидатов: `{engineering.get('selected_run_ready_candidate_count')}`",
                f"- Кандидатов без входных данных: `{engineering.get('selected_run_missing_inputs_candidate_count')}`",
            ]
    lines += [
        "",
        "## Последняя анимация",
        f"- Доступна: {anim.get('available')}",
        f"- Токен визуального кэша: `{anim.get('visual_cache_token') or '—'}`",
        f"- Входные данные перезагрузки: {', '.join(str(x) for x in reload_inputs) if reload_inputs else '—'}",
        f"- Указатель синхронизирован: {anim.get('pointer_sync_ok')}",
        f"- Входные данные синхронизированы: {anim.get('reload_inputs_sync_ok')}",
        f"- Файл анимации синхронизирован: {anim.get('npz_path_sync_ok')}",
        f"- Файл анимации: `{anim.get('npz_path') or '—'}`",
        f"- Обновлено UTC: {anim.get('updated_utc') or '—'}",
        f"- Тип сценария: {anim.get('scenario_kind') or '—'}",
        f"- Замыкание кольца: режим={anim.get('ring_closure_policy') or '—'} / применено={anim.get('ring_closure_applied')} / шов открыт={anim.get('ring_seam_open')} / скачок шва, м={anim.get('ring_seam_max_jump_m')} / исходный скачок, м={anim.get('ring_raw_seam_max_jump_m')}",
        f"- Состояние производительности: `{anim.get('browser_perf_status') or '—'}` / уровень=`{anim.get('browser_perf_level') or '—'}`",
        f"- Данные производительности: `{anim.get('browser_perf_evidence_status') or '—'}` / уровень=`{anim.get('browser_perf_evidence_level') or '—'}` / готовы в архиве=`{anim.get('browser_perf_bundle_ready')}` / снимок совпадает с условиями=`{anim.get('browser_perf_snapshot_contract_match')}`",
        f"- Сравнение производительности: `{anim.get('browser_perf_comparison_status') or '—'}` / уровень=`{anim.get('browser_perf_comparison_level') or '—'}` / готово=`{anim.get('browser_perf_comparison_ready')}` / изменилось=`{anim.get('browser_perf_comparison_changed')}`",
        f"- Изменение производительности: пробуждения=`{anim.get('browser_perf_comparison_delta_total_wakeups')}` / дубли=`{anim.get('browser_perf_comparison_delta_total_duplicate_guard_hits')}` / отрисовка=`{anim.get('browser_perf_comparison_delta_total_render_count')}` / max idle poll ms=`{anim.get('browser_perf_comparison_delta_max_idle_poll_ms')}`",
        f"- Основные данные производительности: снимок=`{anim.get('browser_perf_registry_snapshot_ref') or '—'}` / есть=`{anim.get('browser_perf_registry_snapshot_exists')}` / в архиве=`{anim.get('browser_perf_registry_snapshot_in_bundle')}` ; условия=`{anim.get('browser_perf_contract_ref') or '—'}` / есть=`{anim.get('browser_perf_contract_exists')}` / в архиве=`{anim.get('browser_perf_contract_in_bundle')}`",
        f"- Дополнительные данные производительности: предыдущий снимок=`{anim.get('browser_perf_previous_snapshot_ref') or '—'}` / есть=`{anim.get('browser_perf_previous_snapshot_exists')}` / в архиве=`{anim.get('browser_perf_previous_snapshot_in_bundle')}` ; отчёт=`{anim.get('browser_perf_evidence_report_ref') or '—'}` / есть=`{anim.get('browser_perf_evidence_report_exists')}` / в архиве=`{anim.get('browser_perf_evidence_report_in_bundle')}` ; сравнение=`{anim.get('browser_perf_comparison_report_ref') or '—'}` / есть=`{anim.get('browser_perf_comparison_report_exists')}` / в архиве=`{anim.get('browser_perf_comparison_report_in_bundle')}` ; трасса=`{anim.get('browser_perf_trace_ref') or '—'}` / есть=`{anim.get('browser_perf_trace_exists')}` / в архиве=`{anim.get('browser_perf_trace_in_bundle')}`",
    ]
    if ring_closure:
        lines += [
            "",
            "## Замыкание кольца",
            f"- Важность: {ring_closure.get('severity') or 'missing'}",
            f"- Сводка: {ring_closure.get('headline') or '—'}",
            f"- Режим: {ring_closure.get('closure_policy') or '—'} / применено={ring_closure.get('closure_applied')} / шов открыт={ring_closure.get('seam_open')}",
            f"- Скачок шва, м: обработанный=`{ring_closure.get('seam_max_jump_m')}` / исходный=`{ring_closure.get('raw_seam_max_jump_m')}`",
        ]
        for flag in list(ring_closure.get("red_flags") or [])[:3]:
            lines.append(f"- Предупреждение: {flag}")
    if mnemo:
        lines += [
            "",
            "## События мнемосхемы",
            f"- Важность: {mnemo.get('severity') or 'missing'}",
            f"- Сводка: {mnemo.get('headline') or '—'}",
            f"- Текущий режим: {mnemo.get('current_mode') or '—'}",
            f"- Состояние событий: всего=`{mnemo.get('event_count')}` / активно=`{mnemo.get('active_latch_count')}` / принято=`{mnemo.get('acknowledged_latch_count')}`",
        ]
        recent_titles = [str(x) for x in (mnemo.get("recent_titles") or []) if str(x).strip()]
        if recent_titles:
            lines.append(f"- Последние события: {' | '.join(recent_titles[:3])}")
    if operator_recommendations:
        lines += ["", "## Рекомендуемые действия"] + [f"{idx}. {item}" for idx, item in enumerate(operator_recommendations, start=1)]
    issues = list(anim.get("issues") or [])
    if issues:
        lines += ["", "## Замечания по последней анимации"] + [f"- {x}" for x in issues]
    geom = dict(summary.get("geometry_acceptance") or {})
    if geom:
        lines += ["", "## Проверка геометрии"] + _geometry_acceptance_lines(geom)
    notes = list(summary.get("notes") or [])
    if notes:
        lines += ["", "## Примечания"] + [f"- {x}" for x in notes]
    lines += [
        "",
        "## Машиночитаемые данные",
        "```json",
        json.dumps(rep_signals, ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Проверить архив проекта без запуска приложения")
    ap.add_argument("--zip", required=True, help="Путь к ZIP-архиву проекта")
    ap.add_argument("--json_out", default="", help="Необязательный путь для JSON-сводки")
    ap.add_argument("--md_out", default="", help="Необязательный путь для Markdown-сводки")
    ap.add_argument("--print_summary", action="store_true", help="Напечатать краткую сводку")
    ns = ap.parse_args(argv)

    summary = inspect_send_bundle(Path(ns.zip))
    if ns.json_out:
        Path(ns.json_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_inspection_md(summary)
    if ns.md_out:
        Path(ns.md_out).write_text(md, encoding="utf-8")
    if ns.print_summary:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
