# -*- coding: utf-8 -*-
"""_page_runner.py

Совместимость для legacy-страниц.

Исторически в проекте были страницы с русскими именами файлов.
Для устойчивой упаковки ZIP под Windows эти файлы могли быть
переназваны в ASCII (например, nonascii_<hash>.py), а исходное имя
сохраняется в заголовке как:

    # ORIGINAL_FILENAME: 20_Распределенная_оптимизация.py

В `pages/` лежат ASCII-обёртки (00_Preflight.py и т.п.), которые
вызывают `run_page(<original_filename>)`.

Задача этого раннера — корректно найти цель:
1) pages/<filename>
2) pages_legacy/<filename>
3) pages_legacy/nonascii_*.py по метке ORIGINAL_FILENAME

Так мы избегаем «мертвых ссылок» и проблем с кодировками имён в ZIP.

Важно:
- Здесь мы НЕ вызываем set_page_config, только исполняем целевой файл.
"""

from __future__ import annotations

import json
import re
import runpy
import traceback
from functools import lru_cache
from pathlib import Path
from typing import Optional

import streamlit as st
from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_DIAG_SIDECAR_JSON,
    format_anim_dashboard_brief_lines,
    load_latest_send_bundle_anim_dashboard,
)


HERE = Path(__file__).resolve().parent
LEGACY_DIR = HERE.parent / "pages_legacy"

_ORIG_RE = re.compile(r"ORIGINAL_FILENAME:\s*(.+)")


def _safe_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _is_full_file_clipboard_success(ok: bool, msg: str) -> bool:
    if not ok:
        return False
    m = str(msg)
    return "Copied path as text" not in m and "Fallback(text): Copied path as text" not in m


def _copy_bundle_to_clipboard(bundle_path: Path) -> tuple[bool, str]:
    status_path = bundle_path.parent / "latest_send_bundle_clipboard_status.json"
    try:
        from pneumo_solver_ui.tools.clipboard_file import copy_file_to_clipboard

        ok, msg = copy_file_to_clipboard(bundle_path)
    except Exception:
        ok = False
        msg = traceback.format_exc()

    full_ok = _is_full_file_clipboard_success(bool(ok), str(msg))
    payload = {
        "ok": bool(full_ok),
        "message": str(msg),
        "zip_path": str(bundle_path),
    }
    _safe_write_text(status_path, json.dumps(payload, ensure_ascii=False, indent=2))
    return bool(full_ok), str(msg)


@lru_cache(maxsize=1)
def _legacy_original_map() -> dict[str, Path]:
    """Карта: ORIGINAL_FILENAME -> реальный путь nonascii_*.py."""
    mapping: dict[str, Path] = {}
    if not LEGACY_DIR.exists():
        return mapping

    for p in LEGACY_DIR.glob("nonascii_*.py"):
        try:
            head_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:40]
        except Exception:
            continue
        for line in head_lines:
            m = _ORIG_RE.search(line)
            if m:
                orig = m.group(1).strip()
                if orig:
                    mapping[orig] = p
                break

    return mapping


def _resolve_page_path(filename: str) -> Optional[Path]:
    fn = Path(str(filename)).name

    # 1) pages/
    cand = (HERE / fn).resolve()
    if cand.exists():
        return cand

    # 2) pages_legacy/ (если файл реально лежит там под тем же именем)
    cand2 = (LEGACY_DIR / fn).resolve()
    if cand2.exists():
        return cand2

    # 3) pages_legacy/nonascii_*.py по метке ORIGINAL_FILENAME
    mapping = _legacy_original_map()
    if fn in mapping:
        return mapping[fn].resolve()

    return None


def run_page(filename: str, *, title: Optional[str] = None) -> None:
    target = _resolve_page_path(filename)
    if not target or not target.exists():
        st.error("🚧 Страница в разработке")
        st.caption(f"Не удалось найти файл страницы: {filename}")
        with st.expander("Подробности поиска (для разработчика)"):
            st.write("pages:", str(HERE))
            st.write("pages_legacy:", str(LEGACY_DIR))
            m = _legacy_original_map()
            st.write("ORIGINAL_FILENAME-карт:", len(m))
            if m:
                st.write("Примеры ключей:")
                st.write(sorted(m.keys())[:50])
        return

    if title:
        st.title(str(title))

    # UI bootstrap (persist + defaults + run artifacts) — чтобы результаты/настройки не терялись между страницами
    try:
        from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
        _ui_bootstrap(st)
    except Exception:
        pass

    try:
        runpy.run_path(str(target), run_name="__main__")
    except Exception as e:
        st.error("🚧 Страница в разработке")
        st.caption("Страница найдена, но временно не работает (ошибка выполнения).")
        with st.expander("Технические детали"):
            st.exception(e)


def run_script_page(target: str, *, auto_bundle: bool = False, title: Optional[str] = None) -> None:
    """Run a Streamlit page script by absolute path or legacy filename.

    Why:
    - `page_registry.py` stores absolute paths for discovered pages.
    - Some wrappers still reference legacy filenames (incl. ORIGINAL_FILENAME mapping).
    - In WIP/BROKEN mode we want to attempt running the script and also save
      a project archive on exception (best-effort).

    Parameters:
    - target: absolute path or filename
    - auto_bundle: if True, try to autosave the project archive when execution fails
    - title: optional title to render (no set_page_config here!)
    """
    target_str = str(target)

    # 1) Absolute/relative path as-is
    p = Path(target_str)
    if p.exists() and p.is_file():
        resolved = p.resolve()
    else:
        # 2) Legacy filename resolution (pages/ + pages_legacy/ + ORIGINAL_FILENAME map)
        resolved = _resolve_page_path(target_str)

    if not resolved or not resolved.exists():
        # Reuse the same UX as run_page for missing targets.
        run_page(target_str, title=title)
        return

    if title:
        st.title(str(title))

    # UI bootstrap (persist + defaults + run artifacts) — keep behavior aligned with run_page()
    try:
        from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
        _ui_bootstrap(st)
    except Exception:
        pass

    try:
        runpy.run_path(str(resolved), run_name="__main__")
    except Exception as e:
        saved_path = None
        clipboard_ok = False
        clipboard_msg = ""
        if auto_bundle:
            # Best-effort autosave — never raise from here.
            try:
                from pneumo_solver_ui.crash_guard import try_autosave_bundle
                safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(resolved.stem))
                reason = f"ui_page_exception_{safe_stem}"
                saved_path = try_autosave_bundle(reason=reason, fatal=False)
                if saved_path:
                    clipboard_ok, clipboard_msg = _copy_bundle_to_clipboard(Path(saved_path))
            except Exception:
                saved_path = None
                clipboard_ok = False
                clipboard_msg = ""

        st.error("Ошибка выполнения страницы")
        if saved_path:
            st.caption(f"Архив проекта сохранён: {saved_path}")
            bundle_dir = Path(saved_path).parent
            anim_summary = load_latest_send_bundle_anim_dashboard(bundle_dir)
            anim_lines = format_anim_dashboard_brief_lines(anim_summary)
            if anim_lines:
                st.markdown("\n".join(f"- {line}" for line in anim_lines))
            diag_json = bundle_dir / ANIM_DIAG_SIDECAR_JSON
            if diag_json.exists():
                st.caption(f"Данные последней анимации: {diag_json}")
            if clipboard_ok:
                st.success("Архив проекта скопирован в буфер обмена.")
            elif clipboard_msg:
                st.warning(f"Архив проекта сохранён, но копирование в буфер обмена не подтвердилось: {clipboard_msg}")
        with st.expander("Технические детали"):
            st.exception(e)
        return
