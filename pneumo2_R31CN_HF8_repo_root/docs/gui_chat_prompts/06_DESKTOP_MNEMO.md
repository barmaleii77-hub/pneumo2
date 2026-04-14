# Chat Prompt: Desktop Mnemo

## Контекст

Desktop Mnemo должен стать основным GUI схемы и мнемосхемы. WEB mnemo/scheme surfaces нужны только как источник текущего поведения.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Specialized mnemo window может отходить от полного CAD-layout, но обязана сохранять command discipline, keyboard-first, accessibility, High-DPI и performance policy.
- `Ribbon` не использовать как default. Core-команды должны быть discoverable через menu, toolbar, panes или search.

## Цель

Развивать Desktop Mnemo как основное окно схемы и мнемосхемы. Нужно постепенно перенести туда WEB-side mnemo/scheme functionality.

## Можно менять

- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/app.py)
- связанные `desktop_mnemo/*`
- mnemo-specific tests

## Можно читать как источник поведения

- [15_PneumoScheme_Mnemo.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/15_PneumoScheme_Mnemo.py)
- [scheme_integrity.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scheme_integrity.py)
- `ui_svg_*` helpers
- [validation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/validation_cockpit_web.py)

## Нельзя менять

- desktop shell
- desktop input editor
- compare viewer
- desktop animator
- WEB pages

## Правила

- Не переносить mnemo logic в shell.
- Не дублировать animator и compare viewer.
- Удерживать отдельное специализированное окно.

## Готовый промт

```text
Работай только в lane "Desktop Mnemo".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: Desktop Mnemo должен стать основным GUI схемы и мнемосхемы. WEB mnemo/scheme surfaces используются только как источник поведения.

Цель: развивать Desktop Mnemo как основное окно схемы и мнемосхемы. Нужно постепенно перенести туда WEB-side mnemo/scheme functionality.

Можно менять только:
- pneumo_solver_ui/desktop_mnemo/*
- mnemo-specific tests

Можно читать как источник поведения:
- pneumo_solver_ui/pages/15_PneumoScheme_Mnemo.py
- pneumo_solver_ui/scheme_integrity.py
- pneumo_solver_ui/ui_svg_* helpers
- pneumo_solver_ui/validation_cockpit_web.py

Нельзя менять:
- desktop_shell/*
- desktop_input_editor.py
- qt_compare_viewer.py
- desktop_animator
- WEB pages

Правила:
- не переносить mnemo logic в shell
- не дублировать animator и compare viewer
- удерживать отдельное специализированное окно

Сделай следующий локальный шаг по Desktop Mnemo и проверь только mnemo-relevant tests.
```
