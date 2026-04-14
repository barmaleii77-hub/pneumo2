from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Mapping

from pneumo_solver_ui.desktop_shell.contracts import DesktopShellToolSpec
from pneumo_solver_ui.desktop_shell.external_launch import (
    build_shell_context_env,
    spawn_module,
)


def _default_context_payload(
    spec: DesktopShellToolSpec,
    context_payload: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "selected_tool_key": spec.key,
        "workflow_stage": spec.workflow_stage or "",
        "active_optimization_mode": "",
        "selected_run_dir": "",
        "selected_artifact": "",
        "selected_scenario": "",
        "source_of_truth_role": spec.effective_source_of_truth_role,
        "workspace_role": spec.effective_workspace_role,
        "runtime_kind": spec.effective_runtime_kind,
        "migration_status": spec.effective_migration_status,
    }
    if context_payload:
        payload.update({str(key): value for key, value in context_payload.items()})
    allowed_keys = set(spec.effective_context_handoff_keys)
    allowed_keys.update(
        {
            "workspace_role",
            "runtime_kind",
            "migration_status",
        }
    )
    return {key: value for key, value in payload.items() if key in allowed_keys}


@dataclass(slots=True)
class ManagedExternalWindowSession:
    spec: DesktopShellToolSpec
    process: subprocess.Popen[object]
    context_payload: dict[str, object] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)

    @property
    def pid(self) -> int | None:
        try:
            return int(self.process.pid)
        except Exception:
            return None

    @property
    def is_running(self) -> bool:
        return self.process.poll() is None

    @property
    def runtime_label(self) -> str:
        kind = self.spec.effective_runtime_kind
        status = self.spec.effective_migration_status
        if kind == "tk" and status == "managed_external":
            return "Tk -> управляемое внешнее окно"
        if kind == "qt":
            return "Qt"
        return "Процесс"

    def status_label(self) -> str:
        if self.is_running:
            return "Открыто"
        code = self.process.poll()
        if code is None:
            return "Открыто"
        return f"Завершено ({code})"


class DesktopShellCoexistenceManager:
    """Launcher-level coexistence for the transition from Tk workspaces to Qt shell."""

    def __init__(self) -> None:
        self._sessions: dict[str, ManagedExternalWindowSession] = {}

    def open_tool(
        self,
        spec: DesktopShellToolSpec,
        *,
        context_payload: Mapping[str, object] | None = None,
    ) -> ManagedExternalWindowSession:
        existing = self._sessions.get(spec.key)
        if existing and existing.is_running:
            return existing
        if not spec.standalone_module:
            raise RuntimeError(f"Shell spec '{spec.key}' does not expose standalone_module")
        payload = _default_context_payload(spec, context_payload)
        process = spawn_module(
            spec.standalone_module,
            env_updates=build_shell_context_env(payload),
        )
        session = ManagedExternalWindowSession(
            spec=spec,
            process=process,
            context_payload=payload,
        )
        self._sessions[spec.key] = session
        return session

    def session_for(self, key: str) -> ManagedExternalWindowSession | None:
        return self._sessions.get(key)

    def stop_tool(self, key: str) -> bool:
        session = self._sessions.get(key)
        if not session or not session.is_running:
            return False
        try:
            session.process.terminate()
        except Exception:
            return False
        return True

    def stop_all(self) -> int:
        stopped = 0
        for key in tuple(self._sessions):
            if self.stop_tool(key):
                stopped += 1
        return stopped

    def poll(self) -> tuple[ManagedExternalWindowSession, ...]:
        finished: list[ManagedExternalWindowSession] = []
        for session in self._sessions.values():
            if session.process.poll() is not None:
                finished.append(session)
        return tuple(finished)

    def running_sessions(self) -> tuple[ManagedExternalWindowSession, ...]:
        sessions = [session for session in self._sessions.values() if session.is_running]
        return tuple(sorted(sessions, key=lambda item: item.spec.title.lower()))

    def all_sessions(self) -> tuple[ManagedExternalWindowSession, ...]:
        return tuple(sorted(self._sessions.values(), key=lambda item: item.spec.title.lower()))

    def has_running_sessions(self) -> bool:
        return any(session.is_running for session in self._sessions.values())
