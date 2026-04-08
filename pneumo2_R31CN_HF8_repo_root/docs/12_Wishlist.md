# Текущий Wishlist-снимок

Дата: 2026-03-21

## Физика и геометрия

- Catalogue-aware packaging для цилиндров после базового контракта R31W: Camozzi типоразмеры, outer-body limits, spring clearance, уши/крышки и реальные ограничения по каталогу.
- Адаптивный road mesh по кривизне поверхности и разрешению экрана.
- Контактный патч по локальной геометрии дороги и ориентации колеса, без декоративных форм.
- Честная 3D геометрия колеса относительно подвески: развал, схождение, изменение колеи.

## Визуальная эргономика

- Screen-aware layout для Windows DPI / scale / multi-monitor.
- Стабильный Dock layout без перекрытий и скрытой информации.
- Понятная телеметрия пневматики и мнемосхемы без неоднозначных обозначений.

## Производительность

- Убрать тяжёлые CPU-циклы после завершения расчётов.
- Кэшировать статическую 3D геометрию и обновлять только реально изменившиеся объекты.
- Держать OpenGL-путь быстрым на Windows за счёт `PyOpenGL_accelerate`.

## Источники

- `docs/PROJECT_SOURCES.md`
- `DOCS_SOURCES/PROJECT_CONTEXT_GOOGLE_DRIVE_LINKS.md`

## R29 addendum — 2026-03-21

- Автоматический self-check на SEND-bundle: детектор overlapping road traces / accordion-risk ещё до запуска Animator.
- Browser-side perf HUD: счётчики idle loops / redraw rate / RAF sources после detail-run.
- Visual acceptance preset для дороги: сравнение old/new road-profile reconstruction на одном bundle без ручного поиска причины.
- Отдельный regression gate: запрет hidden closure correction / periodic spline для непериодического SINE в ring generator.



## R30 addendum — 2026-03-21

- В ring editor показывать не только локальную амплитуду сегмента, но и сравнение с запрошенной `aL_mm/aR_mm` в явном табличном виде для выбранного SINE-сегмента.
- Для web cockpit добавить browser-side perf overlay: FPS, RAF source count, paused-idle polling interval, wakeups per second после detail-run.
- Для Desktop Animator добавить переключатель `фон. сетка мира`, но по умолчанию держать её выключенной при активной road mesh.
- Отдельный regression-gate на дорожный wire-grid: поперечные линии не должны быть визуально «редкими и неподвижными» относительно движущейся дороги.
- R30: road preview/animator — surface dense by screen/curvature, wire grid attached to road (без статической world-grid путаницы), scenario preview показывает amplitude и peak-to-peak раздельно.


## R31 addendum — 2026-03-21
- IntersectionObserver/visibility gating для тяжёлых web-компонентов, чтобы off-screen iframes не держали CPU.
- Явный browser performance trace exporter в SEND-bundle для post-run CPU regressions.
- Отдельный diagnostic overlay в Animator: mesh density, active FPS, playback lag, source of contact point (solver vs patch).
- Явная политика замыкания кольца: strict-exact profile vs explicit closure segment, без скрытых линейных подтяжек.

## R31O addendum — 2026-03-23
- Явное разделение `raw preview truth` и `closed export spline` для ring, чтобы UI мог показывать реальный authored seam и при этом не ломать periodic export.
- Отдельный debug-переключатель в ring UI: raw vs closed overlay на одном графике, без путаницы "что именно сейчас видит пользователь".
- Release-gate automation, которая отдельно хранит targeted pytest/py_compile логи для patch-release рядом с build manifest.
- Measured Windows acceptance pack: browser performance trace + Qt/OpenGL viewport capture + bundle hash в одном месте.

## R31P addendum — 2026-03-24

- Workaround R31P (`3D остаётся docked`) зафиксирован как временный и **superseded by R31Q**, потому что он ломал требуемый detached 3D UX.
- Логи bundle/triage должны различать seq не только по session_id, но и по процессу, если Desktop Animator пишет в тот же session log.
- После замены workaround на dedicated top-level window нужен повторный ручной Windows acceptance на реальном viewport/driver stack.

## R31Q addendum — 2026-03-24

- Dedicated top-level GL window для Animator вместо floating `QDockWidget`: сохранить отдельное 3D окно без отключения требуемого detached режима.
- Persistence для внешних panel windows: geometry/visible state, корректное закрытие с main window, быстрый reopen из меню `Окна`.
- Отдельный regression-gate для Windows GL viewport: open → retile → move → resize → close/reopen → playback без `GLError` и без `0xC0000409`.
- Bundle acceptance pack должен явно фиксировать, что `R31P` был workaround, а `R31Q` — попытка root-cause-oriented layout fix с сохранением требуемого UX.

## R31R addendum — 2026-03-24

- Regression-gate на 3D road window: нельзя строить mesh за пределами общего диапазона реальных дорожных данных; repeated endpoint slices и degenerate faces должны считаться багом, а не допустимой деградацией.
- Явный playback performance tier для live GL road mesh: отдельные caps для normal-play и many-docks mode вместо одного тяжёлого quality-профиля на любой playback.
- Bundle-side diagnostic для road mesh: число duplicate longitudinal slices / degenerate faces на representative frames у начала, середины и конца run.
- Canonical `road_width_m` должен приходить из exporter/base contract, а не только вычисляться в Animator как SERVICE/DERIVED.
## R31S addendum — 2026-03-24

- Visible auxiliary panes в Desktop Animator должны оставаться «живыми» на playback: допустим capped FPS + lighter overlays, но не single-panel round-robin starvation, который визуально замораживает остальные окна.
- Road wire-grid в 3D должна быть world-anchored по longitudinal `s`, а не viewport-anchored к первой видимой строке mesh, чтобы сетка не дрейфовала относительно дороги.
- Acceptance pack для Animator должен явно фиксировать cadence auxiliary panes и визуальную фазу road grid relative to road на живом Windows bundle.


## R31T addendum — 2026-03-24

- Bundle/view-stable longitudinal road grid spacing: visible cross-bars должны быть привязаны не только по world-phase, но и по world-spacing, независимому от текущего playback window.
- Acceptance telemetry для detached panes: SEND bundle должен содержать cadence-метрики redraw/update по каждому exposed auxiliary pane, timeline и trends, чтобы frozen/pseudo-live режим проверялся количественно.
- Higher playback cadence floor для many-docks: облегчённые overlays допустимы, но detached окна не должны опускаться до субъективного near-freeze ради 3D FPS.

## R31U addendum — 2026-03-24

- Startup GL placeholder meshes не должны порождать даже одиночный `MeshData invalid value encountered in divide`: пустое состояние Animator должно быть genuinely empty, а не состоять из нулевых дегенератных faces.
- `meta.geometry.road_width_m` должен приходить в bundle явно из exporter-side supplement/policy, чтобы Animator не подменял export contract собственным consumer-side SERVICE/DERIVED fallback.
- Acceptance bundle должен быть логически чистым: runtime warnings уровня deprecated Qt API не должны маскировать реальные визуальные/GL регрессии.



## R31V addendum — 2026-03-24

- Для road wire-grid держать именно world-anchored поперечные полосы без viewport-edge bar и без привязки к ближайшим строкам surface mesh.
- Для acceptance bundle сохранять и проверять визуально smoothness поперечных полос на длинном playback, особенно на ring/seam и при изменении look-ahead.


## R31W addendum — 2026-03-24

- Explicit packaging contract для цилиндров/поршней должен жить в `meta.geometry`, а не в Animator-эвристиках.
- Поршень в 3D должен рисоваться от contract-derived piston plane; никакой выдуманной thickness/fake-offset в consumer-side коде.
- Следующий уровень после R31W: catalogue-aware Camozzi sizing/limits + acceptance `поршень≈середина хода` в статике.


## R31X addendum — 2026-03-24

- Для road surface mesh нужна та же world/bundle-stable longitudinal anchoring policy, что уже была введена для wire-grid: нельзя оставлять shaded surface на per-frame `linspace(s_min, s_max, n_long)`, если пользователь видит дрейф самой геометрии поверхности.
- Для cylinders/pistons visual contract должен явно фиксировать семантику: `cyl*_top = frame/body side`, `cyl*_bot = arm/rod side`, `stroke_pos = rod extension`, а не допускать обратную consumer-side трактовку.
- Acceptance bundle после R31X должен отдельно проверять две вещи: (1) исчезновение drift у dense surface mesh, не только у cross-bars; (2) визуальное соответствие «цилиндр к раме, шток к рычагу» на всех углах и для обоих каналов.



## R31Y addendum — 2026-03-24

- Dense road surface не должна зависеть даже от способа локальной аппроксимации visible slice: lateral normal/width orientation нужно брать из bundle-level world path cache, иначе пользователь всё ещё видит drift/«ползущую» геометрию при изменении размера 3D окна.
- 3D GL по умолчанию должен оставаться **dockable** и пристыковываться обратно как обычная панель; safe separate window допустимо только как explicit detach-mode, а не как forced startup policy.
- Для cylinders/pistons до появления explicit gland/body-end contract Animator должен честно показывать transparent housing shell + exact rod + exact piston plane, а confusing scatter markers должны оставаться debug-only и скрыты по умолчанию.
- Следующий уровень visual contract для цилиндров — exporter-side `cyl*_gland_xyz` / equivalent external body-end point, чтобы уйти от fallback shell и прийти к полностью честному fixed housing length + exposed rod rendering без consumer-side выдумок.
- Acceptance bundle после R31Y должен дополнительно проверять четыре вещи: отсутствие road drift при resize 3D окна, понятную видимость piston plane, detach/re-dock 3D без потери snapping UX и отсутствие CPU tail после завершения расчётов / остановки playback.


## R31Z addendum — 2026-03-24

- [x] Убран special external/reparent path для live 3D GL как основной пользовательский сценарий: 3D снова живёт через native dock/floating `QDockWidget`, а не через «безопасное отдельное окно».
- [x] Во время move/resize/layout change live 3D playback теперь автоматически ставится на паузу, обновление GL подавляется до стабилизации layout, затем playback продолжается с текущего кадра.
- [x] Из user-facing 3D сцены убраны point-sprite/GLScatter шары: contact markers переведены в line-crosses, а piston debug-balls не участвуют в обычной отрисовке.
- [x] Cylinder packaging в Animator стал читаемее: outer housing shell остаётся честной оболочкой, но внутри теперь отдельно видны exact chamber, exact rod, exact piston plane и piston ring — не только «просто цилиндры».
- [ ] Принять R31Z на живом Windows SEND bundle: native float/re-dock 3D при playback с авто-паузой, отсутствие `GLMesh/GLLine/GLScatter` warning-spam/AV-crash и отсутствие CPU tail после расчётов/stop playback.
- [ ] Если CPU tail не уйдёт вместе с GL error-spam/layout-fix, добавить отдельную post-calc instrumentation и принудительное завершение хвостовых redraw/update loops.


## R31AA addendum — 2026-03-25

- Browser follower-компоненты должны уметь отличать реально видимый iframe от hidden Streamlit tab/layout slot: zero-size rect, `clientWidth/clientHeight≈0` и CSS-hidden frame обязаны считаться off-screen, иначе page-level idle guards бессмысленны.
- Для тяжёлых web-loop path нужен single-flight scheduler policy: `storage`/`focus`/`visibility` wakeups не должны запускать вторую/третью RAF/timeout chain поверх уже существующей.
- Acceptance pack должен сохранять browser-side wakeup counters по компонентам (`mech_anim`, `mech_car3d`, `pneumo_svg_flow`, minimap, road profile), чтобы post-run CPU regressions можно было ловить по bundle, а не по устному описанию.
- После R31AA следующий шаг для Web UI — page-level perf overlay / trace export: количество активных iframes, idle poll interval, off-screen gated count, duplicate-loop guard hits и browser FPS после detail-run.


## R31AB addendum — 2026-03-25

- Browser idle-CPU policy должна быть **сквозной**, а не жить только в 2–3 тяжёлых виджетах: любой follower с own RAF/timeout loop обязан иметь off-screen guard, single-flight wake discipline и измеримую perf-телеметрию.
- Acceptance для Web UI должен включать не только "CPU стало тише", но и **browser perf registry snapshot**: wakeups, duplicate-loop guard hits, hidden iframe gating, current loop kind, idle poll и render counts по каждому follower-компоненту.
- `playhead_ctrl` становится user-facing точкой для browser perf inspection: быстрый overlay + JSON export без forced rerun и без необходимости лезть в DevTools.
- Если R31AB всё ещё не добьёт post-run CPU tail на живом Windows, следующий wishlist-уровень — автоматическая инъекция browser perf snapshot в diagnostics/SEND bundle и page-level aggregate trace по всем iframe-компонентам.



## R31AC addendum — 2026-03-25

- Любой user-facing cylinder/packaging refactor в Desktop Animator обязан проходить regression-gate на **startup first-frame load**: нельзя считать релиз валидным, если `load_npz` падает раньше первого кадра и пользователь видит «аниматор висит / дороги не видно».
- Acceptance bundle должен различать `data missing` и `consumer crash`: если `anim_latest`/road CSV присутствуют и pointer sync = OK, но сцена не рисуется, triage обязан поднимать это как visual-consumer crash, а не как проблему экспорта дороги.
- Для Car3D helper-методов, которые не используют состояние объекта, нужно держать явную семантику (`@staticmethod` или явный `self`) и покрывать её source-level regression test, иначе мелкая сигнатурная ошибка ломает весь Animator path.

## R31AD addendum — 2026-03-25

- User-facing visual слои Animator должны быть fail-soft: ошибка в sublayer (например piston ring polyline) не имеет права скрывать road/scene целиком и не должна снова маскироваться под «дорога пропала».
- Ring editor defaults нужно держать как explicit user-approved canonical preset, а не как случайный исторический набор старых `C/B + 4 мм` значений; следующий шаг — кнопка `Сделать текущий сценарий дефолтом` с сохранением в явный профиль.
- Suite/test list должен поддерживать честное состояние `(не выбрано)` и после autosave/import/reset, чтобы UI не навязывал пользователю карточку первого сценария без явного выбора.



## R31AE addendum — 2026-03-25

- [x] Возвращён нормальный выбор сценария в main/legacy suite editor: принудительный пустой selection убран, а выбор первого сценария снова используется только как UI-focus, а не как запуск enabled-по-умолчанию baseline.
- [x] Оба shipped suite presets (`default_suite.json`, `default_suite_long.json`) теперь стартуют с `включен=false` для всех строк; baseline больше не начинает считать из-за случайно включённого default-сценария.
- [x] Создание нового ring-сценария остаётся intentional-action path: новые сценарии по-прежнему создаются с `включен=true`.
- [x] Web follower-компоненты и embedded HTML-виджеты переведены на более жёсткий idle-sleep (`15s / 30s / 60s`): основной wake-path теперь `storage/focus/visibility`, а не частый paused polling.
- [x] Dense road surface и visible wire grid теперь оба используют stable native support rows из dataset `s_world`; frame-local visible-window resampling оставлен только как fallback, а не как основной источник longitudinal geometry.
- [x] Для цилиндров добавлены явные frame-side mount markers по `cyl*_top`, ослаблено визуальное доминирование full housing shell и усилена читаемость chamber / piston слоёв.
- [ ] Принять R31AE на живом Windows SEND bundle: подтвердить отсутствие post-run Web UI CPU tail, исчезновение resize/playback road drift и визуально корректное положение frame-side cylinder mount markers.

## R31AF addendum — 2026-03-25

- [x] Добить следующий шаг по Web UI idle CPU: перевести follower-компоненты и embedded HTML-виджеты на очень длинный pause-idle cadence `60 s / 180 s / 300 s`, оставив `storage / focus / visibility` основным wake-path.
- [x] Исправить дефолтные frame-side точки крепления цилиндров в source data: верхние крепления по умолчанию ставятся на верхнюю плоскость рамы по `z` и на левую/правую боковые плоскости рамы по `y`.
- [x] Вернуть полную графику на видах `2D: Спереди/Сзади`: локально восстановить runtime visual toggles в `FrontViewWidget.update_frame()` вместо частично отключённого richer-draw path.
- [x] Не показывать пустые startup GL road/contact/cylinder meshes до прихода валидной геометрии кадра, чтобы не провоцировать чёрный экран / "дороги не видно" на старте.
- [ ] Принять R31AF на живом Windows SEND bundle: проверить, что post-run Web UI CPU tail действительно погашен, что front/rear views рисуют полный набор графики, и что новая дефолтная постановка frame-side cylinder mounts визуально читается как `цилиндр к раме / шток к рычагу`.

## R31AH addendum — 2026-03-26

- Solver/export contract должен гарантировать **геометрическую неразрывность** без учёта жёсткости: frame-side hardpoints остаются жёстко приклеенными к раме при крене/тангаже/перемещении, wheel-side hardpoints — к ступице/колесу, rod-side cylinder mount — к выбранной ветви рычага.
- Acceptance для подвески должен быть не только визуальным, но и метрическим: `max_frame_mount_body_local_drift_m`, `max_hub_mount_pairwise_drift_m`, `max_cyl*_bot_arm_offset_m` должны попадать в HUD/self-check/bundle diagnostics.
- Архив чатов нужно использовать как контекстный индекс, а не как равноправный слой истины: в `mhtml.zip` много точных дублей тем и обсуждений, поэтому каноном остаются ABSOLUTE LAW, PARAMETER REGISTRY, master TODO/WISHLIST и свежий patch-plan.
- Для Web UI post-run CPU acceptance нужен именно browser render-loop/trace gate, а не очередное растягивание idle timeout: если `requestAnimationFrame`/render loop живы в паузе, это должно ловиться perf registry/trace и попадать в SEND bundle.


## R31AI addendum — 2026-03-26

- [x] Разобран свежий Windows SEND bundle и подтверждён новый root cause по Desktop Animator: при манипуляции окнами ловятся реальные `OpenGL GLError` в `GLMeshItem/GLLinePlotItem`, а cadence playback при 11 видимых панелях проваливается примерно до 0.9–1.0 Hz.
- [x] Live GL layout guard переведён на dock-level observation only: больше не отслеживаются внутренние Move/Resize/Show события самого GL viewport/child widget, из-за которых layout transition churn рос лавинообразно.
- [x] На время floating move/resize 3D viewport теперь действительно **suspend**: показывается placeholder, GL view скрывается и перестаёт пытаться paint во время нестабильного layout/context path.
- [x] Playback budget ужесточён в пользу 3D: service timer ускорен (`4 ms` на `x1.0`), threshold `many visible docks` снижен до `8`, а cadence fast/slow panes уменьшен, чтобы не отбирать кадры у live 3D.
- [x] В 3D playback уменьшена плотность road mesh для active/perf mode: меньше longitudinal/lateral samples во время play, без возврата к старой редкой wire-grid вместо поверхности.
- [ ] Повторно принять R31AI на живом Windows bundle: подтвердить отсутствие `OpenGL GLError` при drag/resize/floating/re-dock, заметно более живую playback cadence на `speed=1.0` и отсутствие полного UI freeze при манипуляции окнами.
- [ ] Web UI CPU acceptance остаётся отдельной задачей и не считается автоматически закрытой этим Desktop Animator fix-pass.

## R31AL addendum — 2026-03-26

- [x] Сделан углублённый аудит производительности Desktop Animator: подтверждено, что после R31AK bottleneck сместился с плотности `anim_latest` кадров на GUI-thread playback/timer policy, агрессивное source-frame chasing и слишком дорогие auxiliary panes.
- [x] Playback Desktop Animator переведён с source-frame chasing на display-rate continuous-time playhead: таймер больше не работает как `4 ms` service loop на `x1.0`, а скорость снова влияет на положение проигрывания вместо схлопывания в «одинаково дёрганый» режим под нагрузкой.
- [x] Auxiliary panes во время playback дополнительно демотированы: fast-group оставлен только для HUD, а front/rear/left/right и остальная периферия переведены в slow-group с ещё более жёсткими FPS лимитами.
- [x] Web follower/embedded widgets перестали держать старый `__nextIdleMs(60000, 180000, 300000)` timeout-polling: в idle они теперь останавливают loop полностью и просыпаются в основном по `storage/focus/visibility/scroll/resize`.
- [x] Визуализация цилиндров стала читаемее: actuator meshes теперь используют capped cylinder geometry с торцевыми стенками, внешний корпус рисуется гранями, а внутренняя камера ослаблена и больше не должна выглядеть как «второй цилиндр внутри сверху».
- [ ] Принять R31AL на живом Windows SEND bundle: подтвердить, что speed selector снова реально меняет playback speed, что `x1.0` меньше дёргается, что auxiliary panes перестали заметно душить 3D, и что post-run browser/Web UI CPU tail действительно ушёл уже на реальном стеке.

## R31BU addendum — 2026-03-31

- [x] `playhead_ctrl` теперь умеет не только скачать browser perf registry JSON в браузер, но и отправить явный `browser_perf_snapshot` обратно в Python/UI для сохранения в `workspace/exports`.
- [x] В `workspace/exports` введены канонические артефакты `browser_perf_registry_snapshot.json` и `browser_perf_contract.json`; если рядом присутствует тяжёлый trace (`browser_perf_trace.trace|json|cpuprofile`), diagnostics/SEND bundle/triage поднимают и его.
- [x] SEND bundle и triage теперь явно показывают browser perf evidence (`snapshot / contract / trace`), чтобы post-run CPU обсуждался по артефактам, а не по устным симптомам.
- [ ] Измеримая Windows acceptance для `WEB-PERF-05` остаётся отдельным следующим шагом: нужен живой `browser_perf_trace` + comparison report с реального detail-run.


## R31BV addendum — 2026-04-07

- Канонический путь задания **всех** пользовательских сценариев в проекте — только через `ring editor`; дублирующие/альтернативные сценарные UI могут жить только как compatibility/read-only surfaces.
- Сценарии должны не только запускаться из `ring editor`, но и полноценно **редактироваться** там же: пользователь не должен лазить в JSON или в скрытые service-поля, чтобы поменять смысл сценария.
- Все пользовательские настройки сценария обязаны быть доступны в UI; любое поле/флаг, влияющее на физический смысл, должно иметь понятное развёрнутое объяснение прямо рядом с контролом.
- Семантика сегмента должна быть переосмыслена: типы `ACCEL/BRAKE/...` не являются каноническими пользовательскими типами сегмента. Пользователь задаёт:
  - направление движения сегмента: `прямо / поворот влево / поворот вправо`;
  - конечную скорость сегмента;
  - дорожные параметры сегмента.
- Для кольцевого редактора начальные параметры явно редактируются только у **первого** сегмента; у остальных сегментов пользователь задаёт только конечные параметры, а стартовые значения наследуются автоматически от предыдущего сегмента.
- Конечные параметры последнего сегмента должны автоматически совпадать с начальными параметрами первого сегмента, чтобы кольцо замыкалось без ручного дублирования пользователем.
- Продольный уклон дороги нужно задавать через **высоту дороги в конце каждого сегмента** и через **высоту дороги в начале первого сегмента**.
- Разбегание высот левой/правой колеи нужно решать не раздельным дрейфом двух колей, а через явный параметр **поперечного уклона сегмента**.
- Пружины должны задаваться либо вручную, либо автоматически подбираться так, чтобы при стоянке на ровной площадке с текущей массой поршни находились примерно в середине хода.
- Геометрия пружин должна проверяться на непересечение: пружины одного угла не должны пересекаться между собой и с цилиндрами.
- Передние `Ц1/Ц2` и задние `Ц1/Ц2` цилиндры могут быть разными по типу, ходу и точкам крепления; то же относится к пружинам. Это нужно поддержать как минимум для четырёх семейств на одну сторону с учётом продольной симметрии машинки.
- Оптимизация обязана учитывать эти независимые семейства цилиндров/пружин и их ограничения, а не предполагать «один общий цилиндр» или «одну общую пружину» на все углы.

