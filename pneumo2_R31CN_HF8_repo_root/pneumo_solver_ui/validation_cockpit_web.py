
# -*- coding: utf-8 -*-
"""validation_cockpit_web.py

Streamlit: "один экран" для быстрой валидации одного прогона (NPZ).

Фокус:
- анимация (2D/3D) + синхронный playhead
- ключевые графики механики и пневматики
- нулевая базовая поза для перемещений/углов/дороги (display-only)
- одинаковые шкалы Y (по unit)

Цель: за 10–20 секунд понять, "похоже ли на правду".
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from pneumo_solver_ui.entrypoints import desktop_animator_page_rel, desktop_mnemo_page_rel
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary
from pneumo_solver_ui.tools.send_bundle_contract import build_anim_operator_recommendations

try:
    import plotly.graph_objects as go  # type: ignore
    from plotly.subplots import make_subplots  # type: ignore
    _HAS_PLOTLY = True
    _PLOTLY_IMPORT_ERR = None
except Exception as _e_plotly:  # pragma: no cover - depends on runtime env
    go = None  # type: ignore
    make_subplots = None  # type: ignore
    _HAS_PLOTLY = False
    _PLOTLY_IMPORT_ERR = _e_plotly

from pneumo_solver_ui.compare_ui import (
    BAR_PA,
    P_ATM_DEFAULT,
    apply_zero_baseline,
    detect_time_col,
    extract_time_vector,
    is_zeroable_unit,
    load_npz_bundle,
    locked_ranges_by_unit,
    resample_linear,
    robust_minmax,
    _infer_unit_and_transform,
)

# We reuse component declarations from simulator page (safe; only declares components).
from pneumo_solver_ui.pneumo_ui_app import get_mech_anim_component, get_mech_car3d_component
from pneumo_solver_ui.visual_contract import (
    collect_visual_cache_dependencies,
    collect_visual_contract_status as _collect_visual_contract_status,
    filter_road_payload as _filter_road_payload,
)
from pneumo_solver_ui.geometry_acceptance_contract import (
    build_geometry_acceptance_rows,
    format_geometry_acceptance_summary_lines,
)


CORNERS = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
DESKTOP_MNEMO_PAGE = desktop_mnemo_page_rel(here=__file__)
DESKTOP_ANIMATOR_PAGE = desktop_animator_page_rel(here=__file__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_npz_dirs() -> List[Path]:
    root = _repo_root()
    ui = root / "pneumo_solver_ui"
    cands = [
        ui / "workspace" / "exports",
        ui / "workspace" / "osc",
        root / "workspace" / "exports",
        root / "workspace" / "osc",
    ]
    out: List[Path] = []
    for p in cands:
        if p.exists() and p.is_dir():
            out.append(p)
    seen = set()
    uniq: List[Path] = []
    for p in out:
        s = str(p.resolve())
        if s not in seen:
            uniq.append(p)
            seen.add(s)
    return uniq


def _page_link_or_info(page: str, label: str, *, key: str) -> None:
    try:
        if hasattr(st, "page_link"):
            st.page_link(page, label=label, width="stretch")
            return
    except Exception:
        pass
    st.caption(f"{label}: {page}")


@st.cache_data(show_spinner=False)
def _load_npz(path_str: str, cache_deps: Optional[Dict[str, object]] = None) -> Dict:
    _ = cache_deps
    return load_npz_bundle(path_str)



def _pick_first_existing(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = {str(c).lower(): str(c) for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    # heuristic: substring match
    for c in candidates:
        for cc in df.columns:
            if c.lower() in str(cc).lower():
                return str(cc)
    return None


def _extract_mech_arrays(df_main: pd.DataFrame, *, dist_unit: str, angle_unit: str, p_atm: float, zero_baseline: bool, road_override: Optional[Dict[str, List[float]]] = None):
    tcol = detect_time_col(df_main)
    t = extract_time_vector(df_main, tcol)

    body: Dict[str, List[float]] = {}
    wheel: Dict[str, List[float]] = {}
    road: Dict[str, List[float]] = {}
    stroke: Dict[str, List[float]] = {}

    road_override = dict(road_override or {})

    for c in CORNERS:
        for kind, prefix, target in [
            ("body", f"z_рамы_{c}_м", body),
            ("wheel", f"z_колеса_{c}_м", wheel),
            ("road", f"дорога_{c}_м", road),
            ("stroke", f"шток_{c}_м", stroke),
        ]:
            if prefix in df_main.columns:
                y = np.asarray(df_main[prefix].values, dtype=float)
            elif kind == "road" and c in road_override:
                y = np.asarray(road_override.get(c, []), dtype=float)
            else:
                y = np.zeros_like(t, dtype=float)
            unit, tr = _infer_unit_and_transform(prefix, P_ATM=p_atm, dist_unit=dist_unit, angle_unit=angle_unit)
            y = np.asarray(tr(y), dtype=float)
            if zero_baseline and is_zeroable_unit(unit):
                y = apply_zero_baseline(t, y, unit=unit, enable=True, mode="t0")
            target[c] = y.tolist()

    # phi/theta (rad) — best effort
    col_phi = _pick_first_existing(df_main, ["phi_rad", "roll_rad", "крен_рад", "крен_rad"])
    col_th = _pick_first_existing(df_main, ["theta_rad", "pitch_rad", "тангаж_рад", "тангаж_rad"])
    phi = np.asarray(df_main[col_phi].values, dtype=float) if col_phi else np.zeros_like(t)
    theta = np.asarray(df_main[col_th].values, dtype=float) if col_th else np.zeros_like(t)

    # baseline for angles
    if zero_baseline:
        phi = apply_zero_baseline(t, phi, unit="rad", enable=True, mode="t0")
        theta = apply_zero_baseline(t, theta, unit="rad", enable=True, mode="t0")

    return t, body, wheel, road, stroke, phi, theta


def _plot_small_multiples(df: pd.DataFrame, signals: List[str], *, dist_unit: str, angle_unit: str, p_atm: float, zero_baseline: bool, lock_unit: bool) -> go.Figure:
    tcol = detect_time_col(df) or df.columns[0]
    t = extract_time_vector(df, tcol)

    fig = make_subplots(rows=len(signals), cols=1, shared_xaxes=True, vertical_spacing=0.02)
    fig.update_layout(height=max(520, 220 * len(signals)), hovermode="x unified", margin=dict(l=40, r=10, t=30, b=30))

    # compute per-unit ranges
    unit_ranges = {}
    if lock_unit:
        series_by_sig = {}
        for s in signals:
            if s not in df.columns:
                continue
            y0 = np.asarray(df[s].values, dtype=float)
            unit, tr = _infer_unit_and_transform(s, P_ATM=p_atm, dist_unit=dist_unit, angle_unit=angle_unit)
            y = np.asarray(tr(y0), dtype=float)
            if zero_baseline and is_zeroable_unit(unit):
                y = apply_zero_baseline(t, y, unit=unit, enable=True, mode="t0")
            series_by_sig[s] = (unit, y)
        unit_ranges = locked_ranges_by_unit(series_by_sig, robust=True, symmetric=False)

    for i, s in enumerate(signals, start=1):
        if s not in df.columns:
            continue
        y0 = np.asarray(df[s].values, dtype=float)
        unit, tr = _infer_unit_and_transform(s, P_ATM=p_atm, dist_unit=dist_unit, angle_unit=angle_unit)
        y = np.asarray(tr(y0), dtype=float)
        if zero_baseline and is_zeroable_unit(unit):
            y = apply_zero_baseline(t, y, unit=unit, enable=True, mode="t0")
        fig.add_trace(go.Scatter(x=t, y=y, mode="lines", name=s), row=i, col=1)

        if lock_unit and unit in unit_ranges:
            yr = unit_ranges[unit]
            fig.update_yaxes(range=[yr.ymin, yr.ymax], row=i, col=1)

        fig.update_yaxes(title_text=f"{s} [{unit}]" if unit else s, row=i, col=1)

    fig.update_xaxes(title_text="t, s", row=len(signals), col=1)
    return fig

def _plot_small_multiples_matplotlib(df: pd.DataFrame, signals: List[str], *, dist_unit: str, angle_unit: str, p_atm: float, zero_baseline: bool, lock_unit: bool):
    import matplotlib.pyplot as plt

    tcol = detect_time_col(df)
    t = extract_time_vector(df, tcol)
    sigs = [s for s in signals if s in df.columns]
    n = max(1, len(sigs))
    fig, axes = plt.subplots(n, 1, figsize=(14, max(3.0, 2.2 * n)), sharex=True)
    if not isinstance(axes, np.ndarray):
        axes = np.asarray([axes])

    unit_ranges = {}
    if lock_unit:
        series_by_sig = {}
        for s in sigs:
            y0 = np.asarray(df[s].values, dtype=float)
            unit, tr = _infer_unit_and_transform(s, P_ATM=p_atm, dist_unit=dist_unit, angle_unit=angle_unit)
            y = np.asarray(tr(y0), dtype=float)
            if zero_baseline and is_zeroable_unit(unit):
                y = apply_zero_baseline(t, y, unit=unit, enable=True, mode="t0")
            series_by_sig[s] = (unit, y)
        unit_ranges = locked_ranges_by_unit(series_by_sig, robust=True, symmetric=False)

    for ax, s in zip(axes.tolist(), sigs):
        y0 = np.asarray(df[s].values, dtype=float)
        unit, tr = _infer_unit_and_transform(s, P_ATM=p_atm, dist_unit=dist_unit, angle_unit=angle_unit)
        y = np.asarray(tr(y0), dtype=float)
        if zero_baseline and is_zeroable_unit(unit):
            y = apply_zero_baseline(t, y, unit=unit, enable=True, mode="t0")
        ax.plot(t, y)
        if lock_unit and unit in unit_ranges:
            yr = unit_ranges[unit]
            ax.set_ylim(float(yr.ymin), float(yr.ymax))
        ax.set_ylabel(f"{s} [{unit}]" if unit else s)
        ax.grid(True, alpha=0.25)

    axes[-1].set_xlabel("t, s")
    fig.tight_layout()
    return fig


def _plot_valves_heatmap_matplotlib(df_open: pd.DataFrame, *, tcol: str, cols: List[str]):
    import matplotlib.pyplot as plt

    tt = extract_time_vector(df_open, tcol)
    z = np.vstack([np.asarray(df_open[c].values, dtype=float) for c in cols])
    fig_h = max(4.0, min(16.0, 0.28 * len(cols) + 2.5))
    fig, ax = plt.subplots(figsize=(14, fig_h))
    extent = [float(tt[0]) if len(tt) else 0.0, float(tt[-1]) if len(tt) else 0.0, -0.5, len(cols) - 0.5]
    im = ax.imshow(z, aspect="auto", origin="lower", extent=extent)
    ax.set_yticks(range(len(cols)))
    ax.set_yticklabels(cols)
    ax.set_xlabel("t, s")
    ax.set_title("Клапаны (open): быстрый таймлайн")
    fig.colorbar(im, ax=ax, label="open")
    fig.tight_layout()
    return fig



def render_validation_cockpit_web() -> None:
    st.title("Кокпит валидации (Web) — один экран проверки прогона")
    st.caption("Анимация + ключевые графики + нулевая статика и одинаковые шкалы.")

    if not _HAS_PLOTLY:
        st.warning(
            "Plotly не установлен в текущем окружении. Страница продолжит работать, "
            "но тяжёлые графики будут показаны через matplotlib без интерактивного выбора. "
            f"Ошибка импорта: {_PLOTLY_IMPORT_ERR!r}"
        )

    dirs = _default_npz_dirs()
    if not dirs:
        st.warning("Не найдены папки с NPZ. Сначала выполните экспорт.")
        return

    with st.sidebar:
        base_dir = st.selectbox("Папка", options=[str(p) for p in dirs], index=0)
        files = sorted(Path(base_dir).glob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            st.warning("В папке нет NPZ")
            return
        pick = st.selectbox("NPZ", options=[str(p) for p in files], index=0)

        st.header("Отображение")
        dist_unit = st.selectbox("Ед. расстояний", options=["mm", "m"], index=0)
        angle_unit = st.selectbox("Ед. углов", options=["deg", "rad"], index=0)
        zero_baseline = st.checkbox("Нулевая база (позиции/углы/дорога)", value=True)
        lock_unit = st.checkbox("Одинаковая шкала Y (по единице)", value=True)

        st.header("Давление")
        p_atm = st.number_input("P_ATM, Pa", min_value=0.0, value=float(P_ATM_DEFAULT), step=1000.0)

        st.header("Анимация")
        view = st.radio("Вид", options=["2D", "3D"], index=0, horizontal=True)
        height = st.slider("Высота", min_value=420, max_value=900, value=620, step=10)

    cache_deps = collect_visual_cache_dependencies(pick, context="Validation Cockpit NPZ cache")
    bun = _load_npz(pick, cache_deps)
    tables = bun.get("tables") if isinstance(bun, dict) else {}
    meta = bun.get("meta") if isinstance(bun, dict) else {}
    visual_contract = bun.get("visual_contract") if isinstance(bun, dict) else {}
    geometry_acceptance = bun.get("geometry_acceptance") if isinstance(bun, dict) else {}
    road_sidecar_wheels = bun.get("road_sidecar_wheels") if isinstance(bun, dict) else {}
    if not isinstance(tables, dict) or not tables:
        st.error("NPZ не содержит таблиц")
        return
    df_main = tables.get("main") or tables.get("full")
    if df_main is None or df_main.empty:
        st.error("В NPZ нет таблицы main/full")
        return

    # static stroke length
    L_stroke_m = 0.25
    try:
        if isinstance(meta, dict) and meta.get("L_stroke_m") is not None:
            L_stroke_m = float(meta.get("L_stroke_m"))

    except Exception:
        pass

    if not isinstance(visual_contract, dict) or not visual_contract:
        visual_contract = _collect_visual_contract_status(
            df_main,
            meta=meta if isinstance(meta, dict) else {},
            npz_path=pick,
            context="Validation Cockpit NPZ",
        )
    if not isinstance(road_sidecar_wheels, dict):
        road_sidecar_wheels = {}

    t, body, wheel, road, stroke, phi, theta = _extract_mech_arrays(
        df_main,
        dist_unit=dist_unit,
        angle_unit=angle_unit,
        p_atm=float(p_atm),
        zero_baseline=bool(zero_baseline),
        road_override=road_sidecar_wheels,
    )
    road_payload = _filter_road_payload(road, visual_contract)

    if visual_contract.get("road_overlay_text"):
        st.warning(str(visual_contract["road_overlay_text"]))
    if visual_contract.get("solver_points_overlay_text"):
        st.warning(str(visual_contract["solver_points_overlay_text"]))

    if isinstance(geometry_acceptance, dict) and geometry_acceptance:
        ga_gate = str(geometry_acceptance.get("release_gate") or "MISSING")
        ga_reason = str(geometry_acceptance.get("release_gate_reason") or "")
        if ga_gate == "FAIL":
            st.error(f"Геометрический acceptance gate=FAIL: {ga_reason or 'нарушен контракт рама / колесо / дорога'}. Проверьте summary ниже.")
        elif ga_gate == "WARN":
            st.warning(f"Геометрический acceptance gate=WARN: {ga_reason or 'есть warning (missing triplets или XY-расхождения)'}." )
        elif ga_gate == "PASS":
            st.success("Геометрический acceptance gate=PASS: solver-point контракт согласован.")
        else:
            st.info("Геометрический acceptance gate=MISSING: triplet-ы solver-point не найдены.")
        with st.expander("Геометрический acceptance (рама / колесо / дорога)", expanded=False):
            rows = build_geometry_acceptance_rows(geometry_acceptance)
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.text("\n".join(format_geometry_acceptance_summary_lines(geometry_acceptance)))

    st.subheader("Связанные desktop-инструменты")
    st.caption(
        "Когда нужен быстрый визуальный sanity-check вне браузера: Desktop Mnemo удобен для пневматики и причинно-следственных связей, "
        "а Desktop Animator лучше подходит для механики, 2D/3D и дорожного профиля."
    )
    tool_col1, tool_col2 = st.columns(2)
    with tool_col1:
        _page_link_or_info(DESKTOP_MNEMO_PAGE, "Открыть Desktop Mnemo", key="validation_to_mnemo")
    with tool_col2:
        _page_link_or_info(DESKTOP_ANIMATOR_PAGE, "Открыть Desktop Animator", key="validation_to_animator")

    mnemo_event_diag = collect_anim_latest_diagnostics_summary(
        {
            "npz_path": pick,
            "meta": meta if isinstance(meta, dict) else {},
        },
        include_meta=False,
    )
    operator_recommendations = build_anim_operator_recommendations(mnemo_event_diag)
    st.markdown("**Журнал событий Desktop Mnemo**")
    if mnemo_event_diag.get("anim_latest_mnemo_event_log_exists"):
        ev_col1, ev_col2, ev_col3, ev_col4 = st.columns(4)
        ev_col1.metric("Событий", int(mnemo_event_diag.get("anim_latest_mnemo_event_log_event_count") or 0))
        ev_col2.metric("Активных latch", int(mnemo_event_diag.get("anim_latest_mnemo_event_log_active_latch_count") or 0))
        ev_col3.metric("ACK latch", int(mnemo_event_diag.get("anim_latest_mnemo_event_log_acknowledged_latch_count") or 0))
        ev_col4.metric("Режим", str(mnemo_event_diag.get("anim_latest_mnemo_event_log_current_mode") or "—"))
        st.caption(
            "Event-log: "
            f"{mnemo_event_diag.get('anim_latest_mnemo_event_log_ref') or '—'}; "
            f"updated={mnemo_event_diag.get('anim_latest_mnemo_event_log_updated_utc') or '—'}; "
            f"schema={mnemo_event_diag.get('anim_latest_mnemo_event_log_schema_version') or '—'}"
        )
        recent_titles = [
            str(x)
            for x in (mnemo_event_diag.get("anim_latest_mnemo_event_log_recent_titles") or [])
            if str(x).strip()
        ]
        if recent_titles:
            st.info("Недавние события: " + " | ".join(recent_titles[:3]))
    else:
        st.info(
            "Для текущего NPZ журнал событий Desktop Mnemo пока не найден. "
            "Откройте Desktop Mnemo, пройдите сценарий и выполните ACK/экспорт, чтобы добавить event-log в triage."
        )
    if operator_recommendations:
        st.markdown("**Рекомендуемые действия**")
        st.warning("Сначала: " + operator_recommendations[0])
        st.markdown("\n".join(f"{idx}. {item}" for idx, item in enumerate(operator_recommendations, start=1)))

    # --- animation ---
    st.subheader("Механика + дорога (синхронно по времени)")
    path = Path(pick).expanduser().resolve()
    dataset_id = path.stem
    bundle_cache_deps = bun.get("cache_deps") if isinstance(bun, dict) else {}
    if not isinstance(bundle_cache_deps, dict) or not bundle_cache_deps:
        bundle_cache_deps = collect_visual_cache_dependencies(path, meta=meta if isinstance(meta, dict) else {}, context="Validation Cockpit NPZ")
    if view == "2D":
        comp = get_mech_anim_component()
        if comp is None:
            st.warning("Компонент mech_anim недоступен.")
        else:
            comp(
                title="Механика (Validation Cockpit)",
                time=t.tolist(),
                body=body,
                wheel=wheel,
                road=road_payload,
                stroke=stroke,
                phi=phi.tolist(),
                theta=theta.tolist(),
                selected=[],
                meta={"L_stroke_m": float(L_stroke_m), "frame_dt_s": float(np.nanmedian(np.diff(t))) if len(t) > 2 else 0.0, "visual_contract": visual_contract},
                sync_playhead=True,
                playhead_storage_key="pneumo_play_state",
                dataset_id=dataset_id,
                height=int(height),
                key=f"cockpit_mech2d_{dataset_id}",
                default=None,
            )
    else:
        comp3d = get_mech_car3d_component()
        if comp3d is None:
            st.warning("Компонент mech_car3d недоступен.")
        else:
            comp3d(
                title="Машинка (3D Validation Cockpit)",
                time=t.tolist(),
                body={"z": body.get("ЛП", [0.0]*len(t)), "phi": phi.tolist(), "theta": theta.tolist()},
                wheel=wheel,
                road=road_payload,
                stroke=stroke,
                path={},
                geo={"road_mode": "track", "show_road_mesh": True},
                sync_playhead=True,
                playhead_storage_key="pneumo_play_state",
                dataset_id=dataset_id,
                height=int(height),
                key=f"cockpit_mech3d_{dataset_id}",
                default=None,
            )

    # --- static report ---
    st.subheader("Статика (t0): проверка штоков (цель ≈ середина хода)")
    rows = []
    for c in CORNERS:
        s = np.asarray(stroke.get(c, []), dtype=float)
        if s.size == 0:
            continue
        s0 = float(s[0])
        pct = (s0 / float(L_stroke_m) * 100.0) if L_stroke_m > 1e-9 else np.nan
        rows.append({"corner": c, "stroke": s0, "stroke_%": pct, "delta_to_50%": pct - 50.0})
    if rows:
        sdf = pd.DataFrame(rows)
        st.dataframe(sdf, width="stretch")
        bad = sdf["delta_to_50%"].abs().max()
        if np.isfinite(bad) and bad > 20:
            st.warning("Штоки сильно не в середине хода в t0. Это может означать, что начальные условия не статические.")
    else:
        st.info("Не найдены колонки штоков в main/full (шток_*_м).")

    # --- key plots ---
    st.subheader("Ключевые графики (small multiples, одинаковые шкалы)")
    show_key_plots = st.checkbox(
        "Показывать ключевые графики",
        value=True,
        key="val_show_key_plots",
        help="Если выключить — графики не строятся. Полезно на слабых машинах и на больших NPZ.",
    )

    if show_key_plots:
        # heuristics for signals
        sigs = []
        for pref in ["phi_rad", "theta_rad"]:
            if pref in df_main.columns:
                sigs.append(pref)
        for c in CORNERS:
            for pref in [f"z_рамы_{c}_м", f"z_колеса_{c}_м", f"дорога_{c}_м", f"шток_{c}_м"]:
                if pref in df_main.columns:
                    sigs.append(pref)

        sigs = sigs[: min(len(sigs), 16)]
        if sigs:
            if _HAS_PLOTLY:
                # Единый кэш тяжёлых графиков: сохраняем Plotly JSON (быстро восстанавливается).
                try:
                    import plotly.io as pio

                    from pneumo_solver_ui.ui_heavy_cache import cached_json, stable_hash

                    fp = dict(bundle_cache_deps)
                    key = "val_sm_" + stable_hash(
                        {
                            "fp": fp,
                            "sigs": sigs,
                            "dist_unit": dist_unit,
                            "angle_unit": angle_unit,
                            "p_atm": float(p_atm),
                            "zero": bool(zero_baseline),
                            "lock_unit": bool(lock_unit),
                        }
                    )
                    fig_json = cached_json(
                        st,
                        key=key,
                        build=lambda: _plot_small_multiples(
                            df_main,
                            sigs,
                            dist_unit=dist_unit,
                            angle_unit=angle_unit,
                            p_atm=float(p_atm),
                            zero_baseline=bool(zero_baseline),
                            lock_unit=bool(lock_unit),
                        ).to_json(),
                    )
                    fig = pio.from_json(fig_json)
                except Exception:
                    fig = _plot_small_multiples(
                        df_main,
                        sigs,
                        dist_unit=dist_unit,
                        angle_unit=angle_unit,
                        p_atm=float(p_atm),
                        zero_baseline=bool(zero_baseline),
                        lock_unit=bool(lock_unit),
                    )
                st.plotly_chart(fig, width="stretch")
            else:
                fig = _plot_small_multiples_matplotlib(
                    df_main,
                    sigs,
                    dist_unit=dist_unit,
                    angle_unit=angle_unit,
                    p_atm=float(p_atm),
                    zero_baseline=bool(zero_baseline),
                    lock_unit=bool(lock_unit),
                )
                st.pyplot(fig, clear_figure=True)
        else:
            st.info("В main/full не найден стандартный набор сигналов для построения графиков.")
    else:
        st.info("Графики скрыты. Включи чекбокс выше, если нужно построение.")

    # valve states if present
    if "open" in tables and isinstance(tables["open"], pd.DataFrame) and not tables["open"].empty:
        st.subheader("Клапаны (open): быстрый таймлайн")
        show_valves_heatmap = st.checkbox(
            "Показывать таймлайн клапанов (может быть тяжело)",
            value=False,
            key="val_show_valves_timeline",
            help="На больших данных построение теплокарты может занимать заметное время. По умолчанию выключено.",
        )

        if show_valves_heatmap:
            df_open = tables["open"]
            tcol = detect_time_col(df_open) or df_open.columns[0]
            cols = [c for c in df_open.columns if str(c) != str(tcol)]
            cols = cols[: min(40, len(cols))]

            if cols:
                if _HAS_PLOTLY:
                    try:
                        import plotly.io as pio

                        from pneumo_solver_ui.ui_heavy_cache import cached_json, stable_hash

                        fp = dict(bundle_cache_deps)
                        key = "val_openhm_" + stable_hash({"fp": fp, "tcol": str(tcol), "cols": cols})

                        def _build_open_heatmap_json() -> str:
                            tt = extract_time_vector(df_open, tcol)
                            Z = np.vstack([np.asarray(df_open[c].values, dtype=float) for c in cols])
                            figv = go.Figure(data=go.Heatmap(z=Z, x=tt, y=cols, colorscale="Viridis"))
                            figv.update_layout(height=600, margin=dict(l=180, r=10, t=30, b=30))
                            return figv.to_json()

                        fig_json = cached_json(st, key=key, build=_build_open_heatmap_json)
                    except Exception:
                        fig_json = None

                    if fig_json:
                        try:
                            figv = pio.from_json(fig_json)
                        except Exception:
                            figv = None
                    else:
                        tt = extract_time_vector(df_open, tcol)
                        Z = np.vstack([np.asarray(df_open[c].values, dtype=float) for c in cols])
                        figv = go.Figure(data=go.Heatmap(z=Z, x=tt, y=cols, colorscale="Viridis"))
                        figv.update_layout(height=600, margin=dict(l=180, r=10, t=30, b=30))

                    if figv is not None:
                        st.plotly_chart(figv, width="stretch")
                else:
                    figv = _plot_valves_heatmap_matplotlib(df_open, tcol=str(tcol), cols=cols)
                    st.pyplot(figv, clear_figure=True)
            else:
                st.info("open-таблица есть, но нет колонок для клапанов.")
        else:
            st.info("Таймлайн клапанов скрыт. Включи чекбокс выше, если нужно построение.")
