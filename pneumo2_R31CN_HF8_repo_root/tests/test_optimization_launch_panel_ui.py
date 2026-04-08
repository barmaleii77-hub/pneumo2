from __future__ import annotations

from pneumo_solver_ui.optimization_launch_panel_ui import (
    render_optimization_launch_panel,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, launch_clicked: bool = False) -> None:
        self.calls: list[tuple[str, object]] = []
        self._launch_clicked = bool(launch_clicked)

    def subheader(self, text: str) -> None:
        self.calls.append(("subheader", text))

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def button(self, label: str, **kwargs) -> bool:
        self.calls.append(("button", label))
        return self._launch_clicked if label.startswith("Запустить ") else False

    def download_button(self, label: str, *, data, file_name: str, help: str) -> None:
        self.calls.append(("download_button", (label, data, file_name, help)))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]


def test_launch_panel_ui_renders_intro_download_and_stage_note() -> None:
    st = _FakeStreamlit(launch_clicked=True)

    clicked = render_optimization_launch_panel(
        st,
        launch_button_label="Запустить StageRunner",
        launch_intro_markdown="intro",
        workflow_caption="workflow",
        cmd_preview_text="python worker.py\n",
        is_staged=True,
    )

    assert clicked is True
    assert ("subheader", "Новый запуск") in st.calls
    assert ("markdown", "intro") in st.calls
    assert ("caption", "workflow") in st.calls
    assert ("button", "Запустить StageRunner") in st.calls
    assert any(
        kind == "download_button"
        and value[0] == "Скачать шаблон команды"
        and value[1] == "python worker.py\n"
        and value[2] == "dist_opt_command.txt"
        for kind, value in st.calls
    )
    assert any(kind == "caption" and "StageRunner запускается через console" in text for kind, text in st.calls)


def test_launch_panel_ui_renders_coordinator_note() -> None:
    st = _FakeStreamlit()

    clicked = render_optimization_launch_panel(
        st,
        launch_button_label="Запустить distributed coordinator",
        launch_intro_markdown="intro",
        workflow_caption="workflow",
        cmd_preview_text="python coord.py\n",
        is_staged=False,
    )

    assert clicked is False
    assert any(kind == "caption" and "coordinator создаёт локальный кластер автоматически" in text for kind, text in st.calls)
