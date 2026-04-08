from __future__ import annotations

from pneumo_solver_ui.optimization_botorch_advanced_ui import (
    render_botorch_advanced_controls,
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

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def warning(self, text: str) -> None:
        self.calls.append(("warning", text))

    def success(self, text: str) -> None:
        self.calls.append(("success", text))

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def number_input(self, label: str, **kwargs):
        self.calls.append(("number_input", label))
        return kwargs.get("value")

    def checkbox(self, label: str, **kwargs):
        self.calls.append(("checkbox", label))
        return kwargs.get("value")


def test_botorch_advanced_ui_renders_expected_controls() -> None:
    st = _FakeStreamlit()

    render_botorch_advanced_controls(st, show_staged_caption=True)

    assert ("expander", ("BoTorch / qNEHVI advanced", False)) in st.calls
    assert any(kind == "caption" and "distributed coordinator" in text for kind, text in st.calls)
    assert ("number_input", "n-init (warmup before qNEHVI)") in st.calls
    assert ("number_input", "min-feasible") in st.calls
    assert ("number_input", "num_restarts") in st.calls
    assert ("number_input", "raw_samples") in st.calls
    assert ("number_input", "maxiter") in st.calls
    assert ("number_input", "ref_margin") in st.calls
    assert ("checkbox", "Normalize objectives before GP fit") in st.calls
    assert any(kind == "info" and "локального proposer path" in text for kind, text in st.calls)
