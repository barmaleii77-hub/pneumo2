# -*- coding: utf-8 -*-
"""project_state.py

Проектная структура хранения пользовательских настроек и данных.

Зачем:
- Требование проекта: введённые пользователем значения/настройки не должны пропадать
  при обновлении страницы/перезапуске.
- Плюс: инженеру часто нужно вести несколько независимых конфигураций (проекты).

Решение:
- PNEUMO_STATE_DIR = корень хранения (задаётся переменной окружения, либо рядом с приложением).
- Внутри корня создаётся каталог projects/<project_name>/...

Внутри каждого проекта:
- ui_state/autosave_profile.json
- ui_state/profiles/*.json
- user_data/uploads/*
- user_data/scenarios/*
- exports/*

Модуль **без Streamlit**, чтобы его можно было использовать в самопроверках и CLI.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


DEFAULT_PROJECT = "default"
_WINDOWS_FORBIDDEN = set('<>:"/\\|?*')


def sanitize_project_name(name: str) -> str:
    """Make a filesystem-safe project name.

    Разрешаем русские буквы, но убираем запрещённые для Windows символы.
    """
    s = str(name or "").strip()
    if not s:
        return DEFAULT_PROJECT
    out: List[str] = []
    for ch in s:
        if ch in _WINDOWS_FORBIDDEN:
            out.append("_")
        elif ch in ("\n", "\r", "\t"):
            out.append(" ")
        else:
            out.append(ch)
    s2 = "".join(out).strip().strip(".")
    if not s2:
        s2 = DEFAULT_PROJECT
    if len(s2) > 80:
        s2 = s2[:80].rstrip()
    return s2


@dataclass(frozen=True)
class ProjectPaths:
    state_root: Path
    project_name: str
    projects_root: Path
    project_dir: Path

    ui_state_dir: Path
    autosave_profile_path: Path
    profiles_dir: Path

    user_data_dir: Path
    uploads_dir: Path
    scenarios_dir: Path

    exports_dir: Path


def get_project_paths(state_root: Path, project_name: str) -> ProjectPaths:
    state_root = Path(state_root).expanduser().resolve()
    projects_root = state_root / "projects"
    pn = sanitize_project_name(project_name)
    project_dir = projects_root / pn

    ui_state_dir = project_dir / "ui_state"
    autosave_profile_path = ui_state_dir / "autosave_profile.json"
    profiles_dir = ui_state_dir / "profiles"

    user_data_dir = project_dir / "user_data"
    uploads_dir = user_data_dir / "uploads"
    scenarios_dir = user_data_dir / "scenarios"

    exports_dir = project_dir / "exports"

    return ProjectPaths(
        state_root=state_root,
        project_name=pn,
        projects_root=projects_root,
        project_dir=project_dir,
        ui_state_dir=ui_state_dir,
        autosave_profile_path=autosave_profile_path,
        profiles_dir=profiles_dir,
        user_data_dir=user_data_dir,
        uploads_dir=uploads_dir,
        scenarios_dir=scenarios_dir,
        exports_dir=exports_dir,
    )


def ensure_project_dirs(paths: ProjectPaths) -> None:
    for p in [
        paths.projects_root,
        paths.project_dir,
        paths.ui_state_dir,
        paths.profiles_dir,
        paths.user_data_dir,
        paths.uploads_dir,
        paths.scenarios_dir,
        paths.exports_dir,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def _current_project_file(state_root: Path) -> Path:
    state_root = Path(state_root).expanduser().resolve()
    return state_root / "projects" / "_current_project.json"


def list_projects(state_root: Path) -> List[str]:
    """List existing projects under state_root/projects."""
    pr = Path(state_root).expanduser().resolve() / "projects"
    if not pr.exists():
        return []
    out: List[str] = []
    for p in sorted(pr.iterdir()):
        if not p.is_dir():
            continue
        if p.name.startswith("_"):
            continue
        out.append(p.name)
    return out


def read_current_project(state_root: Path, default: str = DEFAULT_PROJECT) -> str:
    """Read active project from disk (or env), ensure it exists, return sanitized name."""
    state_root = Path(state_root).expanduser().resolve()

    # env override (useful for CI / distributed runs)
    env_name = (os.environ.get("PNEUMO_PROJECT") or "").strip()
    if env_name:
        name = sanitize_project_name(env_name)
        pp = get_project_paths(state_root, name)
        ensure_project_dirs(pp)
        # do not overwrite disk file automatically (respect env)
        return name

    p = _current_project_file(state_root)
    name = ""
    try:
        if p.exists():
            data = json.loads(p.read_text("utf-8"))
            if isinstance(data, dict):
                name = str(data.get("project") or "").strip()
    except Exception:
        name = ""

    if not name:
        name = default

    name = sanitize_project_name(name)
    pp = get_project_paths(state_root, name)
    ensure_project_dirs(pp)
    return name


def write_current_project(state_root: Path, project_name: str) -> str:
    """Persist active project to disk. Returns sanitized name."""
    state_root = Path(state_root).expanduser().resolve()
    name = sanitize_project_name(project_name)
    pp = get_project_paths(state_root, name)
    ensure_project_dirs(pp)

    p = _current_project_file(state_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"project": name, "saved_at": datetime.now().isoformat(timespec="seconds")}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return name


def migrate_legacy_state(state_root: Path, default_project: str = DEFAULT_PROJECT) -> List[str]:
    """Migrate pre-project-layout folders into projects/<default_project>/... (best effort).

    Legacy layout (old):
      state_root/ui_state/autosave_profile.json
      state_root/ui_state/profiles/*.json
      state_root/user_data/(uploads|scenarios)/*

    New layout:
      state_root/projects/<project>/ui_state/...
      state_root/projects/<project>/user_data/...

    Migration is idempotent: only copies/moves when destination is missing.
    Returns list of human-readable messages (what was migrated).
    """
    msgs: List[str] = []
    state_root = Path(state_root).expanduser().resolve()

    legacy_ui_state = state_root / "ui_state"
    legacy_user_data = state_root / "user_data"

    dp_name = sanitize_project_name(default_project)
    dp = get_project_paths(state_root, dp_name)
    ensure_project_dirs(dp)

    # autosave
    try:
        src = legacy_ui_state / "autosave_profile.json"
        dst = dp.autosave_profile_path
        if src.exists() and (not dst.exists()):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            msgs.append(f"Скопирован autosave_profile.json -> projects/{dp_name}/ui_state/")
    except Exception as e:
        msgs.append(f"Не удалось перенести autosave_profile.json: {e}")

    # profiles
    try:
        src_dir = legacy_ui_state / "profiles"
        dst_dir = dp.profiles_dir
        if src_dir.exists() and src_dir.is_dir():
            dst_dir.mkdir(parents=True, exist_ok=True)
            # копируем только если в новом профиле нет файлов
            if not any(dst_dir.glob("*.json")):
                for fp in src_dir.glob("*.json"):
                    try:
                        shutil.copy2(fp, dst_dir / fp.name)
                    except Exception:
                        pass
                msgs.append(f"Скопированы profiles/*.json -> projects/{dp_name}/ui_state/profiles/")
    except Exception as e:
        msgs.append(f"Не удалось перенести profiles: {e}")

    # user_data subfolders
    for sub in ("uploads", "scenarios"):
        try:
            src_dir = legacy_user_data / sub
            dst_dir = (dp.user_data_dir / sub)
            if src_dir.exists() and src_dir.is_dir():
                dst_dir.mkdir(parents=True, exist_ok=True)
                if not any(dst_dir.iterdir()):
                    # предпочитаем move (чтобы не плодить копии), но не обязуемся
                    try:
                        for fp in src_dir.iterdir():
                            shutil.move(str(fp), str(dst_dir / fp.name))
                        msgs.append(f"Перенесены user_data/{sub} -> projects/{dp_name}/user_data/{sub}")
                    except Exception:
                        # fallback: copy
                        for fp in src_dir.iterdir():
                            try:
                                if fp.is_file():
                                    shutil.copy2(fp, dst_dir / fp.name)
                            except Exception:
                                pass
                        msgs.append(f"Скопированы user_data/{sub} -> projects/{dp_name}/user_data/{sub}")
        except Exception as e:
            msgs.append(f"Не удалось перенести user_data/{sub}: {e}")

    return msgs


def build_project_export_zip(
    paths: ProjectPaths,
    *,
    include_autosave: bool = True,
    include_profiles: bool = True,
    include_user_data: bool = True,
) -> bytes:
    """Create a portable ZIP with project configuration and user inputs.

    ZIP contents are intentionally limited (no heavy results/logs):
    - ui_state/autosave_profile.json (optional)
    - ui_state/profiles/*.json (optional)
    - user_data/uploads/* (optional)
    - user_data/scenarios/* (optional)
    - meta.json

    Returns ZIP bytes (in-memory).
    """
    ensure_project_dirs(paths)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        meta = {
            "schema": "pneumo-project-export",
            "version": 1,
            "project_name": paths.project_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        def _add_file(fs_path: Path, arc_name: str) -> None:
            try:
                if fs_path.exists() and fs_path.is_file():
                    z.write(fs_path, arcname=arc_name)
            except Exception:
                pass

        def _add_dir(dir_path: Path, arc_prefix: str) -> None:
            if not dir_path.exists() or (not dir_path.is_dir()):
                return
            for fp in dir_path.rglob("*"):
                try:
                    if fp.is_file():
                        rel = fp.relative_to(dir_path).as_posix()
                        z.write(fp, arcname=f"{arc_prefix}/{rel}")
                except Exception:
                    continue

        if include_autosave:
            _add_file(paths.autosave_profile_path, "ui_state/autosave_profile.json")
        if include_profiles:
            _add_dir(paths.profiles_dir, "ui_state/profiles")
        if include_user_data:
            _add_dir(paths.uploads_dir, "user_data/uploads")
            _add_dir(paths.scenarios_dir, "user_data/scenarios")

    return buf.getvalue()


def _zip_is_safe_member(name: str) -> bool:
    # Prevent zip-slip (path traversal) and absolute paths
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    norm = name.replace("\\", "/")
    if ".." in [p for p in norm.split("/") if p]:
        return False
    return True


def import_project_from_zip(
    state_root: Path,
    zip_bytes: bytes,
    project_name: str,
    *,
    overwrite: bool = False,
) -> ProjectPaths:
    """Import project ZIP into projects/<project_name>/...

    The ZIP is expected to be created by build_project_export_zip().
    Extraction is guarded against path traversal.
    """
    state_root = Path(state_root).expanduser().resolve()
    pn = sanitize_project_name(project_name)
    paths = get_project_paths(state_root, pn)
    ensure_project_dirs(paths)

    if overwrite:
        # Remove existing content (best effort, but keep the project_dir itself)
        for sub in [paths.ui_state_dir, paths.user_data_dir, paths.exports_dir]:
            try:
                if sub.exists():
                    shutil.rmtree(sub)
            except Exception:
                pass
        ensure_project_dirs(paths)

    with zipfile.ZipFile(io.BytesIO(zip_bytes), mode="r") as z:
        for member in z.infolist():
            name = member.filename
            if not _zip_is_safe_member(name):
                continue
            # only allow known prefixes
            if not (name.startswith("ui_state/") or name.startswith("user_data/") or name == "meta.json"):
                continue
            # directories are fine
            if name.endswith("/"):
                continue
            dest = paths.project_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(member, "r") as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)

    return paths
