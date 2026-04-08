from __future__ import annotations

from pneumo_solver_ui.optimization_coordinator_cluster_ui import (
    render_coordinator_cluster_controls,
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
    def __init__(self, *, select_values: dict[str, object] | None = None, radio_values: dict[str, object] | None = None) -> None:
        self.session_state = {}
        self.calls: list[tuple[str, object]] = []
        self._select_values = dict(select_values or {})
        self._radio_values = dict(radio_values or {})

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

    def selectbox(self, label: str, **kwargs):
        self.calls.append(("selectbox", label))
        if label in self._select_values:
            return self._select_values[label]
        options = kwargs.get("options") or []
        index = int(kwargs.get("index", 0) or 0)
        return options[index] if options else None

    def radio(self, label: str, **kwargs):
        self.calls.append(("radio", label))
        if label in self._radio_values:
            return self._radio_values[label]
        options = kwargs.get("options") or []
        index = int(kwargs.get("index", 0) or 0)
        return options[index] if options else None

    def text_input(self, label: str, **kwargs):
        self.calls.append(("text_input", label))
        return kwargs.get("value")

    def number_input(self, label: str, **kwargs):
        self.calls.append(("number_input", label))
        return kwargs.get("value")

    def checkbox(self, label: str, **kwargs):
        self.calls.append(("checkbox", label))
        return kwargs.get("value")


def test_coordinator_cluster_ui_renders_dask_local_controls() -> None:
    st = _FakeStreamlit(
        select_values={"Бэкенд распределённых вычислений": "Dask"},
        radio_values={"Режим Dask": "Локальный кластер (создать автоматически)"},
    )

    render_coordinator_cluster_controls(st)

    assert ("expander", ("Параллелизм и кластер (Dask / Ray)", True)) in st.calls
    assert ("selectbox", "Бэкенд распределённых вычислений") in st.calls
    assert ("radio", "Режим Dask") in st.calls
    assert ("number_input", "Воркеры") in st.calls
    assert ("number_input", "Потоки/воркер") in st.calls
    assert ("text_input", "Лимит памяти/воркер") in st.calls
    assert ("text_input", "Dashboard address") in st.calls


def test_coordinator_cluster_ui_renders_ray_remote_controls() -> None:
    st = _FakeStreamlit(
        select_values={"Бэкенд распределённых вычислений": "Ray"},
        radio_values={"Режим Ray": "Подключиться к кластеру"},
    )

    render_coordinator_cluster_controls(st)

    assert ("radio", "Режим Ray") in st.calls
    assert ("text_input", "Адрес Ray (например: 127.0.0.1:6379 или 'auto')") in st.calls
