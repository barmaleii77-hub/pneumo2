from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.tools.desktop_run_setup_center import DesktopRunSetupCenter


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_run_setup_center_uses_workspace_layout_instead_of_long_vertical_page() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_run_setup_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'workspace = ttk.Panedwindow(outer, orient="horizontal")' in src
    assert 'context_box = ttk.LabelFrame(sidebar, text="Что выбрано", padding=8)' in src
    assert 'nav_box = ttk.LabelFrame(sidebar, text="Настройки расчёта", padding=8)' in src
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
    assert '"Поведение и выгрузка"' in src
    assert '"Результаты и журналы"' in src
    assert '"Повторное использование расчётов"' in src
    assert '"Поведение при предупреждениях"' in src
    assert '"Набор испытаний"' in src
    assert '"Состояние набора испытаний"' in src
    assert '"Зафиксировать набор"' in src
    assert '"Открыть снимок набора"' in src
    assert '"Открыть папку набора"' in src
    assert '"Сбросить ручные изменения"' in src
    assert "self._build_suite_tab()" in src
    assert "self.suite_tree = ttk.Treeview" in src
    assert '"Открыть файл анимации"' in src
    assert '"Открыть сводку"' in src
    assert '"Открыть снимок набора (JSON)"' not in src
    assert '"Открыть набор NPZ"' not in src
    assert '"Открыть сводку (JSON)"' not in src
    assert '"Набор испытаний"' in src
    assert '"Служебные папки и журналы"' not in src
    assert '"Флаги запуска"' not in src
    assert '"Контекст"' not in src
    assert '"Разделы"' not in src
    assert '"Политики и выгрузка"' not in src
    assert "Снимок исходных данных" in suite_runtime_src
    assert "resolve_suite_inputs_handoff" in suite_runtime_src
    assert "can_consume" in suite_runtime_src


def test_desktop_run_setup_center_surfaces_ho003_ho004_ho005_and_readonly_ring_refs() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_run_setup_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "suite_lineage_var" in src
    assert "Исходные данные:" in src
    assert "Снимок колец:" in src
    assert "Экспорт колец:" in src
    assert "ring_handoff_stale" in src
    assert "ring_stale_reasons" in src
    assert "segment_meta_ref" in src
    assert "исходные файлы" in src
    assert "контрольные суммы" in src
    assert "Геометрия колец используется только для чтения" in src

    block = src[src.index("def _build_suite_tab"): src.index("def _build_launch_tab")]
    assert "ttk.Entry" not in block
    assert "ttk.Combobox" not in block


def test_desktop_run_setup_center_formats_suite_lineage_and_stale_rows() -> None:
    context = {
        "inputs_context": {
            "state": "current",
            "payload_hash": "i" * 64,
        },
        "ring_context": {
            "state": "current",
            "source_hash": "s" * 64,
            "source_ref": {
                "ring_export_set_hash_sha256": "e" * 64,
            },
        },
        "existing_state": {
            "state": "stale",
            "stale_reasons": ["ring_source_hash_changed"],
        },
        "snapshot": {
            "suite_snapshot_hash": "h" * 64,
            "validation": {
                "missing_refs": [{"row": "ring_auto_full"}],
            },
            "suite_rows": [
                {
                    "enabled": True,
                    "name": "ring_auto_full",
                    "stage": 2,
                    "type": "maneuver_csv",
                    "dt": 0.003,
                    "t_end": 12.0,
                    "road_csv": "road.csv",
                    "axay_csv": "axay.csv",
                    "scenario_json": "scenario.json",
                    "segment_meta_ref": "meta.json",
                    "ring_source_hash_sha256": "s" * 64,
                    "ring_export_set_hash_sha256": "e" * 64,
                    "ring_handoff_stale": True,
                    "ring_stale_reasons": ["ring_export_set_hash_changed"],
                }
            ],
        },
    }

    status = DesktopRunSetupCenter._suite_lineage_status_text(context)
    rows = DesktopRunSetupCenter._suite_preview_rows(context)

    assert "Исходные данные: актуально; сценарии колец: актуально; снимок набора: устарело" in status
    assert "Снимок колец: ssssssssssss" in status
    assert "Экспорт колец: eeeeeeeeeeee" in status
    assert "Устаревшие строки: ring_auto_full" in status
    assert "изменился исходный сценарий" in status
    assert "изменилась выгрузка сценария" in status
    assert rows[0][6] == "road_csv, axay_csv, scenario_json, segment_meta_ref"
    assert rows[0][7] == "источник=ssssssssssss | экспорт=eeeeeeeeeeee"
    assert rows[0][8] == "устарело: да; изменилась выгрузка сценария, не хватает ссылок: 1"
