# -*- coding: utf-8 -*-
"""ui_selfcheck.py

Лёгкие автономные самопроверки, связанные с UI/GUI.

Важно: здесь **нет Streamlit‑кода** — файл можно запускать из консоли
или вызывать из страниц Streamlit, не поднимая сервер.

Цель
----
Ловить регрессии UI/UX ещё до того, как пользователь наткнётся на них:
- битые пути страниц в app.py
- неудачная русификация (видимая пользователю)
- отсутствие обязательных UI‑модулей
- покрытие автосохранения ключевых UI ключей
- русификация HTML‑компонента пневмосхемы

Запуск
------
python -m pneumo_solver_ui.ui_selfcheck

Выход: JSON‑отчёт. Если есть ошибки -> код возврата 2.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List


# Чтобы модуль можно было запускать напрямую как скрипт:
#   python pneumo_solver_ui/ui_selfcheck.py
# нужно добавить корень репозитория в sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str = ""
    details: Dict[str, Any] | None = None


def _ok(name: str, message: str = "", **details: Any) -> CheckResult:
    return CheckResult(name=name, ok=True, message=message, details=(details or None))


def _fail(name: str, message: str, **details: Any) -> CheckResult:
    return CheckResult(name=name, ok=False, message=message, details=(details or None))


_ASCII_PAGE_RE = re.compile(r"^[0-9A-Za-z_\-\.]+\.py$")


def _is_ascii_page_filename(fname: str) -> bool:
    """Безопасное для ZIP/Windows имя файла страницы.

    Важно: локализация должна быть в *title=* и строках UI, а не в имени файла.
    """

    if fname == "__init__.py":
        return True
    return bool(_ASCII_PAGE_RE.match(fname))


def _extract_app_page_paths(app_text: str) -> List[str]:
    """Извлечь пути к файлам страниц из app.py.

    app.py использует helper p("...") для формирования путей.
    Регулярные выражения по st.Page(...) в целом хрупкие из‑за вложенных скобок,
    поэтому здесь мы просто ищем все вызовы p("...") и фильтруем по pages/.
    """

    paths: List[str] = []
    # 1) p("...") / p('...')
    for pm in re.finditer(r"\bp\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)", app_text):
        pp = pm.group(1)
        if "pneumo_solver_ui/pages/" in pp and pp.endswith(".py"):
            paths.append(pp)
    # 2) На всякий случай — st.Page("...") без p()
    for pm in re.finditer(r"st\.Page\(\s*[\'\"]([^\'\"]+)[\'\"]", app_text):
        pp = pm.group(1)
        if "pneumo_solver_ui/pages/" in pp and pp.endswith(".py"):
            paths.append(pp)
    # unique, keep order
    seen = set()
    out: List[str] = []
    for pp in paths:
        if pp in seen:
            continue
        seen.add(pp)
        out.append(pp)
    return out


def _extract_app_page_titles(app_text: str) -> List[str]:
    titles = []
    for m in re.finditer(r"title\s*=\s*['\"]([^'\"]+)['\"]", app_text):
        titles.append(m.group(1))
    return titles


def _has_cyrillic(s: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", s or ""))


def run_ui_selfcheck(repo_root: Path) -> Dict[str, Any]:
    """Запуск самопроверок. Возвращает JSON‑совместимый отчёт."""

    results: List[CheckResult] = []

    # --- 1) Страницы: имена файлов должны быть ASCII (локализация делается title=...) ---
    pages_dir = repo_root / "pneumo_solver_ui" / "pages"
    if pages_dir.exists():
        bad = []
        for p in sorted(pages_dir.glob("*.py")):
            if not _is_ascii_page_filename(p.name):
                bad.append(p.name)
        if bad:
            results.append(
                _fail(
                    "pages_filenames_ascii",
                    "Есть страницы с небезопасными именами файлов (не ASCII).",
                    bad=bad,
                )
            )
        else:
            results.append(_ok("pages_filenames_ascii", "Имена файлов страниц выглядят безопасными (ASCII)."))
    else:
        results.append(_fail("pages_filenames_ascii", "Не найден каталог pages", path=str(pages_dir)))

    # --- 2) Генератор сценариев должен создавать корректные CSV ---
    try:
        from pneumo_solver_ui.scenario_generator import (
            ISO8608Spec,
            ManeuverSpec,
            generate_iso8608_road_csv,
            generate_maneuver_csv,
        )

        tmp = repo_root / "pneumo_solver_ui" / "workspace" / "_selfcheck_tmp"
        tmp.mkdir(parents=True, exist_ok=True)

        road_p = tmp / "road_selfcheck.csv"
        man_p = tmp / "maneuver_selfcheck.csv"

        iso = ISO8608Spec(road_class="C", gd_pick="mid")
        _, road_meta = generate_iso8608_road_csv(
            out_csv=road_p,
            dt=0.01,
            t_end=2.0,
            speed_mps=10.0,
            wheelbase_m=1.6,
            spec=iso,
            dx_m=0.02,
            left_right_coherence=0.6,
            seed=123,
        )
        if (not road_p.exists()) or (road_p.stat().st_size < 50):
            results.append(_fail("scenario_generator_road_csv", "road_csv не создан или пустой", path=str(road_p)))
        else:
            head = road_p.read_text("utf-8", errors="ignore").splitlines()[0]
            ok_cols = all(c in head for c in ["t", "z0", "z1", "z2", "z3"])
            results.append(
                _ok("scenario_generator_road_csv", "road_csv создан", meta=road_meta)
                if ok_cols
                else _fail("scenario_generator_road_csv", "Неверные колонки в road_csv", header=head)
            )

        ms = ManeuverSpec(p_accel_per_s=0.06, p_brake_per_s=0.06, p_turn_per_s=0.05)
        _, man_meta = generate_maneuver_csv(out_csv=man_p, dt=0.01, t_end=2.0, spec=ms, seed=123)
        if (not man_p.exists()) or (man_p.stat().st_size < 30):
            results.append(_fail("scenario_generator_axay_csv", "axay_csv не создан или пустой", path=str(man_p)))
        else:
            head = man_p.read_text("utf-8", errors="ignore").splitlines()[0]
            ok_cols = all(c in head for c in ["t", "ax", "ay"])
            results.append(
                _ok("scenario_generator_axay_csv", "axay_csv создан", meta=man_meta)
                if ok_cols
                else _fail("scenario_generator_axay_csv", "Неверные колонки в axay_csv", header=head)
            )

        # cleanup
        for fp in [road_p, man_p]:
            try:
                fp.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            if tmp.exists() and (len(list(tmp.iterdir())) == 0):
                tmp.rmdir()
        except Exception:
            pass

    except Exception as ex:
        results.append(
            _fail(
                "scenario_generator_import",
                "Не удалось импортировать/выполнить генератор сценариев",
                error=repr(ex),
            )
        )

    # --- 3) Навигация в app.py должна ссылаться на существующие страницы ---
    try:
        app_py = repo_root / "app.py"
        if not app_py.exists():
            results.append(_fail("app_py_exists", "Не найден app.py (entrypoint Streamlit)", path=str(app_py)))
        else:
            txt = app_py.read_text("utf-8", errors="ignore")
            page_paths = _extract_app_page_paths(txt)
            missing = []
            for pp in page_paths:
                if not (repo_root / pp).exists():
                    missing.append(pp)

            if missing:
                results.append(
                    _fail(
                        "app_navigation_paths",
                        "В app.py есть ссылки на отсутствующие файлы страниц",
                        missing=missing,
                        count=len(page_paths),
                    )
                )
            else:
                results.append(_ok("app_navigation_paths", "Навигация app.py: пути страниц существуют", count=len(page_paths)))

            # --- 3b) Названия страниц, которые видит пользователь, должны быть русскими ---
            titles = _extract_app_page_titles(txt)
            if titles:
                non_ru = [t for t in titles if not _has_cyrillic(t)]
                if non_ru:
                    results.append(
                        _fail(
                            "app_titles_ru",
                            "Не все title= в app.py содержат кириллицу (видимая локализация может быть неполной).",
                            non_ru=non_ru,
                            count=len(titles),
                        )
                    )
                else:
                    results.append(_ok("app_titles_ru", "title= в app.py выглядят русифицированными", count=len(titles)))
            else:
                # Начиная с новых релизов, app.py может строить навигацию через page_registry
                # (без явных title= в app.py). Это не ошибка.
                if "build_streamlit_pages" in txt or "page_registry" in txt:
                    results.append(
                        _ok(
                            "app_titles_ru",
                            "app.py использует page_registry; видимые названия страниц определяются в реестре",
                            count=0,
                        )
                    )
                else:
                    results.append(_fail("app_titles_ru", "Не удалось извлечь title= из app.py (проверь формат)",))
    except Exception as ex:
        results.append(_fail("app_navigation_paths", "Ошибка проверки app.py", error=repr(ex)))

    # --- 4) Обязательные UI‑модули должны присутствовать ---
    try:
        must = [
            repo_root / "pneumo_solver_ui" / "ui_tooltips_ru.py",
            repo_root / "pneumo_solver_ui" / "ui_persistence.py",
            repo_root / "pneumo_solver_ui" / "ui_bootstrap.py",
            repo_root / "pneumo_solver_ui" / "diag_bundle.py",
        ]
        miss = [str(x) for x in must if not x.exists()]
        if miss:
            results.append(_fail("ui_modules_present", "Не найдены обязательные UI‑модули", missing=miss))
        else:
            results.append(_ok("ui_modules_present", "UI‑модули присутствуют", files=[str(x) for x in must]))
    except Exception as ex:
        results.append(_fail("ui_modules_present", "Ошибка проверки UI‑модулей", error=repr(ex)))

    # --- 5) Проверка: важные настройки UI действительно попадают в автосохранение ---
    try:
        from pneumo_solver_ui import ui_persistence as _up

        _must_persist = [
            "ui_params_section",
            "ui_params_group",
            "ui_params_search",
            "use_rel0_for_plots",
            "skip_heavy_on_play",
            "detail_max_points",
            "detail_want_full",
            "auto_detail_on_select",
            "pareto_obj1",
            "pareto_obj2",
            "mech_plot_corners",
            "node_pressure_plot",
        ]
        _miss = [k for k in _must_persist if not _up._should_persist_key(k)]
        results.append(
            CheckResult(
                name="ui_persistence_coverage",
                ok=(len(_miss) == 0),
                message="",
                details={"status": "OK"} if len(_miss) == 0 else {"missing": _miss},
            )
        )
    except Exception as e:
        results.append(CheckResult(name="ui_persistence_coverage", ok=False, message=str(e)))

    # --- 6) Проверка: локализация компонента пневмосхемы ---
    try:
        comp_path = Path(__file__).resolve().parent / "components" / "pneumo_svg_flow" / "index.html"
        text_html = comp_path.read_text(encoding="utf-8", errors="ignore") if comp_path.exists() else ""
        bad = [s for s in ["Only pending", "Show all", "SVG flow", "Review overlay"] if s in text_html]
        good = ("Пневмосхема" in text_html) and ("Слой проверки" in text_html) and ("Горячие клавиши" in text_html)
        results.append(
            CheckResult(
                name="component_pneumo_svg_flow_ru",
                ok=(len(bad) == 0 and bool(good)),
                message="",
                details={"bad": bad, "good": bool(good)},
            )
        )
    except Exception as e:
        results.append(CheckResult(name="component_pneumo_svg_flow_ru", ok=False, message=str(e)))

    

    # --- 7) Проверка: все страницы multipage используют bootstrap + автосохранение ---
    try:
        pages_dir = repo_root / "pneumo_solver_ui" / "pages"
        missing = []
        if pages_dir.exists():
            for pf in sorted(pages_dir.glob("*.py")):
                # _page_runner.py и __init__.py — служебные модули, это НЕ страницы.
                if pf.name.startswith("_") or pf.name == "__init__.py":
                    continue
                src = pf.read_text(encoding="utf-8", errors="ignore")
                # Допускаем, что st.set_page_config может быть первым Streamlit-вызовом.
                has_boot = "bootstrap(st)" in src
                has_auto = "autosave_if_enabled" in src
                if not has_boot or not has_auto:
                    missing.append({
                        "page": pf.name,
                        "bootstrap": bool(has_boot),
                        "autosave": bool(has_auto),
                    })
        # Отдельно — страница DW2D (она важна и раньше ломалась)
        dw = pages_dir / "10_SuspensionGeometry.py"
        dw_ok = True
        dw_details = {}
        if dw.exists():
            dw_src = dw.read_text(encoding="utf-8", errors="ignore")
            dw_details = {
                "import_st": ("import streamlit as st" in dw_src),
                "bootstrap": ("bootstrap(st)" in dw_src),
                "autosave": ("autosave_if_enabled" in dw_src),
            }
            dw_ok = all(dw_details.values())
        results.append(
            CheckResult(
                name="pages_bootstrap_autosave",
                ok=(len(missing) == 0 and dw_ok),
                message="",
                details={
                    "missing": missing,
                    "dw2d": dw_details,
                },
            )
        )
    except Exception as e:
        results.append(CheckResult(name="pages_bootstrap_autosave", ok=False, message=str(e)))

    # --- 8) Проверка: JS компонента мех-анимации не содержит очевидных падений (playState/updateLabels) ---
    try:
        comp = Path(__file__).resolve().parent / "components" / "mech_anim" / "index.html"
        html = comp.read_text(encoding="utf-8", errors="ignore") if comp.exists() else ""
        bad = []
        if "playState" in html:
            bad.append("playState")
        # updateLabels должна существовать (или не вызываться). Мы держим заглушку.
        if "updateLabels()" in html and "function updateLabels" not in html:
            bad.append("updateLabels_missing")
        results.append(
            CheckResult(
                name="component_mech_anim_js_sanity",
                ok=(len(bad) == 0),
                message="",
                details={"bad": bad},
            )
        )
    except Exception as e:
        results.append(CheckResult(name="component_mech_anim_js_sanity", ok=False, message=str(e)))
    ok = all(r.ok for r in results)
    return {
        "ok": bool(ok),
        "results": [asdict(r) for r in results],
    }


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rep = run_ui_selfcheck(repo_root)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if not rep.get("ok", False):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
