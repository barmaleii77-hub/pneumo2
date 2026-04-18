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


def test_desktop_run_setup_center_surfaces_ho003_ho004_ho005_and_readonly_ring_refs() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_run_setup_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "suite_lineage_var" in src
    assert "HO-003 / HO-004 / HO-005" in src
    assert "WS-RING source hash" in src
    assert "Derived export-set hash" in src
    assert "ring_handoff_stale" in src
    assert "ring_stale_reasons" in src
    assert "segment_meta_ref" in src
    assert "read-only WS-RING refs" in src
    assert "edit geometry in Ring Editor / WS-RING source" in src

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

    assert "HO-003 / HO-004 / HO-005: inputs=current; ring=current; validated_suite_snapshot=stale" in status
    assert "WS-RING source hash=ssssssssssss" in status
    assert "Derived export-set hash=eeeeeeeeeeee" in status
    assert "ring_handoff_stale rows=ring_auto_full" in status
    assert "ring_source_hash_changed" in status
    assert "ring_export_set_hash_changed" in status
    assert rows[0][6] == "road_csv, axay_csv, scenario_json, segment_meta_ref"
    assert rows[0][7] == "source=ssssssssssss | export=eeeeeeeeeeee"
    assert rows[0][8] == "ring_handoff_stale=yes; ring_export_set_hash_changed, missing_refs=1"
