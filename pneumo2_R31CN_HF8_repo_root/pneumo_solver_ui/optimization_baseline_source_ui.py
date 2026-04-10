from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from pneumo_solver_ui.optimization_baseline_source import (
    baseline_source_label,
    read_baseline_source_artifact,
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


__all__ = [
    "baseline_source_surface_payload",
    "render_baseline_source_summary",
]
