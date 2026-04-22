from __future__ import annotations

import json
import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pneumo_solver_ui.desktop_results_model import (
    DesktopResultsArtifact,
    DesktopResultsContextField,
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


COMPARE_CURRENT_CONTEXT_SIDECAR_JSON = "latest_compare_current_context.json"
ANALYSIS_ANIMATION_HANDOFF_JSON = "latest_analysis_animation_handoff.json"
ANIMATION_DIAGNOSTICS_HANDOFF_JSON = "latest_animation_diagnostics_handoff.json"


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


def _preview_number(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "нет данных"
    if not (number == number) or number in {float("inf"), float("-inf")}:
        return "нет данных"
    abs_number = abs(number)
    if abs_number and (abs_number >= 10000 or abs_number < 0.001):
        return f"{number:.3g}"
    return f"{number:.4g}"


def _status_ru(value: Any) -> str:
    raw = str(value or "").strip()
    labels = {
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
        "UNKNOWN": "не определено",
    }
    return labels.get(raw.upper(), raw or "—")


def _operator_text(value: Any) -> str:
    text = str(value or "").strip()
    replacements = {
        "Open Desktop Animator first and inspect Mnemo red flags before send.": (
    "Сначала откройте аниматор и проверьте красные флаги мнемосхемы перед сохранением архива проекта."
        ),
        "Open Desktop Animator first": "Сначала откройте аниматор",
        "Then inspect Compare Viewer": "Затем проверьте сравнение прогонов",
        "Open Compare Viewer next": "Перейдите к сравнению прогонов",
        "Открыть Compare Viewer " "следующим шагом": "Перейти к сравнению прогонов",
        "Desktop Mnemo recent:": "Недавнее событие мнемосхемы:",
        "Pointer drift": "Расхождение данных сопровождения",
        "Compare Viewer": "сравнение прогонов",
        "Desktop Animator": "аниматор",
        "Desktop Mnemo": "мнемосхема",
        "Open ": "Открыть ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


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


_OPERATOR_RECOMMENDATION_TRANSLATIONS_RU: dict[str, str] = {
    "Open Desktop Animator first and inspect Mnemo red flags before send.": (
        "Сначала откройте аниматор и проверьте красные флаги мнемосхемы перед сохранением архива проекта."
    ),
    "Open Desktop Animator first": "Сначала откройте аниматор.",
    "Then inspect Compare Viewer": "Затем проверьте сравнение прогонов.",
    "Open Compare Viewer next": "Перейдите к сравнению прогонов.",
}


def _operator_recommendation_ru(value: object) -> str:
    text = str(value or "").strip()
    return _operator_text(_OPERATOR_RECOMMENDATION_TRANSLATIONS_RU.get(text, text))


_CONTEXT_FIELD_TITLES: dict[str, str] = {
    "run_id": "Номер прогона",
    "run_contract_hash": "Метка прогона",
    "selected_run_hash": "Метка выбранного прогона",
    "analysis_context_hash": "Метка данных анализа",
    "analysis_context_status": "Состояние данных анализа",
    "animator_link_contract_hash": "Метка данных анимации",
    "selected_run_contract_hash": "Метка выбранного прогона",
    "selected_run_contract_path": "Файл выбранного прогона",
    "run_dir": "Папка прогона оптимизатора",
    "results_csv_path": "Таблица результатов оптимизатора",
    "selected_test_id": "Номер выбранного испытания",
    "selected_npz_path": "Файл выбранной анимации",
    "compare_contract_hash": "Метка сравнения",
        "evidence_manifest_hash": "Метка материалов проверки проекта",
    "objective_contract_hash": "Метка целевого профиля",
    "hard_gate_key": "Ограничение",
    "hard_gate_tolerance": "Допуск ограничения",
    "active_baseline_hash": "Метка базового варианта",
    "suite_snapshot_hash": "Метка набора испытаний",
    "scenario_lineage_hash": "Метка сценария",
    "problem_hash": "Метка задачи",
    "problem_hash_mode": "Режим метки задачи",
    "objective_keys": "Показатели цели",
    "penalty_key": "Штраф",
    "penalty_tol": "Допуск штрафа",
    "capture_export_manifest_handoff_id": "Метка записи анимации",
    "capture_hash": "Метка сохранённой анимации",
    "truth_mode_hash": "Метка режима отображения",
    "visual_cache_token": "Метка готовых данных анимации",
}

_CONTEXT_FIELD_KEYS: tuple[str, ...] = tuple(_CONTEXT_FIELD_TITLES)

_CONTEXT_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "visual_cache_token": ("visual_cache_token", "anim_latest_visual_cache_token"),
    "run_contract_hash": ("run_contract_hash", "selected_run_hash"),
    "analysis_context_hash": ("analysis_context_hash", "anim_latest_analysis_context_hash"),
    "analysis_context_status": ("analysis_context_status", "anim_latest_analysis_context_status"),
    "animator_link_contract_hash": (
        "animator_link_contract_hash",
        "anim_latest_animator_link_contract_hash",
    ),
    "selected_run_contract_hash": (
        "selected_run_contract_hash",
        "anim_latest_selected_run_contract_hash",
    ),
    "selected_run_contract_path": (
        "selected_run_contract_path",
        "anim_latest_selected_run_contract_path",
    ),
    "run_dir": ("run_dir", "optimizer_run_dir", "selected_run_dir"),
    "results_csv_path": ("results_csv_path", "optimizer_results_csv_path"),
    "selected_test_id": ("selected_test_id", "anim_latest_selected_test_id"),
    "selected_npz_path": ("selected_npz_path", "anim_latest_selected_npz_path", "anim_latest_npz_path"),
    "compare_contract_hash": ("compare_contract_hash", "compare_contract_id"),
    "objective_contract_hash": ("objective_contract_hash", "anim_latest_objective_contract_hash"),
    "suite_snapshot_hash": ("suite_snapshot_hash", "anim_latest_suite_snapshot_hash"),
    "problem_hash": ("problem_hash", "anim_latest_problem_hash"),
    "capture_export_manifest_handoff_id": (
        "capture_export_manifest_handoff_id",
        "anim_latest_capture_export_manifest_handoff_id",
    ),
    "capture_hash": ("capture_hash", "anim_latest_capture_hash"),
    "truth_mode_hash": ("truth_mode_hash", "anim_latest_truth_mode_hash"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_dumps_canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))


def _effective_workspace_dir(repo_root: Path) -> Path:
    raw = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw).expanduser()
    return (Path(repo_root) / "pneumo_solver_ui" / "workspace").resolve()


def _latest_optimizer_pointer_paths(repo_root: Path) -> tuple[Path, Path]:
    workspace_dir = _effective_workspace_dir(repo_root)
    return (
        workspace_dir / "_pointers" / "latest_optimization.json",
        workspace_dir / "opt" / "_last_opt.json",
    )


def _latest_optimizer_pointer_payload(repo_root: Path) -> tuple[Path | None, dict[str, Any]]:
    for path in _latest_optimizer_pointer_paths(repo_root):
        payload = _safe_read_json_dict(path)
        if payload:
            return path.resolve(), payload
    return None, {}


def _optimizer_selected_contract_info(
    *,
    repo_root: Path,
    pointer_path: Path | None,
    pointer_payload: Mapping[str, Any],
) -> dict[str, Any]:
    meta = _as_mapping(pointer_payload.get("meta"))
    run_dir = _existing_path(pointer_payload.get("run_dir"))
    contract_path = _existing_path(meta.get("selected_run_contract_path"))
    if contract_path is None:
        fallback = (
            _effective_workspace_dir(repo_root)
            / "handoffs"
            / "WS-OPTIMIZATION"
            / "selected_run_contract.json"
        )
        contract_path = _existing_path(fallback)
    contract_payload = _safe_read_json_dict(contract_path)
    if run_dir is None:
        run_dir = _existing_path(contract_payload.get("run_dir"))
    selected_run_contract_hash = str(
        meta.get("selected_run_contract_hash")
        or contract_payload.get("selected_run_contract_hash")
        or ""
    ).strip()
    if not selected_run_contract_hash and contract_path is not None:
        selected_run_contract_hash = _sha256_file(contract_path)
    ready_state = str(
        meta.get("analysis_handoff_ready_state")
        or contract_payload.get("analysis_handoff_ready_state")
        or ""
    ).strip()
    blocking_states = tuple(
        str(item)
        for item in (contract_payload.get("blocking_states") or ())
        if str(item).strip()
    )
    warnings = tuple(
        str(item)
        for item in (contract_payload.get("warnings") or ())
        if str(item).strip()
    )
    if contract_path is None:
        status = "MISSING"
        if pointer_path is None:
            banner = "Данные выбранного оптимизационного прогона пока недоступны."
        else:
            banner = "Данные анализа есть, но файл выбранного прогона не найден."
    elif blocking_states or ready_state == "blocked":
        status = "BLOCKED"
        banner = "Выбранный прогон оптимизации заблокирован для анализа."
    elif warnings or ready_state == "warning":
        status = "WARN"
        banner = "Выбранный прогон оптимизации доступен с предупреждениями."
    elif pointer_path is None:
        status = "WARN"
        banner = (
            "Файл выбранного прогона найден; "
            "закреплённые данные анализа отсутствуют."
        )
    else:
        status = "READY"
        banner = "Выбранный прогон оптимизации готов для анализа результатов."

    selected_context: dict[str, Any] = {
        "selected_run_contract_hash": selected_run_contract_hash,
        "selected_run_contract_path": str(contract_path or ""),
        "run_dir": str(run_dir or pointer_payload.get("run_dir") or ""),
        "run_id": str(contract_payload.get("run_id") or meta.get("run_id") or ""),
        "run_contract_hash": selected_run_contract_hash,
        "selected_run_hash": selected_run_contract_hash,
        "objective_contract_hash": str(
            contract_payload.get("objective_contract_hash")
            or meta.get("objective_contract_hash")
            or ""
        ),
        "hard_gate_key": str(contract_payload.get("hard_gate_key") or meta.get("penalty_key") or ""),
        "hard_gate_tolerance": str(
            contract_payload.get("hard_gate_tolerance")
            if contract_payload.get("hard_gate_tolerance") is not None
            else meta.get("penalty_tol", "")
        ),
        "active_baseline_hash": str(
            contract_payload.get("active_baseline_hash")
            or meta.get("active_baseline_hash")
            or ""
        ),
        "suite_snapshot_hash": str(
            contract_payload.get("suite_snapshot_hash")
            or meta.get("suite_snapshot_hash")
            or ""
        ),
        "problem_hash": str(contract_payload.get("problem_hash") or meta.get("problem_hash") or ""),
        "problem_hash_mode": str(
            contract_payload.get("problem_hash_mode") or meta.get("problem_hash_mode") or ""
        ),
        "objective_keys": contract_payload.get("objective_stack")
        or meta.get("objective_keys")
        or (),
        "penalty_key": str(
            contract_payload.get("hard_gate_key")
            or meta.get("penalty_key")
            or ""
        ),
        "penalty_tol": str(
            contract_payload.get("hard_gate_tolerance")
            if contract_payload.get("hard_gate_tolerance") is not None
            else meta.get("penalty_tol", "")
        ),
        "results_csv_path": str(
            contract_payload.get("results_csv_path")
            or meta.get("result_path")
            or ""
        ),
    }
    selected_context = {
        key: value
        for key, value in selected_context.items()
        if _stringify_context_value(value)
    }
    return {
        "pointer_path": pointer_path,
        "pointer_payload": dict(pointer_payload),
        "run_dir": run_dir,
        "meta": meta,
        "contract_path": contract_path,
        "contract_payload": contract_payload,
        "selected_context": selected_context,
        "selected_run_contract_hash": selected_run_contract_hash,
        "status": status,
        "banner": banner,
        "ready_state": ready_state,
        "blocking_states": blocking_states,
        "warnings": warnings,
    }


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nested_mapping(root: Mapping[str, Any], *path: str) -> dict[str, Any]:
    current: Any = root
    for key in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return _as_mapping(current)


def _stringify_context_value(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (Mapping, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(value)
    return str(value)


def _context_value(mapping: Mapping[str, Any], key: str) -> str:
    aliases = _CONTEXT_KEY_ALIASES.get(key, (key,))
    for alias in aliases:
        if alias in mapping:
            value = _stringify_context_value(mapping.get(alias))
            if value:
                return value
    return ""


def _merge_context(dst: dict[str, Any], src: Mapping[str, Any]) -> None:
    for key in _CONTEXT_FIELD_KEYS:
        if _context_value(dst, key):
            continue
        value = _context_value(src, key)
        if value:
            dst[key] = value


def _extract_result_context(
    *,
    validation_payload: Mapping[str, Any],
    triage_payload: Mapping[str, Any],
    anim_diag: Mapping[str, Any],
    optimizer_selected_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result_context = _nested_mapping(validation_payload, "result_context")
    current: dict[str, Any] = {}
    selected: dict[str, Any] = {}

    for src in (
        _nested_mapping(result_context, "current"),
        _nested_mapping(result_context, "current_context"),
        _nested_mapping(validation_payload, "current_context"),
        _nested_mapping(validation_payload, "optimizer_scope", "current"),
    ):
        _merge_context(current, src)
    _merge_context(current, anim_diag)

    for src in (
        _nested_mapping(result_context, "selected"),
        _nested_mapping(result_context, "selected_context"),
        _nested_mapping(validation_payload, "selected_context"),
        _nested_mapping(validation_payload, "analysis_context"),
        _nested_mapping(validation_payload, "optimizer_scope", "selected"),
    ):
        _merge_context(selected, src)

    _merge_context(selected, result_context)
    _merge_context(selected, _as_mapping(validation_payload.get("optimizer_scope")))
    _merge_context(selected, _as_mapping(triage_payload.get("dist_progress")))
    _merge_context(selected, anim_diag)
    _merge_context(selected, _as_mapping(optimizer_selected_context or {}))

    fields: list[DesktopResultsContextField] = []
    mismatches: list[str] = []
    comparable_count = 0
    for key in _CONTEXT_FIELD_KEYS:
        current_value = _context_value(current, key)
        selected_value = _context_value(selected, key)
        if not current_value and not selected_value:
            continue
        status = "HISTORICAL" if selected_value else "MISSING"
        detail = ""
        if current_value and selected_value:
            comparable_count += 1
            if current_value == selected_value:
                status = "CURRENT"
            else:
                status = "STALE"
                detail = f"{key}: текущее: {current_value}; выбранное: {selected_value}"
                mismatches.append(key)
        elif current_value and not selected_value:
            status = "MISSING"
            detail = f"{key}: текущее значение есть, результаты расчёта его не опубликовали"
        fields.append(
            DesktopResultsContextField(
                key=key,
                title=_CONTEXT_FIELD_TITLES.get(key, key),
                current_value=current_value,
                selected_value=selected_value,
                status=status,
                detail=detail,
            )
        )

    explicit_state = str(
        result_context.get("state")
        or result_context.get("context_state")
        or validation_payload.get("result_context_state")
        or ""
    ).strip().upper()
    selected_has_signal = any(_context_value(selected, key) for key in _CONTEXT_FIELD_KEYS)
    current_has_signal = any(_context_value(current, key) for key in _CONTEXT_FIELD_KEYS)

    if mismatches:
        state = "STALE"
        banner = "Текущая постановка отличается от результатов расчёта."
        detail = "Различаются поля: " + ", ".join(mismatches)
        action = "Откройте окно сравнения или переключите выбранные данные; сохранение материалов проверки проекта оставит оба набора данных."
    elif explicit_state in {"CURRENT", "HISTORICAL", "STALE"}:
        state = explicit_state
        banner = {
            "CURRENT": "Результаты расчёта соответствуют текущим данным.",
            "HISTORICAL": "Открыты исторические результаты расчёта с закреплёнными данными.",
            "STALE": "Текущие данные помечены как устаревшие для результатов расчёта.",
        }[state]
        detail = str(result_context.get("detail") or result_context.get("banner_detail") or "")
        action = str(result_context.get("action") or result_context.get("required_action") or "")
    elif selected_has_signal and current_has_signal and comparable_count > 0:
        state = "CURRENT"
        banner = "Результаты расчёта соответствуют текущим данным."
        detail = "Совпали опубликованные поля данных и метки результатов расчёта."
        action = "Можно переходить к сравнению, аниматору или сохранению материалов проверки проекта."
    elif selected_has_signal:
        state = "HISTORICAL"
        banner = "Открыты исторические результаты расчёта с закреплёнными данными."
        detail = "Текущие данные не опубликованы для полной сверки; результаты расчёта остаются историческими."
        action = "Для актуализации откройте текущий прогон или сохраните материалы как исторические результаты расчёта."
    else:
        state = "MISSING"
        banner = "Результаты расчёта отсутствуют."
        detail = "Отчёт проверки не опубликовал метки прогона и результатов расчёта."
        action = "Запустите проверку проекта или сохраните архив проекта со свежими результатами расчёта."

    return {
        "state": state,
        "banner": banner,
        "detail": detail,
        "action": action,
        "fields": tuple(fields),
        "current": dict(current),
        "selected": dict(selected),
        "mismatches": tuple(mismatches),
    }


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
        detail = validation_errors[0] if validation_errors else gate_reason or "Проверка вернула блокирующие ошибки."
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
                "Откройте аниматор в режиме сопровождения и проверьте последний критический участок."
                if latest_pointer_json_path is not None
                else "Откройте окно сравнения по последнему файлу анимации и проверьте критический результат."
            )
        )
        detail = triage_red_flags[0] if triage_red_flags else "Разбор замечаний отметил критические находки."
        if latest_pointer_json_path is not None:
            return action, detail, "open_animator_follow", "latest_pointer"
        if latest_npz_path is not None:
            return action, detail, "open_compare_viewer", "latest_npz"
        return action, detail, "open_artifact", "triage_json"

    if gate and gate not in {"PASS", "OK", "READY"}:
        return (
            "Перед сохранением архива проекта проверьте ограничения оптимизации.",
            gate_reason or f"Ограничение оптимизации: {_status_ru(gate)}",
            "open_artifact",
            "validation_json",
        )

    if validation_status == "WARN":
        detail = validation_warnings[0] if validation_warnings else "Проверка вернула предупреждения для просмотра оператором."
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
            else "Проверьте предупреждения разбора замечаний перед закрытием проверки."
        )
        detail = triage_red_flags[0] if triage_red_flags else "Разбор замечаний содержит предупреждения или красные флаги."
        return action, detail, "open_artifact", "triage_json"

    if triage_recommendations:
        return (
            triage_recommendations[0],
            "Последний разбор замечаний предлагает это как следующую операторскую проверку.",
            "open_artifact",
            "triage_json",
        )

    if anim_recommendations:
        if latest_pointer_json_path is not None:
            return (
                anim_recommendations[0],
                "Проверка анимации рекомендует именно это действие.",
                "open_animator_follow",
                "latest_pointer",
            )
        if latest_npz_path is not None:
            return (
                anim_recommendations[0],
                "Проверка анимации рекомендует именно это действие.",
                "open_compare_viewer",
                "latest_npz",
            )
        return (
            anim_recommendations[0],
            "Проверка анимации рекомендует именно это действие.",
            "open_artifact",
            "anim_diag_json",
        )

    if latest_npz_path is not None:
        return (
            "Откройте сравнение по последнему файлу анимации.",
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
            "Откройте проверку проекта и проверьте свежие материалы архива.",
            latest_zip_path.name,
            "open_send_center",
            "send_bundle_zip",
        )

    return (
            "Сначала запустите проверку проекта или сохраните архив проекта.",
        "Свежие материалы проверки и результатов пока не появились.",
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
            _operator_recommendation_ru(line)
            for line in build_anim_operator_recommendations(anim_dashboard)
            if str(line).strip()
        )
        triage_operator_recommendations = tuple(
            _operator_recommendation_ru(line)
            for line in (triage_payload.get("operator_recommendations") or [])
            if str(line).strip()
        )
        operator_recommendations = _dedupe_text_items(
            list(triage_operator_recommendations) + list(anim_operator_recommendations)
        )

        anim_diag = dict(collect_anim_latest_diagnostics_summary(include_meta=True) or {})
        latest_npz_path = _existing_path(anim_diag.get("anim_latest_npz_path"))
        latest_pointer_json_path = _existing_path(anim_diag.get("anim_latest_pointer_json"))
        latest_capture_export_manifest_path = _existing_path(
            anim_diag.get("anim_latest_capture_export_manifest_path")
        )
        capture_export_manifest_handoff_id = str(
            anim_diag.get("anim_latest_capture_export_manifest_handoff_id") or ""
        )
        capture_hash = str(anim_diag.get("anim_latest_capture_hash") or "")
        capture_blocking_states = tuple(
            str(item)
            for item in (anim_diag.get("anim_latest_capture_export_manifest_blocking_states") or [])
            if str(item).strip()
        )
        capture_truth_state = str(
            anim_diag.get("anim_latest_capture_export_manifest_truth_state") or ""
        )
        capture_analysis_context_status = str(
            anim_diag.get("anim_latest_analysis_context_status") or ""
        )
        if latest_capture_export_manifest_path is None:
            capture_manifest_status = "MISSING"
        elif capture_blocking_states:
            capture_manifest_status = "BLOCKED"
        elif (
            capture_export_manifest_handoff_id
            and capture_export_manifest_handoff_id != "HO-010"
        ):
            capture_manifest_status = "WARN"
        else:
            capture_manifest_status = "READY"
        latest_mnemo_event_log_path = _existing_path(
            anim_diag.get("anim_latest_mnemo_event_log_path")
        )
        latest_optimizer_pointer_path, latest_optimizer_pointer_payload = (
            _latest_optimizer_pointer_payload(self.repo_root)
        )
        optimizer_contract_info = _optimizer_selected_contract_info(
            repo_root=self.repo_root,
            pointer_path=latest_optimizer_pointer_path,
            pointer_payload=latest_optimizer_pointer_payload,
        )

        latest_autotest_run_dir = _latest_child_dir(self.autotest_runs_dir)
        latest_diagnostics_run_dir = _latest_child_dir(self.diagnostics_runs_dir)
        context = _extract_result_context(
            validation_payload=validation_payload,
            triage_payload=triage_payload,
            anim_diag=anim_diag,
            optimizer_selected_context=optimizer_contract_info.get("selected_context"),
        )
        workspace_manifest_path = (
            _effective_workspace_dir(self.repo_root) / "exports" / "analysis_evidence_manifest.json"
        )
        diagnostics_evidence_manifest_path = _existing_path(
            out_dir / "latest_analysis_evidence_manifest.json"
        ) or _existing_path(workspace_manifest_path)
        compare_current_context_sidecar_path = _existing_path(
            out_dir / COMPARE_CURRENT_CONTEXT_SIDECAR_JSON
        )
        evidence_manifest_payload = _safe_read_json_dict(diagnostics_evidence_manifest_path)
        diagnostics_evidence_manifest_hash = str(
            evidence_manifest_payload.get("evidence_manifest_hash") or ""
        )

        items: list[DesktopResultsArtifact] = []
        _append_artifact(items, key="send_bundle_zip", title="Последний архив проекта", category="bundle", path=latest_zip_path)
        _append_artifact(items, key="validation_json", title="Данные проверки", category="validation", path=validation_json_path)
        _append_artifact(items, key="validation_md", title="Отчёт проверки", category="validation", path=validation_md_path)
        _append_artifact(items, key="triage_json", title="Данные разбора замечаний", category="triage", path=triage_json_path)
        _append_artifact(items, key="triage_md", title="Отчёт разбора замечаний", category="triage", path=triage_md_path)
        _append_artifact(items, key="dashboard_html", title="Сводная страница результатов", category="results", path=dashboard_html_path)
        _append_artifact(items, key="anim_diag_json", title="Проверка анимации", category="anim_latest", path=anim_diag_json_path)
        _append_artifact(items, key="latest_npz", title="Последний файл анимации", category="results", path=latest_npz_path)
        _append_artifact(items, key="latest_pointer", title="Данные последней анимации", category="results", path=latest_pointer_json_path)
        _append_artifact(
            items,
            key="capture_export_manifest",
            title="Запись сохранения анимации",
            category="evidence",
            path=latest_capture_export_manifest_path,
            detail="Сохранённая связь выбранной анимации с результатом.",
        )
        _append_artifact(items, key="mnemo_event_log", title="Журнал событий мнемосхемы", category="results", path=latest_mnemo_event_log_path)
        _append_artifact(items, key="autotest_run", title="Последний каталог автотеста", category="runs", path=latest_autotest_run_dir)
        _append_artifact(items, key="diagnostics_run", title="Последняя папка проверки проекта", category="runs", path=latest_diagnostics_run_dir)
        _append_artifact(
            items,
            key="diagnostics_evidence_manifest",
            title="Материалы проверки проекта",
            category="evidence",
            path=diagnostics_evidence_manifest_path,
            detail="Материалы для связи анализа и проверки проекта.",
        )
        _append_artifact(
            items,
            key="compare_current_context_sidecar",
            title="Данные для окна сравнения",
            category="evidence",
            path=compare_current_context_sidecar_path,
            detail="Материалы для сравнения результатов расчёта.",
        )
        _append_artifact(
            items,
            key="selected_optimizer_run_contract",
            title="Выбранный прогон оптимизации",
            category="evidence",
            path=optimizer_contract_info.get("contract_path"),
            detail="Источник выбранного прогона для анализа результатов.",
        )
        _append_artifact(
            items,
            key="latest_optimizer_pointer",
            title="Закреплённые данные оптимизации",
            category="evidence",
            path=latest_optimizer_pointer_path,
            detail="Закреплённый выбранный расчёт для анализа результатов.",
        )

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
            _operator_text(item)
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
                title="Проверка архива проекта",
                status=validation_status,
                detail=(
                    f"ошибок: {len(validation_payload.get('errors') or [])}; "
                    f"предупреждений: {len(validation_payload.get('warnings') or [])}"
                ),
                next_action="Открыть отчёт проверки" if validation_json_path is not None else "Сначала запустить проверку проекта",
                evidence_path=validation_json_path or validation_md_path,
                action_key="open_artifact",
                artifact_key="validation_json" if validation_json_path is not None else "validation_md",
            ),
            DesktopResultsOverviewRow(
                key="triage_report",
                title="Разбор замечаний",
                status=triage_status,
                detail=(
                    f"критично: {triage_critical_count}; "
                    f"предупреждений: {triage_warn_count}; "
                    f"информация: {triage_info_count}; "
                    f"красных флагов: {len(triage_red_flags)}"
                ),
                next_action=(
                    triage_operator_recommendations[0]
                    if triage_operator_recommendations
                    else (
                        "Проверить красные флаги"
                        if triage_red_flags
                        else "Открыть разбор замечаний"
                    )
                )
                if triage_json_path is not None or triage_md_path is not None
                else "Сформировать разбор замечаний",
                evidence_path=triage_json_path or triage_md_path,
                action_key="open_artifact" if triage_json_path is not None or triage_md_path is not None else "open_diagnostics_gui",
                artifact_key="triage_json" if triage_json_path is not None else "triage_md",
            ),
            DesktopResultsOverviewRow(
                key="optimizer_scope_gate",
                title="Ограничения оптимизации",
                status=str(optimizer_scope_gate.get("release_gate") or "MISSING"),
                detail=str(optimizer_scope_gate.get("release_gate_reason") or "В последней проверке нет ограничений области оптимизации."),
                next_action="Проверить предупреждения" if validation_json_path is not None else "",
                evidence_path=validation_json_path,
                action_key="open_artifact",
                artifact_key="validation_json" if validation_json_path is not None else "validation_md",
            ),
            DesktopResultsOverviewRow(
                key="selected_result_context",
                title="Данные результатов расчёта",
                status=str(context.get("state") or "MISSING"),
                detail=str(context.get("banner") or ""),
                next_action=str(context.get("action") or "Сохранить материалы проверки проекта"),
                evidence_path=diagnostics_evidence_manifest_path,
                action_key="export_diagnostics_evidence",
                artifact_key="diagnostics_evidence_manifest",
            ),
            DesktopResultsOverviewRow(
                key="selected_optimizer_run_contract",
                title="Выбранный прогон оптимизации",
                status=str(optimizer_contract_info.get("status") or "MISSING"),
                detail=(
                    str(optimizer_contract_info.get("banner") or "")
                    + " Метка: "
                    + _short_text(
                        optimizer_contract_info.get("selected_run_contract_hash"),
                        limit=18,
                    )
                ),
                next_action=(
                    "Показать файл выбранного прогона"
                    if optimizer_contract_info.get("contract_path") is not None
                    else "Выбрать прогон в оптимизации"
                ),
                evidence_path=optimizer_contract_info.get("contract_path"),
                action_key=(
                    "open_artifact"
                    if optimizer_contract_info.get("contract_path") is not None
                    else "open_diagnostics_gui"
                ),
                artifact_key="selected_optimizer_run_contract",
            ),
            DesktopResultsOverviewRow(
                key="anim_latest_results",
                title="Последний результат анимации",
                status="READY" if latest_npz_path is not None else "MISSING",
                detail=str(latest_npz_path.name if latest_npz_path is not None else "Файл последней анимации недоступен."),
                next_action="Открыть сравнение" if latest_npz_path is not None else "Запустить автотест или проверку проекта",
                evidence_path=latest_npz_path,
                action_key="open_compare_viewer" if latest_npz_path is not None else "open_diagnostics_gui",
                artifact_key="latest_npz",
            ),
            DesktopResultsOverviewRow(
                key="animator_pointer",
                title="Анимация результатов расчёта",
                status="READY" if latest_pointer_json_path is not None else "MISSING",
                detail=str(
                    latest_pointer_json_path.name
                    if latest_pointer_json_path is not None
                    else "Данные анимации пока недоступны."
                ),
                next_action="Открыть анимацию расчёта" if latest_pointer_json_path is not None else "Сформировать данные анимации",
                evidence_path=latest_pointer_json_path,
                action_key="open_animator_follow" if latest_pointer_json_path is not None else "open_diagnostics_gui",
                artifact_key="latest_pointer",
            ),
            DesktopResultsOverviewRow(
                key="capture_export_manifest",
                title="Запись сохранения анимации",
                status=capture_manifest_status,
                detail=(
                    f"метка записи: {_short_text(capture_hash, limit=18) or '—'}; "
                    f"данные анализа: {_status_ru(capture_analysis_context_status)}; "
                    f"достоверность: {_status_ru(capture_truth_state)}"
                ),
                next_action=(
                    "Открыть запись сохранения анимации"
                    if latest_capture_export_manifest_path is not None
                    else "Сохранить выбранную анимацию в аниматоре"
                ),
                evidence_path=latest_capture_export_manifest_path,
                action_key=(
                    "open_artifact"
                    if latest_capture_export_manifest_path is not None
                    else "open_animator_follow"
                ),
                artifact_key="capture_export_manifest",
            ),
            DesktopResultsOverviewRow(
                key="mnemo_event_log",
                title="Журнал событий мнемосхемы",
                status="READY" if latest_mnemo_event_log_path is not None else "MISSING",
                detail=str(
                    latest_mnemo_event_log_path.name
                    if latest_mnemo_event_log_path is not None
                    else "Журнал событий для последнего результата не найден."
                ),
                next_action="Посмотреть свежие события" if latest_mnemo_event_log_path is not None else "Открыть мнемосхему и выгрузить журнал",
                evidence_path=latest_mnemo_event_log_path,
                action_key="open_artifact" if latest_mnemo_event_log_path is not None else "open_diagnostics_gui",
                artifact_key="mnemo_event_log",
            ),
            DesktopResultsOverviewRow(
                key="bundle_sidecars",
                title="Материалы архива проекта",
                status=(
                    "READY"
                    if latest_zip_path is not None and triage_md_path is not None and dashboard_html_path is not None
                    else "PARTIAL"
                ),
                detail=(
                    f"архив: {'есть' if latest_zip_path is not None else 'нет'}; "
                    f"разбор: {'есть' if triage_md_path is not None else 'нет'}; "
                    f"панель: {'есть' if dashboard_html_path is not None else 'нет'}"
                ),
                next_action="Скопировать архив" if latest_zip_path is not None else "Сохранить архив проекта",
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
            result_context_state=str(context.get("state") or "MISSING"),
            result_context_banner=str(context.get("banner") or ""),
            result_context_detail=str(context.get("detail") or ""),
            result_context_action=str(context.get("action") or ""),
            result_context_fields=tuple(context.get("fields") or ()),
            diagnostics_evidence_manifest_path=diagnostics_evidence_manifest_path,
            diagnostics_evidence_manifest_hash=diagnostics_evidence_manifest_hash,
            diagnostics_evidence_manifest_status=(
                "READY" if diagnostics_evidence_manifest_path is not None else "MISSING"
            ),
            latest_capture_export_manifest_path=latest_capture_export_manifest_path,
            latest_capture_export_manifest_status=capture_manifest_status,
            latest_capture_export_manifest_handoff_id=capture_export_manifest_handoff_id,
            latest_capture_hash=capture_hash,
            latest_optimizer_pointer_json_path=latest_optimizer_pointer_path,
            latest_optimizer_run_dir=optimizer_contract_info.get("run_dir"),
            selected_run_contract_path=optimizer_contract_info.get("contract_path"),
            selected_run_contract_hash=str(
                optimizer_contract_info.get("selected_run_contract_hash") or ""
            ),
            selected_run_contract_status=str(
                optimizer_contract_info.get("status") or "MISSING"
            ),
            selected_run_contract_banner=str(optimizer_contract_info.get("banner") or ""),
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

    def chart_preview_rows(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
        *,
        max_series: int = 6,
    ) -> tuple[dict[str, str], ...]:
        target_artifact = artifact or self.artifact_by_key(snapshot, "latest_npz")
        target_path = self.compare_viewer_path(snapshot, artifact=target_artifact)
        if target_path is None:
            return (
                {
                    "series": "Результат",
                    "points": "нет данных",
                    "range": "нужен результат расчёта",
                    "role": "сначала выполните расчёт",
                },
            )
        if not target_path.exists():
            return (
                {
                    "series": target_path.name,
                    "points": "нет данных",
                    "range": "файл не найден",
                    "role": "обновите анализ",
                },
            )
        if target_path.suffix.lower() != ".npz":
            return (
                {
                    "series": target_path.name,
                    "points": "нет данных",
                    "range": "не файл результата",
                    "role": "выберите файл расчёта",
                },
            )

        try:
            import numpy as np
        except Exception:
            return (
                {
                    "series": target_path.name,
                    "points": "нет данных",
                    "range": "предпросмотр временно недоступен",
                    "role": "используйте подробное сравнение",
                },
            )

        rows: list[dict[str, str]] = []
        try:
            with np.load(target_path, allow_pickle=False) as data:
                for key in data.files:
                    if len(rows) >= max_series:
                        break
                    try:
                        array = np.asarray(data[key])
                    except Exception:
                        continue
                    if array.size <= 0 or not np.issubdtype(array.dtype, np.number):
                        continue
                    finite = array[np.isfinite(array)]
                    if finite.size:
                        value_range = (
                            f"{_preview_number(finite.min())} .. "
                            f"{_preview_number(finite.max())}"
                        )
                    else:
                        value_range = "нет конечных значений"
                    shape = " x ".join(str(part) for part in array.shape) or "1"
                    rows.append(
                        {
                            "series": str(key),
                            "points": f"{int(array.size)}; форма {shape}",
                            "range": value_range,
                            "role": "готово к графику",
                        }
                    )
        except Exception:
            return (
                {
                    "series": target_path.name,
                    "points": "нет данных",
                    "range": "предпросмотр не прочитан",
                    "role": "используйте подробное сравнение",
                },
            )

        if rows:
            return tuple(rows)
        return (
            {
                "series": target_path.name,
                "points": "0",
                "range": "числовые серии не найдены",
                "role": "проверьте файл результата",
            },
        )

    def chart_preview_series_samples(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
        *,
        max_points: int = 80,
    ) -> dict[str, Any]:
        target_artifact = artifact or self.artifact_by_key(snapshot, "latest_npz")
        target_path = self.compare_viewer_path(snapshot, artifact=target_artifact)
        if target_path is None:
            return {
                "status": "MISSING",
                "series": "Результат",
                "samples": (),
                "point_count": 0,
                "range": "нужен результат расчёта",
            }
        if not target_path.exists() or target_path.suffix.lower() != ".npz":
            return {
                "status": "MISSING",
                "series": target_path.name,
                "samples": (),
                "point_count": 0,
                "range": "файл результата недоступен",
                "source_path": str(target_path),
            }
        try:
            import numpy as np
        except Exception:
            return {
                "status": "WARN",
                "series": target_path.name,
                "samples": (),
                "point_count": 0,
                "range": "numpy недоступен",
                "source_path": str(target_path),
            }

        try:
            with np.load(target_path, allow_pickle=False) as data:
                for key in data.files:
                    try:
                        array = np.asarray(data[key])
                    except Exception:
                        continue
                    if array.size <= 0 or not np.issubdtype(array.dtype, np.number):
                        continue
                    flat = array.reshape(-1)
                    finite = flat[np.isfinite(flat)]
                    if finite.size <= 0:
                        continue
                    limit = max(2, int(max_points or 80))
                    if finite.size > limit:
                        indices = np.linspace(0, finite.size - 1, num=limit, dtype=int)
                        sampled = finite[indices]
                    else:
                        sampled = finite
                    return {
                        "status": "READY",
                        "series": str(key),
                        "samples": tuple(float(value) for value in sampled.tolist()),
                        "point_count": int(array.size),
                        "finite_count": int(finite.size),
                        "minimum": _preview_number(finite.min()),
                        "maximum": _preview_number(finite.max()),
                        "range": f"{_preview_number(finite.min())} .. {_preview_number(finite.max())}",
                        "source_path": str(target_path),
                    }
        except Exception:
            return {
                "status": "WARN",
                "series": target_path.name,
                "samples": (),
                "point_count": 0,
                "range": "предпросмотр не прочитан",
                "source_path": str(target_path),
            }

        return {
            "status": "MISSING",
            "series": target_path.name,
            "samples": (),
            "point_count": 0,
            "range": "числовые серии не найдены",
            "source_path": str(target_path),
        }

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
            "Архив текущего прогона",
            handoff.zip_path,
            category="bundle",
        )
        append_current(
            "session_autotest_run",
            "Папка автотеста текущего прогона",
            handoff.autotest_run_dir,
            category="runs",
        )
        append_current(
            "session_diagnostics_run",
            "Папка проверки проекта текущего прогона",
            handoff.diagnostics_run_dir,
            category="runs",
        )

        pinned_map = (
            ("validation_json", "Данные проверки текущего прогона"),
            ("validation_md", "Отчёт проверки текущего прогона"),
            ("triage_json", "Данные разбора замечаний текущего прогона"),
            ("triage_md", "Отчёт разбора замечаний текущего прогона"),
            ("dashboard_html", "Сводная страница текущего прогона"),
            ("anim_diag_json", "Проверка анимации текущего прогона"),
            ("latest_npz", "Файл анимации текущего прогона"),
            ("latest_pointer", "Анимация текущего прогона"),
            ("capture_export_manifest", "Запись сохранения анимации текущего прогона"),
            ("mnemo_event_log", "Журнал мнемосхемы текущего прогона"),
            ("compare_current_context_sidecar", "Данные сравнения текущего прогона"),
            ("selected_optimizer_run_contract", "Выбранный прогон оптимизации для текущих результатов"),
            ("latest_optimizer_pointer", "Закреплённые данные оптимизации текущего прогона"),
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
                    detail="Закреплено из последнего локального прогона.",
                )
            )
        return tuple(items)

    def _evidence_artifact_record(self, artifact: DesktopResultsArtifact) -> dict[str, Any]:
        path = artifact.path
        record: dict[str, Any] = {
            "key": artifact.key,
            "title": artifact.title,
            "category": artifact.category,
            "path": str(path),
            "exists": bool(path.exists()),
            "is_dir": bool(path.is_dir()) if path.exists() else None,
            "detail": artifact.detail,
        }
        try:
            if path.exists() and path.is_file():
                stat = path.stat()
                record["size_bytes"] = int(stat.st_size)
                record["mtime_epoch"] = float(stat.st_mtime)
                record["sha256"] = _sha256_file(path)
            elif path.exists() and path.is_dir():
                record["child_count"] = sum(1 for _item in path.iterdir())
        except Exception as exc:
            record["sha256_error"] = str(exc)
        return record

    def _animation_diagnostics_handoff_evidence(self) -> dict[str, Any]:
        path = self.animation_diagnostics_handoff_path()
        payload = _safe_read_json_dict(path)
        selected = dict(payload.get("selected_artifact") or {}) if payload else {}
        artifacts = dict(payload.get("artifacts") or {}) if payload else {}
        context = dict(payload.get("animation_context") or {}) if payload else {}
        return {
            "status": "READY" if payload else "MISSING",
            "sidecar_path": str(path if path.exists() else ""),
            "schema": str(payload.get("schema") or "") if payload else "",
            "handoff_id": str(payload.get("handoff_id") or "") if payload else "",
            "handoff_hash": str(payload.get("handoff_hash") or "") if payload else "",
            "produced_by": str(payload.get("produced_by") or "") if payload else "",
            "consumed_by": str(payload.get("consumed_by") or "") if payload else "",
            "selected_artifact": {
                "key": str(selected.get("key") or ""),
                "title": str(selected.get("title") or ""),
                "category": str(selected.get("category") or ""),
                "path": str(selected.get("path") or ""),
            },
            "artifacts": {
                "scene_npz_path": str(artifacts.get("scene_npz_path") or ""),
                "pointer_json_path": str(artifacts.get("pointer_json_path") or ""),
                "mnemo_event_log_path": str(artifacts.get("mnemo_event_log_path") or ""),
                "capture_export_manifest_path": str(
                    artifacts.get("capture_export_manifest_path") or ""
                ),
                "analysis_animation_handoff_path": str(
                    artifacts.get("analysis_animation_handoff_path") or ""
                ),
            },
            "animation_context": {
                "scene_ready": bool(context.get("scene_ready")),
                "mnemo_ready": bool(context.get("mnemo_ready")),
                "capture_status": str(context.get("capture_status") or ""),
            },
            "next_step": str(payload.get("next_step") or "") if payload else "",
        }

    def build_diagnostics_evidence_manifest(
        self,
        snapshot: DesktopResultsSnapshot,
        *,
        handoff: DesktopResultsSessionHandoff | None = None,
    ) -> dict[str, Any]:
        artifacts = list(self.session_artifacts(snapshot, handoff)) + list(snapshot.recent_artifacts)
        selected_artifacts: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for artifact in artifacts:
            identity = (artifact.key, str(artifact.path))
            if identity in seen:
                continue
            seen.add(identity)
            selected_artifacts.append(self._evidence_artifact_record(artifact))

        selected_context = {
            field.key: field.selected_value
            for field in snapshot.result_context_fields
            if field.selected_value
        }
        current_context = {
            field.key: field.current_value
            for field in snapshot.result_context_fields
            if field.current_value
        }
        mismatches = [
            {
                "key": field.key,
                "title": field.title,
                "current": field.current_value,
                "selected": field.selected_value,
                "detail": field.detail,
            }
            for field in snapshot.result_context_fields
            if str(field.status or "").upper() == "STALE"
        ]
        payload: dict[str, Any] = {
            "schema": "desktop_results_evidence_manifest",
            "schema_version": "1.0.0",
            "handoff_id": "HO-009",
            "produced_by": "WS-ANALYSIS",
            "consumed_by": "WS-DIAGNOSTICS",
            "created_at": _utc_now(),
            "project_id": self.repo_root.name,
            "project_path": str(self.repo_root),
            "run_id": selected_context.get("run_id") or os.environ.get("PNEUMO_RUN_ID", ""),
            "run_contract_hash": selected_context.get("run_contract_hash", ""),
            "selected_run_contract_hash": snapshot.selected_run_contract_hash,
            "selected_run_contract_path": str(snapshot.selected_run_contract_path or ""),
            "compare_contract_id": selected_context.get("compare_contract_hash", ""),
            "context_hash": selected_context.get("analysis_context_hash")
            or selected_context.get("run_contract_hash")
            or "",
            "optimizer_selected_run_contract": {
                "status": snapshot.selected_run_contract_status,
                "banner": snapshot.selected_run_contract_banner,
                "path": str(snapshot.selected_run_contract_path or ""),
                "hash": snapshot.selected_run_contract_hash,
                "latest_optimizer_pointer_path": str(
                    snapshot.latest_optimizer_pointer_json_path or ""
                ),
                "latest_optimizer_run_dir": str(snapshot.latest_optimizer_run_dir or ""),
            },
            "selected_artifact_list": selected_artifacts,
            "selected_tables": [],
            "selected_charts": [],
            "selected_filters": {
                "source": "desktop_results_center",
                "artifact_scope": "session_handoff_plus_latest",
                "handoff_present": handoff is not None,
                "categories": sorted({str(item.get("category") or "") for item in selected_artifacts if item.get("category")}),
            },
            "mismatch_summary": {
                "state": snapshot.result_context_state,
                "banner": snapshot.result_context_banner,
                "detail": snapshot.result_context_detail,
                "required_action": snapshot.result_context_action,
                "mismatches": mismatches,
            },
            "result_context": {
                "state": snapshot.result_context_state,
                "current": current_context,
                "selected": selected_context,
                "fields": [
                    {
                        "key": field.key,
                        "title": field.title,
                        "current": field.current_value,
                        "selected": field.selected_value,
                        "status": field.status,
                        "detail": field.detail,
                    }
                    for field in snapshot.result_context_fields
                ],
            },
            "validation_reports": {
                "json": str(snapshot.latest_validation_json_path or ""),
                "markdown": str(snapshot.latest_validation_md_path or ""),
                "ok": snapshot.validation_ok,
                "errors": list(snapshot.validation_errors),
                "warnings": list(snapshot.validation_warnings),
            },
            "run_summaries": {
                "autotest_run_dir": str(snapshot.latest_autotest_run_dir or ""),
                "diagnostics_run_dir": str(snapshot.latest_diagnostics_run_dir or ""),
                "session_handoff": {
                    "summary": handoff.summary if handoff is not None else "",
                    "detail": handoff.detail if handoff is not None else "",
                    "step_lines": list(handoff.step_lines) if handoff is not None else [],
                },
            },
            "animation_diagnostics_handoff": self._animation_diagnostics_handoff_evidence(),
        }
        payload["evidence_manifest_hash"] = _sha256_text(_json_dumps_canonical(payload))
        return payload

    def write_diagnostics_evidence_manifest(
        self,
        snapshot: DesktopResultsSnapshot,
        *,
        handoff: DesktopResultsSessionHandoff | None = None,
    ) -> Path:
        payload = self.build_diagnostics_evidence_manifest(snapshot, handoff=handoff)
        workspace_path = (
            _effective_workspace_dir(self.repo_root) / "exports" / "analysis_evidence_manifest.json"
        )
        sidecar_path = self.send_bundles_dir / "latest_analysis_evidence_manifest.json"
        _atomic_write_json(workspace_path, payload)
        _atomic_write_json(sidecar_path, payload)
        return sidecar_path.resolve()

    def compare_current_context_sidecar_path(self) -> Path:
        return (self.send_bundles_dir / COMPARE_CURRENT_CONTEXT_SIDECAR_JSON).resolve()

    def analysis_animation_handoff_path(self) -> Path:
        return (self.send_bundles_dir / ANALYSIS_ANIMATION_HANDOFF_JSON).resolve()

    def animation_diagnostics_handoff_path(self) -> Path:
        return (self.send_bundles_dir / ANIMATION_DIAGNOSTICS_HANDOFF_JSON).resolve()

    def build_compare_current_context_sidecar(
        self,
        snapshot: DesktopResultsSnapshot,
    ) -> dict[str, Any]:
        selected_context = {
            field.key: field.selected_value
            for field in snapshot.result_context_fields
            if field.selected_value
        }
        current_context = {
            field.key: field.current_value
            for field in snapshot.result_context_fields
            if field.current_value
        }
        mismatches = [
            {
                "key": field.key,
                "title": field.title,
                "current": field.current_value,
                "selected": field.selected_value,
                "detail": field.detail,
            }
            for field in snapshot.result_context_fields
            if str(field.status or "").upper() == "STALE"
        ]
        payload: dict[str, Any] = {
            "schema": "desktop_results_compare_current_context",
            "schema_version": "1.0.0",
            "handoff_id": "HO-009",
            "produced_by": "WS-ANALYSIS",
            "consumed_by": "CompareViewer",
            "created_at": _utc_now(),
            "project_id": self.repo_root.name,
            "project_path": str(self.repo_root),
            "readonly": True,
            "source": "desktop_results_runtime",
            "current_context_ref": current_context,
            "selected_context_ref": selected_context,
            "result_context": {
                "state": snapshot.result_context_state,
                "banner": snapshot.result_context_banner,
                "detail": snapshot.result_context_detail,
                "required_action": snapshot.result_context_action,
            },
            "optimizer_selected_run_contract": {
                "status": snapshot.selected_run_contract_status,
                "banner": snapshot.selected_run_contract_banner,
                "path": str(snapshot.selected_run_contract_path or ""),
                "hash": snapshot.selected_run_contract_hash,
                "latest_optimizer_pointer_path": str(
                    snapshot.latest_optimizer_pointer_json_path or ""
                ),
                "latest_optimizer_run_dir": str(snapshot.latest_optimizer_run_dir or ""),
            },
            "mismatch_banner": {
                "banner_id": "BANNER-HIST-002" if mismatches else "BANNER-HIST-001",
                "severity": "warning" if mismatches else "info",
                "scope": "results_current_context_handoff",
                "mismatch_dimensions": [str(item.get("key") or "") for item in mismatches],
                "mismatches": mismatches,
            },
            "artifacts": {
                "latest_npz_path": str(snapshot.latest_npz_path or ""),
                "latest_validation_json_path": str(snapshot.latest_validation_json_path or ""),
                "latest_validation_md_path": str(snapshot.latest_validation_md_path or ""),
                "diagnostics_evidence_manifest_path": str(
                    snapshot.diagnostics_evidence_manifest_path or ""
                ),
                "latest_capture_export_manifest_path": str(
                    snapshot.latest_capture_export_manifest_path or ""
                ),
                "selected_run_contract_path": str(snapshot.selected_run_contract_path or ""),
                "latest_optimizer_pointer_path": str(
                    snapshot.latest_optimizer_pointer_json_path or ""
                ),
            },
        }
        payload["current_context_ref_hash"] = _sha256_text(
            _json_dumps_canonical(payload["current_context_ref"])
        )
        payload["sidecar_hash"] = _sha256_text(_json_dumps_canonical(payload))
        return payload

    def write_compare_current_context_sidecar(self, snapshot: DesktopResultsSnapshot) -> Path:
        path = self.compare_current_context_sidecar_path()
        _atomic_write_json(path, self.build_compare_current_context_sidecar(snapshot))
        return path.resolve()

    def build_analysis_animation_handoff(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ) -> dict[str, Any]:
        target_artifact = artifact or self.artifact_by_key(snapshot, "latest_npz")
        npz_path, pointer_path = self.animator_target_paths(snapshot, artifact=target_artifact)
        payload: dict[str, Any] = {
            "schema": "desktop_results_analysis_animation_handoff",
            "schema_version": "1.0.0",
            "handoff_id": "HO-ANALYSIS-ANIMATION-001",
            "produced_by": "WS-ANALYSIS",
            "consumed_by": "WS-ANIMATOR",
            "created_at": _utc_now(),
            "project_id": self.repo_root.name,
            "project_path": str(self.repo_root),
            "readonly": True,
            "source": "desktop_results_runtime",
            "selected_artifact": {
                "key": str(getattr(target_artifact, "key", "") or ""),
                "title": str(getattr(target_artifact, "title", "") or ""),
                "category": str(getattr(target_artifact, "category", "") or ""),
                "path": str(getattr(target_artifact, "path", "") or ""),
                "detail": str(getattr(target_artifact, "detail", "") or ""),
            },
            "artifacts": {
                "selected_artifact_path": str(getattr(target_artifact, "path", "") or ""),
                "latest_npz_path": str(npz_path or ""),
                "latest_pointer_json_path": str(pointer_path or ""),
                "latest_mnemo_event_log_path": str(
                    getattr(snapshot, "latest_mnemo_event_log_path", None) or ""
                ),
                "latest_capture_export_manifest_path": str(
                    getattr(snapshot, "latest_capture_export_manifest_path", None) or ""
                ),
                "selected_run_contract_path": str(
                    getattr(snapshot, "selected_run_contract_path", None) or ""
                ),
            },
            "result_context": {
                "state": getattr(snapshot, "result_context_state", "UNKNOWN"),
                "banner": getattr(snapshot, "result_context_banner", ""),
            },
            "next_step": "Откройте рабочий шаг анимации и проверьте движение по выбранному результату.",
        }
        payload["handoff_hash"] = _sha256_text(_json_dumps_canonical(payload))
        return payload

    def write_analysis_animation_handoff(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ) -> Path:
        path = self.analysis_animation_handoff_path()
        _atomic_write_json(path, self.build_analysis_animation_handoff(snapshot, artifact=artifact))
        return path.resolve()

    def animation_handoff_artifact(
        self,
        snapshot: DesktopResultsSnapshot | None = None,
    ) -> DesktopResultsArtifact | None:
        payload = _safe_read_json_dict(self.analysis_animation_handoff_path())
        artifacts = dict(payload.get("artifacts") or {})
        selected = dict(payload.get("selected_artifact") or {})
        target_path = _existing_path(
            selected.get("path")
            or artifacts.get("selected_artifact_path")
            or artifacts.get("latest_npz_path")
            or artifacts.get("latest_pointer_json_path")
        )
        if target_path is None:
            return None
        return DesktopResultsArtifact(
            key=str(selected.get("key") or "analysis_animation_handoff"),
            title=str(selected.get("title") or "Переданный результат анализа"),
            category=str(selected.get("category") or "results"),
            path=target_path,
            detail=str(selected.get("detail") or "Материал передан из анализа результатов."),
        )

    def build_animation_diagnostics_handoff(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ) -> dict[str, Any]:
        target_artifact = artifact or self.animation_handoff_artifact(snapshot)
        npz_path, pointer_path = self.animator_target_paths(snapshot, artifact=target_artifact)
        payload: dict[str, Any] = {
            "schema": "desktop_animation_diagnostics_handoff",
            "schema_version": "1.0.0",
            "handoff_id": "HO-ANIMATION-DIAGNOSTICS-001",
            "produced_by": "WS-ANIMATOR",
            "consumed_by": "WS-DIAGNOSTICS",
            "created_at": _utc_now(),
            "project_id": self.repo_root.name,
            "project_path": str(self.repo_root),
            "readonly": True,
            "source": "desktop_results_runtime",
            "selected_artifact": {
                "key": str(getattr(target_artifact, "key", "") or ""),
                "title": str(getattr(target_artifact, "title", "") or ""),
                "category": str(getattr(target_artifact, "category", "") or ""),
                "path": str(getattr(target_artifact, "path", "") or ""),
                "detail": str(getattr(target_artifact, "detail", "") or ""),
            },
            "artifacts": {
                "scene_npz_path": str(npz_path or ""),
                "pointer_json_path": str(pointer_path or ""),
                "mnemo_event_log_path": str(
                    getattr(snapshot, "latest_mnemo_event_log_path", None) or ""
                ),
                "capture_export_manifest_path": str(
                    getattr(snapshot, "latest_capture_export_manifest_path", None) or ""
                ),
                "analysis_animation_handoff_path": str(self.analysis_animation_handoff_path()),
            },
            "animation_context": {
                "scene_ready": bool(npz_path or pointer_path),
                "mnemo_ready": bool(
                    npz_path
                    or pointer_path
                    or getattr(snapshot, "latest_mnemo_event_log_path", None)
                ),
                "capture_status": str(
                    getattr(snapshot, "latest_capture_export_manifest_status", "") or ""
                ),
            },
            "next_step": "Перейдите к проверке проекта и сохраните архив с этим материалом анимации.",
        }
        payload["handoff_hash"] = _sha256_text(_json_dumps_canonical(payload))
        return payload

    def write_animation_diagnostics_handoff(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ) -> Path:
        path = self.animation_diagnostics_handoff_path()
        _atomic_write_json(path, self.build_animation_diagnostics_handoff(snapshot, artifact=artifact))
        return path.resolve()

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

    def animation_scene_preview_points(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
        *,
        max_points: int = 80,
    ) -> dict[str, Any]:
        target_artifact = artifact or self.animation_handoff_artifact(snapshot)
        npz_path, pointer_path = self.animator_target_paths(snapshot, artifact=target_artifact)
        if npz_path is None:
            return {
                "status": "MISSING",
                "source_path": "",
                "pointer_path": str(pointer_path or ""),
                "series_x": "index",
                "series_y": "scene",
                "points": (),
                "point_count": 0,
                "range": "нужен результат расчёта",
            }
        if not npz_path.exists() or npz_path.suffix.lower() != ".npz":
            return {
                "status": "MISSING",
                "source_path": str(npz_path),
                "pointer_path": str(pointer_path or ""),
                "series_x": "index",
                "series_y": npz_path.name,
                "points": (),
                "point_count": 0,
                "range": "файл сцены недоступен",
            }
        try:
            import numpy as np
        except Exception:
            return {
                "status": "WARN",
                "source_path": str(npz_path),
                "pointer_path": str(pointer_path or ""),
                "series_x": "index",
                "series_y": npz_path.name,
                "points": (),
                "point_count": 0,
                "range": "numpy недоступен",
            }

        try:
            with np.load(npz_path, allow_pickle=False) as data:
                numeric: list[tuple[str, Any]] = []
                for key in data.files:
                    try:
                        array = np.asarray(data[key]).reshape(-1)
                    except Exception:
                        continue
                    if array.size <= 0 or not np.issubdtype(array.dtype, np.number):
                        continue
                    finite_mask = np.isfinite(array)
                    if not finite_mask.any():
                        continue
                    numeric.append((str(key), array.astype(float, copy=False)))
                if not numeric:
                    return {
                        "status": "MISSING",
                        "source_path": str(npz_path),
                        "pointer_path": str(pointer_path or ""),
                        "series_x": "index",
                        "series_y": npz_path.name,
                        "points": (),
                        "point_count": 0,
                        "range": "числовые координаты не найдены",
                    }
                y_name, y_values = numeric[0]
                x_name = "index"
                x_values = np.arange(y_values.size, dtype=float)
                for candidate_name, candidate_values in numeric[1:]:
                    if candidate_values.size == y_values.size:
                        x_name = candidate_name
                        x_values = candidate_values
                        break
                mask = np.isfinite(x_values) & np.isfinite(y_values)
                x_values = x_values[mask]
                y_values = y_values[mask]
                if x_values.size <= 0:
                    return {
                        "status": "MISSING",
                        "source_path": str(npz_path),
                        "pointer_path": str(pointer_path or ""),
                        "series_x": x_name,
                        "series_y": y_name,
                        "points": (),
                        "point_count": 0,
                        "range": "нет конечных координат",
                    }
                limit = max(2, int(max_points or 80))
                if x_values.size > limit:
                    indices = np.linspace(0, x_values.size - 1, num=limit, dtype=int)
                    x_values = x_values[indices]
                    y_values = y_values[indices]
                points = tuple(
                    (float(x), float(y))
                    for x, y in zip(x_values.tolist(), y_values.tolist())
                )
                return {
                    "status": "READY",
                    "source_path": str(npz_path),
                    "pointer_path": str(pointer_path or ""),
                    "series_x": x_name,
                    "series_y": y_name,
                    "points": points,
                    "point_count": int(mask.sum()),
                    "range": (
                        f"x {_preview_number(x_values.min())} .. {_preview_number(x_values.max())}; "
                        f"y {_preview_number(y_values.min())} .. {_preview_number(y_values.max())}"
                    ),
                }
        except Exception:
            return {
                "status": "WARN",
                "source_path": str(npz_path),
                "pointer_path": str(pointer_path or ""),
                "series_x": "index",
                "series_y": npz_path.name,
                "points": (),
                "point_count": 0,
                "range": "предпросмотр сцены не прочитан",
            }

    def compare_viewer_args(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
        *,
        current_context_path: Path | None = None,
    ) -> list[str]:
        npz_path = self.compare_viewer_path(snapshot, artifact=artifact)
        if npz_path is None:
            return []
        args: list[str] = []
        if current_context_path is not None:
            args.extend(["--current-context", str(current_context_path)])
        args.append(str(npz_path))
        return args

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

    def mnemo_args(
        self,
        snapshot: DesktopResultsSnapshot,
        *,
        follow: bool,
        artifact: DesktopResultsArtifact | None = None,
    ) -> list[str]:
        npz_path, pointer_path = self.animator_target_paths(snapshot, artifact=artifact)
        if follow and pointer_path is not None:
            return ["--follow", "--pointer", str(pointer_path)]
        args: list[str] = []
        if npz_path is not None:
            args.extend(["--npz", str(npz_path)])
        if pointer_path is not None:
            args.extend(["--pointer", str(pointer_path)])
        return args

    def launch_compare_viewer(
        self,
        snapshot: DesktopResultsSnapshot,
        artifact: DesktopResultsArtifact | None = None,
    ):
        current_context_path = self.write_compare_current_context_sidecar(snapshot)
        return spawn_module(
            "pneumo_solver_ui.qt_compare_viewer",
            args=self.compare_viewer_args(
                snapshot,
                artifact=artifact,
                current_context_path=current_context_path,
            ),
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

    def launch_mnemo(
        self,
        snapshot: DesktopResultsSnapshot,
        *,
        follow: bool,
        artifact: DesktopResultsArtifact | None = None,
    ):
        return spawn_module(
            "pneumo_solver_ui.desktop_mnemo.main",
            args=self.mnemo_args(snapshot, follow=follow, artifact=artifact),
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
            return ("Материал отсутствует на диске.",)

        if path.is_dir():
            children = sorted(path.iterdir(), key=lambda item: item.name.lower())
            lines = [f"Элементов в папке: {len(children)}"]
            for child in children[:6]:
                label = child.name + ("/" if child.is_dir() else "")
                lines.append(label)
            return tuple(lines)

        suffix = path.suffix.lower()
        if suffix == ".json":
            obj = _safe_read_json_any(path)
            if isinstance(obj, dict):
                if artifact.key == "diagnostics_evidence_manifest":
                    selected = obj.get("selected_artifact_list") or []
                    mismatch = dict(obj.get("mismatch_summary") or {})
                    lines = [
                    "Тип: материалы проверки проекта",
                        f"Состояние данных: {_status_ru(mismatch.get('state'))}",
                        f"Материалов: {len(selected) if isinstance(selected, list) else 0}",
                    ]
                    if obj.get("evidence_manifest_hash"):
                        lines.append(
                            "Метка материалов: "
                            + _short_text(obj.get("evidence_manifest_hash"), limit=36)
                        )
                    if mismatch.get("banner"):
                        lines.append("Сводка: " + _short_text(mismatch.get("banner")))
                    return tuple(lines)

                if artifact.key == "compare_current_context_sidecar":
                    current = dict(obj.get("current_context_ref") or {})
                    selected = dict(obj.get("selected_context_ref") or {})
                    result_context = dict(obj.get("result_context") or {})
                    mismatch = dict(obj.get("mismatch_banner") or {})
                    lines = [
                        "Тип: данные сравнения",
                        f"Состояние данных: {_status_ru(result_context.get('state'))}",
                        f"Текущих ссылок: {len(current)}",
                        f"Выбранных ссылок: {len(selected)}",
                        f"Согласование: {_short_text(mismatch.get('banner_id') or '—')}",
                    ]
                    if obj.get("current_context_ref_hash"):
                        lines.append(
                            "Метка текущих данных: "
                            + _short_text(obj.get("current_context_ref_hash"), limit=36)
                        )
                    return tuple(lines)

                if artifact.key == "selected_optimizer_run_contract":
                    lines = [
                        "Тип: выбранный прогон оптимизации",
                        f"Прогон: {obj.get('run_id') or '—'}",
                        "Метка прогона: "
                        + _short_text(obj.get("selected_run_contract_hash"), limit=36),
                        "Целевой профиль: "
                        + _short_text(obj.get("objective_contract_hash"), limit=36),
                        "Задача: " + _short_text(obj.get("problem_hash"), limit=36),
                        "Базовый прогон: "
                        + _short_text(obj.get("active_baseline_hash"), limit=36),
                        f"Готовность анализа: {_status_ru(obj.get('analysis_handoff_ready_state'))}",
                    ]
                    blocking = [str(item) for item in (obj.get("blocking_states") or ()) if str(item).strip()]
                    warnings = [str(item) for item in (obj.get("warnings") or ()) if str(item).strip()]
                    lines.append(f"Блокировок: {len(blocking)}")
                    lines.append(f"Предупреждений: {len(warnings)}")
                    return tuple(lines)

                if artifact.key == "capture_export_manifest":
                    analysis_refs = dict(obj.get("analysis_context_refs") or {})
                    truth_summary = dict(obj.get("truth_summary") or {})
                    blocking = [
                        str(item)
                        for item in (obj.get("blocking_states") or [])
                        if str(item).strip()
                    ]
                    lines = [
                        "Тип: сохранение анимации",
                        "Метка записи: "
                        + _short_text(obj.get("capture_hash"), limit=36),
                        "Данные анализа: "
                        + _short_text(
                            _status_ru(
                                obj.get("analysis_context_status")
                            or analysis_refs.get("analysis_context_status")
                            or "—"
                            )
                        ),
                        "Состояние достоверности: "
                        + _short_text(
                            _status_ru(
                                truth_summary.get("overall_truth_state")
                            or obj.get("truth_state")
                            or "—"
                            )
                        ),
                        f"Блокировок: {len(blocking)}",
                    ]
                    if analysis_refs.get("selected_test_id"):
                        lines.append(
                            "Испытание: "
                            + _short_text(analysis_refs.get("selected_test_id"))
                        )
                    return tuple(lines)

                if artifact.key == "validation_json":
                    errors = [str(item) for item in (obj.get("errors") or []) if str(item).strip()]
                    warnings = [str(item) for item in (obj.get("warnings") or []) if str(item).strip()]
                    gate = dict(obj.get("optimizer_scope_gate") or {})
                    lines = [
                        f"Проверка: {'пройдена' if obj.get('ok') else 'требует внимания'}",
                        f"Ошибок: {len(errors)}",
                        f"Предупреждений: {len(warnings)}",
                    ]
                    if gate:
                        lines.append(f"Оптимизация: {_status_ru(gate.get('release_gate'))}")
                        if gate.get("release_gate_reason"):
                            lines.append(_short_text(gate.get("release_gate_reason")))
                    for item in errors[:3]:
                        lines.append("Ошибка: " + _short_text(item))
                    for item in warnings[:3]:
                        lines.append("Предупреждение: " + _short_text(item))
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
                        "Замечания: "
                        + f"критичных: {_to_int(severity.get('critical'))}; "
                        + f"предупреждений: {_to_int(severity.get('warn'))}; "
                        + f"справочных: {_to_int(severity.get('info'))}",
                        f"Красных флагов: {len(red_flags)}",
                    ]
                    if dist:
                        lines.append(
                            _short_text(
                                f"Распределенный расчет: состояние {_status_ru(dist.get('status'))}, завершено {dist.get('completed')}, в работе {dist.get('in_flight')}"
                            )
                        )
                    for item in red_flags[:3]:
                        lines.append("Красный флаг: " + _short_text(_operator_text(item)))
                    for item in recommendations[:2]:
                        lines.append("Рекомендация: " + _short_text(_operator_text(item)))
                    return tuple(lines)

                if artifact.key in {"anim_diag_json", "latest_pointer"}:
                    token = obj.get("anim_latest_visual_cache_token") or obj.get("visual_cache_token")
                    reload_inputs = obj.get("anim_latest_visual_reload_inputs") or obj.get("visual_reload_inputs")
                    npz_path = obj.get("anim_latest_npz_path") or obj.get("npz_path")
                    lines = []
                    if token:
                        lines.append(f"Метка готовых данных анимации: {token}")
                    if reload_inputs:
                        lines.append("Состав данных анимации: " + _short_text(reload_inputs))
                    if npz_path:
                        lines.append("Файл анимации: " + _short_text(Path(str(npz_path)).name))
                    if obj.get("anim_latest_mnemo_event_log_current_mode"):
                        lines.append(
                            "Режим мнемосхемы: "
                            + _short_text(obj.get("anim_latest_mnemo_event_log_current_mode"))
                        )
                    if obj.get("updated_utc") or obj.get("anim_latest_updated_utc"):
                        lines.append(
                            "Обновлено: "
                            + _short_text(obj.get("updated_utc") or obj.get("anim_latest_updated_utc"))
                        )
                    return tuple(lines[:6] or ["Предпросмотр данных доступен."])

                if artifact.key == "mnemo_event_log":
                    recent_events = obj.get("recent_events") or []
                    titles = []
                    if isinstance(recent_events, list):
                        for item in recent_events[:3]:
                            if isinstance(item, dict) and str(item.get("title") or "").strip():
                                titles.append(str(item.get("title")))
                    lines = [
                        f"Режим: {obj.get('current_mode') or '—'}",
                        f"Событий: {obj.get('event_count')}",
                        f"Активных фиксаций: {obj.get('active_latch_count')}",
                        f"Подтвержденных фиксаций: {obj.get('acknowledged_latch_count')}",
                    ]
                    for item in titles:
                        lines.append("Недавнее событие: " + _short_text(item))
                    return tuple(lines)

                return (f"Файл данных: полей {len(obj)}. Откройте файл для технических деталей.",)
            return ("Предпросмотр данных недоступен.",)

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
                f"Файл анимации: {path.name}",
                f"Размер: {size_bytes} байт",
                "Для подробного разбора откройте сравнение или аниматор.",
            )

        try:
            size_bytes = int(path.stat().st_size)
        except Exception:
            size_bytes = 0
        return (
            f"Файл: {path.name}",
            f"Размер: {size_bytes} байт",
        )


__all__ = ["DesktopResultsRuntime"]
