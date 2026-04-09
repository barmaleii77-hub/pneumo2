from __future__ import annotations

"""Canonical entrypoint paths for the current release tree.

Why this exists
---------------
- The project contains several top-level UI files with different roles.
- Some tools historically launched `pneumo_ui_app.py` directly while the
  Windows launcher starts the root `app.py`.
- Centralizing these paths reduces drift and makes tooling consistent.
"""

from dataclasses import dataclass
from pathlib import Path


def repo_root(*, here: str | Path | None = None) -> Path:
    base = Path(here) if here is not None else Path(__file__)
    cur = base.resolve()
    if cur.is_file():
        cur = cur.parent

    for candidate in (cur, *cur.parents):
        if (candidate / "app.py").exists() and (candidate / "pneumo_solver_ui").is_dir():
            return candidate
        if candidate.name == "pneumo_solver_ui":
            return candidate.parent
    return cur


def canonical_streamlit_entrypoint(*, here: str | Path | None = None) -> Path:
    """Root Streamlit app used by launcher/manual `streamlit run`."""
    return repo_root(here=here) / "app.py"


def canonical_home_page(*, here: str | Path | None = None) -> Path:
    """Heavy home page that remains a page target inside the multipage app."""
    return repo_root(here=here) / "pneumo_solver_ui" / "pneumo_ui_app.py"


def legacy_single_page_entrypoint(*, here: str | Path | None = None) -> Path:
    """Legacy single-page package UI kept for compatibility and source guards."""
    return repo_root(here=here) / "pneumo_solver_ui" / "app.py"


def desktop_animator_page(*, here: str | Path | None = None) -> Path:
    """Desktop Animator page inside the multipage UI."""
    return repo_root(here=here) / "pneumo_solver_ui" / "pages" / "08_DesktopAnimator.py"


def desktop_mnemo_page(*, here: str | Path | None = None) -> Path:
    """Desktop Mnemo page inside the multipage UI."""
    return repo_root(here=here) / "pneumo_solver_ui" / "pages" / "08_DesktopMnemo.py"


def validation_web_page(*, here: str | Path | None = None) -> Path:
    """Validation page used as the next step after preflight."""
    return repo_root(here=here) / "pneumo_solver_ui" / "pages" / "09_Validation_Web.py"


def env_diagnostics_page(*, here: str | Path | None = None) -> Path:
    """Environment diagnostics page exposed from the multipage UI."""
    return repo_root(here=here) / "pneumo_solver_ui" / "pages" / "99_EnvDiagnostics.py"


def repo_relative(path: str | Path, *, here: str | Path | None = None) -> str:
    """Return a repo-relative path with forward slashes for Streamlit navigation."""
    root = repo_root(here=here).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"path {candidate} is outside repo root {root}") from exc


def canonical_streamlit_entrypoint_rel(*, here: str | Path | None = None) -> str:
    return repo_relative(canonical_streamlit_entrypoint(here=here), here=here)


def canonical_home_page_rel(*, here: str | Path | None = None) -> str:
    return repo_relative(canonical_home_page(here=here), here=here)


def legacy_single_page_entrypoint_rel(*, here: str | Path | None = None) -> str:
    return repo_relative(legacy_single_page_entrypoint(here=here), here=here)


def desktop_animator_page_rel(*, here: str | Path | None = None) -> str:
    return repo_relative(desktop_animator_page(here=here), here=here)


def desktop_mnemo_page_rel(*, here: str | Path | None = None) -> str:
    return repo_relative(desktop_mnemo_page(here=here), here=here)


def validation_web_page_rel(*, here: str | Path | None = None) -> str:
    return repo_relative(validation_web_page(here=here), here=here)


def env_diagnostics_page_rel(*, here: str | Path | None = None) -> str:
    return repo_relative(env_diagnostics_page(here=here), here=here)


@dataclass(frozen=True)
class UiEntrypointSpec:
    key: str
    rel_path: str
    role: str


def ui_entrypoint_specs(*, here: str | Path | None = None) -> tuple[UiEntrypointSpec, ...]:
    """Ordered entrypoint inventory for docs, checks, and tooling."""
    return (
        UiEntrypointSpec(
            key="canonical_shell",
            rel_path=canonical_streamlit_entrypoint_rel(here=here),
            role="Canonical Streamlit shell launched by START_PNEUMO_APP and manual streamlit run app.py.",
        ),
        UiEntrypointSpec(
            key="home_page",
            rel_path=canonical_home_page_rel(here=here),
            role="Heavy multipage home screen rendered inside the canonical shell.",
        ),
        UiEntrypointSpec(
            key="legacy_single_page",
            rel_path=legacy_single_page_entrypoint_rel(here=here),
            role="Legacy single-page package UI kept for compatibility and source-level regression guards.",
        ),
    )


__all__ = [
    "UiEntrypointSpec",
    "repo_root",
    "repo_relative",
    "canonical_streamlit_entrypoint",
    "canonical_streamlit_entrypoint_rel",
    "canonical_home_page",
    "canonical_home_page_rel",
    "legacy_single_page_entrypoint",
    "legacy_single_page_entrypoint_rel",
    "desktop_animator_page",
    "desktop_animator_page_rel",
    "desktop_mnemo_page",
    "desktop_mnemo_page_rel",
    "validation_web_page",
    "validation_web_page_rel",
    "env_diagnostics_page",
    "env_diagnostics_page_rel",
    "ui_entrypoint_specs",
]
