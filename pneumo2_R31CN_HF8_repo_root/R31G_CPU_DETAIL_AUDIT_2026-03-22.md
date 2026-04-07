# R31G audit — 2026-03-22

База: `PneumoApp_v6_80_R176_R31F_SINE_A_SEMANTICS_DETAIL_RECALC_2026-03-22.zip`

## Что локализовано

### 1) Семантика амплитуды
В коде worldroad/sine теперь явно зафиксировано: `A` — полуразмах. Пользовательский ввод помечен как `Амплитуда A (полуразмах), м`, и UI сразу показывает интерпретацию `-A..+A` и `p-p = 2A`.

### 2) baseline -> auto-detail
В `pneumo_ui_app.py` обнаружен реальный разрыв с уже существующим helper-модулем `detail_autorun_policy.py`: entrypoint UI не использовал политику force-fresh-after-baseline и мог молча брать старый detail disk-cache. В R31G entrypoint синхронизирован с helper-модулем:
- armed pending autorun on test change / baseline finish;
- `detail_force_fresh_key` задаётся после свежего baseline;
- disk-cache для текущего key обходится при force-fresh;
- флаг force-fresh очищается после завершения/загрузки.

### 3) post-run CPU culprit
Найден конкретный живой источник CPU-нагрузки после окончания расчётов:
- `pneumo_solver_ui/components/mech_car3d/index.html`
- в базовой версии было: `if (W < 10 || H < 10) { requestAnimationFrame(renderFrame); return; }`
- это означало бесконечный rAF-spin, когда 3D-iframe схлопнут/скрыт/ещё не размечен по размеру.

Это главный smoking gun.

## Вторичные contributors
Также подтверждены постоянные paused/off-screen self-wake loops в follower web-components:
- `components/pneumo_svg_flow/index.html`
- `components/road_profile_live/index.html`
- `components/minimap_live/index.html`
- `components/corner_heatmap_live/index.html`
- `components/mech_anim/index.html`
- `components/mech_anim_quad/index.html`
- `components/playhead_ctrl/index.html`
- `components/playhead_ctrl/index_unified_v1.html`
- `plotly_playhead_html.py`

В базе они держали idle-poll примерно 220–1200 мс и не знали про parent viewport. В R31G добавлены:
- best-effort `window.frameElement` / parent viewport visibility helper;
- `__nextIdleMs(...)` с сильно более редким idle;
- запрет полноскоростного follower-animation off-screen;
- замена unconditional `setInterval(updatePlayhead, POLL_MS)` на adaptive one-shot timer loop.

## Проверки
- `py_compile`: PASS (`pneumo_ui_app.py`, `plotly_playhead_html.py`)
- targeted regression slice: PASS
  - `tests/test_r31g_detail_autorun_fresh_and_cpu_idle.py`
  - `tests/test_r27_ring_sine_phase_amplitude.py`
  - `tests/test_r29_embedded_html_idle_guards.py`
  - `tests/test_r29_ring_profile_no_hidden_closure_ramp.py`
  - `tests/test_r30_ring_sine_segment_local_metrics.py`
  - `tests/test_r30_ring_segment_summary.py`
  - `tests/test_active_generators_solver_points_canon.py`
  - `tests/test_streamlit_width_runtime_sources.py`

Итог targeted slice: `15 passed`.

## Что ещё НЕ закрыто
- Нет browser Performance trace acceptance на реальной Windows-сессии — следовательно, снижение CPU подтверждено по коду и статическим тестам, но не финализировано browser-trace метрикой.
- Parent viewport gating сделан best-effort; если конкретное окружение не даёт доступ к `window.frameElement`, нужен отдельный visibility-hint channel.
