from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Iterable


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_existing_files(
    root: Path,
    patterns: tuple[str, ...],
    *,
    recursive: bool,
    max_candidates: int,
) -> Iterable[Path]:
    if not root.exists():
        return
    seen: set[Path] = set()
    checked = 0
    for pattern in patterns:
        iterator = root.rglob(pattern) if recursive else root.glob(pattern)
        for path in iterator:
            if checked >= max_candidates:
                return
            checked += 1
            if path in seen:
                continue
            seen.add(path)
            try:
                if path.is_file():
                    yield path
            except OSError:
                continue


def _latest_path(
    root: Path,
    patterns: tuple[str, ...],
    *,
    recursive: bool = True,
    max_candidates: int = 512,
) -> Path | None:
    files = list(
        _iter_existing_files(
            root,
            patterns,
            recursive=recursive,
            max_candidates=max_candidates,
        )
    )
    if not files:
        return None
    return max(files, key=lambda path: _safe_mtime(path))


def _latest_from_roots(
    roots: tuple[Path, ...],
    patterns: tuple[str, ...],
    *,
    recursive: bool = False,
    max_candidates_per_root: int = 256,
) -> Path | None:
    candidates = [
        path
        for root in roots
        for path in _iter_existing_files(
            root,
            patterns,
            recursive=recursive,
            max_candidates=max_candidates_per_root,
        )
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: _safe_mtime(path))


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


@dataclass(frozen=True)
class OverviewCardState:
    title: str
    value: str
    detail: str
    command_id: str
    action_text: str = "Открыть"


@dataclass(frozen=True)
class OverviewSnapshot:
    cards: tuple[OverviewCardState, ...]


def build_overview_snapshot(repo_root: Path | None = None) -> OverviewSnapshot:
    root = repo_root or _repo_root()
    runs_root = root / "runs"
    desktop_root = Path.home() / "Desktop"
    baseline_path = (
        _latest_path(
            runs_root,
            ("*baseline*.json", "*baseline*.npz", "*baseline*.csv"),
            max_candidates=512,
        )
        if runs_root.exists()
        else None
    )
    result_path = (
        _latest_path(
            runs_root,
            ("*.npz", "summary*.json", "*results*.json"),
            max_candidates=512,
        )
        if runs_root.exists()
        else None
    )
    bundle_path = _latest_from_roots(
        (
            root / "send_bundles",
            root / "diagnostics_runs",
            root / "pneumo_solver_ui" / "send_bundles",
            desktop_root,
        ),
        ("SEND_*.zip", "*bundle*.zip", "diagnostics.zip", "send_bundles.zip"),
        recursive=False,
        max_candidates_per_root=256,
    )

    pyside6_ready = find_spec("PySide6") is not None
    animator_ready = find_spec("pneumo_solver_ui.desktop_animator.app") is not None
    diagnostics_ready = (root / "pneumo_solver_ui" / "tools" / "desktop_diagnostics_center.py").exists()
    workflow_graphs_ready = (
        (root / "docs" / "context" / "gui_spec_imports" / "current_pipeline.dot").exists()
        and (root / "docs" / "context" / "gui_spec_imports" / "optimized_pipeline.dot").exists()
    )

    cards = (
        OverviewCardState(
            title="Текущий проект",
            value=root.name,
            detail=str(root),
            command_id="workspace.input_data.open",
            action_text="Открыть исходные данные",
        ),
        OverviewCardState(
            title="Активный опорный прогон",
            value=_safe_relative(baseline_path, root) if baseline_path else "Не выбран",
            detail="Источник данных по опорному прогону должен быть виден в отдельном рабочем шаге.",
            command_id="workspace.baseline_run.open",
            action_text="Открыть базовый прогон",
        ),
        OverviewCardState(
            title="Настройки оптимизации",
            value="Поэтапный запуск - основной режим",
            detail="Распределённая координация остаётся расширенным режимом и не должна конкурировать с основным запуском.",
            command_id="workspace.optimization.open",
            action_text="Открыть оптимизацию",
        ),
        OverviewCardState(
            title="Последние результаты",
            value=_safe_relative(result_path, root) if result_path else "Пока нет файлов результатов",
            detail="Результаты и сравнение доступны в анализе результатов.",
            command_id="results.center.open",
            action_text="Открыть анализ результатов",
        ),
        OverviewCardState(
            title="Последний архив проекта",
            value=str(bundle_path.name) if bundle_path else "Архив пока не найден",
            detail=str(bundle_path.parent) if bundle_path else "Проверка проекта и архив должны оставаться доступными из любого рабочего шага приложения.",
            command_id="diagnostics.collect_bundle",
            action_text="Сохранить архив проекта",
        ),
        OverviewCardState(
            title="Проверка готовности",
            value=(
                f"Основные окна: {'готовы' if pyside6_ready else 'не найдены'} | "
                f"Аниматор: {'найден' if animator_ready else 'не найден'} | "
                f"Проверка проекта и архив: {'готовы' if diagnostics_ready else 'не найдены'}"
            ),
            detail=(
                "Схема последовательности "
                + ("готова" if workflow_graphs_ready else "не найдена")
            + "; рабочее место должно открывать существующие инженерные окна без скрытой подмены."
            ),
            command_id="workspace.diagnostics.open",
            action_text="Открыть проверку проекта",
        ),
    )
    return OverviewSnapshot(cards=cards)
