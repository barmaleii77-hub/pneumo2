from __future__ import annotations

import tkinter as tk

import pytest

from pneumo_solver_ui.desktop_input_graphics import DesktopInputGraphicPanel
from pneumo_solver_ui.desktop_input_model import (
    desktop_section_display_title,
    field_spec_map,
    load_base_with_defaults,
)
from pneumo_solver_ui.tools.desktop_input_editor import DesktopInputEditor


_ROOT: tk.Tk | None = None
_PANEL: DesktopInputGraphicPanel | None = None


def _make_root_or_skip() -> tk.Tk:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime is unavailable in this environment: {exc}")
    root.withdraw()
    return root


def _make_panel() -> tuple[tk.Tk, DesktopInputGraphicPanel]:
    global _ROOT, _PANEL
    if _ROOT is None or _PANEL is None:
        _ROOT = _make_root_or_skip()
        _PANEL = DesktopInputGraphicPanel(_ROOT)
        _PANEL.pack()
        _ROOT.update_idletasks()
    return _ROOT, _PANEL


def _canvas_texts(panel: DesktopInputGraphicPanel) -> list[str]:
    texts: list[str] = []
    for item in panel.canvas.find_all():
        if panel.canvas.type(item) != "text":
            continue
        text = str(panel.canvas.itemcget(item, "text") or "").strip()
        if text:
            texts.append(text)
    return texts


def _canvas_item_types(panel: DesktopInputGraphicPanel) -> list[str]:
    return [panel.canvas.type(item) for item in panel.canvas.find_all()]


def _text_coords_by_value(panel: DesktopInputGraphicPanel, needle: str) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for item in panel.canvas.find_all():
        if panel.canvas.type(item) != "text":
            continue
        text = str(panel.canvas.itemcget(item, "text") or "").strip()
        if needle not in text:
            continue
        xy = panel.canvas.coords(item)
        if len(xy) >= 2:
            coords.append((float(xy[0]), float(xy[1])))
    return coords


def test_desktop_input_graphic_panel_renders_engineering_workspace_for_all_main_sections() -> None:
    payload = load_base_with_defaults()
    _root, panel = _make_panel()
    for section in (
        "Геометрия",
        "Пневматика",
        "Механика",
        "Статическая настройка",
        "Компоненты",
        "Справочные данные",
        "Расчётные настройки",
    ):
        panel.refresh(section_title=section, payload=payload, field_label="Тестовое поле", unit_label="м")
        assert str(panel.summary_var.get() or "").strip()
        assert len(panel.canvas.find_all()) >= 8, section


def test_desktop_input_graphic_panel_uses_project_scheme_with_named_geometry_dimensions() -> None:
    payload = load_base_with_defaults()
    _root, panel = _make_panel()
    panel.refresh(section_title="Геометрия", payload=payload, field_label="Колёсная база", unit_label="м")
    joined = " ".join(_canvas_texts(panel))
    assert "Схема подвески проекта" in joined
    assert "Показано:" in joined
    assert "База" in joined
    assert "Колея" in joined
    assert "м" in joined
    assert "image" in _canvas_item_types(panel)


def test_desktop_input_graphic_panel_shows_pneumatic_scheme_and_metrics() -> None:
    payload = load_base_with_defaults()
    payload.update(
        {
            "начальное_давление_Ресивер1": 520000.0,
            "начальное_давление_Ресивер2": 540000.0,
            "начальное_давление_Ресивер3": 560000.0,
            "начальное_давление_аккумулятора": 610000.0,
            "объём_ресивера_1": 18.0,
            "объём_ресивера_2": 20.0,
            "объём_ресивера_3": 22.0,
        }
    )
    _root, panel = _make_panel()
    panel.refresh(
        section_title="Пневматика",
        payload=payload,
        field_label="Начальное давление",
        unit_label="кПа",
    )
    joined = " ".join(_canvas_texts(panel))
    assert "Пневмосхема проекта" in joined
    assert "Ресивер 1" in joined
    assert "Аккумулятор" in joined
    assert "Суммарный объём" in joined
    assert "кПа" in joined

    title_coords = _text_coords_by_value(panel, "Пневмосхема проекта")
    metric_coords = _text_coords_by_value(panel, "Ресивер 1")
    assert title_coords
    assert metric_coords
    assert title_coords[0][0] < panel.SCHEME_X1
    assert metric_coords[0][0] >= panel.METRICS_X0


def test_desktop_input_graphic_panel_shows_static_trim_metrics_and_context() -> None:
    payload = load_base_with_defaults()
    payload.update(
        {
            "zero_pose_target_stroke_frac": 0.58,
            "zero_pose_tol_stroke_frac": 0.07,
            "vx0_м_с": 12.5,
            "cg_x_м": 0.12,
            "cg_y_м": -0.04,
        }
    )
    _root, panel = _make_panel()
    panel.refresh(
        section_title="Статическая настройка",
        payload=payload,
        field_label="Целевая доля хода",
        unit_label="доля",
        field_key="zero_pose_target_stroke_frac",
    )
    joined = " ".join(_canvas_texts(panel))
    assert "Показано: Целевое положение по ходу" in joined
    assert "Цель по ходу" in joined
    assert "ЦМ X" in joined
    assert "ЦМ Y" in joined
    assert "CG X" not in joined
    assert "CG Y" not in joined


def test_desktop_input_graphic_panel_shows_v38_source_marker_and_calculation_settings() -> None:
    payload = load_base_with_defaults()
    _root, panel = _make_panel()
    panel.refresh(
        section_title="Расчётные настройки",
        payload=payload,
        field_label="Шаг интегрирования",
        unit_label="мс",
        field_key="макс_шаг_интегрирования_с",
        graphic_context="integration",
        source_marker="source: default_base.json · state: dirty",
    )

    marker = str(panel.source_marker_var.get() or "")
    assert "источник: исходный шаблон" in marker
    assert "состояние: изменено" in marker
    assert "режим: По исходным данным" in marker
    assert "WS-INPUTS" not in marker
    assert "source:" not in marker
    assert "state:" not in marker

    joined = " ".join(_canvas_texts(panel))
    assert "Показано: Интегрирование" in joined
    assert "Шаг интегрирования" in joined
    assert "Проверка" in joined
    assert "Autoverif" not in joined


def test_desktop_input_editor_tree_selection_opens_cluster_editor_directly() -> None:
    root = _make_root_or_skip()
    editor = DesktopInputEditor(host=root, hosted=True)
    try:
        for section_title in ("Механика", "Численные настройки"):
            item_id = editor._section_tree_ids[section_title]
            editor.section_tree.selection_set(item_id)
            editor.section_tree.focus(item_id)
            editor._on_section_tree_selected()
            root.update_idletasks()

            expected_index = editor.section_title_to_index[section_title]
            current_index = editor.section_notebook.index(editor.section_notebook.select())
            display_title = desktop_section_display_title(section_title)
            first_field = editor.section_by_title[section_title].fields[0]

            assert current_index == expected_index
            assert editor.current_section_title_var.get() == display_title
            assert display_title in str(editor.section_tree.item(item_id, "text") or "")
            assert first_field.key in editor._widget_handles
            assert editor._field_tabs_by_key[first_field.key] is not None
    finally:
        root.destroy()


def test_desktop_input_editor_forwards_graphic_context_from_selected_field() -> None:
    root, _panel = _make_panel()
    editor = DesktopInputEditor(host=root, hosted=True)
    captured: list[dict[str, object]] = []

    class _ProbePanel:
        def refresh(self, **kwargs: object) -> None:
            captured.append(dict(kwargs))

    try:
        spec = field_spec_map()["zero_pose_target_stroke_frac"]
        editor.graphics_panel = _ProbePanel()
        editor.section_graphics_panels["Статическая настройка"] = _ProbePanel()
        editor._select_field(spec.key)
        assert captured
        assert captured[-1]["field_key"] == spec.key
        assert captured[-1]["graphic_context"] == spec.effective_graphic_context
        assert captured[-1]["unit_label"] == spec.unit_label
    finally:
        editor.root.destroy()
