from __future__ import annotations

import json
from typing import Any


def parse_svg_mapping_upload(uploaded_file: Any) -> tuple[Any, str, int]:
    raw_bytes = uploaded_file.getvalue()
    mapping = json.loads(raw_bytes.decode("utf-8"))
    source = f"uploaded:{getattr(uploaded_file, 'name', '')}".strip(":")
    return mapping, source, len(raw_bytes)


def parse_svg_mapping_text(map_text: str) -> Any:
    return json.loads(map_text)


def render_svg_mapping_input(
    st: Any,
    session_state: dict[str, Any],
    *,
    log_event_fn: Any | None = None,
) -> Any:
    map_upl = st.file_uploader("Загрузить mapping JSON", type=["json"], key="svg_mapping_upl")
    map_text = st.text_area(
        "…или вставьте mapping JSON сюда (если вы нажали Copy в разметчике)",
        value=session_state.get("svg_mapping_text", ""),
        height=160,
    )

    mapping = None
    if map_upl is not None:
        try:
            mapping, source, raw_size = parse_svg_mapping_upload(map_upl)
            session_state["svg_mapping_text"] = json.dumps(mapping, ensure_ascii=False, indent=2)
            session_state["svg_mapping_source"] = source
            if log_event_fn is not None:
                log_event_fn("svg_mapping_uploaded", name=getattr(map_upl, "name", ""), bytes=raw_size)
        except Exception as exc:
            st.error(f"Не удалось прочитать mapping JSON: {exc}")
            if log_event_fn is not None:
                log_event_fn("svg_mapping_upload_failed", error=repr(exc))
    elif map_text.strip():
        try:
            mapping = parse_svg_mapping_text(map_text)
            if session_state.get("svg_mapping_source", "").startswith("uploaded") is False:
                session_state["svg_mapping_source"] = "textarea"
        except Exception as exc:
            st.error(f"JSON не парсится: {exc}")
            if log_event_fn is not None:
                log_event_fn("svg_mapping_text_parse_failed", error=repr(exc))

    return mapping
