"""Пневмосхема: SVG‑мнемосхема и редактор соответствия.

Ключевая идея:
 - схема (SVG) — это визуализация;
 - результаты расчёта (df_mdot / df_p) — это данные;
 - mapping связывает «имена ребер/узлов модели» с геометрией SVG.

Страница делает 3 вещи:
 1) показывает SVG‑мнемосхему и анимацию (если есть данные и mapping);
 2) показывает статус mapping (сколько ребер/узлов привязано);
 3) позволяет вручную править mapping (JSON) и/или собирать его из полилиний SVG.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from pneumo_solver_ui.streamlit_compat import request_rerun

from pneumo_solver_ui import run_artifacts
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
from pneumo_solver_ui.ui_components import get_pneumo_svg_flow_component
from pneumo_solver_ui.svg_autotrace import analysis_polylines_to_coords, extract_polylines


PAGE_TITLE = "🫁 Пневмосхема: мнемосхема (SVG)"
PAGE_DESC = "Анимированная мнемосхема пневмосистемы + редактор соответствия «модель ↔ SVG»."
PAGE_HELP = (
    "**Зачем эта страница**\n"
    "\n"
    "Мнемосхема (SVG) показывает работу пневмосистемы на одной картинке: расход по ребрам и давление в объёмах.\n"
    "Чтобы анимация была корректной, нужен *mapping* — соответствие между именами ребер/узлов модели и геометрией SVG.\n"
    "\n"
    "**Что нужно для работы**\n"
    "- Выполнить опорный прогон с полными записями (record_full=True), чтобы были df_mdot и df_p.\n"
    "- Настроить mapping (вручную или через редактор полилиний).\n"
    "\n"
    "**Типовые ошибки**\n"
    "- В расчёте нет df_mdot/df_p → включите полный лог (record_full).\n"
    "- Mapping пустой → анимация покажет только SVG без данных.\n"
    "- Несовпадение имён ребер/узлов → проверьте названия столбцов df_mdot/df_p и ключи mapping.\n"
)


HERE = Path(__file__).resolve().parents[1]
DEFAULT_SVG_PATH = HERE / "data" / "pneumo_scheme" / "pneumo_scheme.svg"
DEFAULT_MAPPING_PATH = HERE / "default_svg_mapping.json"  # шаблон (может быть пустым)


P_ATM = 101325.0
BAR_PA = 1.0e5
R_AIR = 287.05
T_AIR = 293.15


@dataclass
class DetailCacheItem:
    path: Path
    label: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _safe_json_loads(s: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        obj = json.loads(s)
    except Exception as e:  # noqa: BLE001
        return None, f"JSON не разобран: {e}"
    if not isinstance(obj, dict):
        return None, "Ожидался JSON‑объект (словарь)."
    if "edges" not in obj or "nodes" not in obj:
        return None, "Некорректный mapping: отсутствуют ключи 'edges'/'nodes'."
    return obj, None


def _load_default_mapping_text() -> str:
    try:
        return _read_text(DEFAULT_MAPPING_PATH)
    except Exception:
        # fallback
        return json.dumps({"version": 2, "edges": {}, "nodes": {}}, ensure_ascii=False, indent=2)


def _get_mapping_text() -> str:
    if "svg_mapping_text" not in st.session_state:
        st.session_state["svg_mapping_text"] = _load_default_mapping_text()
    return str(st.session_state.get("svg_mapping_text", ""))


@st.cache_resource(show_spinner=False)
def _load_gz_pickle(path_str: str, mtime_ns: int) -> Dict[str, Any]:
    """Загрузка gz‑pickle с привязкой к mtime для корректной инвалидации кэша.

    В detail-cache могут лежать объекты с классами из динамически загруженного
    модуля модели (например, ``pneumo_model_mod.Node``). ``st.cache_data``
    сериализует возвращаемое значение через pickle и на таких объектах падает.
    Здесь нужен ``st.cache_resource``: он кэширует объект по ключу, но не
    пытается повторно сериализовать payload.
    """
    _ = mtime_ns
    # В baseline‑кэше используется cloudpickle; но обычный pickle тоже справится на большинстве объектов.
    try:
        import cloudpickle as pkl  # type: ignore
    except Exception:  # noqa: BLE001
        import pickle as pkl  # type: ignore

    with gzip.open(path_str, "rb") as f:
        obj = pkl.load(f)
    if not isinstance(obj, dict):
        raise TypeError(f"Ожидался dict в detail cache, получено: {type(obj)}")
    return obj


def _list_detail_caches(run_dir: Path) -> List[DetailCacheItem]:
    d = run_dir / "detail"
    if not d.exists():
        return []
    items: List[DetailCacheItem] = []
    for p in sorted(d.glob("*.pkl.gz"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append(DetailCacheItem(path=p, label=p.name))
    # поддержка legacy *.pkl
    for p in sorted(d.glob("*.pkl"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append(DetailCacheItem(path=p, label=p.name + " (legacy)"))
    return items


def _unit_convert_mdot_to_nlpm(mdot_kg_s: List[float]) -> List[float]:
    # Нормальные литры/мин (оценка): Q_N[L/min] = mdot * 60 / rho_N * 1000
    rho_n = P_ATM / (R_AIR * T_AIR)
    k = (60.0 * 1000.0) / rho_n
    return [float(v) * k for v in mdot_kg_s]


def _unit_convert_p_to_gauge_bar(p_pa: List[float]) -> List[float]:
    return [(float(v) - P_ATM) / BAR_PA for v in p_pa]


def _pick_run_source() -> Tuple[str, Optional[Path]]:
    """Выбор источника данных для мнемосхемы.

    Нюанс: для "симуляции/опорного прогона" run_artifacts хранит cache_dir,
    а для оптимизации — run_dir. Здесь приводим к единому виду Path.

    Возвращает:
    - tag: 'baseline' | 'opt' | 'manual' | '—'
    - run_dir: Path (каталог с detail/*.pkl) или None
    """

    last_b = run_artifacts.load_last_baseline_ptr() or {}
    last_o = run_artifacts.load_last_opt_ptr() or {}

    choices: List[Tuple[str, Optional[Path], str]] = []

    # baseline/simulation -> cache_dir
    b_dir = last_b.get('cache_dir') or last_b.get('run_dir')
    if b_dir:
        choices.append(("Опорный прогон", Path(b_dir), "baseline"))

    # optimization -> run_dir
    o_dir = last_o.get('run_dir') or last_o.get('cache_dir')
    if o_dir:
        choices.append(("Оптимизация", Path(o_dir), "opt"))

    # Session_state fallback
    try:
        ss = st.session_state
        if ss.get('baseline_cache_dir'):
            choices.append(("Опорный прогон (session_state)", Path(ss['baseline_cache_dir']), "baseline"))
        if ss.get('opt_run_dir'):
            choices.append(("Оптимизация (session_state)", Path(ss['opt_run_dir']), "opt"))
    except Exception:
        pass

    # Manual option
    choices.append(("Указать путь вручную", None, "manual"))

    if not choices:
        return "—", None

    # Стабильный порядок: baseline → opt → manual
    labels = [c[0] for c in choices]
    tags = [c[2] for c in choices]

    default_tag = st.session_state.get("svg_run_source", tags[0])
    default_ix = tags.index(default_tag) if default_tag in tags else 0

    src_label = st.radio(
        "Источник результатов",
        labels,
        index=default_ix,
        horizontal=True,
        help=(
            "Откуда брать детали для мнемосхемы (detail/*.pkl). "
            "Обычно это последний опорный прогон." 
        ),
        key="_svg_run_source_label",
    )
    ix = labels.index(src_label)
    st.session_state["svg_run_source"] = tags[ix]

    tag = tags[ix]
    run_dir = choices[ix][1]

    if tag == 'manual':
        raw = st.text_input(
            "Путь к каталогу прогона/кэша",
            value="",
            help=(
                "Каталог должен содержать папку detail/ с *.pkl (детали прогона). "
                "Для опорного прогона это cache_dir, для оптимизации — run_dir." 
            ),
        )
        try:
            run_dir = Path(raw).expanduser().resolve() if raw.strip() else None
        except Exception:
            run_dir = None

    if run_dir is not None and not run_dir.exists():
        st.warning(f"Каталог не найден: {run_dir}")
        run_dir = None

    return tag, run_dir


def _ensure_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(v) for v in x]
    return [str(x)]


def main() -> None:
    bootstrap(st)
    autosave_if_enabled(st)
    st.title(PAGE_TITLE)
    st.caption(PAGE_DESC)

    with st.expander("? Справка", expanded=False):
        st.markdown(PAGE_HELP)

    # --- Источник результатов ---
    tag, run_dir = _pick_run_source()
    if run_dir is None:
        st.warning(
            "Нет сохранённых результатов (run_artifacts). Сначала выполните «Опорный прогон» "
            "в «Рабочем месте» или запустите оптимизацию."
        )
        return

    st.info(f"Источник: **{tag}** · каталог: `{run_dir}`")

    # --- Выбор detail cache (где лежат df_mdot/df_p) ---
    caches = _list_detail_caches(run_dir)
    if not caches:
        st.warning(
            "В выбранном прогоне нет detail‑кэшей (`detail/*.pkl.gz`). "
            "Скорее всего, расчёт выполнялся без полного логирования (record_full=False)."
        )
        return

    default_cache = st.session_state.get("svg_detail_cache", caches[0].path.as_posix())
    cache_labels = [c.label for c in caches]
    cache_paths = [c.path.as_posix() for c in caches]
    if default_cache in cache_paths:
        default_ix = cache_paths.index(default_cache)
    else:
        default_ix = 0

    chosen_label = st.selectbox(
        "Детализация (detail‑cache)",
        cache_labels,
        index=default_ix,
        help="Файл с детальными временными рядами. Для мнемосхемы нужны df_mdot и df_p.",
    )
    chosen_ix = cache_labels.index(chosen_label)
    chosen_path = caches[chosen_ix].path
    st.session_state["svg_detail_cache"] = chosen_path.as_posix()

    # --- Загрузка данных (с кэшем) ---
    with st.spinner("Загрузка детальных данных…"):
        mtime_ns = chosen_path.stat().st_mtime_ns
        payload = _load_gz_pickle(chosen_path.as_posix(), mtime_ns)

    df_mdot = payload.get("df_mdot")
    df_p = payload.get("df_p")
    if not isinstance(df_mdot, pd.DataFrame) or not isinstance(df_p, pd.DataFrame):
        st.error(
            "В detail‑кэше не найдены df_mdot/df_p. "
            "Перезапустите опорный прогон с record_full=True."
        )
        return

    # --- SVG и mapping ---
    if not DEFAULT_SVG_PATH.exists():
        st.error(f"Не найден SVG: {DEFAULT_SVG_PATH}")
        return

    svg_text = _read_text(DEFAULT_SVG_PATH)

    mapping_text = _get_mapping_text()
    mapping_obj, mapping_err = _safe_json_loads(mapping_text)
    if mapping_err:
        st.error(mapping_err)
        st.stop()
    assert mapping_obj is not None

    # --- Сводка по данным (делаем колонками) ---
    t_col = "время_с" if "время_с" in df_mdot.columns else None
    n_steps = len(df_mdot)
    edge_cols = [c for c in df_mdot.columns if c != t_col]
    node_cols = [c for c in df_p.columns if c != t_col and c != "время_с"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Шагов", f"{n_steps}")
    c2.metric("Ребер (df_mdot)", f"{len(edge_cols)}")
    c3.metric("Узлов (df_p)", f"{len(node_cols)}")
    c4.metric("Mapping: ребра/узлы", f"{len(mapping_obj.get('edges', {}))}/{len(mapping_obj.get('nodes', {}))}")

    # --- Выбор отображаемых ребер/узлов ---
    with st.expander("⚙️ Отображение: какие ребра/узлы показывать", expanded=False):
        default_edges = st.session_state.get("svg_pick_edges", edge_cols[: min(8, len(edge_cols))])
        default_nodes = st.session_state.get("svg_pick_nodes", node_cols[: min(8, len(node_cols))])
        pick_edges = st.multiselect(
            "Ребра (расход)",
            options=edge_cols,
            default=[e for e in _ensure_list(default_edges) if e in edge_cols],
            help="Выберите ребра, которые будут анимироваться на схеме."
        )
        pick_nodes = st.multiselect(
            "Узлы (давление)",
            options=node_cols,
            default=[n for n in _ensure_list(default_nodes) if n in node_cols],
            help="Выберите объёмы/узлы, для которых показывается давление."
        )
        st.session_state["svg_pick_edges"] = pick_edges
        st.session_state["svg_pick_nodes"] = pick_nodes

        unit_flow = st.selectbox(
            "Единицы расхода",
            options=["кг/с", "Нл/мин"],
            index=1,
            help="Преобразование расхода (mdot) для удобства восприятия. Нл/мин — нормальные литры/мин (оценка).",
            key="svg_flow_unit",
        )
        unit_p = st.selectbox(
            "Единицы давления",
            options=["Па (абсолютное)", "бар (избыточное)"],
            index=1,
            help="Для мнемосхемы обычно удобнее избыточное давление (bar gauge).",
            key="svg_p_unit",
        )

    # --- Подготовка рядов для компонента ---
    # Важно: компонент ожидает list[{'name': str, 'q': [..], 'unit': str}] и list[{'name': str, 'p': [..]}]
    edge_series: List[Dict[str, Any]] = []
    for e in pick_edges:
        arr = [float(v) for v in df_mdot[e].values.tolist()]
        if unit_flow == "Нл/мин":
            arr = _unit_convert_mdot_to_nlpm(arr)
            u = "Нл/мин"
        else:
            u = "кг/с"
        edge_series.append({"name": str(e), "q": arr, "unit": u})

    node_series: List[Dict[str, Any]] = []
    for n in pick_nodes:
        parr = [float(v) for v in df_p[n].values.tolist()]
        if unit_p == "бар (избыточное)":
            parr = _unit_convert_p_to_gauge_bar(parr)
            pu = "бар"
        else:
            pu = "Па"
        node_series.append({"name": str(n), "p": parr, "unit": pu})

    # --- Мнемосхема (гейт) ---
    show_svg = st.checkbox(
        "Показать мнемосхему (SVG)",
        value=True,
        help="Если выключено — тяжёлый компонент не создаётся. Это ускоряет работу страницы.",
        key="svg_show_component",
    )

    if show_svg:
        comp = get_pneumo_svg_flow_component()
        # time (сек) может быть в df_mdot[время_с]; иначе используем индекс
        if t_col and t_col in df_mdot.columns:
            time_arr = [float(v) for v in df_mdot[t_col].values.tolist()]
        else:
            time_arr = [float(i) for i in range(len(df_mdot))]

        selected = st.session_state.get("svg_selected", {"edge": None, "node": None})
        out = comp(
            title="Мнемосхема пневмосистемы",
            svg=svg_text,
            mapping=mapping_obj,
            time=time_arr,
            edges=edge_series,
            nodes=node_series,
            selected=selected,
            sync_playhead=True,
            playhead_storage_key="svg_playhead",
            dataset_id=f"{tag}:{chosen_path.name}",
            height=520,
            key="pneumo_svg_flow",
            default={"ok": True},
        )
        if isinstance(out, dict):
            st.session_state["svg_selected"] = out.get("selected", selected)
            # review_action/other events можно обработать позже

    # --- Редактор mapping ---
    with st.expander("🧩 Редактор соответствия (mapping)", expanded=False):
        st.markdown(
            "Mapping хранится в session_state и **автоматически сохраняется** (на диск профиля UI). "
            "Здесь можно отредактировать JSON вручную или собрать привязки из полилиний SVG."
        )

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            if st.button("Сбросить на шаблон", width="stretch"):
                st.session_state["svg_mapping_text"] = json.dumps(
                    {"version": 2, "edges": {}, "nodes": {}}, ensure_ascii=False, indent=2
                )
                request_rerun(st)
        with col_b:
            up = st.file_uploader(
                "Загрузить mapping (JSON)",
                type=["json"],
                help="Можно загрузить ранее сохранённый mapping.json.",
                key="svg_mapping_uploader",
            )
            if up is not None:
                try:
                    st.session_state["svg_mapping_text"] = up.getvalue().decode("utf-8")
                    request_rerun(st)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Не удалось прочитать файл: {e}")
        with col_c:
            st.download_button(
                "Скачать mapping (JSON)",
                data=st.session_state.get("svg_mapping_text", ""),
                file_name="pneumo_svg_mapping.json",
                mime="application/json",
                width="stretch",
                help="Сохраните mapping, чтобы перенести на другую машину/проект.",
            )

        mapping_text2 = st.text_area(
            "mapping (JSON)",
            value=st.session_state.get("svg_mapping_text", ""),
            height=260,
            help="Главный источник соответствия модель↔SVG. При ошибке JSON анимация не будет работать.",
            key="svg_mapping_textarea",
        )
        obj2, err2 = _safe_json_loads(mapping_text2)
        if err2:
            st.error(err2)
        else:
            st.session_state["svg_mapping_text"] = mapping_text2
            mapping_obj = obj2  # обновим для дальнейших действий

        # --- Полилинии SVG: быстрый конструктор mapping.edges ---
        st.markdown("#### Привязка ребер к полилиниям SVG")
        st.caption(
            "Мы извлекаем из SVG набор полилиний (отрезков труб) и привязываем их к ребрам модели. "
            "Это ручной инструмент: выберите ребро модели и укажите индексы полилиний."
        )

        with st.spinner("Извлекаем полилинии из SVG…"):
            analysis = extract_polylines(svg_text)
            polylines = analysis_polylines_to_coords(analysis)
            texts = list(analysis.get("texts", [])) if isinstance(analysis, dict) else []

        st.caption(f"Полилиний найдено: {len(polylines)} · текстовых меток: {len(texts)}")

        col_e1, col_e2 = st.columns([2, 3])
        with col_e1:
            edge_name = st.selectbox(
                "Ребро модели",
                options=edge_cols,
                help="Имя ребра берётся из столбцов df_mdot.",
                key="svg_map_edge_name",
            )
            poly_ids = st.multiselect(
                "Полилинии SVG (индексы)",
                options=list(range(len(polylines))),
                default=[],
                help="Индексы полилиний. Подсказка: откройте страницу «Пневмосхема: граф (SVG)» и посмотрите номера.",
                key="svg_map_poly_ids",
            )
            reverse_dir = st.checkbox(
                "Инвертировать направление полилиний",
                value=False,
                help="Иногда стрелка/анимация получается наоборот — можно развернуть список точек.",
                key="svg_map_reverse",
            )
            if st.button("Привязать (заменить)", width="stretch"):
                if obj2 is None:
                    st.error("Нельзя изменить mapping: JSON содержит ошибку.")
                else:
                    polys = []
                    for pid in poly_ids:
                        pts = [list(map(float, xy)) for xy in polylines[int(pid)]]
                        if reverse_dir:
                            pts = list(reversed(pts))
                        polys.append(pts)
                    obj2.setdefault("edges", {})[str(edge_name)] = polys
                    st.session_state["svg_mapping_text"] = json.dumps(obj2, ensure_ascii=False, indent=2)
                    st.success("Привязка ребра обновлена.")

        with col_e2:
            st.markdown("**Текущее значение в mapping.edges:**")
            if obj2 is not None:
                cur = obj2.get("edges", {}).get(str(edge_name))
                st.json(cur if cur is not None else [])

        st.markdown("#### Привязка узлов (давление)")
        st.caption(
            "Узел (объём) задаётся одной точкой [x,y] в координатах SVG. "
            "Можно выбрать по текстовой метке или ввести координаты вручную."
        )
        col_n1, col_n2 = st.columns([2, 3])
        with col_n1:
            node_name = st.selectbox(
                "Узел модели",
                options=node_cols,
                help="Имя узла берётся из столбцов df_p.",
                key="svg_map_node_name",
            )
            label_opts = ["(вручную)"] + [t.get("text", "") for t in texts]
            pick_label = st.selectbox(
                "Подсказка по метке SVG",
                options=label_opts,
                index=0,
                help="Если в SVG есть подписи рядом с объёмами — выберите их, чтобы взять координаты автоматически.",
                key="svg_map_node_label",
            )
            x0, y0 = 0.0, 0.0
            if pick_label != "(вручную)":
                try:
                    idx = label_opts.index(pick_label) - 1
                    if idx >= 0:
                        x0 = float(texts[idx].get("x", 0.0))
                        y0 = float(texts[idx].get("y", 0.0))
                except Exception:
                    pass
            x = st.number_input("x, px", value=float(x0), step=1.0, format="%.2f", key="svg_map_node_x")
            y = st.number_input("y, px", value=float(y0), step=1.0, format="%.2f", key="svg_map_node_y")

            if st.button("Привязать узел", width="stretch"):
                if obj2 is None:
                    st.error("Нельзя изменить mapping: JSON содержит ошибку.")
                else:
                    obj2.setdefault("nodes", {})[str(node_name)] = [float(x), float(y)]
                    st.session_state["svg_mapping_text"] = json.dumps(obj2, ensure_ascii=False, indent=2)
                    st.success("Привязка узла обновлена.")

        with col_n2:
            st.markdown("**Текущее значение в mapping.nodes:**")
            if obj2 is not None:
                cur2 = obj2.get("nodes", {}).get(str(node_name))
                st.json(cur2 if cur2 is not None else [])


if __name__ == "__main__":
    main()
