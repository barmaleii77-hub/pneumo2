from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


def desktop_mnemo_settings_path(project_root: Path) -> Path:
    return Path(project_root) / "pneumo_solver_ui" / "workspace" / "desktop_animator_settings.ini"


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
