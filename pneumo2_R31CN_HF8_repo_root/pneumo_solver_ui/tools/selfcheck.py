# -*- coding: utf-8 -*-
"""Lightweight self-checks.

Назначение
----------
Самопроверка должна:
- выполняться быстро (секунды)
- не запускать долгих расчётов модели
- находить типовые причины «не работает UI/анимация/графики»:
  * не установлены зависимости
  * отсутствуют ассеты компонентов
  * повреждена структура проекта

Самопроверка **не** заменяет полный диагностический прогон.
Для глубокой проверки см. «Инструменты → Диагностика».
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

from pneumo_solver_ui.entrypoints import ui_entrypoint_specs


@dataclass
class CheckResult:
    check_id: str
    title: str
    ok: bool
    level: str = "error"  # error|warn|info
    details: str = ""
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _file_exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def run_quick_selfcheck(project_root: str | os.PathLike) -> List[dict]:
    """Run fast checks. Returns list[dict] to make Streamlit session_state JSON-friendly."""

    root = Path(project_root).resolve()
    out: List[CheckResult] = []

    # 1) Python version
    py_ok = sys.version_info >= (3, 10)
    out.append(
        CheckResult(
            check_id="python_version",
            title="Версия Python (>= 3.10)",
            ok=py_ok,
            level="error" if not py_ok else "info",
            details=f"Текущая версия: {sys.version.split()[0]}",
            hint="Установите Python 3.11+ (рекомендуется) и пересоздайте виртуальное окружение." if not py_ok else "",
        )
    )

    # 2) Required modules
    required = [
        ("streamlit", "Streamlit"),
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("plotly", "Plotly (графики)"),
        ("matplotlib", "Matplotlib (fallback-графика/анимация)"),
    ]
    for mod, title in required:
        ok = _has_module(mod)
        out.append(
            CheckResult(
                check_id=f"import_{mod}",
                title=f"Зависимость установлена: {title}",
                ok=ok,
                level="error" if not ok else "info",
                details="OK" if ok else "Модуль не найден",
                hint=(
                    "Запустите START_PNEUMO_APP.py (он сам ставит зависимости) "
                    "или выполните: python -m pip install -r requirements.txt"
                    if not ok
                    else ""
                ),
            )
        )

    optional = [
        ("streamlit_autorefresh", "streamlit-autorefresh (удобно для анимаций)", "warn"),
        ("scipy", "SciPy (часть вычислений)", "warn"),
    ]
    for mod, title, lvl in optional:
        ok = _has_module(mod)
        out.append(
            CheckResult(
                check_id=f"import_opt_{mod}",
                title=f"Опционально: {title}",
                ok=ok,
                level=("info" if ok else lvl),
                details="OK" if ok else "Не установлено",
                hint="Можно установить из requirements.txt (не критично для запуска UI)." if not ok else "",
            )
        )

    # 3) Project structure
    must_have_files = [
        ("START_PNEUMO_APP.py", "Windows/bootstrap launcher"),
        ("requirements.txt", "Runtime dependency manifest"),
    ]
    must_have_files.extend((spec.rel_path, spec.role) for spec in ui_entrypoint_specs(here=__file__))
    for rel, role in must_have_files:
        ok = _file_exists(root, rel)
        out.append(
            CheckResult(
                check_id=f"file_{rel}",
                title=f"Файл на месте: {rel}",
                ok=ok,
                level="error" if not ok else "info",
                details="OK" if ok else "Не найден",
                hint="Проверьте, что вы распаковали архив полностью, без потерь." if not ok else "",
            )
        )

    # 4) Component assets (animation)
    # Components assets live under pneumo_solver_ui/components/
    # (Ранее здесь проверялся путь без префикса, что давало ложные "missing".)
    comp_assets = [
        ("pneumo_solver_ui/components/mech_anim/index.html", "2D-анимация подвески (mech_anim)"),
        ("pneumo_solver_ui/components/mech_car3d/index.html", "3D-анимация автомобиля (mech_car3d)"),
        ("pneumo_solver_ui/components/pneumo_svg_flow/index.html", "Pneumo SVG Flow (pneumo_svg_flow)"),
        ("pneumo_solver_ui/components/playhead_ctrl/index.html", "Playhead Control (playhead_ctrl)"),
        ("pneumo_solver_ui/components/corner_heatmap_live/index.html", "Corner Heatmap Live (corner_heatmap_live)"),
        ("pneumo_solver_ui/components/minimap_live/index.html", "Minimap Live (minimap_live)"),
        ("pneumo_solver_ui/components/road_profile_live/index.html", "Road Profile Live (road_profile_live)"),
        ("pneumo_solver_ui/components/mech_anim_quad/index.html", "Mech Anim Quad (mech_anim_quad)"),
    ]
    for rel, title in comp_assets:
        ok = _file_exists(root, rel)
        out.append(
            CheckResult(
                check_id=f"asset_{rel}",
                title=f"Ассеты компонента: {title}",
                ok=ok,
                level="error" if not ok else "info",
                details="OK" if ok else "Файл отсутствует",
                hint=(
                    "Если ассеты отсутствуют — анимация перейдёт в fallback. "
                    "Перераспакуйте релиз или возьмите полный пакет."
                    if not ok
                    else ""
                ),
            )
        )

    # 5) Import of main UI module (cheap smoke-test)
    # Не импортируем тяжёлые модули модели. Импорт UI файла сам по себе должен отработать.
    ui_import_ok = True
    ui_import_err = ""
    try:
        import pneumo_solver_ui  # noqa: F401
        # Try import a small helper that should not trigger heavy calc
        import pneumo_solver_ui.pneumo_ui_app  # noqa: F401
    except Exception as e:  # noqa: BLE001
        ui_import_ok = False
        ui_import_err = f"{type(e).__name__}: {e}"

    out.append(
        CheckResult(
            check_id="import_ui",
            title="Импорт UI-модуля (smoke-test)",
            ok=ui_import_ok,
            level="error" if not ui_import_ok else "info",
            details="OK" if ui_import_ok else ui_import_err,
            hint=(
                "Ошибка импорта почти всегда означает конфликт версий зависимостей или повреждение файлов. "
                "Запустите «Инструменты → Диагностика» и посмотрите логи."
                if not ui_import_ok
                else ""
            ),
        )
    )


    # 5b) Page registry entries (must not crash on metadata)
    page_reg_ok = True
    page_reg_err = ""
    page_reg_n = 0
    try:
        from pneumo_solver_ui.page_registry import get_entries as _get_entries

        _entries = _get_entries()
        page_reg_n = len(_entries)
        if page_reg_n <= 0:
            raise RuntimeError("entries list is empty")
    except Exception as e:  # noqa: BLE001
        page_reg_ok = False
        page_reg_err = f"{type(e).__name__}: {e}"

    out.append(
        CheckResult(
            check_id="page_registry_entries",
            title="Реестр страниц: сборка entries без ошибок",
            ok=page_reg_ok,
            level="error" if not page_reg_ok else "info",
            details=(f"entries={page_reg_n}" if page_reg_ok else page_reg_err),
            hint=(
                "Если падает реестр страниц — обычно это ошибка метаданных или несовместимость Streamlit API. "
                "Проверьте pneumo_solver_ui/page_registry.py."
                if not page_reg_ok
                else ""
            ),
        )
    )



    # 6) UI traceability guard (не строгий)
    #
    # Ловит регрессии вида: «куда-то пропала страница/раздел».
    # Не валит приложение, но явно показывает предупреждение.
    try:
        from pneumo_solver_ui.tools.ui_traceability import (
            snapshot_path as _ui_snap_path,
            load_snapshot as _ui_load_snapshot,
            collect_ui_files as _ui_collect,
            compare_snapshot as _ui_compare,
        )

        sp = _ui_snap_path()
        if not sp.exists():
            out.append(
                CheckResult(
                    check_id="ui_trace_guard",
                    title="UI traceability guard (страницы не пропали)",
                    ok=False,
                    level="warn",
                    details="Snapshot не найден: ui_trace_snapshot.json",
                    hint=(
                        "Это не критично. Для стабильности релиза держите snapshot в репозитории. "
                        "(pneumo_solver_ui/tools/ui_trace_snapshot.json)"
                    ),
                )
            )
        else:
            snap = _ui_load_snapshot(sp)
            cur = _ui_collect(root)
            missing, extra = _ui_compare(snap, cur)

            ok = len(missing) == 0
            details = f"missing={len(missing)}, extra={len(extra)}"
            if missing:
                preview = "\n- ".join(missing[:15])
                details += "\nПотеряны страницы (первые 15):\n- " + preview
                if len(missing) > 15:
                    details += f"\n... и ещё {len(missing) - 15}"

            out.append(
                CheckResult(
                    check_id="ui_trace_guard",
                    title="UI traceability guard (страницы не пропали)",
                    ok=ok,
                    level=("info" if ok else "warn"),
                    details=details,
                    hint=(
                        "Если исчезновение было НЕ намеренным — восстановите страницы/маршруты. "
                        "Если намеренным — обновите snapshot (pneumo_solver_ui/tools/ui_trace_snapshot.json)."
                        if not ok
                        else ""
                    ),
                )
            )

    except Exception as e:  # noqa: BLE001
        out.append(
            CheckResult(
                check_id="ui_trace_guard",
                title="UI traceability guard (страницы не пропали)",
                ok=False,
                level="warn",
                details=f"{type(e).__name__}: {e}",
                hint="Если самопроверка падает — это тоже сигнал. Проверьте структуру проекта.",
            )
        )

    # Finalize
    results = [c.to_dict() for c in out]
    return results


def summarize_selfcheck(results: Iterable[dict]) -> tuple[bool, int, int]:
    """Return (ok, errors, warnings)."""
    errors = 0
    warns = 0
    for r in results:
        if r.get("ok"):
            continue
        lvl = (r.get("level") or "error").lower()
        if lvl == "warn":
            warns += 1
        else:
            errors += 1
    return (errors == 0), errors, warns


def save_selfcheck_report(results: List[dict], path: str | os.PathLike) -> str:
    """Save report as JSON. Returns absolute path."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": time.time(),
        "results": results,
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def get_selfcheck_signals(project_root: Path) -> List[tuple[str, bool, str]]:
    """Compact signals for the sidebar (non-strict).

    Returns tuples: (name, ok, message)
    """

    root = Path(project_root).resolve()
    res = run_quick_selfcheck(root)

    wanted = {
        "python_version",
        "import_streamlit",
        "import_numpy",
        "import_pandas",
        "import_plotly",
        "import_ui",
        "ui_trace_guard",
    }

    out: List[tuple[str, bool, str]] = []
    for r in res:
        if r.get("check_id") in wanted:
            out.append((str(r.get("title") or r.get("check_id")), bool(r.get("ok")), str(r.get("details") or "")))

    # Registry completeness (warn-only)
    try:
        from pneumo_solver_ui.ui_pages_registry import build_registry

        reg = build_registry(repo=root, include_legacy=True, include_main_unified=True)
        missing = [p.page_id for p in reg if p.status == "READY" and (not p.short_help.strip() or not p.tags)]
        out.append(("UI registry metadata", len(missing) == 0, "OK" if not missing else f"missing={len(missing)}"))
    except Exception as e:  # noqa: BLE001
        out.append(("UI registry metadata", False, f"Ошибка: {type(e).__name__}: {e}"))

    return out
