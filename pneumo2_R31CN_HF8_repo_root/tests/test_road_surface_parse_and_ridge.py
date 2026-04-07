import json
import math

from pneumo_solver_ui.road_surface import make_surface


def test_ridge_cosine_bump_profile_and_grad():
    spec = {
        "type": "ridge_cosine_bump",
        "A": 0.02,
        "angle_deg": 0.0,
        "u0": 1.0,
        "length": 0.5,
    }
    surf = make_surface(spec)

    # before bump
    assert abs(surf.h(0.0, 0.0)) < 1e-12

    # start boundary (u=u0): h≈0, grad≈0
    h_start = surf.h(1.0, 0.0)
    assert abs(h_start) < 1e-12
    gx0, gy0 = surf.grad(1.0, 0.0)
    assert abs(gx0) < 1e-6
    assert abs(gy0) < 1e-6

    # mid bump: h≈A/2 and positive slope along +x
    h_mid = surf.h(1.25, 0.0)
    assert 0.4 * spec["A"] <= h_mid <= 0.6 * spec["A"]
    gmx, gmy = surf.grad(1.25, 0.0)
    assert gmx > 0.0
    assert abs(gmy) < 1e-6

    # end boundary (u=u0+length): h≈A, grad≈0
    h_end = surf.h(1.5, 0.0)
    assert abs(h_end - spec["A"]) < 1e-6
    gx1, gy1 = surf.grad(1.5, 0.0)
    assert abs(gx1) < 1e-6
    assert abs(gy1) < 1e-6


def test_make_surface_parses_json_string():
    spec = {
        "type": "ridge_cosine_bump",
        "A": 0.01,
        "angle_deg": 30.0,
        "u0": 0.0,
        "length": 0.2,
    }
    s = json.dumps(spec, ensure_ascii=False)
    surf = make_surface(s)

    h = surf.h(0.0, 0.0)
    gx, gy = surf.grad(0.0, 0.0)

    assert math.isfinite(h)
    assert math.isfinite(gx)
    assert math.isfinite(gy)
