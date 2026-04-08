from __future__ import annotations

from pneumo_solver_ui.optimization_page_shell_ui import (
    render_optimization_help_expander,
    render_optimization_navigation_row,
    render_optimization_page_header,
    render_optimization_readonly_expanders,
)


class _FakeExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, buttons: dict[str, bool] | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self._buttons = dict(buttons or {})

    def title(self, text: str) -> None:
        self.calls.append(("title", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def button(self, label: str, **kwargs) -> bool:
        self.calls.append(("button", label))
        return bool(self._buttons.get(label, False))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def expander(self, label: str, expanded: bool = False):
        self.calls.append(("expander", (label, expanded)))
        return _FakeExpander()


def test_page_shell_ui_renders_header_navigation_and_help() -> None:
    st = _FakeStreamlit(buttons={"📊 Результаты оптимизации": True})
    events: list[str] = []

    render_optimization_page_header(st, title="Оптимизация", caption="caption")
    render_optimization_navigation_row(
        st,
        home_label="🏠 Главная: входные данные и suite",
        home_key="home",
        home_action=lambda: events.append("home"),
        home_fallback="home fallback",
        results_label="📊 Результаты оптимизации",
        results_key="results",
        results_action=lambda: events.append("results"),
        results_fallback="results fallback",
        db_label="🗄️ База оптимизаций",
        db_key="db",
        db_action=lambda: events.append("db"),
        db_fallback="db fallback",
    )
    render_optimization_help_expander(st, label="Справка: что именно запускается", markdown_text="help", expanded=False)

    assert ("title", "Оптимизация") in st.calls
    assert ("caption", "caption") in st.calls
    assert ("button", "📊 Результаты оптимизации") in st.calls
    assert events == ["results"]
    assert ("expander", ("Справка: что именно запускается", False)) in st.calls
    assert ("markdown", "help") in st.calls


def test_page_shell_ui_renders_readonly_expanders() -> None:
    st = _FakeStreamlit()
    events: list[str] = []

    render_optimization_readonly_expanders(
        st,
        last_label="Последняя оптимизация",
        render_last=lambda: events.append("last"),
        physical_label="Физический смысл путей запуска",
        render_physical=lambda: events.append("physical"),
        history_label="Последовательные запуски в текущем workspace",
        render_history=lambda: events.append("history"),
    )

    assert ("expander", ("Последняя оптимизация", True)) in st.calls
    assert ("expander", ("Физический смысл путей запуска", True)) in st.calls
    assert ("expander", ("Последовательные запуски в текущем workspace", True)) in st.calls
    assert events == ["last", "physical", "history"]
