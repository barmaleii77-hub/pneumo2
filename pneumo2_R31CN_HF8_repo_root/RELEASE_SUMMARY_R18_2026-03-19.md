# R18 — краткая сводка

База: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R17_2026-03-19`

Главные исправления:
1. launcher dependency gate hardened
2. broken shared venv auto-recreate
3. hard fail on missing mandatory imports after install
4. windows-clean repack with short paths

Ожидаемый результат:
- архив распаковывается без ошибок из-за длинных путей;
- лаунчер не считает повреждённое окружение "здоровым";
- вместо немого падения пользователь получает явное сообщение и логи.
