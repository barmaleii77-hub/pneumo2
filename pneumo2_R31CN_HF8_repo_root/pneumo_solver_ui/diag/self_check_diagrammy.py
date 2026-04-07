"""Quick self-checks for the Streamlit UI bundle.

This module is intentionally lightweight:

* no network access
* no heavy simulations
* mostly file existence checks and basic imports

It is used by the Streamlit section "Инструменты".
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class _Check:
    name: str
    ok: bool
    details: str = ""


def _try_import(modname: str) -> Tuple[bool, str]:
    try:
        __import__(modname)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _exists(p: Path) -> Tuple[bool, str]:
    try:
        if p.exists():
            size = p.stat().st_size
            return True, f"ok ({size} bytes)"
        return False, "missing"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run_self_checks(repo_root: Path | str, quick: bool = True) -> Dict[str, Any]:
    """Run self-checks.

    Args:
        repo_root: path to the `pneumo_solver_ui/` folder.
        quick: keep checks lightweight.

    Returns:
        dict report with keys: ok, errors, warnings, checks, info.
    """

    rr = Path(repo_root).resolve()

    # Ensure imports work even when executed directly (python .../self_check_diagrammy.py)
    try:
        import sys

        if str(rr) not in sys.path:
            sys.path.insert(0, str(rr))
    except Exception:
        pass
    t0 = datetime.now().isoformat(timespec="seconds")

    errors: List[str] = []
    warnings: List[str] = []
    checks: List[_Check] = []

    # --- Basic environment ---
    pyver = sys.version.split()[0]
    checks.append(_Check("python_version", True, pyver))
    checks.append(_Check("platform", True, f"{platform.system()} {platform.release()}"))

    # --- Required imports (for the Streamlit UI) ---
    required_imports = ["numpy", "pandas", "streamlit"]
    optional_imports = ["plotly", "scipy"]

    for m in required_imports:
        ok, det = _try_import(m)
        checks.append(_Check(f"import:{m}", ok, det))
        if not ok:
            errors.append(f"Не установлен модуль '{m}' ({det}).")

    for m in optional_imports:
        ok, det = _try_import(m)
        checks.append(_Check(f"import(optional):{m}", ok, det))
        if not ok:
            warnings.append(f"Опциональный модуль '{m}' не найден ({det}).")

    # --- Key files under repo_root ---
    key_files = [
        rr / "pneumo_ui_app.py",
        rr / "default_base.json",
        rr / "default_suite.json",
        rr / "compare_npz_web.py",
        rr / "qt_compare_viewer.py",
        rr / "compare_influence_time.py",
        rr / "diag" / "qa_suspicious_signals.py",
        rr / "diag" / "event_markers.py",
    ]
    for p in key_files:
        ok, det = _exists(p)
        checks.append(_Check(f"file:{p.name}", ok, det))
        if not ok:
            errors.append(f"Отсутствует файл: {p} ({det}).")

    # --- Smoke test: discrete events ---
    try:
        from pneumo_solver_ui.diag.event_markers import scan_run_tables, events_to_frame
        import pandas as pd

        df = pd.DataFrame({"t": [0.0, 0.5, 1.0, 1.5], "valve_open": [0, 0, 1, 1]})
        evs = scan_run_tables({"main": df}, rising_only=True)
        ev_df = events_to_frame(evs)
        ok = (len(ev_df) == 1)
        det = f"events={len(ev_df)}"
        checks.append(_Check("event_markers:basic", ok, det))
        if not ok:
            errors.append(f"event_markers: ожидалось 1 событие, получено {len(ev_df)}")
    except Exception as e:
        checks.append(_Check("event_markers:basic", False, str(e)))
        errors.append(f"event_markers smoke test failed: {e}")

    # --- Smoke test: ev_detect_discrete_signals helper (used by 3D 'pebbles') ---
    try:
        import pandas as pd
        from pneumo_solver_ui.compare_npz_web import ev_detect_discrete_signals

        df = pd.DataFrame({"t": [0.0, 0.5, 1.0, 1.5], "valve_open": [0, 0, 1, 1], "mode": [1, 1, 1, 2]})
        sigs = ev_detect_discrete_signals(df, top_k=10)
        ok = isinstance(sigs, list)
        det = f"n={len(sigs)}"
        checks.append(_Check("compare_npz_web:ev_detect_discrete_signals", ok, det))
        if not ok:
            errors.append("compare_npz_web: ev_detect_discrete_signals должен возвращать list")
    except Exception as e:
        checks.append(_Check("compare_npz_web:ev_detect_discrete_signals", False, str(e)))
        errors.append(f"compare_npz_web ev_detect_discrete_signals smoke test failed: {e}")

    # --- Streamlit custom components assets ---
    comp_root = rr / "components"
    ok, det = _exists(comp_root)
    checks.append(_Check("dir:components", ok, det))
    if not ok:
        errors.append(f"Нет папки компонентов: {comp_root}")
    else:
        expected_components = ["mech_anim", "mech_car3d", "pneumo_svg_flow"]
        for c in expected_components:
            idx = comp_root / c / "index.html"
            ok_i, det_i = _exists(idx)
            checks.append(_Check(f"component:{c}", ok_i, det_i))
            if not ok_i:
                errors.append(f"Нет frontend файла компонента: {idx} ({det_i}).")

    # --- Desktop animator (optional) ---
    da_root = rr / "desktop_animator"
    if da_root.exists():
        ok_app, det_app = _exists(da_root / "app.py")
        checks.append(_Check("desktop_animator:app.py", ok_app, det_app))
        ok_main, det_main = _exists(da_root / "main.py")
        checks.append(_Check("desktop_animator:main.py", ok_main, det_main))

        # Import checks are optional (PyQt/OpenGL can be unavailable)
        ok_qt, det_qt = _try_import("PyQt5")
        checks.append(_Check("import(optional):PyQt5", ok_qt, det_qt))
        if not ok_qt:
            warnings.append(
                "PyQt5 не найден — Desktop Animator может не запуститься (это не мешает Streamlit UI)."
            )
    else:
        warnings.append("Папка desktop_animator не найдена (если вы её ожидали, проверьте архив).")

    # --- Top-level helpers (one level up) ---
    top = rr.parent
    for p in [top / "INSTALL_WINDOWS_SAFE.cmd", top / "START_PNEUMO_APP.cmd"]:
        ok_p, det_p = _exists(p)
        checks.append(_Check(f"top:{p.name}", ok_p, det_p))
        if not ok_p:
            warnings.append(f"Не найден стартовый файл: {p} ({det_p}).")

    ok_all = len(errors) == 0

    report: Dict[str, Any] = {
        "ok": ok_all,
        "ts": t0,
        "repo_root": str(rr),
        "python": pyver,
        "platform": f"{platform.system()} {platform.release()}",
        "errors": errors,
        "warnings": warnings,
        "checks": [c.__dict__ for c in checks],
        "note": "quick" if quick else "full",
    }
    return report


def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Pneumo UI quick self-check")
    # default root = PneumoApp_v6_80 (two levels up from .../pneumo_solver_ui/diag/*.py)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    rep = run_self_checks(Path(args.root), quick=(not args.full))
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(_main())
