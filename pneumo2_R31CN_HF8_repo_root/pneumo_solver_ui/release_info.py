"""Release/version helpers.

This module is intentionally tiny and dependency-free.

Why it exists:
- Many tools and UI modules need a consistent "release tag" for logs, bundles and reports.
- During merge/integration it is easy to accidentally drop these helpers, causing ImportError.

Conventions:
- Environment variable PNEUMO_RELEASE (set by app.py) is the primary source.
- DEFAULT_RELEASE is used when PNEUMO_RELEASE is absent.
"""

from __future__ import annotations

import os
import re
from typing import Optional


# Keep the default aligned with the package version.
DEFAULT_RELEASE = "PneumoApp_v6_80_R176_R31CN_HF8_2026-04-03"


def get_release(default: Optional[str] = None) -> str:
    """Return current release tag.

    Priority:
    1) env PNEUMO_RELEASE
    2) provided default
    3) DEFAULT_RELEASE
    """
    return (os.environ.get("PNEUMO_RELEASE") or default or DEFAULT_RELEASE).strip() or DEFAULT_RELEASE


def get_release_tag(default: Optional[str] = None) -> str:
    """Return a filesystem-safe release tag (for filenames, folders, zip names)."""
    rel = get_release(default=default)
    # Replace anything unusual with underscore, keep dots/dashes.
    return re.sub(r"[^A-Za-z0-9._-]+", "_", rel)


def get_version(default: Optional[str] = None) -> str:
    """Best-effort extract version like 'v6_80' from release string."""
    rel = get_release(default=default)
    m = re.search(r"\bv\d+_\d+\b", rel)
    return m.group(0) if m else rel


def format_release_header(default: Optional[str] = None) -> str:
    """Human-friendly header for UI/reporting."""
    rel = get_release(default=default)
    ver = get_version(default=default)
    return f"{rel} ({ver})" if ver not in rel else rel
