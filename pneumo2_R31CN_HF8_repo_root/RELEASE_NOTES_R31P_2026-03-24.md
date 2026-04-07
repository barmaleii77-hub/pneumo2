# RELEASE NOTES — R31P (2026-03-24)

Этот шаг собирает небольшой, но честный cumulative patch поверх `R31O` уже по фактам из Windows manual SEND-bundle.

## Что исправлено

### 1) Desktop Animator: 3D GL dock больше не переводится в floating detached-mode

Файл: `pneumo_solver_ui/desktop_animator/app.py`

Что показал bundle:
- `anim_latest` usable, geometry acceptance PASS и сам SEND-bundle валиден;
- но при auto-detach / `Панели: разнести` 3D OpenGL dock переводился в floating window;
- в логах это воспроизводилось как повторяющиеся `OpenGL.error.GLError` внутри `pyqtgraph.opengl` и аварийный выход Desktop Animator с кодом `0xC0000409`.

Что теперь сделано:
- для GL-сборок `dock_3d` сохраняется docked при `enforce_detached_windows(...)`;
- detached/tiled режим по-прежнему применяется к боковым/вспомогательным панелям;
- startup warning уточнён: на GL build 3D остаётся docked ради стабильности.

Практический эффект:
- повторный auto-detach больше не должен валить рендер только из-за floating 3D окна;
- screen-aware tiled layout сохраняется для остальных панелей.

### 2) strict loglint: seq теперь проверяется по `session_id + pid`

Файл: `pneumo_solver_ui/tools/loglint.py`

Что показал bundle:
- parent UI и дочерний Desktop Animator писали в один session log;
- дочерний процесс начинал `seq` заново с 1;
- strict loglint помечал это как ложный `non-monotonic seq`, хотя это были разные процессы.

Что теперь сделано:
- ключ строгой seq-проверки стал pid-aware: `session_id|pid=...` при наличии pid.

Практический эффект:
- будущие SEND-bundle/health-report не должны получать ложный strict-loglint fail на нормальной multi-process записи.

## Что обновлено в проектной документации

- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- `TODO_WISHLIST_R31P_ADDENDUM_2026-03-24.md`

Там зафиксировано, что этим шагом закрыты:
- Windows floating-GL crash-path для detached layout;
- ложный strict-loglint seq fail для multi-process session logs.

И отдельно подтверждено, что всё ещё открыто:
- повторный ручной Windows acceptance уже на R31P;
- canonical `road_width_m` в export/meta;
- measured browser/Windows performance acceptance;
- solver-points completeness / cylinder packaging contract.

## Что проверено

- `python -m py_compile`:
  - `pneumo_solver_ui/desktop_animator/app.py`
  - `pneumo_solver_ui/tools/loglint.py`
  - `pneumo_solver_ui/release_info.py`
- pytest targeted slice:
  - `tests/test_desktop_animator_gl_float_suppression.py`
  - `tests/test_desktop_animator_startup_docked.py`
  - `tests/test_desktop_animator_dock_method_contract.py`
  - `tests/test_loglint_seq_pid_split.py`
  - `tests/test_release_info_default_release_sync.py`

## Release status

Это **не** заявление, что весь historical acceptance закрыт.
Это аккуратный patch-release, который: 
- превращает Windows manual bundle из “симптома падения” в конкретный regression fix;
- убирает ложный infra-fail в strict loglint;
- обновляет TODO/WISHLIST и release metadata под новый артефакт.
