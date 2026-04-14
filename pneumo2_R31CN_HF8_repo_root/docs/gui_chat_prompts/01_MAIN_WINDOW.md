# Chat Prompt: Главное Окно Приложения

## Контекст

Мы мигрируем проект в классическое Windows GUI-приложение. WEB больше не целевая платформа развития. Это окно должно стать главным desktop-shell приложения.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Для shell baseline command surface: `menu bar + toolbar + dockable/floating/auto-hide panes + command search + status/progress strip`.
- Левая hierarchy/navigation pane допустима только для реальной структуры разделов и workflow, правая pane должна оставаться context-sensitive и пригодной для inspector/details сценариев.
- `Ribbon` не использовать как базовый шаблон shell. Он допустим только как отдельно обоснованное исключение для конкретного workspace.

## Цель

Развивать главное классическое Windows GUI-приложение как основной вход в систему. Нужен понятный shell с верхним меню, toolbar, home screen, рабочей областью со встроенными окнами и единым пользовательским маршрутом без WEB.

## Можно менять

- [main_window.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/main_window.py)
- [workspace.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/workspace.py)
- [menu_builder.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/menu_builder.py)
- [toolbar.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/toolbar.py)
- [home_view.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/home_view.py)
- [navigation.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/navigation.py)
- [lifecycle.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/lifecycle.py)
- [desktop_main_shell.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell.py)
- [test_desktop_main_shell_contract.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/tests/test_desktop_main_shell_contract.py)

## Можно читать как источник поведения

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- [page_registry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/page_registry.py)

## Нельзя менять

- feature-логику отдельных окон
- [qt_compare_viewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py)
- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/app.py)
- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/app.py)
- WEB pages

## Правила

- Не превращай `main_window.py` в новый монолит.
- Выноси новые seams в отдельные shell-модули.
- Shell должен быть центром приложения, а не свалкой feature-кода.
- Сохраняй классический desktop UX под Windows.
- Если нужно подключить новое окно, меняй adapter/spec/catalog, а не тащи его логику в shell.
- Не прячь core-команды за web-style navigation, hamburger или нестабильные contextual-only паттерны.
- Поддерживай явные scrollbars, resize affordances, keyboard-first переходы по major regions и `command search`.

## Готовый промт

```text
Работай только в lane "Главное Окно Приложения".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: проект уходит из WEB в desktop-first архитектуру. Это окно должно стать главным Windows-приложением с классическим многооконным интерфейсом.

Цель: развивать shell с верхним меню, toolbar, home screen, рабочей областью со встроенными окнами, навигацией, lifecycle hosted tabs и понятным пользовательским маршрутом без WEB.

Можно менять только:
- pneumo_solver_ui/desktop_shell/main_window.py
- pneumo_solver_ui/desktop_shell/workspace.py
- pneumo_solver_ui/desktop_shell/menu_builder.py
- pneumo_solver_ui/desktop_shell/toolbar.py
- pneumo_solver_ui/desktop_shell/home_view.py
- pneumo_solver_ui/desktop_shell/navigation.py
- pneumo_solver_ui/desktop_shell/lifecycle.py
- pneumo_solver_ui/tools/desktop_main_shell.py
- tests/test_desktop_main_shell_contract.py

Можно читать как источник поведения:
- pneumo_solver_ui/pneumo_ui_app.py
- pneumo_solver_ui/page_registry.py

Нельзя менять:
- feature-логику отдельных окон
- qt_compare_viewer.py
- desktop_animator/app.py
- desktop_mnemo/app.py
- WEB pages

Правила:
- не превращай main_window.py в новый монолит
- выноси новые seams в отдельные shell-модули
- shell должен быть центром приложения, а не свалкой feature-кода
- сохраняй классический desktop UX под Windows
- держи baseline command surface: menu bar + toolbar + dockable panes + command search + status/progress strip
- не используй ribbon как shell-default без отдельного обоснования

Сделай следующий логичный шаг по shell core, реализуй его до конца и прогони shell-targeted tests.
```
