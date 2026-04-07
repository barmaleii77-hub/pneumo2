"""Механо‑энергоаудит: быстрый smoke‑тест.

Цель:
  • поймать грубые ошибки знаков/мэппинга (баланс энергии механики «разъезжается»);
  • проверить эквивалентность p·dV (калибр, т.е. gauge) и Σ(F_газ_шток · ṡ).

Запуск:
    python -m pneumo_solver_ui.tools.mech_energy_smoke_check
или через:
    python -m pneumo_solver_ui.tools.preflight_gate

Примечание:
  Начиная с ветки v6.xx в проекте «suite» хранится в default_suite.json, а не в отдельном
  python-модуле. Поэтому smoke‑тест намеренно не импортирует pneumo_solver_ui.suite.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

import numpy as np


def _project_root() -> Path:
    # .../pneumo_solver_ui/tools/mech_energy_smoke_check.py -> .../pneumo_solver_ui
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _test_name(t: dict) -> str:
    return str(t.get("имя") or t.get("name") or t.get("тип") or t.get("type") or "<unnamed>")


def _is_enabled(t: dict) -> bool:
    if "включен" in t:
        return bool(t.get("включен"))
    if "enabled" in t:
        return bool(t.get("enabled"))
    # по умолчанию считаем включенным
    return True


def _normalize_test_keys(t: dict) -> dict:
    tt = dict(t)
    if "тип" not in tt and "type" in tt:
        tt["тип"] = tt["type"]
    if "имя" not in tt and "name" in tt:
        tt["имя"] = tt["name"]
    return tt


def _pick_smoke_tests(suite: list[dict]) -> list[dict]:
    """Выбираем 1–2 теста: (дорога) + (ax/тангаж), чтобы покрыть ключевые источники энергии."""
    enabled = [_normalize_test_keys(t) for t in suite if isinstance(t, dict) and _is_enabled(t)]
    if not enabled:
        return [{}]

    road_like = {"кочка_одно_колесо", "кочка_диагональ", "кочка_ось", "микро_синфаза", "микро_разнофаза"}

    def find(pred):
        for x in enabled:
            if pred(x):
                return x
        return None

    t_road = find(lambda x: str(x.get("тип", "")) in road_like)
    t_ax = find(lambda x: (str(x.get("тип", "")) == "инерция_тангаж") or ("ax" in x))

    tests: list[dict] = []
    if t_road is not None:
        tests.append(t_road)
    if t_ax is not None and (t_ax is not t_road):
        tests.append(t_ax)

    if not tests:
        tests = [enabled[0]]

    return tests


def _import_model(module_name: str):
    root = _project_root()
    # гарантируем, что pneumo_solver_ui виден
    if str(root.parent) not in sys.path:
        sys.path.insert(0, str(root.parent))

    name = module_name.strip()
    if not name:
        raise ValueError("Empty module name")

    # Разрешаем короткие имена без префикса
    if not name.startswith("pneumo_solver_ui."):
        name = f"pneumo_solver_ui.{name}"

    return importlib.import_module(name)


def _metrics_from_df(df_main):
    required = [
        "ошибка_энергии_мех_Дж",
        "ошибка_энергии_мех_отн",
        "ошибка_мощности_p_dV_Вт",
    ]
    missing = [c for c in required if c not in df_main.columns]
    if missing:
        return {"ok": False, "missing": missing}

    err_abs = df_main["ошибка_энергии_мех_Дж"].astype(float).to_numpy()
    err_rel = df_main["ошибка_энергии_мех_отн"].astype(float).to_numpy()
    pdv_err = df_main["ошибка_мощности_p_dV_Вт"].astype(float).to_numpy()

    max_abs = float(np.nanmax(np.abs(err_abs))) if len(err_abs) else 0.0
    max_rel = float(np.nanmax(np.abs(err_rel))) if len(err_rel) else 0.0
    end_rel = float(err_rel[-1]) if len(err_rel) else 0.0
    max_pdv = float(np.nanmax(np.abs(pdv_err))) if len(pdv_err) else 0.0

    # Мягкие пороги: smoke‑check, а не строгая верификация.
    TH_REL = 0.25
    TH_PDV = 5e-3  # Вт, почти машинный ноль (должно быть ~0)

    ok = True
    if not np.isfinite(max_rel) or max_rel > TH_REL:
        ok = False
    if not np.isfinite(end_rel) or abs(end_rel) > TH_REL:
        ok = False
    if not np.isfinite(max_pdv) or max_pdv > TH_PDV:
        ok = False

    return {
        "ok": ok,
        "max_rel": max_rel,
        "end_rel": end_rel,
        "max_abs_J": max_abs,
        "max_pdv_W": max_pdv,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--models",
        default=os.environ.get(
            "MECH_ENERGY_MODELS",
            "model_pneumo_v9_mech_doublewishbone_worldroad,model_pneumo_v8_energy_audit_vacuum_patched_smooth_all",
        ),
        help="Comma-separated list of model modules (with or without 'pneumo_solver_ui.' prefix)",
    )
    ap.add_argument(
        "--t_end_max",
        type=float,
        default=float(os.environ.get("MECH_ENERGY_T_END_MAX", "1.2")),
        help="Limit t_end for smoke speed",
    )
    args = ap.parse_args(argv)

    root = _project_root()
    base_params_path = root / "default_base.json"
    suite_path = root / "default_suite.json"

    params = _load_json(base_params_path)
    suite = _load_json(suite_path)
    suite_list = suite if isinstance(suite, list) else []
    tests = _pick_smoke_tests(suite_list)

    model_names = [m.strip() for m in str(args.models).split(",") if m.strip()]
    if not model_names:
        print("[mech_energy_smoke_check] FAIL: empty models list")
        raise SystemExit(2)

    any_fail = False

    for mn in model_names:
        try:
            model = _import_model(mn)
        except Exception as e:  # noqa: BLE001
            any_fail = True
            print(f"[smoke] FAIL import model='{mn}': {e}")
            continue

        print(f"[smoke] model={mn}")

        for t in tests:
            test = dict(t) if isinstance(t, dict) else {}
            # ограничиваем длительность
            t_end = float(test.get("t_end", 1.2))
            test["t_end"] = min(t_end, float(args.t_end_max))

            # Важно: simulate() в моделях умеет подхватить dt/t_end как аргументы или из test.
            dt = float(test.get("dt", 0.003))

            try:
                df_main, *_ = model.simulate(params, test, dt=dt, t_end=float(test["t_end"]), record_full=False)
            except TypeError:
                # На случай модели без явных dt/t_end параметров
                df_main, *_ = model.simulate(params, test, record_full=False)
            except Exception as e:  # noqa: BLE001
                any_fail = True
                print(f"[smoke] FAIL simulate model='{mn}' test='{_test_name(test)}': {e}")
                continue

            met = _metrics_from_df(df_main)
            if not met.get("ok"):
                any_fail = True
                if "missing" in met:
                    print(f"[smoke] FAIL missing columns in df_main: {met['missing']}")
                else:
                    print("[smoke] FAIL: metrics out of bounds")

            print(
                f"[smoke] test='{_test_name(test)}' "
                f"max_rel={met.get('max_rel', float('nan')):.3g} "
                f"end_rel={met.get('end_rel', float('nan')):.3g} "
                f"max_abs_J={met.get('max_abs_J', float('nan')):.3g} "
                f"max_pdv_W={met.get('max_pdv_W', float('nan')):.3g}"
            )

    if any_fail:
        print("[mech_energy_smoke_check] FAIL")
        raise SystemExit(2)

    print("[mech_energy_smoke_check] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
