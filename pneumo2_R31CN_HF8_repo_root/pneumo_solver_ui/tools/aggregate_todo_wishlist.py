"""aggregate_todo_wishlist.py

Builds a consolidated, machine-readable TODO/WISHLIST index across multiple release archives.

Default behaviour: scans a given root folder for files containing TODO/WISHLIST in filename.

Outputs:
  - consolidated_todo_wishlist.json (machine readable)
  - consolidated_todo_wishlist.md   (human friendly)

Usage:
  python -m pneumo_solver_ui.tools.aggregate_todo_wishlist --scan_root /mnt/data/work

"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


TASK_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(\[[ xX]\]\s+)?(.+?)\s*$")


def _iter_candidates(scan_root: Path) -> List[Path]:
    out: List[Path] = []
    for p in scan_root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if "__pycache__" in p.parts:
            continue
        if "todo" in name or "wishlist" in name:
            # skip binaries
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".exe", ".dll", ".so", ".pdf"}:
                continue
            out.append(p)
    return out


def _extract_from_markdown(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for ln in text.splitlines():
        m = TASK_RE.match(ln)
        if not m:
            continue
        checkbox = (m.group(1) or "").strip() or None
        body = (m.group(2) or "").strip()
        if not body:
            continue
        items.append({"text": body, "checkbox": checkbox})
    return items


def _extract_from_json(obj: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, str):
                items.append({"text": x, "checkbox": None})
            elif isinstance(x, dict):
                # best-effort
                t = x.get("text") or x.get("title") or x.get("desc")
                if isinstance(t, str):
                    items.append({"text": t.strip(), "checkbox": None, "raw": x})
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                items.append({"text": f"{k}: {v}", "checkbox": None})
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, str):
                        items.append({"text": f"{k}: {x}", "checkbox": None})
    return items


def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan_root", type=str, required=True)
    ap.add_argument(
        "--out_dir",
        type=str,
        default=str(Path(__file__).resolve().parents[2] / "docs" / "consolidated"),
    )
    args = ap.parse_args()

    scan_root = Path(args.scan_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    files = _iter_candidates(scan_root)

    aggregate: Dict[str, Any] = {
        "schema": "pneumo.todo_wishlist.aggregate.v1",
        "scan_root": str(scan_root),
        "files_scanned": len(files),
        "items": [],
        "dedup": {},
    }

    dedup: Dict[str, Dict[str, Any]] = {}

    for p in sorted(files):
        rel = str(p.relative_to(scan_root))
        try:
            if p.suffix.lower() == ".json":
                obj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                items = _extract_from_json(obj)
            else:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                items = _extract_from_markdown(txt)
        except Exception:
            continue

        for it in items:
            text = it.get("text")
            if not isinstance(text, str):
                continue
            key = _norm(text)
            if not key:
                continue
            entry = dedup.setdefault(
                key,
                {
                    "text": text.strip(),
                    "sources": [],
                    "kind_guess": "todo" if "todo" in rel.lower() else "wishlist" if "wishlist" in rel.lower() else "mixed",
                },
            )
            entry["sources"].append({"file": rel, "checkbox": it.get("checkbox")})

    aggregate["dedup"] = {
        "count": len(dedup),
        "items": sorted(dedup.values(), key=lambda x: (x.get("kind_guess", ""), x.get("text", "")))
    }

    out_json = out_dir / "consolidated_todo_wishlist.json"
    out_json.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")

    # markdown summary (short)
    md_lines = [
        "# Consolidated TODO + WISHLIST (auto-generated)",
        "",
        f"Scan root: `{scan_root}`",
        f"Files scanned: {len(files)}",
        f"Unique items (dedup): {len(dedup)}",
        "",
        "## Items", "",
    ]
    for item in aggregate["dedup"]["items"][:400]:
        # cap to keep the file readable
        srcs = ", ".join(sorted({s["file"] for s in item.get("sources", [])}))
        md_lines.append(f"- **{item.get('kind_guess','mixed')}**: {item.get('text','').strip()}  ")
        md_lines.append(f"  - sources: {srcs}")

    (out_dir / "consolidated_todo_wishlist.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"[OK] wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
