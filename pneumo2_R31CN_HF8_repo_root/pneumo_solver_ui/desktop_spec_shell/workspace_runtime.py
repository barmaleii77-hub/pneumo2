from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

from pneumo_solver_ui.desktop_diagnostics_runtime import (
    load_desktop_diagnostics_bundle_record,
    load_last_desktop_diagnostics_run_record,
)
from pneumo_solver_ui.desktop_input_model import (
    build_desktop_section_change_cards,
    build_desktop_section_issue_cards,
    build_desktop_section_summary_cards,
    default_base_json_path,
    default_working_copy_path,
    desktop_profile_dir_path,
    desktop_snapshot_dir_path,
    evaluate_desktop_section_readiness,
    list_desktop_profile_paths,
    list_desktop_snapshot_paths,
    load_base_defaults,
    load_base_with_defaults,
)
from pneumo_solver_ui.desktop_optimizer_runtime import DesktopOptimizerRuntime
from pneumo_solver_ui.desktop_results_model import (
    DesktopResultsSnapshot,
    format_npz_summary,
    format_optimizer_gate_summary,
    format_recent_runs_summary,
    format_triage_summary,
    format_validation_summary,
)
from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime


@dataclass(frozen=True)
class WorkspaceSummaryFact:
    label: str
    value: str
    detail: str = ""


@dataclass(frozen=True)
class WorkspaceSummaryState:
    headline: str
    detail: str
    facts: tuple[WorkspaceSummaryFact, ...]
    evidence_lines: tuple[str, ...] = ()


def _python_executable(raw: str | None = None) -> str:
    return str(raw or sys.executable or "python")


def _safe_text(value: Any, *, fallback: str = "нет данных") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _path_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).expanduser().resolve())
    except Exception:
        return text


def _path_name(value: Any, *, fallback: str = "нет") -> str:
    text = _path_text(value)
    if not text:
        return fallback
    try:
        return Path(text).name
    except Exception:
        return text


def _dedupe_lines(*groups: tuple[str, ...] | list[str] | tuple[Any, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    lines: list[str] = []
    for group in groups:
        for raw in group:
            text = " ".join(str(raw or "").split()).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            lines.append(text)
    return tuple(lines)


def _stage_counts_text(counts: dict[str, int] | None) -> str:
    data = dict(counts or {})
    if not data:
        return "стадии пока не размечены"
    ordered = [f"{key}={int(value)}" for key, value in sorted(data.items())]
    return " | ".join(ordered)


def _objective_text(values: tuple[str, ...] | list[str] | None) -> str:
    items = [str(item).strip() for item in (values or ()) if str(item).strip()]
    return ", ".join(items) if items else "цели пока не заданы"


def _count_rows_with_status(rows: list[dict[str, Any]], status: str) -> int:
    expected = str(status or "").strip().casefold()
    return sum(
        1
        for row in rows
        if str(row.get("status") or "").strip().casefold() == expected
    )


def _titles_by_status(rows: list[dict[str, Any]], status: str) -> tuple[str, ...]:
    expected = str(status or "").strip().casefold()
    titles: list[str] = []
    for row in rows:
        if str(row.get("status") or "").strip().casefold() != expected:
            continue
        title = str(row.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
    return tuple(titles)


def _preview_list(values: tuple[str, ...] | list[str], *, empty: str) -> str:
    items = [str(value).strip() for value in values if str(value).strip()]
    if not items:
        return empty
    if len(items) <= 3:
        return ", ".join(items)
    return f"{', '.join(items[:3])} и ещё {len(items) - 3}"


def _build_results_runtime(repo_root: Path, python_executable: str | None = None) -> DesktopResultsRuntime:
    return DesktopResultsRuntime(
        repo_root=repo_root,
        python_executable=_python_executable(python_executable),
    )


def _build_optimizer_runtime(repo_root: Path, python_executable: str | None = None) -> DesktopOptimizerRuntime:
    return DesktopOptimizerRuntime(
        ui_root=repo_root,
        python_executable=_python_executable(python_executable),
    )


def _safe_results_snapshot(
    repo_root: Path,
    python_executable: str | None = None,
) -> DesktopResultsSnapshot | None:
    try:
        return _build_results_runtime(repo_root, python_executable).snapshot()
    except Exception:
        return None


def build_baseline_workspace_summary(
    repo_root: Path,
    *,
    python_executable: str | None = None,
) -> WorkspaceSummaryState:
    optimizer_runtime = _build_optimizer_runtime(repo_root, python_executable)
    contract = optimizer_runtime.contract_snapshot()
    results_snapshot = _safe_results_snapshot(repo_root, python_executable)

    baseline_label = _safe_text(contract.baseline_source_label, fallback="baseline provenance не найден")
    baseline_path = _path_text(contract.baseline_path) or "Сначала выполните baseline-aware запуск и сохраните provenance."
    latest_result = (
        format_npz_summary(results_snapshot)
        if results_snapshot is not None
        else "Последний NPZ пока не найден."
    )
    recent_runs = (
        format_recent_runs_summary(results_snapshot)
        if results_snapshot is not None
        else "История последних прогонов пока не собрана."
    )
    suggested_next = (
        _safe_text(results_snapshot.suggested_next_step, fallback="Откройте baseline launch surface и выполните базовый прогон.")
        if results_snapshot is not None
        else "Откройте baseline launch surface и выполните базовый прогон."
    )
    suggested_detail = (
        _safe_text(results_snapshot.suggested_next_detail, fallback="После baseline переходите в оптимизацию только из baseline-aware контекста.")
        if results_snapshot is not None
        else "После baseline переходите в оптимизацию только из baseline-aware контекста."
    )

    facts = (
        WorkspaceSummaryFact("Активный baseline", baseline_label, baseline_path),
        WorkspaceSummaryFact(
            "Контракт задачи",
            f"{_safe_text(contract.problem_hash_mode, fallback='mode n/a')} | {_safe_text(contract.problem_hash, fallback='hash n/a')}",
            f"Путь модели: {contract.model_path}",
        ),
        WorkspaceSummaryFact(
            "Пространство параметров",
            f"base={int(contract.base_param_count)} | search={int(contract.search_param_count)}",
            f"widened={int(contract.widened_range_count)} | runtime knobs removed={int(contract.removed_runtime_knob_count)}",
        ),
        WorkspaceSummaryFact(
            "Набор испытаний",
            f"rows={int(contract.suite_row_count)} | enabled={int(contract.enabled_suite_total)}",
            _stage_counts_text(contract.enabled_stage_counts),
        ),
        WorkspaceSummaryFact("Последний результат", latest_result, recent_runs),
        WorkspaceSummaryFact("Рекомендуемый следующий шаг", suggested_next, suggested_detail),
    )
    evidence_lines = _dedupe_lines(
        (
            f"Baseline path: {baseline_path}",
            f"Suite: {contract.suite_json_path}",
            f"Ranges: {contract.ranges_json_path}",
            f"Worker: {contract.worker_path}",
        ),
        (
            f"Latest NPZ: {_path_text(results_snapshot.latest_npz_path) if results_snapshot is not None else ''}",
            f"Latest validation: {_path_text(results_snapshot.latest_validation_json_path) if results_snapshot is not None else ''}",
        ),
    )
    return WorkspaceSummaryState(
        headline=baseline_label,
        detail=baseline_path,
        facts=facts,
        evidence_lines=evidence_lines,
    )


def build_input_workspace_summary(
    repo_root: Path,
    *,
    python_executable: str | None = None,
) -> WorkspaceSummaryState:
    del repo_root, python_executable
    try:
        current_payload = load_base_with_defaults()
        reference_payload = load_base_defaults()
        readiness_rows = evaluate_desktop_section_readiness(current_payload)
        summary_cards = build_desktop_section_summary_cards(current_payload)
        issue_cards = build_desktop_section_issue_cards(current_payload)
        change_cards = build_desktop_section_change_cards(
            current_payload,
            reference_payload,
        )
        working_copy_path = default_working_copy_path()
        base_json_path = default_base_json_path()
        profile_dir = desktop_profile_dir_path()
        snapshot_dir = desktop_snapshot_dir_path()
        profile_paths = list_desktop_profile_paths()
        snapshot_paths = list_desktop_snapshot_paths()
    except Exception as exc:
        return WorkspaceSummaryState(
            headline="Сводка исходных данных пока недоступна",
            detail="Не удалось собрать hosted summary для workspace исходных данных.",
            facts=(
                WorkspaceSummaryFact(
                    "Состояние",
                    "runtime summary недоступен",
                    _safe_text(exc, fallback="Проверьте desktop_input_model и рабочую копию входных данных."),
                ),
                WorkspaceSummaryFact(
                    "Следующий шаг",
                    "Откройте legacy editor исходных данных",
                    "После восстановления runtime можно вернуться в hosted workspace и продолжить маршрут shell.",
                ),
            ),
            evidence_lines=(
                f"Working copy: {_path_text(default_working_copy_path())}",
                f"Default base JSON: {_path_text(default_base_json_path())}",
            ),
        )

    warn_titles = _titles_by_status(readiness_rows, "warn")
    ok_count = _count_rows_with_status(readiness_rows, "ok")
    warn_count = len(warn_titles)
    issue_total = sum(int(card.get("issue_count") or 0) for card in issue_cards)
    changed_sections = tuple(
        str(card.get("title") or "").strip()
        for card in change_cards
        if int(card.get("changed_count") or 0) > 0
    )
    changed_total = sum(int(card.get("changed_count") or 0) for card in change_cards)
    top_section_lines = tuple(
        f"{str(card.get('title') or '').strip()}: {_safe_text(card.get('headline'))}"
        for card in summary_cards[:5]
        if str(card.get("title") or "").strip()
    )
    issue_lines = tuple(
        f"{str(card.get('title') or '').strip()}: {_safe_text(card.get('summary'))}"
        for card in issue_cards
        if int(card.get("issue_count") or 0) > 0
    )
    change_lines = tuple(
        f"{str(card.get('title') or '').strip()}: {_safe_text(card.get('summary'))}"
        for card in change_cards
        if int(card.get("changed_count") or 0) > 0
    )

    headline = (
        "Исходные данные готовы к следующему маршруту"
        if warn_count == 0
        else f"Требуют внимания {warn_count} разделов исходных данных"
    )
    detail = (
        "Рабочая копия, эталон и готовность разделов собраны прямо в hosted shell."
        if warn_count == 0
        else f"Проверьте разделы: {_preview_list(warn_titles, empty='нет предупреждений')}."
    )

    facts = (
        WorkspaceSummaryFact(
            "Рабочая копия",
            _path_name(working_copy_path, fallback="desktop_input_base.json"),
            _path_text(working_copy_path) or "Файл рабочей копии пока не найден.",
        ),
        WorkspaceSummaryFact(
            "Эталон base JSON",
            _path_name(base_json_path, fallback="default_base.json"),
            _path_text(base_json_path) or "Эталонный JSON пока не найден.",
        ),
        WorkspaceSummaryFact(
            "Готовность разделов",
            f"ok={ok_count} | warn={warn_count}",
            (
                "Все ключевые разделы выглядят готовыми к переходу в сценарии и набор испытаний."
                if warn_count == 0
                else f"Требуют проверки: {_preview_list(warn_titles, empty='нет предупреждений')}."
            ),
        ),
        WorkspaceSummaryFact(
            "Инженерные замечания",
            f"{issue_total} активных сигналов",
            _preview_list(
                tuple(
                    str(card.get("summary") or "").strip()
                    for card in issue_cards
                    if int(card.get("issue_count") or 0) > 0
                ),
                empty="Замечаний по разделам сейчас нет.",
            ),
        ),
        WorkspaceSummaryFact(
            "Изменения относительно эталона",
            f"разделов={len(changed_sections)} | параметров={changed_total}",
            (
                "Рабочая копия совпадает с эталоном."
                if not changed_sections
                else f"Изменены разделы: {_preview_list(changed_sections, empty='без изменений')}."
            ),
        ),
        WorkspaceSummaryFact(
            "Профили и snapshots",
            f"profiles={len(profile_paths)} | snapshots={len(snapshot_paths)}",
            f"Profiles: {_path_text(profile_dir)} | Snapshots: {_path_text(snapshot_dir)}",
        ),
        WorkspaceSummaryFact(
            "Следующий шаг",
            (
                "Переходите к сценариям и редактору кольца"
                if warn_count == 0
                else "Сначала доберите предупреждения в исходных данных или откройте legacy editor"
            ),
            "После стабилизации исходных данных переходите в сценарии, затем в набор испытаний и baseline.",
        ),
    )
    evidence_lines = _dedupe_lines(
        (
            f"Working copy: {_path_text(working_copy_path)}",
            f"Default base JSON: {_path_text(base_json_path)}",
            f"Profiles dir: {_path_text(profile_dir)}",
            f"Snapshots dir: {_path_text(snapshot_dir)}",
        ),
        top_section_lines,
        issue_lines,
        change_lines,
    )
    return WorkspaceSummaryState(
        headline=headline,
        detail=detail,
        facts=facts,
        evidence_lines=evidence_lines,
    )


def build_optimization_workspace_summary(
    repo_root: Path,
    *,
    python_executable: str | None = None,
) -> WorkspaceSummaryState:
    runtime = _build_optimizer_runtime(repo_root, python_executable)
    contract = runtime.contract_snapshot()
    pointer = runtime.latest_pointer_summary()
    current_job = runtime.current_job()

    active_job = "нет активного job"
    active_job_detail = "Можно запускать только один активный route: StageRunner primary, distributed coordinator как advanced mode."
    if current_job is not None:
        active_job = f"{_safe_text(current_job.backend, fallback='backend')} | {_path_name(current_job.run_dir)}"
        active_job_detail = (
            f"pipeline={_safe_text(current_job.pipeline_mode, fallback='n/a')} | "
            f"budget={int(getattr(current_job, 'budget', 0) or 0)}"
        )

    pointer_value = "указатель последнего optimization run пока не найден"
    pointer_detail = "Сначала нужен завершённый или выбранный run в истории."
    if bool(pointer.get("exists")):
        pointer_value = f"{_safe_text(pointer.get('status_label'), fallback='run')} | {_safe_text(pointer.get('run_name'), fallback='run')}"
        pointer_detail = (
            f"backend={_safe_text(pointer.get('backend'), fallback='n/a')} | "
            f"rows={int(pointer.get('rows') or 0)} | "
            f"done={int(pointer.get('done_count') or 0)} | "
            f"errors={int(pointer.get('error_count') or 0)}"
        )

    facts = (
        WorkspaceSummaryFact(
            "Рекомендуемый путь",
            "StageRunner — основной маршрут",
            "Distributed coordinator остаётся advanced mode и не должен становиться вторым параллельным основным запуском.",
        ),
        WorkspaceSummaryFact(
            "Objective stack",
            _objective_text(contract.objective_keys),
            f"Penalty: {_safe_text(contract.penalty_key, fallback='n/a')} <= {float(contract.penalty_tol):g}",
        ),
        WorkspaceSummaryFact(
            "Baseline provenance",
            _safe_text(contract.baseline_source_label, fallback="не найден"),
            _path_text(contract.baseline_path) or "Нужен явный baseline provenance.",
        ),
        WorkspaceSummaryFact(
            "Suite / stages",
            f"enabled={int(contract.enabled_suite_total)} | rows={int(contract.suite_row_count)}",
            _stage_counts_text(contract.enabled_stage_counts),
        ),
        WorkspaceSummaryFact(
            "Search space",
            f"base={int(contract.base_param_count)} | search={int(contract.search_param_count)}",
            f"widened={int(contract.widened_range_count)} | runtime knobs removed={int(contract.removed_runtime_knob_count)}",
        ),
        WorkspaceSummaryFact("Активный job", active_job, active_job_detail),
        WorkspaceSummaryFact("Последний optimization pointer", pointer_value, pointer_detail),
    )
    evidence_lines = _dedupe_lines(
        (
            f"Model: {contract.model_path}",
            f"Base JSON: {contract.base_json_path}",
            f"Ranges JSON: {contract.ranges_json_path}",
            f"Suite JSON: {contract.suite_json_path}",
            f"Stage tuner: {contract.stage_tuner_json_path or 'не используется'}",
        ),
        (
            f"Pointer run dir: {_safe_text(pointer.get('run_dir'), fallback='')}",
            f"Pointer result: {_safe_text(pointer.get('result_path'), fallback='')}",
        ),
    )
    return WorkspaceSummaryState(
        headline="Optimization contract готов к управляемому запуску",
        detail="Shell держит objective stack, hard gate и baseline provenance рядом с входом в optimization.",
        facts=facts,
        evidence_lines=evidence_lines,
    )


def build_results_workspace_summary(
    repo_root: Path,
    *,
    python_executable: str | None = None,
) -> WorkspaceSummaryState:
    snapshot = _safe_results_snapshot(repo_root, python_executable)
    if snapshot is None:
        return WorkspaceSummaryState(
            headline="Сводка результатов пока недоступна",
            detail="Не удалось прочитать latest results artifacts. Откройте results center или diagnostics lane и обновите артефакты.",
            facts=(
                WorkspaceSummaryFact(
                    "Состояние",
                    "нет snapshot",
                    "Results snapshot должен собраться из send_bundles, autotest_runs и diagnostics_runs.",
                ),
            ),
        )

    artifact_lines = tuple(
        f"{artifact.title}: {artifact.path}"
        for artifact in snapshot.recent_artifacts[:6]
    )
    facts = (
        WorkspaceSummaryFact("Валидация", format_validation_summary(snapshot), snapshot.suggested_next_detail),
        WorkspaceSummaryFact("Optimizer gate", format_optimizer_gate_summary(snapshot), "Gate должен быть видимым прямо в analysis lane."),
        WorkspaceSummaryFact("Triage", format_triage_summary(snapshot), _safe_text(snapshot.triage_red_flags[0] if snapshot.triage_red_flags else "", fallback="Красных флагов сейчас нет.")),
        WorkspaceSummaryFact("Последний NPZ", format_npz_summary(snapshot), format_recent_runs_summary(snapshot)),
        WorkspaceSummaryFact(
            "Animator / Mnemo",
            f"mode={_safe_text(snapshot.mnemo_current_mode, fallback='нет данных')}",
            ", ".join(snapshot.mnemo_recent_titles[:3]) if snapshot.mnemo_recent_titles else "Недавние мнемо-события пока не найдены.",
        ),
        WorkspaceSummaryFact("Следующий шаг", _safe_text(snapshot.suggested_next_step, fallback="Откройте results center или compare viewer."), snapshot.suggested_next_detail),
    )
    evidence_lines = _dedupe_lines(
        artifact_lines,
        tuple(str(line) for line in snapshot.anim_summary_lines[:4]),
        tuple(str(line) for line in snapshot.operator_recommendations[:4]),
    )
    return WorkspaceSummaryState(
        headline=_safe_text(snapshot.suggested_next_step, fallback="Последние results artifacts готовы к анализу"),
        detail=_safe_text(snapshot.suggested_next_detail, fallback="Откройте compare, animator или diagnostics в зависимости от latest artifacts."),
        facts=facts,
        evidence_lines=evidence_lines,
    )


def build_diagnostics_workspace_summary(
    repo_root: Path,
    *,
    python_executable: str | None = None,
) -> WorkspaceSummaryState:
    del python_executable
    bundle = load_desktop_diagnostics_bundle_record(repo_root)
    run_record = load_last_desktop_diagnostics_run_record(repo_root / "diagnostics")

    headline = _safe_text(bundle.latest_zip_name, fallback="Последний diagnostics bundle пока не найден")
    detail = _safe_text(bundle.clipboard_message, fallback="Bundle lane должен оставаться доступным из любого workspace.")
    run_status = "запусков пока нет"
    run_detail = "Команда запуска диагностики ещё не сохраняла state."
    if run_record is not None:
        run_status = f"{_safe_text(run_record.status, fallback='run')} | ok={bool(run_record.ok)}"
        run_detail = _safe_text(run_record.last_message, fallback=_path_text(run_record.run_dir) or "Последний запуск сохранён без текстового сообщения.")

    validation_state = "нет свежей проверки"
    if bundle.latest_validation_json_path or bundle.latest_validation_md_path:
        validation_state = _path_name(bundle.latest_validation_json_path or bundle.latest_validation_md_path)

    facts = (
        WorkspaceSummaryFact("Последний ZIP", headline, _path_text(bundle.latest_zip_path) or "ZIP ещё не собран."),
        WorkspaceSummaryFact("Каталог bundle lane", _safe_text(bundle.out_dir), "Этот каталог используется как always-visible diagnostics lane."),
        WorkspaceSummaryFact("Последняя проверка bundle", validation_state, _path_text(bundle.latest_inspection_md_path) or "inspection report пока не найден."),
        WorkspaceSummaryFact(
            "Clipboard / handoff",
            "готово" if bundle.clipboard_ok else "не подтверждено",
            detail,
        ),
        WorkspaceSummaryFact("Последний запуск диагностики", run_status, run_detail),
        WorkspaceSummaryFact(
            "Следующий шаг",
            "Собрать диагностику или проверить bundle",
            "Command search должен уметь открыть collect / verify / send flow из любого места shell.",
        ),
    )
    evidence_lines = _dedupe_lines(
        tuple(bundle.summary_lines[:6]),
        (
            f"Inspection JSON: {_path_text(bundle.latest_inspection_json_path)}",
            f"Health JSON: {_path_text(bundle.latest_health_json_path)}",
            f"Triage MD: {_path_text(bundle.latest_triage_md_path)}",
            f"Validation JSON: {_path_text(bundle.latest_validation_json_path)}",
            f"Run dir: {_path_text(run_record.run_dir) if run_record is not None else ''}",
            f"Run log: {_path_text(run_record.log_path) if run_record is not None else ''}",
        ),
    )
    return WorkspaceSummaryState(
        headline=headline,
        detail=detail,
        facts=facts,
        evidence_lines=evidence_lines,
    )
