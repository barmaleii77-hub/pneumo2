"""Пневмосхема: граф SVG (полилинии) и диагностические подсказки.

Страница нужна для:
 - просмотра «разбиения» SVG на полилинии (отрезки труб),
 - понимания индексов полилиний, чтобы собрать mapping (см. страницу мнемосхемы).

Мы НЕ делаем здесь «ещё один редактор» — только визуализация и справочные таблицы.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go  # type: ignore
    _HAS_PLOTLY = True
    _PLOTLY_IMPORT_ERR = None
except Exception as _e_plotly:  # pragma: no cover - depends on runtime env
    go = None  # type: ignore
    _HAS_PLOTLY = False
    _PLOTLY_IMPORT_ERR = _e_plotly

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
from pneumo_solver_ui.svg_autotrace import analysis_polylines_to_coords, extract_polylines


PAGE_TITLE = "🫁 Пневмосхема: граф (SVG)"
PAGE_DESC = "Визуализация полилиний, извлечённых из SVG. Помогает собирать mapping для мнемосхемы."
PAGE_HELP = (
    "**Как пользоваться**\n"
    "1) Откройте страницу и посмотрите номера полилиний на графе.\n"
    "2) Перейдите на «Пневмосхема: мнемосхема (SVG)» и в редакторе привяжите нужные полилинии к ребрам модели.\n"
    "\n"
    "**Заметка**\n"
    "SVG разбивается на полилинии автоматически, эвристически. Иногда трубопровод распадается на несколько полилиний — "
    "это нормально: в mapping одно ребро модели может ссылаться на несколько полилиний.\n"
)


HERE = Path(__file__).resolve().parents[1]
DEFAULT_SVG_PATH = HERE / "data" / "pneumo_scheme" / "pneumo_scheme.svg"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@st.cache_data(show_spinner=False)
def _cached_extract_polylines(svg_text: str, mtime: float):
    """Парсинг SVG — CPU‑тяжёлая часть.

    Важно: expander не предотвращает выполнение кода в Streamlit,
    поэтому кэшируем здесь явно.
    """
    _ = mtime  # участвует в ключе кэша
    return extract_polylines(svg_text)


def _poly_len(poly: List[Tuple[float, float]]) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
        s += math.hypot(x2 - x1, y2 - y1)
    return s


def _poly_bbox(poly: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _plot_polylines(polylines: List[List[Tuple[float, float]]], highlight: int | None = None):
    if not _HAS_PLOTLY or go is None:
        raise RuntimeError("Plotly недоступен")
    fig = go.Figure()

    for i, poly in enumerate(polylines):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        name = f"#{i}"
        if highlight is not None and i == highlight:
            width = 5
        else:
            width = 2
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                name=name,
                line=dict(width=width),
                hoverinfo="name",
                showlegend=False,
            )
        )
        # подпишем номер примерно посередине
        mid = len(xs) // 2
        fig.add_trace(
            go.Scatter(
                x=[xs[mid]],
                y=[ys[mid]],
                mode="text",
                text=[name],
                textposition="middle center",
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        height=640,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
    )
    # SVG‑координаты обычно с перевёрнутой осью Y; инвертируем для привычного вида
    fig.update_yaxes(autorange="reversed")
    return fig




def _plot_polylines_matplotlib(polylines: List[List[Tuple[float, float]]], highlight: int | None = None):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11.5, 8.0))
    for i, poly in enumerate(polylines):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        lw = 2.8 if (highlight is not None and i == highlight) else 1.4
        ax.plot(xs, ys, linewidth=lw)
        if xs and ys:
            mid = len(xs) // 2
            ax.text(xs[mid], ys[mid], f"#{i}", ha="center", va="center", fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    ax.invert_yaxis()
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("SVG полилинии")
    fig.tight_layout()
    return fig

def main() -> None:
    bootstrap(st)
    autosave_if_enabled(st)
    st.title(PAGE_TITLE)
    st.caption(PAGE_DESC)

    with st.expander("? Справка", expanded=False):
        st.markdown(PAGE_HELP)

    if not DEFAULT_SVG_PATH.exists():
        st.error(f"Не найден SVG: {DEFAULT_SVG_PATH}")
        return

    svg_text = _read_text(DEFAULT_SVG_PATH)

    with st.spinner("Извлекаем полилинии из SVG…"):
        mtime = float(DEFAULT_SVG_PATH.stat().st_mtime)
        analysis = _cached_extract_polylines(svg_text, mtime)
        polylines = analysis_polylines_to_coords(analysis)
        texts = list(analysis.get("texts", [])) if isinstance(analysis, dict) else []

    if not polylines:
        st.error("Полилинии не извлечены. Проверьте SVG или алгоритм svg_autotrace.")
        return

    st.caption(f"Полилиний: **{len(polylines)}** · текстовых меток: **{len(texts)}**")

    # Справочная таблица
    rows: List[Dict[str, Any]] = []
    for i, poly in enumerate(polylines):
        L = _poly_len(poly)
        x1, y1, x2, y2 = _poly_bbox(poly)
        rows.append(
            {
                "id": i,
                "points": len(poly),
                "len": round(L, 1),
                "bbox": f"[{x1:.0f},{y1:.0f}]–[{x2:.0f},{y2:.0f}]",
            }
        )
    df = pd.DataFrame(rows)
    df = df.sort_values("len", ascending=False)

    left, right = st.columns([2, 1])
    with right:
        highlight = st.number_input(
            "Подсветить полилинию [#]",
            min_value=0,
            max_value=max(0, len(polylines) - 1),
            value=int(st.session_state.get("svg_graph_highlight", 0)),
            step=1,
        )
        st.session_state["svg_graph_highlight"] = int(highlight)
        min_len = st.slider(
            "Фильтр по длине, px",
            min_value=0.0,
            max_value=float(df["len"].max()),
            value=0.0,
            step=10.0,
            help="Можно скрыть очень короткие полилинии (шумы).",
        )

        st.markdown("**Подсказка для mapping**")
        st.code(
            f"Ребро → полилинии: {int(highlight)}\n"
            "Перейдите на страницу мнемосхемы и добавьте этот индекс в привязку ребра.",
            language="text",
        )

    with left:
        # применим фильтр по длине
        keep_ids = set(df[df["len"] >= float(min_len)]["id"].astype(int).tolist())
        polylines_f = [p for i, p in enumerate(polylines) if i in keep_ids]
        # если highlight отфильтровался — всё равно покажем его
        if int(highlight) not in keep_ids and 0 <= int(highlight) < len(polylines):
            polylines_f = polylines_f + [polylines[int(highlight)]]

        # Визуальная подсветка конкретного id при фильтре сложна (ids теряются), поэтому подсветка через текст достаточна.
        if _HAS_PLOTLY:
            fig = _plot_polylines(polylines_f, highlight=None)
            st.plotly_chart(fig, width="stretch")
        else:
            st.warning(
                "Plotly не установлен в текущем окружении. Показываю fallback на matplotlib; "
                f"для интерактивного режима нужен plotly (launcher теперь устанавливает его из root requirements). Ошибка импорта: {_PLOTLY_IMPORT_ERR!r}"
            )
            fig = _plot_polylines_matplotlib(polylines_f, highlight=None)
            st.pyplot(fig, clear_figure=True)

    with st.expander("📋 Таблица полилиний", expanded=False):
        st.dataframe(df, width="stretch", height=320)

    with st.expander("🔤 Текстовые метки из SVG", expanded=False):
        # show a compact table
        if texts:
            tdf = pd.DataFrame(
                [
                    {
                        "text": t.get("text", ""),
                        "x": round(float(t.get("x", 0.0)), 1),
                        "y": round(float(t.get("y", 0.0)), 1),
                    }
                    for t in texts
                ]
            )
            st.dataframe(tdf, width="stretch", height=280)
        else:
            st.info("Текстовые метки не найдены.")


if __name__ == "__main__":
    main()
