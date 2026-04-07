# RELEASE NOTES — R31Q (2026-03-24)

Этот шаг исправляет мою ошибку в R31P: там был workaround, который удерживал 3D docked и тем самым отключал требуемый detached 3D режим. В R31Q сделан другой путь: live GL больше не использует floating `QDockWidget`, а работает в отдельном top-level окне.

## Что исправлено

### 1) Desktop Animator: live 3D GL теперь отдельное top-level окно, а не floating `QDockWidget`

Файл: `pneumo_solver_ui/desktop_animator/app.py`

Что было неправильно в R31P:
- crash-path был локализован верно, но исправление было неполным;
- 3D dock просто удерживался в docked-mode;
- это нарушало требование пользователя о detached/movable/resizable 3D окне.

Что сделано в R31Q:
- добавлен `ExternalPanelWindow` для панелей, которые нельзя безопасно пускать через floating `QDockWidget`;
- live 3D GL-panel (`dock_3d`) регистрируется как отдельное top-level окно уже на этапе установки layout;
- auto-retile больше позиционирует это отдельное окно, а не вызывает `dock.setFloating(True)` на GL viewport;
- у внешнего 3D окна есть menu toggle, move/resize, close/reopen и persistence состояния через `QSettings`.

Практический эффект:
- требуемый detached 3D режим возвращён;
- root crash-path из bundle (`dock.setFloating(True)` → GL reparent → `GLError`/`0xC0000409`) больше не вызывается этим layout path;
- 3D окно остаётся отдельным, а не «прибитым» к main window.

### 2) Infra/status: скорректирован project memory слой

Файлы:
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- `TODO_WISHLIST_R31Q_ADDENDUM_2026-03-24.md`

Что сделано:
- R31P помечен как workaround, superseded by R31Q;
- backlog разделён на уже сделанный layout-fix и ещё не закрытый Windows acceptance.

### 3) strict loglint pid-aware fix сохранён

Файл: `pneumo_solver_ui/tools/loglint.py`

Из R31P сохранён полезный infra-fix: strict seq validation остаётся pid-aware (`session_id + pid`) и больше не даёт ложный `non-monotonic seq` на multi-process session logs.

## Что проверено

- `python -m py_compile`:
  - `pneumo_solver_ui/desktop_animator/app.py`
  - `pneumo_solver_ui/tools/loglint.py`
  - `pneumo_solver_ui/release_info.py`
- pytest targeted slice:
  - `tests/test_desktop_animator_gl_float_suppression.py`
  - `tests/test_desktop_animator_startup_docked.py`
  - `tests/test_desktop_animator_external_panel_state.py`
  - `tests/test_desktop_animator_dock_method_contract.py`
  - `tests/test_loglint_seq_pid_split.py`
  - `tests/test_release_info_default_release_sync.py`
  - `tests/test_app_release_sync.py`

## Честный статус

Это всё ещё **не Windows acceptance proof**. В этой среде у меня нет живого PySide6/OpenGL Windows runtime, поэтому R31Q — это кодовый релиз с root-cause-oriented layout fix и статической проверкой, а не заявка о завершённом Windows retest.
