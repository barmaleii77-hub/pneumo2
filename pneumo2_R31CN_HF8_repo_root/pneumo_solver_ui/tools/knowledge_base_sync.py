#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""knowledge_base_sync.py

Lightweight knowledge-base capture and sync tool for project chat decisions.

What it does:
- stores chat-derived requirements and plans in a local JSON store;
- regenerates the markdown logs in docs/;
- can optionally stage/commit/push the knowledge-base files to git.

This tool does not replace the canonical law/registry/data-contract layer.
It is the operational capture layer for chat-originated requirements and plans.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _docs_dir(repo_root: Path) -> Path:
    return repo_root / "docs"


def knowledge_base_store_path(repo_root: Path | None = None) -> Path:
    root = repo_root or _repo_root()
    return _docs_dir(root) / "15_CHAT_KNOWLEDGE_BASE.json"


def knowledge_base_requirement_log_path(repo_root: Path | None = None) -> Path:
    root = repo_root or _repo_root()
    return _docs_dir(root) / "13_CHAT_REQUIREMENTS_LOG.md"


def knowledge_base_plan_log_path(repo_root: Path | None = None) -> Path:
    root = repo_root or _repo_root()
    return _docs_dir(root) / "14_CHAT_PLANS_LOG.md"


def knowledge_base_tracked_paths(repo_root: Path | None = None) -> tuple[Path, ...]:
    root = repo_root or _repo_root()
    return (
        _docs_dir(root) / "00_PROJECT_KNOWLEDGE_BASE.md",
        knowledge_base_requirement_log_path(root),
        knowledge_base_plan_log_path(root),
        knowledge_base_store_path(root),
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _empty_store() -> dict[str, Any]:
    return {
        "schema": "pneumo.chat_knowledge_base.v1",
        "updated_at": _utc_now_iso(),
        "requirements": [],
        "plans": [],
    }


def load_knowledge_base_store(repo_root: Path | None = None) -> dict[str, Any]:
    path = knowledge_base_store_path(repo_root)
    if not path.exists():
        return _empty_store()
    return json.loads(path.read_text(encoding="utf-8"))


def save_knowledge_base_store(store: dict[str, Any], repo_root: Path | None = None) -> Path:
    path = knowledge_base_store_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    store["updated_at"] = _utc_now_iso()
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _next_entry_id(entries: list[dict[str, Any]], prefix: str) -> str:
    max_no = 0
    for entry in entries:
        rid = str(entry.get("id", ""))
        if not rid.startswith(prefix):
            continue
        tail = rid.removeprefix(prefix)
        if tail.isdigit():
            max_no = max(max_no, int(tail))
    return f"{prefix}{max_no + 1:04d}"


def _entry_exists(entries: list[dict[str, Any]], *, title: str, details: str) -> bool:
    key = (_normalize_text(title), _normalize_text(details))
    for entry in entries:
        entry_key = (
            _normalize_text(str(entry.get("title", ""))),
            _normalize_text(str(entry.get("details", ""))),
        )
        if entry_key == key:
            return True
    return False


def add_chat_requirement(
    store: dict[str, Any],
    *,
    title: str,
    details: str,
    status: str = "активно",
    source: str = "chat",
) -> bool:
    entries = store.setdefault("requirements", [])
    if _entry_exists(entries, title=title, details=details):
        return False
    entries.append(
        {
            "id": _next_entry_id(entries, "REQ-"),
            "created_at": _utc_now_iso(),
            "source": source,
            "title": title.strip(),
            "details": details.strip(),
            "status": status.strip(),
        }
    )
    return True


def add_chat_plan(
    store: dict[str, Any],
    *,
    title: str,
    details: str,
    artifact_path: str = "",
    status: str = "актуален",
    source: str = "chat",
) -> bool:
    entries = store.setdefault("plans", [])
    if _entry_exists(entries, title=title, details=details):
        return False
    entries.append(
        {
            "id": _next_entry_id(entries, "PLAN-"),
            "created_at": _utc_now_iso(),
            "source": source,
            "title": title.strip(),
            "details": details.strip(),
            "artifact_path": artifact_path.strip(),
            "status": status.strip(),
        }
    )
    return True


def render_chat_requirements_markdown(store: dict[str, Any]) -> str:
    lines = [
        "# Журнал требований из чатов проекта",
        "",
        "> Этот файл обновляется через `pneumo_solver_ui.tools.knowledge_base_sync`.",
        "",
        "## Назначение",
        "",
        "Этот файл фиксирует пользовательские хотелки, решения и рабочие директивы, которые были сформулированы в чатах проекта и должны сохраняться для последующего использования.",
        "",
        "Это не канон уровня `ABSOLUTE LAW`, но это обязательный knowledge-base слой рабочего контекста.",
        "",
        "## Правило ведения",
        "",
        "- добавлять сюда каждую существенную пользовательскую хотелку из чатов проекта;",
        "- писать кратко, но однозначно;",
        "- если требование потом реализовано, не удалять его, а отмечать статус;",
        "- если требование конфликтует с каноном, канон важнее, но конфликт должен быть явно отмечен.",
        "",
        "## Активные требования, уже зафиксированные в чатах",
        "",
    ]

    requirements = list(store.get("requirements", []))
    if not requirements:
        lines.append("_Пока записей нет._")
    else:
        for index, entry in enumerate(requirements, start=1):
            lines.append(f"{index}. {entry.get('title', '').strip()}")
            details = str(entry.get("details", "")).strip()
            status = str(entry.get("status", "активно")).strip()
            if details and not _normalize_text(details).startswith("статус:"):
                lines.append(details)
            lines.append(f"Статус: {status}.")
            lines.append(f"Источник: {entry.get('source', 'chat')}.")
            lines.append(f"ID: `{entry.get('id', '')}`.")
            lines.append("")

    lines.extend(
        [
            "## Как ссылаться из будущих задач",
            "",
            "Если новая задача опирается на решение из чата, но не отражена в старом каноне, сначала проверить этот файл, а затем соответствующие plan-файлы из [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md).",
            "",
        ]
    )
    return "\n".join(lines)


def render_chat_plans_markdown(store: dict[str, Any]) -> str:
    lines = [
        "# Журнал планов, сгенерированных чатами проекта",
        "",
        "> Этот файл обновляется через `pneumo_solver_ui.tools.knowledge_base_sync`.",
        "",
        "## Назначение",
        "",
        "Этот файл фиксирует планы, decomposition-пакеты, migration-планы и prompt-наборы, которые были сгенерированы в чатах проекта и должны учитываться как рабочий knowledge-base слой.",
        "",
        "## Правило ведения",
        "",
        "- если чат генерирует рабочий план, migration-map, prompt-pack или ownership matrix, он должен попасть в этот журнал;",
        "- здесь хранится не полный текст каждого плана, а карта plan-артефактов и их назначение;",
        "- полный текст должен лежать в отдельном файле, а здесь должна быть ссылка на него и краткое описание;",
        "- более новый план не стирает старый автоматически: сначала нужно понять, заменяет ли он его или дополняет.",
        "",
        "## Актуальные plan-артефакты",
        "",
    ]

    plans = list(store.get("plans", []))
    if not plans:
        lines.append("_Пока записей нет._")
    else:
        for index, entry in enumerate(plans, start=1):
            lines.append(f"{index}. {entry.get('title', '').strip()}")
            details = str(entry.get("details", "")).strip()
            if details:
                lines.append(f"Назначение: {details}")
            artifact_path = str(entry.get("artifact_path", "")).strip()
            if artifact_path:
                lines.append(f"Артефакт: [{artifact_path}](./{artifact_path})")
            lines.append(f"Статус: {entry.get('status', 'актуален')}.")
            lines.append(f"Источник: {entry.get('source', 'chat')}.")
            lines.append(f"ID: `{entry.get('id', '')}`.")
            lines.append("")

    lines.extend(
        [
            "## Текущее правило интерпретации",
            "",
            "Если в будущем возникает вопрос:",
            "",
            '- "какой план у проекта сейчас?",',
            '- "какой prompt выдавать новому чату?",',
            '- "какая декомпозиция уже была согласована?",',
            "",
            "то сначала нужно читать этот файл, затем открывать соответствующий linked plan document.",
            "",
        ]
    )
    return "\n".join(lines)


def write_chat_logs(store: dict[str, Any], repo_root: Path | None = None) -> tuple[Path, Path]:
    req_path = knowledge_base_requirement_log_path(repo_root)
    plan_path = knowledge_base_plan_log_path(repo_root)
    req_path.write_text(render_chat_requirements_markdown(store) + "\n", encoding="utf-8")
    plan_path.write_text(render_chat_plans_markdown(store) + "\n", encoding="utf-8")
    return req_path, plan_path


def git_sync_knowledge_base(
    *,
    repo_root: Path | None = None,
    commit_message: str,
    push: bool = True,
) -> None:
    root = repo_root or _repo_root()
    tracked = [str(path.relative_to(root)) for path in knowledge_base_tracked_paths(root) if path.exists()]
    if not tracked:
        return

    subprocess.run(["git", "-C", str(root), "add", *tracked], check=True)

    staged = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--quiet"],
        check=False,
    )
    if staged.returncode == 0:
        return

    subprocess.run(["git", "-C", str(root), "commit", "-m", commit_message], check=True)
    if not push:
        return

    pushed = subprocess.run(["git", "-C", str(root), "push"], check=False)
    if pushed.returncode != 0:
        subprocess.run(["git", "-C", str(root), "push", "-u", "origin", "HEAD"], check=True)


def seed_default_chat_knowledge_base() -> dict[str, Any]:
    store = _empty_store()

    seed_requirements = [
        (
            "Проект должен мигрировать из WEB в понятный классический desktop GUI под Windows без потери функциональности.",
            "Статус: активно.",
        ),
        (
            "WEB больше не является целевой платформой развития пользовательских сценариев.",
            "В WEB допустимы только минимальные мосты, launch-кнопки и reference-поведение до полного переноса в GUI.",
        ),
        (
            "Главные операторские сценарии должны жить в GUI.",
            "Состав: главное окно приложения; ввод исходных данных; настройка расчёта; редактор и генератор сценариев колец; compare viewer; desktop mnemo; desktop animator; optimizer center; diagnostics/send bundle; validation/results/test center; geometry/reference center; engineering analysis/calibration/influence.",
        ),
        (
            "Архитектура GUI должна быть модульной и пригодной для параллельной разработки разными чатами без пересечения по тем же файлам.",
            "Статус: активно.",
        ),
        (
            "Нельзя дублировать домены Desktop Animator, Compare Viewer и Desktop Mnemo в других окнах без отдельной необходимости.",
            "Статус: активно.",
        ),
        (
            "Главное desktop-приложение должно быть классическим Windows GUI с верхним меню и многооконным интерфейсом внутри приложения.",
            "Статус: активно.",
        ),
        (
            "Ввод исходных данных должен быть удобным, секционным и понятным для пользователя.",
            "Минимальные кластеры: геометрия; пневматика; механика; настройки расчёта.",
        ),
        (
            "Все пользовательские хотелки из чатов этого проекта должны записываться в базу знаний.",
            "Статус: активно.",
        ),
        (
            "Все планы работ, prompt-пакеты и decomposition, которые генерируют чаты этого проекта, должны записываться в базу знаний.",
            "Статус: активно.",
        ),
        (
            "Release-gate closure must stay evidence-mapped before runtime closure claims.",
            "V32-16 uses RELEASE_GATE_ACCEPTANCE_MAP.md, RELEASE_GATE_HARDENING_MATRIX.csv and GAP_TO_EVIDENCE_ACTION_MAP.csv to require artifact/test/bundle evidence before any gate or open gap can be treated as closed.",
        ),
    ]
    for title, details in seed_requirements:
        add_chat_requirement(store, title=title, details=details)

    seed_plans = [
        ("GUI_MIGRATION_CHAT_PROMPTS.md", "GUI-only пакет миграции из WEB в desktop GUI по отдельным направлениям.", "GUI_MIGRATION_CHAT_PROMPTS.md", "актуален"),
        ("PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md", "Исторический пакет параллельной разработки GUI и WEB. После решения о GUI-first WEB-часть использовать только как reference.", "PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md", "частично актуален"),
        ("gui_chat_prompts/00_INDEX.md", "Индекс prompt-файлов для параллельных GUI-чатов.", "gui_chat_prompts/00_INDEX.md", "актуален"),
        ("gui_chat_prompts/01_MAIN_WINDOW.md", "Главное окно приложения.", "gui_chat_prompts/01_MAIN_WINDOW.md", "актуален"),
        ("gui_chat_prompts/02_INPUT_DATA.md", "Ввод исходных данных.", "gui_chat_prompts/02_INPUT_DATA.md", "актуален"),
        ("gui_chat_prompts/03_RUN_SETUP.md", "Настройка расчёта.", "gui_chat_prompts/03_RUN_SETUP.md", "актуален"),
        ("gui_chat_prompts/04_RING_EDITOR.md", "Редактор и генератор сценариев колец.", "gui_chat_prompts/04_RING_EDITOR.md", "актуален"),
        ("gui_chat_prompts/05_COMPARE_VIEWER.md", "Compare viewer.", "gui_chat_prompts/05_COMPARE_VIEWER.md", "актуален"),
        ("gui_chat_prompts/06_DESKTOP_MNEMO.md", "Desktop mnemo.", "gui_chat_prompts/06_DESKTOP_MNEMO.md", "актуален"),
        ("gui_chat_prompts/07_DESKTOP_ANIMATOR.md", "Desktop animator.", "gui_chat_prompts/07_DESKTOP_ANIMATOR.md", "актуален"),
        ("gui_chat_prompts/08_OPTIMIZER_CENTER.md", "Optimizer center со всеми настройками.", "gui_chat_prompts/08_OPTIMIZER_CENTER.md", "актуален"),
        ("gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md", "Diagnostics и send bundle.", "gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md", "актуален"),
        ("gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md", "Test, validation, results center.", "gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md", "актуален"),
        ("gui_chat_prompts/11_GEOMETRY_REFERENCE.md", "Geometry, catalogs, reference.", "gui_chat_prompts/11_GEOMETRY_REFERENCE.md", "актуален"),
        ("gui_chat_prompts/12_ENGINEERING_ANALYSIS.md", "Engineering analysis, calibration, influence.", "gui_chat_prompts/12_ENGINEERING_ANALYSIS.md", "актуален"),
        ("gui_chat_prompts/13_RELEASE_GATES_KB_ACCEPTANCE.md", "Release gates, KB, source authority and acceptance map for V32-16.", "gui_chat_prompts/13_RELEASE_GATES_KB_ACCEPTANCE.md", "актуален"),
        ("context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md", "Repo-side map from v32 release hardening and open gaps to required evidence.", "context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md", "актуален"),
    ]
    for title, details, artifact_path, status in seed_plans:
        add_chat_plan(store, title=title, details=details, artifact_path=artifact_path, status=status)

    return store


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed-defaults")
    seed.add_argument("--git-sync", action=argparse.BooleanOptionalAction, default=False)
    seed.add_argument("--push", action=argparse.BooleanOptionalAction, default=False)

    rebuild = sub.add_parser("rebuild")
    rebuild.add_argument("--git-sync", action=argparse.BooleanOptionalAction, default=False)
    rebuild.add_argument("--push", action=argparse.BooleanOptionalAction, default=False)

    req = sub.add_parser("add-requirement")
    req.add_argument("--title", required=True)
    req.add_argument("--details", required=True)
    req.add_argument("--status", default="активно")
    req.add_argument("--source", default="chat")
    req.add_argument("--git-sync", action=argparse.BooleanOptionalAction, default=True)
    req.add_argument("--push", action=argparse.BooleanOptionalAction, default=True)

    plan = sub.add_parser("add-plan")
    plan.add_argument("--title", required=True)
    plan.add_argument("--details", required=True)
    plan.add_argument("--artifact-path", default="")
    plan.add_argument("--status", default="актуален")
    plan.add_argument("--source", default="chat")
    plan.add_argument("--git-sync", action=argparse.BooleanOptionalAction, default=True)
    plan.add_argument("--push", action=argparse.BooleanOptionalAction, default=True)

    return parser


def _commit_message_for_args(args: argparse.Namespace) -> str:
    if args.command == "add-requirement":
        return f"docs(kb): capture chat requirement - {args.title}"
    if args.command == "add-plan":
        return f"docs(kb): capture chat plan - {args.title}"
    if args.command == "seed-defaults":
        return "docs(kb): seed chat knowledge base"
    return "docs(kb): rebuild chat knowledge base"


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    repo_root = _repo_root()
    store = load_knowledge_base_store(repo_root)

    if args.command == "seed-defaults":
        if not store.get("requirements") and not store.get("plans"):
            store = seed_default_chat_knowledge_base()
    elif args.command == "add-requirement":
        add_chat_requirement(
            store,
            title=args.title,
            details=args.details,
            status=args.status,
            source=args.source,
        )
    elif args.command == "add-plan":
        add_chat_plan(
            store,
            title=args.title,
            details=args.details,
            artifact_path=args.artifact_path,
            status=args.status,
            source=args.source,
        )

    save_knowledge_base_store(store, repo_root)
    write_chat_logs(store, repo_root)

    if getattr(args, "git_sync", False):
        git_sync_knowledge_base(
            repo_root=repo_root,
            commit_message=_commit_message_for_args(args),
            push=getattr(args, "push", False),
        )

    print(f"[OK] knowledge-base store: {knowledge_base_store_path(repo_root)}")
    print(f"[OK] requirements log: {knowledge_base_requirement_log_path(repo_root)}")
    print(f"[OK] plans log: {knowledge_base_plan_log_path(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
