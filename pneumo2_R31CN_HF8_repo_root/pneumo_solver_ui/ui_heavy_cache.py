"""UI-level cache for expensive *visual* artifacts.

Why this exists
--------------
Streamlit reruns the script on many UI interactions.
If a page builds heavy charts/tables on every rerun, the UX feels like "it hangs".

This module provides a tiny cache layer that is:
- deterministic (key-based),
- controllable from UI (enabled/TTL/disk),
- safe (atomic writes),
- shareable across pages (single place).

It is *not* intended to cache the physical solver – only the expensive UI rendering artifacts
(e.g. Plotly figure JSON, pre-aggregated tables, downsampled arrays).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple


# ---------------------------
# Workspace / paths
# ---------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def workspace_dir() -> Path:
    env = os.environ.get("PNEUMO_WORKSPACE_DIR")
    if env:
        return Path(env)
    return _repo_root() / "workspace"


def cache_root_dir() -> Path:
    return workspace_dir() / "cache" / "ui_heavy"


def default_cache_dir(_here: "Path | None" = None) -> Path:
    """Compatibility alias for older UI code.

    Older versions of `pneumo_ui_app.py` imported and called `default_cache_dir(HERE)`.
    The cache is now always rooted in the per-session workspace when
    `PNEUMO_WORKSPACE_DIR` is set, otherwise under `<repo>/workspace`.

    Parameters
    ----------
    _here:
        Kept for backwards compatibility. It is ignored.
    """
    return cache_root_dir()


# ---------------------------
# Helpers
# ---------------------------

def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(obj: Any) -> str:
    """Stable hash for cache keys."""
    s = _safe_json(obj)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def file_fingerprint(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    try:
        st = p.stat()
        return {
            "path": str(p.resolve()),
            "mtime_ns": int(st.st_mtime_ns),
            "size": int(st.st_size),
        }
    except Exception:
        return {"path": str(p)}


# ---------------------------
# Cache
# ---------------------------


@dataclass
class UIHeavyCache:
    root: Path = field(default_factory=cache_root_dir)
    enabled: bool = True
    persist_disk: bool = True
    ttl_s: int = 24 * 3600

    # key -> (ts, value)
    _mem: Dict[str, Tuple[float, Any]] = field(default_factory=dict)

    def _now(self) -> float:
        return time.time()

    def _expired(self, ts: float) -> bool:
        return (self._now() - ts) > max(1, int(self.ttl_s))

    def _path_for(self, key: str, kind: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")
        if kind == "json":
            return self.root / f"{safe}.json"
        if kind == "pkl":
            return self.root / f"{safe}.pkl.gz"
        return self.root / f"{safe}.bin"

    def get_json(self, key: str) -> Optional[str]:
        if not self.enabled:
            return None

        # mem
        if key in self._mem:
            ts, val = self._mem[key]
            if not self._expired(ts):
                return val if isinstance(val, str) else None
            self._mem.pop(key, None)

        if not self.persist_disk:
            return None

        p = self._path_for(key, "json")
        if not p.exists():
            return None
        try:
            obj = json.loads(p.read_text("utf-8"))
            ts = float(obj.get("_ts", 0.0))
            if ts and self._expired(ts):
                return None
            payload = obj.get("payload")
            if isinstance(payload, str):
                # store in mem
                self._mem[key] = (self._now(), payload)
                return payload
        except Exception:
            return None
        return None

    def set_json(self, key: str, payload: str) -> None:
        if not self.enabled:
            return
        self._mem[key] = (self._now(), payload)
        if not self.persist_disk:
            return
        p = self._path_for(key, "json")
        data = {"_ts": self._now(), "payload": payload}
        _atomic_write_bytes(p, _safe_json(data).encode("utf-8"))

    def get_pickle(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None

        if key in self._mem:
            ts, val = self._mem[key]
            if not self._expired(ts):
                return val
            self._mem.pop(key, None)

        if not self.persist_disk:
            return None

        p = self._path_for(key, "pkl")
        if not p.exists():
            return None

        # Main path: gzip + pickle
        try:
            import pickle

            with gzip.open(p, "rb") as f:
                raw = f.read()
            val = pickle.loads(raw)
            self._mem[key] = (self._now(), val)
            return val
        except Exception:
            # Fallback (legacy/debug): gzip + utf-8 JSON
            try:
                with gzip.open(p, "rb") as f:
                    raw = f.read()
                obj = json.loads(raw.decode("utf-8"))
                if isinstance(obj, dict) and "payload" in obj:
                    ts = float(obj.get("_ts", 0.0))
                    if ts and self._expired(ts):
                        return None
                    payload = obj.get("payload")
                    self._mem[key] = (self._now(), payload)
                    return payload
            except Exception:
                return None
        return None

    def set_pickle(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        self._mem[key] = (self._now(), value)
        if not self.persist_disk:
            return
        p = self._path_for(key, "pkl")
        try:
            import pickle

            payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            with gzip.open(p, "wb") as f:
                f.write(payload)
        except Exception:
            # Last resort: JSON in gzip (may be big)
            try:
                data = {"_ts": self._now(), "payload": value}
                with gzip.open(p, "wt", encoding="utf-8") as f:
                    f.write(_safe_json(data))
            except Exception:
                pass

    def clear(self) -> int:
        """Clear cache files + memory. Returns number of removed files."""
        self._mem.clear()
        if not self.root.exists():
            return 0
        removed = 0
        try:
            for p in self.root.glob("*"):
                if p.is_file():
                    try:
                        p.unlink()
                        removed += 1
                    except Exception:
                        pass
        except Exception:
            pass
        return removed


# ---------------------------
# Streamlit integration helpers
# ---------------------------


def init_perf_defaults(st) -> None:
    """Initialize UI performance settings defaults (once)."""
    if "ui_perf_cache_enabled" not in st.session_state:
        st.session_state["ui_perf_cache_enabled"] = True
    if "ui_perf_cache_disk" not in st.session_state:
        st.session_state["ui_perf_cache_disk"] = True
    if "ui_perf_cache_ttl_s" not in st.session_state:
        st.session_state["ui_perf_cache_ttl_s"] = 24 * 3600


def get_cache(st) -> UIHeavyCache:
    """Get a singleton cache object configured from session_state."""
    init_perf_defaults(st)
    obj = st.session_state.get("_ui_heavy_cache_obj")
    if not isinstance(obj, UIHeavyCache):
        obj = UIHeavyCache()
        st.session_state["_ui_heavy_cache_obj"] = obj

    obj.enabled = bool(st.session_state.get("ui_perf_cache_enabled", True))
    obj.persist_disk = bool(st.session_state.get("ui_perf_cache_disk", True))
    try:
        obj.ttl_s = int(st.session_state.get("ui_perf_cache_ttl_s", 24 * 3600))
    except Exception:
        obj.ttl_s = 24 * 3600
    return obj


def cached_json(
    st,
    *,
    key: str,
    build: Callable[[], str],
) -> str:
    cache = get_cache(st)
    val = cache.get_json(key)
    if val is not None:
        return val
    val = build()
    cache.set_json(key, val)
    return val


def cached_pickle(
    st,
    *,
    key: str,
    build: Callable[[], Any],
) -> Any:
    cache = get_cache(st)
    val = cache.get_pickle(key)
    if val is not None:
        return val
    val = build()
    cache.set_pickle(key, val)
    return val
