# RELEASE NOTES — R31O (2026-03-23)

Этот шаг собирает небольшой, но честный cumulative patch поверх `R31N`.

## Что исправлено

### 1) Ring: raw authored profile больше не подменяется seam-closure коррекцией

Файл: `pneumo_solver_ui/scenario_ring.py`

Что было плохо:
- при `closure_policy=closed_c1_periodic` локальная seam-коррекция переписывала сами `zL_m/zR_m`;
- из-за этого preview/summary могли показывать ложное увеличение амплитуды даже для детерминированного SINE;
- для уже периодического SINE с ненулевой фазой срабатывала ложная slope-mismatch диагностика из-за грубого edge derivative.

Что теперь сделано:
- raw authored треки сохраняются как truth для preview/summary в `zL_m/zR_m`;
- периодически замкнутая версия строится отдельно как `zL_closed_m/zR_closed_m` и используется для spline/export;
- оценка seam slope переведена на более аккуратный edge estimate, а для практически уже замкнутого сигнала добавлен no-op fast path без лишней коррекции.

Практический эффект:
- периодический SINE с фазой сохраняет запрошенную амплитуду;
- непериодический SINE не «лечится» скрытой подменой raw preview;
- export всё ещё может использовать smooth periodic spline там, где это нужно для кольца.

### 2) Active Streamlit runtime: убран оставшийся deprecated `use_container_width`

Файл: `pneumo_solver_ui/ui_scenario_ring.py`

Что сделано:
- debug-график кольца переведён с `use_container_width=True` на `width="stretch"`.

Практический эффект:
- активный runtime больше не держит этот deprecated call в ring UI;
- меньше warning-шумов на новых версиях Streamlit.

## Что обновлено в проектной документации

- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `TODO_WISHLIST_R31O_ADDENDUM_2026-03-23.md`

Там зафиксировано, что этим шагом закрыты:
- raw-vs-closed ring preview truth;
- last active Streamlit width deprecation in ring UI.

И отдельно подтверждено, что всё ещё открыто:
- measured Windows browser perf acceptance;
- solver-points completeness / packaging contract for fully honest mechanics;
- release-gate acceptance на реальном Windows viewport.

## Что проверено

- `python -m py_compile`:
  - `pneumo_solver_ui/scenario_ring.py`
  - `pneumo_solver_ui/ui_scenario_ring.py`
  - `pneumo_solver_ui/release_info.py`
- pytest targeted slice:
  - `tests/test_r27_ring_sine_phase_amplitude.py`
  - `tests/test_r29_ring_profile_no_hidden_closure_ramp.py`
  - `tests/test_r30_ring_sine_segment_local_metrics.py`
  - `tests/test_r32_ring_closure_policy_and_ui_labels.py`
  - `tests/test_r33_ring_sine_input_semantics.py`
  - `tests/test_streamlit_width_runtime_sources.py`
  - `tests/test_streamlit_use_container_width_compat_contract.py`
  - `tests/test_release_info_default_release_sync.py`

## Release status

Это **не** заявление, что весь исторический wishlist закрыт.
Это аккуратный patch-release, который:
- убирает воспроизводимый regression в ring amplitude/preview truth;
- дочищает активный Streamlit runtime;
- обновляет TODO/WISHLIST и release metadata под новый артефакт.
