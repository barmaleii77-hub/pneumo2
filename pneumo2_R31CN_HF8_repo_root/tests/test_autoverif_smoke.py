# -*- coding: utf-8 -*-

def test_autoverif_nonfinite_penalty():
    from pneumo_solver_ui.verif_autochecks import check_candidate_metrics

    metrics = {
        "roll_max_abs_deg": float('nan'),
        "pitch_max_abs_deg": 1.0,
    }
    params = {
        "enforce_scheme_integrity": True,
        "enforce_camozzi_only": True,
        "autoverif_enable": True,
    }

    out = check_candidate_metrics(metrics, params, test={"name": "t"})
    assert int(out.get("верификация_ok", 0)) == 0
    assert float(out.get("верификация_штраф", 0.0)) >= 1.0
    assert "nonfinite" in str(out.get("верификация_флаги", ""))


def test_autoverif_scheme_lock_required():
    from pneumo_solver_ui.verif_autochecks import check_candidate_metrics

    metrics = {"roll_max_abs_deg": 0.0}
    params = {
        "enforce_scheme_integrity": False,
        "enforce_camozzi_only": False,
        "autoverif_enable": True,
        "autoverif_require_scheme_lock": True,
        "autoverif_penalty_invariant": 123.0,
    }

    out = check_candidate_metrics(metrics, params, test={"name": "t"})
    assert int(out.get("верификация_ok", 1)) == 0
    assert float(out.get("верификация_штраф", 0.0)) >= 123.0
    flags = str(out.get("верификация_флаги", ""))
    assert "scheme_lock_off" in flags
    assert "camozzi_only_off" in flags


def test_autoverif_ok_path():
    from pneumo_solver_ui.verif_autochecks import check_candidate_metrics

    metrics = {
        "roll_max_abs_deg": 0.1,
        "ошибка_энергии_газа_отн": 1e-4,
        "энтропия_смешение_Дж_К": 0.0,
        "mech_selfcheck_ok": 1,
    }
    params = {
        "enforce_scheme_integrity": True,
        "enforce_camozzi_only": True,
        "autoverif_enable": True,
        "autoverif_require_scheme_lock": True,
        "autoverif_energy_err_rel_max": 1e-3,
        "autoverif_entropy_mix_min": -1e-9,
    }

    out = check_candidate_metrics(metrics, params, test={"name": "t"})
    assert int(out.get("верификация_ok", 0)) == 1
    assert float(out.get("верификация_штраф", 1.0)) == 0.0
    assert str(out.get("верификация_флаги", "")) == ""
