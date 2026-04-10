from __future__ import annotations

import math

from pneumo_solver_ui.model_pneumo_v9_doublewishbone_camozzi import build_network_full as build_camozzi_network
from pneumo_solver_ui.model_pneumo_v9_mech_doublewishbone_worldroad import build_network_full as build_worldroad_network


def _assert_builder_uses_chamber_specific_dead_volumes(builder) -> None:
    cyl1_cap_len = 0.010
    cyl1_rod_len = 0.016
    cyl2_cap_len = 0.007
    cyl2_rod_len = 0.011

    params = {
        "dead_volume_chamber_m3": 1e-6,
        "cyl1_dead_cap_length_m": cyl1_cap_len,
        "cyl1_dead_rod_length_m": cyl1_rod_len,
        "cyl2_dead_cap_length_m": cyl2_cap_len,
        "cyl2_dead_rod_length_m": cyl2_rod_len,
    }

    nodes, _node_index, _edges, _B = builder(params)
    nodes_by_name = {node.name: node for node in nodes}

    c1_cap_area = math.pi * (0.032 * 0.5) ** 2
    c1_rod_area = c1_cap_area - math.pi * (0.016 * 0.5) ** 2
    c2_cap_area = math.pi * (0.050 * 0.5) ** 2
    c2_rod_area = c2_cap_area - math.pi * (0.014 * 0.5) ** 2

    assert math.isclose(nodes_by_name["Ц1_ЛП_БП"].V0, c1_cap_area * cyl1_cap_len, rel_tol=1e-12)
    assert math.isclose(nodes_by_name["Ц1_ЛП_ШП"].V0, c1_rod_area * cyl1_rod_len, rel_tol=1e-12)
    assert math.isclose(nodes_by_name["Ц2_ЛП_БП"].V0, c2_cap_area * cyl2_cap_len, rel_tol=1e-12)
    assert math.isclose(nodes_by_name["Ц2_ЛП_ШП"].V0, c2_rod_area * cyl2_rod_len, rel_tol=1e-12)
    assert nodes_by_name["Ц1_ЛП_БП"].V0 != nodes_by_name["Ц1_ЛП_ШП"].V0
    assert nodes_by_name["Ц2_ЛП_БП"].V0 != nodes_by_name["Ц2_ЛП_ШП"].V0


def test_worldroad_build_network_uses_chamber_specific_dead_volumes() -> None:
    _assert_builder_uses_chamber_specific_dead_volumes(build_worldroad_network)


def test_camozzi_build_network_uses_chamber_specific_dead_volumes() -> None:
    _assert_builder_uses_chamber_specific_dead_volumes(build_camozzi_network)
