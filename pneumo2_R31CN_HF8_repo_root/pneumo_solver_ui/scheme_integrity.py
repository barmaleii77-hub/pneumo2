"""Scheme integrity helpers.

Fixes & goals
- Detect scheme regressions after merges (sha256 fingerprint).
- Validate Camozzi codes against the component passport.
- Be robust to multiple representations:
  * Node/Edge objects (attrs) used by models
  * dicts/lists loaded from JSON

This module is part of the "no functional loss" release policy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Like getattr, but supports dict objects."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_list(obj: Any) -> list[Any]:
    """Normalize nodes/edges container into a list of items."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, dict):
        # dict keys are not nodes; use values
        return list(obj.values())
    # fallback: treat as iterable
    return list(obj)


def canonicalize_scheme(nodes: Iterable[Any], edges: Iterable[Any]) -> dict:
    """Canonicalize nodes/edges into a stable JSON-serializable structure.

    IMPORTANT: the fingerprint MUST NOT depend on numerical parameters.
    Only topology and identifiers.

    Canonical format:
      {
        "nodes": [
          {"name": str, "kind": str, ...optional fields...},
          ...
        ],
        "edges": [
          {"name": str, "kind": str, "n1": str, "n2": str, "camozzi_код": str},
          ...
        ]
      }
    """

    nodes_list = _as_list(nodes)
    edges_list = _as_list(edges)

    # Map node index -> node name (models often reference nodes by index)
    idx_to_name: dict[int, str] = {}
    nodes_out: list[dict[str, Any]] = []

    for i, n in enumerate(nodes_list):
        name = str(_get_attr(n, "name", f"node_{i}"))
        kind = str(_get_attr(n, "kind", ""))
        idx_to_name[i] = name

        row: dict[str, Any] = {"name": name, "kind": kind}
        # Optional identity-ish fields that affect topology mapping in UI/models
        for opt in ("corner", "chamber", "cyl"):
            v = _get_attr(n, opt, None)
            if v is not None and v != "":
                row[opt] = v
        nodes_out.append(row)

    def _node_ref_to_name(ref: Any) -> str:
        if ref is None or ref == "":
            return ""
        # index -> name
        if isinstance(ref, int) and ref in idx_to_name:
            return idx_to_name[ref]
        # already a string name
        if isinstance(ref, str):
            return ref
        # object/dict with name
        nm = _get_attr(ref, "name", None)
        if isinstance(nm, str) and nm:
            return nm
        return str(ref)

    edges_out: list[dict[str, Any]] = []
    for i, e in enumerate(edges_list):
        name = str(_get_attr(e, "name", f"edge_{i}"))
        kind = str(_get_attr(e, "kind", ""))

        # endpoints may be indices, names, or Node objects
        n1_raw = _get_attr(e, "n1", None)
        n2_raw = _get_attr(e, "n2", None)
        # some representations use u/v
        if n1_raw is None:
            n1_raw = _get_attr(e, "u", None)
        if n2_raw is None:
            n2_raw = _get_attr(e, "v", None)

        n1 = _node_ref_to_name(n1_raw)
        n2 = _node_ref_to_name(n2_raw)

        camozzi_code = _get_attr(e, "camozzi_код", None)
        if camozzi_code is None or camozzi_code == "":
            camozzi_code = _get_attr(e, "camozzi", "")
        if camozzi_code is None:
            camozzi_code = ""
        camozzi_code = str(camozzi_code).strip()

        edges_out.append(
            {
                "name": name,
                "kind": kind,
                "n1": n1,
                "n2": n2,
                "camozzi_код": camozzi_code,
            }
        )

    # Stable ordering
    nodes_out.sort(key=lambda r: (r.get("name", ""), r.get("kind", "")))
    edges_out.sort(
        key=lambda r: (
            r.get("name", ""),
            r.get("kind", ""),
            r.get("n1", ""),
            r.get("n2", ""),
            r.get("camozzi_код", ""),
        )
    )

    return {"nodes": nodes_out, "edges": edges_out}


def fingerprint_scheme(canonical: dict) -> str:
    """Compute sha256 fingerprint for canonical scheme dict."""
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_camozzi_codes_sha256(edges_canonical: Iterable[dict[str, Any]]) -> str:
    codes: set[str] = set()
    for e in edges_canonical:
        if not isinstance(e, dict):
            continue
        c = (e.get("camozzi_код") or "").strip()
        if c:
            codes.add(c)
    blob = "\n".join(sorted(codes))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compute_fingerprint(nodes: Any, edges: Any) -> dict:
    """Compute a fingerprint dict.

    The returned dict is JSON-serializable and intentionally includes both keys:
    - "fingerprint" (legacy) and "sha256" (newer UI usage).
    """
    canonical = canonicalize_scheme(nodes, edges)
    sha256 = fingerprint_scheme(canonical)
    return {
        "algo": "sha256",
        "fingerprint": sha256,
        "sha256": sha256,
        "nodes": len(canonical.get("nodes", [])),
        "edges": len(canonical.get("edges", [])),
        "canonical": canonical,
        "camozzi_codes_sha256": compute_camozzi_codes_sha256(canonical.get("edges", [])),
    }


def load_fingerprint_file(fp_path: str | Path) -> dict:
    p = Path(fp_path)
    return json.loads(p.read_text(encoding="utf-8"))


def _expected_fingerprint(fp_dict: dict) -> str:
    return (fp_dict.get("fingerprint") or fp_dict.get("sha256") or fp_dict.get("hash") or "").strip()


def assert_fingerprint(nodes: Any, edges: Any, expected_fp_path: str | Path) -> bool:
    """Raise AssertionError if fingerprint mismatch."""
    data = load_fingerprint_file(expected_fp_path)
    exp = _expected_fingerprint(data)
    if not exp:
        raise ValueError(f"Fingerprint file '{expected_fp_path}' has no fingerprint/sha256 field")

    canonical = canonicalize_scheme(nodes, edges)
    act = fingerprint_scheme(canonical)

    if act != exp:
        mismatch_path = Path(str(expected_fp_path) + ".mismatch.json")
        try:
            mismatch_path.write_text(
                json.dumps({"expected": exp, "actual": act, "canonical": canonical}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            # never break the assert due to logging
            pass
        raise AssertionError(f"scheme_fingerprint mismatch: expected={exp} actual={act}")

    return True


def _extract_passport_codes(passport: dict) -> set[str]:
    """Collect allowed Camozzi codes from different passport layouts."""
    codes: set[str] = set()

    # Some passports expose precomputed map
    by_code = passport.get("by_code")
    if isinstance(by_code, dict):
        for k in by_code.keys():
            if k:
                codes.add(str(k).strip())

    comps = passport.get("components", [])
    if isinstance(comps, list):
        for c in comps:
            if not isinstance(c, dict):
                continue
            # common: id is the normalized code
            if c.get("id"):
                codes.add(str(c["id"]).strip())
            # flat field
            if c.get("camozzi_код_string"):
                codes.add(str(c["camozzi_код_string"]).strip())
            # nested fields variants seen across versions
            for key in ("fields", "in_code", "code"):
                sub = c.get(key)
                if isinstance(sub, dict) and sub.get("camozzi_код_string"):
                    codes.add(str(sub["camozzi_код_string"]).strip())

    # Drop empties
    return {c for c in codes if c}


def check_camozzi_passport_edges(edges: Any, passport_json_path: str | Path) -> dict:
    passport = json.loads(Path(passport_json_path).read_text(encoding="utf-8"))
    valid_codes = _extract_passport_codes(passport)

    missing: list[str] = []
    for e in _as_list(edges):
        code = _get_attr(e, "camozzi_код", None)
        if code is None or code == "":
            code = _get_attr(e, "camozzi", "")
        if code is None:
            code = ""
        code = str(code).strip()
        if code and code not in valid_codes:
            missing.append(code)

    missing_sorted = sorted(set(missing))
    return {
        "ok": len(missing_sorted) == 0,
        "missing_count": len(missing_sorted),
        "missing_codes": missing_sorted,
        "valid_codes_count": len(valid_codes),
    }


def assert_camozzi_only(edges: Any, passport_json_path: str | Path) -> bool:
    rep = check_camozzi_passport_edges(edges, passport_json_path)
    if rep["ok"]:
        return True

    sample = rep["missing_codes"][:20]
    raise ValueError(
        "Camozzi passport mismatch: missing codes in passport: "
        + ", ".join(sample)
        + (" ..." if rep["missing_count"] > len(sample) else "")
    )


def _load_scheme_nodes_edges(scheme_json_path: str | Path) -> tuple[list[Any], list[Any]]:
    data = json.loads(Path(scheme_json_path).read_text(encoding="utf-8"))

    # Preferred: {"canonical": {"nodes":..., "edges":...}}
    can = data.get("canonical")
    if isinstance(can, dict):
        nodes = can.get("nodes", [])
        edges = can.get("edges", [])
        return _as_list(nodes), _as_list(edges)

    # Alternative: {"nodes":..., "edges":...}
    return _as_list(data.get("nodes", [])), _as_list(data.get("edges", []))


def verify_scheme_integrity(scheme_json_path: str | Path, fingerprint_json_path: str | Path) -> tuple[bool, str]:
    """Return (ok, message) instead of raising — used by self_check."""
    try:
        nodes, edges = _load_scheme_nodes_edges(scheme_json_path)
        fp = compute_fingerprint(nodes, edges)
        expected = load_fingerprint_file(fingerprint_json_path)
        exp = _expected_fingerprint(expected)
        act = fp.get("sha256", "")
        if exp and act == exp:
            return True, f"OK sha256={act}"
        if not exp:
            return False, f"Fingerprint file '{fingerprint_json_path}' missing fingerprint field"
        return False, f"Mismatch expected={exp} actual={act}"
    except Exception as e:
        return False, f"ERROR: {type(e).__name__}: {e}"


def enforce_camozzi_only(scheme_json_path: str | Path, passport_json_path: str | Path | None = None) -> tuple[bool, str]:
    """Return (ok, message) instead of raising — used by self_check."""
    try:
        nodes, edges = _load_scheme_nodes_edges(scheme_json_path)
        if passport_json_path is None:
            passport_json_path = Path(__file__).with_name("component_passport.json")
        assert_camozzi_only(edges, passport_json_path)
        return True, "OK"
    except Exception as e:
        return False, f"ERROR: {type(e).__name__}: {e}"
