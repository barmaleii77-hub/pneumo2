# Chat Prompt: Desktop Animator

## Контекст

Desktop Animator должен стать основным окном анимации и инженерного просмотра результатов. WEB animation cockpit используется только как источник поведения.

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
