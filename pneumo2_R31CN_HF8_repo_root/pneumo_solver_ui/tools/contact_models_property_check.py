# -*- coding: utf-8 -*-
"""
Проверка согласованности "сглаженных" контактных моделей (шина/отбойники) с потенциальной энергией.

Зачем:
- при включённом smooth_contacts мы хотим, чтобы консервативная часть силы была производной от U(x)
- иначе механический энерго‑аудит будет показывать систематическую ошибку, а оптимизатор сможет
  "выигрывать" за счёт нефизики на сглаженных порогах.

Проверяем:
1) В коде модели действительно используется energy-consistent формула для сил:
   F_spring = k * pos(x) * dpos/dx
   при U = 0.5 * k * pos(x)^2

2) Численно: dU/dx ≈ F_spring на диапазоне x (используем 5-точечную схему O(h^4)).

Эта проверка рассчитана на быстрый запуск в Preflight Gate.
"""

from __future__ import annotations

from pathlib import Path
import importlib.util
import re
import numpy as np


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось создать spec для {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _require(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def _pattern_ok(txt: str, pattern: str) -> bool:
    return re.search(pattern, txt, flags=re.MULTILINE) is not None


def main() -> int:
    root = Path(__file__).resolve().parents[1]  # .../pneumo_solver_ui
    model_path = root / "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py"
    if not model_path.exists():
        print(f"!! Не найден файл модели: {model_path}")
        return 2

    txt = model_path.read_text(encoding="utf-8")

    # 1) Структурные проверки
    pat_tire = r"F_tire\s*=\s*\(k_tire\*pen_pos\s*\+\s*c_tire\*pen_dot_pos\)\s*\*\s*g_contact"
    pat_stop = r"F_stop\s*=\s*\(k_stop\*over_pos\s*\+\s*c_stop\*delta_dot_pos\)\s*\*\s*g_over\s*-\s*\(k_stop\*under_pos\s*\+\s*c_stop\*delta_dot_neg\)\s*\*\s*g_under"
    pat_Utire = r"Utire\s*=\s*0\.5\s*\*\s*float\(k_tire\)\s*\*\s*float\(np\.sum\(pen_pos\*\*2\)\)"
    pat_Ustop = r"Ustop\s*=\s*0\.5\s*\*\s*float\(k_stop\)\s*\*\s*float\(np\.sum\(over_pos\*\*2\s*\+\s*under_pos\*\*2\)\)"

    _require(_pattern_ok(txt, pat_tire),
             "В модели не найдена energy-consistent формула F_tire=(k*pen_pos+c*pen_dot_pos)*g_contact")
    _require(_pattern_ok(txt, pat_stop),
             "В модели не найдена energy-consistent формула F_stop=(...)*g_over-(...)*g_under")
    _require(_pattern_ok(txt, pat_Utire),
             "В модели не найдена формула энергии Utire=0.5*k*sum(pen_pos**2) (ожидалась для согласования)")
    _require(_pattern_ok(txt, pat_Ustop),
             "В модели не найдена формула энергии Ustop=0.5*k*sum(over_pos**2+under_pos**2)")

    # 2) Численная проверка производной (через функции smooth_pos/smooth_pos_grad из модели)
    mod = _load_module("model_pneumo_v8_energy_audit_vacuum_patched_smooth_all", model_path)

    _require(hasattr(mod, "smooth_pos") and hasattr(mod, "smooth_pos_grad"),
             "В модуле модели нет функций smooth_pos / smooth_pos_grad")

    smooth_pos = mod.smooth_pos
    smooth_pos_grad = mod.smooth_pos_grad

    k = 12345.0
    eps = 1e-4

    xs = np.linspace(-5e-3, 5e-3, 4001)
    h = float(xs[1] - xs[0])

    pos = smooth_pos(xs, eps)
    grad = smooth_pos_grad(xs, eps)

    U = 0.5 * k * (pos ** 2)
    F = k * pos * grad

    # 5-точечная центральная разность: O(h^4)
    dU = (-U[4:] + 8.0 * U[3:-1] - 8.0 * U[1:-3] + U[:-4]) / (12.0 * h)
    F_mid = F[2:-2]

    abs_err = np.abs(dU - F_mid)
    max_abs = float(np.max(abs_err))

    denom = np.maximum(1e-12, np.abs(F_mid))
    rel_err = abs_err / denom
    max_rel = float(np.max(rel_err))

    abs_tol = 1e-4
    rel_tol = 1e-4
    _require(max_abs < abs_tol,
             f"Проверка dU/dx≈F не прошла по abs: max_abs={max_abs:.3e} >= {abs_tol:.3e}")
    _require(max_rel < rel_tol,
             f"Проверка dU/dx≈F не прошла по rel: max_rel={max_rel:.3e} >= {rel_tol:.3e}")

    print("OK: contact_models_property_check")
    print(f"  max_abs(dU/dx vs F) = {max_abs:.3e} (tol={abs_tol:.3e})")
    print(f"  max_rel(dU/dx vs F) = {max_rel:.3e} (tol={rel_tol:.3e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
