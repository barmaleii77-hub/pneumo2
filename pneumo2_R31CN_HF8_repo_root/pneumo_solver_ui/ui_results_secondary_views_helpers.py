from __future__ import annotations

from typing import Any, Callable


def render_secondary_results_views(
    st: Any,
    *,
    view_res: str,
    flow_view_label: str,
    energy_audit_view_label: str,
    animation_view_label: str,
    render_flow_section_fn: Callable[..., None],
    flow_section_kwargs: dict[str, Any],
    render_energy_audit_section_fn: Callable[..., None],
    energy_audit_section_kwargs: dict[str, Any],
    render_animation_section_fn: Callable[..., None],
    animation_section_kwargs: dict[str, Any],
) -> bool:
    if view_res == flow_view_label:
        render_flow_section_fn(st, **flow_section_kwargs)
        return True
    if view_res == energy_audit_view_label:
        render_energy_audit_section_fn(st, **energy_audit_section_kwargs)
        return True
    if view_res == animation_view_label:
        render_animation_section_fn(st, **animation_section_kwargs)
        return True
    return False
