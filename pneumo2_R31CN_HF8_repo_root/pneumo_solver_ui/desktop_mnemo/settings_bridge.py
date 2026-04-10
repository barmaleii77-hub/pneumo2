from __future__ import annotations

import json
from configparser import ConfigParser
from pathlib import Path
from typing import Any


def desktop_mnemo_settings_path(project_root: Path) -> Path:
    return Path(project_root) / "pneumo_solver_ui" / "workspace" / "desktop_animator_settings.ini"


def desktop_mnemo_event_log_path(npz_path: Path) -> Path:
    npz_abs = Path(npz_path).expanduser().resolve()
    return npz_abs.with_name(f"{npz_abs.stem}.desktop_mnemo_events.json")


def normalize_desktop_mnemo_view_mode(mode: str) -> str:
    return "overview" if str(mode or "").strip().lower() == "overview" else "focus"


def desktop_mnemo_view_mode_label(mode: str) -> str:
    normalized = normalize_desktop_mnemo_view_mode(mode)
    if normalized == "overview":
        return "Полная схема"
    return "Фокусный сценарий"


def read_desktop_mnemo_view_mode(project_root: Path) -> str:
    ini_path = desktop_mnemo_settings_path(project_root)
    if not ini_path.exists():
        return "focus"

    parser = ConfigParser()
    parser.optionxform = str
    try:
        parser.read(ini_path, encoding="utf-8")
    except Exception:
        return "focus"

    candidates = [
        ("desktop_mnemo", "view_mode"),
        ("General", "desktop_mnemo/view_mode"),
        ("General", "desktop_mnemo\\view_mode"),
    ]
    for section, key in candidates:
        if parser.has_section(section) and parser.has_option(section, key):
            return normalize_desktop_mnemo_view_mode(parser.get(section, key, fallback="focus"))

    raw_text = ""
    try:
        raw_text = ini_path.read_text(encoding="utf-8")
    except Exception:
        raw_text = ""
    for marker in ("desktop_mnemo/view_mode=", "desktop_mnemo\\view_mode="):
        for line in raw_text.splitlines():
            if line.strip().startswith(marker):
                return normalize_desktop_mnemo_view_mode(line.split("=", 1)[-1].strip())
    return "focus"


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _coerce_text(value: Any) -> str:
    return str(value or "").strip()


def _focus_label(edge_name: str, node_name: str) -> str:
    if edge_name and node_name:
        return f"{edge_name} / {node_name}"
    return edge_name or node_name


def infer_desktop_mnemo_startup_seek(npz_path: Path) -> dict[str, Any]:
    npz_abs = Path(npz_path).expanduser().resolve()
    event_log = desktop_mnemo_event_log_path(npz_abs)
    fallback = {
        "available": False,
        "time_s": None,
        "label": "Старт с начала прогона",
        "reason": "Event-log sidecar для этого NPZ ещё не найден.",
        "event_title": "",
        "event_summary": "",
        "edge_name": "",
        "node_name": "",
        "focus_label": "",
        "source": "none",
        "event_log_path": str(event_log),
    }
    if not event_log.exists():
        return fallback

    try:
        payload = json.loads(event_log.read_text(encoding="utf-8"))
    except Exception:
        broken = dict(fallback)
        broken["reason"] = "Event-log sidecar найден, но не читается как JSON."
        broken["source"] = "broken_sidecar"
        return broken

    def _pick_event(rows: Any) -> dict[str, Any] | None:
        if not isinstance(rows, list):
            return None
        for item in rows:
            if not isinstance(item, dict):
                continue
            time_s = _coerce_float(item.get("time_s"))
            if time_s is None:
                continue
            return {
                "time_s": time_s,
                "title": _coerce_text(item.get("title")),
                "summary": _coerce_text(item.get("summary")),
                "edge_name": _coerce_text(item.get("edge_name")),
                "node_name": _coerce_text(item.get("node_name")),
            }
        return None

    active_event = _pick_event(payload.get("active_latches"))
    if active_event is not None:
        title = active_event["title"] or "Активный latch"
        time_s = float(active_event["time_s"])
        edge_name = str(active_event["edge_name"])
        node_name = str(active_event["node_name"])
        return {
            "available": True,
            "time_s": time_s,
            "label": f"{time_s:0.3f} s · {title}",
            "reason": "Старт окна смещён к последнему активному latch из event-log.",
            "event_title": title,
            "event_summary": active_event["summary"],
            "edge_name": edge_name,
            "node_name": node_name,
            "focus_label": _focus_label(edge_name, node_name),
            "source": "active_latch",
            "event_log_path": str(event_log),
        }

    recent_event = _pick_event(payload.get("recent_events"))
    if recent_event is not None:
        title = recent_event["title"] or "Недавнее событие"
        time_s = float(recent_event["time_s"])
        edge_name = str(recent_event["edge_name"])
        node_name = str(recent_event["node_name"])
        return {
            "available": True,
            "time_s": time_s,
            "label": f"{time_s:0.3f} s · {title}",
            "reason": "Старт окна смещён к ближайшему недавнему событию из event-log.",
            "event_title": title,
            "event_summary": recent_event["summary"],
            "edge_name": edge_name,
            "node_name": node_name,
            "focus_label": _focus_label(edge_name, node_name),
            "source": "recent_event",
            "event_log_path": str(event_log),
        }

    current_time_s = _coerce_float(payload.get("current_time_s"))
    if current_time_s is not None:
        title = _coerce_text(payload.get("current_mode")) or "Текущий режим"
        edge_name = _coerce_text(payload.get("selected_edge"))
        node_name = _coerce_text(payload.get("selected_node"))
        return {
            "available": True,
            "time_s": float(current_time_s),
            "label": f"{float(current_time_s):0.3f} s · {title}",
            "reason": "Старт окна смещён к текущему кадру, зафиксированному в event-log sidecar.",
            "event_title": title,
            "event_summary": "",
            "edge_name": edge_name,
            "node_name": node_name,
            "focus_label": _focus_label(edge_name, node_name),
            "source": "current_frame",
            "event_log_path": str(event_log),
        }

    empty = dict(fallback)
    empty["reason"] = "Event-log sidecar найден, но в нём нет пригодной временной привязки."
    empty["source"] = "empty_sidecar"
    return empty
