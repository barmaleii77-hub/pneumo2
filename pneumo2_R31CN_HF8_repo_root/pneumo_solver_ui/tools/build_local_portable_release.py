from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from pneumo_solver_ui.release_info import get_release_tag
from pneumo_solver_ui.release_packaging import build_portable_release_tree, build_portable_release_zip


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_root(project_root: Path) -> Path:
    return project_root.parent


def _release_label(project_root: Path) -> str:
    release_tag_path = project_root / "release_tag.json"
    release_text = get_release_tag()
    try:
        payload = json.loads(release_tag_path.read_text(encoding="utf-8"))
        release_text = str(payload.get("release") or release_text).strip() or release_text
    except Exception:
        pass
    parts = [part for part in release_text.split("_") if part]
    if len(parts) > 1 and re.fullmatch(r"R\d+", parts[0]):
        return "_".join(parts[1:])
    return release_text


def _default_release_name(project_root: Path) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    return f"PneumoApp_{_release_label(project_root)}_portable_{stamp}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local portable release tree and zip under local_portable_release/")
    parser.add_argument("--project-root", default=str(_project_root()), help="Path to the app project root")
    parser.add_argument("--out-root", default=None, help="Output directory root; defaults to <git-root>/local_portable_release")
    parser.add_argument("--name", default=None, help="Portable release folder/zip stem")
    parser.add_argument("--no-zip", action="store_true", help="Only build the release folder, skip zip creation")
    parser.add_argument("--print-json", action="store_true", help="Print machine-readable JSON summary")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve() if args.out_root else (_git_root(project_root) / "local_portable_release")
    name = args.name or _default_release_name(project_root)

    out_root.mkdir(parents=True, exist_ok=True)
    release_dir = out_root / name
    tree_manifest = build_portable_release_tree(project_root, release_dir, clean=True)

    result: dict[str, object] = {
        "project_root": str(project_root),
        "out_root": str(out_root),
        "release_dir": str(release_dir),
        "tree_member_count": tree_manifest.get("member_count"),
        "tree_manifest_path": str(release_dir / "portable_release_manifest.json"),
    }

    if not args.no_zip:
        zip_path = out_root / f"{name}.zip"
        zip_manifest = build_portable_release_zip(project_root, zip_path)
        result.update(
            {
                "zip_path": str(zip_path),
                "zip_member_count": zip_manifest.get("member_count"),
                "zip_manifest_path": str(zip_path.with_suffix(zip_path.suffix + ".manifest.json")),
                "zip_max_abs_path_len_desktop": zip_manifest.get("max_abs_path_len_desktop"),
            }
        )

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Portable folder: {release_dir}")
        if not args.no_zip:
            print(f"Portable zip: {result['zip_path']}")
            print(f"Zip manifest: {result['zip_manifest_path']}")


if __name__ == "__main__":
    main()
