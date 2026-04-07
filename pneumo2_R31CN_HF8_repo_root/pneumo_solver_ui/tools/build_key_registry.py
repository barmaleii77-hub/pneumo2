"""build_key_registry.py

Static scanner that builds a machine-readable index of:
  - environment variables
  - streamlit session_state keys

The goal is to keep ONE shared registry/contract across modules.

Output:
  pneumo_solver_ui/contracts/generated/key_usage_index.json
  pneumo_solver_ui/contracts/generated/keys_registry.yaml

Usage:
  python -m pneumo_solver_ui.tools.build_key_registry --root PneumoApp_v6_80

"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


@dataclass
class KeyUse:
    kind: str  # 'env' | 'session'
    key: str
    file: str
    line: int
    col: int
    context: str


ENV_FUNC_NAMES = {"getenv"}
ENV_GET_ATTR = {"get"}


def _iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _safe_get_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def scan_file(py: Path) -> List[KeyUse]:
    src = py.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    uses: List[KeyUse] = []

    class V(ast.NodeVisitor):
        def visit_Subscript(self, node: ast.Subscript):
            # st.session_state["key"]
            try:
                if isinstance(node.value, ast.Attribute) and node.value.attr == "session_state":
                    # st.session_state
                    if isinstance(node.value.value, ast.Name) and node.value.value.id in {"st", "streamlit"}:
                        key = _safe_get_str(node.slice) if isinstance(node.slice, ast.AST) else None
                        if key:
                            uses.append(
                                KeyUse(
                                    kind="session",
                                    key=key,
                                    file=str(py),
                                    line=getattr(node, "lineno", 0),
                                    col=getattr(node, "col_offset", 0),
                                    context="st.session_state[...]",
                                )
                            )
            except Exception:
                pass
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call):
            # os.environ.get("KEY") / os.getenv("KEY") / st.session_state.get("KEY")
            try:
                # os.getenv("KEY")
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    base = node.func.value.id
                    attr = node.func.attr
                    if base == "os" and attr in ENV_FUNC_NAMES and node.args:
                        key = _safe_get_str(node.args[0])
                        if key:
                            uses.append(
                                KeyUse(
                                    kind="env",
                                    key=key,
                                    file=str(py),
                                    line=getattr(node, "lineno", 0),
                                    col=getattr(node, "col_offset", 0),
                                    context=f"os.{attr}(...)" ,
                                )
                            )

                # os.environ.get("KEY")
                if isinstance(node.func, ast.Attribute) and node.func.attr in ENV_GET_ATTR:
                    # something.get(...)
                    if isinstance(node.func.value, ast.Attribute) and isinstance(node.func.value.value, ast.Name):
                        if node.func.value.value.id == "os" and node.func.value.attr == "environ" and node.args:
                            key = _safe_get_str(node.args[0])
                            if key:
                                uses.append(
                                    KeyUse(
                                        kind="env",
                                        key=key,
                                        file=str(py),
                                        line=getattr(node, "lineno", 0),
                                        col=getattr(node, "col_offset", 0),
                                        context="os.environ.get(...)" ,
                                    )
                                )

                # st.session_state.get("KEY")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                    if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "session_state":
                        if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id in {"st", "streamlit"}:
                            if node.args:
                                key = _safe_get_str(node.args[0])
                                if key:
                                    uses.append(
                                        KeyUse(
                                            kind="session",
                                            key=key,
                                            file=str(py),
                                            line=getattr(node, "lineno", 0),
                                            col=getattr(node, "col_offset", 0),
                                            context="st.session_state.get(...)" ,
                                        )
                                    )
            except Exception:
                pass

            self.generic_visit(node)

    V().visit(tree)
    return uses


def build_registry(root: Path) -> Tuple[List[KeyUse], Dict[str, Any]]:
    all_uses: List[KeyUse] = []
    for py in _iter_py_files(root):
        all_uses.extend(scan_file(py))

    # Unique sets
    env_keys: Set[str] = {u.key for u in all_uses if u.kind == "env"}
    sess_keys: Set[str] = {u.key for u in all_uses if u.kind == "session"}

    # Minimal annotations for the most critical keys
    known_env: Dict[str, Dict[str, Any]] = {
        "PNEUMO_OPT_PROBLEM_HASH_MODE": {
            "default": "stable",
            "type": "enum[stable,legacy]",
            "owner": "optimization",
            "desc": "Режим вычисления problem_hash для distributed optimization (stable=контентный, legacy=совместимость).",
        },
        "PNEUMO_ISO6358_RHO_ANR_MODE": {
            "default": "norm",
            "type": "enum[norm,calc]",
            "owner": "pneumatics.iso6358",
            "desc": "Выбор ρ_ANR: norm=1.185 (ISO 8778), calc=p_ANR/(R*T_ANR).",
        },
    }

    env_entries: Dict[str, Any] = {}
    for k in sorted(env_keys):
        env_entries[k] = known_env.get(k, {"default": None, "type": None, "owner": None, "desc": None})

    registry = {
        "schema": "pneumo.contracts.keys_registry.v1",
        "env_vars": env_entries,
        "session_state_keys": sorted(sess_keys),
    }
    return all_uses, registry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--out_dir", type=str, default=str(Path(__file__).resolve().parents[1] / "contracts" / "generated"))
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    uses, registry = build_registry(root)

    (out_dir / "key_usage_index.json").write_text(
        json.dumps([u.__dict__ for u in uses], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if yaml is not None:
        (out_dir / "keys_registry.yaml").write_text(
            yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    else:
        (out_dir / "keys_registry.yaml").write_text(
            "# YAML support not available. Use key_usage_index.json instead.\n" + json.dumps(registry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"[OK] wrote {out_dir}/key_usage_index.json")
    print(f"[OK] wrote {out_dir}/keys_registry.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
