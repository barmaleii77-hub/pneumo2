"""build_donor_diff_inventory.py

Scans a folder of unpacked release archives (donors) and builds a diff inventory
against a chosen base.

This is meant for *AI-driven merges*: the output is a machine-readable index
that can be fed into an integration planner.

Output:
  docs/consolidated/donor_diff_inventory.json

Usage:
  python -m pneumo_solver_ui.tools.build_donor_diff_inventory \
      --base /path/to/base/PneumoApp_v6_80 \
      --scan_root /mnt/data/work

"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


EXCLUDES = [
    "--exclude=__pycache__",
    "--exclude=*.pyc",
    "--exclude=.git",
]


def find_donor_apps(scan_root: Path, app_dir_name: str = "PneumoApp_v6_80") -> List[Path]:
    out: List[Path] = []
    for p in scan_root.rglob(app_dir_name):
        if p.is_dir() and (p / "app.py").exists() and (p / "pneumo_solver_ui").exists():
            out.append(p)
    # De-dup by realpath
    uniq: Dict[str, Path] = {}
    for p in out:
        uniq[str(p.resolve())] = p
    return sorted(uniq.values(), key=lambda x: str(x))


def diff_qr(base: Path, donor: Path) -> Dict[str, Any]:
    cmd = ["diff", "-qr", *EXCLUDES, str(base), str(donor)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")

    only_in: List[Dict[str, Any]] = []
    files_differ: List[Dict[str, Any]] = []

    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("Only in "):
            # Only in X: name
            try:
                rest = ln[len("Only in "):]
                folder, name = rest.split(":", 1)
                only_in.append({"folder": folder.strip(), "name": name.strip()})
            except Exception:
                only_in.append({"raw": ln})
        elif ln.startswith("Files ") and " differ" in ln:
            # Files A and B differ
            try:
                parts = ln.split(" differ")[0]
                _, a, _, b = parts.split(" ", 3)  # naive
            except Exception:
                # safer parse
                try:
                    a = ln.split("Files ", 1)[1].split(" and ", 1)[0]
                    b = ln.split(" and ", 1)[1].split(" differ", 1)[0]
                except Exception:
                    a = ""
                    b = ""
            files_differ.append({"a": a, "b": b})
        else:
            # ignore
            pass

    return {
        "returncode": p.returncode,
        "only_in": only_in,
        "files_differ": files_differ,
        "raw_lines_count": len(out.splitlines()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=str, required=True)
    ap.add_argument("--scan_root", type=str, required=True)
    ap.add_argument(
        "--out",
        type=str,
        default=str(Path(__file__).resolve().parents[2] / "docs" / "consolidated" / "donor_diff_inventory.json"),
    )
    args = ap.parse_args()

    base = Path(args.base).resolve()
    scan_root = Path(args.scan_root).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    donors = find_donor_apps(scan_root)

    inv: Dict[str, Any] = {
        "schema": "pneumo.merge.donor_diff_inventory.v1",
        "base": str(base),
        "scan_root": str(scan_root),
        "donors_found": len(donors),
        "donors": [],
    }

    for donor in donors:
        # Skip if donor is the base itself
        if donor.resolve() == base.resolve():
            continue
        rel = None
        try:
            rel = str(donor.relative_to(scan_root))
        except Exception:
            rel = str(donor)

        diff = diff_qr(base, donor)
        inv["donors"].append(
            {
                "donor_path": str(donor),
                "donor_rel": rel,
                "diff": diff,
            }
        )

    out_path.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
