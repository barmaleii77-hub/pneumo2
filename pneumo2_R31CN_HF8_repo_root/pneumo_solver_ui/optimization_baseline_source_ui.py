from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from pneumo_solver_ui.optimization_baseline_source import (
    baseline_source_label,
    build_baseline_center_surface,
    describe_active_baseline_state,
    read_active_baseline_contract,
    read_baseline_source_artifact,
    resolve_baseline_suite_handoff,
)


def _coerce_path(value: Any) -> Optional[Path]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Path(text)
    except Exception:
        return None


def baseline_source_surface_payload(
    *,
    summary: Any = None,
    run_dir: Path | str | None = None,
    read_artifact_fn: Callable[[Path | str], dict[str, Any]] = read_baseline_source_artifact,
) -> dict[str, Any]:
    source_kind = ""
    source_label_text = ""
    baseline_path = None

    if summary is not None:
        source_kind = str(getattr(summary, "baseline_source_kind", "") or "").strip().lower()
        source_label_text = str(getattr(summary, "baseline_source_label", "") or "").strip()
        baseline_path = _coerce_path(getattr(summary, "baseline_source_path", None))

    if not source_kind and not source_label_text and baseline_path is None and run_dir is not None:
        payload = dict(read_artifact_fn(run_dir) or {})
        source_kind = str(payload.get("source_kind") or "").strip().lower()
        source_label_text = str(payload.get("source_label") or "").strip()
        baseline_path = _coerce_path(payload.get("baseline_path"))

    if source_kind and not source_label_text:
        source_label_text = baseline_source_label(source_kind)

    if not source_kind and not source_label_text and baseline_path is None:
        return {}

    return {
        "source_kind": source_kind,
        "source_label": source_label_text,
        "baseline_path": baseline_path,
    }


def render_baseline_source_summary(
    st: Any,
    *,
    summary: Any = None,
    run_dir: Path | str | None = None,
    heading: str = "Baseline source",
    path_caption_prefix: str = "Baseline override at launch",
    read_artifact_fn: Callable[[Path | str], dict[str, Any]] = read_baseline_source_artifact,
) -> bool:
    payload = baseline_source_surface_payload(
        summary=summary,
        run_dir=run_dir,
        read_artifact_fn=read_artifact_fn,
    )
    if not payload:
        return False

    st.write(f"**{heading}:** {payload.get('source_label') or '—'}")

    baseline_path = payload.get("baseline_path")
    if baseline_path is not None:
        st.caption(f"{path_caption_prefix}: `{baseline_path}`")
    return True


def active_baseline_surface_payload(
    *,
    contract: dict[str, Any] | None = None,
    contract_path: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    read_contract_fn: Callable[..., dict[str, Any]] = read_active_baseline_contract,
) -> dict[str, Any]:
    payload = dict(contract or {})
    if not payload and contract_path is not None:
        payload = read_contract_fn(path=contract_path)
    state = describe_active_baseline_state(
        payload if payload else None,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
    )
    return {
        "state": str(state.get("state") or ""),
        "banner_id": str(state.get("banner_id") or ""),
        "banner": str(state.get("banner") or ""),
        "optimizer_can_consume": bool(state.get("optimizer_can_consume", False)),
        "active_baseline_hash": str(state.get("active_baseline_hash") or payload.get("active_baseline_hash") or ""),
        "suite_snapshot_hash": str(state.get("suite_snapshot_hash") or payload.get("suite_snapshot_hash") or ""),
    }


def render_active_baseline_summary(
    st: Any,
    *,
    contract: dict[str, Any] | None = None,
    contract_path: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    heading: str = "Active baseline handoff",
    read_contract_fn: Callable[..., dict[str, Any]] = read_active_baseline_contract,
) -> bool:
    payload = active_baseline_surface_payload(
        contract=contract,
        contract_path=contract_path,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
        read_contract_fn=read_contract_fn,
    )
    if not payload:
        return False

    state = payload.get("state") or "missing"
    st.write(f"**{heading}:** HO-006 / {state}")
    active_hash = str(payload.get("active_baseline_hash") or "")
    suite_hash = str(payload.get("suite_snapshot_hash") or "")
    if active_hash:
        st.caption(f"active_baseline_hash={active_hash[:12]}")
    if suite_hash:
        st.caption(f"suite_snapshot_hash={suite_hash[:12]}")
    banner = str(payload.get("banner") or "")
    if banner:
        st.caption(banner)
    return True


def baseline_suite_handoff_surface_payload(
    *,
    handoff: dict[str, Any] | None = None,
    workspace_dir: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    read_handoff_fn: Callable[..., dict[str, Any]] = resolve_baseline_suite_handoff,
) -> dict[str, Any]:
    payload = dict(handoff or {})
    if not payload:
        payload = read_handoff_fn(
            workspace_dir=workspace_dir,
            current_suite_snapshot_hash=current_suite_snapshot_hash,
        )
    if not payload:
        return {}
    return {
        "handoff_id": str(payload.get("handoff_id") or "HO-005"),
        "state": str(payload.get("state") or "missing"),
        "banner": str(payload.get("banner") or ""),
        "baseline_can_consume": bool(payload.get("baseline_can_consume", False)),
        "suite_snapshot_hash": str(payload.get("suite_snapshot_hash") or ""),
        "inputs_snapshot_hash": str(payload.get("inputs_snapshot_hash") or ""),
        "ring_source_hash": str(payload.get("ring_source_hash") or ""),
        "snapshot_path": _coerce_path(payload.get("snapshot_path")),
    }


def render_baseline_suite_handoff_summary(
    st: Any,
    *,
    handoff: dict[str, Any] | None = None,
    workspace_dir: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    heading: str = "Baseline suite handoff",
    read_handoff_fn: Callable[..., dict[str, Any]] = resolve_baseline_suite_handoff,
) -> bool:
    payload = baseline_suite_handoff_surface_payload(
        handoff=handoff,
        workspace_dir=workspace_dir,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        read_handoff_fn=read_handoff_fn,
    )
    if not payload:
        return False

    state = payload.get("state") or "missing"
    st.write(f"**{heading}:** HO-005 / {state}")
    suite_hash = str(payload.get("suite_snapshot_hash") or "")
    if suite_hash:
        st.caption(f"suite_snapshot_hash={suite_hash[:12]}")
    snapshot_path = payload.get("snapshot_path")
    if snapshot_path is not None:
        st.caption(f"validated_suite_snapshot={snapshot_path}")
    banner = str(payload.get("banner") or "")
    if banner:
        st.caption(banner)
    return True


def baseline_center_surface_payload(
    *,
    workspace_dir: Path | str | None = None,
    current_suite_snapshot_hash: str = "",
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
    selected_history_id: str = "",
    explicit_confirmation: bool = False,
    history_limit: int | None = 20,
) -> dict[str, Any]:
    return build_baseline_center_surface(
        workspace_dir=workspace_dir,
        current_suite_snapshot_hash=current_suite_snapshot_hash,
        current_inputs_snapshot_hash=current_inputs_snapshot_hash,
        current_ring_source_hash=current_ring_source_hash,
        selected_history_id=selected_history_id,
        explicit_confirmation=explicit_confirmation,
        history_limit=history_limit,
    )


def render_baseline_center_summary(
    st: Any,
    *,
    surface: dict[str, Any] | None = None,
    workspace_dir: Path | str | None = None,
    selected_history_id: str = "",
    explicit_confirmation: bool = False,
) -> bool:
    payload = dict(surface or {})
    if not payload:
        payload = baseline_center_surface_payload(
            workspace_dir=workspace_dir,
            selected_history_id=selected_history_id,
            explicit_confirmation=explicit_confirmation,
        )
    active = dict(payload.get("active_baseline") or {})
    suite = dict(payload.get("suite_handoff") or {})
    history_rows = tuple(payload.get("history_rows") or ())
    banner = dict(payload.get("banner_state") or {})

    st.write("**WS-BASELINE:** HO-005 -> active_baseline_contract -> HO-006")
    st.caption(
        " | ".join(
            [
                f"HO-005={suite.get('state') or 'missing'}",
                f"HO-006={active.get('state') or 'missing'}",
                f"history={len(history_rows)}",
            ]
        )
    )
    if str(active.get("active_baseline_hash") or ""):
        st.caption(f"active_baseline_hash={str(active.get('active_baseline_hash'))[:12]}")
    if suite:
        render_baseline_suite_handoff_summary(
            st,
            handoff=suite,
            heading="Baseline suite handoff",
        )
    if str(active.get("suite_snapshot_hash") or ""):
        st.caption(f"suite_snapshot_hash={str(active.get('suite_snapshot_hash'))[:12]}")
    if str(active.get("inputs_snapshot_hash") or ""):
        st.caption(f"inputs_snapshot_hash={str(active.get('inputs_snapshot_hash'))[:12]}")
    if str(active.get("ring_source_hash") or ""):
        st.caption(f"ring_source_hash={str(active.get('ring_source_hash'))[:12]}")
    if str(active.get("policy_mode") or ""):
        st.caption(f"policy_mode={active.get('policy_mode')}")
    if str(active.get("source_run_dir") or ""):
        st.caption(f"source_run={active.get('source_run_dir')}")
    if str(active.get("created_at_utc") or ""):
        st.caption(f"created={active.get('created_at_utc')}")
    if str(banner.get("banner") or ""):
        st.caption(str(banner.get("banner") or ""))
    return True


__all__ = [
    "active_baseline_surface_payload",
    "baseline_center_surface_payload",
    "baseline_source_surface_payload",
    "baseline_suite_handoff_surface_payload",
    "render_active_baseline_summary",
    "render_baseline_center_summary",
    "render_baseline_source_summary",
    "render_baseline_suite_handoff_summary",
]
