# Bundle analysis — R31T SEND (2026-03-24)

Проверен bundle `3009ddbb-30a5-4a46-979e-dd2707a94a9c.zip` от **PneumoApp_v6_80_R176_R31T_2026-03-24**.

## Что подтверждено
- SEND bundle validation: **OK=True**
- Health report: **OK=True**
- Geometry release gate: **PASS**
- Старые регрессии R31O/R31P/R31Q не воспроизвелись: в bundle нет `GLError`, `0xC0000409` и ложного `non-monotonic seq`.

## Auxiliary pane cadence (steady-state окна 5..30 Hz)
- `dock_corner_quick`: median **9.991 Hz**, range 7.761..26.259 Hz, worst `dt_max_ms`=286.133 ms, samples=203.
- `dock_flows`: median **9.464 Hz**, range 7.761..19.49 Hz, worst `dt_max_ms`=286.133 ms, samples=70.
- `dock_heatmap`: median **9.991 Hz**, range 7.761..26.259 Hz, worst `dt_max_ms`=286.133 ms, samples=203.
- `dock_left`: median **10.551 Hz**, range 8.557..26.259 Hz, worst `dt_max_ms`=286.133 ms, samples=203.
- `dock_pressures`: median **9.598 Hz**, range 7.761..19.49 Hz, worst `dt_max_ms`=286.133 ms, samples=106.
- `dock_telemetry`: median **9.991 Hz**, range 7.761..26.259 Hz, worst `dt_max_ms`=286.133 ms, samples=203.
- `dock_timeline`: median **9.991 Hz**, range 7.761..26.259 Hz, worst `dt_max_ms`=286.133 ms, samples=203.
- `dock_trends`: median **9.991 Hz**, range 7.761..26.259 Hz, worst `dt_max_ms`=286.133 ms, samples=203.

Интерпретация: detached auxiliary panes уже не выглядят «мертвыми» по телеметрии, но bundle всё ещё несёт шумные startup/runtime warnings, которые мешают чистой acceptance-картине.

## Оставшиеся предупреждения в bundle
- **DeprecationWarning** — Enum value 'Qt::ApplicationAttribute.AA_EnableHighDpiScaling' is marked as deprecated, please check the documentation for more information.
- **DeprecationWarning** — Enum value 'Qt::ApplicationAttribute.AA_UseHighDpiPixmaps' is marked as deprecated, please check the documentation for more information.
- **DeprecationWarning** — Function: 'QTableWidgetItem.setTextAlignment(int alignment)' is marked as deprecated, please check the documentation for more information.
- **RuntimeWarning** — invalid value encountered in divide
- **startup_external_gl_window** — Animator starts with auxiliary docks attached for stability. After first show side panels are re-tiled against current screen metrics; live 3D GL uses a dedicated top-level window from launch instead of floating QDockWidget mode.
- **derived_road_width_m** — [Animator] road_width_m отсутствует/некорректен в meta_json.geometry → использована SERVICE/DERIVED ширина ленты дороги 1.22 м из track_m + wheel_width_m.

## Вывод
- Нового bundle-driven root-cause по road/FPS здесь не найдено.
- Следующий патч должен бить не в уже закрытые playback/grid fixes, а в чистоту startup/runtime-contract: degenerate placeholder meshdata, exporter-side `road_width_m`, deprecation-noise Qt API.
