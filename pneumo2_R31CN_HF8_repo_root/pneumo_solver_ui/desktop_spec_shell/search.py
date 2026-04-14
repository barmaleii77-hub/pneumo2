from __future__ import annotations

from dataclasses import dataclass

from .contracts import DesktopShellCommandSpec, DesktopWorkspaceSpec


def _normalize(text: str) -> str:
    return " ".join(str(text or "").casefold().split())


@dataclass(frozen=True)
class CommandSearchEntry:
    entry_id: str
    command_id: str
    title: str
    subtitle: str
    haystack: str
    workspace_id: str


def build_search_entries(
    workspaces: tuple[DesktopWorkspaceSpec, ...],
    commands: tuple[DesktopShellCommandSpec, ...],
) -> tuple[CommandSearchEntry, ...]:
    workspace_by_id = {workspace.workspace_id: workspace for workspace in workspaces}
    entries: list[CommandSearchEntry] = []
    for command in commands:
        workspace = workspace_by_id[command.workspace_id]
        keywords = [
            command.title,
            command.summary,
            command.route_label,
            workspace.title,
            workspace.summary,
            workspace.group,
            *command.search_aliases,
            *command.web_aliases,
            *workspace.search_aliases,
        ]
        entries.append(
            CommandSearchEntry(
                entry_id=f"command:{command.command_id}",
                command_id=command.command_id,
                title=command.title,
                subtitle=command.route_label,
                haystack=_normalize(" ".join(keywords)),
                workspace_id=command.workspace_id,
            )
        )
    return tuple(entries)


def search_command_palette(
    entries: tuple[CommandSearchEntry, ...],
    query: str,
    *,
    limit: int = 8,
) -> tuple[CommandSearchEntry, ...]:
    normalized = _normalize(query)
    if not normalized:
        return entries[:limit]

    tokens = tuple(token for token in normalized.split(" ") if token)
    scored: list[tuple[int, CommandSearchEntry]] = []
    for entry in entries:
        if not all(token in entry.haystack for token in tokens):
            continue
        score = 0
        haystack = entry.haystack
        title = _normalize(entry.title)
        if title.startswith(normalized):
            score += 60
        if normalized in title:
            score += 25
        if haystack.startswith(normalized):
            score += 20
        score += max(0, 15 - len(entry.title))
        scored.append((score, entry))

    scored.sort(key=lambda item: (-item[0], item[1].title))
    return tuple(entry for _score, entry in scored[:limit])
