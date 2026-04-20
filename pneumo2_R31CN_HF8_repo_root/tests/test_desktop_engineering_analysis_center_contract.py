from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def test_engineering_analysis_center_uses_ttk_panedwindow_actions_status_and_log() -> None:
    src = _read("pneumo_solver_ui/tools/desktop_engineering_analysis_center.py")
    runtime_src = _read("pneumo_solver_ui/desktop_engineering_analysis_runtime.py")

    assert "class DesktopEngineeringAnalysisCenter" in src
    assert "DesktopEngineeringAnalysisRuntime" in src
    assert 'workspace = ttk.Panedwindow(self, orient="horizontal")' in src
    for label in (
        "Обновить данные",
        "Открыть выбранный файл",
        "Зафиксировать прогон",
        "Подготовить материалы отправки",
        "Открыть материалы отправки",
        "Влияние системы",
        "Полный отчёт",
        "Диапазоны влияния",
        "Открыть проверку и отправку",
        "Что открыть",
        "Открыть выбранное",
    ):
        assert label in src
    assert "threading.Thread" in src
    assert 'text="Обновить"' not in src
    assert "ttk.Progressbar" in src
    assert "status_var" in src
    assert "log_text" in src
    assert "def _run_system_influence" in src
    assert "def _run_full_report" in src
    assert "def _run_param_staging" in src
    assert "def _export_selected_run_contract_bridge" in src
    assert "discover_selected_run_candidates" in src
    assert "_candidate_by_iid" in src
    assert "Прогоны оптимизации для выбора" in src
    assert "candidate_ready_only_var" in src
    assert "ttk.Checkbutton" in src
    assert "Только готовые" in src
    assert "def _refresh_candidate_filter" in src
    assert "в списке" in src
    assert "def _selected_candidate_run_dir" in src
    assert "bridge_status" in src
    assert 'label == "Зафиксировать выбранный прогон" and result.ok' in src
    assert "def _auto_export_evidence_after_ho007" in src
    assert "write_diagnostics_evidence_manifest" in src
    assert "Материалы проверки и отправки подготовлены автоматически" in src
    assert "def _open_evidence_manifest" in src
    assert "Материалы проверки и отправки открыты" in src
    assert "Подготовить материалы отправки" in src
    assert "compare_influence_surface_count" in src
    assert "def _compare_surface_details" in src
    assert "def _compare_surface_preview_for_artifact" in src
    assert "compare_influence_surface_preview" in src
    assert "compare_influence_surface_for_artifact" in src
    assert "validated_artifacts_summary" in src
    assert '"validated_artifacts"' in src
    assert "Проверенные файлы" in src
    assert "Порядок работы и замечания" in src
    assert "analysis_workspace_pipeline_status" in src
    assert "analysis_workspace_runtime_gaps" in src
    assert '"analysis_workspace_pipeline"' in src
    assert '"runtime_data_gaps"' in src
    assert "Калибровка" in src
    assert "Влияние и сравнение" in src
    assert "Чувствительность и неопределённость" in src
    assert "Аниматор и отправка" in src
    assert "Предпросмотр графиков и таблиц" in src
    assert "Графики влияния" in src
    assert "Табличные файлы" in src
    assert "Таблица данных" in src
    assert "CSV-таблица" not in src
    assert "метка: {snapshot.diagnostics_evidence_manifest_hash[:12] or '-'}" in src
    assert "код: {snapshot.diagnostics_evidence_manifest_hash[:12] or '-'}" not in src
    assert "analysis_workspace_chart_table_preview" in src
    assert '"analysis_chart_table_preview"' in src
    assert "Связь с окном сравнения" in runtime_src
    assert "Связь с центром результатов" in runtime_src
    assert "Выбранный прогон для анализа" in runtime_src
    assert "Калибровочный запуск" in runtime_src
    assert "Статическая настройка" in runtime_src
    assert "Неопределённость и приоритет измерений" in runtime_src
    assert "Материалы проверки и отправки" in runtime_src
    assert "analysis_compare_handoff_summary" in src
    assert "analysis_results_boundary_summary" in src
    assert '"compare_viewer_handoff_summary"' in src
    assert '"results_center_boundary_summary"' in src
    assert "animator_handoff_summary" in src
    assert "compare_influence_diagnostics" in src
    assert "missing_required_artifacts" in src
    assert "missing_required_artifact" in src
    assert "Обязательные файлы готовы" in src
    assert "filedialog.askdirectory" in src
    assert "Инженерный анализ готов." in src
    for forbidden in (
        "Центр инженерного анализа готов",
        "Открыть артефакт",
        "Открыть выбранный артефакт",
        "Открыть выбранный прогон",
        "Открыть связь анализа с аниматором",
        "Открыть данные для анимации",
        "Открыть контекст анимации",
        "Показать выбранный файл",
        "Показать выбранное",
        "Показать диагностику",
        "Собрать диагностику",
        "Подготовить диагностику",
        "Материалы диагностики",
        "Аниматор и диагностика",
        "Диагностические данные",
        "Проверенные артефакты",
        "Табличные артефакты",
        "Маршрут рабочего места",
        "Обязательные артефакты готовы",
        "статус:",
        "Команда процесса",
        "Идентификатор процесса",
        'text="Открыть файл"',
        'text="Открыть"',
        "Быстро открыть",
    ):
        assert forbidden not in src
    for forbidden in (
        "HO-007 selected-run context",
        "Master selected-run contract consumed by WS-ANALYSIS.",
        "Autopilot v20 calibration pipeline",
        "Autopilot wrapper evidence was found.",
        "Calibration fit reports",
        "Full/final calibration reports and fit evidence",
        "Static-trim result evidence",
        "Static-trim evidence is blocked",
        "System influence report",
        "System influence artifacts",
        "Influence-guided staging",
        "Compare influence surfaces",
        "Sensitivity summary",
        "Uncertainty/UQ artifacts",
        "Optional UQ advisor outputs",
        "Compare Viewer boundary",
        "Results Center boundary",
        "HO-008 Animator handoff",
        "HO-009 Diagnostics evidence manifest",
        "Diagnostics/SEND handoff",
        "Материалы диагностики",
        "диагностическим признакам",
        "для диагностики и отправки",
        "workspace/handoffs/WS-ANALYSIS",
        "send_bundles/latest_engineering_analysis_evidence_manifest.json",
    ):
        assert forbidden not in runtime_src


def test_engineering_analysis_shell_discovery_is_wired_to_module_and_aliases() -> None:
    spec_registry = _read("pneumo_solver_ui/desktop_spec_shell/registry.py")
    legacy_registry = _read("pneumo_solver_ui/desktop_shell/registry.py")
    legacy_contracts = _read("pneumo_solver_ui/desktop_shell/contracts.py")
    adapter = _read("pneumo_solver_ui/desktop_shell/adapters/desktop_engineering_analysis_center_adapter.py")

    assert "analysis.engineering.open" in spec_registry
    assert "pneumo_solver_ui.tools.desktop_engineering_analysis_center" in spec_registry
    assert "analysis.influence_and_exploration" in spec_registry
    for alias in (
        "engineering analysis",
        "calibration",
        "influence",
        "sensitivity",
        "system influence",
        "калибровка",
        "влияние",
        "чувствительность",
    ):
        assert alias in spec_registry
        assert alias in legacy_contracts

    assert "build_desktop_engineering_analysis_center_spec" in legacy_registry
    assert "desktop_engineering_analysis_center" in adapter
    assert "DesktopEngineeringAnalysisRuntime" in adapter
    assert "DesktopEngineeringAnalysisCenter(parent, runtime=runtime)" in adapter
    assert "host=parent" not in adapter
    assert "hosted=True" not in adapter


def test_engineering_analysis_hosted_adapter_uses_current_center_constructor(monkeypatch) -> None:
    from pneumo_solver_ui.desktop_shell.adapters import (
        desktop_engineering_analysis_center_adapter as adapter,
    )

    calls: dict[str, object] = {}

    class FakeRuntime:
        def __init__(self, *, repo_root, python_executable) -> None:
            calls["runtime_repo_root"] = repo_root
            calls["runtime_python_executable"] = python_executable

    class FakeCenter:
        def __init__(self, master, *, runtime) -> None:
            calls["center_master"] = master
            calls["center_runtime"] = runtime

    monkeypatch.setattr(adapter, "DesktopEngineeringAnalysisRuntime", FakeRuntime)
    monkeypatch.setattr(adapter, "DesktopEngineeringAnalysisCenter", FakeCenter)

    center = adapter.create_hosted_engineering_analysis_center("host-parent")

    assert isinstance(center, FakeCenter)
    assert calls["center_master"] == "host-parent"
    assert isinstance(calls["center_runtime"], FakeRuntime)
    assert Path(calls["runtime_repo_root"]).name == "pneumo2_R31CN_HF8_repo_root"


def test_engineering_analysis_send_bundle_sources_reference_expected_artifacts() -> None:
    make_bundle = _read("pneumo_solver_ui/tools/make_send_bundle.py")
    evidence = _read("pneumo_solver_ui/tools/send_bundle_evidence.py")
    validate = _read("pneumo_solver_ui/tools/validate_send_bundle.py")
    inspect = _read("pneumo_solver_ui/tools/inspect_send_bundle.py")

    assert "ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME" in make_bundle
    assert "ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME" in make_bundle
    assert "BND-021" in evidence
    assert "if engineering analysis used" in evidence
    assert "release_blocking_if_missing\": False" in evidence
    assert "engineering_analysis_evidence" in validate
    assert "has_engineering_analysis_evidence" in inspect
