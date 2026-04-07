# UnifiedPneumoApp / PneumoApp v6_80

Дата сборки (UTC): 2026-02-15T10:04:49Z

## Главное

v6_80 — технический релиз, который чинит критические импорт-регрессии v6_79 и восстанавливает совместимость distributed tools.

## Исправления

### P0 — старт приложения / crash guard

- Восстановлены функции `get_release`, `get_release_tag`, `get_version`, `format_release_header` в `pneumo_solver_ui/release_info.py`.
  В v6_79 модуль оказался урезан до одного `DEFAULT_RELEASE`, что приводило к `ImportError` в:
  - `pneumo_solver_ui/crash_guard.py`
  - `pneumo_solver_ui/desktop_animator/app.py`
  - `pneumo_solver_ui/tools/selfcheck_suite.py`

### P1 — distributed optimization tools

Восстановлены отсутствующие имена/интерфейсы, которые импортируются скриптами:
- `pneumo_solver_ui/tools/run_dask_distributed_opt.py`
- `pneumo_solver_ui/tools/run_ray_distributed_opt.py`

Добавлено/восстановлено:
- `pneumo_solver_ui/pneumo_dist/eval_core.py`: `Evaluator`, `evaluate_xu_to_row`
- `pneumo_solver_ui/pneumo_dist/mobo_propose.py`: `ProposeOptions`, `propose_next` (с безопасным fallback на random)
- `pneumo_solver_ui/pneumo_dist/hv_tools.py`: `hypervolume_from_min`
- `pneumo_solver_ui/pneumo_dist/trial_hash.py`: `stable_hash_params`, `stable_hash_problem`

### P1 — unified diagnostics

- `pneumo_solver_ui/ui_persistence.py`: добавлен `_extract_persistable_state` (используется unified diagnostics).
- Также добавлены совместимые алиасы `load_ui_settings`/`save_ui_settings`.

## Совместимость

- Истина схемы: без изменений.
- Формат диагностического архива: без изменений.
- UI-навигация: без изменений (скрытых режимов нет; `pages_legacy` используется только как источник для восстановления страниц и дедупликации).

