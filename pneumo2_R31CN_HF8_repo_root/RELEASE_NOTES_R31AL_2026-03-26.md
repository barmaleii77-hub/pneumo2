# RELEASE NOTES R31AL (2026-03-26)

## Что исправлено

### 1. Desktop Animator playback переведён на display-rate playhead
- playback больше не использует старую схему source-frame chasing с 4 ms service timer на `x1.0`;
- теперь Animator двигает **continuous-time playhead** и выбирает ближайший кадр к текущему времени проигрывания;
- это должно вернуть реальное влияние speed selector и уменьшить рваность, когда GUI thread под нагрузкой не успевает показывать каждый source frame.

### 2. Auxiliary panes перестали конкурировать с live 3D на равных
- fast-group оставлен только для HUD;
- `front/rear/left/right` и остальная периферия переведены в slow-group;
- бюджеты auxiliary pane FPS дополнительно ужесточены, а порог many-visible panes опущен.

### 3. Добит Web idle path там, где прежние попытки били не туда
- follower/embedded widgets больше не должны держать старый `__nextIdleMs(60000, 180000, 300000)` timeout-polling;
- в idle loops теперь останавливаются полностью и просыпаются в основном по `storage/focus/visibility/scroll/resize`.

### 4. Цилиндры стали читаемее
- actuator geometry переведена на **capped cylinders** с торцевыми стенками;
- внешний корпус теперь рисуется гранями, а не почти только рёбрами;
- внутренняя камера ослаблена, чтобы не выглядеть как «второй цилиндр внутри сверху».

## Почему это понадобилось
Свежий bundle уже показывал, что после R31AK `anim_latest` стал достаточно плотным для playback. Значит bottleneck сместился: проблема была уже не в нехватке кадров, а в самой модели работы Animator — слишком частом GUI timer path, source-frame chasing, конкуренции со вспомогательными окнами и незавершённой остановке browser idle loops.

## Что сознательно НЕ объявляется закрытым
- финальная Windows acceptance для post-run Web UI CPU tail;
- окончательная проверка гладкости `speed=1.0` на живом SEND bundle;
- возможная необходимость полного recreate GL viewport/context, если pause-only layout policy всё ещё окажется недостаточной на реальном Windows стеке.
