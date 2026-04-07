# -*- coding: utf-8 -*-
"""ui_preflight.py

Preflight = "чеклист" готовности проекта + подсказка "что делать дальше".

Задачи (по требованиям проекта):
- сделать UI максимально "idiot-proof": пользователь должен видеть следующий шаг;
- минимизировать неоднозначность последовательности действий;
- помогать проверять, что введённые данные и результаты не потерялись;
- не ломать приложение: best-effort, без жёстких зависимостей.

Этот модуль НЕ выполняет расчёты. Он только читает состояние (session_state, файлы workspace)
и аккуратно отображает статусы в sidebar / на отдельной странице.
"""

from __future__ import annotations

import json
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pneumo_solver_ui.entrypoints import (
    canonical_home_page_rel,
    desktop_animator_page_rel,
    env_diagnostics_page_rel,
    validation_web_page_rel,
)


@dataclass
class _Step:
    key: str
    title: str
    ok: bool
    level: str  # ok|warn|err
    detail: str
    page: Optional[str] = None
    action_label: Optional[str] = None


HOME_PAGE = canonical_home_page_rel(here=__file__)
DESKTOP_ANIMATOR_PAGE = desktop_animator_page_rel(here=__file__)
VALIDATION_WEB_PAGE = validation_web_page_rel(here=__file__)
ENV_DIAGNOSTICS_PAGE = env_diagnostics_page_rel(here=__file__)


def _fmt_ts(ts: Any) -> str:
    try:
        tsf = float(ts)
        if tsf <= 0:
            return "—"
        # local time string (no tz fuss inside UI)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tsf))
    except Exception:
        return "—"


def _exports_paths(app_dir: Path) -> Tuple[Path, Path]:
    exports_dir = (app_dir / "pneumo_solver_ui" / "workspace" / "exports").resolve()
    pointer = exports_dir / "anim_latest.json"
    return exports_dir, pointer


def _read_anim_pointer(pointer_path: Path) -> Tuple[Optional[dict], Optional[Path]]:
    if not pointer_path.exists():
        return None, None
    try:
        obj = json.loads(pointer_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    npz_rel = obj.get("npz_path")
    npz_path = None
    if isinstance(npz_rel, str) and npz_rel.strip():
        try:
            npz_path = (pointer_path.parent / npz_rel).resolve()
        except Exception:
            npz_path = None
    return obj, npz_path


def _read_global_anim_pointer() -> Tuple[Optional[dict], Optional[Path]]:
    try:
        from pneumo_solver_ui.run_artifacts import latest_animation_ptr_path
    except Exception:
        return None, None

    try:
        path = latest_animation_ptr_path()
    except Exception:
        return None, None

    obj = None
    try:
        if path.exists():
            obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        obj = None
    return obj, path


def _short_token(token: Any) -> str:
    s = str(token or "").strip()
    if not s:
        return "—"
    if len(s) <= 16:
        return s
    return s[:16] + "…"


def _suite_info(st_mod: Any) -> Tuple[bool, str]:
    """Проверка, что тест-набор загружен и в нём есть включённые тесты."""
    df = st_mod.session_state.get("df_suite_edit", None)
    if df is None:
        return False, "Тест-набор ещё не загружен (зайдите в «Интерфейс»)."

    try:
        import pandas as pd  # type: ignore

        if isinstance(df, pd.DataFrame):
            n = int(len(df))
            if n <= 0:
                return False, "Тест-набор пустой. Добавьте хотя бы один тест."
            if "включен" in df.columns:
                nen = int(pd.Series(df["включен"]).fillna(False).astype(bool).sum())
                if nen <= 0:
                    return False, f"Тестов: {n}. Включённых: 0 (включите хотя бы один)."
                return True, f"Тестов: {n}. Включённых: {nen}."
            return True, f"Тестов: {n}. (Колонка «включен» не найдена — считаем, что всё ок.)"
    except Exception:
        # если pandas недоступен или тип неожиданный — не ломаем UI
        pass

    # fallback: хотя бы объект существует
    try:
        n = len(df)  # type: ignore
        return bool(n), f"Тестов: {n}."
    except Exception:
        return True, "Тест-набор загружен."


def _baseline_info(st_mod: Any) -> Tuple[bool, str]:
    ran = st_mod.session_state.get("baseline_ran_tests", None)
    ts = st_mod.session_state.get("baseline_updated_ts", None)

    try:
        n = len(ran) if isinstance(ran, (list, tuple)) else 0
    except Exception:
        n = 0

    if n <= 0:
        return False, "Baseline ещё не запускался (или нет результатов в session_state)."

    return True, f"Прогнано тестов: {n}. Обновлено: {_fmt_ts(ts)}."


def _autosave_info(st_mod: Any) -> Tuple[bool, str]:
    enabled = bool(st_mod.session_state.get("ui_autosave_enabled", True))

    # проверим, что директория состояния доступна
    try:
        from pneumo_solver_ui.ui_persistence import pick_state_dir

        state_dir = pick_state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        test_file = state_dir / ".write_test"
        try:
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)  # type: ignore[arg-type]
            writable = True
        except Exception:
            writable = False

        if not enabled:
            return False, "Автосохранение отключено (можно включить в sidebar → Автосохранение)."
        if not writable:
            return False, f"Автосохранение включено, но папка состояния не пишется: {state_dir}"
        return True, f"Автосохранение включено. Папка состояния: {state_dir}"
    except Exception:
        if not enabled:
            return False, "Автосохранение отключено."
        return True, "Автосохранение включено."


def _desktop_deps_info() -> Tuple[bool, str]:
    # Быстро и без падений
    try:
        import PySide6  # noqa: F401
        has_pyside6 = True
    except Exception:
        has_pyside6 = False

    try:
        import pyqtgraph  # noqa: F401
        has_pg = True
    except Exception:
        has_pg = False

    try:
        import pyqtgraph.opengl  # noqa: F401
        has_gl = True
    except Exception:
        has_gl = False

    try:
        import OpenGL_accelerate  # noqa: F401
        has_gl_accel = True
    except Exception:
        has_gl_accel = False

    ok = bool(has_pyside6 and has_pg)
    if ok and has_gl and has_gl_accel:
        return True, "PySide6 + pyqtgraph + OpenGL готовы. OpenGL_accelerate найден."
    if ok and has_gl and not has_gl_accel:
        return True, "PySide6 + pyqtgraph + OpenGL готовы, но OpenGL_accelerate не найден (3D будет работать, но медленнее)."
    if ok and not has_gl:
        return True, "PySide6 + pyqtgraph готовы. OpenGL не найден (можно --no-gl)."

    need = []
    if not has_pyside6:
        need.append("PySide6")
    if not has_pg:
        need.append("pyqtgraph")
    if not has_gl:
        need.append("PyOpenGL")
    return False, "Не хватает зависимостей: " + ", ".join(need)


def collect_steps(st_mod: Any, app_dir: Path) -> Dict[str, _Step]:
    steps: Dict[str, _Step] = {}

    ok, detail = _autosave_info(st_mod)
    steps["autosave"] = _Step(
        key="autosave",
        title="Автосохранение (UI)",
        ok=ok,
        level="ok" if ok else "warn",
        detail=detail,
        page=None,
        action_label=None,
    )

    ok, detail = _suite_info(st_mod)
    steps["suite"] = _Step(
        key="suite",
        title="Тест‑набор",
        ok=ok,
        level="ok" if ok else "warn",
        detail=detail,
        page=HOME_PAGE,
        action_label="Открыть Интерфейс",
    )

    ok, detail = _baseline_info(st_mod)
    steps["baseline"] = _Step(
        key="baseline",
        title="Baseline",
        ok=ok,
        level="ok" if ok else "warn",
        detail=detail,
        page=HOME_PAGE,
        action_label="Открыть Интерфейс",
    )

    exports_dir, pointer_path = _exports_paths(app_dir)
    obj, npz_path = _read_anim_pointer(pointer_path)
    global_obj, global_pointer_path = _read_global_anim_pointer()
    local_token = str((obj or {}).get("visual_cache_token") or "").strip()
    global_token = str((global_obj or {}).get("visual_cache_token") or "").strip()
    reload_inputs = list((obj or {}).get("visual_reload_inputs") or (global_obj or {}).get("visual_reload_inputs") or [])
    detail_lines = []
    if obj is None:
        ok = False
        detail_lines.append("anim_latest.json не найден. Запустите детальный прогон с авто‑экспортом anim_latest.")
    else:
        if npz_path is not None and npz_path.exists():
            try:
                mb = npz_path.stat().st_size / 1024.0 / 1024.0
                detail_lines.append(f"Pointer OK. NPZ: {npz_path.name} ({mb:.2f} MB).")
            except Exception:
                detail_lines.append(f"Pointer OK. NPZ: {npz_path.name}.")
            ok = True
        else:
            ok = False
            detail_lines.append("anim_latest.json найден, но NPZ не найден по указанному пути.")

    detail_lines.append(f"Папка exports: {exports_dir}")
    detail_lines.append(f"visual_cache_token: {_short_token(local_token or global_token)}")
    if reload_inputs:
        detail_lines.append("reload inputs: " + ", ".join(str(x) for x in reload_inputs))
    if global_pointer_path is not None:
        detail_lines.append(f"global pointer: {global_pointer_path}")
        if global_obj is None:
            detail_lines.append("global pointer status: отсутствует или не читается")
        elif local_token and global_token:
            detail_lines.append("global token sync: OK" if local_token == global_token else "global token sync: MISMATCH")
        elif global_token:
            detail_lines.append("global token sync: only global token available")

    steps["export"] = _Step(
        key="export",
        title="Экспорт для Desktop Animator",
        ok=ok,
        level="ok" if ok else "warn",
        detail="\n".join(detail_lines),
        page=DESKTOP_ANIMATOR_PAGE,
        action_label="Открыть Desktop Animator",
    )

    ok, detail = _desktop_deps_info()
    steps["desktop"] = _Step(
        key="desktop",
        title="Зависимости Desktop Animator",
        ok=ok,
        level="ok" if ok else "warn",
        detail=detail,
        page=DESKTOP_ANIMATOR_PAGE,
        action_label="Открыть Desktop Animator",
    )

    # Небольшая подсказка про окружение
    steps["env"] = _Step(
        key="env",
        title="Окружение",
        ok=True,
        level="ok",
        detail=f"OS: {platform.system()} | Python: {platform.python_version()}",
        page=ENV_DIAGNOSTICS_PAGE,
        action_label="Диагностика",
    )

    return steps


def _pick_next_page(steps: Dict[str, _Step]) -> Tuple[str, str]:
    """Вернуть (page_path, label) для "следующего шага"."""

    # приоритет: suite -> baseline -> export -> desktop -> validation
    if not steps.get("suite", _Step("", "", True, "ok", "")).ok:
        return "pneumo_solver_ui/pneumo_ui_app.py", "Открыть Интерфейс и настроить тест‑набор"
    if not steps.get("baseline", _Step("", "", True, "ok", "")).ok:
        return "pneumo_solver_ui/pneumo_ui_app.py", "Запустить Baseline"
    if not steps.get("export", _Step("", "", True, "ok", "")).ok:
        return "pneumo_solver_ui/pneumo_ui_app.py", "Сделать детальный прогон + экспорт anim_latest"
    if not steps.get("desktop", _Step("", "", True, "ok", "")).ok:
        return "pneumo_solver_ui/pages/08_DesktopAnimator.py", "Установить/запустить Desktop Animator"

    return "pneumo_solver_ui/pages/09_Validation_Web.py", "Перейти к Валидации (Web)"


def _pick_next_page_canonical(steps: Dict[str, _Step]) -> Tuple[str, str]:
    """Return canonical relative page targets for the recommended next step."""
    if not steps.get("suite", _Step("", "", True, "ok", "")).ok:
        return HOME_PAGE, "РћС‚РєСЂС‹С‚СЊ РРЅС‚РµСЂС„РµР№СЃ Рё РЅР°СЃС‚СЂРѕРёС‚СЊ С‚РµСЃС‚вЂ‘РЅР°Р±РѕСЂ"
    if not steps.get("baseline", _Step("", "", True, "ok", "")).ok:
        return HOME_PAGE, "Р—Р°РїСѓСЃС‚РёС‚СЊ Baseline"
    if not steps.get("export", _Step("", "", True, "ok", "")).ok:
        return HOME_PAGE, "РЎРґРµР»Р°С‚СЊ РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ + СЌРєСЃРїРѕСЂС‚ anim_latest"
    if not steps.get("desktop", _Step("", "", True, "ok", "")).ok:
        return DESKTOP_ANIMATOR_PAGE, "РЈСЃС‚Р°РЅРѕРІРёС‚СЊ/Р·Р°РїСѓСЃС‚РёС‚СЊ Desktop Animator"
    return VALIDATION_WEB_PAGE, "РџРµСЂРµР№С‚Рё Рє Р’Р°Р»РёРґР°С†РёРё (Web)"


_pick_next_page = _pick_next_page_canonical


def _nav_link(st_mod: Any, page: str, label: str, *, key: str) -> None:
    """Безопасная навигация: st.page_link -> fallback на кнопку + st.switch_page."""
    try:
        if hasattr(st_mod, "page_link"):
            st_mod.page_link(page, label=label, width="stretch")
            return
    except Exception:
        pass

    # fallback
    if st_mod.button(label, key=key, width="stretch"):
        try:
            if hasattr(st_mod, "switch_page"):
                st_mod.switch_page(page)
            else:
                st_mod.info("Используйте меню навигации слева.")
        except Exception:
            st_mod.info("Используйте меню навигации слева.")


def render_preflight_sidebar(st_mod: Any, app_dir: Path) -> None:
    """Компактный preflight в sidebar."""
    st_mod.markdown("### 🚦 Preflight")
    st_mod.caption("Быстрая проверка готовности + подсказка следующего шага.")

    steps = collect_steps(st_mod, Path(app_dir))
    next_page, next_label = _pick_next_page(steps)

    st_mod.info(f"**Следующий шаг:** {next_label}")
    _nav_link(st_mod, next_page, "➡️ " + next_label, key="preflight_next")

    with st_mod.expander("Статусы", expanded=False):
        for step in ["autosave", "suite", "baseline", "export", "desktop", "env"]:
            s = steps.get(step)
            if not s:
                continue
            icon = "✅" if s.ok else ("⚠️" if s.level == "warn" else "❌")
            st_mod.markdown(f"**{icon} {s.title}**")
            st_mod.caption(s.detail)
            if s.page and s.action_label:
                _nav_link(st_mod, s.page, s.action_label, key=f"preflight_go_{s.key}")
            st_mod.divider()


def render_preflight_page(st_mod: Any, app_dir: Path) -> None:
    """Полноэкранная страница preflight (подробнее, чем sidebar)."""
    st_mod.title("🚦 Preflight: готовность проекта")
    st_mod.caption(
        "Это чеклист, который помогает не потеряться в последовательности действий и не забыть важные шаги. "
        "Он ничего не рассчитывает — только проверяет состояние UI/файлов."
    )

    steps = collect_steps(st_mod, Path(app_dir))
    next_page, next_label = _pick_next_page(steps)

    st_mod.subheader("Следующий рекомендуемый шаг")
    st_mod.success(next_label)
    _nav_link(st_mod, next_page, "➡️ Перейти", key="preflight_next_page")

    st_mod.divider()
    st_mod.subheader("Чеклист")

    for k in ["autosave", "suite", "baseline", "export", "desktop", "env"]:
        s = steps.get(k)
        if not s:
            continue
        if s.ok:
            st_mod.success(s.title)
        else:
            st_mod.warning(s.title)
        st_mod.write(s.detail)
        if s.page and s.action_label:
            _nav_link(st_mod, s.page, s.action_label, key=f"preflight_go2_{s.key}")
        st_mod.divider()
