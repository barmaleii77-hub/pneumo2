from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_mapping_input_helpers import (
    parse_svg_mapping_text,
    parse_svg_mapping_upload,
    render_svg_mapping_input,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_input_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


class _FakeUpload:
    def __init__(self, name: str, payload: bytes) -> None:
        self.name = name
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


class _FakeStreamlit:
    def __init__(self, *, upload=None, text: str = "") -> None:
        self.upload = upload
        self.text = text
        self.errors: list[str] = []
        self.file_uploader_calls: list[tuple[str, tuple[str, ...], str | None]] = []
        self.text_area_calls: list[tuple[str, str, int | None]] = []

    def file_uploader(self, label: str, type=None, key: str | None = None):
        self.file_uploader_calls.append((label, tuple(type or ()), key))
        return self.upload

    def text_area(self, label: str, value: str = "", height: int | None = None):
        self.text_area_calls.append((label, value, height))
        return self.text

    def error(self, text: str) -> None:
        self.errors.append(text)


def test_parse_svg_mapping_upload_and_text() -> None:
    mapping, source, raw_size = parse_svg_mapping_upload(
        _FakeUpload("mapping.json", b'{"edges":{"a":[]}}')
    )
    assert mapping == {"edges": {"a": []}}
    assert source == "uploaded:mapping.json"
    assert raw_size == len(b'{"edges":{"a":[]}}')
    assert parse_svg_mapping_text('{"nodes":{"n":[1,2]}}') == {"nodes": {"n": [1, 2]}}


def test_render_svg_mapping_input_prefers_upload_and_updates_session() -> None:
    fake_st = _FakeStreamlit(upload=_FakeUpload("m.json", b'{"edges":{"a":[]}}'), text='{"bad":1}')
    session_state: dict[str, object] = {"svg_mapping_text": ""}
    events: list[tuple[str, dict[str, object]]] = []

    mapping = render_svg_mapping_input(
        fake_st,
        session_state,
        log_event_fn=lambda event_name, **kwargs: events.append((event_name, kwargs)),
    )

    assert mapping == {"edges": {"a": []}}
    assert session_state["svg_mapping_source"] == "uploaded:m.json"
    assert '"edges"' in str(session_state["svg_mapping_text"])
    assert events == [("svg_mapping_uploaded", {"name": "m.json", "bytes": len(b'{"edges":{"a":[]}}')})]
    assert fake_st.errors == []


def test_render_svg_mapping_input_parses_text_and_preserves_uploaded_source_prefix() -> None:
    fake_st = _FakeStreamlit(text='{"edges":{"b":[]}}')
    session_state: dict[str, object] = {
        "svg_mapping_text": '{"edges":{"old":[]}}',
        "svg_mapping_source": "uploaded:prev.json",
    }
    events: list[tuple[str, dict[str, object]]] = []

    mapping = render_svg_mapping_input(
        fake_st,
        session_state,
        log_event_fn=lambda event_name, **kwargs: events.append((event_name, kwargs)),
    )

    assert mapping == {"edges": {"b": []}}
    assert session_state["svg_mapping_source"] == "uploaded:prev.json"
    assert events == []


def test_render_svg_mapping_input_reports_parse_error() -> None:
    fake_st = _FakeStreamlit(text="{bad json")
    session_state: dict[str, object] = {"svg_mapping_text": ""}
    events: list[tuple[str, dict[str, object]]] = []

    mapping = render_svg_mapping_input(
        fake_st,
        session_state,
        log_event_fn=lambda event_name, **kwargs: events.append((event_name, kwargs)),
    )

    assert mapping is None
    assert len(fake_st.errors) == 1
    assert fake_st.errors[0].startswith("JSON не парсится:")
    assert events and events[0][0] == "svg_mapping_text_parse_failed"


def test_entrypoints_use_shared_svg_mapping_input_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_HELPERS_PATH.read_text(encoding="utf-8")
    tools_text = TOOLS_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert 'st.file_uploader("Загрузить mapping JSON", type=["json"], key="svg_mapping_upl")' not in app_text
    assert 'st.file_uploader("Загрузить mapping JSON", type=["json"], key="svg_mapping_upl")' not in heavy_text
    assert "svg_mapping_uploaded" not in app_text
    assert "svg_mapping_uploaded" not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_mapping_input_helpers import (" in tools_text
    assert "render_svg_mapping_input(" in tools_text
    assert "def parse_svg_mapping_upload(" in helper_text
    assert "def parse_svg_mapping_text(" in helper_text
    assert "def render_svg_mapping_input(" in helper_text
