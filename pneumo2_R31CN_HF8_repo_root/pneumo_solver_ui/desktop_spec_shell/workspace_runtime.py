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
from pneumo_solver_ui.optimization_baseline_source import build_baseline_center_surface


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


def _yes_no(value: Any) -> str:
    return "да" if bool(value) else "нет"


def _state_text(value: Any, *, fallback: str = "нет данных") -> str:
    raw = " ".join(str(value or "").replace("_", " ").split()).strip()
    if not raw:
        return fallback
    labels = {
        "artifacts-missing": "не хватает файлов результатов",
        "artifact missing": "не хватает файла результата",
        "artifacts missing": "не хватает файлов результатов",
        "blocked": "заблокировано",
        "coordinator": "распределённый режим",
        "done": "завершено",
        "enabled": "включено",
        "failed": "ошибка",
        "missing": "не найдено",
        "ok": "готово",
        "ready": "готово",
        "running": "выполняется",
        "stage runner": "поэтапный запуск",
        "staged": "поэтапный режим",
        "stale": "устарело",
    }
    return labels.get(raw.casefold(), raw)


def _operator_token_text(value: Any, *, fallback: str = "нет данных") -> str:
    text = _safe_text(value, fallback=fallback)
    replacements = (
        ("StageRunner", "поэтапный запуск"),
        ("stage_runner", "поэтапный запуск"),
        ("staged", "поэтапный режим"),
        ("coordinator", "распределённый режим"),
        ("metric_", ""),
        ("метрика_", ""),
        ("penalty_", "штраф "),
        ("штраф_", "штраф "),
        ("RMS", "RMS"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = " ".join(text.replace("_", " ").split())
    return text or fallback


def _operator_message_text(raw: Any) -> str:
    text = " ".join(str(raw or "").split()).strip()
    replacements = (
        ("Clipboard status is stale for the current latest bundle:", "Буфер обмена устарел для текущего последнего архива:"),
        ("Clipboard updated for latest bundle:", "Буфер обмена обновлён для последнего архива:"),
        ("no clipboard activity", "буфер обмена не использовался"),
        ("inspection", "проверка состава"),
        ("health", "состояние проекта"),
        ("validation", "проверка результата"),
        ("triage", "разбор предупреждений"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _operator_result_text(raw: Any) -> str:
    text = _operator_message_text(raw)
    replacements = (
        ("Optimizer scope gate", "Проверка области оптимизации"),
        ("Optimizer scope", "Область оптимизации"),
        ("optimizer scope artifacts are missing", "материалы области оптимизации не найдены"),
        ("Шлюз оптимизации", "Готовность оптимизации"),
        ("шлюз оптимизации", "готовность оптимизации"),
        ("Open browser perf evidence artifacts and refresh the trace; current evidence status is missing (WARN), bundle_ready=False.", "Откройте материалы проверки быстродействия интерфейса и обновите трассу; текущий статус: не найдено, предупреждение; архив не готов."),
        ("Browser perf evidence", "Проверка быстродействия интерфейса"),
        ("Browser perf comparison", "Сравнение быстродействия интерфейса"),
        ("browser perf evidence artifacts", "материалы проверки быстродействия интерфейса"),
        ("Open материалы проверки быстродействия интерфейса and refresh the trace; current evidence status is не найдено (предупреждение), архив готов=нет.", "Откройте материалы проверки быстродействия интерфейса и обновите трассу; текущий статус: не найдено, предупреждение; архив не готов."),
        ("Open материалы проверки быстродействия интерфейса", "Откройте материалы проверки быстродействия интерфейса"),
        ("and refresh the trace", "и обновите трассу"),
        ("current evidence status is", "текущее состояние"),
        ("Create or refresh a browser perf reference snapshot before marking performance review complete.", "Создайте или обновите эталонный снимок быстродействия интерфейса перед завершением проверки."),
        ("Rebuild the send-bundle after re-export so anim_latest is reproducible directly from the archive.", "Пересоберите архив отправки после повторного экспорта, чтобы последний результат анимации воспроизводился из архива."),
        ("send-bundle", "архив отправки"),
        ("anim_latest", "последний результат анимации"),
        ("release_gate", "готовность"),
        ("release_risk", "риск выдачи"),
        ("риск выпуска=", "риск для выдачи "),
        ("риск выпуска", "риск для выдачи"),
        ("bundle_ready", "архив готов"),
        ("архив готов=", "архив готов "),
        ("no_reference", "нет эталона"),
        ("trace_bundle_ready", "архив трассы готов"),
        ("regression_checked", "регрессия проверена"),
        ("MISSING", "не найдено"),
        ("missing", "не найдено"),
        ("WARN", "предупреждение"),
        ("FAIL", "ошибка"),
        ("PASS", "норма"),
        ("READY", "готово"),
        ("UNKNOWN", "не определено"),
        ("True", "да"),
        ("False", "нет"),
        ("true", "да"),
        ("false", "нет"),
        ("Проверка:", "Проверка результата -"),
        ("Разбор замечаний:", "Разбор замечаний -"),
        ("Последние прогоны:", "Последние прогоны -"),
        ("errors=", "ошибок "),
        ("warnings=", "предупреждений "),
        ("ошибок=", "ошибок "),
        ("предупреждений=", "предупреждений "),
        ("критичных=", "критичных "),
        ("справочных=", "справочных "),
        ("красных флагов=", "красных флагов "),
        ("автотест=", "автотест "),
        ("диагностика=", "диагностика "),
        ("ready=", "готовность "),
        ("ошибок:", "ошибок"),
        ("предупреждений:", "предупреждений"),
        ("критичных:", "критичных"),
        ("справочных:", "справочных"),
        ("красных флагов:", "красных флагов"),
        ("автотест:", "автотест"),
        ("диагностика:", "диагностика"),
        ("готово:", "готовность"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.replace(" / ", "; ").replace(" | ", "; ")
    text = text.replace("_", " ")
    return " ".join(text.split()).strip()


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
    ordered = [
        f"На стадии {_operator_token_text(key)} включено {int(value)} испытаний"
        for key, value in sorted(data.items())
    ]
    return "; ".join(ordered)


def _objective_text(values: tuple[str, ...] | list[str] | None) -> str:
    items = [_operator_token_text(item) for item in (values or ()) if str(item).strip()]
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
    try:
        baseline_surface = build_baseline_center_surface(workspace_dir=contract.workspace_dir)
    except Exception:
        baseline_surface = {}

    active = dict(baseline_surface.get("active_baseline") or {})
    suite_handoff = dict(baseline_surface.get("suite_handoff") or {})
    banner_state = dict(baseline_surface.get("banner_state") or {})
    mismatch_state = dict(baseline_surface.get("mismatch_state") or {})
    history_rows = tuple(dict(row) for row in baseline_surface.get("history_rows") or ())
    action_strip = dict(baseline_surface.get("action_strip") or {})

    active_state_raw = active.get("state")
    ho005_state_raw = suite_handoff.get("state")
    active_state = _state_text(active_state_raw, fallback="не найдено")
    ho005_state = _state_text(ho005_state_raw, fallback="не найдено")
    active_hash = str(active.get("active_baseline_hash") or "")
    suite_hash = str(active.get("suite_snapshot_hash") or suite_handoff.get("suite_snapshot_hash") or "")
    inputs_hash = str(active.get("inputs_snapshot_hash") or suite_handoff.get("inputs_snapshot_hash") or "")
    ring_hash = str(active.get("ring_source_hash") or suite_handoff.get("ring_source_hash") or "")
    policy_mode = _safe_text(active.get("policy_mode"), fallback="режим не выбран")
    source_run = _path_text(active.get("source_run_dir")) or "исходный запуск не указан"
    active_contract_path = _path_text(active.get("contract_path")) or "активный опорный прогон пока не найден"
    history_path = _path_text(baseline_surface.get("history_path")) or "история опорных прогонов пока не найдена"
    optimizer_can_consume = bool(active.get("optimizer_baseline_can_consume", False))
    baseline_label = (
        f"Опорный прогон {active_state}"
        if active_hash or str(active_state_raw or "").strip().casefold() != "missing"
        else "Активный опорный прогон не найден"
    )
    baseline_path = active_contract_path
    latest_result = (
        _operator_result_text(format_npz_summary(results_snapshot))
        if results_snapshot is not None
        else "Последний NPZ пока не найден."
    )
    recent_runs = (
        _operator_result_text(format_recent_runs_summary(results_snapshot))
        if results_snapshot is not None
        else "История последних прогонов пока не собрана."
    )
    suggested_next = (
        _operator_result_text(_safe_text(results_snapshot.suggested_next_step, fallback="Откройте базовый прогон и выполните расчёт."))
        if results_snapshot is not None
        else "Откройте базовый прогон и выполните расчёт."
    )
    suggested_detail = (
        _operator_result_text(_safe_text(results_snapshot.suggested_next_detail, fallback="После опорного прогона переходите в оптимизацию только из согласованного контекста."))
        if results_snapshot is not None
        else "После опорного прогона переходите в оптимизацию только из согласованного контекста."
    )
    mismatch_fields = tuple(str(field) for field in mismatch_state.get("mismatch_fields") or ())
    mismatch_text = (
        ", ".join(mismatch_fields)
        if mismatch_fields
        else _state_text(mismatch_state.get("state"), fallback="расхождение активного прогона и истории не выбрано")
    )
    action_labels = {"review": "просмотр", "adopt": "принять", "restore": "восстановить"}
    state_labels = {"enabled": "доступно", "blocked": "заблокировано", "read-only": "только просмотр"}
    allowed_actions = []
    for action_name in ("review", "adopt", "restore"):
        action = dict(action_strip.get(action_name) or {})
        state = "enabled" if bool(action.get("enabled", False)) else "blocked"
        if action_name == "review" and bool(action.get("read_only", False)):
            state = "read-only"
        allowed_actions.append(f"{action_labels.get(action_name, action_name)} - {state_labels.get(state, state)}")

    facts = (
        WorkspaceSummaryFact(
            "Снимок набора и активный опорный прогон",
            f"Набор испытаний {ho005_state}. Опорный прогон {active_state}.",
            _safe_text(banner_state.get("banner"), fallback="Базовый прогон ждёт просмотра, принятия или восстановления."),
        ),
        WorkspaceSummaryFact(
            "Активный опорный прогон",
            baseline_label,
            (
                f"Метка прогона - {active_hash[:12]}. "
                f"Оптимизатор может использовать его: {_yes_no(optimizer_can_consume)}."
                if active_hash
                else f"Метка прогона пока отсутствует. Оптимизатор может использовать его: {_yes_no(optimizer_can_consume)}."
            ),
        ),
        WorkspaceSummaryFact(
            "Зафиксированный контекст",
            f"Набор испытаний - {suite_hash[:12] or '—'}. Исходные данные - {inputs_hash[:12] or '—'}. Сценарий - {ring_hash[:12] or '—'}.",
            f"Режим работы: {_operator_token_text(policy_mode)}.",
        ),
        WorkspaceSummaryFact(
            "История опорных прогонов",
            f"В истории {len(history_rows)} записей. Выбранная запись: {_safe_text(baseline_surface.get('selected_history_id'), fallback='нет')}.",
            f"Сверка истории: {mismatch_text}.",
        ),
        WorkspaceSummaryFact(
            "Действия с опорным прогоном",
            ". ".join(allowed_actions) + ".",
            "Принятие и восстановление применяются только после явного выбора; молчаливая подмена запрещена.",
        ),
        WorkspaceSummaryFact(
            "Задача расчёта",
            f"{_operator_token_text(contract.problem_hash_mode, fallback='режим не выбран')}; {_safe_text(contract.problem_hash, fallback='контроль не найден')}",
            f"Файл модели расположен здесь - {contract.model_path}",
        ),
        WorkspaceSummaryFact(
            "Пространство параметров",
            f"Базовых параметров {int(contract.base_param_count)}. В переборе участвуют {int(contract.search_param_count)}.",
            f"Расширенных диапазонов {int(contract.widened_range_count)}. Технических параметров, скрытых от запуска, {int(contract.removed_runtime_knob_count)}.",
        ),
        WorkspaceSummaryFact(
            "Набор испытаний",
            f"Включено {int(contract.enabled_suite_total)} из {int(contract.suite_row_count)} испытаний.",
            _stage_counts_text(contract.enabled_stage_counts),
        ),
        WorkspaceSummaryFact("Последний результат", latest_result, recent_runs),
        WorkspaceSummaryFact("Рекомендуемый следующий шаг", suggested_next, suggested_detail),
    )
    evidence_lines = _dedupe_lines(
        (
            f"Активный опорный прогон - {active_contract_path}",
            f"История опорных прогонов - {history_path}",
            f"Предупреждение - {_safe_text(banner_state.get('banner'), fallback='нет предупреждений')}",
            f"Сверка - {mismatch_text}",
            f"Набор испытаний - {contract.suite_json_path}",
            f"Диапазоны оптимизации - {contract.ranges_json_path}",
            f"Исполнитель расчёта - {contract.worker_path}",
        ),
        (
            f"Последний NPZ - {_path_text(results_snapshot.latest_npz_path) if results_snapshot is not None else ''}",
            f"Последняя проверка - {_path_text(results_snapshot.latest_validation_json_path) if results_snapshot is not None else ''}",
        ),
    )
    return WorkspaceSummaryState(
        headline=baseline_label,
        detail=_safe_text(banner_state.get("banner"), fallback=baseline_path),
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
            detail="Не удалось собрать сводку исходных данных для главного окна.",
            facts=(
                WorkspaceSummaryFact(
                    "Состояние",
                    "сводка недоступна",
                    _safe_text(exc, fallback="Проверьте desktop_input_model и рабочую копию входных данных."),
                ),
                WorkspaceSummaryFact(
                    "Следующий шаг",
                    "Откройте исходные данные отдельным окном",
                    "После восстановления можно вернуться в рабочий шаг исходных данных и продолжить работу в главном окне.",
                ),
            ),
            evidence_lines=(
                f"Рабочая копия: {_path_text(default_working_copy_path())}",
                f"Эталонный JSON: {_path_text(default_base_json_path())}",
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
        "Исходные данные готовы к следующему шагу"
        if warn_count == 0
        else f"Требуют внимания {warn_count} кластеров исходных данных"
    )
    detail = (
        "Рабочая копия, эталон и готовность кластеров собраны прямо в главном окне."
        if warn_count == 0
        else f"Проверьте кластеры: {_preview_list(warn_titles, empty='нет предупреждений')}."
    )

    facts = (
        WorkspaceSummaryFact(
            "Рабочая копия",
            _path_name(working_copy_path, fallback="desktop_input_base.json"),
            _path_text(working_copy_path) or "Файл рабочей копии пока не найден.",
        ),
        WorkspaceSummaryFact(
            "Эталон исходных данных",
            _path_name(base_json_path, fallback="default_base.json"),
            _path_text(base_json_path) or "Эталонный файл исходных данных пока не найден.",
        ),
        WorkspaceSummaryFact(
            "Готовность кластеров",
            f"Готовы {ok_count} кластеров. Требуют внимания {warn_count}.",
            (
                "Все ключевые кластеры выглядят готовыми к переходу в сценарии и набор испытаний."
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
                empty="Замечаний по кластерам сейчас нет.",
            ),
        ),
        WorkspaceSummaryFact(
            "Изменения относительно эталона",
            f"изменённых кластеров: {len(changed_sections)}; параметров: {changed_total}",
            (
                "Рабочая копия совпадает с эталоном."
                if not changed_sections
                else f"Изменены кластеры: {_preview_list(changed_sections, empty='без изменений')}."
            ),
        ),
        WorkspaceSummaryFact(
            "Профили и снимки",
            f"профилей: {len(profile_paths)}; снимков: {len(snapshot_paths)}",
            f"Профили: {_path_text(profile_dir)} | Снимки: {_path_text(snapshot_dir)}",
        ),
        WorkspaceSummaryFact(
            "Следующий шаг",
            (
                "Переходите к редактору циклического сценария"
                if warn_count == 0
                else "Сначала разберите предупреждения в исходных данных или откройте исходные данные отдельным окном"
            ),
            "После стабилизации исходных данных переходите в сценарии, затем в набор испытаний и опорный прогон.",
        ),
    )
    evidence_lines = _dedupe_lines(
        (
            f"Рабочая копия: {_path_text(working_copy_path)}",
            f"Эталонный JSON: {_path_text(base_json_path)}",
            f"Папка профилей: {_path_text(profile_dir)}",
            f"Папка снимков: {_path_text(snapshot_dir)}",
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

    active_job = "нет активного задания"
    active_job_detail = "Одновременно допускается только один активный способ выполнения: основной расчёт или расширенный распределённый расчёт."
    if current_job is not None:
        active_job = f"{_operator_token_text(current_job.backend, fallback='исполнитель не выбран')}; {_path_name(current_job.run_dir)}"
        active_job_detail = (
            f"Режим выполнения: {_state_text(current_job.pipeline_mode, fallback='не выбран')}. "
            f"Бюджет запуска: {int(getattr(current_job, 'budget', 0) or 0)}."
        )

    pointer_value = "последний запуск оптимизации пока не найден"
    pointer_detail = "Сначала нужен завершённый или выбранный запуск в истории."
    if bool(pointer.get("exists")):
        pointer_value = f"{_state_text(pointer.get('status_label'), fallback='запуск')}; {_safe_text(pointer.get('run_name'), fallback='запуск')}"
        pointer_detail = (
            f"Исполнитель: {_operator_token_text(pointer.get('backend'), fallback='не выбран')}. "
            f"В таблице {int(pointer.get('rows') or 0)} строк, готово {int(pointer.get('done_count') or 0)}, ошибок {int(pointer.get('error_count') or 0)}."
        )

    facts = (
        WorkspaceSummaryFact(
            "Рекомендуемый путь",
            "Основной расчёт — главный режим",
            "Распределённый режим остаётся расширенной настройкой и не должен становиться вторым параллельным основным запуском.",
        ),
        WorkspaceSummaryFact(
            "Цели оптимизации",
            _objective_text(contract.objective_keys),
            f"Ограничение - {_operator_token_text(contract.penalty_key, fallback='не задано')} не выше {float(contract.penalty_tol):g}",
        ),
        WorkspaceSummaryFact(
            "Происхождение опорного прогона",
            f"Состояние опорного прогона - {_state_text(contract.active_baseline_state, fallback='не найдено')}.",
            (
                f"Метка прогона - {str(contract.active_baseline_hash or '')[:12]}. "
                f"Оптимизатор может использовать его: {_yes_no(contract.optimizer_baseline_can_consume)}."
                if str(contract.active_baseline_hash or "")
                else f"Метка прогона пока отсутствует. Оптимизатор может использовать его: {_yes_no(contract.optimizer_baseline_can_consume)}."
            ),
        ),
        WorkspaceSummaryFact(
            "Набор и стадии",
            f"Включено {int(contract.enabled_suite_total)} из {int(contract.suite_row_count)} испытаний.",
            _stage_counts_text(contract.enabled_stage_counts),
        ),
        WorkspaceSummaryFact(
            "Пространство поиска",
            f"Базовых параметров {int(contract.base_param_count)}. В переборе участвуют {int(contract.search_param_count)}.",
            f"Расширенных диапазонов {int(contract.widened_range_count)}. Технических параметров, скрытых от запуска, {int(contract.removed_runtime_knob_count)}.",
        ),
        WorkspaceSummaryFact("Активное задание", active_job, active_job_detail),
        WorkspaceSummaryFact("Последний запуск оптимизации", pointer_value, pointer_detail),
    )
    evidence_lines = _dedupe_lines(
        (
            f"Модель - {contract.model_path}",
            f"Исходные данные - {contract.base_json_path}",
            f"Диапазоны оптимизации - {contract.ranges_json_path}",
            f"Набор испытаний - {contract.suite_json_path}",
            f"Настройка стадий - {contract.stage_tuner_json_path or 'не используется'}",
        ),
        (
            f"Папка последнего запуска - {_safe_text(pointer.get('run_dir'), fallback='')}",
            f"Результат последнего запуска - {_safe_text(pointer.get('result_path'), fallback='')}",
        ),
    )
    return WorkspaceSummaryState(
        headline="Оптимизация готова к управляемому запуску",
        detail="Окно держит цели оптимизации, обязательные проверки и происхождение опорного прогона рядом с запуском.",
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
            detail="Не удалось прочитать последние файлы результатов. Откройте анализ результатов или диагностику и обновите данные.",
            facts=(
                WorkspaceSummaryFact(
                    "Состояние",
                    "нет свежего снимка",
        "Сводка результатов собирается из отправленных файлов, проверок и диагностики.",
                ),
            ),
        )

    artifact_lines = tuple(
        f"{_operator_result_text(artifact.title)}: {artifact.path}"
        for artifact in snapshot.recent_artifacts[:6]
    )
    facts = (
        WorkspaceSummaryFact(
            "Проверка результата",
            _operator_result_text(format_validation_summary(snapshot)),
            _operator_result_text(snapshot.suggested_next_detail),
        ),
        WorkspaceSummaryFact(
            "Готовность оптимизации",
            _operator_result_text(format_optimizer_gate_summary(snapshot)),
            "Проверка должна быть видима прямо в анализе результатов.",
        ),
        WorkspaceSummaryFact(
            "Разбор предупреждений",
            _operator_result_text(format_triage_summary(snapshot)),
            _operator_result_text(
                _safe_text(
                    snapshot.triage_red_flags[0] if snapshot.triage_red_flags else "",
                    fallback="Красных флагов сейчас нет.",
                )
            ),
        ),
        WorkspaceSummaryFact(
            "Последний NPZ",
            _operator_result_text(format_npz_summary(snapshot)),
            _operator_result_text(format_recent_runs_summary(snapshot)),
        ),
        WorkspaceSummaryFact(
            "Анимация и мнемосхема",
            f"Текущий режим мнемосхемы: {_operator_token_text(snapshot.mnemo_current_mode, fallback='нет данных')}.",
            _operator_result_text(", ".join(snapshot.mnemo_recent_titles[:3])) if snapshot.mnemo_recent_titles else "Недавние события мнемосхемы пока не найдены.",
        ),
        WorkspaceSummaryFact(
            "Следующий шаг",
            _operator_result_text(_safe_text(snapshot.suggested_next_step, fallback="Откройте анализ результатов или окно сравнения.")),
            _operator_result_text(snapshot.suggested_next_detail),
        ),
    )
    evidence_lines = _dedupe_lines(
        artifact_lines,
        tuple(_operator_result_text(line) for line in snapshot.anim_summary_lines[:4]),
        tuple(_operator_result_text(line) for line in snapshot.operator_recommendations[:4]),
    )
    return WorkspaceSummaryState(
        headline=_operator_result_text(_safe_text(snapshot.suggested_next_step, fallback="Последние результаты готовы к анализу")),
        detail=_operator_result_text(_safe_text(snapshot.suggested_next_detail, fallback="Откройте сравнение, анимацию или диагностику в зависимости от найденных файлов.")),
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

    headline = _safe_text(bundle.latest_zip_name, fallback="Последний архив диагностики пока не найден")
    detail = _safe_text(
        _operator_message_text(bundle.clipboard_message),
        fallback="Диагностика должна оставаться доступной из любого окна.",
    )
    run_status = "запусков пока нет"
    run_detail = "Команда запуска диагностики ещё не сохраняла состояние."
    if run_record is not None:
        run_status = f"Последний запуск: {_safe_text(run_record.status, fallback='запуск')}. Завершён успешно: {'да' if bool(run_record.ok) else 'нет'}."
        run_detail = _safe_text(run_record.last_message, fallback=_path_text(run_record.run_dir) or "Последний запуск сохранён без текстового сообщения.")

    validation_state = "нет свежей проверки"
    if bundle.latest_validation_json_path or bundle.latest_validation_md_path:
        validation_state = _path_name(bundle.latest_validation_json_path or bundle.latest_validation_md_path)

    facts = (
        WorkspaceSummaryFact("Последний архив", headline, _path_text(bundle.latest_zip_path) or "Архив диагностики ещё не собран."),
        WorkspaceSummaryFact("Папка файлов диагностики", _safe_text(bundle.out_dir), "Эта папка используется для архива диагностики, отчётов и файлов проверки."),
        WorkspaceSummaryFact("Последняя проверка архива", validation_state, _path_text(bundle.latest_inspection_md_path) or "Отчёт о составе архива пока не найден."),
        WorkspaceSummaryFact(
            "Буфер обмена",
            "готово" if bundle.clipboard_ok else "не подтверждено",
            detail,
        ),
        WorkspaceSummaryFact("Последний запуск диагностики", run_status, run_detail),
        WorkspaceSummaryFact(
            "Следующий шаг",
            "Собрать диагностику или проверить архив",
            "Быстрый поиск должен открывать сбор, проверку и отправку из любого места основного окна.",
        ),
    )
    evidence_lines = _dedupe_lines(
        tuple(_operator_message_text(line) for line in bundle.summary_lines[:6]),
        (
            f"Состав архива JSON: {_path_text(bundle.latest_inspection_json_path)}",
            f"Состояние проекта JSON: {_path_text(bundle.latest_health_json_path)}",
            f"Разбор предупреждений MD: {_path_text(bundle.latest_triage_md_path)}",
            f"Проверка результата JSON: {_path_text(bundle.latest_validation_json_path)}",
            f"Папка запуска: {_path_text(run_record.run_dir) if run_record is not None else ''}",
            f"Журнал запуска: {_path_text(run_record.log_path) if run_record is not None else ''}",
        ),
    )
    return WorkspaceSummaryState(
        headline=headline,
        detail=detail,
        facts=facts,
        evidence_lines=evidence_lines,
    )
