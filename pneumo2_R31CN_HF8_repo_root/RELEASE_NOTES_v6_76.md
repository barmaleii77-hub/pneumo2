# RELEASE NOTES — v6_77

Дата сборки (UTC): 2026-02-14

## Фокус релиза
Bugfix-only. Никакого расширения функционала — только восстановление работоспособности после мерджей без потери функций.

## P0 исправления (диагностика / краш-гард)

### 1) Восстановлен единый API для сборки диагностического ZIP
**Проблема:** UI (sidebar) и crash-guard передавали `tag=...`, но `make_send_bundle_bytes()` / `make_send_bundle()` в некоторых ветках не принимали этот аргумент → падение кнопки диагностики и отсутствие автосейва при краше.

**Исправление:**
- `pneumo_solver_ui.send_bundle.make_send_bundle(..., tag=...)` — теперь принимает `tag` (kw-only).
- `pneumo_solver_ui.send_bundle.make_send_bundle_bytes(..., tag=...)` — теперь принимает `tag` (kw-only).

### 2) Crash-guard снова способен автосохранять диагностику
**Проблема:** crash-guard импортировал low-level функцию с нестабильной сигнатурой.

**Исправление:**
- `pneumo_solver_ui.crash_guard` теперь импортирует `make_send_bundle` из стабильного wrapper API `pneumo_solver_ui.send_bundle`.
- Исправлен runtime-баг в crash-guard: ссылка на несуществующую `_get_project_root()` (заменено на `_repo_root()`).

## Проверки
- `python -m compileall` — OK
- `python pneumo_solver_ui/tools/preflight_gate.py` — OK (fingerprint OK; предупреждения остаются предупреждениями)
- `python pneumo_solver_ui/tools/mech_energy_smoke_check.py` — OK
- Self-test: `make_send_bundle_bytes(tag=...)` возвращает `(bytes, filename)` — OK

