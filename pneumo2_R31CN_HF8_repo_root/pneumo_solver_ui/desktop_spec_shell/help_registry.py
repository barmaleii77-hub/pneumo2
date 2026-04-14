from __future__ import annotations

from .catalogs import get_help_topic, get_tooltip
from .contracts import DesktopHelpTopicSpec
from .registry import build_workspace_map


def _payload_text(payload: dict[str, object], keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        value = " ".join(str(payload.get(key) or "").split()).strip()
        if value:
            return value
    return fallback


def build_help_registry() -> dict[str, DesktopHelpTopicSpec]:
    registry: dict[str, DesktopHelpTopicSpec] = {}
    for workspace in build_workspace_map().values():
        catalog_help = get_help_topic(workspace.help_id or workspace.workspace_id)
        tooltip = get_tooltip(workspace.tooltip_id)
        payload = catalog_help.payload if catalog_help is not None else {}
        title = (catalog_help.title or workspace.title) if catalog_help is not None else workspace.title
        summary = ". ".join(
            part
            for part in (
                _payload_text(payload, ("что_это", "Р§С‚Рѕ_СЌС‚Рѕ"), workspace.summary),
                _payload_text(payload, ("зачем_нужно", "Р·Р°С‡РµРј_РЅСѓР¶РЅРѕ"), workspace.details or workspace.summary),
            )
            if part
        )
        registry[workspace.workspace_id] = DesktopHelpTopicSpec(
            topic_id=workspace.workspace_id,
            title=title,
            summary=summary,
            source_of_truth=workspace.source_of_truth,
            units_policy=_payload_text(
                payload,
                (
                    "единицы_измерения_если_применимо",
                    "РµРґРёРЅРёС†С‹_РёР·РјРµСЂРµРЅРёСЏ_РµСЃР»Рё_РїСЂРёРјРµРЅРёРјРѕ",
                ),
                workspace.units_policy
                or "Единицы и смысл должны быть видимы рядом с действием пользователя.",
            ),
            next_step=workspace.next_step,
            hard_gate=_payload_text(
                payload,
                ("ограничения_и_валидация", "РѕРіСЂР°РЅРёС‡РµРЅРёСЏ_Рё_РІР°Р»РёРґР°С†РёСЏ"),
                workspace.hard_gate,
            ),
            graphics_policy=workspace.graphics_policy
            or "Derived view обязан показывать provenance и уровень достоверности.",
            tooltip_text=tooltip.text if tooltip is not None else "",
            why_it_matters=_payload_text(
                payload,
                ("как_влияет_на_поток", "РєР°Рє_РІР»РёСЏРµС‚_РЅР°_РїРѕС‚РѕРє"),
                workspace.details or workspace.summary,
            ),
            result_location=_payload_text(
                payload,
                (
                    "где_пользователь_видит_результат",
                    "РіРґРµ_РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ_РІРёРґРёС‚_СЂРµР·СѓР»СЊС‚Р°С‚",
                ),
                workspace.next_step,
            ),
        )
    return registry
