# Как поправить по V16

1. Всё, что влияет на interpretation результата, поднять хотя бы в `top strip`, `summary card` или `message bar`.
2. Не отправлять пользователя в inspector за ответом на вопрос “что сейчас активно?”.
3. Для каждого workspace определить 3–5 обязательных первых смыслов и проверить, что они читаются без help.
4. Все `stale / mismatch / degraded` состояния делать banner-first, а не log-first.
5. В Inputs и Ring обязательно показывать **следствие действия**, а не только факт изменения поля.
6. В Optimization держать objective stack, hard gate и stage/gate reasons в центре текущего экрана.
7. В Animator truth-state и режим цилиндров делать крупнее эстетики viewport.
8. В Diagnostics держать одну primary action и только потом secondary actions.
