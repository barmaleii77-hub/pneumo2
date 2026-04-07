# Unified data contract (UI ⇄ Generator ⇄ Desktop Animator)

Дата: 2026‑02‑18

Цель этого документа — зафиксировать **единый формат ключей и метаданных** для передачи данных между:

- Web UI (Streamlit)
- GUI/генератор тестов (внутри UI)
- Desktop Animator (Qt)
- run_artifacts (диск‑кэш и «последний прогон/оптимизация»)

Чтобы **данные не терялись**, любые артефакты прогонов должны быть либо:

1) **самодостаточны** (sidecar‑файлы лежат рядом с `.npz` и упомянуты в meta), либо
2) содержать **абсолютные пути** (но это хуже для переносимости).

В релизе R150 реализован вариант (1) для `anim_latest`.

---

## 1) Контейнер лога: `.npz`

Файл: `pneumo_solver_ui/npz_bundle.py`

NPZ содержит:

- `main_cols`, `main_values`
- `p_cols`, `p_values` *(опционально)*
- `q_cols`, `q_values` *(опционально)*
- `open_cols`, `open_values` *(опционально)*
- `meta_json` *(строка JSON)*

Это формат, который читает Desktop Animator через `pneumo_solver_ui/desktop_animator/data_bundle.py`.

---

## 2) Meta JSON: обязательные и канонические ключи

### 2.1 Версионирование

- `schema_version`: строка версии (сейчас `pneumo_npz_meta_v1`)

### 2.2 Sidecar‑файлы сценария (канон)

Эти ключи используются везде одинаково (UI/генератор/аниматор).

- `road_csv` — путь к CSV профиля дороги
- `axay_csv` — путь к CSV профиля движения/манёвра
- `scenario_json` — путь к JSON‑спецификации сценария (например ring_scenario)

### 2.3 Никаких алиасов

**Алиасы/псевдонимы запрещены.**

Если встречаются legacy-ключи (например `road_profile_path`) — это считается нарушением контракта.
Допускается только **явная миграция** (с warning в лог и последующим сохранением *только* канонических ключей).

---

## 3) Экспорт для Desktop Animator: `anim_latest`

Файлы в `WORKSPACE_DIR/exports/`:

- `anim_latest.npz`
- `anim_latest.json` (указатель)

Указатель содержит:

- `schema_version: anim_latest_pointer_v1`
- `npz_path: <полный путь к anim_latest.npz>`

### 3.1 Sidecar‑копирование

Если в `meta` при экспорте присутствуют `road_csv/axay_csv/scenario_json`, то при `export_anim_latest_bundle()`:

- эти файлы копируются в `exports/` рядом с NPZ под стабильными именами:
  - `anim_latest_road_csv.csv`
  - `anim_latest_axay_csv.csv`
  - `anim_latest_scenario_json.json`
- а `meta_json` внутри NPZ переписывается на **относительные** пути (только имена файлов)

Так Animator может загрузить всё «без потерь», просто открыв `anim_latest.json`.

---

## 4) Что должен отдавать генератор тестов

Генератор (например ring) должен сохранять bundle и возвращать/записывать пути в тест‑спеку:

- `road_csv`
- `axay_csv`
- `scenario_json`

А UI при запуске теста должен прокидывать эти значения в `meta` (см. изменения в `pneumo_ui_app.py`).

---

## 5) Рекомендации

- Всегда добавляйте `scenario_kind` (например `ring_v1`) и `test_type` в meta — это сильно облегчает отладку.
- Не храните «формат» только в названиях колонок — дублируйте ключевые параметры в `meta_json`.

---

## 6) LAW: Animator показывает ровно то, что экспортировала модель

**Закон проекта:** любая анимация (web mech_anim и Desktop Animator) обязана использовать
**сигналы расчётной модели/исходных данных/результатов**.

Рендер **не имеет права** придумывать недостающие каналы и «чинить» смысл сигналов
через скрытые baseline/offset/«нулевую позу».

### 6.1 Практические правила

- Если модель экспортирует координаты в относительном базисе (`*_rel0`) — Animator может **показать именно этот базис**,
  но это должно быть **явно** (индикатор базиса + запись в лог).
- Для **абсолютной геометрии** (клиренс/абсолютная высота кузова/абсолютное положение колёс относительно земли)
  модель обязана экспортировать **абсолютные** координаты (колонки **без** суффикса `_rel0`).
- Колонки `*_rel0` допускаются как удобство для анализа/графиков, но **никогда не подставляются автоматически**.
- Если UI/аниматору нужен rel0, он делает это **явно как service/derived**:
  - вычисляет из абсолютных (например `x - x[0]`), или
  - обращается к `*_rel0` по имени.

### 6.2 Минимальные обязательные сигналы геометрии (df_main)

Эти колонки должны присутствовать в `df_main` / экспортируемом NPZ, чтобы анимация работала корректно:

- `t_с`
- Дорога в точках контакта (абсолют): `дорога_ЛП_м`, `дорога_ПП_м`, `дорога_ЛЗ_м`, `дорога_ПЗ_м`
- Высоты кузова/рамы (абсолют): `рама_ЛП_z_м`, `рама_ПП_z_м`, `рама_ЛЗ_z_м`, `рама_ПЗ_z_м`
- Высоты колёс (абсолют): `перемещение_колеса_ЛП_м`, `перемещение_колеса_ПП_м`, `перемещение_колеса_ЛЗ_м`, `перемещение_колеса_ПЗ_м`

Если bundle содержит только `*_rel0` без соответствующих абсолютных колонок — это нарушение контракта.

## 7) Solver-point contract для visual bundle

Для новых `anim_latest` bundle визуальный тракт больше не имеет права дорисовывать точки подвески.
Производящая модель обязана экспортировать **канонические triplets** для каждого угла:

- `arm_pivot_{угол}_{x|y|z}_м`
- `arm_joint_{угол}_{x|y|z}_м`
- `cyl1_top_{угол}_{x|y|z}_м`
- `cyl1_bot_{угол}_{x|y|z}_м`
- `cyl2_top_{угол}_{x|y|z}_м`
- `cyl2_bot_{угол}_{x|y|z}_м`
- `wheel_center_{угол}_{x|y|z}_м`
- `road_contact_{угол}_{x|y|z}_м`

Где `угол ∈ {ЛП, ПП, ЛЗ, ПЗ}`.

### 7.1 Жёсткое правило

- Частичный triplet (`x/y` без `z` и т.п.) — **ошибка контракта**.
- Legacy/alias имена не допускаются.
- `export_anim_latest_bundle()` обязан блокировать экспорт, если solver-point contract не выполнен.

### 7.2 Источник координат

Координаты этих точек должны вычисляться **из реальной геометрии модели**, уже разрешённой внутри solver/generator path.
Нельзя:

- подставлять плоскую дорогу;
- придумывать длины рычагов/смещения;
- восстанавливать точки в visual consumer через скрытые baseline/fallback.

Если модель не умеет честно отдать solver points, такой bundle не должен экспортироваться как `anim_latest`.


---

## 7) Unified visual contract audit (R176 cumulative line)

Файлы:
- `pneumo_solver_ui/visual_contract.py`
- `pneumo_solver_ui/compare_ui.py`
- `pneumo_solver_ui/validation_cockpit_web.py`
- `pneumo_solver_ui/animation_cockpit_web.py`
- `pneumo_solver_ui/desktop_animator/data_bundle.py`
- `pneumo_solver_ui/desktop_animator/selfcheck_cli.py`

### 7.1 Один helper для всех visual consumers

С этого шага web/desktop/CLI обязаны брать visual-contract статус из одного места:

- `collect_visual_contract_status(...)`

Он проверяет единообразно:

- nested `meta_json.geometry`
- каноническую дорогу из `df_main` **или** canonical `road_csv` sidecar
- canonical solver-point triplets
- overlay/status сообщения `NO ROAD DATA` / `NO SOLVER POINTS`

### 7.2 `road_csv` — канонический источник дороги для visual path

Если в bundle дорога вынесена в sidecar:

- `meta_json["road_csv"]` считается канонической ссылкой
- web consumers и Desktop Animator обязаны читать её одинаково
- отсутствие дорожных колонок в `df_main` **не является проблемой**, если валиден `road_csv`

Требования к `road_csv`:

- колонка `t`
- колонки `z0`, `z1`, `z2`, `z3` для `ЛП`, `ПП`, `ЛЗ`, `ПЗ`
- допустимо fallback-чтение первых четырёх `z*` колонок, но это логируется как warning

Если sidecar есть, но он битый/пропал/неразрешим — это не чинится тихо, а поднимается как contract issue.

### 7.3 Что кладётся в загруженный bundle

`compare_ui.load_npz_bundle(...)` и `desktop_animator.data_bundle.load_npz(...)` теперь добавляют:

- `meta["_visual_contract"]` — сводный audit-status без массивов
- `bundle["visual_contract"]` — тот же статус для web consumers
- `bundle["road_sidecar_wheels"]` — реальные дорожные трассы из `road_csv` (если sidecar валиден)
- `meta["_visual_cache_dependencies"]` — fingerprint зависимостей для UI-кэша
- `bundle["cache_deps"]` — тот же fingerprint для Streamlit/web consumers

Это нужно, чтобы Validation Cockpit, Animation Cockpit и Desktop Animator не расходились
по вопросу "есть дорога / нет дороги" и не строили разные предупреждения на одном и том же bundle.

### 7.4 Cache-buster для visual sidecar

Поскольку visual consumers зависят не только от самого `.npz`, но и от внешнего `road_csv`,
кэш по одному только пути NPZ считается **некорректным**.

С этого шага:

- `collect_visual_cache_dependencies(...)` собирает fingerprint для:
  - самого `.npz`
  - canonical `road_csv` sidecar (если он объявлен в `meta_json`)
- Streamlit `cache_data` для загрузки bundle обязан принимать этот fingerprint отдельным аргументом
- тяжёлые UI-кэши (`ui_heavy_cache`) обязаны строить ключи по `bundle["cache_deps"]`, а не только по `file_fingerprint(npz)`

Иначе ситуация «NPZ тот же, но рядом заменили `road_csv`» приводит к тихо устаревшей дороге в web UI, что недопустимо.


### 7.5 Desktop Animator follow-mode тоже обязан учитывать sidecar fingerprint

`anim_latest.json` сам по себе не гарантирует, что достаточно смотреть только на mtime pointer-файла
или только на имя `anim_latest.npz`.

Если `anim_latest.npz` перезаписали по тому же пути **или** рядом заменили canonical `road_csv`,
follow-mode обязан перезагрузить bundle.

Поэтому:

- Desktop Animator follow-mode обязан строить token через `collect_visual_cache_dependencies(...)`
  + `visual_cache_dependencies_token(...)`
- решение "перезагружать / не перезагружать" нельзя принимать только по `pointer.mtime`
  или только по строке пути до `.npz`
- `desktop_animator.data_bundle.load_npz(...)` обязан сохранять:
  - `meta["_visual_cache_dependencies"]`
  - `meta["_visual_cache_token"]`
- `anim_latest.json` и `anim_latest_trace.json` обязаны публиковать тот же `visual_cache_token`
  и payload `visual_cache_dependencies`, чтобы причина reload была видна в pointer/export diagnostics,
  а не только внутри follow-watcher
- canonical `anim_latest` diagnostics обязаны дополнительно публиковать признаки пригодности pointer/npz:
  - `anim_latest_usable`
  - `anim_latest_pointer_json_exists`
  - `anim_latest_npz_exists`
  - `anim_latest_pointer_json_in_workspace`
  - `anim_latest_npz_in_workspace`
  - `anim_latest_issues`
- send-bundle validation / health / dashboard обязаны отдельно помечать, когда pointer/token есть,
  но `anim_latest` **не воспроизводим из самого bundle** (`usable_from_bundle = false`)
- автоматическое зеркало в global pointer `workspace/_pointers/anim_latest.json` разрешено только
  для канонического `PNEUMO_WORKSPACE_DIR/exports` или при явном opt-in; ad-hoc/pytest/offline exports
  не должны отравлять durable global pointer тестовыми путями
- `run_artifacts._workspace_dir()` не должен импортировать optional `pneumo_solver_ui.config`
  пока `PNEUMO_WORKSPACE_DIR` уже задан: иначе это создаёт ложные internal `ModuleNotFoundError` в логах
- pointer preview в Desktop Animator page обязан показывать `visual_cache_token`
  и `visual_reload_inputs`
- global run-artifacts pointer `workspace/_pointers/anim_latest.json` обязан зеркалить тот же
  `visual_cache_token`, `visual_reload_inputs` и `visual_cache_dependencies`, чтобы cross-page autoload
  и preflight видели ту же причину reload, что и локальный `workspace/exports/anim_latest.json`
- `run_artifacts.autoload_to_session(...)` обязан публиковать в session_state:
  - `anim_latest_visual_cache_token`
  - `anim_latest_visual_reload_inputs`
  - `anim_latest_visual_cache_dependencies`
- `ui_preflight` обязан показывать short token и статус синхронизации локального/export pointer
  с global run-artifacts pointer

Иначе получается тихий рассинхрон:
web UI уже показывает новую дорогу из sidecar, а Desktop Animator в режиме follow остаётся на старой.

### 7.6 run_registry / launcher / send-bundle обязаны видеть тот же anim_latest reload contract

- `workspace/_pointers` должен попадать в send-bundle вместе с `workspace/exports`, чтобы global pointer не терялся вне UI
- root `workspace/` внутри send-bundle обязан отражать **effective runtime workspace**: если задан `PNEUMO_WORKSPACE_DIR`, то именно его `exports/ui_state/_pointers/...` должны попадать под `workspace/`, а не пустой repo-local fallback
- `env_override/PNEUMO_WORKSPACE_DIR/...` разрешён только как дополнительная прозрачная копия, когда effective workspace уже другой; он не должен быть единственным местом, где лежат `anim_latest` и `ui_state`, иначе validator/health/dashboard видят ложные `_EMPTY_OR_MISSING` markers
- send-bundle обязан публиковать sidecar-файлы:
  - `latest_anim_pointer_diagnostics.json`
  - `latest_anim_pointer_diagnostics.md`
  и включать их в `triage/` внутри ZIP
- `run_registry.log_send_bundle_created(...)` обязан принимать и логировать поля:
  - `anim_latest_available`
  - `anim_latest_global_pointer_json`
  - `anim_latest_pointer_json`
  - `anim_latest_npz_path`
  - `anim_latest_visual_cache_token`
  - `anim_latest_visual_reload_inputs`
  - `anim_latest_visual_cache_dependencies`
  - `anim_latest_updated_utc`
- launcher-события `run_start`, `run_end` и `send_results_gui_spawned` обязаны прикладывать тот же anim-latest diagnostics snapshot, чтобы RCA по run-registry видел не только факт запуска/закрытия, но и какой именно reload-token был активен
- `send_results_gui` должен показывать `anim_latest_visual_cache_token` и `anim_latest_visual_reload_inputs`, если send-bundle sidecar уже собран

Иначе токен reload есть внутри локального pointer, но теряется в send-bundle/launcher telemetry, а это ломает сквозную диагностику.
- `validate_send_bundle` обязан поднимать в `validation_report.json/.md` отдельный блок `anim_latest` с полями:
  - `visual_cache_token`
  - `visual_reload_inputs`
  - `pointer_sync_ok`
  - `reload_inputs_sync_ok`
  - `npz_path_sync_ok`
  - `sources`
- validator обязан сравнивать минимум три поверхности, если они присутствуют:
  - `triage/latest_anim_pointer_diagnostics.json`
  - `workspace/exports/anim_latest.json`
  - `workspace/_pointers/anim_latest.json`
- `dashboard_report` обязан показывать `anim_latest` diagnostics отдельной секцией и тянуть их:
  1. из `latest_anim_pointer_diagnostics.*` sidecar рядом с bundle,
  2. либо из `triage/latest_anim_pointer_diagnostics.*` внутри ZIP,
  3. либо из `validation_report.json`, если sidecar ещё не разложен рядом

### 7.7 Финальные triage / validation / dashboard отчёты обязаны сохранять anim_latest reload-первопричину

- финальные отчёты не имеют права терять `anim_latest_visual_cache_token` и `anim_latest_visual_reload_inputs`
  после того, как они уже появились в pointer/export/run-registry
- mismatch между triage-sidecar, local pointer и global pointer должен всплывать в validation как человекочитаемое предупреждение,
  а не теряться в глубине ZIP
- `triage_report` обязан поднимать отдельный блок `anim_latest` и показывать минимум:
  - `anim_latest_available`
  - `anim_latest_visual_cache_token`
  - `anim_latest_visual_reload_inputs`
  - `anim_latest_pointer_json`
  - `anim_latest_global_pointer_json`
  - `anim_latest_npz_path`
- `bundle/README_SEND_BUNDLE.txt` обязан дублировать тот же `anim_latest_visual_cache_token` и `anim_latest_visual_reload_inputs`,
  чтобы получатель видел активный reload-контракт сразу после открытия ZIP, без обязательного чтения sidecar/JSON
- dashboard HTML обязан показывать:
  - `anim_latest.available`
  - short token
  - `visual_reload_inputs`
  - статус `pointer_sync_ok`
- sidecar отсутствие допускается только как warning; старые bundle не должны ломаться,
  но новые bundle обязаны давать полную сквозную диагностику

Иначе token reload уже есть в bundle, но пользователь всё ещё не видит его в финальных отчётах, а значит RCA снова рвётся на последнем шаге.

- `health/health_report.json` и `health/health_report.md` обязаны создаваться в финальном send-bundle после того,
  как в ZIP уже встроены validation/dashboard/triage
- `health_report` обязан поднимать canonical `signals.anim_latest` и не терять:
  - `visual_cache_token`
  - `visual_reload_inputs`
  - `pointer_sync_ok`
  - `reload_inputs_sync_ok`
  - `npz_path_sync_ok`
  - `issues`
- `tools.inspect_send_bundle` обязан уметь собрать тот же anim-latest summary даже для старого bundle,
  где embedded health-report ещё отсутствует

Иначе offline-разбор ZIP снова зависит от ручного чтения нескольких JSON внутри архива, а это ломает быстрый RCA уже после получения bundle.

## Compare / Qt / offline NPZ inspection

- `compare_ui.load_npz_bundle(...)` обязан поднимать `bundle["anim_diagnostics"]` и
  `meta["_anim_diagnostics"]` для любого загруженного NPZ
- этот snapshot обязан содержать **оба** слоя:
  - `bundle_visual_cache_token` / `bundle_visual_reload_inputs` — токен, вычисленный для текущего местоположения файла
  - `pointer_visual_cache_token` / `pointer_visual_reload_inputs` — токен из соседних pointer/triage surfaces, если они найдены
- compare/offline consumers обязаны явно показывать флаги:
  - `bundle_vs_pointer_token_match`
  - `bundle_vs_pointer_reload_inputs_match`
  - `bundle_vs_pointer_npz_path_match`
- `visual_cache_token` обязан быть **context-agnostic**: один и тот же NPZ + sidecar payload не имеет права давать разные token
  только из-за разных строк `context` в exporter / compare_ui / offline tools
- `qt_compare_viewer` обязан показывать этот snapshot в UI для выбранного прогона,
  чтобы перенос/распаковка bundle не маскировали mismatch между текущим файлом и старым pointer token
- `tools.inspect_npz_bundle` обязан печатать тот же canonical snapshot для offline-разбора одного `.npz`

Иначе Compare/Qt/offline-анализ видит только текущий сигнал, но не видит, что pointer-диагностика уже разъехалась после копирования/распаковки артефакта.

---

## R17 stage‑1 — solver-points v2 scaffold для spatial DW

Ниже зафиксирован **переходный visual/solver contract** для R17.
Он не отменяет действующий R48‑порядок работы: сначала честный solver-points contract,
потом перевод 2D/3D, и только потом новый runtime.

### 1) Source-data intake

Новый solver не должен читать geometry-параметры напрямую из legacy `dw_*` как окончательный канон.
В stage‑1 вводится отдельный validated source-data слой с семействами:

- hardpoints рычагов (`верхний_рычаг_...`, `нижний_рычаг_...`),
- верхние точки цилиндров (`верх_Ц1/Ц2_...`),
- нижние крепления штока (`низ_Ц1/Ц2_..._рычаг_крепления`, `..._ветвь_трапеции`, `..._доля_рычага`).

Машинный контракт см. `pneumo_solver_ui/r17_source_data_contract.py`.

### 2) Solver-points v2 (обязательные triplets)

Для каждой оси `ось ∈ {перед, зад}` solver v2 должен уметь экспортировать
абсолютные triplets не только для "одной линии рычага", а для ветвей трапеций.

#### Верхний рычаг
- `upper_arm_frame_front_{ось}_{x|y|z}_м`
- `upper_arm_frame_rear_{ось}_{x|y|z}_м`
- `upper_arm_hub_front_{ось}_{x|y|z}_м`
- `upper_arm_hub_rear_{ось}_{x|y|z}_м`

#### Нижний рычаг
- `lower_arm_frame_front_{ось}_{x|y|z}_м`
- `lower_arm_frame_rear_{ось}_{x|y|z}_м`
- `lower_arm_hub_front_{ось}_{x|y|z}_м`
- `lower_arm_hub_rear_{ось}_{x|y|z}_м`

#### Цилиндры
- `cyl1_top_{ось}_{x|y|z}_м`
- `cyl1_bot_{ось}_{x|y|z}_м`
- `cyl2_top_{ось}_{x|y|z}_м`
- `cyl2_bot_{ось}_{x|y|z}_м`
- `cyl1_axis_{ось}_{x|y|z}` *(service/derived)*
- `cyl2_axis_{ось}_{x|y|z}` *(service/derived)*
- `cyl1_piston_{ось}_{x|y|z}_м` *(service/derived)*
- `cyl2_piston_{ось}_{x|y|z}_м` *(service/derived)*
- `cyl1_rod_end_{ось}_{x|y|z}_м` *(service/derived)*
- `cyl2_rod_end_{ось}_{x|y|z}_м` *(service/derived)*

#### Колесо / дорога
- `wheel_center_{угол}_{x|y|z}_м`
- `road_contact_{угол}_{x|y|z}_м`

### 3) Жёсткие правила

- Частичный triplet — ошибка контракта.
- Если source-data не содержит обязательных hardpoints трапеции — solver не имеет права
  "угадывать" их из `dw_*` или из визуальных эвристик.
- `cyl1/cyl2` не привязываются к upper/lower arm по номеру цилиндра. Это задаётся
  только source-data ключом `низ_Ц*_*_рычаг_крепления`.
- Параметр `..._доля_рычага` сохраняется как канон, но работает вместе с
  `..._ветвь_трапеции`; одного скаляра доли недостаточно.

### 4) Stage‑1 boundary

На текущем этапе этот документ фиксирует scaffold и канон имен.
Полный runtime‑переход разрешён только после того, как manual/source-data intake
закроет обязательные hardpoints без invented values.


## R20 solver-points v2 / explicit trapezoid branches
- Solver/export must emit `lower_arm_frame_front/rear`, `lower_arm_hub_front/rear`, `upper_arm_frame_front/rear`, `upper_arm_hub_front/rear` triplets when explicit DW trapezoid branch data is available.
- `cyl1_top/cyl2_top` must respect explicit `верх_Ц*_x_относительно_оси_ступицы_м` source-data.
- `cyl1_bot/cyl2_bot` must respect explicit arm selection + trapezoid branch selection, without animator-side fallbacks.


### 7.4 Cylinder packaging contract for honest 3D body/rod/piston rendering

Если bundle хочет, чтобы Desktop Animator рисовал **честные** 3D цилиндры/штоки/поршни,
одних solver-point осей недостаточно. В `meta_json.geometry` должны присутствовать
канонические packaging-ключи:

- `cyl1_bore_diameter_m`, `cyl1_rod_diameter_m`, `cyl2_bore_diameter_m`, `cyl2_rod_diameter_m`
- `cyl1_stroke_front_m`, `cyl1_stroke_rear_m`, `cyl2_stroke_front_m`, `cyl2_stroke_rear_m`
- `cyl1_outer_diameter_m`, `cyl2_outer_diameter_m`
- `cyl1_dead_cap_length_m`, `cyl1_dead_rod_length_m`, `cyl2_dead_cap_length_m`, `cyl2_dead_rod_length_m`

Правила:

- solver points задают **реальную ось сборки** (`cyl*_top` → `cyl*_bot`);
- geometry contract задаёт **типоразмер/упаковку**;
- Animator не имеет права выдумывать body outer diameter или piston thickness по месту.
- Visual semantics оси фиксированы: **body/frame-side at `cyl*_top`, rod/arm-side at `cyl*_bot`**.
- `положение_штока_*_м` трактуется как **rod extension** `0..Stroke`; при росте этого сигнала
  contract-derived piston plane должен двигаться к `cyl*_top` (cap/frame side), а не к `cyl*_bot`.

Допустимый SERVICE/DERIVED уровень в consumer:

- преобразовать contract-derived piston plane в визуальный диск;
- использовать contract-derived axis/center для body/rod/piston mesh placement;
- при отсутствии отдельного `gland/body-end` contract consumer имеет право показывать
  `housing = top -> bot` как **transparent shell**, а внутри неё — `rod = piston_plane -> bot`
  и точный piston plane. Это честнее, чем выдумывать fixed outer body break по месту.
- line/diagnostic helpers по-прежнему могут использовать внутренний split
  `body = top -> piston_plane`, `rod = piston_plane -> bot` как contract-derived internal geometry,
  но UI не должен выдавать этот split за точную внешнюю границу корпуса.

Недопустимо:

- silently рисовать 3D body по одному bore без outer diameter;
- silently выбирать piston thickness/offset из произвольных коэффициентов;
- визуально инвертировать сборку так, чтобы body выглядел закреплённым на arm-side,
  а piston plane при росте stroke уходил к `cyl*_bot`.



Дополнение R31Y:
- крупные scatter/billboard markers для piston plane не являются частью user-facing contract;
  если они используются для диагностики, они должны быть `debug-only` и hidden-by-default,
  иначе пользователь путает их с mount points / frame anchors.
- exporter-side `cyl*_gland_xyz` (или эквивалентный body-end key) остаётся открытым P0,
  потому что только он позволит consumer отказаться от transparent housing shell fallback.


Дополнение R31Z:
- live 3D GL больше не должен опираться на special external reparent path как на нормальный пользовательский detach-flow; для acceptance допускается native dock/floating с авто-паузой playback на время move/resize/layout transitions.
- user-facing 3D сцена не должна использовать `GLScatterPlotItem`/point-sprite шары для contact/piston markers; если нужны маркеры, они должны быть line-based или debug-only.
- пока exporter не даёт explicit `cyl*_gland_xyz`, consumer обязан показывать хотя бы четыре различимых слоя: transparent/edge outer shell, exact cap-side chamber, exact rod и exact piston plane/ring. Просто «ещё один цилиндр» не считается достаточной визуализацией packaging contract.
