from __future__ import annotations

from pneumo_solver_ui.optimization_coordinator_algorithm_ui import (
    render_coordinator_algorithm_controls,
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

    def divider(self) -> None:
        self.calls.append(("divider", None))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def selectbox(self, label: str, **kwargs):
        self.calls.append(("selectbox", label))
        options = kwargs.get("options") or []
        index = int(kwargs.get("index", 0) or 0)
        return options[index] if options else None

    def number_input(self, label: str, **kwargs):
        self.calls.append(("number_input", label))
        return kwargs.get("value")

    def text_input(self, label: str, **kwargs):
        self.calls.append(("text_input", label))
        return kwargs.get("value")

    def text_area(self, label: str, **kwargs):
        self.calls.append(("text_area", label))
        return kwargs.get("value")


def test_coordinator_algorithm_ui_renders_expected_controls() -> None:
    st = _FakeStreamlit()

    render_coordinator_algorithm_controls(st, show_staged_caption=False)

    assert ("expander", ("Алгоритм и критерии останова", True)) in st.calls
    assert any(kind == "selectbox" and value == "Метод (алгоритм) предложения кандидатов" for kind, value in st.calls)
    assert any(kind == "number_input" and value == "Бюджет (кол-во оценок целевой функции)" for kind, value in st.calls)
    assert any(kind == "text_input" and value == "Ключ штрафа/ограничений (penalty_key)" for kind, value in st.calls)
    assert any(kind == "selectbox" and value == "Режим идентификатора задачи (problem_hash)" for kind, value in st.calls)
    assert any(kind == "text_area" and value == "Целевые метрики (objective keys) — по одной в строке" for kind, value in st.calls)


def test_coordinator_algorithm_ui_can_render_staged_caption() -> None:
    st = _FakeStreamlit()

    render_coordinator_algorithm_controls(st, show_staged_caption=True)

    assert any(kind == "caption" and "Этот блок нужен для distributed coordinator path" in text for kind, text in st.calls)
