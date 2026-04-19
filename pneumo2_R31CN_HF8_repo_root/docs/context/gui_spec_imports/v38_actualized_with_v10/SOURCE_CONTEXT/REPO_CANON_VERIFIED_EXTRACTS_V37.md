# REPO_CANON_VERIFIED_EXTRACTS_V37

## PROJECT_SOURCES
- `docs/PROJECT_SOURCES.md` фиксирует порядок: сначала `17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`, затем `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`, затем `foundations/*`, потом imported layers (`v3`, `v13_ring_editor_migration`, `v12_design_recovery`), а imported JSON/DOT/CSV используются как reference artifacts, не как единственный источник правды.

## 17_WINDOWS_DESKTOP_CAD_GUI_CANON
- базовый shell: native Windows desktop engineering software;
- main window: menu bar, toolbar/command strip, command search, left browser/tree, center work surface, right inspector, bottom status/progress;
- dockable / floating / auto-hide panes и сохранение раскладок между сеансами.

## 18_PNEUMOAPP_WINDOWS_GUI_SPEC
- маршрут пользователя должен быть видим: `Исходные данные -> Набор испытаний и сценарии -> Базовый прогон -> Оптимизация -> Анализ -> Анимация -> Диагностика`;
- `Редактор кольца` закреплён как единственный источник сценарной истины;
- parity `web -> desktop` — release-gate;
- графика и анимация обязаны быть honest-by-contract;
- по цилиндрам нельзя растягивать корпус по всей pin-to-pin оси и нельзя выдумывать гланду/шток/поршень.

## 11_TODO
Открытые P0 включают:
- browser/Web UI idle load и perf trace;
- dt-aware playback / FPS в Desktop Animator;
- road surface/contact patch acceptance;
- возврат цилиндров/штоков/поршней только после полного solver/export packaging contract.
