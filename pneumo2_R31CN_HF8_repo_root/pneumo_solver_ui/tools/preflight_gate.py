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

import sys
from pathlib import Path
from typing import Callable, Tuple

# Allow direct execution (`python pneumo_solver_ui/tools/preflight_gate.py`)
# in addition to package execution (`python -m pneumo_solver_ui.tools.preflight_gate`).
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    from pathlib import Path as _Path

    _ROOT = _Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

from ..module_loading import load_python_module_from_path


def _canonical_module_name(path: Path, ui_root: Path) -> str:
    path = path.resolve()
    ui_root = ui_root.resolve()
    if path.parent == (ui_root / "tools").resolve():
        return f"pneumo_solver_ui.tools.{path.stem}"
    if path.parent == ui_root:
        return f"pneumo_solver_ui.{path.stem}"
    return path.stem


def _load_module(path: Path, ui_root: Path):
    return load_python_module_from_path(path, _canonical_module_name(path, ui_root))


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
    mod_contracts = _load_module(tools / "param_contract_check.py", root)
    steps.append(("param_contract_check", mod_contracts.main))

    # 2) passport
    mod_passport = _load_module(root / "passport_check.py", root)
    steps.append(("passport_check", mod_passport.main))

    # 3) self_check
    mod_self = _load_module(root / "self_check.py", root)
    steps.append(("self_check", mod_self.main))

    # 3b) contact models consistency (smooth contacts)
    mod_contact = _load_module(tools / "contact_models_property_check.py", root)
    steps.append(("contact_models_property_check", mod_contact.main))

    # 4) invariants
    mod_inv = _load_module(tools / "property_invariants.py", root)
    steps.append(("property_invariants", mod_inv.main))

    # 4b) integrator autotune smoke-check
    mod_integ = _load_module(tools / "integrator_autotune_smoke_check.py", root)
    steps.append(("integrator_autotune_smoke_check", mod_integ.main))

    # 4c) mech energy audit smoke-check (баланс механической энергии + p·dV) (баланс механической энергии + p·dV)
    mod_mech = _load_module(tools / "mech_energy_smoke_check.py", root)
    steps.append(("mech_energy_smoke_check", mod_mech.main))

    # 5) ISO bottlenecks report (не блокирует запуск)
    mod_iso = _load_module(tools / "iso_network_bottleneck_report.py", root)

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
