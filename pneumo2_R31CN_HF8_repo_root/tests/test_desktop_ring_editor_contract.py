from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.desktop_ring_editor_panels import RoadPanel
from pneumo_solver_ui.desktop_ring_editor_model import (
    apply_ring_preset,
    apply_segment_preset_to_selected,
    build_default_ring_spec,
    create_editor_state,
    insert_segment_preset_after_selection,
    list_ring_preset_names,
    list_segment_preset_names,
    resolve_ring_inputs_handoff,
)
from pneumo_solver_ui.desktop_input_model import (
    desktop_input_payload_hash,
    desktop_inputs_snapshot_handoff_path,
    load_base_defaults,
    save_desktop_inputs_snapshot,
)
from pneumo_solver_ui.desktop_ring_editor_runtime import (
    build_ring_bundle_optimization_preview,
    build_ring_bundle_optimization_suite_preview,
    build_ring_editor_diagnostics,
    export_ring_scenario_bundle,
    materialize_ring_bundle_optimization_suite,
    mirror_ring_bundle_to_anim_latest_exports,
)
from pneumo_solver_ui.tools.desktop_ring_scenario_editor import DesktopRingScenarioEditor


ROOT = Path(__file__).resolve().parents[1]


class _FakeRoot:
    def __init__(self) -> None:
        self.bindings: dict[str, object] = {}
        self.protocols: dict[str, object] = {}
        self.destroy_called = False
        self._title = ""

    def bind(self, sequence: str, callback: object) -> None:
        self.bindings[sequence] = callback

    def protocol(self, name: str, callback: object) -> None:
        self.protocols[name] = callback

    def title(self, value: str | None = None) -> str:
        if value is not None:
            self._title = value
        return self._title

    def winfo_exists(self) -> int:
        return 1

    def destroy(self) -> None:
        self.destroy_called = True


class _FakeVar:
    def __init__(self, value: object) -> None:
        self.value = value

    def get(self) -> object:
        return self.value


def _canvas_texts(canvas: tk.Canvas) -> list[str]:
    texts: list[str] = []
    for item in canvas.find_all():
        if canvas.type(item) != "text":
            continue
        text = str(canvas.itemcget(item, "text") or "").strip()
        if text:
            texts.append(text)
    return texts


def _make_stub_editor(tmp_path: Path) -> DesktopRingScenarioEditor:
    editor = DesktopRingScenarioEditor.__new__(DesktopRingScenarioEditor)
    editor._owns_root = True
    editor._hosted = False
    editor.root = _FakeRoot()
    editor.repo_root = tmp_path
    editor.state = create_editor_state(output_dir=str(tmp_path))
    editor._loading_ui = False
    editor._queued_refresh = None
    editor._selected_event_index = None
    editor._host_closed = False
    editor._last_diagnostics = None
    editor._apply_form_to_state = lambda: None
    editor._refresh_from_state = lambda: None
    editor._queue_refresh = lambda: None
    editor._update_window_title = lambda: None
    return editor


def _write_inputs_snapshot_for_workspace(tmp_path: Path) -> tuple[dict[str, object], Path]:
    workspace = tmp_path / "workspace"
    payload = load_base_defaults()
    payload["база"] = 1.72
    payload["колея"] = 1.42
    target = desktop_inputs_snapshot_handoff_path(workspace_dir=workspace)
    saved = save_desktop_inputs_snapshot(payload, target_path=target)
    return payload, saved


def test_desktop_ring_editor_is_registered_as_standalone_hosted_tool() -> None:
    from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog
    from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs

    specs = build_desktop_shell_specs()
    by_key = {spec.key: spec for spec in specs}

    assert "desktop_ring_editor" in by_key
    spec = by_key["desktop_ring_editor"]
    assert spec.mode == "hosted"
    assert spec.group == "Встроенные окна"
    assert spec.primary is True
    assert spec.entry_kind == "main"
    assert spec.workflow_stage == "scenarios"
    assert spec.effective_workspace_role == "workspace"
    assert spec.effective_source_of_truth_role == "master"
    assert spec.standalone_module == "pneumo_solver_ui.tools.desktop_ring_scenario_editor"
    assert spec.create_hosted is not None
    assert "scenarios.handoff_ho004" in spec.capability_ids
    assert "suite.source_ring_export" in spec.capability_ids
    assert "calculation" in spec.launch_contexts
    assert "WS-RING" in spec.description
    assert "HO-004" in spec.description
    assert "без дополнительной навигации" in spec.details
    assert "ring_source_of_truth_json" in spec.details
    assert "derived/consumer handoff" in spec.details
    assert {"WS-RING", "HO-004", "HO-005", "source-of-truth", "validated suite"} <= set(
        spec.effective_search_aliases
    )
    for handoff_key in (
        "ring_source_of_truth_json",
        "ring_source_hash",
        "ring_export_set_hash",
        "scenario_json",
        "road_csv",
        "axay_csv",
        "meta_json",
        "validated_suite_snapshot",
        "suite_snapshot_hash",
    ):
        assert handoff_key in spec.effective_context_handoff_keys

    v38_path = ("desktop_input_editor", "desktop_ring_editor", "test_center", "desktop_optimizer_center")
    assert [by_key[key].workflow_stage for key in v38_path] == [
        "data",
        "scenarios",
        "calculation",
        "optimization",
    ]
    assert [by_key[key].nav_order for key in v38_path] == sorted(by_key[key].nav_order for key in v38_path)
    assert "suite.handoff_ho005" in by_key["test_center"].capability_ids
    assert "validated_suite_snapshot" in by_key["test_center"].effective_context_handoff_keys

    catalog_modules = {item.module for item in build_desktop_launch_catalog(include_mnemo=False)}
    assert "pneumo_solver_ui.tools.desktop_ring_scenario_editor" in catalog_modules


def test_ring_resolves_missing_inputs_snapshot_without_surrogate_inputs(tmp_path: Path) -> None:
    resolved = resolve_ring_inputs_handoff(workspace_dir=tmp_path / "workspace")

    assert resolved["handoff_id"] == "HO-002"
    assert resolved["target_workspace"] == "WS-RING"
    assert resolved["state"] == "missing"
    assert resolved["can_consume"] is False
    assert "surrogate inputs" in resolved["banner"]
    assert "inputs" not in resolved


def test_ring_consumes_only_frozen_inputs_snapshot_ref_and_detects_stale_hash(tmp_path: Path) -> None:
    payload, target = _write_inputs_snapshot_for_workspace(tmp_path)
    current_hash = desktop_input_payload_hash(payload)

    current = resolve_ring_inputs_handoff(
        workspace_dir=tmp_path / "workspace",
        current_inputs_snapshot_hash=current_hash,
    )
    stale = resolve_ring_inputs_handoff(
        workspace_dir=tmp_path / "workspace",
        current_inputs_snapshot_hash="different-inputs-hash",
    )

    assert current["state"] == "current"
    assert current["can_consume"] is True
    assert current["snapshot_path"] == str(target)
    assert current["payload_hash"] == current_hash
    assert current["ref"]["snapshot_ref"] == str(target)
    assert "inputs" not in current
    assert "inputs" not in current["ref"]
    assert stale["state"] == "stale"
    assert stale["can_consume"] is False
    assert "inputs_snapshot_hash_changed" in stale["stale_reasons"]


def test_root_desktop_ring_editor_wrappers_delegate_to_launcher() -> None:
    cmd = (ROOT / "START_DESKTOP_RING_EDITOR.cmd").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    vbs = (ROOT / "START_DESKTOP_RING_EDITOR.vbs").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    pyw = (ROOT / "START_DESKTOP_RING_EDITOR.pyw").read_text(
        encoding="utf-8",
        errors="replace",
    )
    py = (ROOT / "START_DESKTOP_RING_EDITOR.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "start_desktop_ring_editor.vbs" in cmd or "start_desktop_ring_editor.pyw" in cmd
    assert "wscript.shell" in vbs
    assert "start_desktop_ring_editor.pyw" in vbs
    assert 'Path(__file__).with_name("START_DESKTOP_RING_EDITOR.py")' in pyw
    assert "ensure_root_launcher_runtime" in py
    assert 'MODULE = "pneumo_solver_ui.tools.desktop_ring_scenario_editor"' in py


def test_desktop_ring_editor_modules_keep_panelized_architecture() -> None:
    tool_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_ring_scenario_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    panels_src = (ROOT / "pneumo_solver_ui" / "desktop_ring_editor_panels.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    runtime_src = (ROOT / "pneumo_solver_ui" / "desktop_ring_editor_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopRingScenarioEditor" in tool_src
    assert "SegmentListPanel" in tool_src
    assert "MotionPanel" in tool_src
    assert "RoadPanel" in tool_src
    assert "EventsPanel" in tool_src
    assert "DiagnosticsPanel" in tool_src
    assert "ExportPanel" in tool_src
    assert "PreviewPanel" in tool_src
    assert "def on_host_close(self) -> None:" in tool_src
    assert "Редактор кольцевых сценариев" in tool_src
    assert "Пресет кольца" in tool_src
    assert "Применить" in tool_src
    assert "Вставить сегмент" in tool_src
    assert "def _install_window_bindings" in tool_src
    assert 'WM_DELETE_WINDOW' in tool_src
    assert '"<Control-s>"' in tool_src
    assert '"<Control-o>"' in tool_src
    assert '"<F5>"' in tool_src
    assert "mirror_ring_bundle_to_anim_latest_exports" in tool_src
    assert "materialize_ring_bundle_optimization_suite" in tool_src
    assert "resolve_ring_inputs_handoff" in tool_src
    assert "_refresh_inputs_handoff_state" in tool_src
    assert "HO-002 inputs_snapshot" in tool_src
    assert "inputs_handoff_var" in tool_src
    assert "opt_workspace_var" in tool_src
    assert "opt_window_var" in tool_src
    assert "def _choose_opt_workspace_dir" in tool_src
    assert "def _open_opt_workspace_dir" in tool_src
    assert "def _open_opt_suite_dir" in tool_src
    assert "def _open_last_generated_spec" in tool_src
    assert "def _open_last_generated_road" in tool_src
    assert "def _open_last_generated_axay" in tool_src
    assert "def _open_last_generated_meta" in tool_src
    assert "def _open_ring_source_of_truth" in tool_src
    assert "def _open_anim_latest_exports" in tool_src
    assert "artifacts_stale" in tool_src
    assert "opt_suite_stale" in tool_src
    assert "WS-RING source state" in tool_src
    assert "Derived artifacts state" in tool_src
    assert "HO-005 suite link state" in tool_src
    assert "Длина кольца:" in tool_src
    assert "Post-policy seam:" in tool_src
    assert "WS-RING source hash" in tool_src
    assert "Derived export-set hash" in tool_src
    assert "build_ring_bundle_optimization_preview" in tool_src
    assert "build_ring_bundle_optimization_suite_preview" in tool_src
    assert "Фрагментов оптимизации:" in tool_src
    assert "Строк набора:" in tool_src
    assert "Копия для анимации:" in tool_src
    assert "self.road_panel.render(diagnostics, selected_index)" in tool_src
    assert 'self.notebook.add(self.road_tab_scroll, text="Дорога")' in tool_src
    assert "ttk.PanedWindow(right, orient=\"vertical\")" in tool_src
    assert "ScrollablePanel(self.notebook)" in tool_src

    assert "class SegmentListPanel" in panels_src
    assert "class ScrollablePanel" in panels_src
    assert "class PreviewPanel" in panels_src
    assert "class MotionPanel" in panels_src
    assert "class RoadPanel" in panels_src
    assert 'text="Профиль дороги"' in panels_src
    assert "def render(self, diagnostics: RingEditorDiagnostics, selected_index: int) -> None:" in panels_src
    assert "self.profile_canvas" in panels_src
    assert "class EventsPanel" in panels_src
    assert "class DiagnosticsPanel" in panels_src
    assert "class ExportPanel" in panels_src
    assert "Сегменты" in panels_src
    assert "Развёрнутый циклический preview" in panels_src
    assert "Параметры дороги" in panels_src
    assert "Передача в оптимизацию" in panels_src
    assert "Inputs handoff / HO-002" in panels_src
    assert "WS-RING читает только frozen ref/hash из WS-INPUTS." in panels_src
    assert "inputs_handoff_var" in panels_src
    assert "Окна оптимизации" in panels_src
    assert "Строки набора оптимизации" in panels_src
    assert "Открыть каталог оптимизации" in panels_src
    assert "Открыть последний набор" in panels_src
    assert "Последние артефакты" in panels_src
    assert "Открыть meta HO-004" in panels_src
    assert "Открыть source WS-RING" in panels_src
    assert "Загрузить сценарий" in panels_src
    assert "Сохранить сценарий" in panels_src
    assert "Построить набор оптимизации" in panels_src
    assert "Начальная скорость, км/ч" in panels_src
    assert "Режим прохождения" in panels_src
    assert "Зерно генерации" in panels_src
    assert "Шаг профиля, м" in panels_src
    assert "Шаг времени, с" in panels_src
    assert "Число кругов" in panels_src
    assert "Колёсная база, м" in panels_src
    assert "Колея, м" in panels_src
    assert "Длительность, с" in panels_src
    assert "Скорость в конце, км/ч" in panels_src
    assert "Радиус поворота, м" in panels_src
    assert "Стартовая скорость:" in panels_src
    assert "Длина сегмента:" in panels_src
    assert "Изменение скорости:" in panels_src
    assert "Длина кольца примерно" in panels_src
    assert "Профиль всего кольца: амплитуда (A) левого/правого следа, мм" in panels_src
    assert "Профиль всего кольца: полный размах левого/правого следа, мм" in panels_src
    assert "Шов замыкания слева/справа" in panels_src
    assert "не геометрическое кольцо" in panels_src
    assert "create_arc" not in panels_src
    assert "create_oval" not in panels_src
    assert "scroll_to_top" in panels_src
    assert 'label="v0, км/ч"' not in panels_src
    assert 'label="seed"' not in panels_src
    assert 'label="dx, м"' not in panels_src
    assert 'label="dt, c"' not in panels_src
    assert 'label="n_laps"' not in panels_src
    assert 'label="wheelbase, м"' not in panels_src
    assert 'label="track, м"' not in panels_src
    assert 'label="duration, c"' not in panels_src
    assert 'label="speed_end, км/ч"' not in panels_src
    assert 'label="turn_radius, м"' not in panels_src
    assert "L сегм." not in panels_src
    assert "Δv:" not in panels_src
    assert "Профиль ВСЕГО кольца: амплитуда A L/R (служебно)" not in panels_src
    assert "Профиль ВСЕГО кольца: полный размах max-min L/R (не A)" not in panels_src
    assert "Локальная амплитуда (A) левого/правого следа" in panels_src
    assert "Локальный полный размах левого/правого следа" in panels_src
    assert "Сводка ниже специально разделяет амплитуду (A) и полный размах профиля." in panels_src
    assert "Diagnostics не собраны." not in panels_src
    assert "Optimization suite preview ещё не готов." not in panels_src
    assert "Открыть последний axay" not in panels_src
    assert "Открыть exports anim_latest" not in panels_src
    assert "Собрать сценарий/дорогу/axay" not in panels_src
    assert "файл ускорений" in panels_src
    assert "Окно фрагмента, с" in panels_src

    assert "class RingEditorDiagnostics" in runtime_src
    assert "class RingRoadProfilePreview" in runtime_src
    assert "road_profile: RingRoadProfilePreview | None" in runtime_src
    assert "def _build_road_profile_preview" in runtime_src
    assert "def build_ring_editor_diagnostics" in runtime_src
    assert "def export_ring_scenario_bundle" in runtime_src
    assert "meta_json" in runtime_src
    assert "ring_source_of_truth_json" in runtime_src
    assert "def mirror_ring_bundle_to_anim_latest_exports" in runtime_src
    assert "def materialize_ring_bundle_optimization_suite" in runtime_src
    assert "def build_ring_bundle_optimization_preview" in runtime_src
    assert "def build_ring_bundle_optimization_suite_preview" in runtime_src


def test_desktop_ring_editor_presets_apply_ring_and_segment_templates() -> None:
    state = create_editor_state()
    base_uid = str(state.spec["segments"][0]["uid"])

    assert "Ресурсный круг ISO 8608" in list_ring_preset_names()
    assert "Левый поворот с синусоидой" in list_segment_preset_names()

    apply_ring_preset(state, "Ресурсный круг ISO 8608")
    assert state.spec["n_laps"] == 3
    assert len(state.spec["segments"]) == 4
    assert state.spec["segments"][1]["turn_direction"] == "LEFT"

    apply_segment_preset_to_selected(state, "Левый поворот с синусоидой")
    assert str(state.spec["segments"][0]["uid"]) == str(state.selected_segment_uid)
    assert state.spec["segments"][0]["turn_direction"] == "LEFT"
    assert str(state.spec["segments"][0]["road"]["mode"]).upper() == "SINE"

    before_count = len(state.spec["segments"])
    insert_segment_preset_after_selection(state, "Препятствия и ямы")
    assert len(state.spec["segments"]) == before_count + 1
    inserted = next(seg for seg in state.spec["segments"] if str(seg["uid"]) == str(state.selected_segment_uid))
    assert inserted["events"]
    assert str(inserted["road"]["mode"]).upper() == "ISO8608"
    assert base_uid != str(inserted["uid"])
    apply_ring_preset(state, "ISO endurance")
    apply_segment_preset_to_selected(state, "Left turn sine")


def test_desktop_ring_editor_default_spec_builds_preview_and_bundle(tmp_path: Path) -> None:
    spec = build_default_ring_spec()
    diagnostics = build_ring_editor_diagnostics(spec)

    assert diagnostics.errors == []
    assert diagnostics.segment_rows
    assert diagnostics.preview_segments
    assert diagnostics.road_profile is not None
    assert diagnostics.metrics["ring_length_m"] > 0.0
    assert diagnostics.metrics["ring_amp_left_mm"] >= 0.0
    assert diagnostics.metrics["ring_p2p_left_mm"] >= diagnostics.metrics["ring_amp_left_mm"]
    assert "L_amp_mm" in diagnostics.segment_rows[0]
    assert "L_p2p_mm" in diagnostics.segment_rows[0]
    assert "R_amp_mm" in diagnostics.segment_rows[0]
    assert "R_p2p_mm" in diagnostics.segment_rows[0]
    assert len(diagnostics.road_profile.x_m) >= 16
    assert len(diagnostics.road_profile.x_m) == len(diagnostics.road_profile.left_mm)
    assert len(diagnostics.road_profile.x_m) == len(diagnostics.road_profile.right_mm)
    assert float(diagnostics.segment_rows[0]["x_end_m"]) > float(diagnostics.segment_rows[0]["x_start_m"])

    bundle = export_ring_scenario_bundle(spec, output_dir=tmp_path, tag="desktop_ring")
    spec_path = Path(str(bundle["scenario_json"]))
    road_path = Path(str(bundle["road_csv"]))
    axay_path = Path(str(bundle["axay_csv"]))
    meta_path = Path(str(bundle["meta_json"]))
    source_path = Path(str(bundle["ring_source_of_truth_json"]))

    assert spec_path.exists()
    assert road_path.exists()
    assert axay_path.exists()
    assert meta_path.exists()
    assert source_path.exists()
    assert "segment_id" in road_path.read_text(encoding="utf-8").splitlines()[0].split(",")

    exported = json.loads(spec_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "ring_v2"
    assert exported["_generated_outputs"]["road_csv"] == road_path.name
    assert exported["_generated_outputs"]["axay_csv"] == axay_path.name
    assert exported["_generated_outputs"]["meta_json"] == meta_path.name
    assert exported["_generated_outputs"]["ring_source_of_truth_json"] == source_path.name
    assert exported["_lineage"]["handoff_id"] == "HO-004"
    assert meta["handoff_id"] == "HO-004"
    assert meta["source_workspace"] == "WS-RING"
    assert meta["consumer_workspace"] == "WS-SUITE"
    assert meta["downstream_geometry_editing_allowed"] is False
    assert exported["_artifact_roles"]["ring_source_of_truth_json"]["role"] == "authoritative_ws_ring_source"
    assert exported["_artifact_roles"]["scenario_json"]["role"] == "derived_runtime_scenario"
    assert exported["_artifact_roles"]["scenario_json"]["derived"] is True
    assert meta["artifact_roles"]["ring_source_of_truth_json"]["editable_source"] is True
    assert meta["artifact_roles"]["road_csv"]["role"] == "derived_road_timeseries"
    assert meta["source_and_derived_boundaries"]["authoritative_source"] == "ring_source_of_truth_json"
    assert meta["source_and_derived_boundaries"]["editable_owner"] == "WS-RING"
    assert meta["source_and_derived_boundaries"]["downstream_geometry_editing_allowed"] is False
    assert "scenario_json" in meta["source_and_derived_boundaries"]["derived_artifacts"]
    assert "segment_meta_ref" in meta["source_and_derived_boundaries"]["ws_suite_readonly_ring_refs"]
    assert meta["road"]["segments"]
    assert meta["road"]["segment_id_series"]["csv_column"] == "segment_id"
    assert meta["lineage"]["ring_source_hash_sha256"]
    assert meta["lineage"]["ring_export_set_hash_sha256"]
    assert source["_source_contract"]["editable_owner"] == "WS-RING"
    assert source["_source_contract"]["artifact_role"] == "authoritative_ws_ring_source"
    assert source["_source_contract"]["downstream_geometry_editing_allowed"] is False


def test_desktop_ring_editor_can_mirror_bundle_into_workspace_anim_latest_exports(tmp_path: Path) -> None:
    spec = build_default_ring_spec()
    bundle_dir = tmp_path / "bundle_out"
    exports_dir = tmp_path / "workspace" / "exports"

    bundle = export_ring_scenario_bundle(spec, output_dir=bundle_dir, tag="desktop_ring")
    mirrored = mirror_ring_bundle_to_anim_latest_exports(bundle, exports_dir=exports_dir)

    assert Path(mirrored["road_csv"]).name == "anim_latest_road_csv.csv"
    assert Path(mirrored["axay_csv"]).name == "anim_latest_axay_csv.csv"
    assert Path(mirrored["scenario_json"]).name == "anim_latest_scenario_json.json"
    assert Path(mirrored["road_csv"]).exists()
    assert Path(mirrored["axay_csv"]).exists()
    assert Path(mirrored["scenario_json"]).exists()

    scenario_payload = json.loads(Path(mirrored["scenario_json"]).read_text(encoding="utf-8"))
    assert scenario_payload["schema_version"] == "ring_v2"


def test_desktop_ring_editor_can_materialize_optimization_auto_ring_suite(tmp_path: Path) -> None:
    spec = build_default_ring_spec()
    bundle_dir = tmp_path / "bundle_out"
    workspace_dir = tmp_path / "workspace"
    exports_dir = workspace_dir / "exports"

    bundle = export_ring_scenario_bundle(spec, output_dir=bundle_dir, tag="desktop_ring")
    mirrored = mirror_ring_bundle_to_anim_latest_exports(bundle, exports_dir=exports_dir)
    suite_info = materialize_ring_bundle_optimization_suite(
        {
            **bundle,
            "anim_latest_road_csv": mirrored["road_csv"],
            "anim_latest_axay_csv": mirrored["axay_csv"],
            "anim_latest_scenario_json": mirrored["scenario_json"],
        },
        workspace_dir=workspace_dir,
        window_s=6.5,
    )

    suite_path = Path(str(suite_info["suite_json"]))
    meta_path = Path(str(suite_info["suite_meta_json"]))
    assert suite_path.exists()
    assert meta_path.exists()
    rows = json.loads(suite_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert any(str((row or {}).get("имя") or "") == "ring_auto_full" for row in rows if isinstance(row, dict))
    assert int(suite_info["generated_row_count"]) == len(rows)
    assert float(suite_info["window_s"]) == 6.5
    assert Path(str(suite_info["workspace_dir"])).resolve() == workspace_dir.resolve()
    assert meta["input_ring"]["scenario_json"].endswith("anim_latest_scenario_json.json")
    assert meta["handoff"]["handoff_id"] == "HO-004"
    assert meta["handoff"]["source_workspace"] == "WS-RING"
    assert meta["handoff"]["ring_geometry_editable"] is False
    full_row = next(row for row in rows if isinstance(row, dict) and str(row.get("имя") or "") == "ring_auto_full")
    assert full_row["test_type"] == "ring"
    assert full_row["handoff_id"] == "HO-004"
    assert full_row["ring_geometry_editable"] is False


def test_desktop_ring_road_panel_renders_whole_and_local_profile() -> None:
    root = tk.Tk()
    root.withdraw()
    panel = RoadPanel(root)
    panel.pack(fill="both", expand=True)
    try:
        diagnostics = build_ring_editor_diagnostics(build_default_ring_spec())
        panel.render(diagnostics, 0)
        root.update_idletasks()

        assert diagnostics.road_profile is not None
        assert "Профиль кольца" in str(panel.profile_stats_var.get() or "")
        canvas_text = " ".join(_canvas_texts(panel.profile_canvas))
        assert "Профиль кольца" in canvas_text
        assert "Выбранный сегмент" in canvas_text
        assert "Левый след" in canvas_text
        assert "Правый след" in canvas_text
        assert "мм" in canvas_text
        assert len(panel.profile_canvas.find_all()) >= 12
    finally:
        root.destroy()


def test_desktop_ring_editor_can_build_optimization_preview_rows_from_bundle(tmp_path: Path) -> None:
    spec = build_default_ring_spec()
    bundle = export_ring_scenario_bundle(spec, output_dir=tmp_path / "bundle_out", tag="desktop_ring")

    preview_rows = build_ring_bundle_optimization_preview(bundle, window_s=4.0)

    assert preview_rows
    assert all(float(row["duration_s"]) > 0.0 for row in preview_rows)
    assert all(str(row["id"]).startswith("ringfrag_") for row in preview_rows)
    assert all("segments_text" in row for row in preview_rows)


def test_desktop_ring_editor_can_build_optimization_suite_preview_summary(tmp_path: Path) -> None:
    spec = build_default_ring_spec()
    bundle = export_ring_scenario_bundle(spec, output_dir=tmp_path / "bundle_out", tag="desktop_ring")

    preview = build_ring_bundle_optimization_suite_preview(bundle, window_s=4.0)

    assert "stage_counts" in preview
    assert "fragment_rows" in preview
    assert "suite_rows" in preview
    assert "summary_text" in preview
    assert int(preview["stage_counts"]["stage2_full_count"]) == 1
    assert int(preview["stage_counts"]["total_count"]) >= 1
    assert "stage0 seeds=" in str(preview["summary_text"])


def test_desktop_ring_editor_quick_save_reuses_known_spec_path(tmp_path: Path) -> None:
    editor = _make_stub_editor(tmp_path)
    refresh_calls: list[str] = []
    editor._refresh_from_state = lambda: refresh_calls.append("refresh")
    editor.state.spec_path = str(tmp_path / "saved_ring_spec.json")
    editor.state.dirty = True
    editor.state.spec["segments"][0]["road"]["center_height_start_mm"] = 7.0
    editor.state.spec["segments"][0]["road"]["cross_slope_start_pct"] = 2.0
    editor.state.spec["segments"][1]["speed_start_kph"] = 99.0
    editor.state.spec["segments"][1]["road"]["center_height_start_mm"] = 123.0
    editor.state.spec["segments"][1]["road"]["cross_slope_start_pct"] = 4.0
    editor.state.spec["segments"][-1]["speed_end_kph"] = 99.0
    editor.state.spec["segments"][-1]["road"]["center_height_end_mm"] = 999.0

    saved_path = DesktopRingScenarioEditor._save_spec(editor)

    assert saved_path == editor.state.spec_path
    assert Path(saved_path or "").exists()
    exported = json.loads(Path(saved_path or "").read_text(encoding="utf-8"))
    assert exported["schema_version"] == "ring_v2"
    assert exported["_source_contract"]["editable_owner"] == "WS-RING"
    assert "speed_start_kph" not in exported["segments"][1]
    assert "center_height_start_mm" not in exported["segments"][1]["road"]
    assert "cross_slope_start_pct" not in exported["segments"][1]["road"]
    assert float(exported["segments"][-1]["speed_end_kph"]) == float(exported["v0_kph"])
    assert float(exported["segments"][-1]["road"]["center_height_end_mm"]) == 7.0
    assert float(exported["segments"][-1]["road"]["cross_slope_end_pct"]) == 2.0
    assert editor.state.dirty is False
    assert refresh_calls == ["refresh"]


def test_desktop_ring_editor_standalone_bindings_and_close_confirm(tmp_path: Path, monkeypatch) -> None:
    editor = _make_stub_editor(tmp_path)
    fake_root = editor.root

    DesktopRingScenarioEditor._install_window_bindings(editor)

    assert "WM_DELETE_WINDOW" in fake_root.protocols
    assert "<Control-s>" in fake_root.bindings
    assert "<Control-o>" in fake_root.bindings
    assert "<F5>" in fake_root.bindings

    editor.state.dirty = True
    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor.messagebox.askyesno",
        lambda *_args, **_kwargs: False,
    )
    DesktopRingScenarioEditor._request_close(editor)
    assert fake_root.destroy_called is False
    assert editor._host_closed is False

    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor.messagebox.askyesno",
        lambda *_args, **_kwargs: True,
    )
    DesktopRingScenarioEditor._request_close(editor)
    assert fake_root.destroy_called is True
    assert editor._host_closed is True


def test_desktop_ring_editor_marks_generated_outputs_stale_on_dirty_change(tmp_path: Path) -> None:
    editor = _make_stub_editor(tmp_path)
    editor.state.export.artifacts_stale = False
    editor.state.export.opt_suite_stale = False
    editor.state.export.last_bundle = {
        "scenario_json": str(tmp_path / "old_spec.json"),
        "road_csv": str(tmp_path / "old_road.csv"),
        "axay_csv": str(tmp_path / "old_axay.csv"),
        "suite_json": str(tmp_path / "old_suite.json"),
    }

    DesktopRingScenarioEditor._mark_dirty(editor, "spec changed")

    assert editor.state.dirty is True
    assert editor.state.export.artifacts_stale is True
    assert editor.state.export.opt_suite_stale is True
    assert editor.state.status_message == "spec changed"


def test_desktop_ring_editor_rebuilds_fresh_bundle_before_opt_suite_when_stale(tmp_path: Path, monkeypatch) -> None:
    editor = _make_stub_editor(tmp_path)
    refresh_calls: list[str] = []
    editor._refresh_from_state = lambda: refresh_calls.append("refresh")
    editor.state.export.artifacts_stale = True
    editor.state.export.opt_workspace_dir = str(tmp_path / "workspace")
    editor.state.export.opt_window_s = 5.5
    editor.state.export.last_bundle = {
        "scenario_json": str(tmp_path / "stale_spec.json"),
        "road_csv": str(tmp_path / "stale_road.csv"),
        "axay_csv": str(tmp_path / "stale_axay.csv"),
    }

    generated_bundle = {
        "scenario_json": str(tmp_path / "fresh_spec.json"),
        "road_csv": str(tmp_path / "fresh_road.csv"),
        "axay_csv": str(tmp_path / "fresh_axay.csv"),
        "anim_latest_scenario_json": str(tmp_path / "anim_latest_scenario_json.json"),
        "anim_latest_road_csv": str(tmp_path / "anim_latest_road_csv.csv"),
        "anim_latest_axay_csv": str(tmp_path / "anim_latest_axay_csv.csv"),
    }
    regen_calls: list[bool] = []
    editor._generate_bundle = lambda *, show_dialog=True: regen_calls.append(bool(show_dialog)) or dict(generated_bundle)
    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor.materialize_ring_bundle_optimization_suite",
        lambda bundle, **kwargs: {
            "suite_json": str(tmp_path / "workspace" / "ui_state" / "optimization_auto_ring_suite" / "suite_auto_ring.json"),
            "suite_meta_json": str(tmp_path / "workspace" / "ui_state" / "optimization_auto_ring_suite" / "suite_auto_ring_meta.json"),
            "workspace_dir": str(kwargs.get("workspace_dir") or ""),
            "window_s": float(kwargs.get("window_s") or 0.0),
            "generated_row_count": 11,
            "source_bundle_scenario_json": str(bundle.get("scenario_json") or ""),
        },
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor.messagebox.showinfo",
        lambda *_args, **_kwargs: None,
    )

    DesktopRingScenarioEditor._build_optimization_auto_suite(editor)

    assert regen_calls == [False]
    assert editor.state.export.last_bundle["scenario_json"] == generated_bundle["scenario_json"]
    assert editor.state.export.last_bundle["suite_json"].endswith("suite_auto_ring.json")
    assert float(editor.state.export.last_bundle["window_s"]) == 5.5
    assert "derived artifacts were rebuilt from current WS-RING source" in editor.state.status_message
    assert refresh_calls == ["refresh"]


def test_desktop_ring_editor_surfaces_source_derived_stale_and_closure_labels() -> None:
    src = (
        ROOT / "pneumo_solver_ui" / "tools" / "desktop_ring_scenario_editor.py"
    ).read_text(encoding="utf-8", errors="replace")

    assert "WS-RING source state" in src
    assert "Derived artifacts state" in src
    assert "HO-005 suite link state" in src
    assert "WS-RING source hash" in src
    assert "Derived export-set hash" in src
    assert "Raw seam before export policy" in src
    assert "Post-policy seam" in src
    assert "Closure transform applied" in src
    assert "Closure correction max L/R" in src
    assert "Derived artifacts were rebuilt from current WS-RING source before suite handoff" in src


def test_desktop_ring_editor_export_path_change_marks_bundle_and_suite_stale(tmp_path: Path) -> None:
    editor = _make_stub_editor(tmp_path)
    editor.state.export.output_dir = str(tmp_path / "out_old")
    editor.state.export.tag = "old_tag"
    editor.state.export.opt_workspace_dir = str(tmp_path / "ws_old")
    editor.state.export.opt_window_s = 4.0
    editor.state.export.artifacts_stale = False
    editor.state.export.opt_suite_stale = False
    editor.export_panel = SimpleNamespace(
        output_dir_var=_FakeVar(str(tmp_path / "out_new")),
        tag_var=_FakeVar("new_tag"),
        opt_workspace_var=_FakeVar(str(tmp_path / "ws_old")),
        opt_window_var=_FakeVar("4.0"),
    )

    DesktopRingScenarioEditor._on_export_fields_changed(editor)

    assert editor.state.export.output_dir.endswith("out_new")
    assert editor.state.export.tag == "new_tag"
    assert editor.state.export.artifacts_stale is True
    assert editor.state.export.opt_suite_stale is True


def test_desktop_ring_editor_opt_handoff_change_marks_only_suite_stale(tmp_path: Path) -> None:
    editor = _make_stub_editor(tmp_path)
    editor.state.export.output_dir = str(tmp_path / "out_same")
    editor.state.export.tag = "same_tag"
    editor.state.export.opt_workspace_dir = str(tmp_path / "ws_old")
    editor.state.export.opt_window_s = 4.0
    editor.state.export.artifacts_stale = False
    editor.state.export.opt_suite_stale = False
    editor.export_panel = SimpleNamespace(
        output_dir_var=_FakeVar(str(tmp_path / "out_same")),
        tag_var=_FakeVar("same_tag"),
        opt_workspace_var=_FakeVar(str(tmp_path / "ws_new")),
        opt_window_var=_FakeVar("6.25"),
    )

    DesktopRingScenarioEditor._on_export_fields_changed(editor)

    assert editor.state.export.artifacts_stale is False
    assert editor.state.export.opt_suite_stale is True
    assert editor.state.export.opt_workspace_dir.endswith("ws_new")
    assert float(editor.state.export.opt_window_s) == 6.25


def test_desktop_ring_editor_can_open_opt_workspace_dir(tmp_path: Path, monkeypatch) -> None:
    editor = _make_stub_editor(tmp_path)
    editor.state.export.opt_workspace_dir = str(tmp_path / "workspace_opt")
    opened: list[str] = []
    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor._open_path",
        lambda path: opened.append(str(path)),
    )

    DesktopRingScenarioEditor._open_opt_workspace_dir(editor)

    assert opened == [str(tmp_path / "workspace_opt")]
    assert (tmp_path / "workspace_opt").exists()


def test_desktop_ring_editor_open_last_suite_warns_when_missing(tmp_path: Path, monkeypatch) -> None:
    editor = _make_stub_editor(tmp_path)
    editor.state.export.last_bundle = {}
    infos: list[str] = []
    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor.messagebox.showinfo",
        lambda _title, message: infos.append(str(message)),
    )

    DesktopRingScenarioEditor._open_opt_suite_dir(editor)

    assert infos
    assert "ещё не собран" in infos[0]


def test_desktop_ring_editor_can_open_last_generated_bundle_files(tmp_path: Path, monkeypatch) -> None:
    editor = _make_stub_editor(tmp_path)
    spec_path = tmp_path / "ring_spec.json"
    road_path = tmp_path / "ring_road.csv"
    axay_path = tmp_path / "ring_axay.csv"
    for path in (spec_path, road_path, axay_path):
        path.write_text("stub", encoding="utf-8")
    editor.state.export.last_bundle = {
        "scenario_json": str(spec_path),
        "road_csv": str(road_path),
        "axay_csv": str(axay_path),
    }
    opened: list[str] = []
    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor._open_file_path",
        lambda path: opened.append(str(path)),
    )

    DesktopRingScenarioEditor._open_last_generated_spec(editor)
    DesktopRingScenarioEditor._open_last_generated_road(editor)
    DesktopRingScenarioEditor._open_last_generated_axay(editor)

    assert opened == [str(spec_path), str(road_path), str(axay_path)]


def test_desktop_ring_editor_open_anim_latest_exports_uses_bundle_or_workspace_fallback(tmp_path: Path, monkeypatch) -> None:
    editor = _make_stub_editor(tmp_path)
    anim_latest = tmp_path / "workspace" / "exports" / "anim_latest_scenario_json.json"
    anim_latest.parent.mkdir(parents=True, exist_ok=True)
    anim_latest.write_text("{}", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr(
        "pneumo_solver_ui.tools.desktop_ring_scenario_editor._open_path",
        lambda path: opened.append(str(path)),
    )

    editor.state.export.last_bundle = {"anim_latest_scenario_json": str(anim_latest)}
    DesktopRingScenarioEditor._open_anim_latest_exports(editor)

    editor.state.export.last_bundle = {}
    editor.state.export.opt_workspace_dir = str(tmp_path / "workspace_custom")
    DesktopRingScenarioEditor._open_anim_latest_exports(editor)

    assert opened == [
        str(anim_latest),
        str(tmp_path / "workspace_custom" / "exports"),
    ]
    assert (tmp_path / "workspace_custom" / "exports").exists()
