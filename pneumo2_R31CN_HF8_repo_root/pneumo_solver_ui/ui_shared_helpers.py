from __future__ import annotations

"""Small pure helpers shared by legacy and home-page UI entrypoints."""

from difflib import SequenceMatcher
import re
from typing import Any, Iterable

import numpy as np


_DASH_RE = re.compile(r"[-‐‑‒–—−]")
_NONWORD_RE = re.compile(r"[^0-9A-Za-zА-Яа-я]+", re.UNICODE)


def run_starts(mask: np.ndarray | None) -> list[int]:
    """Return indices where a boolean mask starts being True."""
    if mask is None:
        return []
    m = np.asarray(mask, dtype=bool)
    if m.size == 0:
        return []
    prev = np.concatenate([[False], m[:-1]])
    starts = np.where(m & (~prev))[0]
    return [int(i) for i in starts.tolist()]


def shorten_name(name: str, max_len: int = 60) -> str:
    s = str(name)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def norm_name(s: Any) -> str:
    """Normalize a label for tolerant matching."""
    try:
        s = str(s)
    except Exception:
        return ""
    s = s.strip().lower()
    s = _DASH_RE.sub("-", s)
    s = _NONWORD_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_score(a: str, b: str) -> float:
    na = norm_name(a)
    nb = norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    r = SequenceMatcher(None, na, nb).ratio()
    ta = set(na.split())
    tb = set(nb.split())
    jac = len(ta & tb) / max(1, len(ta | tb))
    return 0.75 * r + 0.25 * jac


def best_match(target: str, candidates: Iterable[str]) -> tuple[str | None, float]:
    best: str | None = None
    best_s = 0.0
    for candidate in candidates:
        sc = name_score(target, candidate)
        if sc > best_s:
            best_s = sc
            best = candidate
    return best, float(best_s)


__all__ = [
    "best_match",
    "name_score",
    "norm_name",
    "run_starts",
    "shorten_name",
]
