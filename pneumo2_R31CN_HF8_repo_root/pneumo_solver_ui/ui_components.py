# -*- coding: utf-8 -*-
"""pneumo_solver_ui.ui_components

Зачем этот модуль:

Streamlit `components.declare_component()` иногда падает с:
  RuntimeError: module is None. This should never happen.

Это происходит, когда declare_component вызывается из "страницы", которую Streamlit
исполняет через `exec(...)` (у модуля может отсутствовать корректный __spec__).

Решение:
- вызывать `declare_component` из обычного импортируемого модуля (этого файла),
  который грузится стандартным importlib и имеет нормальный module spec.

Этот модуль содержит фабрики (lazy) для кастомных компонентов:
- playhead_ctrl
- mech_anim
- mech_car3d
- pneumo_svg_flow

Он НИКОГДА не должен ронять приложение: любые ошибки -> лог + None.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import os

# Best-effort diagnostics
def _emit(event: str, msg: str, **kw) -> None:
    try:
        from pneumo_solver_ui.diag.eventlog import get_global_logger
        root = Path(__file__).resolve().parents[1]
        ev = get_global_logger(root)
        ev.emit(event, msg, **kw)
    except Exception:
        return


try:
    import streamlit.components.v1 as components  # type: ignore
except Exception as _e:
    components = None  # type: ignore
    _emit("ComponentSystemMissing", repr(_e))


HERE = Path(__file__).resolve().parent

# caches
_PNEUMO_SVG_FLOW: Optional[Callable] = None
_MECH_ANIM: Optional[Callable] = None
_MECH_CAR3D: Optional[Callable] = None
_PLAYHEAD: Optional[Callable] = None

# extra live components (added earlier, but missing exports caused ImportError in web cockpits)
_CORNER_HEATMAP_LIVE: Optional[Callable] = None
_MINIMAP_LIVE: Optional[Callable] = None
_ROAD_PROFILE_LIVE: Optional[Callable] = None
_MECH_ANIM_QUAD: Optional[Callable] = None

# error strings (for UI/diagnostics if needed)
_LAST_ERR = {
    "pneumo_svg_flow": None,
    "mech_anim": None,
    "mech_car3d": None,
    "playhead_ctrl": None,
    "corner_heatmap_live": None,
    "minimap_live": None,
    "road_profile_live": None,
    "mech_anim_quad": None,
}


def _find_component_dir(name: str) -> Optional[Path]:
    """Find component directory.

    Priority:
    1) pneumo_solver_ui/components/<name>
    2) <repo_root>/components/<name>
    """
    cand1 = HERE / "components" / name
    if cand1.exists():
        return cand1
    cand2 = HERE.parent / "components" / name
    if cand2.exists():
        return cand2
    return None


def _declare(name: str) -> Optional[Callable]:
    if components is None:
        _LAST_ERR[name] = "streamlit.components not available"
        return None

    comp_dir = _find_component_dir(name)
    if comp_dir is None:
        _LAST_ERR[name] = f"assets missing: {name}"
        _emit("ComponentMissing", f"{name} assets missing", component=name)
        return None

    try:
        comp = components.declare_component(name, path=str(comp_dir.resolve()))
        _LAST_ERR[name] = None
        _emit("ComponentDeclared", name, component=name, path=str(comp_dir.resolve()))
        return comp
    except Exception as e:
        _LAST_ERR[name] = repr(e)
        _emit("ComponentDeclareFailed", repr(e), component=name, path=str(comp_dir), traceback="(see python logs)")
        return None


def last_error(name: str) -> Optional[str]:
    return _LAST_ERR.get(name)


def get_pneumo_svg_flow_component() -> Optional[Callable]:
    global _PNEUMO_SVG_FLOW
    if _PNEUMO_SVG_FLOW is not None:
        return _PNEUMO_SVG_FLOW
    _PNEUMO_SVG_FLOW = _declare("pneumo_svg_flow")
    return _PNEUMO_SVG_FLOW


def get_mech_anim_component() -> Optional[Callable]:
    global _MECH_ANIM
    if _MECH_ANIM is not None:
        return _MECH_ANIM
    _MECH_ANIM = _declare("mech_anim")
    return _MECH_ANIM


def get_mech_car3d_component() -> Optional[Callable]:
    global _MECH_CAR3D
    if _MECH_CAR3D is not None:
        return _MECH_CAR3D
    _MECH_CAR3D = _declare("mech_car3d")
    return _MECH_CAR3D


def get_playhead_ctrl_component() -> Optional[Callable]:
    global _PLAYHEAD
    if _PLAYHEAD is not None:
        return _PLAYHEAD
    _PLAYHEAD = _declare("playhead_ctrl")
    return _PLAYHEAD


def get_corner_heatmap_live_component() -> Optional[Callable]:
    """corner_heatmap_live streamlit component (web)."""
    global _CORNER_HEATMAP_LIVE
    if _CORNER_HEATMAP_LIVE is None:
        _CORNER_HEATMAP_LIVE = _declare("corner_heatmap_live")
    return _CORNER_HEATMAP_LIVE


def get_minimap_live_component() -> Optional[Callable]:
    """minimap_live streamlit component (web)."""
    global _MINIMAP_LIVE
    if _MINIMAP_LIVE is None:
        _MINIMAP_LIVE = _declare("minimap_live")
    return _MINIMAP_LIVE


def get_road_profile_live_component() -> Optional[Callable]:
    """road_profile_live streamlit component (web)."""
    global _ROAD_PROFILE_LIVE
    if _ROAD_PROFILE_LIVE is None:
        _ROAD_PROFILE_LIVE = _declare("road_profile_live")
    return _ROAD_PROFILE_LIVE


def get_mech_anim_quad_component() -> Optional[Callable]:
    """mech_anim_quad streamlit component (web)."""
    global _MECH_ANIM_QUAD
    if _MECH_ANIM_QUAD is None:
        _MECH_ANIM_QUAD = _declare("mech_anim_quad")
    return _MECH_ANIM_QUAD
