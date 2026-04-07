# UnifiedPneumoApp — RELEASE NOTES v6_79

## Цель релиза

Минимальные правки **только для стабильности/совместимости** (без расширения функционала):

- убрать/подавить «тихие» предупреждения Streamlit о `use_container_width` (которые в 2026 уже считаются устаревшими);
- убрать Pandas FutureWarning по `fillna(...).astype(bool)` для колонок с object dtype;
- сохранить весь текущий функционал v6_78 без выноса в legacy.

## Что изменено

### 1) Streamlit: совместимость `use_container_width` ↔ `width`

- Добавлен стартовый вызов `install_st_compat()` в корневом `app.py`.
- Обновлён `pneumo_solver_ui/ui_st_compat.py`:
  - если Streamlit поддерживает `width`, то `use_container_width=True/False` автоматически переводится в `width='stretch'/'content'` (чтобы не ловить WARN);
  - если Streamlit **не** поддерживает `width`, то `width='stretch'/'content'` переводится обратно в `use_container_width=True/False`.

Это **не меняет** логику вычислений, только параметры отрисовки UI.

### 2) Pandas: устранение FutureWarning (dtype downcasting)

В `pneumo_ui_app.py` нормализован dtype для `df['включен']` перед `.astype(bool)`:

- сначала `fillna(True)`
- затем `infer_objects(copy=False)` (или fallback)
- затем `.astype(bool)`

Цель — убрать предупреждения и зафиксировать предсказуемое поведение при будущих изменениях Pandas.

## Что НЕ менялось

- Пневмосхема/истина схемы **не трогалась** (SOURCE OF TRUTH остаётся прежним).
- Никакие страницы не убирались в legacy и не скрывались.
- Solver/модели/оптимизация не расширялись.

## Где смотреть отчёты

- `REPORTS/AUDIT_SILENT_WARNINGS_energy_entropy_v6_78.md` — предыдущий аудит WARN по энергии/энтропии.
- `REPORTS/SELF_CHECK_SILENT_WARNINGS.json` — файл для сигнализации WARN в UI (если self_check/preflight его сгенерировали).

