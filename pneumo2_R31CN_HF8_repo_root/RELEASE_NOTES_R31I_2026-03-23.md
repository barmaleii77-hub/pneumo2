# RELEASE NOTES — R31I (2026-03-23)

Этот шаг продолжает R31H и закрывает два живых пункта из TODO/WISHLIST:

1. **exporter/meta canonical speed contract for ring**
2. **cockpit/minimap segment overlays beyond mech_car3d**

## Что изменено

### 1) Канонический speed/meta contract для ring → anim_latest

Добавлен новый helper `pneumo_solver_ui/anim_export_meta.py`.

Теперь при экспорте `anim_latest` для ring-сценариев:
- если `scenario_json` в suite/test cfg отсутствует, он **инферится автоматически** рядом с `*_road.csv` / `*_axay.csv`;
- `vx0_м_с` в meta больше не остаётся тихо равным `0.0`, если ring-spec реально стартует с ненулевой скорости;
- для ring-spec в meta добавляются:
  - `ring_v0_kph`
  - `ring_v0_mps`
  - `ring_nominal_speed_min_mps`
  - `ring_nominal_speed_max_mps`
  - `ring_nominal_speed_mean_mps`
  - `ring_speed_profile_source="scenario_json"`

Важно: для ring каноническая начальная скорость берётся **из authored ring-spec**, а не из сломанного/stale suite `vx0_м_с=0`.

### 2) Segment overlays в cockpit/minimap

`animation_cockpit_web.py` теперь передаёт `ring_visual` не только в 3D, но и в:
- `minimap_live`
- `road_profile_live`

#### `minimap_live`
- добавлен цветной segment overlay поверх траектории;
- HUD теперь показывает текущий сегмент.

#### `road_profile_live`
- добавлены цветные фоновые segment bands по оси Δs;
- HUD теперь показывает текущий сегмент.

Это даёт segment highlighting в cockpit без необходимости смотреть только на 3D.

## Что проверено

- `python -m py_compile`:
  - `pneumo_solver_ui/anim_export_meta.py`
  - `pneumo_solver_ui/pneumo_ui_app.py`
  - `pneumo_solver_ui/animation_cockpit_web.py`
- `node --check` на JS, извлечённом из:
  - `components/minimap_live/index.html`
  - `components/road_profile_live/index.html`
- pytest slice:
  - `tests/test_r32_ring_closure_policy_and_ui_labels.py`
  - `tests/test_r32_triage_and_anim_sidecars.py`
  - `tests/test_r33_ring_sine_input_semantics.py`
  - `tests/test_r34_ring_visual_3d_worldfixed.py`
  - `tests/test_r35_anim_export_meta_and_cockpit_overlays.py`

Результат: **17 passed**.

## Что ещё не закрыто полностью

- measured Windows browser Performance trace / acceptance;
- solver-points completeness для полностью честной геометрии подвески;
- исторические уже выгруженные bundle сами по себе не переписываются задним числом.
