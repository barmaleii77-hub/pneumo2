#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bundle_lock.py

Межпроцессная защита (lock) для сборки Send Bundle.

Зачем
-----
В проекте есть несколько потенциальных триггеров сборки send bundle:

- normal path: launcher после закрытия Streamlit
- atexit safety net
- postmortem_watchdog
- ручной запуск send_results_gui

Без lock'а эти триггеры могут сработать одновременно и:
- начать параллельно писать один и тот же latest_send_bundle.zip
- повредить sidecar-файлы latest_* (частичная запись)

Решение
--------
Используем lock-файл с *атомарным созданием* через O_CREAT|O_EXCL.
Это стандартная техника: если файл уже существует, создание падает.
На POSIX и Windows это даёт простой и достаточно надёжный "mutex".

Источник (в терминах POSIX):
- open() с O_CREAT и O_EXCL должен падать, если файл существует, и проверка
  существования + создание происходят атомарно. (Open Group / POSIX)

Ограничения
-----------
Это best-effort lock для локального диска. На некоторых NFS-конфигурациях
O_EXCL может быть небезопасным. Мы для проекта "пневмо" предполагаем локальные
пути (обычные user workstation).

"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _now() -> float:
    return time.time()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _pid_alive(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        pid_i = int(pid)
    except Exception:
        return False
    if pid_i <= 0:
        return False

    if os.name == "nt":
        # best-effort Windows check without external deps
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, int(pid_i))
            if not handle:
                return False
            code = wintypes.DWORD()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            if not ok:
                return False
            return int(code.value) == STILL_ACTIVE
        except Exception:
            return False

    # POSIX
    try:
        os.kill(int(pid_i), 0)
        return True
    except Exception:
        return False


@dataclass
class LockInfo:
    pid: Optional[int] = None
    created_at: Optional[float] = None
    release: Optional[str] = None
    note: Optional[str] = None


class SendBundleLock:
    """Контекстный менеджер для межпроцессного lock'а на сборку send bundle."""

    def __init__(
        self,
        lock_path: Path,
        *,
        timeout_s: float = 180.0,
        poll_s: float = 0.25,
        stale_ttl_s: float = 600.0,
        release: str = "",
    ) -> None:
        self.lock_path = Path(lock_path)
        self.timeout_s = float(timeout_s)
        self.poll_s = float(poll_s)
        self.stale_ttl_s = float(stale_ttl_s)
        self.release = str(release or "")

        self._fd: Optional[int] = None

    def __enter__(self) -> "SendBundleLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release_lock()

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = _now() + self.timeout_s

        while True:
            # Try atomic create
            try:
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                # 0o644 is fine for local user env
                fd = os.open(str(self.lock_path), flags, 0o644)
                self._fd = int(fd)
                payload = {
                    "pid": os.getpid(),
                    "created_at": _now(),
                    "release": self.release,
                }
                try:
                    os.write(self._fd, (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8", errors="replace"))
                except Exception:
                    pass
                return
            except FileExistsError:
                # Check stale lock
                info = self.peek()
                if info.created_at is not None:
                    age = _now() - float(info.created_at)
                else:
                    age = None

                # stale if too old OR pid dead
                stale = False
                if age is not None and age > self.stale_ttl_s:
                    stale = True
                if info.pid is not None and not _pid_alive(info.pid):
                    stale = True

                if stale:
                    try:
                        self.lock_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    # loop and retry immediately
                    continue

                if _now() >= deadline:
                    raise TimeoutError(
                        f"SendBundleLock timeout after {self.timeout_s:.1f}s: {self.lock_path} (owner pid={info.pid}, age={age})"
                    )

                time.sleep(max(0.05, self.poll_s))
                continue
            except Exception:
                # other unexpected errors
                if _now() >= deadline:
                    raise
                time.sleep(max(0.05, self.poll_s))

    def release_lock(self) -> None:
        try:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except Exception:
                    pass
        finally:
            self._fd = None
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass

    def peek(self) -> LockInfo:
        if not self.lock_path.exists():
            return LockInfo()
        j = _read_json(self.lock_path)
        return LockInfo(
            pid=(j.get("pid") if isinstance(j, dict) else None),
            created_at=(j.get("created_at") if isinstance(j, dict) else None),
            release=(j.get("release") if isinstance(j, dict) else None),
            note=(j.get("note") if isinstance(j, dict) else None),
        )
