"""Page registry and menu structure.

Goals
-----
1) Provide a *structured* sidebar menu (sections / groups), not a flat list.
2) Support explicit WIP marking ("В разработке") in menu + banner on page.
3) Keep navigation stable (unique url_path) across merges.
4) Allow partial auto-discovery for new pages while keeping deterministic order.

This module is intentionally UI-only. It should not import heavy model modules.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import re
from pathlib import Path

from pneumo_solver_ui.entrypoints import canonical_home_page_rel, repo_root

import re

def _extract_original_filename(p: Path) -> str | None:
    """Recover original filename for nonascii_*.py pages.

    Donor bundles sometimes wrote ORIGINAL_FILENAME using legacy encodings or with
    mojibake (e.g. 'РЎРѕ...' or '╨ö╨...').

    We:
    1) Parse the header line in raw bytes.
    2) Decode payload as UTF-8 (preferred) with fallbacks.
    3) De-mojibake if needed.
    """
    try:
        data = p.read_bytes()[:4096]
    except Exception:
        return None

    def _demojibake(s: str) -> str:
        # Pattern A: UTF-8 bytes were decoded as CP866 earlier -> box-drawing chars.
        if any(ch in s for ch in '╨╤╘╙╒╓╥╔╗╚╝'):
            try:
                fixed = s.encode('cp866', errors='ignore').decode('utf-8', errors='ignore')
            except Exception:
                fixed = ''
            if fixed and not any(ch in fixed for ch in '╨╤╘╙╒╓╥╔╗╚╝'):
                s = fixed

        # Pattern B: UTF-8 bytes were decoded as CP1251 earlier -> many 'Р'/'С' pairs.
        if s and (s.count('Р') + s.count('С')) / max(1, len(s)) > 0.18:
            try:
                fixed = s.encode('cp1251', errors='ignore').decode('utf-8', errors='ignore')
            except Exception:
                fixed = ''
            if fixed:
                s = fixed
        return s

    for raw_line in data.splitlines()[:40]:
        line = raw_line.lstrip()
        if not line.startswith(b'#'):
            continue
        if b'ORIGINAL_FILENAME' not in line:
            continue
        m = re.match(br'^#\s*ORIGINAL_FILENAME:\s*(.+)$', line)
        if not m:
            continue
        payload = m.group(1).strip()

        # Decode candidates (UTF-8 preferred)
        decoded: str | None = None
        try:
            decoded = payload.decode('utf-8')
        except UnicodeDecodeError:
            decoded = None
        if decoded is None:
            for enc in ('cp1251', 'cp866'):
                try:
                    decoded = payload.decode(enc)
                    break
                except Exception:
                    continue
        if decoded is None:
            decoded = payload.decode('utf-8', errors='ignore')

        decoded = _demojibake(decoded).strip()
        return decoded or None

    return None

def _pretty_title_from_fname(fname: str) -> str:
    stem = Path(fname).stem
    stem = re.sub(r"^\d+[_-]", "", stem)
    stem = re.sub(r"__dup$", "", stem)
    stem = stem.replace('_', ' ').strip()
    return stem or Path(fname).stem





def _extract_declared_title(p: Path) -> str | None:
    """Best-effort: extract page title from inside the page script."""
    try:
        head = p.read_text(encoding='utf-8', errors='ignore').splitlines()[:220]
    except Exception:
        return None
    txt = "\n".join(head)

    m = re.search(r"safe_set_page_config\([^\)]*page_title\s*=\s*['\"]([^'\"]+)['\"]", txt)
    if m:
        return m.group(1).strip()
    m = re.search(r"st\.title\(\s*[\'\\\"]([^\'\\\"]+)[\'\\\"]", txt)
    if m:
        return m.group(1).strip()
    return None
from typing import Callable, Iterable


class PageStatus:
    READY = "READY"
    IN_DEV = "IN_DEV"
    BROKEN = "BROKEN"


@dataclass(frozen=True)
class PageEntry:
    # Menu taxonomy
    section: str
    group: str

    # Display
    title: str
    icon: str = "📄"
    help: str | None = None
    status: str = PageStatus.READY

    # Target
    target: str | Callable[[], None] = ""
    url_path: str = ""

    # Flags
    default: bool = False
    show_in_menu: bool = True

    def menu_title(self) -> str:
        suffix = ""
        if self.status == PageStatus.IN_DEV:
            suffix = "  🛠️ в разработке"
        elif self.status == PageStatus.BROKEN:
            suffix = "  ❌ сломано"
        return f"{self.icon} {self.title}{suffix}".strip()


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "page"


def _stable_url_path(rel: str) -> str:
    """Stable, unique url_path for Streamlit pages.

    Streamlit requires url_path without slashes. We also need deterministic and
    collision-resistant values across merges. We derive it from *relative path*.
    """

    h = hashlib.blake2s(rel.encode("utf-8"), digest_size=4).hexdigest()
    return f"p-{_slug(Path(rel).stem)}-{h}"


def _discover_page_files() -> dict[str, Path]:
    """Discover *.py in pneumo_solver_ui/pages and pages_legacy.

    Returns mapping by file name (basename) -> best candidate path.
    Policy: prefer non-legacy path when duplicate names exist.
    """

    base = Path(__file__).resolve().parent
    pages_dir = base / "pages"
    legacy_dir = base / "pages_legacy"

    candidates: list[Path] = []
    for d in (pages_dir, legacy_dir):
        if d.exists():
            candidates += sorted(p for p in d.glob("*.py") if not p.name.startswith("_"))

    best: dict[str, Path] = {}
    for p in candidates:
        key = p.name
        if key not in best:
            best[key] = p
            continue
        # Prefer non-legacy over legacy when same filename.
        is_new_legacy = "pages_legacy" in str(p)
        is_old_legacy = "pages_legacy" in str(best[key])
        if is_old_legacy and not is_new_legacy:
            best[key] = p
    return best


def _default_taxonomy_for_file(name: str) -> tuple[str, str]:
    """Heuristic: derive section/group from numeric prefix."""
    m = re.match(r"^(\d{2})_", name)
    if not m:
        return ("Дополнительно", "Авто")
    k = int(m.group(1))
    if k <= 1:
        return ("Старт", "Подготовка")
    if 2 <= k <= 5:
        return ("Анализ", "Влияния")
    if 6 <= k <= 6:
        return ("Анализ", "Сравнение")
    if 7 <= k <= 11:
        return ("Визуализация", "Анимация")
    if 12 <= k <= 29:
        return ("Анализ", "Результаты")
    if 30 <= k <= 49:
        return ("Оптимизация", "Запуск")
    if 50 <= k <= 79:
        return ("Оптимизация", "Инструменты")
    if 80 <= k <= 97:
        return ("Оптимизация", "Распределённая")
    if 98 <= k <= 99:
        return ("Диагностика", "Диагностика")
    return ("Дополнительно", "Авто")


def get_entries() -> list[PageEntry]:
    """Return explicit + autodiscovered page entries."""

    files = _discover_page_files()
    repo = repo_root(here=__file__)

    # Explicit (curated) pages first.
    curated: list[PageEntry] = []

    # Home page (main UI)
    home_rel = canonical_home_page_rel(here=__file__)
    curated.append(
        PageEntry(
            section="Старт",
            group="Главное",
            title="Главная",
            icon="🏠",
            help="Основной расчёт, исходные данные и baseline/results. Оптимизация — на отдельной странице.",
            status=PageStatus.READY,
            target=str((repo / home_rel).resolve()),
            # Default page must be true root (pathname "").
            # We keep url_path empty so the custom sidebar can highlight it.
            url_path="",
            default=True,
        )
    )

    # Map of known filenames -> metadata overrides.
    known_meta: dict[str, dict] = {
        "00_Setup.py": dict(section="Старт", group="Подготовка", title="Настройка проекта", icon="⚙️"),
        "00_Preflight.py": dict(section="Старт", group="Самопроверки", title="Preflight (проверки)", icon="✅"),
        "00_UnitsAndZero.py": dict(section="Старт", group="Справка", title="Единицы и нули", icon="📏"),
        "01_SchemeIntegrity.py": dict(section="Модель", group="Схема", title="Целостность схемы", icon="🧩"),
        "02_Calibration_NPZ.py": dict(section="Калибровка", group="Стенды", title="Калибровка (НПЗ)", icon="🧪"),
        "03_SystemInfluence.py": dict(section="Анализ", group="Влияния", title="Влияния: система", icon="📈"),
        "04_SubsystemsInfluence.py": dict(section="Анализ", group="Влияния", title="Влияния: подсистемы", icon="📈"),
        "04_Uncertainty.py": dict(section="Анализ", group="Влияния", title="Неопределённость", icon="📉"),
        "05_ParamInfluence.py": dict(section="Анализ", group="Влияния", title="Влияния: параметры", icon="📈"),
        "06_CompareRuns.py": dict(section="Анализ", group="Сравнение", title="Сравнение прогонов", icon="⚖️"),
        "07_DesktopAnimator.py": dict(section="Визуализация", group="Анимация", title="Анимация (desktop)", icon="🎞️"),
        "08_DesktopAnimator.py": dict(section="Визуализация", group="Анимация", title="Анимация 2 (desktop)", icon="🎞️"),
        "08_DesktopMnemo.py": dict(
            section="Визуализация",
            group="Анимация",
            title="Мнемосхема (desktop)",
            icon="🫁",
            help="Отдельное HMI-окно с анимированной мнемосхемой, follow-режимом и трендами по выбранным узлам.",
        ),
        "11_AnimationCockpit_Web.py": dict(section="Визуализация", group="Анимация", title="Анимация (web cockpit)", icon="🕹️"),
        "12_ResultsViewer.py": dict(section="Анализ", group="Результаты", title="Просмотр результатов", icon="📊"),
        "20_ParamsGuide.py": dict(section="Справка", group="Параметры", title="Справочник параметров", icon="📌"),
        "21_CompareRuns_Quick.py": dict(section="Анализ", group="Сравнение", title="Сравнение (быстро)", icon="⚡"),
        "30_Optimization.py": dict(section="Оптимизация", group="Запуск", title="Оптимизация", icon="🎯"),
        "31_OptDatabase.py": dict(section="Оптимизация", group="База", title="База оптимизаций", icon="🗄️"),
        "04_DistributedOptimization.py": dict(section="Оптимизация", group="Распределённая", title="Distributed optimization", icon="🛰️"),
        "98_Diagnostics.py": dict(section="Диагностика", group="Отчёты", title="Diagnostics", icon="🧰"),
        "99_DiagnosticsHub.py": dict(section="Диагностика", group="Отчёты", title="Diagnostics Hub", icon="🧰"),
    
        # --- Donor UI/Tools pages (v6.80) ---
        # Важно: никаких PageMeta (он был убран при унификации реестра страниц).
        # 03_Optimization — внутренний файл, прячем из меню, чтобы не дублировать 30_Optimization.
        "03_Optimization.py": dict(
            section="Оптимизация",
            group="Запуск",
            title="Оптимизация (внутр.)",
            icon="🧩",
            default=False,
            show_in_menu=False,
            status=PageStatus.IN_DEV,
            help="Внутренний модуль страницы оптимизации (используется 30_Optimization).",
        ),
        "97_Settings.py": dict(
            section="Диагностика",
            group="Настройки",
            title="Настройки",
            icon="⚙️",
            default=False,
            help="Все пользовательские настройки приложения, диагностики и UX‑баннеров.",
        ),
        "13_CamozziCylindersCatalog.py": dict(
            section="Модель",
            group="Каталоги",
            title="Camozzi: каталог цилиндров",
            icon="📚",
            default=False,
            help="Просмотр и подбор цилиндров Camozzi (из встроенного JSON каталога).",
        ),
        "14_SpringsGeometry_CoilBind.py": dict(
            section="Модель",
            group="Инструменты",
            title="Пружина: геометрия и coil‑bind",
            icon="🌀",
            default=False,
            help="Калькулятор геометрии пружины, оценка coil‑bind, экспорт патча параметров.",
        ),
        "15_PneumoScheme_Mnemo.py": dict(
            section="Модель",
            group="Схема",
            title="Пневмосхема: мнемосхема",
            icon="🗺️",
            default=False,
            help="Интерактивная мнемосхема пневмолинии/клапанов, привязанная к реестру ключей.",
        ),
        "16_PneumoScheme_Graph.py": dict(
            section="Модель",
            group="Схема",
            title="Пневмосхема: граф",
            icon="🕸️",
            default=False,
            help="Графовое представление пневмосхемы, проверка связности и ключей.",
        ),
}

    used_files: set[str] = set()
    for fname, meta in known_meta.items():
        if fname not in files:
            continue
        p = files[fname]
        used_files.add(fname)
        rel = str(p.relative_to(repo))

                # Mark legacy/dup pages as IN_DEV by default, but allow meta overrides.
        status = meta.get("status") or (PageStatus.IN_DEV if ("LEGACY" in fname.upper() or "__dup" in fname) else PageStatus.READY)
        if status not in (PageStatus.READY, PageStatus.IN_DEV, PageStatus.BROKEN):
            status = PageStatus.READY

        default = bool(meta.get("default") or False)
        show_in_menu = bool(meta.get("show_in_menu", True))
        url_path = str(meta.get("url_path") or _stable_url_path(rel))

        curated.append(
            PageEntry(
                section=meta.get("section") or _default_taxonomy_for_file(fname)[0],
                group=meta.get("group") or _default_taxonomy_for_file(fname)[1],
                title=meta.get("title") or _pretty_title_from_fname(fname),
                icon=meta.get("icon") or "📄",
                help=meta.get("help"),
                status=status,
                target=str(p.resolve()),
                url_path=url_path,
                default=default,
                show_in_menu=show_in_menu,
            )
        )

    def _archive_entry(e: PageEntry, *, reason: str) -> PageEntry:
        """Move an entry to the Archive section to keep the main menu clean.

        We never *hide* pages completely (contract: engineers must be able to open
        legacy/WIP pages), but we also must avoid duplicated labels in the main
        sidebar which causes confusion.
        """
        try:
            src = Path(e.target).name if isinstance(e.target, str) else "callable"
        except Exception:
            src = "page"

        new_title = e.title
        if src and src not in new_title:
            new_title = f"{new_title} ({src})"

        new_help = e.help
        if reason:
            new_help = ((new_help or "").rstrip() + f"\n\n[Архив] {reason}").rstrip()

        # Preserve BROKEN status if present; otherwise mark as IN_DEV.
        new_status = e.status if e.status == PageStatus.BROKEN else PageStatus.IN_DEV

        return replace(
            e,
            section="Дополнительно",
            group="Архив",
            icon="🗃️",
            status=new_status,
            title=new_title,
            help=new_help,
        )

    # Primary (curated) keys: if an autodiscovered page duplicates one of these,
    # it must be archived.
    primary_keys: set[tuple[str, str, str]] = set()
    primary_titles: set[str] = set()
    for e in curated:
        try:
            fn = Path(e.target).name if isinstance(e.target, str) else ""
        except Exception:
            fn = ""
        if e.default or (fn in used_files):
            primary_keys.add((e.section, e.group, e.title))
            primary_titles.add(e.title)

    # Auto-discover remaining pages (not curated).
    for fname, p in sorted(files.items()):
        if fname in used_files:
            continue

        rel = str(p.relative_to(repo))
        is_nonascii = fname.startswith("nonascii_")
        display_fname = fname
        orig_fname = None
        if is_nonascii:
            orig_fname = _extract_original_filename(p)
            if orig_fname:
                display_fname = orig_fname

        section, group = _default_taxonomy_for_file(display_fname)

        # Default: autodiscovered pages are READY unless explicitly marked.
        status = PageStatus.IN_DEV if ("LEGACY" in fname.upper() or "__dup" in fname) else PageStatus.READY
        title = _pretty_title_from_fname(display_fname)

        # nonascii pages often contain a better declared title.
        declared = _extract_declared_title(p) if is_nonascii else None
        if declared:
            title = declared

        entry = PageEntry(
            section=section,
            group=group,
            title=title,
            icon="📄",
            help="Автообнаруженная страница (проверь структуру/статус).",
            status=status,
            target=str(p.resolve()),
            url_path=_stable_url_path(rel),
        )

        # --- Archive policies (reduce duplicates in main menu) ---
        if "LEGACY" in fname.upper() or "__dup" in fname:
            entry = _archive_entry(entry, reason="LEGACY/__dup копия")

        # nonascii_* pages: if they correspond to an existing normal page file,
        # treat them as archive duplicates.
        if is_nonascii and orig_fname and (orig_fname in files) and (files[orig_fname].resolve() != p.resolve()):
            entry = _archive_entry(entry, reason=f"nonascii дубликат страницы {orig_fname}")
        elif is_nonascii and entry.status == PageStatus.READY:
            # Keep unique nonascii pages accessible but clearly marked.
            entry = replace(entry, status=PageStatus.IN_DEV)

        # If this entry duplicates a primary curated page (same section/group/title), archive it.
        if (entry.section, entry.group, entry.title) in primary_keys and ("Архив" not in entry.group):
            entry = _archive_entry(entry, reason="дубликат основной (curated) страницы")

        # nonascii pages with titles matching curated pages are almost always
        # redundant (donor-bundle artifacts). Archive them to avoid confusing
        # "двойные" пункты меню.
        if is_nonascii and (entry.title in primary_titles) and ("Архив" not in entry.group):
            entry = _archive_entry(entry, reason="nonascii копия с тем же заголовком, что и curated страница")

        curated.append(entry)

    # Final pass: avoid identical labels repeated within the same section/group.
    seen: set[tuple[str, str, str]] = set()
    final: list[PageEntry] = []
    for e in curated:
        key = (e.section, e.group, e.title)
        if key in seen and ("Архив" not in e.group):
            e = _archive_entry(e, reason="повторяющийся заголовок в меню")
            key = (e.section, e.group, e.title)
        seen.add(key)
        final.append(e)

    return final


def menu_structure(entries: Iterable[PageEntry]) -> dict[str, dict[str, list[PageEntry]]]:
    """Build ordered menu tree: section -> group -> entries."""
    section_order = [
        "Старт",
        "Модель",
        "Калибровка",
        "Справка",
        "Анализ",
        "Оптимизация",
        "Визуализация",
        "Диагностика",
        "Дополнительно",
    ]

    tree: dict[str, dict[str, list[PageEntry]]] = {}
    for e in entries:
        if not e.show_in_menu:
            continue
        tree.setdefault(e.section, {}).setdefault(e.group, []).append(e)

    # stable order: by explicit section_order then alpha.
    ordered: dict[str, dict[str, list[PageEntry]]] = {}
    for sec in section_order + sorted(k for k in tree.keys() if k not in section_order):
        if sec not in tree:
            continue
        groups = tree[sec]
        ordered_groups: dict[str, list[PageEntry]] = {}
        for grp in sorted(groups.keys()):
            ordered_groups[grp] = sorted(groups[grp], key=lambda x: (0 if x.default else 1, x.title))
        ordered[sec] = ordered_groups
    return ordered


def build_streamlit_pages():
    """Build StreamlitPage objects + page_map for custom menus."""
    import streamlit as st

    from pneumo_solver_ui.pages._page_runner import run_script_page
    from pneumo_solver_ui.ui_wip import render_wip_banner, WipInfo

    
    def _make_page(target: Any, title: str, url_path: str, default: bool = False):
        """Create st.Page with best-effort compatibility across Streamlit versions.

        Notes:
        - Streamlit's default page must map to the root URL (pathname "").
          We therefore *avoid* passing url_path when default=True.
        - Some older versions may not support url_path at all (fallback below).
        """
        kwargs: dict[str, Any] = {"title": title}
        if default:
            kwargs["default"] = True
        else:
            if url_path:
                kwargs["url_path"] = url_path
        try:
            return st.Page(target, **kwargs)
        except TypeError:
            try:
                # very old Streamlit versions
                return st.Page(target, title=title)
            except TypeError:
                return st.Page(target)
    
    entries = get_entries()
    
    pages = []
    page_map = {}
    for e in entries:
        if isinstance(e.target, str):
            target_path = e.target
            if e.status == PageStatus.READY:
                pg = _make_page(target_path, title=e.menu_title(), url_path=e.url_path, default=e.default)
            else:
                # Wrap with WIP banner but still execute original script.
                def _wrapped(tp=target_path, title=e.title, help_text=e.help, status=e.status):
                    import streamlit as st

                    render_wip_banner(
                        st,
                        WipInfo(
                            title=title,
                            reason=help_text or "Страница помечена как WIP.",
                            what_next="Эта страница должна быть доведена до рабочего состояния и переведена в READY.",
                        ),
                    )
                    run_script_page(tp, auto_bundle=True)

                pg = _make_page(_wrapped, title=e.menu_title(), url_path=e.url_path, default=e.default)
        else:
            pg = _make_page(e.target, title=e.menu_title(), url_path=e.url_path, default=e.default)

        pages.append(pg)
        page_map[e.url_path] = pg

    return entries, pages, page_map
