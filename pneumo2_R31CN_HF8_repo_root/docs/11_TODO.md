# Текущий TODO-снимок

Дата: 2026-03-21

## P0 — не закрыто

- Проверить и исправить генератор ring/road profile: амплитуда, фаза, координата по длине, отсутствие метровых выбросов.
- Добить post-run CPU load в Web UI после завершения детального прогона: исключить idle redraw / RAF / DOM-loop.
- Добить FPS / playback в Desktop Animator: честный dt-aware режим без потери кадров.
- Дорога в Animator: плотная поверхность по кривизне и экранному разрешению, без гармошки и без редкой сетки вместо меша.
- Пятно контакта: только по subset поверхности дороги в зоне контакта, без эллипса/прямоугольника-фантазии.
- Цилиндры/штоки/поршни: не возвращать фейковый 3D; вернуть только после полноценного solver/export packaging-контракта.
- Проверить геометрию колёс при ходе подвески: развал, схождение, колея, контакт с дорогой.
- Перепроверить телеметрию пневматики и мнемосхему ресивера: убрать неоднозначность потоков/состояний.
- Проверить и восстановить деградировавший Windows viewer графиков/диаграмм.

## Инфраструктура

- Установщик Windows должен ставить Desktop Animator зависимости, включая `PyOpenGL_accelerate`.
- В проекте должны быть закреплены внешние источники контекста: `docs/PROJECT_SOURCES.md`.

## Внешние источники

- `docs/PROJECT_SOURCES.md`
- `DOCS_SOURCES/PROJECT_CONTEXT_GOOGLE_DRIVE_LINKS.md`

## R29 status — 2026-03-21

Сделано в этом проходе:
- Найден и исправлен корень «гармошки» дороги: bin-merge overlapping road traces в `ensure_road_profile()`.
- Из 3D road mesh убрана бесполезная пересборка regular-grid faces на каждом кадре (`build_faces=False` + face cache в Animator).
- В ring generator убраны скрытые искажения профиля: нет per-segment mean shift для детерминированного SINE, нет hidden closure ramp, нет forced periodic spline.
- Встроенные HTML-виджеты `app.py` / `pneumo_ui_app.py` переведены на idle-guard: без лишнего DOM redraw в паузе.

Остаётся P0:
- Добить оставшийся post-run CPU load в реальном браузере на Windows SEND-run и найти, нет ли ещё живых idle-loop в page-level составе.
- Перепроверить визуальную приёмку дороги в Desktop Animator на реальном Qt/OpenGL viewport Windows после bin-merge.
- Вернуть честные 3D тела цилиндров/штоков/поршней только после полноценного solver/export packaging-contract.
- Добить контактный патч по полной локальной поверхности дороги и перепроверить колёсную геометрию (развал/схождение/колея).



## R30 status — 2026-03-21

Сделано в этом проходе:
- В ring editor добавлен локальный preview выбранного сегмента: отдельная локальная x-длина, локальная амплитуда по |z-median| и отдельные графики `z(x)` / `z-median(x)` для selected segment.
- Глобальный metric `Профиль: max-min` переименован в `Профиль ВСЕГО кольца: max-min`, чтобы не путать перепад всего кольца с амплитудой одного SINE-сегмента.
- Web cockpit follower-компоненты (`playhead_ctrl`, `road_profile_live`, `minimap_live`, `corner_heatmap_live`, `mech_anim_quad`, `mech_car3d`) переведены на более редкий idle-poll + storage-event wakeup.
- В Desktop Animator скрыта статическая мировая сетка при включённой дороге; дорожная wire-grid сделана заметно плотнее поперёк хода без возврата к тяжёлому full-refine.
- Для светлой road-surface убран shaded-шейдинг дороги, чтобы не подсвечивать ложную фасеточность на полигонах.

Остаётся P0:
- Живым браузерным профилированием на Windows подтвердить, что post-run CPU load действительно упал после перехода follower-компонентов на storage-event wakeup.
- На реальном Qt/OpenGL viewport Windows проверить, что пропали визуально «неподвижные редкие поперечные линии» и уменьшилась ломкость светлой поверхности дороги.
- Если пользовательский кейс всё ещё показывает «метры перепада», нужно сохранить конкретный spec/bundle и добить именно генерацию/preview этого кейса, а не лечить вслепую.
- [ ] R30: добить web idle-loops (storage-event wake + low-power pause), сделать ring-preview с явным разделением amplitude vs peak-to-peak и убрать визуальную путаницу road grid/world grid.


## R31 addendum — 2026-03-21
- [x] Проверить присланные diagnostics (`logs.zip`, `runs.zip`, latest SEND bundle) и подтвердить реальные источники симптомов.
- [x] Убрать idle `requestAnimationFrame` из web follower-компонентов в паузе; оставить wake по `storage/focus/visibility`.
- [x] Вернуть шейдинг дорожной поверхности в Desktop Animator и поднять потолок плотности surface mesh.
- [x] Перевести playback Animator с variable-interval таймера на wall-time accumulator, чтобы скорость и FPS не ломались на `dt=0.01`.
- [x] Переделать `contact patch` на refined local road-submesh вокруг колеса без возврата к эллипсам/прямоугольникам.
- [ ] Повторно принять на Windows: post-run CPU в браузере, реальное ощущение FPS, скорость playback, контактное пятно на кривой дороге.
- [ ] Отдельно добить ring-editor по глобальному шву кольца и диагностике ISO сегментов, не путая `A` и `p-p`.

## R31O addendum — 2026-03-23
- [x] Развести raw ring preview и periodic closure: `zL_m/zR_m` теперь сохраняют authored profile, а closed spline строится отдельно для export.
- [x] Убрать ложную seam slope correction для уже периодического SINE с фазой — без искусственного раздувания амплитуды у конца круга.
- [x] Убрать последний deprecated `use_container_width` из активного ring UI.
- [ ] Повторно принять на Windows: post-run browser CPU/FPS + Qt/OpenGL viewport acceptance на живом bundle.
- [ ] Добить solver-points / cylinder packaging contract для полностью честной 3D-механики.

## R31P addendum — 2026-03-24

- [x] В Windows manual SEND-bundle локализован crash-path: floating 3D GL dock при auto-detach/retile вызывал повторяющиеся OpenGL GLError и выход `0xC0000409`.
- [ ] Временный workaround R31P (`держать 3D docked`) **не считается принятым исправлением**: он нарушал требуемый detached 3D режим и был заменён в R31Q.
- [x] strict loglint больше не даёт ложный `non-monotonic seq` при смешении UI-процесса и дочернего Desktop Animator в одном session log.
- [ ] Повторно принять Windows bundle уже на R31Q: подтвердить отдельное 3D окно, move/resize/toggle и отсутствие падения на живом driver stack.
- [ ] Отдельно дожать canonical `road_width_m` в export/meta, чтобы Animator не уходил в SERVICE/DERIVED warning.

## R31Q addendum — 2026-03-24

- [x] Исправлена ошибка инженерного решения из R31P: live 3D GL больше не загоняется в docked-mode ради стабильности.
- [x] Для live GL введён отдельный `ExternalPanelWindow` вместо floating `QDockWidget`, чтобы сохранить требуемый detached/movable/resizable/toggleable 3D режим без Windows crash-path.
- [x] Для внешнего 3D окна добавлены menu-toggle, persistence `geometry/visible` через `QSettings` и корректное закрытие вместе с главным Animator окном.
- [ ] Повторно принять на реальном Windows bundle: spawn, detach, move/resize, close/reopen 3D окна, playback и bundle health уже на R31Q.
- [ ] Дожать canonical `road_width_m` в export/meta, measured Windows/browser perf acceptance и solver-points / cylinder packaging contract.

## R31R addendum — 2026-03-24

- [x] Найден корень дорожного артефакта/просадки FPS в Desktop Animator R31Q: окно дороги выходило за диапазон реальных данных, `np.interp` прижимал края к endpoint, что рождало repeated longitudinal slices, degenerate road faces и `MeshData invalid value encountered in divide`.
- [x] 3D road sampling window теперь клипуется к общему диапазону `s_world / road_profile(left/center/right)` перед интерполяцией — без фальшивых повторов на старте/финише прогона.
- [x] Для Car3D добавлены playback density tiers: во время play road mesh становится легче, а при множестве открытых dock-панелей включается более жёсткий perf-cap.
- [ ] Повторно принять R31R на живом Windows bundle: проверить исчезновение артефакта дороги у начала/конца записи, FPS playback и отсутствие `MeshData` warning-spam.
- [ ] Отдельно дожать canonical `road_width_m` в export/meta, чтобы Animator не работал через SERVICE/DERIVED warning.
## R31S addendum — 2026-03-24

- [x] Найден и убран корень «почти замороженных» auxiliary-окон в Desktop Animator: R31R при playback переводил visible panes в ultra-low cadence и в many-docks режиме обновлял fast/slow панели по одной через round-robin, из-за чего остальные окна выглядели остановившимися.
- [x] Playback scheduler теперь обновляет **все видимые fast/slow группы** на ограниченной, но живой частоте; many-docks mode остаётся облегчающим режимом, но больше не превращает окна в 1–2 FPS pseudo-freeze.
- [x] Видимая road wire-grid в 3D больше не привязана к локальному row=0 текущего viewport-окна: cross-bars выбраны по world-anchored `s`, чтобы сетка не «плыла» относительно самой дороги во время playback.
- [ ] Повторно принять R31S на живом Windows bundle: подтвердить, что 2D/HUD/telemetry окна остаются визуально живыми на playback и что road wire-grid идёт вместе с дорогой без фазового дрейфа.
- [ ] Отдельно дожать canonical `road_width_m` в export/meta, measured Windows/browser perf acceptance и solver-points / cylinder packaging contract.


## R31T addendum — 2026-03-24

- [x] Найден и закрыт второй корень drift-багa road wire-grid после R31S: world-anchor фазы сам по себе был недостаточен, потому что world spacing cross-bars всё ещё пересчитывался из текущего playback viewport/window и визуально «растягивался/сжимался» относительно одной и той же дороги.
- [x] Для Car3D введён bundle/view-stable расчёт `grid_cross_spacing_m`: spacing теперь кэшируется от nominal visible length + viewport bucket и больше не следует за каждым изменением look-ahead/visible window во время playback.
- [x] `CockpitWidget` получил более живой cadence floor для auxiliary panes (`24/12 FPS`, `18/10 FPS` в many-docks) вместо R31S-уровня, который ещё мог выглядеть близким к freeze на реальном Windows run.
- [x] В Desktop Animator добавлена telemetry-метрика `AnimatorAuxCadence`: будущие SEND bundles должны нести доказуемые cadence-окна по detached panes/timeline/trends вместо визуальных догадок.
- [ ] Повторно принять R31T на живом Windows bundle: подтвердить, что detached auxiliary panes действительно остаются живыми, а шаг/фаза road wire-grid визуально стабильны относительно дороги по всему playback.
- [ ] Отдельно дожать canonical `road_width_m` в export/meta, measured Windows/browser perf acceptance и solver-points / cylinder packaging contract.

## R31U addendum — 2026-03-24

- [x] Убран startup-source для `RuntimeWarning: invalid value encountered in divide` в Desktop Animator: road/contact placeholder meshes теперь создаются как truly empty meshdata, а не как два нулевых дегенератных треугольника.
- [x] Exporter больше не оставляет Animator без canonical `road_width_m`: при отсутствии/нуле visual road width теперь явно дополняется в `meta.geometry` из `track_m + wheel_width_m`, чтобы consumer-side SERVICE/DERIVED warning не был нормой каждого bundle.
- [x] Из Animator убраны текущие Qt deprecation-warning хвосты (`AA_EnableHighDpiScaling`, `AA_UseHighDpiPixmaps`, `QTableWidgetItem.setTextAlignment(int)`), чтобы acceptance pack чище отличал реальные регрессии от шумных runtime предупреждений.
- [ ] Повторно принять R31U на живом Windows bundle: подтвердить, что исчезли startup `MeshData` warning, derived `road_width_m` warning и Qt deprecation-warning trio, а playback/visual fixes R31Q–R31T не регресснули.
- [ ] Отдельно дожать measured Windows/browser perf acceptance и solver-points / cylinder packaging contract.



## R31V addendum — 2026-03-24

- [x] Убрана viewport-привязанная последняя поперечная полоса дороги: больше нет лишнего бара на дальнем краю текущего окна.
- [x] Поперечные полосы больше не привязаны к ближайшим строкам road mesh: они строятся по точным world-anchored `s`-позициям и не должны дрожать при скольжении viewport.
- [ ] Подтвердить на живом Windows SEND-bundle, что поведение полос визуально стало ровным на полном playback без новых артефактов.


## R31W addendum — 2026-03-24

- [x] Формализован explicit cylinder packaging contract для Animator: exporter теперь может передавать `cyl1/2_outer_diameter_m` и `cyl1/2_dead_cap|dead_rod_length_m` в `meta.geometry` без алиасов и скрытых догадок consumer-side.
- [x] В Desktop Animator возвращены честные 3D-тела цилиндров/штоков/поршней: ось идёт строго по solver-points, body/rod радиусы берутся из packaging contract, поршень рисуется как диск в contract-derived piston plane без выдуманной толщины.
- [x] Обновлены registry/contract docs под новый packaging слой (`01_PARAMETER_REGISTRY.md`, `DATA_CONTRACT_UNIFIED_KEYS.md`), чтобы ключи не жили «только в коде».
- [ ] Повторно принять R31W на живом Windows bundle: подтвердить, что cylinders/rods/pistons действительно видимы, не дрожат, не инвертируются и не вносят новую GL/FPS регрессию.
- [ ] Дальше по wishlist: перейти от общего packaging contract к catalogue-aware Camozzi sizing/limits и к статическому acceptance `поршень≈середина хода`.


## R31X addendum — 2026-03-24

- [x] Найден третий корень road-drift в Desktop Animator: после фиксов R31S/R31T world-stable оставалась только wire-grid, но dense shaded road surface всё ещё пересобиралась из frame-local `linspace(s_min, s_max, n_long)` и визуально «плыла» по той же дороге при изменении visible window/playback.
- [x] Dense road surface переведена на world-anchored longitudinal rows: `s_nodes` теперь строятся из bundle/view-stable `surface_spacing_m` + world anchor, а не из per-frame local linspace по текущему viewport.
- [x] Найден и закрыт корень visual-инверсии cylinders/pistons: consumer-side packaging трактовал рост `положение_штока` в обратную сторону, а body рисовал по всей оси до `cyl*_bot`, из-за чего нарушалась обязательная семантика «цилиндр к раме, шток к рычагу».
- [x] Packaging visual law уточнён в contract docs и коде: piston plane при росте `stroke_pos` идёт к `cyl*_top` (cap/frame side), внутренний split остаётся `top -> piston_plane -> bot`, а billboard piston markers переведены в debug-only режим и скрыты по умолчанию, чтобы их не путали с точками крепления.
- [ ] Принять R31X на живом Windows SEND bundle: подтвердить исчезновение drift именно у **surface mesh**, а не только у cross-bars, и проверить, что body/rod/piston теперь визуально соответствуют требованию «шток на рычаг, цилиндр к раме» на всех 4 углах и для Ц1/Ц2.



## R31Y addendum — 2026-03-24

- [x] Проверен свежий SEND bundle: `cyl*_top` действительно сидят на frame-side, а `cyl*_bot` — на arm-side (в текущей геометрии ближе всего к ветвям upper arm); проблема была не в экспортированных mount points, а в consumer-side visual path и в confusing debug markers.
- [x] Убрана визуальная путаница cylinders/pistons: большие жёлтые scatter-markers остаются только как debug-only слой, по умолчанию скрыты; Animator рисует прозрачный full housing shell + точный rod + точный piston plane вместо shrinking opaque body, который выглядел как ложное изменение длины корпуса.
- [x] Найден ещё один корень road-drift: lateral normal dense road surface не должен вычисляться из текущего viewport slice. В Car3D введён bundle-level cache world normals по полному `s_world/x/y`, а surface mesh теперь берёт lateral orientation из этого world cache, а не из локальной аппроксимации видимого окна.
- [x] Возвращён нормальный dock UX для live 3D GL: окно 3D снова docked по умолчанию, forced detach on startup убран, старый persisted detached-only layout gated новой `layout_version`, а safe external window используется только по явному действию `Разнести панели` / menu toggle.
- [x] Убран stale post-playback state: manual stop теперь принудительно делает final frame refresh и возвращает light/perf-gated panes в полноценную отрисовку сразу, без ожидания следующего внешнего события.
- [ ] Принять R31Y на живом Windows SEND bundle: отдельно проверить (1) исчезновение drift dense road surface при изменении размеров 3D окна; (2) понятную видимость piston plane внутри цилиндров; (3) реальную возможность detach/re-dock 3D окна; (4) отсутствие CPU/regression хвоста после завершения расчётов и после остановки playback.
- [ ] Следующий честный шаг по контракту: exporter должен начать отдавать **explicit external gland/body-end point** для каждого цилиндра. Пока этого ключа нет, Animator сознательно использует transparent housing shell как честный fallback и не притворяется, что знает точную внешнюю границу корпуса.


## R31Z addendum — 2026-03-24

- [x] Убран special external/reparent path для live 3D GL как основной пользовательский сценарий: 3D снова живёт через native dock/floating `QDockWidget`, а не через «безопасное отдельное окно».
- [x] Во время move/resize/layout change live 3D playback теперь автоматически ставится на паузу, обновление GL подавляется до стабилизации layout, затем playback продолжается с текущего кадра.
- [x] Из user-facing 3D сцены убраны point-sprite/GLScatter шары: contact markers переведены в line-crosses, а piston debug-balls не участвуют в обычной отрисовке.
- [x] Cylinder packaging в Animator стал читаемее: outer housing shell остаётся честной оболочкой, но внутри теперь отдельно видны exact chamber, exact rod, exact piston plane и piston ring — не только «просто цилиндры».
- [ ] Принять R31Z на живом Windows SEND bundle: native float/re-dock 3D при playback с авто-паузой, отсутствие `GLMesh/GLLine/GLScatter` warning-spam/AV-crash и отсутствие CPU tail после расчётов/stop playback.
- [ ] Если CPU tail не уйдёт вместе с GL error-spam/layout-fix, добавить отдельную post-calc instrumentation и принудительное завершение хвостовых redraw/update loops.


## R31AA addendum — 2026-03-25

- [x] Локализован реальный источник post-run idle CPU в Web UI: hidden/zero-size Streamlit iframes всё ещё считались "visible", потому что viewport-guard проверял только координаты `getBoundingClientRect()`, но не размер/`display:none`/`visibility:hidden`.
- [x] Во всех web follower-компонентах и встроенных HTML-виджетах idle-guard теперь считает iframe off-screen, если у него крошечный/нулевой rect, `clientWidth/clientHeight≈0` или CSS скрывает сам frame.
- [x] Для самых тяжёлых web-компонентов (`mech_anim`, `mech_car3d`, `pneumo_svg_flow`) введён single-flight scheduler: storage/focus/visibility wakeups больше не плодят параллельные `requestAnimationFrame`/`setTimeout` цепочки поверх уже запланированного loop.
- [x] Пауза/idle в браузерных follower-компонентах стала существенно реже будить CPU: visible idle poll поднят, а быстрый wake остаётся по `storage`/`focus`/`visibility`.
- [ ] Повторно принять R31AA на живом Windows SEND bundle: подтвердить, что web UI после detail-run действительно перестал держать холостую CPU-нагрузку и что скрытые табы/свернутые панели больше не продолжают жить как "видимые".
- [ ] Следующий измеримый шаг по browser acceptance: вынести в SEND-bundle явный browser-side trace/wakeup counters, чтобы post-run CPU хвост проверялся числами, а не только ощущением/Task Manager.


## R31AB addendum — 2026-03-25

- [x] Повторно прогрет контекст проекта с опорой на ABSOLUTE LAW + текущие TODO/Wishlist: следующий шаг по Web UI CPU сделан не вслепую, а как измеримый browser-side слой поверх R31AA.
- [x] Политика `single-flight scheduler + off-screen guard` расширена с трёх самых тяжёлых компонентов на **все** browser follower-компоненты с `requestAnimationFrame` / `setTimeout` loop-path (`corner_heatmap_live`, `minimap_live`, `road_profile_live`, `mech_anim_quad`, `mech_anim`, `mech_car3d`, `pneumo_svg_flow`, `playhead_ctrl`, `playhead_ctrl_unified`).
- [x] Каждый follower-компонент теперь публикует компактный browser perf snapshot в `localStorage` (`pneumo_perf_component::*`): wakeups, duplicate-guard hits, hidden/zero-size gating, loop kind, idle poll и render counters.
- [x] В `playhead_ctrl` добавлены browser perf overlay и JSON export, чтобы Windows acceptance по idle CPU можно было подтверждать числами, а не только Task Manager / «ощущением». 
- [x] Inline HTML widgets в `app.py` и `pneumo_ui_app.py` переведены на тот же single-flight/off-screen policy; wake-path больше не должен плодить параллельные `RAF/timeout` цепочки в hidden/paused состоянии.
- [ ] Принять R31AB на живом Windows SEND bundle: подтвердить, что post-run idle CPU действительно уходит, скрытые табы спят, а perf registry / JSON export дают стабильную картину wakeups и duplicate-guard suppression.
- [ ] Если после R31AB у Web UI всё ещё останется холостой CPU tail, следующий шаг — автоматом включать perf registry snapshot в diagnostics/SEND bundle, а не полагаться только на ручной JSON export.



## R31AC addendum — 2026-03-25

- [x] Проверен свежий `logs.zip` / `runs.zip` / latest SEND bundle R31AB: корень симптома «аниматор висит, дороги не видно» — не отсутствие `anim_latest` и не пустая дорога, а unhandled `TypeError` в `Car3DWidget._corner_is_front()` во время `load_npz -> _update_frame(0)`.
- [x] Подтверждено bundle-side: `anim_latest.npz`, `anim_latest.json` и `anim_latest_road_csv.csv` в пакете есть, pointer sync = OK, geometry acceptance = PASS; road assets были готовы, но первый кадр Animator падал раньше завершения отрисовки сцены.
- [x] Исправлен root cause в коде: `Car3DWidget._corner_is_front` снова оформлен как валидный helper (`@staticmethod`), поэтому вызов `self._corner_is_front(corner)` больше не валит Desktop Animator на первом кадре.
- [x] Добавлен regression test на сигнатуру/декоратор `_corner_is_front`, чтобы последующие cylinder/packaging-правки снова не сломали binding semantics.
- [ ] Принять R31AC на живом Windows SEND bundle: Desktop Animator должен открываться без `sys.excepthook`, дорога должна быть видима с первого кадра, а bundle больше не должен содержать `TypeError('Car3DWidget._corner_is_front() takes 1 positional argument but 2 were given')`.
- [ ] Browser idle CPU acceptance из R31AB остаётся открытым отдельным треком: этот проход сознательно не смешивал новый web/perf слой с ещё одной волной визуальных/cylinder правок.

## R31AD addendum — 2026-03-25

- [x] Исправлен новый first-frame crash в Desktop Animator: `Car3DWidget._circle_line_vertices` снова имеет валидную staticmethod-сигнатуру и больше не валит `load_npz -> _update_frame(0)` до первой отрисовки дороги.
- [x] Piston-ring polyline path сделан fail-soft: если построение кольца снова сломается, Animator скрывает именно ring-line и пишет exception в лог, но не роняет весь кадр и не маскирует road как «отсутствующую».
- [x] Дефолты редактора кольца синхронизированы с последним пользовательским setup из принятого ring-сценария: `ISO8608/E` на прямом/разгоне/торможении, `SINE` 50 мм / 1.5 м / φR=180° на повороте, `closure_policy=closed_c1_periodic`, `n_laps=1`.
- [x] Список сценариев/test suite теперь допускает состояние «ничего не выбрано»: на свежей сессии выбор очищается, selectbox показывает `(не выбрано)`, а карточка справа не открывается без явного выбора пользователя.
- [ ] Принять R31AD на живом Windows SEND bundle: Animator должен стартовать без `TypeError` по `_circle_line_vertices`, дорога должна быть видна с первого кадра, ring editor — открываться с новыми дефолтами, а список сценариев — начинаться без автоселекта.



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

- [x] Разобран архив `mhtml.zip` с чатами: выделены тематические кластеры, найдены точные дубликаты и подтверждён приоритетный слой требований (математика, код, физика, UI/GUI, CPU, прогрев контекста).
- [x] Найден и исправлен корень геометрического разрыва в solver/export: frame-mounted точки (`frame_corner`, inboard hardpoints, `cyl*_top`) теперь экспортируются через единый rigid-frame transform, а не как yaw-only XY + отдельный Z.
- [x] Найден и исправлен разрыв `шток → рычаг`: `cyl*_bot` теперь строится как интерполяция по фактической world-геометрии выбранной ветви рычага, а не через смешанный локальный XY/Z путь.
- [x] Введены новые diagnostics/self-checks/tests на геометрическую неразрывность: жёсткость frame-mounts относительно рамы, wheel/upright hardpoints относительно ступицы/колеса и attachment `cyl*_bot` к ветви рычага.
- [ ] Повторно принять на живом Windows SEND bundle уже после R31AH: точки крепления к раме не дрейфуют относительно рамы, точки к ступице/колесу не дрейфуют относительно wheel/upright, `cyl*_bot` остаётся на выбранной ветви рычага, а Animator HUD/self-check не показывает geometry continuity FAIL.
- [ ] Web UI CPU tail остаётся отдельным P0: следующая проверка должна идти уже не через паузы таймеров, а через browser-side trace/render-loop counters, чтобы доказать источник хвоста численно.


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
