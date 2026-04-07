"""UI settings kept in session_state.

This project avoids any hidden "advanced" mode. Settings are always available,
but rare/global knobs should live in a dedicated Settings page.

The root app (app.py) applies a subset of settings to environment variables so
that crash/exit diagnostics work consistently.
"""

from __future__ import annotations

import os
from pathlib import Path


def _default_user_out_dir() -> Path:
    """Writable default directory for diagnostics bundles."""

    home = Path.home()
    return (home / "UnifiedPneumoApp" / "diagnostics").resolve()


def ensure_defaults(st_mod) -> None:
    """Ensure all known settings exist in st.session_state."""

    ss = st_mod.session_state

    ss.setdefault("settings_diag_out_dir", str(_default_user_out_dir()))
    ss.setdefault("settings_diag_keep_last_n", int(os.environ.get("PNEUMO_BUNDLE_KEEP_LAST_N", "10")))
    ss.setdefault("settings_diag_max_file_mb", int(os.environ.get("PNEUMO_BUNDLE_MAX_FILE_MB", "50")))
    ss.setdefault(
        "settings_diag_include_workspace",
        os.environ.get("PNEUMO_BUNDLE_INCLUDE_WORKSPACE", "1").lower() in ("1", "true", "yes", "on"),
    )
    ss.setdefault(
        "settings_diag_autosave_on_exit",
        os.environ.get("PNEUMO_AUTOSAVE_DIAG_ON_EXIT", "1").lower() in ("1", "true", "yes", "on"),
    )
    ss.setdefault(
        "settings_diag_autosave_on_crash",
        os.environ.get("PNEUMO_AUTOSAVE_DIAG_ON_CRASH", "1").lower() in ("1", "true", "yes", "on"),
    )
    ss.setdefault("settings_diag_tag", os.environ.get("PNEUMO_DIAG_TAG", ""))
    ss.setdefault("settings_diag_reason", "")

    # UI performance (global toggles)
    ss.setdefault("settings_ui_disable_heavy_plots", ss.get("disable_heavy_plots", False))
    ss.setdefault("settings_ui_cache_ttl_sec", int(os.environ.get("UI_CACHE_TTL_SEC", "3600")))

    # Optimization / determinism
    ss.setdefault("settings_opt_problem_hash_mode", os.environ.get("PNEUMO_OPT_PROBLEM_HASH_MODE", "stable"))
    # Pneumatics (ISO6358)
    ss.setdefault("settings_iso6358_rho_anr_mode", os.environ.get("PNEUMO_ISO6358_RHO_ANR_MODE", "norm"))


def apply_env_from_settings(st_mod) -> None:
    """Apply selected settings to environment variables.

    crash_guard reads env vars at crash time, so we set them on every run.
    """

    ss = st_mod.session_state

    # Diagnostics bundle
    out_dir = str(ss.get("settings_diag_out_dir") or str(_default_user_out_dir()))
    os.environ["PNEUMO_BUNDLE_OUT_DIR"] = out_dir
    os.environ["PNEUMO_BUNDLE_KEEP_LAST_N"] = str(int(ss.get("settings_diag_keep_last_n", 10)))
    os.environ["PNEUMO_BUNDLE_MAX_FILE_MB"] = str(int(ss.get("settings_diag_max_file_mb", 50)))
    os.environ["PNEUMO_BUNDLE_INCLUDE_WORKSPACE"] = "1" if ss.get("settings_diag_include_workspace", True) else "0"
    os.environ["PNEUMO_AUTOSAVE_DIAG_ON_EXIT"] = "1" if ss.get("settings_diag_autosave_on_exit", True) else "0"
    os.environ["PNEUMO_AUTOSAVE_DIAG_ON_CRASH"] = "1" if ss.get("settings_diag_autosave_on_crash", True) else "0"
    os.environ["PNEUMO_DIAG_TAG"] = str(ss.get("settings_diag_tag", ""))

    # Optimization / determinism
    os.environ["PNEUMO_OPT_PROBLEM_HASH_MODE"] = str(ss.get("settings_opt_problem_hash_mode", "stable") or "stable")
    # Pneumatics (ISO6358)
    os.environ["PNEUMO_ISO6358_RHO_ANR_MODE"] = str(ss.get("settings_iso6358_rho_anr_mode", "norm") or "norm")

    # UI perf
    os.environ["UI_CACHE_TTL_SEC"] = str(int(ss.get("settings_ui_cache_ttl_sec", 3600)))

    # Backwards-compatible alias used by old tooling.
    os.environ.setdefault("PNEUMO_SEND_BUNDLE_OUT_DIR", out_dir)


def sync_common_flags(st_mod) -> None:
    """Mirror common toggles into historically used session_state keys."""

    ss = st_mod.session_state
    # Some pages still use this flag directly.
    ss["disable_heavy_plots"] = bool(ss.get("settings_ui_disable_heavy_plots", False))
