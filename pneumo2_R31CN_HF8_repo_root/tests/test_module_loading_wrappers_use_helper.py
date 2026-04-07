from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_active_wrappers_use_canonical_module_loading_helper() -> None:
    files = [
        ROOT / "pneumo_solver_ui" / "app.py",
        ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
        ROOT / "pneumo_solver_ui" / "design_advisor.py",
        ROOT / "pneumo_solver_ui" / "root_cause_report.py",
        ROOT / "pneumo_solver_ui" / "self_check.py",
        ROOT / "pneumo_solver_ui" / "uncertainty_advisor.py",
        ROOT / "pneumo_solver_ui" / "generate_scheme_fingerprint.py",
        ROOT / "pneumo_solver_ui" / "pages" / "03_DesignAdvisor.py",
        ROOT / "pneumo_solver_ui" / "pages" / "04_Uncertainty.py",
        ROOT / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py",
        ROOT / "pneumo_solver_ui" / "pneumo_dist" / "eval_core.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "load_python_module_from_path" in text, f"helper missing in {path.name}"

    opt_worker = (ROOT / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py").read_text(encoding="utf-8")
    assert "load_python_module_from_path" in opt_worker
    assert "resolve_project_py_path" in opt_worker

    eval_core = (ROOT / "pneumo_solver_ui" / "pneumo_dist" / "eval_core.py").read_text(encoding="utf-8")
    assert "return load_python_module_from_path(Path(path), module_name)" in eval_core
