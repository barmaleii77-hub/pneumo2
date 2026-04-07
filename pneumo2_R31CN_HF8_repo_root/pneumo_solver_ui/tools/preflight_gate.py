# -*- coding: utf-8 -*-
"""Preflight Gate: быстрый набор проверок перед симуляцией/оптимизацией.

Зачем:
- чтобы запуск «не тратил часы» на очевидно некорректной конфигурации
- чтобы ошибки типов/режимов/паспортов/ISO-математики ловились сразу

Покрытие:
1) Контракты параметров (tools/param_contract_check.py)
2) Паспорт компонентов (passport_check.py)
3) Самопроверка модели и ISO-сети (self_check.py)
4) Проверка свойств контактных моделей (tools/contact_models_property_check.py)
5) Быстрые инварианты модели (tools/property_invariants.py)
6) Интегратор: smoke‑check автотюна (tools/integrator_autotune_smoke_check.py)
7) Механо‑энергоаудит: smoke‑check (tools/mech_energy_smoke_check.py)
8) ISO сети: отчёт по bottleneck (tools/iso_network_bottleneck_report.py) — НЕ блокирует релиз


Запуск:
    python tools/preflight_gate.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable, Tuple


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _run_step(label: str, fn: Callable[[], int]) -> Tuple[bool, int]:
    try:
        rc = fn()
        try:
            code = int(rc) if rc is not None else 0
        except Exception:
            # На всякий случай: некоторые шаги могут вернуть bool/str/None.
            code = 0
        ok = (code == 0)
        return ok, code
    except SystemExit as e:
        code = int(getattr(e, "code", 1) or 0)
        return code == 0, code
    except Exception as e:
        print(f"[{label}] EXCEPTION: {e}")
        return False, 1


def main() -> int:
    root = Path(__file__).resolve().parents[1]  # .../pneumo_solver_ui
    # Чтобы локальные модули (model_*, iso6358_system, ...) находились при import.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    tools = root / "tools"

    steps = []

    # 1) contracts
    mod_contracts = _load_module("param_contract_check", tools / "param_contract_check.py")
    steps.append(("param_contract_check", mod_contracts.main))

    # 2) passport
    mod_passport = _load_module("passport_check", root / "passport_check.py")
    steps.append(("passport_check", mod_passport.main))

    # 3) self_check
    mod_self = _load_module("self_check", root / "self_check.py")
    steps.append(("self_check", mod_self.main))

    # 3b) contact models consistency (smooth contacts)
    mod_contact = _load_module("contact_models_property_check", tools / "contact_models_property_check.py")
    steps.append(("contact_models_property_check", mod_contact.main))

    # 4) invariants
    mod_inv = _load_module("property_invariants", tools / "property_invariants.py")
    steps.append(("property_invariants", mod_inv.main))

    # 4b) integrator autotune smoke-check
    mod_integ = _load_module("integrator_autotune_smoke_check", tools / "integrator_autotune_smoke_check.py")
    steps.append(("integrator_autotune_smoke_check", mod_integ.main))

    # 4c) mech energy audit smoke-check (баланс механической энергии + p·dV) (баланс механической энергии + p·dV)
    mod_mech = _load_module("mech_energy_smoke_check", tools / "mech_energy_smoke_check.py")
    steps.append(("mech_energy_smoke_check", mod_mech.main))

    # 5) ISO bottlenecks report (не блокирует запуск)
    mod_iso = _load_module("iso_network_bottleneck_report", tools / "iso_network_bottleneck_report.py")

    print("\n=== PREFLIGHT GATE ===")
    all_ok = True
    for label, fn in steps:
        print(f"\n-- {label} --")
        ok, rc = _run_step(label, fn)
        print(f"{label}: {'OK' if ok else 'FAIL'} (rc={rc})")
        all_ok = all_ok and ok

    # report step
    print("\n-- iso_network_bottleneck_report --")
    ok_iso, rc_iso = _run_step("iso_network_bottleneck_report", mod_iso.main)
    print(f"iso_network_bottleneck_report: {'OK' if ok_iso else 'FAIL'} (rc={rc_iso})")
    if not ok_iso:
        print("(Отчёт не критичен для запуска, но желательно исправить причину.)")

    print("\n=== SUMMARY ===")
    print("STATUS:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
