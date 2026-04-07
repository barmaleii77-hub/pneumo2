# RELEASE NOTES — R10 — 2026-03-17

## Что исправлено
- Ring scenario editor: убраны прямые записи в `st.session_state[...]` для уже созданных widget keys.
- Ring scenario editor: исправлен runtime NameError в warning для невалидного `drive_mode` (`idx+1` вместо свободного `i`).
- Page-exception diagnostics: `_page_runner.py` теперь пытается сразу положить auto-saved SEND bundle в буфер обмена.
- Рядом с auto-saved bundle пишется `latest_send_bundle_clipboard_status.json`.
- Повторно подтверждены контракты аниматора: ABS basis, канонический режим `колесо_координата`, strict `meta.geometry` consumers.

## Что проверено
- `python -m compileall -q pneumo_solver_ui` → OK
- `pytest` targeted → 33 passed
- `python -m pneumo_solver_ui.tools.selfcheck_suite --level standard` → RC=0

## Живые симптомы, закрытые этим релизом
1. `Ошибка в редакторе сценариев: name 'spec' is not defined` / Streamlit page exception.
2. `лаунчер не копирует диагностику в буфер` для auto page-exception SEND bundle.
3. Повторная проверка координат/осей колёс и рамы в аниматоре через headless contract tests.
