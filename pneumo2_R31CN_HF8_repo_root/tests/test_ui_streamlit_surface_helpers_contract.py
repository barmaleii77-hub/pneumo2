from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_streamlit_surface_helpers import (
    safe_dataframe,
    safe_image,
    safe_plotly_chart,
    safe_previewable_dataframe,
    ui_popover,
)


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.caption_calls: list[str] = []
        self.dataframe_calls: list[tuple[object, dict]] = []
        self.expander_calls: list[tuple[str, bool]] = []
        self.info_calls: list[str] = []
        self.json_calls: list[object] = []
        self.plotly_calls: list[tuple[object, dict]] = []
        self.image_calls: list[tuple[object, dict]] = []
        self._dataframe_failures: list[type[Exception]] = []
        self._plotly_failures: list[type[Exception]] = []
        self._image_failures: list[type[Exception]] = []
        self._popover_available = False

    def queue_dataframe_failures(self, *failures: type[Exception]) -> None:
        self._dataframe_failures.extend(failures)

    def queue_plotly_failures(self, *failures: type[Exception]) -> None:
        self._plotly_failures.extend(failures)

    def queue_image_failures(self, *failures: type[Exception]) -> None:
        self._image_failures.extend(failures)

    def dataframe(self, df, **kwargs):
        self.dataframe_calls.append((df, dict(kwargs)))
        if self._dataframe_failures:
            raise self._dataframe_failures.pop(0)()
        return {"df": df, "kwargs": kwargs}

    def plotly_chart(self, fig, **kwargs):
        self.plotly_calls.append((fig, dict(kwargs)))
        if self._plotly_failures:
            raise self._plotly_failures.pop(0)()
        return {"fig": fig, "kwargs": kwargs}

    def image(self, img, **kwargs):
        self.image_calls.append((img, dict(kwargs)))
        if self._image_failures:
            raise self._image_failures.pop(0)()
        return {"img": img, "kwargs": kwargs}

    def write(self, value):
        return {"write": value}

    def caption(self, text):
        self.caption_calls.append(str(text))

    def info(self, text):
        self.info_calls.append(str(text))

    def json(self, value):
        self.json_calls.append(value)

    def expander(self, label, expanded=False):
        self.expander_calls.append((str(label), bool(expanded)))
        return _NullContext()

    def __getattr__(self, name):
        if name == "popover" and self._popover_available:
            def _popover(label):
                self.expander_calls.append((f"popover:{label}", True))
                return _NullContext()
            return _popover
        raise AttributeError(name)

    def enable_popover(self):
        self._popover_available = True

    def slider(self, label, min_value, max_value, value, *, step=1, key=None):
        return value

    def number_input(self, label, *, min_value, max_value, value, step=1, key=None):
        return value


def test_safe_dataframe_retries_new_then_legacy_api_then_write_fallback() -> None:
    fake = _FakeStreamlit()
    fake.queue_dataframe_failures(TypeError, TypeError, TypeError, TypeError)

    out = safe_dataframe(fake, "frame", height=111, hide_index=True, fallback_write=True)

    assert out == {"write": "frame"}
    assert fake.dataframe_calls == [
        ("frame", {"width": "stretch", "height": 111, "hide_index": True}),
        ("frame", {"width": "stretch", "height": 111}),
        ("frame", {"use_container_width": True, "height": 111, "hide_index": True}),
        ("frame", {"use_container_width": True, "height": 111}),
    ]


def test_safe_previewable_dataframe_uses_preview_and_row_card_for_wide_frames() -> None:
    import pandas as pd

    fake = _FakeStreamlit()
    df = pd.DataFrame(
        [
            {"id": "row-1", "a": 1, "b": 2, "c": 3},
            {"id": "row-2", "a": 4, "b": 5, "c": 6},
        ]
    )

    out = safe_previewable_dataframe(fake, df, max_cols=2, key="demo")

    assert out is None
    assert list(fake.dataframe_calls[0][0].columns) == ["id", "a"]
    assert fake.expander_calls == [("Детали выбранной строки", False)]
    assert fake.json_calls == [{"id": "row-1", "a": 1, "b": 2, "c": 3}]
    assert any("Таблица широкая" in text for text in fake.caption_calls)
    assert any("Строка 0: id = row-1" in text for text in fake.caption_calls)


def test_ui_popover_prefers_native_popover_and_falls_back_to_expander() -> None:
    fake = _FakeStreamlit()
    with ui_popover(fake, "fallback", expanded=True):
        pass

    fake2 = _FakeStreamlit()
    fake2.enable_popover()
    with ui_popover(fake2, "native", expanded=False):
        pass

    assert fake.expander_calls == [("fallback", True)]
    assert fake2.expander_calls == [("popover:native", True)]


def test_safe_plotly_chart_retries_without_selection_then_legacy_container_width() -> None:
    fake = _FakeStreamlit()
    fake.queue_plotly_failures(TypeError, TypeError)

    out = safe_plotly_chart(
        fake,
        "fig",
        key="plot-key",
        on_select="rerun",
        selection_mode=("points",),
    )

    assert out["kwargs"] == {"use_container_width": True, "key": "plot-key"}
    assert fake.plotly_calls == [
        ("fig", {"width": "stretch", "key": "plot-key", "on_select": "rerun", "selection_mode": ("points",)}),
        ("fig", {"width": "stretch", "key": "plot-key"}),
        ("fig", {"use_container_width": True, "key": "plot-key"}),
    ]


def test_safe_image_supports_optional_int_width_fallback() -> None:
    fake = _FakeStreamlit()
    fake.queue_image_failures(RuntimeError, TypeError)

    out = safe_image(fake, "img.png", caption="demo", int_width_fallback=2000)

    assert out["kwargs"] == {"use_container_width": True, "caption": "demo"}
    assert fake.image_calls == [
        ("img.png", {"caption": "demo", "width": "stretch"}),
        ("img.png", {"caption": "demo", "width": 2000}),
        ("img.png", {"caption": "demo", "use_container_width": True}),
    ]


def test_runtime_sources_use_shared_streamlit_surface_helpers() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "pneumo_solver_ui" / "app.py",
        root / "pneumo_solver_ui" / "pneumo_ui_app.py",
        root / "pneumo_solver_ui" / "param_influence_ui.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "ui_streamlit_surface_helpers" in text

    app_text = (root / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_text = (root / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    param_text = (root / "pneumo_solver_ui" / "param_influence_ui.py").read_text(encoding="utf-8")

    assert "def safe_plotly_chart" not in app_text
    assert "def safe_image" not in app_text
    assert "def safe_plotly_chart" not in heavy_text
    assert "def safe_image" not in heavy_text
    assert "def safe_plotly_chart" not in param_text
    assert "def safe_dataframe" not in app_text
    assert "def safe_dataframe" not in heavy_text
    assert "def ui_popover" not in heavy_text
