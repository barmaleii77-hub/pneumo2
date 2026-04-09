from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_mech_animation_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_mech_animation_helpers.py"


class _FakeExpander:
    def __enter__(self) -> "_FakeExpander":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.captions: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.errors: list[str] = []
        self.codes: list[str] = []
        self.markdowns: list[str] = []
        self.checkboxes: list[dict[str, object]] = []
        self.radios: list[dict[str, object]] = []
        self.expanders: list[tuple[str, bool]] = []
        self.downloads: list[dict[str, object]] = []
        self.number_inputs: list[dict[str, object]] = []
        self.selectboxes: list[dict[str, object]] = []
        self.sliders: list[dict[str, object]] = []
        self.buttons: list[dict[str, object]] = []
        self.session_state: dict[str, object] = {}
        self.checkbox_overrides: dict[str, object] = {}
        self.button_overrides: dict[str, object] = {}
        self.radio_overrides: dict[str, object] = {}

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def warning(self, text: str) -> None:
        self.warnings.append(text)

    def info(self, text: str) -> None:
        self.infos.append(text)

    def error(self, text: str) -> None:
        self.errors.append(text)

    def markdown(self, text: str) -> None:
        self.markdowns.append(text)

    def code(self, text: str) -> None:
        self.codes.append(text)

    def checkbox(self, label: str, *, value: bool, key: str, **kwargs):
        self.checkboxes.append({"label": label, "value": value, "key": key, **kwargs})
        return self.checkbox_overrides.get(key, value)

    def radio(self, label: str, options, *, format_func=None, horizontal: bool = False, index: int = 0, key: str | None = None) -> str:
        payload = {
            "label": label,
            "options": list(options),
            "horizontal": horizontal,
            "index": index,
            "key": key,
        }
        if format_func is not None:
            payload["add"] = format_func("add")
            payload["replace"] = format_func("replace")
        self.radios.append(payload)
        if key is not None and key in self.radio_overrides:
            return str(self.radio_overrides[key])
        return str(list(options)[index])

    def expander(self, label: str, expanded: bool = False) -> _FakeExpander:
        self.expanders.append((label, expanded))
        return _FakeExpander()

    def columns(self, spec):
        if isinstance(spec, int):
            count = spec
        else:
            count = len(list(spec))
        return tuple(_FakeExpander() for _ in range(count))

    def download_button(self, label: str, *, data, file_name: str, mime: str) -> None:
        self.downloads.append(
            {
                "label": label,
                "data": data,
                "file_name": file_name,
                "mime": mime,
            }
        )

    def number_input(self, label: str, **kwargs):
        self.number_inputs.append({"label": label, **kwargs})
        return kwargs["value"]

    def selectbox(self, label: str, options, *, index: int, key: str):
        self.selectboxes.append(
            {
                "label": label,
                "options": list(options),
                "index": index,
                "key": key,
            }
        )
        return list(options)[index]

    def slider(self, label: str, *args, **kwargs):
        if args:
            names = ["min_value", "max_value", "value"]
            for name, value in zip(names, args):
                kwargs.setdefault(name, value)
        self.sliders.append({"label": label, **kwargs})
        return kwargs["value"]

    def button(self, label: str, **kwargs):
        self.buttons.append({"label": label, **kwargs})
        key = kwargs.get("key")
        return self.button_overrides.get(str(key), False)


class _Arrayish:
    def __init__(self, values) -> None:
        self._values = list(values)

    def tolist(self):
        return list(self._values)


class _FakeFallbackModule:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def render_mech2d_fallback(self, **kwargs) -> None:
        self.calls.append(kwargs)

    def render_mech3d_fallback(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_render_mechanical_animation_intro_handles_empty_state_and_contract() -> None:
    fake_st = _FakeStreamlit()

    proceed = helpers.render_mechanical_animation_intro(fake_st, df_main=None)

    assert proceed is False
    assert fake_st.captions == [
        "Упрощённая анимация механики: фронтальный вид (крен) и боковой вид (тангаж). Показывает движение рамы/колёс и ход штока по данным df_main."
    ]
    assert fake_st.warnings == ["Нет df_main для анимации механики."]
    assert fake_st.radios == [
        {
            "label": "Клик по механике",
            "options": ["replace", "add"],
            "add": "Добавлять к выбору",
            "replace": "Заменять выбор",
            "horizontal": True,
            "index": 0,
            "key": "mech_click_mode",
        }
    ]


def test_render_mechanical_animation_intro_allows_render_when_time_column_present() -> None:
    fake_st = _FakeStreamlit()
    df_main = pd.DataFrame({"время_с": [0.0, 1.0]})

    proceed = helpers.render_mechanical_animation_intro(fake_st, df_main=df_main)

    assert proceed is True
    assert fake_st.warnings == []


def test_prepare_mechanical_animation_prelude_collects_shared_controls_and_timebase() -> None:
    fake_st = _FakeStreamlit()
    df_main = pd.DataFrame({"время_с": [0.0, 0.5, 1.0]})

    values = helpers.prepare_mechanical_animation_prelude(fake_st, df_main=df_main)

    assert values == {
        "px_per_m": 2000.0,
        "body_offset_px": 110.0,
        "fps": 30.0,
        "frame_dt_s": 1.0 / 30.0,
        "time_s": [0.0, 0.5, 1.0],
        "corners": ["ЛП", "ПП", "ЛЗ", "ПЗ"],
    }
    assert [item["label"] for item in fake_st.sliders] == [
        "Масштаб (px/м)",
        "Отступ рамы над колёсами (px)",
        "Скорость (FPS)",
    ]


def test_prepare_mechanical_animation_body_profiles_builds_body_and_body3d() -> None:
    df_main = pd.DataFrame(
        {
            "перемещение_рамы_z_м": [1.0, 2.0],
            "крен_phi_рад": [0.0, 0.0],
            "тангаж_theta_рад": [0.0, 0.0],
        }
    )

    values = helpers.prepare_mechanical_animation_body_profiles(
        df_main,
        time_len=2,
        corners=["ЛП", "ПП", "ЛЗ", "ПЗ"],
        wheelbase=2.0,
        track=1.0,
    )

    assert values["z"].tolist() == [1.0, 2.0]
    assert values["phi"].tolist() == [0.0, 0.0]
    assert values["theta"].tolist() == [0.0, 0.0]
    assert values["body"] == {
        "ЛП": [1.0, 2.0],
        "ПП": [1.0, 2.0],
        "ЛЗ": [1.0, 2.0],
        "ПЗ": [1.0, 2.0],
    }
    assert values["body3d"] == {"z": [1.0, 2.0]}


def test_prepare_mechanical_animation_corner_series_supports_custom_column_resolvers() -> None:
    df_main = pd.DataFrame(
        {
            "перемещение_колеса_ЛП_м_rel0": [0.1, 0.2],
            "перемещение_колеса_ПП_м_rel0": [0.3, 0.4],
            "дорога_ЛП_м_rel0": [1.1, 1.2],
            "дорога_ПП_м_rel0": [1.3, 1.4],
            "положение_штока_ЛП_м": [2.1, 2.2],
            "положение_штока_ПП_м": [2.3, 2.4],
        }
    )

    values = helpers.prepare_mechanical_animation_corner_series(
        df_main,
        corners=["ЛП", "ПП"],
        time_len=2,
        wheel_column_resolver_fn=lambda c: f"перемещение_колеса_{c}_м_rel0",
        road_column_resolver_fn=lambda c: f"дорога_{c}_м_rel0",
        stroke_column_resolver_fn=lambda c: f"положение_штока_{c}_м",
    )

    assert values == {
        "wheel": {"ЛП": [0.1, 0.2], "ПП": [0.3, 0.4]},
        "road": {"ЛП": [1.1, 1.2], "ПП": [1.3, 1.4]},
        "stroke": {"ЛП": [2.1, 2.2], "ПП": [2.3, 2.4]},
    }


def test_prepare_mechanical_animation_runtime_inputs_collects_geometry_series_and_restore_state() -> None:
    df_main = pd.DataFrame(
        {
            "перемещение_рамы_z_м": [0.0, 0.1],
            "крен_phi_рад": [0.0, 0.01],
            "тангаж_theta_рад": [0.0, 0.02],
            "перемещение_колеса_ЛП_м": [1.0, 1.1],
            "перемещение_колеса_ПП_м": [1.2, 1.3],
            "дорога_ЛП_м": [0.0, 0.0],
            "дорога_ПП_м": [0.0, 0.0],
            "положение_штока_ЛП_м": [2.0, 2.1],
            "положение_штока_ПП_м": [2.2, 2.3],
        }
    )

    calls: list[tuple[float, float, list[str]]] = []

    def _compute_road_profile(_model_mod, _test_cfg, time_s, wheelbase, track, corners):
        calls.append((wheelbase, track, list(corners)))
        assert time_s == [0.0, 0.1]
        return {
            "ЛП": [10.0, 11.0],
            "ПП": [20.0, 21.0],
        }

    values = helpers.prepare_mechanical_animation_runtime_inputs(
        df_main=df_main,
        base_override={"база": 2.8, "колея": 1.6, "ход_штока": 0.33},
        model_mod=object(),
        test_cfg={"road_csv": "road.csv"},
        time_s=[0.0, 0.1],
        corners=["ЛП", "ПП"],
        compute_road_profile_fn=_compute_road_profile,
        wheel_column_resolver_fn=lambda c: f"перемещение_колеса_{c}_м",
        road_column_resolver_fn=lambda c: f"дорога_{c}_м",
        stroke_column_resolver_fn=lambda c: f"положение_штока_{c}_м",
    )

    assert values["wheelbase"] == 2.8
    assert values["track"] == 1.6
    assert values["L_stroke_m"] == 0.33
    assert values["wheel"] == {"ЛП": [1.0, 1.1], "ПП": [1.2, 1.3]}
    assert values["stroke"] == {"ЛП": [2.0, 2.1], "ПП": [2.2, 2.3]}
    assert values["road"] == {"ЛП": [10.0, 11.0], "ПП": [20.0, 21.0]}
    assert values["road_restored"] is True
    assert values["body3d"] == {"z": [0.0, 0.1]}
    assert calls == [(2.8, 1.6, ["ЛП", "ПП"])]


def test_prepare_mechanical_animation_runtime_inputs_supports_heavy_rel0_and_param_hook() -> None:
    df_main = pd.DataFrame(
        {
            "перемещение_рамы_z_м_rel0": [0.5, 0.6],
            "крен_phi_рад_rel0": [0.1, 0.2],
            "тангаж_theta_рад_rel0": [0.3, 0.4],
            "перемещение_колеса_ЛП_м_rel0": [1.0, 1.5],
            "перемещение_колеса_ПП_м_rel0": [2.0, 2.5],
            "дорога_ЛП_м_rel0": [0.0, 0.0],
            "дорога_ПП_м_rel0": [0.0, 0.0],
            "положение_штока_ЛП_м": [3.0, 3.5],
            "положение_штока_ПП_м": [4.0, 4.5],
        }
    )

    param_calls: list[tuple[str, float]] = []

    def _get_float_param(_base_override, key: str, default: float):
        param_calls.append((key, default))
        return {"база": 1.5, "колея": 1.0}[key]

    values = helpers.prepare_mechanical_animation_runtime_inputs(
        df_main=df_main,
        base_override={"ход_штока": 0.25},
        model_mod=object(),
        test_cfg={"road_csv": "road.csv"},
        time_s=[0.0, 0.1],
        corners=["ЛП", "ПП"],
        compute_road_profile_fn=lambda *_args, **_kwargs: {
            "ЛП": [5.0, 5.5],
            "ПП": [7.0, 8.0],
        },
        wheel_column_resolver_fn=lambda c: f"перемещение_колеса_{c}_м_rel0",
        road_column_resolver_fn=lambda c: f"дорога_{c}_м_rel0",
        stroke_column_resolver_fn=lambda c: f"положение_штока_{c}_м",
        z_column="перемещение_рамы_z_м_rel0",
        phi_column="крен_phi_рад_rel0",
        theta_column="тангаж_theta_рад_rel0",
        normalize_restored_road_fn=lambda restored_road: {
            corner: [float(value) - float(values[0]) for value in values]
            for corner, values in restored_road.items()
        },
        get_float_param_fn=_get_float_param,
        wheelbase_default=9.9,
        track_default=8.8,
    )

    assert values["wheelbase"] == 1.5
    assert values["track"] == 1.0
    assert values["L_stroke_m"] == 0.25
    assert values["z"].tolist() == [0.5, 0.6]
    assert values["phi"].tolist() == [0.1, 0.2]
    assert values["theta"].tolist() == [0.3, 0.4]
    assert values["wheel"] == {"ЛП": [1.0, 1.5], "ПП": [2.0, 2.5]}
    assert values["stroke"] == {"ЛП": [3.0, 3.5], "ПП": [4.0, 4.5]}
    assert values["road"] == {"ЛП": [0.0, 0.5], "ПП": [0.0, 1.0]}
    assert values["road_restored"] is True
    assert ("база", 9.9) in param_calls
    assert ("колея", 8.8) in param_calls


def test_render_mechanical_animation_results_panel_orchestrates_prelude_runtime_and_section() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    def _prelude(_st, *, df_main):
        calls.append(("prelude", df_main))
        return {
            "px_per_m": 1234.0,
            "body_offset_px": 88.0,
            "frame_dt_s": 0.05,
            "time_s": [0.0, 0.1],
            "corners": ["FL", "FR"],
        }

    def _runtime_inputs(**kwargs):
        calls.append(("runtime", (kwargs["time_s"], kwargs["corners"])))
        return {
            "phi": [0.1, 0.2],
            "theta": [0.3, 0.4],
            "body": {"FL": [1.0, 1.1]},
            "body3d": {"z": [2.0, 2.1]},
            "wheel": {"FL": [3.0, 3.1]},
            "road": {"FL": [4.0, 4.1]},
            "stroke": {"FL": [5.0, 5.1]},
            "wheelbase": 2.8,
            "track": 1.6,
            "L_stroke_m": 0.33,
            "road_restored": True,
        }

    def _section(_st, **kwargs):
        calls.append(("section", kwargs["time"]))
        return kwargs

    log_calls: list[tuple[str, dict[str, object]]] = []
    df_main = pd.DataFrame({"время_с": [0.0, 0.1]})

    result = helpers.render_mechanical_animation_results_panel(
        fake_st,
        session_state={"demo": True},
        cache_key="cache-1",
        dataset_id="dataset-1",
        df_main=df_main,
        base_override={"база": 2.8},
        model_mod="model-mod",
        test_cfg={"cfg": True},
        compute_road_profile_fn=lambda *_args, **_kwargs: None,
        log_event_fn=lambda name, **kwargs: log_calls.append((name, kwargs)),
        wheel_column_resolver_fn=lambda c: f"wheel_{c}",
        road_column_resolver_fn=lambda c: f"road_{c}",
        stroke_column_resolver_fn=lambda c: f"stroke_{c}",
        playhead_idx=7,
        show_2d_controls=False,
        road_restored_log_kwargs={"test": "pick-1"},
        prelude_fn=_prelude,
        runtime_inputs_fn=_runtime_inputs,
        section_fn=_section,
        section_kwargs={"marker": "ok"},
    )

    assert calls == [
        ("prelude", df_main),
        ("runtime", ([0.0, 0.1], ["FL", "FR"])),
        ("section", [0.0, 0.1]),
    ]
    assert fake_st.captions == [helpers.MECH_ROAD_RESTORED_CAPTION]
    assert log_calls == [("anim_road_from_suite", {"test": "pick-1"})]
    assert result["session_state"] == {"demo": True}
    assert result["cache_key"] == "cache-1"
    assert result["dataset_id"] == "dataset-1"
    assert result["time"] == [0.0, 0.1]
    assert result["playhead_idx"] == 7
    assert result["show_2d_controls"] is False
    assert result["px_per_m"] == 1234.0
    assert result["body_offset_px"] == 88.0
    assert result["wheelbase"] == 2.8
    assert result["track"] == 1.6
    assert result["L_stroke_m"] == 0.33
    assert result["marker"] == "ok"
    assert result["intro_fn"](object(), df_main=df_main) is True


def test_build_mechanical_2d_component_payload_keeps_shared_timeline_and_selection_contract() -> None:
    payload = helpers.build_mechanical_2d_component_payload(
        {
            "mech_selected_corners": ["FL", "RR"],
            "mech3d_cmd_cache-1": {"reset_view": True},
        },
        cache_key="cache-1",
        dataset_id="dataset-1",
        time=[0.0, 0.1],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        stroke={"stroke": 4},
        phi=_Arrayish([1.0, 2.0]),
        theta=[3.0, 4.0],
        px_per_m=123,
        body_offset_px=45,
        L_stroke_m=0.25,
        frame_dt_s=0.02,
    )

    assert payload == {
        "title": helpers.MECH_2D_COMPONENT_TITLE,
        "time": [0.0, 0.1],
        "body": {"body": 1},
        "wheel": {"wheel": 2},
        "road": {"road": 3},
        "stroke": {"stroke": 4},
        "phi": [1.0, 2.0],
        "theta": [3.0, 4.0],
        "selected": ["FL", "RR"],
        "meta": {
            "px_per_m": 123.0,
            "body_offset_px": 45.0,
            "L_stroke_m": 0.25,
            "frame_dt_s": 0.02,
        },
        "sync_playhead": True,
        "playhead_storage_key": helpers.MECH_2D_PLAYHEAD_STORAGE_KEY,
        "dataset_id": "dataset-1",
        "cmd": {"reset_view": True},
        "height": helpers.MECH_2D_COMPONENT_HEIGHT,
        "key": helpers.MECH_2D_PICK_EVENT_KEY,
        "default": None,
    }


def test_build_mechanical_2d_fallback_payload_and_static_scheme_delegate_to_shared_contract(tmp_path: Path) -> None:
    payload = helpers.build_mechanical_2d_fallback_payload(
        dataset_id="dataset-2",
        time=[0.0],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        stroke={"stroke": 4},
        wheelbase=3.5,
        track=2.1,
        L_stroke_m=0.4,
        idx=7,
        show_controls=False,
        log_cb="log-cb",
    )

    assert payload == {
        "time": [0.0],
        "body": {"body": 1},
        "wheel": {"wheel": 2},
        "road": {"road": 3},
        "stroke": {"stroke": 4},
        "wheelbase_m": 3.5,
        "track_m": 2.1,
        "L_stroke_m": 0.4,
        "dataset_id": "dataset-2",
        "log_cb": "log-cb",
        "idx": 7,
        "show_controls": False,
    }

    missing = helpers.build_mechanical_2d_fallback_payload(
        dataset_id="dataset-3",
        time=[],
        body={},
        wheel={},
        road={},
        stroke={},
        wheelbase=1.0,
        track=1.0,
        L_stroke_m=0.1,
        log_cb=None,
    )
    assert "idx" not in missing
    assert "show_controls" not in missing

    safe_calls: list[tuple[str, str]] = []
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "mech_scheme.png").write_bytes(b"png")
    assert (
        helpers.render_mechanical_static_scheme(
            lambda path, *, caption: safe_calls.append((path, caption)),
            base_dir=tmp_path,
        )
        is True
    )
    assert safe_calls == [
        (str(assets_dir / "mech_scheme.png"), helpers.MECH_STATIC_SCHEME_CAPTION)
    ]


def test_render_mechanical_2d_component_or_fallback_prefers_component_and_returns_component() -> None:
    fake_st = _FakeStreamlit()
    component_calls: list[dict[str, object]] = []
    fallback_module = _FakeFallbackModule()

    result = helpers.render_mechanical_2d_component_or_fallback(
        fake_st,
        use_component_anim=True,
        get_component_fn=lambda: (lambda **kwargs: component_calls.append(kwargs)),
        component_payload={"component": 1},
        mech_fallback_module=fallback_module,
        fallback_payload={"fallback": 2},
        safe_image_fn=lambda *args, **kwargs: None,
        base_dir=Path("."),
    )

    assert result == "component"
    assert component_calls == [{"component": 1}]
    assert fallback_module.calls == []
    assert fake_st.warnings == []
    assert fake_st.infos == []


def test_render_mechanical_2d_component_or_fallback_uses_default_notice_and_fallback(tmp_path: Path) -> None:
    fake_st = _FakeStreamlit()
    fallback_module = _FakeFallbackModule()

    result = helpers.render_mechanical_2d_component_or_fallback(
        fake_st,
        use_component_anim=False,
        get_component_fn=lambda: (_ for _ in ()).throw(RuntimeError("should not be called")),
        component_payload={"component": 1},
        mech_fallback_module=fallback_module,
        fallback_payload={"fallback": 2},
        safe_image_fn=lambda *args, **kwargs: None,
        base_dir=tmp_path,
    )

    assert result == "fallback"
    assert fallback_module.calls == [{"fallback": 2}]
    assert fake_st.infos == [helpers.MECH_COMPONENT_DISABLED_INFO]
    assert fake_st.warnings == []


def test_render_mechanical_2d_component_or_fallback_uses_callbacks_and_static_when_needed(tmp_path: Path) -> None:
    fake_st = _FakeStreamlit()
    callback_events: list[str] = []
    safe_calls: list[tuple[str, str]] = []
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "mech_scheme.png").write_bytes(b"png")

    def _broken_component(**kwargs) -> None:
        raise RuntimeError("boom")

    result = helpers.render_mechanical_2d_component_or_fallback(
        fake_st,
        use_component_anim=True,
        get_component_fn=lambda: _broken_component,
        component_payload={"component": 1},
        mech_fallback_module=None,
        fallback_payload={"fallback": 2},
        safe_image_fn=lambda path, *, caption: safe_calls.append((path, caption)),
        base_dir=tmp_path,
        on_component_runtime_error=lambda exc: callback_events.append(f"runtime:{exc}"),
        on_fallback_missing=lambda: callback_events.append("fallback-missing"),
    )

    assert result == "static"
    assert callback_events == ["runtime:boom", "fallback-missing"]
    assert fake_st.warnings == []
    assert safe_calls == [
        (str(assets_dir / "mech_scheme.png"), helpers.MECH_STATIC_SCHEME_CAPTION)
    ]


def test_build_mechanical_2d_runtime_callbacks_preserves_missing_disabled_and_runtime_contract() -> None:
    fake_st = _FakeStreamlit()
    events: list[tuple[str, dict[str, object]]] = []

    callbacks = helpers.build_mechanical_2d_runtime_callbacks(
        fake_st,
        component_last_error_fn=lambda name: RuntimeError(f"{name}-err"),
        log_cb=lambda event, **kwargs: events.append((str(event), kwargs)),
        proc_metrics_fn=lambda: {"rss_mb": 8.5},
        fallback_error=RuntimeError("fallback-err"),
    )

    callbacks["on_component_runtime_error"](RuntimeError("boom-2d"))
    callbacks["on_component_missing"]()
    callbacks["on_component_disabled"]()
    callbacks["on_fallback_missing"]()

    assert fake_st.warnings == [
        "Компонент mech_anim упал во время выполнения. Показываю fallback (matplotlib).",
        helpers.MECH_COMPONENT_MISSING_WARNING,
        helpers.MECH_FALLBACK_MISSING_WARNING,
    ]
    assert fake_st.infos == []
    assert fake_st.expanders == [
        ("Диагностика mech_anim", False),
        ("Диагностика mech_anim", False),
        ("Диагностика mech_anim_fallback", False),
    ]
    assert fake_st.codes == [
        "mech_anim-err",
        "mech_anim-err",
        "fallback-err",
    ]
    assert events[0][0] == "component_runtime_error"
    assert events[0][1]["component"] == "mech_anim"
    assert events[0][1]["error"] == "RuntimeError('boom-2d')"
    assert isinstance(events[0][1]["traceback"], str)
    assert events[1] == (
        "component_missing",
        {
            "component": "mech_anim",
            "detail": "mech_anim-err",
            "proc": {"rss_mb": 8.5},
        },
    )
    assert events[2] == (
        "fallback_missing",
        {
            "component": "mech_anim_fallback",
            "detail": "fallback-err",
            "proc": {"rss_mb": 8.5},
        },
    )


def test_render_mechanical_2d_animation_panel_orchestrates_app_like_runtime() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    def _build_component_payload(session_state, **kwargs):
        calls.append(("build_component", kwargs["dataset_id"]))
        return {"component": 1}

    def _build_fallback_payload(**kwargs):
        calls.append(("build_fallback", kwargs["dataset_id"]))
        return {"fallback": 2}

    def _render_component(_st, **kwargs):
        calls.append(("render", kwargs["component_payload"]))
        assert kwargs["on_component_missing"] is None
        return "component"

    result = helpers.render_mechanical_2d_animation_panel(
        fake_st,
        session_state={},
        cache_key="cache-2d-app",
        dataset_id="dataset-2d-app",
        time=[0.0, 1.0],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        stroke={"stroke": 4},
        phi=[0.0, 0.1],
        theta=[0.0, 0.2],
        px_per_m=120.0,
        body_offset_px=40.0,
        L_stroke_m=0.3,
        frame_dt_s=0.02,
        wheelbase=2.8,
        track=1.6,
        use_component_anim=True,
        get_component_fn=lambda: object(),
        mech_fallback_module=None,
        log_cb=lambda *args, **kwargs: None,
        safe_image_fn=lambda *args, **kwargs: None,
        base_dir=Path("."),
        build_component_payload_fn=_build_component_payload,
        build_fallback_payload_fn=_build_fallback_payload,
        render_component_or_fallback_fn=_render_component,
    )

    assert result["component_payload"] == {"component": 1}
    assert result["fallback_payload"] == {"fallback": 2}
    assert result["callbacks"] == {}
    assert result["render_status"] == "component"
    assert calls == [
        ("build_component", "dataset-2d-app"),
        ("build_fallback", "dataset-2d-app"),
        ("render", {"component": 1}),
    ]


def test_render_mechanical_2d_animation_panel_orchestrates_heavy_runtime_callbacks() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    def _build_callbacks(_st, **kwargs):
        calls.append(("build_callbacks", kwargs["fallback_error"]))
        return {
            "on_component_runtime_error": "runtime",
            "on_component_missing": "missing",
            "on_component_disabled": "disabled",
            "on_fallback_missing": "fallback",
        }

    def _render_component(_st, **kwargs):
        calls.append(
            (
                "render",
                (
                    kwargs["fallback_payload"]["idx"],
                    kwargs["fallback_payload"]["show_controls"],
                    kwargs["on_component_runtime_error"],
                    kwargs["on_component_missing"],
                    kwargs["on_component_disabled"],
                    kwargs["on_fallback_missing"],
                ),
            )
        )
        return "fallback"

    result = helpers.render_mechanical_2d_animation_panel(
        fake_st,
        session_state={},
        cache_key="cache-2d-heavy",
        dataset_id="dataset-2d-heavy",
        time=[0.0, 1.0],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        stroke={"stroke": 4},
        phi=[0.0, 0.1],
        theta=[0.0, 0.2],
        px_per_m=100.0,
        body_offset_px=30.0,
        L_stroke_m=0.25,
        frame_dt_s=0.01,
        wheelbase=1.7,
        track=1.2,
        use_component_anim=True,
        get_component_fn=lambda: object(),
        mech_fallback_module="fallback-module",
        log_cb=lambda *args, **kwargs: None,
        safe_image_fn=lambda *args, **kwargs: None,
        base_dir=Path("."),
        idx=12,
        show_controls=False,
        component_last_error_fn=lambda name: RuntimeError(f"{name}-err"),
        proc_metrics_fn=lambda: {"rss_mb": 1.0},
        fallback_error=RuntimeError("fallback-err"),
        build_callbacks_fn=_build_callbacks,
        render_component_or_fallback_fn=_render_component,
    )

    assert result["callbacks"]["on_component_missing"] == "missing"
    assert result["render_status"] == "fallback"
    assert calls[0][0] == "build_callbacks"
    assert repr(calls[0][1]) == "RuntimeError('fallback-err')"
    assert calls[1] == ("render", (12, False, "runtime", "missing", "disabled", "fallback"))


def test_render_mechanical_animation_section_orchestrates_app_like_2d_path() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    def _intro(_st, *, df_main):
        calls.append(("intro", list(df_main.columns)))
        return True

    def _backend(_st, _session_state, **kwargs):
        calls.append(("backend", kwargs["default_backend_index"]))
        return True

    def _render_2d(_st, **kwargs):
        calls.append(("2d", kwargs["dataset_id"]))
        return {"render_status": "component"}

    def _render_3d(_st, **kwargs):
        calls.append(("3d", kwargs["dataset_id"]))
        return {"render_status": "component"}

    def _assets(_st, **kwargs):
        calls.append(("assets", kwargs["base_dir"]))

    result = helpers.render_mechanical_animation_section(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-section-app",
        dataset_id="dataset-section-app",
        df_main=pd.DataFrame({"время_с": [0.0, 1.0]}),
        time=[0.0, 1.0],
        body_2d={"body": 1},
        body_3d={"body3d": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        stroke={"stroke": 4},
        phi=[0.0, 0.1],
        theta=[0.0, 0.2],
        px_per_m=100.0,
        body_offset_px=30.0,
        L_stroke_m=0.25,
        frame_dt_s=0.02,
        wheelbase=2.8,
        track=1.6,
        playhead_idx=None,
        show_2d_controls=None,
        base_override={},
        log_cb=lambda *args, **kwargs: None,
        proc_metrics_fn=lambda: {"rss_mb": 1.0},
        safe_image_fn=lambda *args, **kwargs: None,
        base_dir=Path("."),
        get_mech_anim_component_fn=lambda: object(),
        get_mech_car3d_component_fn=lambda: object(),
        mech_fallback_module=None,
        backend_default_index=1,
        backend_description_text="component-first",
        path_checkbox_label="demo label",
        path_demo_options=["Статика (без движения)"],
        path_demo_info_text="demo info",
        path_non_demo_caption="static caption",
        base_default=2.8,
        track_default=1.6,
        camera_follow_default=True,
        road_mesh_step_default=6,
        intro_fn=_intro,
        backend_selector_fn=_backend,
        render_2d_panel_fn=_render_2d,
        render_3d_panel_fn=_render_3d,
        asset_expander_fn=_assets,
    )

    assert result["proceed"] is True
    assert result["use_component_anim"] is True
    assert result["mech_view"] == "2D (схема)"
    assert result["panel_result"] == {"render_status": "component"}
    assert calls == [
        ("intro", ["время_с"]),
        ("backend", 1),
        ("2d", "dataset-section-app"),
        ("assets", Path(".")),
    ]


def test_render_mechanical_animation_section_orchestrates_heavy_3d_path() -> None:
    fake_st = _FakeStreamlit()
    fake_st.radio_overrides["mech_view_cache-section-heavy"] = "3D (машинка)"
    calls: list[tuple[str, object]] = []

    def _backend(_st, _session_state, **kwargs):
        calls.append(("backend", kwargs["default_backend_index"]))
        return False

    def _render_2d(_st, **kwargs):
        calls.append(("2d", kwargs["dataset_id"]))
        return {"render_status": "component"}

    def _render_3d(_st, **kwargs):
        calls.append(
            (
                "3d",
                (
                    kwargs["dataset_id"],
                    kwargs["model_path_available"],
                    list(kwargs["model_speed_values"]),
                    kwargs["get_float_param_fn"]("x", "y", default=1.0),
                    kwargs["ring_visual_test_pick"],
                ),
            )
        )
        return {"render_status": "runtime_error"}

    result = helpers.render_mechanical_animation_section(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-section-heavy",
        dataset_id="dataset-section-heavy",
        df_main=pd.DataFrame(
            {
                "время_с": [0.0, 1.0],
                "скорость_vx_м_с": [5.0, 7.0],
                "yaw_рад": [0.0, 0.1],
            }
        ),
        time=[0.0, 1.0],
        body_2d={"body": 1},
        body_3d={"body3d": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        stroke={"stroke": 4},
        phi=[0.0, 0.1],
        theta=[0.0, 0.2],
        px_per_m=100.0,
        body_offset_px=30.0,
        L_stroke_m=0.25,
        frame_dt_s=0.02,
        wheelbase=1.7,
        track=1.2,
        playhead_idx=12,
        show_2d_controls=False,
        base_override={},
        log_cb=lambda *args, **kwargs: None,
        proc_metrics_fn=lambda: {"rss_mb": 1.0},
        safe_image_fn=lambda *args, **kwargs: None,
        base_dir=Path("."),
        get_mech_anim_component_fn=lambda: object(),
        get_mech_car3d_component_fn=lambda: object(),
        mech_fallback_module="fb",
        backend_default_index=0,
        backend_description_text="fallback-first",
        path_checkbox_label="heavy label",
        path_demo_options=["По vx/yaw из модели"],
        path_demo_info_text="heavy info",
        path_non_demo_caption="heavy static",
        base_default=1.5,
        track_default=1.0,
        camera_follow_default=False,
        road_mesh_step_default=2,
        get_float_param_fn=lambda *args, **kwargs: 1.7,
        enable_model_path_mode=True,
        model_path_caption="model caption",
        component_last_error_fn=lambda name: None,
        fallback_error=RuntimeError("fallback-err"),
        ring_visual_tests_map={"t": {"cfg": True}},
        ring_visual_test_pick="test-1",
        ring_visual_pick=Path("pick.npz"),
        ring_visual_workspace_exports_dir=Path("."),
        ring_visual_latest_export_paths_fn=lambda *args, **kwargs: (Path("latest.npz"), None),
        ring_visual_base_dir=Path("."),
        backend_selector_fn=_backend,
        render_2d_panel_fn=_render_2d,
        render_3d_panel_fn=_render_3d,
        asset_expander_fn=lambda *args, **kwargs: calls.append(("assets", kwargs["base_dir"])),
    )

    assert result["proceed"] is True
    assert result["use_component_anim"] is False
    assert result["mech_view"] == "3D (машинка)"
    assert result["panel_result"] == {"render_status": "runtime_error"}
    assert calls == [
        ("backend", 0),
        ("3d", ("dataset-section-heavy", True, [5.0, 7.0], 1.7, "test-1")),
        ("assets", Path(".")),
    ]


def test_render_mechanical_3d_intro_uses_shared_caption() -> None:
    fake_st = _FakeStreamlit()

    helpers.render_mechanical_3d_intro(fake_st)

    assert fake_st.captions == [helpers.MECH_3D_INTRO_CAPTION]


def test_render_mechanical_3d_maneuver_controls_renders_inputs_in_demo_mode() -> None:
    fake_st = _FakeStreamlit()

    values = helpers.render_mechanical_3d_maneuver_controls(
        fake_st,
        cache_key="cache-3d",
        demo_paths=True,
        path_mode="Слалом",
    )

    assert values == (1.5, 4.0, 0.15, 35.0, "влево")
    assert [item["label"] for item in fake_st.number_inputs] == [
        "Слалом: амплитуда (м)",
        "Слалом: период (с)",
        "Сглаживание yaw (0..1)",
        "Поворот: радиус R (м)",
    ]
    assert fake_st.markdowns == ["**Поворот/радиус (для манёвра)**"]
    assert fake_st.selectboxes == [
        {
            "label": "Поворот: направление",
            "options": ["влево", "вправо"],
            "index": 0,
            "key": "mech3d_turn_dir_cache-3d",
        }
    ]


def test_render_mechanical_3d_maneuver_controls_uses_hidden_defaults_and_world_path_zero_smoothing() -> None:
    fake_st = _FakeStreamlit()

    world_values = helpers.render_mechanical_3d_maneuver_controls(
        fake_st,
        cache_key="cache-3d",
        demo_paths=False,
        path_mode="По vx/yaw из модели",
    )
    normal_values = helpers.render_mechanical_3d_maneuver_controls(
        fake_st,
        cache_key="cache-3d",
        demo_paths=False,
        path_mode="Статика (без движения)",
    )

    assert world_values == (1.5, 4.0, 0.0, 35.0, "влево")
    assert normal_values == (1.5, 4.0, 0.15, 35.0, "влево")
    assert fake_st.number_inputs == []
    assert fake_st.selectboxes == []


def test_render_mechanical_3d_path_controls_renders_demo_ui_and_returns_inputs() -> None:
    fake_st = _FakeStreamlit()
    fake_st.checkbox_overrides["mech3d_demo_paths_cache-path"] = True

    values = helpers.render_mechanical_3d_path_controls(
        fake_st,
        cache_key="cache-path",
        checkbox_label="demo label",
        demo_options=["Статика (без движения)", "Слалом"],
        demo_info_text="demo info",
        non_demo_caption="non-demo caption",
    )

    assert values == (True, "Статика (без движения)", 12.0, 1.0, 1.0, 35.0)
    assert fake_st.checkboxes == [
        {
            "label": "demo label",
            "value": False,
            "key": "mech3d_demo_paths_cache-path",
        }
    ]
    assert fake_st.infos == ["demo info"]
    assert [item["label"] for item in fake_st.number_inputs] == [
        "v0, м/с",
        "масштаб бокового смещения",
        "усиление руления (по φ)",
    ]
    assert fake_st.sliders == [
        {
            "label": "ограничение руления, град",
            "min_value": 0,
            "max_value": 60,
            "value": 35,
            "step": 1,
            "key": "mech3d_steer_max_deg_cache-path",
        }
    ]


def test_render_mechanical_3d_path_controls_uses_static_non_demo_defaults() -> None:
    fake_st = _FakeStreamlit()

    values = helpers.render_mechanical_3d_path_controls(
        fake_st,
        cache_key="cache-path",
        checkbox_label="demo label",
        demo_options=["Статика (без движения)", "Слалом"],
        demo_info_text="demo info",
        non_demo_caption="static caption",
    )

    assert values == (False, helpers.MECH_3D_STATIC_MODE, 12.0, 1.0, 1.0, 35.0)
    assert fake_st.captions == ["static caption"]
    assert fake_st.number_inputs == []
    assert fake_st.selectboxes == []
    assert fake_st.sliders == []


def test_render_mechanical_3d_path_controls_uses_model_path_defaults_when_available() -> None:
    fake_st = _FakeStreamlit()

    values = helpers.render_mechanical_3d_path_controls(
        fake_st,
        cache_key="cache-path",
        checkbox_label="demo label",
        demo_options=["Статика (без движения)", "Слалом"],
        demo_info_text="demo info",
        non_demo_caption="static caption",
        model_path_available=True,
        model_path_caption="model caption",
        model_speed_values=[5.0, 7.0],
    )

    assert values == (False, helpers.MECH_3D_MODEL_PATH_MODE, 6.0, 1.0, 1.0, 35.0)
    assert fake_st.captions == ["model caption"]


def test_render_mechanical_3d_visual_controls_uses_defaults_and_reset_button_contract() -> None:
    fake_st = _FakeStreamlit()
    fake_st.button_overrides["mech3d_reset_view_cache-viz"] = True

    values = helpers.render_mechanical_3d_visual_controls(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-viz",
        base_override={},
        base_default=2.8,
        track_default=1.6,
        camera_follow_default=True,
        road_mesh_step_default=6,
    )

    assert values["base_m"] == 2.8
    assert values["track_m"] == 1.6
    assert values["camera_follow"] is True
    assert values["road_mesh_step"] == 6
    assert values["road_mode"] == "track"
    assert values["show_trail"] is True
    assert fake_st.session_state["mech3d_cmd_cache-viz"]["reset_view"] is True
    assert isinstance(fake_st.session_state["mech3d_cmd_cache-viz"]["ts"], float)
    assert [item["key"] for item in fake_st.buttons] == ["mech3d_reset_view_cache-viz"]


def test_render_mechanical_3d_visual_controls_uses_get_float_param_hook_for_heavy_ui() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, float]] = []

    def _get_float_param(base_override, name: str, *, default: float) -> float:
        calls.append((name, float(default)))
        return {"база": 1.7, "колея": 1.2}[name]

    values = helpers.render_mechanical_3d_visual_controls(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-heavy",
        base_override={"база": "unused", "колея": "unused"},
        base_default=1.5,
        track_default=1.0,
        camera_follow_default=False,
        road_mesh_step_default=2,
        get_float_param_fn=_get_float_param,
    )

    assert calls == [("база", 1.5), ("колея", 1.0)]
    assert values["base_m"] == 1.7
    assert values["track_m"] == 1.2
    assert values["camera_follow"] is False
    assert values["road_mesh_step"] == 2
    assert "mech3d_cmd_cache-heavy" not in fake_st.session_state


def test_render_mechanical_3d_body_controls_uses_session_defaults_and_updates_keys() -> None:
    fake_st = _FakeStreamlit()
    fake_st.session_state.update(
        {
            "mech3d_body_L_cache-body": 2.9,
            "mech3d_body_W_cache-body": 1.4,
            "mech3d_body_H_cache-body": 0.42,
        }
    )

    body_L, body_W, body_H = helpers.render_mechanical_3d_body_controls(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-body",
        base_m=3.0,
        track_m=1.8,
    )

    assert (body_L, body_W, body_H) == (2.9, 1.4, 0.42)
    assert [item["key"] for item in fake_st.number_inputs[-3:]] == [
        "mech3d_body_L_cache-body",
        "mech3d_body_W_cache-body",
        "mech3d_body_H_cache-body",
    ]


def test_build_mechanical_3d_geo_payload_includes_offsets_dims_and_extra_geo() -> None:
    geo = helpers.build_mechanical_3d_geo_payload(
        base_m=2.8,
        track_m=1.6,
        wheel_r=0.32,
        wheel_w=0.22,
        wheel_center_offset=0.05,
        road_y_offset=-0.03,
        road_subtract_radius=True,
        road_mode="local",
        spin_per_wheel=False,
        show_suspension=True,
        show_contact=False,
        multi_view=True,
        allow_pan=False,
        show_road_mesh=True,
        road_mesh_step=4,
        show_trail=True,
        trail_len=600,
        trail_step=5,
        y_sign=-1.0,
        camera_follow=True,
        camera_follow_heading=False,
        camera_follow_selected=True,
        hover_tooltip=False,
        debug_overlay=True,
        follow_smooth=0.35,
        show_gap_heat=True,
        gap_scale_m=0.07,
        show_gap_hud=False,
        min_gap_window=500,
        min_gap_step=4,
        hover_contact_marker=False,
        show_minimap=True,
        minimap_size=180,
        body_y_off=0.6,
        body_L=2.38,
        body_W=0.88,
        body_H=0.4,
        road_win=240,
        extra_geo={"ring_visual": {"ring": True}},
    )

    assert geo["base_m"] == 2.8
    assert geo["track_m"] == 1.6
    assert geo["body_L_m"] == 2.38
    assert geo["body_W_m"] == 0.88
    assert geo["body_H_m"] == 0.4
    assert geo["road_mode"] == "local"
    assert geo["road_window_points"] == 240
    assert geo["wheel_x_off_m"]["ЛП"] == 1.4
    assert geo["wheel_z_off_m"]["ПП"] == 0.8
    assert geo["ring_visual"] == {"ring": True}


def test_build_mechanical_3d_component_payload_keeps_playhead_and_selection_contract() -> None:
    payload = helpers.build_mechanical_3d_component_payload(
        {"mech_selected_corners": ["ЛП", "ПЗ"]},
        dataset_id="dataset-3d",
        time=[0.0, 0.1],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        phi=_Arrayish([1.0, 2.0]),
        theta=[3.0, 4.0],
        path={"x": [0.0, 1.0]},
        geo={"base_m": 2.8},
    )

    assert payload == {
        "title": helpers.MECH_3D_COMPONENT_TITLE,
        "time": [0.0, 0.1],
        "body": {"body": 1},
        "wheel": {"wheel": 2},
        "road": {"road": 3},
        "phi": [1.0, 2.0],
        "theta": [3.0, 4.0],
        "selected": ["ЛП", "ПЗ"],
        "path": {"x": [0.0, 1.0]},
        "geo": {"base_m": 2.8},
        "dataset_id": "dataset-3d",
        "playhead_storage_key": helpers.MECH_2D_PLAYHEAD_STORAGE_KEY,
        "height": helpers.MECH_3D_COMPONENT_HEIGHT,
        "key": helpers.MECH_3D_COMPONENT_KEY,
        "default": None,
    }


def test_render_mechanical_3d_control_panel_builds_visuals_and_static_path_defaults() -> None:
    fake_st = _FakeStreamlit()

    values = helpers.render_mechanical_3d_control_panel(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-control",
        df_main=pd.DataFrame(),
        time_s=[0.0, 1.0],
        base_override={},
        path_checkbox_label="demo label",
        path_demo_options=["Статика (без движения)", "Слалом"],
        path_demo_info_text="demo info",
        path_non_demo_caption="static caption",
        base_default=2.8,
        track_default=1.6,
        camera_follow_default=True,
        road_mesh_step_default=6,
    )

    assert values["base_m"] == 2.8
    assert values["track_m"] == 1.6
    assert values["camera_follow"] is True
    assert values["road_mesh_step"] == 6
    assert values["path_payload"]["x"] == [0.0, 0.0]
    assert values["path_payload"]["yaw"] == [0.0, 0.0]
    assert fake_st.captions == ["static caption"]


def test_render_mechanical_3d_control_panel_supports_heavy_model_path_mode() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, float]] = []

    def _get_float_param(base_override, name: str, *, default: float) -> float:
        calls.append((name, float(default)))
        return {"база": 1.7, "колея": 1.2}[name]

    values = helpers.render_mechanical_3d_control_panel(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-heavy-control",
        df_main=pd.DataFrame(
            {
                "скорость_vx_м_с": [5.0, 7.0],
                "yaw_рад": [0.0, math.pi / 2.0],
            }
        ),
        time_s=[0.0, 1.0],
        base_override={"база": "unused", "колея": "unused"},
        path_checkbox_label="heavy label",
        path_demo_options=["По vx/yaw из модели", "Статика (без движения)"],
        path_demo_info_text="heavy info",
        path_non_demo_caption="heavy static caption",
        base_default=1.5,
        track_default=1.0,
        camera_follow_default=False,
        road_mesh_step_default=2,
        get_float_param_fn=_get_float_param,
        model_path_available=True,
        model_path_caption="model caption",
        model_speed_values=[5.0, 7.0],
    )

    assert calls == [("база", 1.5), ("колея", 1.0)]
    assert values["base_m"] == 1.7
    assert values["track_m"] == 1.2
    assert values["camera_follow"] is False
    assert values["road_mesh_step"] == 2
    assert values["path_payload"]["yaw"] == [0.0, math.pi / 2.0]
    assert abs(values["path_payload"]["z"][1] - 7.0) < 1e-9
    assert fake_st.captions == ["model caption"]


def test_normalize_mechanical_3d_control_values_coerces_shared_runtime_types() -> None:
    path_payload = {"x": [0.0, 1.0]}

    values = helpers.normalize_mechanical_3d_control_values(
        {
            "base_m": "2.8",
            "track_m": 1.6,
            "wheel_r": "0.32",
            "wheel_w": 0.22,
            "body_y_off": "0.6",
            "road_win": "220",
            "y_sign": "-1",
            "wheel_center_offset": "0.05",
            "road_y_offset": -0.03,
            "road_subtract_radius": 1,
            "camera_follow": 0,
            "camera_follow_heading": True,
            "camera_follow_selected": False,
            "follow_smooth": "0.25",
            "hover_tooltip": 1,
            "show_minimap": 0,
            "minimap_size": "160",
            "road_mode": "track",
            "spin_per_wheel": 1,
            "show_suspension": True,
            "show_contact": 1,
            "show_gap_heat": 0,
            "gap_scale_m": "0.05",
            "show_gap_hud": 1,
            "min_gap_window": "300",
            "min_gap_step": "3",
            "hover_contact_marker": 1,
            "multi_view": 0,
            "allow_pan": 1,
            "debug_overlay": 0,
            "show_road_mesh": 1,
            "road_mesh_step": "6",
            "show_trail": 1,
            "trail_len": "500",
            "trail_step": "3",
            "path_payload": path_payload,
        }
    )

    assert values["base_m"] == 2.8
    assert values["track_m"] == 1.6
    assert values["wheel_r"] == 0.32
    assert values["road_win"] == 220
    assert values["y_sign"] == -1.0
    assert values["road_subtract_radius"] is True
    assert values["camera_follow"] is False
    assert values["hover_tooltip"] is True
    assert values["minimap_size"] == 160
    assert values["road_mode"] == "track"
    assert values["trail_len"] == 500
    assert values["path_payload"] is path_payload


def test_build_mechanical_3d_fallback_payload_serializes_arrays_and_runtime_contract() -> None:
    payload = helpers.build_mechanical_3d_fallback_payload(
        dataset_id="dataset-3d-fallback",
        time=[0.0, 0.2],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        phi=_Arrayish([1.0, 2.0]),
        theta=[3.0, 4.0],
        path={"x": [0.0, 1.0]},
        wheelbase=2.8,
        track=1.6,
        log_cb="log-cb",
    )

    assert payload == {
        "time": [0.0, 0.2],
        "body": {"body": 1},
        "wheel": {"wheel": 2},
        "road": {"road": 3},
        "phi": [1.0, 2.0],
        "theta": [3.0, 4.0],
        "path": {"x": [0.0, 1.0]},
        "wheelbase_m": 2.8,
        "track_m": 1.6,
        "dataset_id": "dataset-3d-fallback",
        "log_cb": "log-cb",
    }


def test_prepare_mechanical_3d_component_runtime_builds_shared_body_geo_and_component_payloads() -> None:
    fake_st = _FakeStreamlit()
    fallback_module = _FakeFallbackModule()
    component = object()
    fake_st.session_state.update(
        {
            "mech_selected_corners": ["ЛП"],
            "mech3d_body_L_cache-runtime": 2.4,
            "mech3d_body_W_cache-runtime": 1.1,
            "mech3d_body_H_cache-runtime": 0.38,
        }
    )
    mech3d_values = helpers.normalize_mechanical_3d_control_values(
        {
            "base_m": 2.8,
            "track_m": 1.6,
            "wheel_r": 0.32,
            "wheel_w": 0.22,
            "body_y_off": 0.6,
            "road_win": 220,
            "y_sign": 1.0,
            "wheel_center_offset": 0.0,
            "road_y_offset": 0.0,
            "road_subtract_radius": False,
            "camera_follow": True,
            "camera_follow_heading": False,
            "camera_follow_selected": False,
            "follow_smooth": 0.25,
            "hover_tooltip": True,
            "show_minimap": False,
            "minimap_size": 160,
            "road_mode": "track",
            "spin_per_wheel": True,
            "show_suspension": True,
            "show_contact": True,
            "show_gap_heat": True,
            "gap_scale_m": 0.05,
            "show_gap_hud": True,
            "min_gap_window": 300,
            "min_gap_step": 3,
            "hover_contact_marker": True,
            "multi_view": False,
            "allow_pan": True,
            "debug_overlay": False,
            "show_road_mesh": True,
            "road_mesh_step": 6,
            "show_trail": True,
            "trail_len": 500,
            "trail_step": 3,
            "path_payload": {"x": [0.0, 1.0]},
        }
    )

    result = helpers.prepare_mechanical_3d_component_runtime(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-runtime",
        dataset_id="dataset-3d-runtime",
        time=[0.0, 0.1],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        phi=_Arrayish([1.0, 2.0]),
        theta=[3.0, 4.0],
        mech3d_values=mech3d_values,
        use_component_anim=True,
        get_component_fn=lambda: component,
        mech_fallback_module=fallback_module,
        log_cb="log-cb",
        extra_geo={"ring_visual": {"ring": True}},
    )

    assert result["status"] == "component"
    assert result["mech3d_comp"] is component
    assert result["body_L"] == 2.4
    assert result["body_W"] == 1.1
    assert result["body_H"] == 0.38
    assert result["fallback_payload"]["dataset_id"] == "dataset-3d-runtime"
    assert result["geo_payload"]["ring_visual"] == {"ring": True}
    assert result["component_payload"]["selected"] == ["ЛП"]
    assert result["component_payload"]["geo"] == result["geo_payload"]
    assert result["component_payload"]["path"] is mech3d_values["path_payload"]
    assert fallback_module.calls == []


def test_prepare_mechanical_3d_component_runtime_uses_fallback_and_skips_geo_when_component_missing() -> None:
    fake_st = _FakeStreamlit()
    fallback_module = _FakeFallbackModule()
    events: list[str] = []
    mech3d_values = helpers.normalize_mechanical_3d_control_values(
        {
            "base_m": 2.8,
            "track_m": 1.6,
            "wheel_r": 0.32,
            "wheel_w": 0.22,
            "body_y_off": 0.6,
            "road_win": 220,
            "y_sign": 1.0,
            "wheel_center_offset": 0.0,
            "road_y_offset": 0.0,
            "road_subtract_radius": False,
            "camera_follow": True,
            "camera_follow_heading": False,
            "camera_follow_selected": False,
            "follow_smooth": 0.25,
            "hover_tooltip": True,
            "show_minimap": False,
            "minimap_size": 160,
            "road_mode": "track",
            "spin_per_wheel": True,
            "show_suspension": True,
            "show_contact": True,
            "show_gap_heat": True,
            "gap_scale_m": 0.05,
            "show_gap_hud": True,
            "min_gap_window": 300,
            "min_gap_step": 3,
            "hover_contact_marker": True,
            "multi_view": False,
            "allow_pan": True,
            "debug_overlay": False,
            "show_road_mesh": True,
            "road_mesh_step": 6,
            "show_trail": True,
            "trail_len": 500,
            "trail_step": 3,
            "path_payload": {"x": [0.0, 1.0]},
        }
    )

    result = helpers.prepare_mechanical_3d_component_runtime(
        fake_st,
        session_state=fake_st.session_state,
        cache_key="cache-runtime",
        dataset_id="dataset-3d-runtime",
        time=[0.0, 0.1],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        phi=_Arrayish([1.0, 2.0]),
        theta=[3.0, 4.0],
        mech3d_values=mech3d_values,
        use_component_anim=True,
        get_component_fn=lambda: None,
        mech_fallback_module=fallback_module,
        log_cb="log-cb",
        on_component_missing=lambda: events.append("missing"),
    )

    assert result["status"] == "fallback"
    assert result["mech3d_comp"] is None
    assert result["geo_payload"] is None
    assert result["component_payload"] is None
    assert fallback_module.calls == [result["fallback_payload"]]
    assert events == ["missing"]


def test_prepare_mechanical_3d_ring_visual_uses_spec_and_embeds_path_payload() -> None:
    calls: list[tuple[str, object]] = []

    def _load_spec_from_test_cfg(test_cfg, *, base_dir):
        calls.append(("load_spec", test_cfg))
        return {"segments": [{}], "seed": 7}

    def _build_visual(spec, *, track_m, wheel_width_m, seed):
        calls.append(("build_visual", (track_m, wheel_width_m, seed)))
        return {"ring_length_m": 12.0, "meta": {"seam_max_jump_m": 0.003}}

    def _build_nominal(spec, time_s):
        calls.append(("build_nominal", list(time_s)))
        return {"distance_m": [0.0, 1.0], "v_mps": [2.0, 2.5]}

    def _embed_payload(path_payload, ring_visual, *, wheelbase_m):
        calls.append(("embed", wheelbase_m))
        out = dict(path_payload)
        out["embedded"] = True
        return out

    ring_visual, path_payload = helpers.prepare_mechanical_3d_ring_visual(
        tests_map={"test-1": {"cfg": True}},
        test_pick="test-1",
        base_dir=Path("."),
        pick="run.json",
        session_state={},
        workspace_exports_dir=Path("."),
        time_s=[0.0, 1.0],
        path_payload={"x": [0.0, 1.0], "v": [1.0, 1.0]},
        track_m=1.6,
        wheel_width_m=0.22,
        wheelbase_m=2.8,
        log_cb=lambda *args, **kwargs: None,
        latest_export_paths_fn=lambda workspace_exports_dir, ensure_exists=False: (Path("latest.npz"), None),
        load_spec_from_test_cfg_fn=_load_spec_from_test_cfg,
        load_spec_from_npz_fn=lambda path: None,
        build_visual_payload_fn=_build_visual,
        build_nominal_progress_fn=_build_nominal,
        embed_path_payload_fn=_embed_payload,
    )

    assert ring_visual == {"ring_length_m": 12.0, "meta": {"seam_max_jump_m": 0.003}}
    assert path_payload["s"] == [0.0, 1.0]
    assert path_payload["v"] == [2.0, 2.5]
    assert path_payload["embedded"] is True
    assert calls == [
        ("load_spec", {"cfg": True}),
        ("build_visual", (1.6, 0.22, 7)),
        ("build_nominal", [0.0, 1.0]),
        ("embed", 2.8),
    ]


def test_prepare_mechanical_3d_ring_visual_uses_npz_sidecar_and_logs_event(tmp_path: Path) -> None:
    events: list[tuple[tuple[object, ...], dict[str, object]]] = []
    pick_npz = tmp_path / "pick.npz"
    latest_npz = tmp_path / "latest.npz"
    pick_npz.write_bytes(b"npz")
    latest_npz.write_bytes(b"npz")

    load_calls: list[str] = []

    def _load_spec_from_npz(path) -> dict[str, object] | None:
        load_calls.append(str(Path(path).name))
        if Path(path).name == "pick.npz":
            return {"segments": [{}], "seed": 0}
        return None

    ring_visual, path_payload = helpers.prepare_mechanical_3d_ring_visual(
        tests_map={},
        test_pick="test-2",
        base_dir=tmp_path,
        pick=pick_npz,
        session_state={"anim_latest_npz": str(tmp_path / "session_latest.npz")},
        workspace_exports_dir=tmp_path,
        time_s=[0.0, 1.0],
        path_payload={"x": [0.0, 1.0]},
        track_m=1.2,
        wheel_width_m=0.3,
        wheelbase_m=2.0,
        log_cb=lambda *args, **kwargs: events.append((args, kwargs)),
        latest_export_paths_fn=lambda workspace_exports_dir, ensure_exists=False: (latest_npz, None),
        load_spec_from_test_cfg_fn=lambda test_cfg, *, base_dir: None,
        load_spec_from_npz_fn=_load_spec_from_npz,
        build_visual_payload_fn=lambda spec, *, track_m, wheel_width_m, seed: {"ring": True},
        build_nominal_progress_fn=lambda spec, time_s: {"distance_m": [], "v_mps": []},
        embed_path_payload_fn=lambda path_payload, ring_visual, *, wheelbase_m: dict(path_payload, ring_mode=True),
    )

    assert ring_visual == {"ring": True}
    assert path_payload["ring_mode"] is True
    assert load_calls[0] == "pick.npz"
    assert events == [
        (
            ("ring_visual_loaded_from_npz_sidecar",),
            {"npz": str(pick_npz), "test": "test-2"},
        )
    ]


def test_render_mechanical_3d_ring_visual_notice_uses_shared_summary() -> None:
    fake_st = _FakeStreamlit()

    helpers.render_mechanical_3d_ring_visual_notice(
        fake_st,
        {"ring_length_m": 42.5, "meta": {"seam_max_jump_m": 0.0015}},
    )

    assert fake_st.infos == [
        "3D кольцо: замкнутый ring-view, сегменты подсвечены по краям, heatmap = кривизна. Длина кольца ≈ 42.50 м, post-seam ≈ 1.5 мм."
    ]


def test_render_mechanical_3d_component_from_runtime_runs_component_and_notice() -> None:
    fake_st = _FakeStreamlit()
    calls: list[dict[str, object]] = []

    result = helpers.render_mechanical_3d_component_from_runtime(
        fake_st,
        {
            "status": "component",
            "mech3d_comp": lambda **kwargs: calls.append(kwargs),
            "component_payload": {"payload": 1},
        },
        ring_visual={"ring_length_m": 10.0, "meta": {"seam_max_jump_m": 0.002}},
    )

    assert result == "component"
    assert calls == [{"payload": 1}]
    assert len(fake_st.infos) == 1
    assert "Длина кольца ≈ 10.00 м" in fake_st.infos[0]


def test_render_mechanical_3d_component_from_runtime_returns_status_when_component_missing() -> None:
    fake_st = _FakeStreamlit()

    result = helpers.render_mechanical_3d_component_from_runtime(
        fake_st,
        {
            "status": "fallback",
            "mech3d_comp": None,
            "component_payload": None,
        },
    )

    assert result == "fallback"
    assert fake_st.infos == []


def test_render_mechanical_3d_component_from_runtime_uses_runtime_error_callback() -> None:
    fake_st = _FakeStreamlit()
    events: list[str] = []

    def _broken_component(**kwargs) -> None:
        raise RuntimeError("boom-3d")

    result = helpers.render_mechanical_3d_component_from_runtime(
        fake_st,
        {
            "status": "component",
            "mech3d_comp": _broken_component,
            "component_payload": {"payload": 1},
        },
        on_runtime_error=lambda exc: events.append(str(exc)),
    )

    assert result == "runtime_error"
    assert events == ["boom-3d"]


def test_build_mechanical_3d_runtime_callbacks_preserves_missing_disabled_and_runtime_contract(tmp_path: Path) -> None:
    fake_st = _FakeStreamlit()
    safe_calls: list[tuple[str, str]] = []
    events: list[tuple[str, dict[str, object]]] = []
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "mech_scheme.png").write_bytes(b"png")

    callbacks = helpers.build_mechanical_3d_runtime_callbacks(
        fake_st,
        component_last_error_fn=lambda name: RuntimeError(f"{name}-err"),
        log_cb=lambda event, **kwargs: events.append((str(event), kwargs)),
        proc_metrics_fn=lambda: {"rss_mb": 12.5},
        safe_image_fn=lambda path, *, caption: safe_calls.append((path, caption)),
        base_dir=tmp_path,
    )

    callbacks["on_component_missing"]()
    callbacks["on_component_disabled"]()
    callbacks["on_fallback_missing"]()
    callbacks["on_runtime_error"](RuntimeError("boom-runtime"))

    assert fake_st.warnings == [
        helpers.MECH_3D_COMPONENT_MISSING_WARNING,
        "Компонент мех. 3D (mech_car3d) упал во время выполнения. Показываю статическую схему.",
    ]
    assert fake_st.infos == [helpers.MECH_3D_COMPONENT_DISABLED_INFO]
    assert fake_st.errors == [helpers.MECH_3D_FALLBACK_MISSING_ERROR]
    assert events[0] == (
        "component_missing",
        {
            "component": "mech_car3d",
            "detail": "mech_car3d-err",
            "proc": {"rss_mb": 12.5},
        },
    )
    assert events[1][0] == "component_runtime_error"
    assert events[1][1]["component"] == "mech_car3d"
    assert events[1][1]["error"] == "RuntimeError('boom-runtime')"
    assert isinstance(events[1][1]["traceback"], str)
    assert safe_calls == [
        (str(assets_dir / "mech_scheme.png"), helpers.MECH_STATIC_SCHEME_CAPTION)
    ]


def test_render_mechanical_3d_animation_panel_orchestrates_app_like_runtime() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    def _intro(_st) -> None:
        calls.append(("intro", None))

    def _control_panel(_st, **kwargs):
        calls.append(("control_panel", kwargs["path_checkbox_label"]))
        return {"raw": True}

    def _normalize(values):
        calls.append(("normalize", values))
        return {"base_m": 2.8, "track_m": 1.6, "wheel_w": 0.22, "path_payload": {"x": [0.0]}}

    def _prepare_runtime(_st, **kwargs):
        calls.append(("prepare_runtime", kwargs["extra_geo"]))
        return {"status": "component", "mech3d_comp": object(), "component_payload": {"payload": 1}}

    def _render_component(_st, runtime, **kwargs):
        calls.append(("render_component", kwargs.get("ring_visual")))
        return "component"

    result = helpers.render_mechanical_3d_animation_panel(
        fake_st,
        session_state={},
        cache_key="cache-app",
        dataset_id="dataset-app",
        time=[0.0, 1.0],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        phi=[0.0, 0.1],
        theta=[0.0, 0.2],
        df_main=pd.DataFrame(),
        base_override={},
        use_component_anim=True,
        get_component_fn=lambda: object(),
        mech_fallback_module=None,
        log_cb=lambda *args, **kwargs: None,
        path_checkbox_label="app label",
        path_demo_options=["Статика (без движения)"],
        path_demo_info_text="demo info",
        path_non_demo_caption="static caption",
        base_default=2.8,
        track_default=1.6,
        camera_follow_default=True,
        road_mesh_step_default=6,
        intro_fn=_intro,
        control_panel_fn=_control_panel,
        normalize_values_fn=_normalize,
        prepare_runtime_fn=_prepare_runtime,
        render_component_fn=_render_component,
    )

    assert result["ring_visual"] is None
    assert result["render_status"] == "component"
    assert result["mech3d_callbacks"] == {}
    assert calls == [
        ("intro", None),
        ("control_panel", "app label"),
        ("normalize", {"raw": True}),
        ("prepare_runtime", None),
        ("render_component", None),
    ]


def test_render_mechanical_3d_animation_panel_orchestrates_heavy_runtime_and_ring_path(tmp_path: Path) -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    def _control_panel(_st, **kwargs):
        calls.append(("control_panel", kwargs["model_path_available"]))
        return {"raw": True}

    def _normalize(values):
        calls.append(("normalize", values))
        return {"base_m": 1.7, "track_m": 1.2, "wheel_w": 0.3, "path_payload": {"x": [0.0]}}

    def _prepare_ring(**kwargs):
        calls.append(("prepare_ring", kwargs["test_pick"]))
        return ({"ring": True}, {"x": [1.0], "ring_mode": True})

    def _build_callbacks(_st, **kwargs):
        calls.append(("build_callbacks", kwargs["base_dir"]))
        return {
            "on_component_missing": "missing",
            "on_component_disabled": "disabled",
            "on_fallback_missing": "fallback",
            "on_runtime_error": "runtime",
        }

    def _prepare_runtime(_st, **kwargs):
        calls.append(("prepare_runtime", kwargs["extra_geo"]))
        assert kwargs["mech3d_values"]["path_payload"] == {"x": [1.0], "ring_mode": True}
        assert kwargs["on_component_missing"] == "missing"
        assert kwargs["on_component_disabled"] == "disabled"
        assert kwargs["on_fallback_missing"] == "fallback"
        return {"status": "component", "mech3d_comp": object(), "component_payload": {"payload": 2}}

    def _render_component(_st, runtime, **kwargs):
        calls.append(("render_component", (kwargs.get("ring_visual"), kwargs.get("on_runtime_error"))))
        return "component"

    result = helpers.render_mechanical_3d_animation_panel(
        fake_st,
        session_state={"anim_latest_npz": str(tmp_path / "anim.npz")},
        cache_key="cache-heavy",
        dataset_id="dataset-heavy",
        time=[0.0, 1.0],
        body={"body": 1},
        wheel={"wheel": 2},
        road={"road": 3},
        phi=[0.0, 0.1],
        theta=[0.0, 0.2],
        df_main=pd.DataFrame({"скорость_vx_м_с": [1.0, 2.0]}),
        base_override={},
        use_component_anim=True,
        get_component_fn=lambda: object(),
        mech_fallback_module=None,
        log_cb=lambda *args, **kwargs: None,
        path_checkbox_label="heavy label",
        path_demo_options=["По vx/yaw из модели"],
        path_demo_info_text="demo info",
        path_non_demo_caption="static caption",
        base_default=1.5,
        track_default=1.0,
        camera_follow_default=False,
        road_mesh_step_default=2,
        get_float_param_fn=lambda *args, **kwargs: 1.0,
        model_path_available=True,
        model_path_caption="model caption",
        model_speed_values=[1.0, 2.0],
        component_last_error_fn=lambda name: None,
        proc_metrics_fn=lambda: {"rss_mb": 1.0},
        safe_image_fn=lambda path, *, caption: None,
        base_dir=tmp_path,
        ring_visual_tests_map={"test-heavy": {"cfg": True}},
        ring_visual_test_pick="test-heavy",
        ring_visual_pick=tmp_path / "pick.npz",
        ring_visual_workspace_exports_dir=tmp_path,
        ring_visual_latest_export_paths_fn=lambda workspace_exports_dir, ensure_exists=False: (tmp_path / "latest.npz", None),
        ring_visual_base_dir=tmp_path,
        control_panel_fn=_control_panel,
        normalize_values_fn=_normalize,
        ring_visual_prepare_fn=_prepare_ring,
        build_runtime_callbacks_fn=_build_callbacks,
        prepare_runtime_fn=_prepare_runtime,
        render_component_fn=_render_component,
    )

    assert result["ring_visual"] == {"ring": True}
    assert result["render_status"] == "component"
    assert result["mech3d_callbacks"]["on_runtime_error"] == "runtime"
    assert calls == [
        ("control_panel", True),
        ("normalize", {"raw": True}),
        ("prepare_ring", "test-heavy"),
        ("build_callbacks", tmp_path),
        ("prepare_runtime", {"ring_visual": {"ring": True}}),
        ("render_component", ({"ring": True}, "runtime")),
    ]


def test_resolve_mechanical_3d_component_or_render_fallback_prefers_component() -> None:
    fake_st = _FakeStreamlit()
    fallback_module = _FakeFallbackModule()
    component = object()

    status, resolved = helpers.resolve_mechanical_3d_component_or_render_fallback(
        fake_st,
        use_component_anim=True,
        get_component_fn=lambda: component,
        mech_fallback_module=fallback_module,
        fallback_payload={"fallback": 1},
    )

    assert status == "component"
    assert resolved is component
    assert fallback_module.calls == []
    assert fake_st.warnings == []
    assert fake_st.infos == []
    assert fake_st.errors == []


def test_resolve_mechanical_3d_component_or_render_fallback_uses_missing_notice_and_fallback() -> None:
    fake_st = _FakeStreamlit()
    fallback_module = _FakeFallbackModule()

    status, resolved = helpers.resolve_mechanical_3d_component_or_render_fallback(
        fake_st,
        use_component_anim=True,
        get_component_fn=lambda: None,
        mech_fallback_module=fallback_module,
        fallback_payload={"fallback": 2},
    )

    assert status == "fallback"
    assert resolved is None
    assert fallback_module.calls == [{"fallback": 2}]
    assert fake_st.warnings == [helpers.MECH_3D_COMPONENT_MISSING_WARNING]


def test_resolve_mechanical_3d_component_or_render_fallback_supports_callbacks_and_missing_fallback() -> None:
    fake_st = _FakeStreamlit()
    events: list[str] = []

    status, resolved = helpers.resolve_mechanical_3d_component_or_render_fallback(
        fake_st,
        use_component_anim=False,
        get_component_fn=lambda: (_ for _ in ()).throw(RuntimeError("should not be called")),
        mech_fallback_module=None,
        fallback_payload={"fallback": 3},
        on_component_disabled=lambda: events.append("disabled"),
        on_fallback_missing=lambda: events.append("fallback-missing"),
    )

    assert status == "missing"
    assert resolved is None
    assert events == ["disabled", "fallback-missing"]
    assert fake_st.infos == []
    assert fake_st.errors == []


def test_build_mechanical_3d_path_payload_handles_static_mode() -> None:
    payload = helpers.build_mechanical_3d_path_payload(
        session_state={},
        df_main=pd.DataFrame(),
        cache_key="cache-3d",
        time_s=[0.0, 1.0],
        path_mode=helpers.MECH_3D_STATIC_MODE,
        v0=12.0,
        slalom_amp=1.5,
        slalom_period=4.0,
        yaw_smooth=0.15,
        lateral_scale=1.0,
        steer_gain=1.0,
        steer_max_deg=35.0,
        base_m=2.8,
    )

    assert payload == {
        "x": [0.0, 0.0],
        "z": [0.0, 0.0],
        "yaw": [0.0, 0.0],
        "s": [0.0, 0.0],
        "v": [0.0, 0.0],
        "steer": [0.0, 0.0],
    }


def test_build_mechanical_3d_path_payload_uses_model_vx_yaw_series_when_requested() -> None:
    payload = helpers.build_mechanical_3d_path_payload(
        session_state={},
        df_main=pd.DataFrame(
            {
                "скорость_vx_м_с": [2.0, 2.0],
                "yaw_рад": [0.0, math.pi / 2.0],
            }
        ),
        cache_key="cache-3d",
        time_s=[0.0, 1.0],
        path_mode=helpers.MECH_3D_MODEL_PATH_MODE,
        v0=12.0,
        slalom_amp=1.5,
        slalom_period=4.0,
        yaw_smooth=0.0,
        lateral_scale=1.0,
        steer_gain=1.0,
        steer_max_deg=35.0,
        base_m=2.8,
    )

    assert payload["yaw"] == [0.0, math.pi / 2.0]
    assert abs(payload["x"][0]) < 1e-9
    assert abs(payload["x"][1]) < 1e-9
    assert abs(payload["z"][0]) < 1e-9
    assert abs(payload["z"][1] - 2.0) < 1e-9
    assert payload["v"] == [2.0, 2.0]


def test_build_mechanical_3d_path_payload_integrates_ax_ay_fallback_mode() -> None:
    payload = helpers.build_mechanical_3d_path_payload(
        session_state={},
        df_main=pd.DataFrame(
            {
                "ускорение_продольное_ax_м_с2": [0.0, 1.0, 1.0],
                "ускорение_поперечное_ay_м_с2": [0.0, 0.0, 0.0],
            }
        ),
        cache_key="cache-3d",
        time_s=[0.0, 1.0, 2.0],
        path_mode="По ax/ay из модели",
        v0=2.0,
        slalom_amp=1.5,
        slalom_period=4.0,
        yaw_smooth=0.0,
        lateral_scale=1.0,
        steer_gain=1.0,
        steer_max_deg=35.0,
        base_m=2.8,
    )

    assert payload["x"][0] == 0.0
    assert payload["x"][1] > payload["x"][0]
    assert payload["x"][2] > payload["x"][1]
    assert payload["v"][0] == 2.0
    assert payload["v"][2] > payload["v"][1]
    assert all(abs(value) < 1e-9 for value in payload["z"])


def test_render_mechanical_scheme_asset_expander_delegates_to_shared_assets(tmp_path: Path) -> None:
    fake_st = _FakeStreamlit()
    safe_images: list[str] = []
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "mech_scheme.png").write_bytes(b"png")
    (assets_dir / "mech_scheme.svg").write_text("<svg/>", encoding="utf-8")

    helpers.render_mechanical_scheme_asset_expander(
        fake_st,
        base_dir=tmp_path,
        safe_image_fn=lambda path: safe_images.append(path),
    )

    assert fake_st.expanders == [("Показать исходную механическую схему (SVG/PNG)", False)]
    assert safe_images == [str(assets_dir / "mech_scheme.png")]
    assert fake_st.downloads == [
        {
            "label": "Скачать mech_scheme.svg",
            "data": b"<svg/>",
            "file_name": "mech_scheme.svg",
            "mime": "image/svg+xml",
        }
    ]


def test_entrypoints_use_shared_mechanical_animation_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_mech_animation_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_mech_animation_helpers import (" in heavy_text
    assert '"render_mechanics_panel_fn": render_mechanical_animation_results_panel' in app_text
    assert '"render_mechanics_panel_fn": render_mechanical_animation_results_panel' in heavy_text
    assert "prepare_mechanical_animation_prelude(" not in app_text
    assert "prepare_mechanical_animation_prelude(" not in heavy_text
    assert "prepare_mechanical_animation_runtime_inputs(" not in app_text
    assert "prepare_mechanical_animation_runtime_inputs(" not in heavy_text
    assert "render_mechanical_animation_section(" not in app_text
    assert "render_mechanical_animation_section(" not in heavy_text
    assert "prepare_mechanical_animation_body_profiles(" not in app_text
    assert "prepare_mechanical_animation_body_profiles(" not in heavy_text
    assert "prepare_mechanical_animation_corner_series(" not in app_text
    assert "prepare_mechanical_animation_corner_series(" not in heavy_text
    assert "resolve_mechanical_road_profile(" not in app_text
    assert "resolve_mechanical_road_profile(" not in heavy_text
    assert "render_mechanical_animation_intro(" not in app_text
    assert "render_mechanical_animation_intro(" not in heavy_text
    assert "render_mechanical_scheme_asset_expander(" not in app_text
    assert "render_mechanical_scheme_asset_expander(" not in heavy_text
    assert "render_mechanical_2d_animation_panel(" not in app_text
    assert "render_mechanical_2d_animation_panel(" not in heavy_text
    assert "render_mechanical_3d_animation_panel(" not in app_text
    assert "render_mechanical_3d_animation_panel(" not in heavy_text
    assert "render_mechanical_animation_backend_selector(" not in app_text
    assert "render_mechanical_animation_backend_selector(" not in heavy_text
    assert "build_mechanical_2d_component_payload(" not in app_text
    assert "build_mechanical_2d_component_payload(" not in heavy_text
    assert "build_mechanical_2d_fallback_payload(" not in app_text
    assert "build_mechanical_2d_fallback_payload(" not in heavy_text
    assert "render_mechanical_2d_component_or_fallback(" not in app_text
    assert "render_mechanical_2d_component_or_fallback(" not in heavy_text
    assert "build_mechanical_3d_path_payload(" not in app_text
    assert "build_mechanical_3d_path_payload(" not in heavy_text
    assert 'st.radio(\n                                "Клик по механике"' not in app_text
    assert 'st.radio(\n                            "Клик по механике"' not in heavy_text
    assert 'with st.expander("Показать исходную механическую схему (SVG/PNG)", expanded=False):' not in app_text
    assert 'with st.expander("Показать исходную механическую схему (SVG/PNG)", expanded=False):' not in heavy_text
    assert 'st.warning("Нет df_main для анимации механики.")' not in app_text
    assert 'st.warning("Нет df_main для анимации механики.")' not in heavy_text
    assert "z_body = (" not in app_text
    assert "z_body = (" not in heavy_text
    assert "body = {corners[i]: z_body[:, i].tolist() for i in range(4)}" not in app_text
    assert "body = {corners[i]: z_body[:, i].tolist() for i in range(4)}" not in heavy_text
    assert "wheel: Dict[str, List[float]] = {}" not in app_text
    assert "wheel: Dict[str, List[float]] = {}" not in heavy_text
    assert 'key="mech2d_pick_event"' not in app_text
    assert 'key="mech2d_pick_event"' not in heavy_text
    assert 'title="Механика (2D схема: крен/тангаж)"' not in app_text
    assert 'title="Механика (2D схема: крен/тангаж)"' not in heavy_text
    assert 'wheelbase_m=float(wheelbase)' not in app_text
    assert 'wheelbase_m=float(wheelbase)' not in heavy_text
    assert "get_mech_anim_component() if use_component_anim else None" not in app_text
    assert "get_mech_anim_component() if use_component_anim else None" not in heavy_text
    assert "def _on_mech_anim_runtime_error" not in heavy_text
    assert "def _on_mech_anim_missing" not in heavy_text
    assert "def _on_mech_anim_disabled" not in heavy_text
    assert "def _on_mech_fallback_missing" not in heavy_text
    assert "render_mechanical_static_scheme(" not in app_text
    assert "render_mechanical_static_scheme(" not in heavy_text
    assert '"3D‑wireframe «машинка»' not in app_text
    assert '"3D-wireframe «машинка»' not in heavy_text
    assert '"Слалом: амплитуда (м)"' not in app_text
    assert '"Слалом: амплитуда (м)"' not in heavy_text
    assert 'key=f"mech3d_demo_paths_{cache_key}"' not in app_text
    assert 'key=f"mech3d_demo_paths_{cache_key}"' not in heavy_text
    assert 'key=f"mech3d_path_mode_{cache_key}"' not in app_text
    assert 'key=f"mech3d_path_mode_{cache_key}"' not in heavy_text
    assert 'key=f"mech3d_wheel_r_{cache_key}"' not in app_text
    assert 'key=f"mech3d_wheel_r_{cache_key}"' not in heavy_text
    assert 'key=f"mech3d_road_mode_{cache_key}"' not in app_text
    assert 'key=f"mech3d_road_mode_{cache_key}"' not in heavy_text
    assert 'key=f"mech3d_reset_view_{cache_key}"' not in app_text
    assert 'key=f"mech3d_reset_view_{cache_key}"' not in heavy_text
    assert 'key=f"mech3d_body_L_{cache_key}"' not in app_text
    assert 'key=f"mech3d_body_L_{cache_key}"' not in heavy_text
    assert 'key="mech3d_pick_event"' not in app_text
    assert 'key="mech3d_pick_event"' not in heavy_text
    assert 'base_m = float(mech3d_controls["base_m"])' not in app_text
    assert 'base_m = float(mech3d_controls["base_m"])' not in heavy_text
    assert 'track_m = float(mech3d_controls["track_m"])' not in app_text
    assert 'track_m = float(mech3d_controls["track_m"])' not in heavy_text
    assert '"body_L_m": float(body_L)' not in app_text
    assert '"body_L_m": float(body_L)' not in heavy_text
    assert "colA, colB, colC = st.columns(3)" not in app_text
    assert "colA, colB, colC = st.columns(3)" not in heavy_text
    assert "get_mech_car3d_component() if use_component_anim else None" not in app_text
    assert "get_mech_car3d_component() if use_component_anim else None" not in heavy_text
    assert "mech_fb.render_mech3d_fallback(" not in app_text
    assert "mech_fb.render_mech3d_fallback(" not in heavy_text
    assert "render_mechanical_3d_intro(" not in app_text
    assert "render_mechanical_3d_intro(" not in heavy_text
    assert "render_mechanical_3d_control_panel(" not in app_text
    assert "render_mechanical_3d_control_panel(" not in heavy_text
    assert "normalize_mechanical_3d_control_values(" not in app_text
    assert "normalize_mechanical_3d_control_values(" not in heavy_text
    assert "build_mechanical_3d_fallback_payload(" not in app_text
    assert "build_mechanical_3d_fallback_payload(" not in heavy_text
    assert "build_mechanical_3d_geo_payload(" not in app_text
    assert "build_mechanical_3d_geo_payload(" not in heavy_text
    assert "build_mechanical_3d_component_payload(" not in app_text
    assert "build_mechanical_3d_component_payload(" not in heavy_text
    assert "render_mechanical_3d_body_controls(" not in app_text
    assert "render_mechanical_3d_body_controls(" not in heavy_text
    assert "resolve_mechanical_3d_component_or_render_fallback(" not in app_text
    assert "resolve_mechanical_3d_component_or_render_fallback(" not in heavy_text
    assert "prepare_mechanical_3d_component_runtime(" not in app_text
    assert "prepare_mechanical_3d_component_runtime(" not in heavy_text
    assert "render_mechanical_3d_component_from_runtime(" not in app_text
    assert "render_mechanical_3d_component_from_runtime(" not in heavy_text
    assert "build_mechanical_3d_runtime_callbacks(" not in heavy_text
    assert "prepare_mechanical_3d_ring_visual(" not in heavy_text
    assert 'if mech3d_runtime["mech3d_comp"] is not None:' not in app_text
    assert 'if mech3d_runtime["mech3d_comp"] is not None:' not in heavy_text
    assert 'mech3d_runtime["mech3d_comp"](**mech3d_runtime["component_payload"])' not in app_text
    assert 'mech3d_runtime["mech3d_comp"](**mech3d_runtime["component_payload"])' not in heavy_text
    assert "render_mechanical_3d_ring_visual_notice(" not in heavy_text
    assert "path_payload = {" not in app_text
    assert "path_payload = {" not in heavy_text
    assert "np.cumsum(vabs * dt)" not in app_text
    assert "np.cumsum(vabs * dt)" not in heavy_text
    assert "load_ring_spec_from_test_cfg(" not in heavy_text
    assert "load_ring_spec_from_npz(" not in heavy_text
    assert "build_ring_visual_payload_from_spec(" not in heavy_text
    assert "build_nominal_ring_progress_from_spec(" not in heavy_text
    assert "embed_path_payload_on_ring(" not in heavy_text
    assert "def _on_mech3d_component_missing()" not in heavy_text
    assert "def _on_mech3d_component_disabled()" not in heavy_text
    assert "def _on_mech3d_fallback_missing()" not in heavy_text
    assert "def _on_mech3d_runtime_error(" not in heavy_text
    assert "st.download_button(" in helper_text
    assert '"Скачать mech_scheme.svg"' in helper_text
    assert "MECH_2D_COMPONENT_TITLE" in helper_text
    assert "MECH_3D_INTRO_CAPTION" in helper_text
    assert "MECH_3D_PATH_MODE_LABEL" in helper_text
    assert "def prepare_mechanical_animation_body_profiles(" in helper_text
    assert "def prepare_mechanical_animation_corner_series(" in helper_text
    assert "def prepare_mechanical_animation_prelude(" in helper_text
    assert "def prepare_mechanical_animation_runtime_inputs(" in helper_text
    assert "def render_mechanical_animation_results_panel(" in helper_text
    assert "def render_mechanical_animation_section(" in helper_text
    assert "def build_mechanical_2d_component_payload(" in helper_text
    assert "def build_mechanical_2d_fallback_payload(" in helper_text
    assert "def build_mechanical_2d_runtime_callbacks(" in helper_text
    assert "def render_mechanical_2d_component_or_fallback(" in helper_text
    assert "def render_mechanical_2d_animation_panel(" in helper_text
    assert "def render_mechanical_3d_intro(" in helper_text
    assert "def render_mechanical_3d_maneuver_controls(" in helper_text
    assert "def render_mechanical_3d_path_controls(" in helper_text
    assert "def render_mechanical_3d_visual_controls(" in helper_text
    assert "def render_mechanical_3d_control_panel(" in helper_text
    assert "def normalize_mechanical_3d_control_values(" in helper_text
    assert "def render_mechanical_3d_body_controls(" in helper_text
    assert "def build_mechanical_3d_fallback_payload(" in helper_text
    assert "def build_mechanical_3d_geo_payload(" in helper_text
    assert "def build_mechanical_3d_component_payload(" in helper_text
    assert "def resolve_mechanical_3d_component_or_render_fallback(" in helper_text
    assert "def prepare_mechanical_3d_component_runtime(" in helper_text
    assert "def build_mechanical_3d_runtime_callbacks(" in helper_text
    assert "def prepare_mechanical_3d_ring_visual(" in helper_text
    assert "def render_mechanical_3d_ring_visual_notice(" in helper_text
    assert "def render_mechanical_3d_component_from_runtime(" in helper_text
    assert "def render_mechanical_3d_animation_panel(" in helper_text
    assert "def build_mechanical_3d_path_payload(" in helper_text
    assert "def render_mechanical_static_scheme(" in helper_text
