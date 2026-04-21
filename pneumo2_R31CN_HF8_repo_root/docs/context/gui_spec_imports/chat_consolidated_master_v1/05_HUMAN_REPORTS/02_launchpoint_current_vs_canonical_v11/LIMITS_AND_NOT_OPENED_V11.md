# Честные границы и нераскрытые current-окна

В этом pass я не делаю вид, что знаю current internal UX там, где окно подтверждено только как launchpoint.

Статусы:
- `GUI диагностики` — launchpoint_only + subsystem_known_window_not_opened
- `Compare Viewer` — launchpoint_only
- `Редактор исходных данных` — launchpoint_only
- `Центр тестов` — launchpoint_only

Что это значит:
- точки входа подтверждены;
- canonical role можно определить;
- но фактический первый экран current не считается живо изученным.
