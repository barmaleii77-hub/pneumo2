# -*- coding: utf-8 -*-
"""iso_fit_demo.py

Демонстрация фита параметров ISO 6358 (b,m) на синтетических данных.

Запуск:
    python iso_fit_demo.py

Сценарий:
- создаём «истинные» b_true, m_true;
- генерируем набор pressure ratio pr;
- строим ratio=φ(pr) + небольшой шум;
- подбираем b,m через iso6358_fit.fit_b_m_from_ratio.

Назначение:
- проверка, что фиттер работает и возвращает разумные b,m;
- пример того, как кормить ему экспериментальные точки (после нормировки).
"""

from __future__ import annotations

import numpy as np

import iso6358_core as model
from iso6358_fit import fit_b_m_from_ratio


def main() -> int:
    rng = np.random.default_rng(42)

    b_true = 0.42
    m_true = 0.65
    beta_lam = model.ISO6358_BETA_LAM_DEFAULT

    pr = np.linspace(0.15, 0.98, 60)
    ratio_clean = np.array([model.iso6358_phi(float(x), b_true, m=m_true, beta_lam=beta_lam) for x in pr])

    noise = rng.normal(0.0, 0.01, size=ratio_clean.shape)
    ratio_noisy = np.clip(ratio_clean + noise, 0.0, 1.0)

    res = fit_b_m_from_ratio(pr, ratio_noisy, beta_lam=beta_lam)

    print("ISO 6358 fit demo (synthetic)")
    print(f"true:  b={b_true:.4f}  m={m_true:.4f}")
    print(f"fit:   b={res.b:.4f}  m={res.m:.4f}   rmse={res.rmse:.5f}  n={res.n}")

    # небольшая sanity-проверка
    if abs(res.b - b_true) > 0.05:
        print("WARNING: b отличается заметно — возможно слишком большой шум или мало точек")
    if abs(res.m - m_true) > 0.20:
        print("WARNING: m отличается заметно — возможно слишком большой шум или мало точек")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
