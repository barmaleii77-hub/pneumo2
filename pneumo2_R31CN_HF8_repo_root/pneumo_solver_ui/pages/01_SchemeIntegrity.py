# -*- coding: utf-8 -*-
"""01_SchemeIntegrity.py — контроль целостности пневмосхемы.

Страница:
- показывает сохранённый fingerprint схемы (scheme_fingerprint.json)
- пересчитывает fingerprint по текущему build_network_full()
- проверяет, что все camozzi_коды схемы есть в component_passport.json
- при необходимости позволяет перегенерировать fingerprint (обновить файл)

Это НЕ электронный «контроллер», а инструмент инженерной дисциплины:
когда мы калибруем параметры, мы хотим быть уверены, что топология и набор компонентов
случайно не изменились.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled




bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
    _ui_bootstrap(st)
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "pneumo_solver_ui"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    st.title("Целостность схемы")
    st.caption("Fingerprint схемы + аудит camozzi-only для текущей конфигурации")

    base_path = MODEL_DIR / "default_base.json"
    pp_path = MODEL_DIR / "component_passport.json"

    if not base_path.exists():
        st.error(f"Не найден default_base.json: {base_path}")
        return

    base = _load_json(base_path)

    fp_rel = str(base.get("scheme_fingerprint_file") or "scheme_fingerprint.json")
    fp_path = (MODEL_DIR / fp_rel).resolve()

    enforce_f = bool(base.get("enforce_scheme_integrity", True))
    enforce_c = bool(base.get("enforce_camozzi_only", True))

    col1, col2, col3 = st.columns(3)
    col1.metric("Контроль целостности", str(enforce_f))
    col2.metric("Только Camozzi", str(enforce_c))
    col3.metric("Файл fingerprint", fp_path.name)

    # --- imports (deferred) ---
    try:
        from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as model
        from pneumo_solver_ui.scheme_integrity import (
            compute_fingerprint,
            assert_camozzi_only,
        )
    except Exception as e:
        st.error("Не удалось импортировать модель/модуль scheme_integrity")
        st.exception(e)
        return

    st.subheader("1) Сохранённый fingerprint")
    if fp_path.exists():
        saved = _load_json(fp_path)
        st.json(saved, expanded=False)
    else:
        st.warning(
            "Fingerprint файл отсутствует. Это не ошибка, но enforce_scheme_integrity=True "
            "может приводить к исключению при запуске модели."
        )
        saved = {}

    st.subheader("2) Текущий fingerprint по build_network_full()")
    try:
        nodes, _idx, edges, _B = model.build_network_full(base)
        cur = compute_fingerprint(nodes, edges)
        st.json(cur, expanded=False)
    except Exception as e:
        st.error("Не удалось построить сеть/вычислить fingerprint")
        st.exception(e)
        return

    st.subheader("3) Сравнение")
    same = bool(saved) and ((saved.get("sha256") or saved.get("fingerprint")) == cur.get("sha256"))
    if same:
        st.success("✅ Fingerprint совпадает — топология/коды схемы не изменились")
    else:
        st.error("❌ Fingerprint НЕ совпадает")
        if saved:
            st.write("saved sha256:", (saved.get("sha256") or saved.get("fingerprint")))
        st.write("current sha256:", cur.get("sha256"))

    st.subheader("4) Camozzi-only аудит")
    if not pp_path.exists():
        st.error(f"Не найден passport: {pp_path}")
    else:
        try:
            # assert_camozzi_only выбрасывает исключение при первой ошибке
            assert_camozzi_only(edges, str(pp_path))
            st.success("✅ Все camozzi_коды схемы присутствуют в component_passport.json")
        except Exception as e:
            st.error("❌ Обнаружены отсутствующие/ошибочные camozzi_коды")
            st.exception(e)

    st.subheader("5) Обновление fingerprint")
    st.info(
        "Используйте это только если вы ОСОЗНАННО меняли схему. "
        "Для простого подбора параметров fingerprint обновлять не нужно."
    )
    if st.button("Записать текущий fingerprint в файл"):
        try:
            fp_path.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
            st.success(f"Fingerprint обновлён: {fp_path}")
        except Exception as e:
            st.error("Не удалось записать fingerprint")
            st.exception(e)


if __name__ == "__main__":
    main()

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
