from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_run_setup_center_uses_workspace_layout_instead_of_long_vertical_page() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_run_setup_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'workspace = ttk.Panedwindow(outer, orient="horizontal")' in src
    assert 'context_box = ttk.LabelFrame(sidebar, text="Контекст", padding=8)' in src
    assert 'nav_box = ttk.LabelFrame(sidebar, text="Разделы", padding=8)' in src
    assert 'build_scrolled_treeview(' in src
    assert 'self.notebook = ttk.Notebook(content)' in src
    assert 'create_scrollable_tab(' in src
    assert 'self._build_profile_tab()' in src
    assert 'self._build_artifacts_tab()' in src
    assert 'footer = build_status_strip(' in src


def test_desktop_run_setup_center_uses_russian_operator_facing_sections() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_run_setup_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    suite_runtime_src = (ROOT / "pneumo_solver_ui" / "desktop_suite_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert '"Профиль запуска"' in src
    assert '"Предпросмотр дороги"' in src
    assert '"Режим расчёта"' in src
    assert '"Политики и выгрузка"' in src
    assert '"Результаты и журналы"' in src
    assert '"Кэш расчёта"' in src
    assert '"Политика выполнения"' in src
    assert '"Набор испытаний / HO-005"' in src
    assert '"validated_suite_snapshot / suite_snapshot_hash"' in src
    assert '"Заморозить HO-005"' in src
    assert '"Открыть validated_suite_snapshot.json"' in src
    assert '"Сбросить overrides"' in src
    assert "self._build_suite_tab()" in src
    assert "self.suite_tree = ttk.Treeview" in src
    assert '"Открыть набор NPZ"' in src
    assert '"Открыть сводку (JSON)"' in src
    assert '"Набор испытаний / HO-005"' in src
    assert "HO-003 inputs_snapshot" in suite_runtime_src
    assert "resolve_suite_inputs_handoff" in suite_runtime_src
    assert "can_consume" in suite_runtime_src
