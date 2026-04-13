from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.desktop_input_graphics import DesktopInputGraphicPanel
from pneumo_solver_ui.desktop_input_model import field_spec_map, load_base_with_defaults
from pneumo_solver_ui.tools.desktop_input_editor import DesktopInputEditor


_ROOT: tk.Tk | None = None
_PANEL: DesktopInputGraphicPanel | None = None


def _make_panel() -> tuple[tk.Tk, DesktopInputGraphicPanel]:
    global _ROOT, _PANEL
    if _ROOT is None or _PANEL is None:
        _ROOT = tk.Tk()
        _ROOT.withdraw()
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


def test_desktop_input_graphic_panel_renders_all_main_sections() -> None:
    payload = load_base_with_defaults()
    root, panel = _make_panel()
    for section in (
        "Геометрия",
        "Пневматика",
        "Механика",
        "Статическая настройка",
        "Компоненты",
        "Справочные данные",
    ):
        panel.refresh(section_title=section, payload=payload, field_label="Тестовое поле", unit_label="м")
        assert str(panel.summary_var.get() or "").strip()
        assert len(panel.canvas.find_all()) >= 10, section


def test_desktop_input_graphic_panel_shows_units_for_geometry_pneumatics_and_reference() -> None:
    payload = load_base_with_defaults()
    root, panel = _make_panel()
    panel.refresh(section_title="Геометрия", payload=payload, field_label="Колёсная база", unit_label="м")
    geometry_text = " ".join(_canvas_texts(panel))
    assert "м" in geometry_text
    assert "мм" in geometry_text

    panel.refresh(section_title="Пневматика", payload=payload, field_label="Начальное давление", unit_label="кПа (абс.)")
    pneumo_text = " ".join(_canvas_texts(panel))
    assert "кПа (абс.)" in pneumo_text
    assert "л" in pneumo_text
    assert "мм" in pneumo_text

    panel.refresh(section_title="Справочные данные", payload=payload, field_label="Температура", unit_label="К")
    reference_text = " ".join(_canvas_texts(panel))
    assert "К" in reference_text
    assert "мс" in reference_text
    assert "Единица: К" in reference_text


def test_desktop_input_graphic_panel_shows_comparative_static_trim_and_mechanics_context() -> None:
    payload = load_base_with_defaults()
    payload.update(
        {
            "масса_рамы": 1450.0,
            "масса_неподрессоренная_на_угол": 62.0,
            "жёсткость_шины": 210000.0,
            "демпфирование_шины": 4200.0,
            "стабилизатор_перед_жесткость_Н_м": 120000.0,
            "стабилизатор_зад_жесткость_Н_м": 90000.0,
            "zero_pose_target_stroke_frac": 0.58,
            "zero_pose_tol_stroke_frac": 0.07,
            "vx0_м_с": 12.5,
            "cg_x_м": 0.12,
            "cg_y_м": -0.04,
        }
    )
    root, panel = _make_panel()
    panel.refresh(section_title="Механика", payload=payload, field_label="Масса рамы", unit_label="кг")
    mechanics_text = " ".join(_canvas_texts(panel))
    assert "кг" in mechanics_text
    assert "Н/м" in mechanics_text
    assert "Н·с/м" in mechanics_text

    panel.refresh(section_title="Статическая настройка", payload=payload, field_label="Целевая доля хода", unit_label="доля")
    trim_text = " ".join(_canvas_texts(panel))
    assert "доли хода" in trim_text
    assert "м/с" in trim_text
    assert "CG X" in trim_text
    assert "CG Y" in trim_text


def test_desktop_input_graphic_panel_displays_active_context_title() -> None:
    payload = load_base_with_defaults()
    root, panel = _make_panel()

    panel.refresh(
        section_title="Статическая настройка",
        payload=payload,
        field_label="Целевая доля хода",
        unit_label="доля",
        field_key="zero_pose_target_stroke_frac",
    )
    trim_text = " ".join(_canvas_texts(panel))
    assert "Контекст: Посадка по ходу" in trim_text

    panel.refresh(
        section_title="Пневматика",
        payload=payload,
        field_label="Начальное давление",
        unit_label="кПа (абс.)",
        field_key="начальное_давление_Ресивер1",
    )
    pneumo_text = " ".join(_canvas_texts(panel))
    assert "Контекст: Давления и контуры" in pneumo_text


def test_desktop_input_editor_forwards_graphic_context_from_selected_field() -> None:
    root = tk.Tk()
    root.withdraw()
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
        root.destroy()
