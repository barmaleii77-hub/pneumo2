from __future__ import annotations

from pneumo_solver_ui.optimization_page_readonly_ui import (
    current_objective_keys,
    render_last_optimization_overview_block,
    render_physical_workflow_block,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, buttons: dict[str, bool] | None = None) -> None:
        self.session_state: dict[str, object] = {}
        self.calls: list[tuple[str, object]] = []
        self._buttons = dict(buttons or {})

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]

    def button(self, label: str, **kwargs) -> bool:
        self.calls.append(("button", label))
        return bool(self._buttons.get(label, False))

    def metric(self, label: str, value) -> None:
        self.calls.append(("metric", (label, value)))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def success(self, text: str) -> None:
        self.calls.append(("success", text))

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def code(self, text: str) -> None:
        self.calls.append(("code", text))

    def switch_page(self, page: str) -> None:
        self.calls.append(("switch_page", page))


def test_page_readonly_current_objective_keys_parses_text() -> None:
    keys = current_objective_keys(
        {"opt_objectives": "comfort, roll\nenergy"},
        default_objectives=("comfort", "roll", "energy"),
        objectives_text_fn=lambda values: "\n".join(values),
    )
    assert keys == ["comfort", "roll", "energy"]


def test_page_readonly_last_overview_renders_actions() -> None:
    st = _FakeStreamlit(buttons={"Открыть результаты": True, "Открыть папку": True})

    render_last_optimization_overview_block(
        st,
        snapshot={"run_dir": "C:/tmp/run-1"},
        results_page="pages/20_DistributedOptimization.py",
        render_summary_fn=lambda *_args, **_kwargs: True,
    )

    assert ("button", "Открыть результаты") in st.calls
    assert ("switch_page", "pages/20_DistributedOptimization.py") in st.calls
    assert ("button", "Открыть папку") in st.calls
    assert ("code", "C:/tmp/run-1") in st.calls


def test_page_readonly_physical_workflow_can_restore_default_objectives() -> None:
    st = _FakeStreamlit(buttons={"Вернуть канонический набор целей (comfort / roll / energy)": True})
    st.session_state["opt_objectives"] = "custom_metric"
    rerun_events: list[str] = []

    render_physical_workflow_block(
        st,
        session_state=st.session_state,
        default_objectives=("comfort", "roll", "energy"),
        penalty_key_default="penalty_total",
        objectives_text_fn=lambda values: "\n".join(values),
        rerun_fn=lambda _st: rerun_events.append("rerun"),
    )

    assert ("metric", ("Быстрый путь по физике", "StageRunner")) in st.calls
    assert ("metric", ("Длинный перебор", "Distributed")) in st.calls
    assert st.session_state["opt_objectives"] == "comfort\nroll\nenergy"
    assert rerun_events == ["rerun"]
