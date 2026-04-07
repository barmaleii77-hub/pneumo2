# Release Notes (Обобщение)

## Matematika releases

- **Matematika55**: см. `docs/00_ReleaseNotes_Matematika55.md` (energy-consistent smooth контакты, preflight check, параметры сглаживания в UI)
- **Matematika54**: см. `docs/00_ReleaseNotes_Matematika54.md` (исправление pen_dot, демпфирование отбойников, road_func_dot, мех‑энерго‑аудит для smooth)
- **Matematika53**: см. `docs/00_ReleaseNotes_Matematika53.md` (энерго‑аудит механики, road_func_dot, ISO6358, preflight‑gate)



- **R43**: см. `docs/RELEASE_NOTES_R43.md` (производительность/стабильность анимации: троттлинг localStorage и защитный троттлинг FPS fallback; явное разделение "FPS (браузер)" vs "серверная синхронизация")
- **R42**: см. `docs/RELEASE_NOTES_R42.md` (фикс: анимация/fallback, playhead, контекст v2, патчи)
## R41 (2026-01-24)
- Baseline cache теперь пишется **атомарно** (tmp→replace) + добавлено **автовосстановление** последнего baseline после refresh окна (чтобы не пересчитывать каждый раз).
- Матмодель: добавлены P0-каналы наблюдаемости (рама по углам z/v/a, скорости/ускорения рамы и углов, скорости/ускорения колёс, относительные перемещения колёс, world-frame vx/x/yaw оценка).
- Добавлен свежий контекст `docs/context/PROJECT_CONTEXT_ANALYSIS.md`, требования перегенерированы (RAW+JSON).
- См. `docs/RELEASE_NOTES_R41.md`.

## R40 (2026-01-24)
- Добавлены ваши актуальные требования/бэклог: `docs/context/WISHLIST.md` и `docs/WISHLIST.json` (см. `docs/12_Wishlist.md`).
- Диагностика усилена: static checks (compileall + ruff F821 undefined names) в `tools/run_full_diagnostics.py`.
- В зависимости добавлен `requests` (для HTTP/UI-проверок в диагностике).
- См. `docs/RELEASE_NOTES_R40.md`.


## R39 (2026-01-24)
- Канонический ключ кэша детального/полного прогона: один формат ключа для одиночного прогона, прогона всех тестов и экспортов.
- Анимация: если в логе солвера нет колонок профиля дороги, профиль восстанавливается из входного описания теста (road_func) для честной визуализации.
- Добавлены диффы/патчи в `diffs/`.
- См. `docs/RELEASE_NOTES_R39.md`.

## R38 (2026-01-24)
- Извлечение требований из контекста (txt/mhtml) в `docs/01_RequirementsFromContext.md`.
- UI nonce в dataset_id, чтобы не было коллизий playhead/localStorage после refresh/смены набора данных.
- См. `docs/RELEASE_NOTES_R38.md`.

- R37: `docs/RELEASE_NOTES_R37.md` — fix playhead “multiple masters” jitter (2D follower in sync), fix 3D idle GPU & JS error in resizeCanvas.

- R36: `docs/RELEASE_NOTES_R36.md` — fix animation fallback Play (no instant jump), fix missing sanitize_test_name (detail disk cache), make auto‑detail after baseline truly one‑shot.

- R35: `docs/RELEASE_NOTES_R35.md` — fix playhead events (NameError events, correct time key).

- R34: `docs/RELEASE_NOTES_R34.md` — фиксы детального блока (detail_dt), стабильность state max_points/record_full, self_check(cp1251).
- R33: `docs/RELEASE_NOTES_R33.md` — кэш детального прогона (атомарность + dt/t_end в ключах), playhead/анимация (no-autoplay, loop off по умолчанию).
## R32
- [RELEASE_NOTES_R32.md](RELEASE_NOTES_R32.md) — фиксы `test_pick`/авто‑detail, `platform` в ZIP‑диагностике, логирование view_switch.
Этот файл — индекс по релизам. Подробности по каждому релизу вынесены в отдельные файлы.

## R31 (2026‑01‑23)

- Fix: устранён `NameError: detail_dt is not defined` в детальном прогоне (full‑лог).
- Fix: `call_simulate()` допускает `dt=None` и `t_end=None` (подхватываются из test/params или используются дефолты).
- Fix: авто‑детальный прогон переведён на **триггерный режим** (смена теста / новый baseline), чтобы не стартовать на каждом rerun (Play/вкладки/прочие события).
- Подробнее: `docs/RELEASE_NOTES_R31.md`

## R30 (2026‑01‑23)

- Fix: `t_sec` NameError in detail run
- Fix: repaired try/except/finally for detail run + proper stop + log events
- Perf: auto‑pause playhead on view change to avoid GPU spikes
- Подробнее: `docs/RELEASE_NOTES_R30.md`

## R29 (2026‑01‑23)
- Исправлен детальный прогон (full‑лог): устранена ошибка `call_simulate() missing ... dt/t_end`.
- 2D/3D анимация переведена в *low‑power* режим при паузе (снижение нагрузки на GPU/CPU при открытии вкладки «Анимация»).
- В `meta` full‑лога добавлены `dt` и `t_end`.

См. `docs/RELEASE_NOTES_R29.md`.

## R28 (2026‑01‑23)
- Исправлен краш старта: переменная `use_component_anim` могла быть не определена в ветке анимации.
- Усилен авто‑режим full‑лога: добавлен **guard от бесконечных авто‑перезапусков** при частых `rerun` (autorefresh, server‑sync playhead, fallback‑Play и т.п.).
  - Авто‑расчёт при выборе теста по умолчанию снова **ON**, но повторные авто‑триггеры по одному и тому же ключу подавляются (manual «Пересчитать полный лог» всегда работает).
  - События пишутся в `logs/ui_combined.log`: `detail_autorun_suppressed`, `detail_autorun_already_running`.
- Документация обновлена: что такое rerun‑loop и как его диагностировать/выключить.

См. `docs/00_ReleaseNotes_R28.md`.

## R27 (2026‑01‑23)
- Исправлен краш старта (не был импортирован `Optional`).
- Исправлена причина «вечного авто‑пересчёта» full‑лога: `model.simulate()` мутировал входной словарь параметров → менялся хеш → кэш считался «другим» → запускалось снова.
- Теперь **все вызовы** `simulate()` в UI и worker'ах получают **deepcopy(params/test)**.
- Авто‑full‑log при выборе теста снова **ON по умолчанию** (без бесконечного пересчёта из‑за дрейфа параметров).
- В матмодель добавлен параметр `радиус_колеса_м` (и алиас `диаметр_колеса_м`), влияет на формулу penetration.

См. `docs/00_ReleaseNotes_R27.md`.

## R26
См. `docs/00_ReleaseNotes_R25.md` (раньше файл назывался по R25; R26 делал упор на кэш baseline/детального прогона).

## R25
См. `docs/00_ReleaseNotes_R25.md`.
