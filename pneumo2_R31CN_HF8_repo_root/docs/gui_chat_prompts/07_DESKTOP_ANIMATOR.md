# Chat Prompt: Desktop Animator

## Контекст

Desktop Animator должен стать основным окном анимации и инженерного просмотра результатов. WEB animation cockpit используется только как источник поведения.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Для animator-поверхностей держи viewport-first layout, а overlays, timelines, properties и diagnostics выноси в управляемые panes.
- Если есть 3D viewport, orientation widget уровня `ViewCube` обязателен. `Ribbon` не использовать как default.
- Соблюдай honest visualization contract: `truth complete / truth partial / truth absent`; не рисуй fake geometry, pin-to-pin cylinder body или декоративный fallback без warning.

## Цель

Развивать Desktop Animator как основное окно анимации и инженерного просмотра. Нужно перенести туда animation cockpit, ring/cockpit overlays и другие related UX, которые ещё остались в WEB.

## Можно менять

- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/app.py)
- связанные `desktop_animator/*`
- animator-specific tests

## Можно читать как источник поведения

- [animation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/animation_cockpit_web.py)
- [11_AnimationCockpit_Web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/11_AnimationCockpit_Web.py)
- [anim_export_meta.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/anim_export_meta.py)
- [ring_visuals.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ring_visuals.py)
- `ui_animation_results_*`

## Нельзя менять

- desktop shell
- compare viewer
- desktop mnemo
- WEB pages

## Правила

- Не переноси animator logic в shell.
- Treat animator as specialized standalone app.
- Работай через маленькие panels/runtime helpers, а не через один giant file.

## Готовый промт

```text
Работай только в lane "Desktop Animator".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: Desktop Animator должен стать основным окном анимации и инженерного просмотра результатов. WEB animation cockpit используется только как источник поведения.

Цель: развивать Desktop Animator как основное окно анимации и инженерного просмотра. Нужно перенести туда animation cockpit, ring/cockpit overlays и другие related UX, которые ещё остались в WEB.

Можно менять только:
- pneumo_solver_ui/desktop_animator/*
- animator-specific tests

Можно читать как источник поведения:
- pneumo_solver_ui/animation_cockpit_web.py
- pneumo_solver_ui/pages/11_AnimationCockpit_Web.py
- pneumo_solver_ui/anim_export_meta.py
- pneumo_solver_ui/ring_visuals.py
- pneumo_solver_ui/ui_animation_results_*

Нельзя менять:
- desktop_shell/*
- qt_compare_viewer.py
- desktop_mnemo/*
- WEB pages

Правила:
- не переноси animator logic в shell
- treat animator as specialized standalone app
- работай через маленькие panels/runtime helpers, а не через один giant file

Сделай следующий шаг по animator и проверь только animator-relevant tests.
```
