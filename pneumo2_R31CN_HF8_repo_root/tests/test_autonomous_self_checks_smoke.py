import json
from pathlib import Path

from pneumo_solver_ui.autonomous_self_checks import preflight_checks
from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as model


def test_autoself_preflight_smoke():
    root = Path(__file__).resolve().parents[1]
    base = json.loads((root / "pneumo_solver_ui" / "default_base.json").read_text("utf-8"))
    # preflight_checks looks for dt in params (simulate passes dt separately)
    base["dt"] = 0.02

    nodes, node_index, edges, B = model.build_network_full(base)
    rep = preflight_checks(model_module=model, params=base, nodes=nodes, edges=edges)

    assert isinstance(rep, dict)
    assert rep.get("stage") == "pre"
    assert "items" in rep
