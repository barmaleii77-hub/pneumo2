# -*- coding: utf-8 -*-
"""ui_overview_viz.py

Набор helper-функций для **человеко-ориентированной** визуализации результатов.

Почему отдельный модуль:
- UI-логика (Streamlit) и визуализация (Plotly) не должны разрастаться в одном файле.
- Эти функции не зависят от Streamlit и могут переиспользоваться в разных страницах.

Фокус:
- теплокарта "тест × метрика" (быстро увидеть проблемные тесты)
- теплокарта "серия × время" (давления/открытия/потоки)
- анимированная теплокарта 2×2 по углам (ЛП/ПП/ЛЗ/ПЗ) — работает в браузере (Plotly frames)

Модуль старается быть устойчивым:
- если plotly не установлен — возвращает None
- если нет нужных колонок — возвращает None
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import math

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go  # type: ignore
except Exception:  # pragma: no cover
    go = None  # type: ignore


CORNERS = ["ЛП", "ПП", "ЛЗ", "ПЗ"]


def _finite_minmax(a: np.ndarray) -> Tuple[float, float]:
    a = np.asarray(a, dtype=float)
    m = np.isfinite(a)
    if not np.any(m):
        return 0.0, 1.0
    v = a[m]
    return float(np.nanmin(v)), float(np.nanmax(v))


def _robust_minmax(a: np.ndarray, q: Tuple[float, float] = (5.0, 95.0)) -> Tuple[float, float]:
    """Robust min/max по перцентилям (по умолчанию 5–95%), чтобы выбросы не портили шкалу."""
    a = np.asarray(a, dtype=float)
    m = np.isfinite(a)
    if not np.any(m):
        return 0.0, 1.0
    v = a[m]
    lo = float(np.nanpercentile(v, q[0]))
    hi = float(np.nanpercentile(v, q[1]))
    if not math.isfinite(lo) or not math.isfinite(hi) or abs(hi - lo) < 1e-12:
        return _finite_minmax(v)
    return lo, hi


def make_test_metric_heatmap(
    df: pd.DataFrame,
    test_col: str,
    metric_cols: Sequence[str],
    *,
    title: str = "Теплокарта метрик по тестам",
    robust: bool = True,
    max_tests: int = 80,
) -> "go.Figure | None":
    """Теплокарта: строки = тесты, столбцы = метрики.

    Чтобы разные единицы не «убивали» визуализацию, значения по каждой метрике
    приводятся к [0..1] (robust min-max по перцентилям).

    В hover показываем и нормированное, и исходное значение.
    """
    if go is None:
        return None
    if df is None or df.empty:
        return None
    if test_col not in df.columns:
        return None

    # ограничим количество тестов на экране по умолчанию (остальное видно в таблице)
    view = df.copy()
    tests = [str(x) for x in view[test_col].tolist()]
    if len(tests) > int(max_tests):
        view = view.iloc[: int(max_tests)].reset_index(drop=True)
        tests = [str(x) for x in view[test_col].tolist()]

    cols = [c for c in metric_cols if c in view.columns]
    if not cols:
        return None

    raw = []
    scaled = []

    for c in cols:
        arr = pd.to_numeric(view[c], errors="coerce").to_numpy(dtype=float)
        raw.append(arr)
        lo, hi = _robust_minmax(arr) if robust else _finite_minmax(arr)
        if abs(hi - lo) < 1e-12:
            sc = np.zeros_like(arr)
        else:
            sc = (arr - lo) / (hi - lo)
        sc = np.clip(sc, 0.0, 1.0)
        scaled.append(sc)

    # shape: tests × metrics
    raw_m = np.vstack(raw).T
    z = np.vstack(scaled).T

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=z,
                x=list(cols),
                y=tests,
                customdata=raw_m,
                colorbar=dict(title="норм.", len=0.75),
                hovertemplate=(
                    "Тест=%{y}<br>Метрика=%{x}<br>Норм=%{z:.3f}<br>Знач=%{customdata:.6g}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        title=title,
        height=max(340, 18 * len(tests) + 140),
        margin=dict(l=100, r=20, t=60, b=40),
        xaxis=dict(tickangle=-20),
    )
    return fig


def make_time_heatmap(
    df: pd.DataFrame,
    time_col: str,
    series_cols: Sequence[str],
    *,
    y_labels: Optional[Sequence[str]] = None,
    title: str = "Теплокарта",
    unit: str = "",
    max_time_points: int = 900,
    transform: Optional[callable] = None,
) -> "go.Figure | None":
    """Теплокарта: Y=серии (узлы/клапаны), X=время."""
    if go is None:
        return None
    if df is None or df.empty:
        return None
    if time_col not in df.columns:
        return None

    cols = [c for c in series_cols if c in df.columns and c != time_col]
    if not cols:
        return None

    t = pd.to_numeric(df[time_col], errors="coerce").to_numpy(dtype=float)
    n = int(len(t))
    if n <= 1:
        return None

    # downsample по времени — защита UI
    if max_time_points and n > int(max_time_points):
        idx = np.linspace(0, n - 1, int(max_time_points)).astype(int)
        t = t[idx]
        data = df.iloc[idx]
    else:
        data = df

    mat = []
    for c in cols:
        arr = pd.to_numeric(data[c], errors="coerce").to_numpy(dtype=float)
        if transform is not None:
            try:
                arr = np.asarray(transform(arr), dtype=float)
            except Exception:
                pass
        mat.append(arr)

    z = np.vstack(mat)  # rows=series, cols=time

    yl = [str(c) for c in cols]
    if y_labels is not None and len(y_labels) == len(cols):
        yl = [str(x) for x in y_labels]

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=z,
                x=t,
                y=yl,
                colorbar=dict(title=unit, len=0.75),
                hovertemplate=("%{y}<br>t=%{x:.3f} s<br>%{z:.6g} " + (unit or "") + "<extra></extra>"),
            )
        ]
    )
    fig.update_layout(
        title=title,
        height=max(320, 22 * len(yl) + 140),
        margin=dict(l=110, r=20, t=60, b=40),
        xaxis_title="t, s",
    )
    return fig


def make_corner_heatmap_animation(
    t: Sequence[float],
    values_by_corner: Dict[str, Sequence[float]],
    *,
    title: str = "Анимированная теплокарта 2×2",
    unit: str = "",
    max_frames: int = 240,
    robust_range: bool = True,
) -> "go.Figure | None":
    """Анимированная теплокарта 2×2 для четырёх углов машины.

    Углы (фикс):
      [ [ЛП, ПП],
        [ЛЗ, ПЗ] ]

    Встроенные кнопки play/pause — анимация идёт **в браузере**, без rerun Streamlit.

    Совместимость:
    - Plotly в проекте может быть довольно старым (например 5.3),
      поэтому мы НЕ используем `texttemplate` у Heatmap. Текст в ячейках
      рисуется поверх теплокарты отдельным Scatter(trace).
    """
    if go is None:
        return None

    t_arr = np.asarray(list(t), dtype=float)
    n = int(len(t_arr))
    if n <= 1:
        return None

    # collect arrays
    arrs: Dict[str, np.ndarray] = {}
    for c in CORNERS:
        v = values_by_corner.get(c)
        if v is None:
            return None
        arrs[c] = np.asarray(list(v), dtype=float)
        if len(arrs[c]) != n:
            return None

    allv = np.concatenate([arrs[c] for c in CORNERS])
    zmin, zmax = (_robust_minmax(allv) if robust_range else _finite_minmax(allv))
    if not math.isfinite(zmin) or not math.isfinite(zmax) or abs(zmax - zmin) < 1e-12:
        zmin = float(zmin if math.isfinite(zmin) else 0.0)
        zmax = float(zmax if math.isfinite(zmax) else 1.0)
        if abs(zmax - zmin) < 1e-12:
            zmax = zmin + 1.0

    n_frames = int(min(max_frames, n))
    idxs = np.linspace(0, n - 1, n_frames).astype(int)

    def z_at(i: int) -> np.ndarray:
        return np.asarray(
            [
                [arrs["ЛП"][i], arrs["ПП"][i]],
                [arrs["ЛЗ"][i], arrs["ПЗ"][i]],
            ],
            dtype=float,
        )

    xlab = ["Лево", "Право"]
    ylab = ["Перед", "Зад"]
    sx = [xlab[0], xlab[1], xlab[0], xlab[1]]
    sy = [ylab[0], ylab[0], ylab[1], ylab[1]]

    def scatter_text(i: int) -> List[str]:
        z = z_at(i)
        return [
            f"ЛП\n{z[0,0]:.3g}",
            f"ПП\n{z[0,1]:.3g}",
            f"ЛЗ\n{z[1,0]:.3g}",
            f"ПЗ\n{z[1,1]:.3g}",
        ]

    i0 = int(idxs[0])
    z0 = z_at(i0)

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=z0,
                x=xlab,
                y=ylab,
                zmin=float(zmin),
                zmax=float(zmax),
                hovertemplate=(
                    "t=%{customdata:.3f} s<br>%{y} / %{x}<br>%{z:.6g} " + (unit or "") + "<extra></extra>"
                ),
                customdata=np.full_like(z0, float(t_arr[i0]), dtype=float),
                colorbar=dict(title=unit, len=0.75),
            ),
            go.Scatter(
                x=sx,
                y=sy,
                text=scatter_text(i0),
                mode="text",
                textposition="middle center",
                hoverinfo="skip",
                showlegend=False,
            ),
        ]
    )

    frames = []
    steps = []
    for k, i in enumerate(idxs.tolist()):
        z = z_at(int(i))
        frames.append(
            go.Frame(
                data=[
                    go.Heatmap(
                        z=z,
                        customdata=np.full_like(z, float(t_arr[int(i)]), dtype=float),
                    ),
                    go.Scatter(
                        text=scatter_text(int(i)),
                    ),
                ],
                name=str(k),
            )
        )
        steps.append(
            {
                "method": "animate",
                "args": [
                    [str(k)],
                    {
                        "mode": "immediate",
                        "frame": {"duration": 0, "redraw": True},
                        "transition": {"duration": 0},
                    },
                ],
                "label": f"{float(t_arr[int(i)]):.2f}",
            }
        )

    fig.frames = frames

    fig.update_layout(
        title=title,
        height=420,
        margin=dict(l=60, r=20, t=60, b=40),
        xaxis=dict(constrain="domain"),
        yaxis=dict(autorange="reversed"),
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "x": 0.02,
                "y": 1.12,
                "pad": {"r": 10, "t": 10},
                "buttons": [
                    {
                        "label": "▶",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "frame": {"duration": 60, "redraw": True},
                                "transition": {"duration": 0},
                                "fromcurrent": True,
                                "mode": "immediate",
                            },
                        ],
                    },
                    {
                        "label": "⏸",
                        "method": "animate",
                        "args": [
                            [None],
                            {
                                "mode": "immediate",
                                "frame": {"duration": 0, "redraw": False},
                                "transition": {"duration": 0},
                            },
                        ],
                    },
                ],
            }
        ],
        sliders=[
            {
                "active": 0,
                "x": 0.02,
                "y": 1.02,
                "len": 0.96,
                "pad": {"b": 0, "t": 0},
                "steps": steps,
            }
        ],
    )
    return fig

