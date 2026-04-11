from __future__ import annotations

from pneumo_solver_ui.optimization_stage_runner_config_ui import (
    render_stage_runner_configuration_controls,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = {}
        self.calls: list[tuple[str, object]] = []

    def expander(self, label: str, expanded: bool = False):
        self.calls.append(("expander", (label, expanded)))
        return _FakeExpander()

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def number_input(self, label: str, **kwargs):
        self.calls.append(("number_input", label))
        return kwargs.get("value")

    def checkbox(self, label: str, **kwargs):
        self.calls.append(("checkbox", label))
        return kwargs.get("value")

    def selectbox(self, label: str, **kwargs):
        self.calls.append(("selectbox", label))
        options = kwargs.get("options") or []
        index = int(kwargs.get("index", 0) or 0)
        return options[index] if options else None


def test_stage_runner_config_ui_renders_expected_controls() -> None:
    st = _FakeStreamlit()

    render_stage_runner_configuration_controls(st, ui_jobs_default=7)

    assert ("expander", ("StageRunner: warm-start, influence и стадийный отбор", True)) in st.calls
    assert ("number_input", "Минуты на staged run") in st.calls
    assert ("number_input", "Jobs (локальный parallel worker pool)") in st.calls
    assert ("checkbox", "Авто-обновлять baseline_best.json") in st.calls
    assert ("checkbox", "Resume staged run") in st.calls
    assert ("number_input", "Seed кандидатов") in st.calls
    assert ("number_input", "Seed условий") in st.calls
    assert ("selectbox", "Warm-start режим") in st.calls
    assert ("number_input", "Surrogate samples") in st.calls
    assert ("number_input", "Surrogate top-k") in st.calls
    assert ("number_input", "Early-stop штраф (stage1)") in st.calls
    assert ("checkbox", "Adaptive epsilon для System Influence") in st.calls
    assert ("selectbox", "Политика отбора и продвижения") in st.calls
    assert any(kind == "caption" and "Профиль стадийного отбора и продвижения" in text for kind, text in st.calls)
