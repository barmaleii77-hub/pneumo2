# -*- coding: utf-8 -*-
"""osc_index.py

NPZ index / traceability utilities.

- Scans folders with *.npz (usually Txx_osc.npz) and builds a JSONL index.
- Extracts meta_json and several useful keys into columns.
- Helps map CSV rows (optimization / experiments) to NPZ logs.

Default index location: workspace/osc_index_full.jsonl
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

DEFAULT_INDEX_NAME = "osc_index_full.jsonl"


def default_index_path(app_dir: Path) -> Path:
    return Path(app_dir) / "workspace" / DEFAULT_INDEX_NAME


def _safe_json_loads(s: Any) -> Dict[str, Any]:
    try:
        if isinstance(s, np.ndarray):
            if s.size == 1:
                s = s.item()
            else:
                s = s.tolist()
        if isinstance(s, (bytes, bytearray)):
            s = s.decode("utf-8", errors="replace")
        if not isinstance(s, str):
            s = str(s)
        return json.loads(s)
    except Exception:
        return {}


def _read_meta_json(npz_path: Path) -> Dict[str, Any]:
    """Try to read only meta_json from a npz. Returns {} if missing."""
    try:
        z = np.load(npz_path, allow_pickle=True)
    except Exception:
        return {}
    try:
        if "meta_json" not in z:
            return {}
        return _safe_json_loads(z["meta_json"])
    except Exception:
        return {}
    finally:
        try:
            z.close()
        except Exception:
            pass


_TESTNUM_RE = re.compile(r"(?:^|[\\/])T(\d{1,3})_.*?\.npz$", re.IGNORECASE)


def infer_test_num(npz_path: Path) -> Optional[int]:
    m = _TESTNUM_RE.search(str(npz_path))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _flatten_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Surface a few common keys from meta to the top-level record."""
    out: Dict[str, Any] = {}

    def pick(*keys: str) -> Optional[Any]:
        for k in keys:
            if k in meta:
                return meta.get(k)
        return None

    out["app_release"] = pick("app_release", "release", "версия")
    out["exported_at"] = pick("exported_at", "export_ts", "ts")
    out["suite"] = pick("suite", "suite_name", "suite_id", "имя_сьюта")
    out["test_name"] = pick("test_name", "имя_теста", "test", "scenario")
    out["test_num"] = pick("test_num", "номер_теста")
    out["run_id"] = pick("run_id", "candidate_id", "id", "trial_id")
    out["seed"] = pick("seed", "rng_seed")
    out["params_hash"] = pick("params_hash", "base_hash", "hash_params", "x_hash")
    out["npz_version"] = pick("npz_version", "format_version")
    return out


def _jsonable_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Make meta JSON-serializable (best-effort)."""
    safe: Dict[str, Any] = {}
    for k, v in (meta or {}).items():
        if v is None or isinstance(v, (str, int, float, bool)):
            safe[str(k)] = v
        else:
            try:
                safe[str(k)] = str(v)
            except Exception:
                safe[str(k)] = "<unrepr>"
    return safe


def scan_npz_files(roots: Sequence[Path], *, recursive: bool = True) -> List[Path]:
    files: List[Path] = []
    for r in roots:
        r = Path(r)
        if not r.exists():
            continue
        if r.is_file() and r.suffix.lower() == ".npz":
            files.append(r)
            continue
        if not r.is_dir():
            continue
        if recursive:
            files.extend(sorted(r.rglob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True))
        else:
            files.extend(sorted(r.glob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True))
    # unique by resolved path
    uniq: Dict[str, Path] = {}
    for p in files:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        uniq[key] = p
    return list(uniq.values())


def load_index(index_path: Path) -> pd.DataFrame:
    index_path = Path(index_path)
    if not index_path.exists():
        return pd.DataFrame()
    rows: List[Dict[str, Any]] = []
    try:
        for line in index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def save_index(index_path: Path, rows: List[Dict[str, Any]]) -> Path:
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return index_path


def build_or_update_index(
    npz_roots: Sequence[Path],
    *,
    index_path: Path,
    recursive: bool = True,
    max_files: Optional[int] = None,
    quick: bool = False,
) -> pd.DataFrame:
    """Build/update index file.

    quick=True: don't open npz for meta_json (store empty meta); useful for huge folders.
    """
    index_path = Path(index_path)
    existing = load_index(index_path)
    prev: Dict[str, Dict[str, Any]] = {}
    if len(existing) > 0 and "path" in existing.columns:
        for _, r in existing.iterrows():
            p = str(r.get("path", ""))
            if p:
                prev[p] = dict(r)

    files = scan_npz_files(npz_roots, recursive=recursive)
    if max_files is not None and len(files) > int(max_files):
        files = files[: int(max_files)]

    out_rows: List[Dict[str, Any]] = []
    for p in files:
        try:
            st = p.stat()
            mtime = float(st.st_mtime)
            size = int(st.st_size)
        except Exception:
            continue

        key = str(p.resolve()) if p.exists() else str(p)
        prev_rec = prev.get(key)
        if prev_rec is not None:
            try:
                if float(prev_rec.get("mtime", -1)) == mtime and int(prev_rec.get("size", -1)) == size:
                    out_rows.append(prev_rec)
                    continue
            except Exception:
                pass

        meta = {} if quick else _read_meta_json(p)
        flat = _flatten_meta(meta)
        test_num = flat.get("test_num")
        if test_num is None:
            tn = infer_test_num(p)
            if tn is not None:
                test_num = tn

        rec: Dict[str, Any] = {
            "path": key,
            "name": p.name,
            "mtime": mtime,
            "size": size,
            "indexed_at": datetime.now().isoformat(timespec="seconds"),
            "test_num": test_num,
            "test_name": flat.get("test_name"),
            "suite": flat.get("suite"),
            "run_id": flat.get("run_id"),
            "seed": flat.get("seed"),
            "params_hash": flat.get("params_hash"),
            "app_release": flat.get("app_release"),
            "exported_at": flat.get("exported_at"),
            "meta": _jsonable_meta(meta),
        }
        out_rows.append(rec)

    save_index(index_path, out_rows)
    return pd.DataFrame(out_rows)


def resolve_paths(raw_paths: Sequence[str], roots: Sequence[Path]) -> Tuple[List[str], pd.DataFrame]:
    """Resolve possibly-relative paths against roots. Return (existing_paths, status_df)."""
    roots = [Path(r) for r in roots if r is not None and Path(r).exists()]
    seen: set[str] = set()
    ok: List[str] = []
    rows = []
    for rp in raw_paths:
        if not isinstance(rp, str):
            continue
        s = rp.strip()
        if not s:
            continue
        cand = Path(s)
        tried: List[str] = []
        hit: Optional[Path] = None
        if cand.exists():
            hit = cand
        else:
            for r in roots:
                p = (r / cand).resolve()
                tried.append(str(p))
                if p.exists():
                    hit = p
                    break
        if hit is not None:
            sp = str(hit.resolve())
            if sp not in seen:
                seen.add(sp)
                ok.append(sp)
        rows.append({"raw": s, "resolved": str(hit) if hit else "", "exists": bool(hit), "tried": "; ".join(tried[:6])})
    return ok, pd.DataFrame(rows)


def match_npz_for_row(
    row: pd.Series,
    idx: pd.DataFrame,
    *,
    roots: Sequence[Path],
    prefer_latest: bool = True,
) -> List[str]:
    """Return candidate NPZ paths for a CSV row using index + heuristics."""
    if idx is None or len(idx) == 0:
        return []

    # 1) explicit path columns
    for c in ("npz_path", "npz_file", "npz", "osc_npz", "log_npz", "path_npz", "путь_npz", "файл_npz"):
        if c in row.index:
            v = row.get(c)
            if isinstance(v, str) and v.strip():
                ok, _ = resolve_paths([v], roots)
                if ok:
                    return ok

    # 2) params_hash
    if "params_hash" in row.index and "params_hash" in idx.columns:
        v = row.get("params_hash")
        if isinstance(v, str) and v:
            df = idx[idx["params_hash"].astype(str) == str(v)]
            if len(df) > 0:
                out = df["path"].astype(str).tolist()
                if prefer_latest and "mtime" in df.columns:
                    out = [p for _, p in sorted(zip(df["mtime"].astype(float).tolist(), out), reverse=True)]
                return [p for p in out if Path(p).exists()]

    # 3) run_id / seed / test_num / test_name
    candidates = idx

    # run_id
    for c in ("run_id", "candidate_id", "id", "trial_id"):
        if c in row.index and "run_id" in idx.columns:
            v = row.get(c)
            if v is not None and str(v).strip():
                candidates = candidates[candidates["run_id"].astype(str) == str(v)]
                break

    # seed
    if "seed" in row.index and "seed" in idx.columns:
        v = row.get("seed")
        if v is not None and str(v).strip():
            candidates = candidates[candidates["seed"].astype(str) == str(v)]

    # test_num
    for c in ("test_num", "номер_теста"):
        if c in row.index and "test_num" in idx.columns:
            v = row.get(c)
            try:
                vv = int(v)
                candidates = candidates[pd.to_numeric(candidates["test_num"], errors="coerce") == vv]
            except Exception:
                pass

    # test_name
    for c in ("имя_теста", "test_name", "test"):
        if c in row.index and "test_name" in idx.columns:
            v = row.get(c)
            if isinstance(v, str) and v.strip():
                candidates = candidates[candidates["test_name"].astype(str) == str(v)]

    if len(candidates) == 0:
        return []

    out = candidates["path"].astype(str).tolist()
    if prefer_latest and "mtime" in candidates.columns:
        out = [p for _, p in sorted(zip(candidates["mtime"].astype(float).tolist(), out), reverse=True)]
    out = [p for p in out if Path(p).exists()]
    return out[:10]


def map_rows_to_npz(
    df_csv: pd.DataFrame,
    idx: pd.DataFrame,
    *,
    roots: Sequence[Path],
    max_per_row: int = 3,
) -> pd.DataFrame:
    """Map each CSV row to up to N NPZ candidates. Returns a dataframe with:
    _row, npz_best, npz_candidates
    """
    rows = []
    if df_csv is None or len(df_csv) == 0:
        return pd.DataFrame(columns=["_row", "npz_best", "npz_candidates"])
    row_ids = df_csv["_row"].tolist() if "_row" in df_csv.columns else list(range(len(df_csv)))

    for i, rid in enumerate(row_ids):
        try:
            r = df_csv.iloc[i]
        except Exception:
            continue
        cands = match_npz_for_row(r, idx, roots=roots)
        best = ""
        for p in cands:
            if Path(p).exists():
                best = str(Path(p).resolve())
                break
        rows.append({"_row": int(rid), "npz_best": best, "npz_candidates": cands[: int(max_per_row)]})
    return pd.DataFrame(rows)
