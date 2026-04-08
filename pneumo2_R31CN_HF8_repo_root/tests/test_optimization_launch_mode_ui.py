from __future__ import annotations

from pneumo_solver_ui.optimization_launch_mode_ui import (
    render_optimization_launch_mode_block,
)


class _FakeExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, selected_mode: str) -> None:
        self.calls: list[tuple[str, object]] = []
        self._selected_mode = selected_mode

    def expander(self, label: str, expanded: bool = False):
        self.calls.append(("expander", (label, expanded)))
        return _FakeExpander()

    def radio(self, label: str, *, options, index: int, horizontal: bool, help: str):
        self.calls.append(("radio", (label, tuple(options), index, horizontal, help)))
        return self._selected_mode

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def success(self, text: str) -> None:
        self.calls.append(("success", text))


def test_launch_mode_ui_renders_stage_path_message() -> None:
    st = _FakeStreamlit(selected_mode="Режим по стадиям (StageRunner) — рекомендуется")

    out = render_optimization_launch_mode_block(
        st,
        expander_label="Режим запуска и стадийность",
        mode_stage_label="Режим по стадиям (StageRunner) — рекомендуется",
        mode_coord_label="Distributed coordinator (Dask / Ray / BoTorch)",
        current_use_staged=True,
        radio_label="Активный путь запуска",
        radio_help="help",
        single_path_message="Сейчас активен только один путь запуска.",
        staged_message="Активен StageRunner",
        coordinator_message="Активен distributed coordinator path",
    )

    assert out is True
    assert ("expander", ("Режим запуска и стадийность", True)) in st.calls
    assert any(kind == "radio" and value[0] == "Активный путь запуска" for kind, value in st.calls)
    assert ("info", "Сейчас активен только один путь запуска.") in st.calls
    assert ("success", "Активен StageRunner") in st.calls


def test_launch_mode_ui_renders_coordinator_message() -> None:
    st = _FakeStreamlit(selected_mode="Distributed coordinator (Dask / Ray / BoTorch)")

    out = render_optimization_launch_mode_block(
        st,
        expander_label="Режим запуска и стадийность",
        mode_stage_label="Режим по стадиям (StageRunner) — рекомендуется",
        mode_coord_label="Distributed coordinator (Dask / Ray / BoTorch)",
        current_use_staged=True,
        radio_label="Активный путь запуска",
        radio_help="help",
        single_path_message="Сейчас активен только один путь запуска.",
        staged_message="Активен StageRunner",
        coordinator_message="Активен distributed coordinator path",
    )

    assert out is False
    assert ("info", "Активен distributed coordinator path") in st.calls
