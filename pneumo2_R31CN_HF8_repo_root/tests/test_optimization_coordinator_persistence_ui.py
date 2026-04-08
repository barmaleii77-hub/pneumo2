from __future__ import annotations

from pneumo_solver_ui.optimization_coordinator_persistence_ui import (
    render_coordinator_persistence_controls,
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

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def selectbox(self, label: str, **kwargs):
        self.calls.append(("selectbox", label))
        options = kwargs.get("options") or []
        index = int(kwargs.get("index", 0) or 0)
        return options[index] if options else None

    def text_area(self, label: str, **kwargs):
        self.calls.append(("text_area", label))
        return kwargs.get("value")

    def number_input(self, label: str, **kwargs):
        self.calls.append(("number_input", label))
        return kwargs.get("value")

    def text_input(self, label: str, **kwargs):
        self.calls.append(("text_input", label))
        return kwargs.get("value")

    def checkbox(self, label: str, **kwargs):
        self.calls.append(("checkbox", label))
        return kwargs.get("value")


def test_coordinator_persistence_ui_renders_expected_controls() -> None:
    st = _FakeStreamlit()

    render_coordinator_persistence_controls(st)

    assert ("expander", ("Coordinator advanced / persistence", False)) in st.calls
    assert ("selectbox", "Ray runtime_env mode") in st.calls
    assert ("text_area", "Ray runtime_env JSON merge (optional)") in st.calls
    assert ("text_area", "Ray runtime exclude (по одному паттерну в строке)") in st.calls
    assert ("number_input", "Ray evaluators") in st.calls
    assert ("number_input", "Ray proposers") in st.calls
    assert ("number_input", "Буфер кандидатов proposer_buffer") in st.calls
    assert ("text_input", "ExperimentDB path / DSN") in st.calls
    assert ("selectbox", "DB engine") in st.calls
    assert ("checkbox", "Resume from existing run") in st.calls
    assert ("text_input", "Explicit run_id (optional)") in st.calls
    assert ("checkbox", "Писать hypervolume log") in st.calls
    assert ("number_input", "export-every") in st.calls
