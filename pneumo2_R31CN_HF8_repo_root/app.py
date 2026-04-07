"""PneumoApp — единая точка входа Streamlit.

Цели:
1) Единый механизм навигации Streamlit Page/Navigation.
2) Ничего не прячем (никаких "expert/legacy" переключателей): страницы доступны всегда.
3) Одна кнопка "Диагностика" в сайдбаре (с настройками) для сборки полного ZIP.
4) Защита от падений из‑за повторного st.set_page_config() на старых страницах.
"""

from __future__ import annotations

import os
import hashlib
import inspect
import re
from datetime import datetime
from pathlib import Path
from typing import List

import streamlit as st

# Diagnostics/logging bootstrap (ABSOLUTE LAW: everything must be logged).
from pneumo_solver_ui.diag.bootstrap import bootstrap as _diag_bootstrap
_diag_bootstrap("PneumoApp")

# Streamlit compatibility: translate deprecated args (use_container_width -> width, etc.)
try:
    from pneumo_solver_ui.ui_st_compat import install_st_compat

    install_st_compat()
except Exception:
    pass

from pneumo_solver_ui.crash_guard import install_crash_guard
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

# Structured navigation (sections/groups + WIP banners)
from pneumo_solver_ui.page_registry import build_streamlit_pages, menu_structure, PageEntry


APP_ROOT = Path(__file__).resolve().parent


# Streamlit may infer URL pathnames from filename/callable/title.
# In some versions it strips numeric prefixes ("07_...") which can cause collisions
# when multiple pages share the same tail name (e.g. 07_DesktopAnimator, 08_DesktopAnimator).
# To make navigation robust across Streamlit versions, we assign a stable unique url_path.
_PAGE_SUPPORTS_URL_PATH = False
try:
    _PAGE_SUPPORTS_URL_PATH = 'url_path' in inspect.signature(st.Page).parameters
except Exception:
    _PAGE_SUPPORTS_URL_PATH = False


def p(rel: str) -> str:
    """Absolute path helper (works for both Windows and Linux)."""
    return str((APP_ROOT / rel).resolve())


# -----------------------------------------------------------------------------
# Safe st.set_page_config (Streamlit allows calling it only once per app run).
# Many historical pages call st.set_page_config() on import.
# We ignore all subsequent calls after the first.
_orig_set_page_config = st.set_page_config


def _safe_set_page_config(*args, **kwargs):
    if getattr(st, "_pneumo_page_config_called", False):
        return
    setattr(st, "_pneumo_page_config_called", True)
    return _orig_set_page_config(*args, **kwargs)


st.set_page_config = _safe_set_page_config  # type: ignore[assignment]


RELEASE = os.environ.get("PNEUMO_RELEASE") or "PneumoApp_v6_80_R176"

st.set_page_config(
    page_title=f"PneumoApp — {RELEASE}",
    layout="wide",
)

# Bootstrap + autosave should be active regardless of which page the user opens.
bootstrap(st)
autosave_if_enabled(st)

# Workaround: Streamlit may still render a navigation widget in the sidebar
# even when `st.navigation(..., position="hidden")` is used.
# This leads to duplicated page lists. We hide the built-in widget via CSS.
try:
    st.markdown(
        """<style>
        /* Hide Streamlit navigation widget (st.navigation / multipage nav) */
        [data-testid=\"stSidebarNav\"] { display: none !important; }
        [data-testid=\"stSidebarNavItems\"] { display: none !important; }
        [data-testid=\"stSidebarNavSeparator\"] { display: none !important; }
        </style>""",
        unsafe_allow_html=True,
    )
except Exception:
    pass

# Crash guard must be installed early (it can autosave diagnostic bundle on crash).
install_crash_guard()


def _discover_pages(dir_rels: List[str]) -> List[st.Page]:
    """Discover *.py pages under APP_ROOT for each directory in dir_rels.

    IMPORTANT:
    - We must NOT allow a thin wrapper in `pages/` to shadow a full implementation
      with the same filename in `pages_legacy/` (this is a common merge/integration regression).
    - We keep historical pages for traceability, but navigation must prioritize
      working pages to prevent "dead links" and lost functionality.
    """

    pages: List[st.Page] = []

    # Collect candidates by filename (same basename may exist in multiple dirs)
    candidates: Dict[str, List[Tuple[Path, str]]] = {}

    for dir_rel in dir_rels:
        dir_path = APP_ROOT / dir_rel
        if not dir_path.exists():
            continue
        for fp in sorted(dir_path.glob("*.py")):
            if fp.name.startswith("_"):
                continue
            if "__dup" in fp.name:
                continue
            candidates.setdefault(fp.name, []).append((fp, dir_rel))

    def _is_thin_wrapper(fp: Path) -> bool:
        # Heuristic: very small file that just calls run_page(...) is a wrapper.
        try:
            size = fp.stat().st_size
        except Exception:
            size = 0
        if size > 4000:
            return False
        try:
            head = fp.read_text(encoding="utf-8", errors="ignore")[:4096]
        except Exception:
            return False
        return ("run_page(" in head) and ("from pneumo_solver_ui.pages._page_runner" in head)

    for fname, opts in sorted(candidates.items(), key=lambda kv: kv[0]):
        # Select "best" candidate when duplicates exist.
        if len(opts) == 1:
            best_fp, best_dir_rel = opts[0]
        else:
            non_wrappers = [opt for opt in opts if not _is_thin_wrapper(opt[0])]
            pool = non_wrappers if non_wrappers else opts

            def _score(opt: Tuple[Path, str]) -> Tuple[int, int]:
                fp, dir_rel = opt
                try:
                    sz = fp.stat().st_size
                except Exception:
                    sz = 0
                prefer_pages = 1 if dir_rel.endswith("/pages") else 0
                return (sz, prefer_pages)

            best_fp, best_dir_rel = max(pool, key=_score)

        # Title comes from stem; keep stable naming for user's muscle-memory.
        title = best_fp.stem.replace("_", " ")
        rel = f"{best_dir_rel}/{best_fp.name}"

        # Stable unique URL path: slug(stem) + short hash(rel)
        stem_slug = re.sub(r"[^a-z0-9_-]+", "-", best_fp.stem.lower()).strip("-_") or "page"
        h = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8]
        url_path = f"p-{stem_slug}-{h}"

        page_kwargs = {"title": title}
        if _PAGE_SUPPORTS_URL_PATH:
            page_kwargs["url_path"] = url_path

        pages.append(st.Page(p(rel), **page_kwargs))


    return pages


# -----------------------------------------------------------------------------
# Structured navigation (sections / groups)
# -----------------------------------------------------------------------------

# Build pages via registry (includes Home + WIP wrappers + stable url_path).
_entries, _nav_pages, _page_map = build_streamlit_pages()

# Hide Streamlit's default navigation widget: we render our own sidebar menu.
_current_page = st.navigation(_nav_pages, position="hidden")


def _safe_page_link(container, *, url_path: str, label: str, help_text: str | None = None) -> None:
    """Robust page link: page_link if available, fallback to switch_page."""
    pg = _page_map.get(url_path)
    if not pg:
        container.error(f"Страница не найдена: {url_path}")
        return

    if hasattr(container, "page_link"):
        container.page_link(pg, label=label, help=help_text, width="stretch")
        return

    # Fallback for older Streamlit (should not happen with requirements.txt).
    if container.button(label, help=help_text, width="stretch"):
        st.switch_page(pg)


def _render_sidebar_menu(entries: list[PageEntry], *, current_url_path: str) -> None:
    st.sidebar.title("Навигация")
    tree = menu_structure(entries)
    for section, groups in tree.items():
        st.sidebar.subheader(section)
        for group, ents in groups.items():
            expanded = any(e.url_path == current_url_path for e in ents)
            box = st.sidebar.expander(group, expanded=expanded)
            for e in ents:
                lbl = e.menu_title()
                if e.url_path == current_url_path:
                    lbl = "➡️ " + lbl
                _safe_page_link(box, url_path=e.url_path, label=lbl, help_text=e.help)


# Sidebar: one-button diagnostics (with settings)
with st.sidebar:
    # Menu first (structured).
    _render_sidebar_menu(_entries, current_url_path=getattr(_current_page, "url_path", ""))

    # Diagnostics below.
    st.markdown("---")
    st.subheader("Диагностика")

    # NOTE: We must NOT rebuild the diagnostic ZIP on every rerun.
    # Instead, build it explicitly and then offer the download.

    # Output directory (persisted in UI autosave so watchdog can see it)
    diag_out_dir_raw = st.text_input(
        "Папка для диагностических ZIP",
        value=str(st.session_state.get("diag_output_dir", "send_bundles")),
        key="diag_output_dir",
        help="Можно указать относительный путь (от папки приложения) или абсолютный. По умолчанию: send_bundles",
    )

    # Status indicator (last bundle + validation)
    try:
        from pathlib import Path as _Path
        import json as _json

        def _resolve_out_dir(raw: str) -> _Path:
            s = (raw or "").strip()
            if not s:
                return (APP_ROOT / "send_bundles").resolve()
            try:
                p = _Path(s).expanduser()
                if p.is_absolute():
                    return p.resolve()
            except Exception:
                pass
            return (APP_ROOT / s).resolve()

        _out_dir = _resolve_out_dir(str(diag_out_dir_raw))
        st.caption(f"Каталог ZIP: {_out_dir}")

        meta_p = _out_dir / "last_bundle_meta.json"
        if meta_p.exists():
            meta = _json.loads(meta_p.read_text(encoding="utf-8", errors="replace"))
            ok = meta.get("ok")
            ts = meta.get("ts")
            trig = meta.get("trigger")
            z = meta.get("zip") or {}
            name = z.get("name") or z.get("path")
            size_b = z.get("size_bytes")
            size_mb = (float(size_b) / (1024 * 1024)) if isinstance(size_b, (int, float)) else None
            st.write(
                f"Последний ZIP: **{name}**" + (f" ({size_mb:.1f} MB)" if size_mb is not None else "")
                + f" — ok={ok}, trigger={trig}, ts={ts}"
            )
        else:
            st.write("Последний ZIP: —")

        vj = _out_dir / "latest_send_bundle_validation.json"
        if vj.exists():
            v = _json.loads(vj.read_text(encoding="utf-8", errors="replace"))
            st.write(
                f"Validation: ok={v.get('ok')} errors={len(v.get('errors') or [])} warnings={len(v.get('warnings') or [])}"
            )
    except Exception:
        # no status if JSON parsing failed
        pass

    keep_last_n = st.number_input(
        "Хранить последние N диагностических ZIP (на диске)",
        min_value=1,
        max_value=200,
        value=int(st.session_state.get("diag_keep_last_n", 10)),
        step=1,
        key="diag_keep_last_n",
    )
    max_file_mb = st.number_input(
        "Лимит размера одного файла в ZIP, МБ",
        min_value=1,
        max_value=2000,
        value=int(st.session_state.get("diag_max_file_mb", 200)),
        step=1,
        key="diag_max_file_mb",
    )
    include_workspace_osc = st.checkbox(
        "Включать большие OSC/сырые осциллограммы (может увеличить ZIP)",
        value=bool(st.session_state.get("diag_include_workspace_osc", False)),
        key="diag_include_workspace_osc",
    )
    # P0-TOOLS-001: preflight_gate/property_invariants/self_check должны реально исполняться
    run_selfcheck_before_bundle = st.checkbox(
        "Запускать preflight/self_check/property_invariants перед сохранением",
        value=bool(st.session_state.get("diag_run_selfcheck", True)),
        key="diag_run_selfcheck",
        help="Рекомендуется держать включенным. Результаты сохраняются в diagnostics_runs/ и попадают в ZIP.",
    )
    selfcheck_level = st.selectbox(
        "Уровень selfcheck suite",
        options=["quick", "standard", "full"],
        index=int(st.session_state.get("diag_selfcheck_level_idx", 1)),
        key="diag_selfcheck_level",
        help="standard = разумный компромисс. full может быть дольше.",
    )
    # keep selectbox index in state (Streamlit stores value; we also keep idx for backward compat)
    st.session_state["diag_selfcheck_level_idx"] = ["quick","standard","full"].index(str(selfcheck_level))

    autosave_on_crash = st.checkbox(
        "Авто-сохранение диагностики при краше",
        value=bool(st.session_state.get("diag_autosave_on_crash", True)),
        key="diag_autosave_on_crash",
        help="Если Streamlit падает из-за необработанного исключения — будет сохранён полный ZIP.",
    )
    autosave_on_exit = st.checkbox(
        "Авто-сохранение диагностики при выходе",
        value=bool(st.session_state.get("diag_autosave_on_exit", True)),
        key="diag_autosave_on_exit",
        help="Полезно, чтобы всегда получать ZIP после закрытия приложения (launcher/GUI).",
    )
    autosave_on_watchdog = st.checkbox(
        "Авто-сохранение диагностики (watchdog после kill)",
        value=bool(st.session_state.get("diag_autosave_on_watchdog", True)),
        key="diag_autosave_on_watchdog",
        help="Внешний watchdog вмешается, если launcher умер раньше Streamlit. Читает настройки из persistent_state.",
    )

    os.environ["PNEUMO_AUTOSAVE_BUNDLE_ON_CRASH"] = "1" if autosave_on_crash else "0"
    os.environ["PNEUMO_AUTOSAVE_BUNDLE_ON_EXIT"] = "1" if autosave_on_exit else "0"
    os.environ["PNEUMO_AUTOSAVE_BUNDLE_ON_WATCHDOG"] = "1" if autosave_on_watchdog else "0"
    os.environ["PNEUMO_BUNDLE_KEEP_LAST_N"] = str(keep_last_n)
    os.environ["PNEUMO_BUNDLE_MAX_FILE_MB"] = str(max_file_mb)
    os.environ["PNEUMO_BUNDLE_INCLUDE_WORKSPACE"] = "1" if include_workspace_osc else "0"
    os.environ["PNEUMO_BUNDLE_RUN_SELFCHECK"] = "1" if run_selfcheck_before_bundle else "0"
    os.environ["PNEUMO_BUNDLE_SELFCHECK_LEVEL"] = str(selfcheck_level)
    # Legacy watchdog env names (still used by some tooling)
    os.environ["PNEUMO_SEND_BUNDLE_KEEP_LAST_N"] = str(keep_last_n)
    os.environ["PNEUMO_SEND_BUNDLE_MAX_FILE_MB"] = str(max_file_mb)
    os.environ["PNEUMO_SEND_BUNDLE_INCLUDE_OSC"] = "1" if include_workspace_osc else "0"

    # Optional tag suffix for diagnostic ZIP name (helps sorting bundles later).
    tag = st.text_input(
        "Тег (суффикс имени ZIP, опционально)",
        value=str(st.session_state.get("diag_tag", "")),
        key="diag_tag",
        placeholder="например: 'regress_v6_71'",
    )
    tag = str(tag).strip()
    if tag:
        os.environ["PNEUMO_BUNDLE_TAG_SUFFIX"] = tag
    else:
        # Keep env clean so other tools don't think a tag was requested.
        os.environ.pop("PNEUMO_BUNDLE_TAG_SUFFIX", None)

    reason = st.text_input(
        "Причина / комментарий (будет вложено в ZIP)",
        value=str(st.session_state.get("diag_reason", "")),
        key="diag_reason",
        placeholder="например: 'регресс v6_66 — падает страница сравнения'",
    )

    if st.button("СОХРАНИТЬ ПОЛНУЮ ДИАГНОСТИКУ (ZIP)", key="btn_diag_build_bundle", width="stretch"):
        try:
            # Unified entrypoint (same as crash_guard/watchdog/send_results_gui)
            from pneumo_solver_ui.diagnostics_entrypoint import build_full_diagnostics_bundle

            res = build_full_diagnostics_bundle(
                trigger="manual",
                repo_root=APP_ROOT,
                session_state=dict(st.session_state),
                open_folder=False,
            )

            if not res.ok or not res.zip_path:
                raise RuntimeError(res.message or "bundle build failed")

            zp = Path(res.zip_path)
            bundle_bytes = zp.read_bytes()
            st.session_state["_diag_bundle_path"] = str(zp)
            st.session_state["_diag_bundle_name"] = zp.name
            st.session_state["_diag_bundle_bytes"] = bundle_bytes
            st.success(f"Готово: {zp.name}")
            st.caption(f"ZIP уже сохранён на диск: {zp}")
            st.download_button(
                "Скачать диагностический ZIP",
                data=bundle_bytes,
                file_name=str(zp.name),
                mime="application/zip",
                key="download_diagnostic_zip_now",
            )
        except Exception as e:
            st.error(f"Не удалось собрать диагностику: {type(e).__name__}: {e}")

    if st.session_state.get("_diag_bundle_bytes") and st.session_state.get("_diag_bundle_name"):
        st.download_button(
            "Скачать диагностический ZIP",
            data=st.session_state["_diag_bundle_bytes"],
            file_name=str(st.session_state["_diag_bundle_name"]),
            mime="application/zip",
            key="download_diagnostic_zip",
        )
        if st.session_state.get("_diag_bundle_path"):
            st.caption(f"Последний сохранённый ZIP: {st.session_state['_diag_bundle_path']}")
        else:
            st.caption("Если нужно обновить ZIP после новых прогонов — нажми «Собрать диагностический ZIP» ещё раз.")

    # ------------------------------------------------------------
    # UI performance settings (no hidden "expert" mode)
    # ------------------------------------------------------------
    with st.expander("Производительность интерфейса", expanded=False):
        st.caption(
            "Настройки влияют на скорость перерисовки тяжёлых графиков/таблиц. "
            "Кэш хранит *визуальные артефакты* (не расчёт физики)."
        )
        try:
            from pneumo_solver_ui.ui_heavy_cache import get_cache
            from pneumo_solver_ui.run_artifacts import get_status

            st.checkbox(
                "Кэшировать тяжёлые графики/таблицы",
                key="ui_perf_cache_enabled",
                value=bool(st.session_state.get("ui_perf_cache_enabled", True)),
                help="Если выключить — любые тяжёлые графики будут перестраиваться при каждом взаимодействии с UI.",
            )
            st.checkbox(
                "Разрешить дисковый кэш",
                key="ui_perf_cache_disk",
                value=bool(st.session_state.get("ui_perf_cache_disk", True)),
                help="Полезно, если ты часто перезапускаешь приложение: графики не будут пересчитываться с нуля.",
            )
            st.number_input(
                "Время жизни кэша, секунд",
                min_value=60,
                max_value=7 * 24 * 3600,
                value=int(st.session_state.get("ui_perf_cache_ttl_s", 24 * 3600)),
                step=60,
                key="ui_perf_cache_ttl_s",
                help="После истечения TTL кэш будет автоматически перестроен.",
            )

            if st.button("Очистить кэш тяжёлых графиков", key="ui_perf_cache_clear"):
                removed = get_cache(st).clear()
                st.success(f"Кэш очищен: удалено файлов: {removed}")

            # Simple global status (helps users understand what is "готово")
            baseline_ready, opt_ready = get_status(st)
            st.markdown("**Статус результатов**")
            st.write(f"Опорный прогон: {'✅ есть' if baseline_ready else '— нет'}")
            st.write(f"Оптимизация: {'✅ есть' if opt_ready else '— нет'}")
        except Exception:
            st.info("Настройки производительности будут доступны после полной инициализации UI-модулей.")

    # --- Silent WARN signalization (self_check energy/entropy etc.) ---
    st.markdown("#### ⚠️ Сигналы self_check (энергия/энтропия)")
    try:
        from pneumo_solver_ui.diag.silent_warnings_report import load_report, REPORT_MD_NAME  # type: ignore
        rep = load_report()
    except Exception as e:
        rep = None
        st.caption(f"(Сигнализация self_check недоступна: {type(e).__name__}: {e})")
    else:
        if not rep:
            st.info(
                "Нет отчёта self_check. Он появится после прогона preflight_gate/self_check.\n\n"
                "Ожидаемый файл: REPORTS/SELF_CHECK_SILENT_WARNINGS.json"
            )
        else:
            summ = rep.get("summary", {}) or {}
            warn_n = int(summ.get("warn_count", 0) or 0)
            fail_n = int(summ.get("fail_count", 0) or 0)
            rc = rep.get("rc")
            if fail_n:
                st.error(f"self_check: FAIL={fail_n}, WARN={warn_n}, rc={rc}")
            elif warn_n:
                st.warning(f"self_check: WARN={warn_n}, rc={rc}")
            else:
                st.success(f"self_check: OK (rc={rc})")

            with st.expander("Показать детали WARN/FAIL", expanded=False):
                items = (rep.get("fails") or []) + (rep.get("warnings") or [])
                if not items:
                    st.write("Нет предупреждений.")
                else:
                    for it in items[:30]:
                        step = it.get("step", "")
                        msg = it.get("message", "")
                        st.write(f"[{step}] {msg}")
                    if len(items) > 30:
                        st.caption(f"…и ещё {len(items)-30} пунктов")
                st.caption(f"Подробный отчёт: REPORTS/{REPORT_MD_NAME}")


# Execute current page selected by registry navigation
# --- Run selected page (with best-effort crash diagnostics) ---
try:
    _current_page.run()
except Exception as _page_exc:
    # Streamlit usually shows the exception, but we also try to capture a diagnostics bundle.
    try:
        import logging, traceback
        logging.exception("ui_page_exception")
        try:
            from pneumo_solver_ui.diag.bootstrap import emit_event as _emit_page_exception  # type: ignore
            _emit_page_exception("ui_page_exception", f"{type(_page_exc).__name__}: {_page_exc}", traceback=traceback.format_exc())
        except Exception:
            pass
        from pneumo_solver_ui.crash_guard import try_autosave_bundle
        saved = try_autosave_bundle(reason=f"ui_page_exception:{type(_page_exc).__name__}", fatal=False)
        if saved:
            st.error(f"❌ Ошибка страницы. Диагностика сохранена: {saved}")
        else:
            st.error("❌ Ошибка страницы. Диагностику сохранить не удалось (см. логи).")
    except Exception:
        pass
    raise
