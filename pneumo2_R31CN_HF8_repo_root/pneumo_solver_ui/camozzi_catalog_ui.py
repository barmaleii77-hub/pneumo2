"""🗂️ Camozzi cylinders catalog UI

Цель страницы:
- Дать инженеру дискретный выбор цилиндра из каталога Camozzi (ISO 15552, Series 63).
- Автозаполнить параметры базы (Ø поршня/Ø штока/ход) для Ц1 и/или Ц2.
- Работать без интернета (каталог хранится в репозитории в JSON).

Интеграция с основной страницей:
- Мы НЕ лезем напрямую в внутренние структуры базовой страницы.
- Вместо этого кладём overrides в st.session_state["pending_overrides_si"].
- На главной странице (pneumo_ui_app.py) эти overrides автоматически применяются
  к таблице параметров через преобразователь SI→UI.

Примечание:
Каталожные данные добавлены как вспомогательные (для инженерного цикла).
Параметры, которые мы заполняем, всё равно остаются редактируемыми вручную.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from .suspension_family_contract import AXLES, cylinder_family_key


CATALOG_DIR = Path(__file__).resolve().parent / "catalogs"
CATALOG_JSON = CATALOG_DIR / "camozzi_catalog.json"


@dataclass(frozen=True)
class CamozziCylinderChoice:
    variant_key: str
    bore_mm: int
    rod_mm: int
    stroke_front_mm: int
    stroke_rear_mm: int


@st.cache_data(show_spinner=False)
def _load_camozzi_catalog() -> Dict:
    if not CATALOG_JSON.exists():
        return {}
    return json.loads(CATALOG_JSON.read_text(encoding="utf-8"))


def _variant_label(key: str) -> str:
    # ключи в JSON: round_tube_through_rod / profile_tube_through_rod
    if "round" in key:
        return "Round tube (tie-rod)"
    if "profile" in key:
        return "Profile"
    return key


def _build_df(variants: Dict) -> pd.DataFrame:
    rows: List[Dict] = []
    for vkey, v in (variants or {}).items():
        for it in v.get("items", []) or []:
            rows.append(
                {
                    "variant_key": vkey,
                    "variant": _variant_label(vkey),
                    "bore_mm": int(it.get("bore_mm", 0) or 0),
                    "rod_mm": int(it.get("rod_mm", 0) or 0),
                    "port_thread": str(it.get("port_thread", "")),
                    "rod_thread": str(it.get("rod_thread", "")),
                    "B_mm": float(it.get("B_mm", float("nan"))),
                    "E_mm": float(it.get("E_mm", float("nan"))),
                    "TG_mm": float(it.get("TG_mm", float("nan"))),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Площадь поршня/штока (инфо)
    import numpy as np

    bore_m = df["bore_mm"].to_numpy(dtype=float) / 1000.0
    rod_m = df["rod_mm"].to_numpy(dtype=float) / 1000.0
    A_cap = np.pi * (bore_m**2) / 4.0
    A_rod = np.pi * (rod_m**2) / 4.0
    df["A_cap_cm2"] = (A_cap * 1e4).round(3)
    df["A_rod_cm2"] = (A_rod * 1e4).round(3)
    return df


def _queue_overrides_si(overrides: Dict[str, float]) -> None:
    bag = st.session_state.get("pending_overrides_si")
    if not isinstance(bag, dict):
        bag = {}
    bag.update({str(k): float(v) for k, v in overrides.items()})
    st.session_state["pending_overrides_si"] = bag


def _target_spec(target: str) -> tuple[str, tuple[str, ...], bool]:
    raw = str(target or "").strip()
    if raw in {"Ц1", "Ц1 обе оси"}:
        return "Ц1", tuple(AXLES), True
    if raw in {"Ц2", "Ц2 обе оси"}:
        return "Ц2", tuple(AXLES), True
    if raw == "Ц1 перед":
        return "Ц1", ("перед",), False
    if raw == "Ц1 зад":
        return "Ц1", ("зад",), False
    if raw == "Ц2 перед":
        return "Ц2", ("перед",), False
    if raw == "Ц2 зад":
        return "Ц2", ("зад",), False
    raise ValueError(f"Unsupported Camozzi target: {target!r}")


def _apply_choice(choice: CamozziCylinderChoice, target: str) -> Dict[str, float]:
    cyl, axles, update_legacy = _target_spec(target)
    bore_m = float(choice.bore_mm) / 1000.0
    rod_m = float(choice.rod_mm) / 1000.0
    stroke_f_m = float(choice.stroke_front_mm) / 1000.0
    stroke_r_m = float(choice.stroke_rear_mm) / 1000.0

    out: Dict[str, float] = {}
    for axle in axles:
        out[cylinder_family_key("bore", cyl, axle)] = bore_m
        out[cylinder_family_key("rod", cyl, axle)] = rod_m
        out[cylinder_family_key("stroke", cyl, axle)] = stroke_f_m if axle == "перед" else stroke_r_m

    if update_legacy:
        out[f"диаметр_поршня_{cyl}"] = bore_m
        out[f"диаметр_штока_{cyl}"] = rod_m
        out[f"ход_штока_{cyl}_перед_м"] = stroke_f_m
        out[f"ход_штока_{cyl}_зад_м"] = stroke_r_m

    # Если человек сознательно выбирает цилиндр из Camozzi — логично включить enforce_camozzi_only
    out.setdefault("enforce_camozzi_only", 1.0)
    return out


def run() -> None:
    st.title("Каталог цилиндров Camozzi → автозаполнение параметров")
    st.info(
        "Канонический режим: цилиндры задаются по семействам `Ц1/Ц2 × перед/зад`. "
        "Можно выбрать только перед, только зад или обе оси сразу. При выборе обеих осей "
        "legacy-ключи тоже синхронизируются для обратной совместимости."
    )

    cat = _load_camozzi_catalog()
    cyl = (cat or {}).get("cylinders", {})
    meta = cyl.get("meta", {}) if isinstance(cyl, dict) else {}

    if not cyl:
        st.error(
            "Каталог не найден. Ожидается файл: pneumo_solver_ui/catalogs/camozzi_catalog.json"
        )
        st.info(
            "Если вы собираете релиз/мердж — убедитесь, что каталоги включены в репозиторий."
        )
        return

    src_pdf = meta.get("source_pdf", "")
    src_url = meta.get("source_url", "")
    st.caption(
        "Источник данных: каталог Camozzi (офлайн JSON). "
        + (f"PDF: {src_pdf}. " if src_pdf else "")
        + (f"URL: {src_url}" if src_url else "")
    )

    variants = cyl.get("variants", {})
    df = _build_df(variants)

    stroke_opts = cyl.get("stroke_options_mm", []) if isinstance(cyl, dict) else []
    if not stroke_opts:
        stroke_opts = [50, 80, 100, 125, 160, 200]

    # --- UI ---
    st.subheader("Выбор цилиндра")

    colA, colB = st.columns([1, 1])
    with colA:
        target = st.selectbox(
            "Куда применить",
            ["Ц1 обе оси", "Ц1 перед", "Ц1 зад", "Ц2 обе оси", "Ц2 перед", "Ц2 зад"],
            index=0,
            help=(
                "Семейства считаются независимыми по передней и задней оси. "
                "Выбор «обе оси» сохраняет совместимость со старым общим контрактом канала Ц1/Ц2."
            ),
        )
    with colB:
        variant_key = st.selectbox(
            "Исполнение (вариант)",
            options=sorted(list(variants.keys())),
            format_func=_variant_label,
        )

    dfv = df[df["variant_key"] == variant_key] if not df.empty else df

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        bore_mm = int(
            st.selectbox(
                "Диаметр поршня (bore), мм",
                options=sorted(dfv["bore_mm"].dropna().unique().tolist())
                if not dfv.empty
                else [32, 40, 50, 63, 80, 100, 125],
                index=0,
            )
        )

    dfb = dfv[dfv["bore_mm"] == bore_mm] if not dfv.empty else dfv

    with c2:
        rod_mm = int(
            st.selectbox(
                "Диаметр штока (rod), мм",
                options=sorted(dfb["rod_mm"].dropna().unique().tolist())
                if not dfb.empty
                else [12, 16, 20, 25, 32],
                index=0,
            )
        )

    with c3:
        port_hint = ""
        if not dfb.empty:
            sub = dfb[dfb["rod_mm"] == rod_mm]
            if not sub.empty:
                port_hint = f"port: {sub['port_thread'].iloc[0]} | rod: {sub['rod_thread'].iloc[0]}"
        st.caption(port_hint)

    s1, s2 = st.columns([1, 1])
    with s1:
        stroke_front_mm = int(
            st.selectbox(
                "Ход штока ПЕРЕД, мм",
                options=stroke_opts,
                index=min(2, len(stroke_opts) - 1),
            )
        )
    with s2:
        stroke_rear_mm = int(
            st.selectbox(
                "Ход штока ЗАД, мм",
                options=stroke_opts,
                index=min(2, len(stroke_opts) - 1),
            )
        )

    choice = CamozziCylinderChoice(
        variant_key=variant_key,
        bore_mm=bore_mm,
        rod_mm=rod_mm,
        stroke_front_mm=stroke_front_mm,
        stroke_rear_mm=stroke_rear_mm,
    )

    st.write(
        {
            "variant": _variant_label(choice.variant_key),
            "target": target,
            "bore_mm": choice.bore_mm,
            "rod_mm": choice.rod_mm,
            "stroke_front_mm": choice.stroke_front_mm,
            "stroke_rear_mm": choice.stroke_rear_mm,
        }
    )

    if st.button("Применить к базе (через pending overrides)", type="primary"):
        overrides = _apply_choice(choice, target=target)
        _queue_overrides_si(overrides)
        st.success(
            "Готово. Overrides сохранены. Откройте страницу 'Главная/Расчёт', "
            "чтобы они автоматически применились к таблице параметров."
        )

    with st.expander("Что будет применено (pending_overrides_si)", expanded=False):
        st.json(st.session_state.get("pending_overrides_si", {}))

    st.divider()

    st.subheader("Каталог (таблица)")
    if df.empty:
        st.warning("Каталог пуст или не распарсился.")
    else:
        st.dataframe(
            df.sort_values(["variant_key", "bore_mm", "rod_mm"], ignore_index=True),
            width="stretch",
            hide_index=True,
        )

    st.info(
        "Если вам нужна 'физичная произвольная модель цилиндра' — просто отключайте "
        "enforce_camozzi_only и задавайте диаметры/ход вручную. "
        "Каталог — это инструмент для дискретного подбора реальных компонентов." 
    )
