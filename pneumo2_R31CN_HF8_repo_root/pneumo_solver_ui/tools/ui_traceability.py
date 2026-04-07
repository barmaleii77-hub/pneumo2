"""UI traceability guard (не строгий).

Идея:
- UI — большая поверхность. Случайный «рефакторинг» легко может «урезать» меню/страницы.
- Пользователь явно запретил «ничего не должно пропадать».

Поэтому держим простой guard:
- В репозитории лежит snapshot ожидаемого набора UI-страниц.
- Самопроверка сравнивает snapshot с текущими файлами.
- Если что-то исчезло — выдаём предупреждение (warning), но не валим приложение.

Это не заменяет полноценный UI-аудит, но хорошо ловит регрессии.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import json


SNAPSHOT_FILENAME = "ui_trace_snapshot.json"


def _repo_root() -> Path:
    # .../pneumo_solver_ui/tools/ui_traceability.py -> repo_root
    return Path(__file__).resolve().parents[2]


def snapshot_path() -> Path:
    return Path(__file__).resolve().with_name(SNAPSHOT_FILENAME)


def collect_ui_files(repo_root: Path | None = None) -> List[str]:
    """Собирает относительные пути UI-страниц (pages + pages_legacy)."""

    rr = repo_root or _repo_root()
    rels: List[str] = []

    for sub in ["pneumo_solver_ui/pages", "pneumo_solver_ui/pages_legacy"]:
        d = rr / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("*.py")):
            # внутренние утилиты не считаем как «страницы»
            if p.name.startswith("_"):
                continue
            rels.append(str(p.relative_to(rr)).replace("\\", "/"))

    return sorted(rels)


def load_snapshot(path: Path | None = None) -> Dict:
    p = path or snapshot_path()
    return json.loads(p.read_text(encoding="utf-8"))


def write_snapshot(files: List[str], path: Path | None = None) -> Path:
    p = path or snapshot_path()
    payload = {
        "files": sorted(files),
        "count": len(files),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def compare_snapshot(snapshot: Dict, current_files: List[str]) -> Tuple[List[str], List[str]]:
    """Возвращает (missing, extra)."""

    snap = set(snapshot.get("files", []) or [])
    cur = set(current_files)
    missing = sorted(snap - cur)
    extra = sorted(cur - snap)
    return missing, extra
