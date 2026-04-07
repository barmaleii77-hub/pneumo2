from __future__ import annotations

"""Helpers for building a portable Windows-friendly release zip.

Why this module exists:
- recent ad-hoc release zips packed the whole working tree, including runtime
  logs, diagnostics and deep historical doc sources;
- when such an archive is extracted under a long Desktop path, Windows Explorer
  can hit path-length problems even if the zip itself is structurally valid;
- runtime releases do not need tests, caches or previous SEND bundles.

This helper builds a curated runtime archive with a short path budget.
"""

import fnmatch
import json
import zipfile
from pathlib import Path, PureWindowsPath
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple

PORTABLE_TOPLEVEL_NAMES: tuple[str, ...] = (
    ".streamlit",
    "app.py",
    "START_PNEUMO_APP.cmd",
    "START_PNEUMO_APP.py",
    "START_PNEUMO_APP.pyw",
    "START_PNEUMO_APP.vbs",
    "README.md",
    "VERSION.txt",
    "release_tag.json",
    "BUILD_INFO_LATEST.txt",
    "RELEASE_NOTES_LATEST.txt",
    "requirements.txt",
    "00_READ_FIRST__ABSOLUTE_LAW.md",
    "01_PARAMETER_REGISTRY.md",
    "pneumo_solver_ui",
    "pneumo_dist",
)

PORTABLE_DOCS_NAMES: tuple[str, ...] = (
    "11_TODO.md",
    "12_Wishlist.md",
    "WISHLIST.json",
)

DEFAULT_EXCLUDE_DIR_NAMES: tuple[str, ...] = (
    "__pycache__",
    ".pytest_cache",
    "diagnostics_runs",
    "runs",
    "send_bundles",
    "workspace",
    "DOCS_SOURCES",
    "tests",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
)

DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    "*.pyc",
    "*.pyo",
    "*.tmp",
    "*.bak",
    ".DS_Store",
)


def _should_exclude_name(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in DEFAULT_EXCLUDE_PATTERNS)


def _iter_tree(root: Path, *, rel_prefix: str = "") -> Iterator[Tuple[Path, str]]:
    stack = [root]
    while stack:
        cur = stack.pop()
        if cur.is_dir():
            if cur.name in DEFAULT_EXCLUDE_DIR_NAMES:
                continue
            entries = sorted(cur.iterdir(), key=lambda p: p.name, reverse=True)
            for child in entries:
                stack.append(child)
            continue
        if _should_exclude_name(cur.name):
            continue
        rel = f"{rel_prefix}{cur.relative_to(root).as_posix()}" if rel_prefix else cur.relative_to(root).as_posix()
        yield cur, rel


def iter_portable_release_members(project_root: Path, *, extra_files: Sequence[Path | str] | None = None) -> Iterator[Tuple[Path, str]]:
    project_root = Path(project_root).resolve()
    seen: set[str] = set()

    for name in PORTABLE_TOPLEVEL_NAMES:
        p = project_root / name
        if not p.exists():
            continue
        if p.is_file():
            arc = p.relative_to(project_root).as_posix()
            if arc not in seen:
                seen.add(arc)
                yield p, arc
            continue
        if p.name == ".streamlit":
            for src, rel in _iter_tree(p, rel_prefix=f"{p.name}/"):
                arc = rel
                if arc not in seen:
                    seen.add(arc)
                    yield src, arc
            continue
        for src, rel in _iter_tree(p, rel_prefix=f"{p.name}/"):
            arc = rel
            if arc not in seen:
                seen.add(arc)
                yield src, arc

    docs_dir = project_root / "docs"
    if docs_dir.exists():
        for name in PORTABLE_DOCS_NAMES:
            p = docs_dir / name
            if p.exists() and p.is_file():
                arc = p.relative_to(project_root).as_posix()
                if arc not in seen:
                    seen.add(arc)
                    yield p, arc

    for raw in extra_files or ():
        p = Path(raw)
        if not p.is_absolute():
            p = (project_root / p).resolve()
        if not p.exists() or not p.is_file():
            continue
        arc = p.relative_to(project_root).as_posix()
        if arc not in seen and not _should_exclude_name(p.name):
            seen.add(arc)
            yield p, arc


def windows_extract_path_stats(member_names: Iterable[str], *, dest_dir: str) -> Dict[str, object]:
    lengths: List[Tuple[str, int]] = []
    base = PureWindowsPath(dest_dir)
    for name in member_names:
        full = str(base / PureWindowsPath(*Path(name).parts))
        lengths.append((name, len(full)))
    max_len = max((n for _, n in lengths), default=0)
    offenders = sorted([{"path": p, "len": n} for p, n in lengths if n == max_len], key=lambda x: x["path"])
    return {
        "dest_dir": str(base),
        "member_count": len(lengths),
        "max_abs_path_len": int(max_len),
        "worst_paths": offenders[:10],
    }


def build_portable_release_zip(
    project_root: Path,
    out_zip: Path,
    *,
    extra_files: Sequence[Path | str] | None = None,
    compresslevel: int = 6,
) -> Dict[str, object]:
    project_root = Path(project_root).resolve()
    out_zip = Path(out_zip).resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    members = sorted(iter_portable_release_members(project_root, extra_files=extra_files), key=lambda x: x[1])
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=compresslevel) as zf:
        for src, arc in members:
            zf.write(src, arc)

    stats = windows_extract_path_stats([arc for _, arc in members], dest_dir=fr"C:\Users\User\Desktop\{out_zip.stem}")
    manifest = {
        "zip_path": str(out_zip),
        "member_count": len(members),
        "max_abs_path_len_desktop": stats["max_abs_path_len"],
        "worst_paths": stats["worst_paths"],
        "members": [arc for _, arc in members],
    }
    manifest_path = out_zip.with_suffix(out_zip.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


__all__ = [
    "PORTABLE_TOPLEVEL_NAMES",
    "PORTABLE_DOCS_NAMES",
    "DEFAULT_EXCLUDE_DIR_NAMES",
    "DEFAULT_EXCLUDE_PATTERNS",
    "iter_portable_release_members",
    "windows_extract_path_stats",
    "build_portable_release_zip",
]
