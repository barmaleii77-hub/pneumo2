from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from pneumo_solver_ui.optimization_problem_hash_mode import (
    normalize_problem_hash_mode,
    problem_hash_mode_artifact_path,
    read_problem_hash_mode_artifact,
)
from pneumo_solver_ui.optimization_problem_scope import (
    problem_hash_artifact_path,
    problem_hash_short_label,
    read_problem_hash_artifact,
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


def problem_scope_surface_payload(
    *,
    summary: Any = None,
    run_dir: Path | str | None = None,
    current_problem_hash: str | None = None,
    current_problem_hash_mode: str | None = None,
    read_artifact_fn: Callable[[Path | str], str] = read_problem_hash_artifact,
    read_mode_artifact_fn: Callable[[Path | str], str] = read_problem_hash_mode_artifact,
) -> dict[str, Any]:
    problem_hash = ""
    problem_hash_path = None
    problem_hash_mode = ""
    problem_hash_mode_path = None

    if summary is not None:
        problem_hash = str(getattr(summary, "problem_hash", "") or "").strip()
        problem_hash_path = _coerce_path(getattr(summary, "problem_hash_path", None))
        problem_hash_mode = normalize_problem_hash_mode(
            getattr(summary, "problem_hash_mode", None),
            default="",
        )
        problem_hash_mode_path = _coerce_path(getattr(summary, "problem_hash_mode_path", None))

    if not problem_hash and run_dir is not None:
        problem_hash = str(read_artifact_fn(run_dir) or "").strip()
        if problem_hash:
            problem_hash_path = problem_hash_artifact_path(run_dir)
    if not problem_hash_mode and run_dir is not None:
        problem_hash_mode = normalize_problem_hash_mode(
            read_mode_artifact_fn(run_dir),
            default="",
        )
        if problem_hash_mode:
            problem_hash_mode_path = problem_hash_mode_artifact_path(run_dir)

    current_hash = str(current_problem_hash or "").strip()
    current_mode = normalize_problem_hash_mode(current_problem_hash_mode, default="")
    compatibility = ""
    if current_hash:
        if not problem_hash:
            compatibility = "unknown"
        elif current_hash == problem_hash:
            compatibility = "match"
        else:
            compatibility = "different"

    mode_compatibility = ""
    if current_mode:
        if not problem_hash_mode:
            mode_compatibility = "unknown"
        elif current_mode == problem_hash_mode:
            mode_compatibility = "match"
        else:
            mode_compatibility = "different"

    if not problem_hash and not current_hash and not problem_hash_mode and not current_mode:
        return {}

    return {
        "problem_hash": problem_hash,
        "problem_hash_path": problem_hash_path,
        "problem_hash_short": problem_hash_short_label(problem_hash),
        "current_problem_hash": current_hash,
        "current_problem_hash_short": problem_hash_short_label(current_hash),
        "compatibility": compatibility,
        "problem_hash_mode": problem_hash_mode,
        "problem_hash_mode_path": problem_hash_mode_path,
        "current_problem_hash_mode": current_mode,
        "mode_compatibility": mode_compatibility,
    }


def render_problem_scope_summary(
    st: Any,
    *,
    summary: Any = None,
    run_dir: Path | str | None = None,
    current_problem_hash: str | None = None,
    current_problem_hash_mode: str | None = None,
    heading: str = "Problem scope",
    mismatch_message: str = (
        "Scope compatibility: differs from current launch contract. "
        "Resume/cache/baseline guards will treat this as a different optimization problem."
    ),
    unknown_message: str = (
        "Scope compatibility is unknown: this run has no explicit problem_hash artifact, "
        "so exact matching against the current launch contract is unavailable."
    ),
    read_artifact_fn: Callable[[Path | str], str] = read_problem_hash_artifact,
    read_mode_artifact_fn: Callable[[Path | str], str] = read_problem_hash_mode_artifact,
) -> bool:
    payload = problem_scope_surface_payload(
        summary=summary,
        run_dir=run_dir,
        current_problem_hash=current_problem_hash,
        current_problem_hash_mode=current_problem_hash_mode,
        read_artifact_fn=read_artifact_fn,
        read_mode_artifact_fn=read_mode_artifact_fn,
    )
    if not payload:
        return False

    problem_hash = str(payload.get("problem_hash") or "").strip()
    current_hash = str(payload.get("current_problem_hash") or "").strip()
    short_hash = str(payload.get("problem_hash_short") or "").strip()
    current_short = str(payload.get("current_problem_hash_short") or "").strip()
    compatibility = str(payload.get("compatibility") or "").strip()
    problem_hash_mode = str(payload.get("problem_hash_mode") or "").strip()
    current_mode = str(payload.get("current_problem_hash_mode") or "").strip()
    mode_compatibility = str(payload.get("mode_compatibility") or "").strip()

    if problem_hash:
        st.write(f"**{heading}:** `{short_hash or problem_hash}`")
        if short_hash and short_hash != problem_hash:
            st.caption(f"problem_hash: `{problem_hash}`")
    else:
        st.write(f"**{heading}:** legacy / no explicit problem_hash")

    if problem_hash_mode:
        st.caption(f"Hash mode: `{problem_hash_mode}`")
    elif current_mode:
        st.caption("Hash mode: implicit / artifact missing")

    if compatibility == "match":
        st.caption(f"Scope compatibility: matches current launch contract (`{current_short or current_hash}`).")
    elif compatibility == "different":
        st.warning(
            mismatch_message
            + f" run=`{short_hash or problem_hash}`, current=`{current_short or current_hash}`."
        )
    elif compatibility == "unknown" and current_hash:
        st.info(unknown_message + f" Current launch scope: `{current_short or current_hash}`.")

    if mode_compatibility == "match":
        st.caption(f"Hash mode matches current launch contract (`{current_mode}`).")
    elif mode_compatibility == "different":
        st.warning(
            "Hash mode differs from current launch contract. "
            f"run=`{problem_hash_mode}`, current=`{current_mode}`. "
            "Even visually similar launches can be treated as different scope for resume/cache."
        )
    elif mode_compatibility == "unknown" and current_mode:
        st.info(
            "Hash mode is unknown for this run because the explicit artifact is missing. "
            f"Current launch mode: `{current_mode}`."
        )
    return True


__all__ = [
    "problem_scope_surface_payload",
    "render_problem_scope_summary",
]
