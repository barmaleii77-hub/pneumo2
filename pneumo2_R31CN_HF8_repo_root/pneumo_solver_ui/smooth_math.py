# -*- coding: utf-8 -*-
"""pneumo_solver_ui.smooth_math

Мини-библиотека «гладких» (дифференцируемых) аппроксимаций.

Зачем:
- убрать разрывы производных из piecewise-логики (if/clip/max/min),
- подготовить RHS динамики к автодиффу (JAX/PyTorch/CasADi),
- сделать оптимизацию параметров стабильнее (особенно градиентную).

Принципы:
- используем tanh-based sigmoid (устойчиво при больших |x|);
- eps всегда в тех же единицах, что аргумент x;
- функции должны работать и со скалярами, и с numpy-массивами.

Важно:
- Этот модуль не навязывает использование «smooth»-режима.
  В моделях smooth включается флагами в params.
"""

from __future__ import annotations

from typing import Union

import numpy as np

ArrayLike = Union[float, np.ndarray]


def sigmoid(x: ArrayLike) -> ArrayLike:
    """Сигмоида 0..1 через tanh: σ(x)=0.5*(1+tanh(x/2))."""
    return 0.5 * (1.0 + np.tanh(0.5 * x))


def softplus(x: ArrayLike, beta: float = 1.0) -> ArrayLike:
    """Гладкий аналог max(0,x): softplus(x)=log(1+exp(beta*x))/beta.

    Реализовано через logaddexp для устойчивости.
    """
    beta = float(beta)
    if beta <= 0.0:
        beta = 1.0
    return np.logaddexp(0.0, beta * x) / beta


def smooth_abs(x: ArrayLike, eps: float) -> ArrayLike:
    """Гладкий |x| ≈ sqrt(x^2 + eps^2)."""
    eps = max(1e-30, float(eps))
    return np.sqrt(x * x + eps * eps)


def smooth_pos(x: ArrayLike, eps: float) -> ArrayLike:
    """Гладкий max(0,x): 0.5*(x + sqrt(x^2+eps^2))."""
    return 0.5 * (x + smooth_abs(x, eps))


def smooth_min(x: ArrayLike, hi: float, eps: float) -> ArrayLike:
    """Гладкий min(x, hi)."""
    return hi - smooth_pos(hi - x, eps)


def smooth_max(x: ArrayLike, lo: float, eps: float) -> ArrayLike:
    """Гладкий max(x, lo)."""
    return lo + smooth_pos(x - lo, eps)


def smooth_clip(x: ArrayLike, lo: float, hi: float, eps: float) -> ArrayLike:
    """Гладкий clip(x, lo, hi)."""
    return smooth_min(smooth_max(x, lo, eps), hi, eps)


def smooth_sign(x: ArrayLike, k: float = 1.0) -> ArrayLike:
    """Гладкий знак: tanh(k*x). k задаёт «резкость»."""
    k = float(k)
    if k <= 0.0:
        # fallback: жесткий знак
        return np.sign(x)
    return np.tanh(k * x)


def blend(a: ArrayLike, b: ArrayLike, w01: ArrayLike) -> ArrayLike:
    """Смешивание a->b по весу w в [0..1]."""
    return (1.0 - w01) * a + w01 * b
