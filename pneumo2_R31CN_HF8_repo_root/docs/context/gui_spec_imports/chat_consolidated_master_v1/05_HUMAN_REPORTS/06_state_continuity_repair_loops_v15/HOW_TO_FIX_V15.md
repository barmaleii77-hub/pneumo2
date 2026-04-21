# Как поправить по канону V15

1. У каждого проблемного состояния должен быть один основной banner/marker и один основной repair-action.
2. Все repair-action должны вести в upstream workspace напрямую:
   - stale suite -> Редактор кольца;
   - baseline mismatch -> Baseline;
   - contract mismatch -> Optimization;
   - truth degraded -> Analysis/Animator provenance;
   - stale bundle -> Diagnostics.
3. При возврате обязательно восстанавливать:
   - selection,
   - filter,
   - scroll,
   - selected run/segment/row,
   - compare picks.
4. Все must-see состояния выводить в явных summary cards / mode chips / badges, а не только в тултипах.
5. Для каждой async операции давать две формы обратной связи:
   - immediate feedback,
   - persistent status marker.
