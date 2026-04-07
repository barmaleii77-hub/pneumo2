# ВАЖНО: сначала прочитай контракт

1) `00_READ_FIRST__ABSOLUTE_LAW.md` — закон совместимости (никаких выдуманных параметров/алиасов).
2) `01_PARAMETER_REGISTRY.md` — где лежит реестр параметров.
3) `DATA_CONTRACT_UNIFIED_KEYS.md` — контракт экспорта NPZ/Animator.

---

# PneumoApp ETALON v6_80 (R114)

Этот архив — **эталонный релиз** для проверок UI/диагностики/оптимизации параметров.

## Быстрый старт (Windows)

1) Распакуй архив **в короткий путь без кириллицы**, например:

   ```
   C:\Work\PneumoApp_ETALON_v6_80_R114\
   ```

2) Запусти:

   - `START_PNEUMO_APP.cmd` (рекомендуется)
   - или `START_PNEUMO_APP.py` (если у тебя Python ассоциирован с *.py)

3) Первый запуск создаст виртуальное окружение `.venv` и поставит зависимости.
4) После старта Streamlit откроется в браузере (обычно `http://127.0.0.1:8505` (alt: `http://localhost:8505`)).

## Dev Bootstrap (локальный smoke)

Для воспроизводимого developer-прогона проект фиксирует Python `3.14.3`
через `.python-version` в git-корне и в папке приложения.

Из `pneumo2_R31CN_HF8_repo_root`:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -r pneumo_solver_ui\requirements_dev.txt
.\.venv\Scripts\python -m compileall -q pneumo_solver_ui tests app.py START_PNEUMO_APP.py
.\.venv\Scripts\python -c "from pathlib import Path; import pneumo_solver_ui.scheme_integrity as si; ok,msg=si.verify_scheme_integrity(Path('pneumo_solver_ui/PNEUMO_SCHEME.json'), Path('pneumo_solver_ui/scheme_fingerprint.json')); print('OK' if ok else 'FAIL', msg)"
.\.venv\Scripts\python -m pytest tests/test_release_info_default_release_sync.py tests/test_app_release_sync.py tests/test_root_requirements_runtime_ui_deps.py tests/test_phase1_repo_bootstrap.py -q
```

Для ручного UI-smoke:

```powershell
.\.venv\Scripts\python -m streamlit run app.py --server.headless true --server.port 8505
```

## Entrypoint Map

- `app.py` — canonical Streamlit shell for `START_PNEUMO_APP.*` and manual `streamlit run app.py`.
- `pneumo_solver_ui/pneumo_ui_app.py` — heavy home page rendered inside the canonical multipage shell.
- `pneumo_solver_ui/app.py` — legacy single-page package UI kept only for compatibility and regression guards; not the default launch target.

`START_PNEUMO_APP.py` и `START_PNEUMO_APP.cmd` по-прежнему поддерживают
shared-venv сценарий. Локальная `.venv` нужна именно для повторяемого
developer smoke и быстрой диагностики состояния репозитория.

## Пост-билд тестирование (обязательный чек‑лист перед отправкой)

### Автоматическое (CLI)

Из корня приложения:

```bat
python -m compileall -q .
python -c "from pathlib import Path; import pneumo_solver_ui.scheme_integrity as si; ok,msg=si.verify_scheme_integrity(Path('pneumo_solver_ui/PNEUMO_SCHEME.json'), Path('pneumo_solver_ui/scheme_fingerprint.json')); print('OK' if ok else 'FAIL', msg)"
python -m pneumo_solver_ui.tools.selfcheck_suite --level standard --out_dir selfcheck_out

REM (рекомендуется) сбор диагностического ZIP + валидация (CLI)
python -c "import os; from pathlib import Path; os.environ['PNEUMO_BUNDLE_RUN_SELFCHECK']='0'; from pneumo_solver_ui.send_bundle import make_send_bundle; p=make_send_bundle(repo_root=Path('.'), out_dir=Path('send_bundles'), keep_last_n=1, max_file_mb=20, include_workspace_osc=False, tag='POSTBUILD'); print('BUNDLE', p)"
python -c "from pathlib import Path; import sys; from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle; p=max(Path('send_bundles').glob('SEND_*POSTBUILD_bundle.zip')); r=validate_send_bundle(p); print('OK' if r.ok else 'FAIL'); sys.exit(0 if r.ok else 2)"
```

### Ручное (UI smoke)

1) Убедись, что **в сайдбаре нет двух навигаций** (никаких «страниц по два раза»).
2) **Главная** открывается без ошибок.
3) Страница **Модель → Схема → Целостность схемы** показывает `OK` (без "fingerprint mismatch").
4) В сайдбаре **Диагностика → Собрать ZIP** создаёт архив, и `validation_report.md` внутри без `ERROR`.

---

Ниже — историческое README (механика/релизы R4x). Для ETALON v6_80 ориентируйся на разделы выше.

# Mechanika Pnevmatika R49 (base Pnevmatika R47)

Единое приложение (Streamlit) для моделирования/анализа пневмоподвески с расширенной **механикой подвески** (кинематика double-wishbone в приближении, раздельные ходы Ц1/Ц2 и перед/зад, правильный пересчёт осевых сил в вертикальные через motion ratio).

## Что нового в Mechanika R49 (механика/кинематика)

1) **Новая модель v9:** `pneumo_solver_ui/model_pneumo_v9_mech_doublewishbone.py`
   - режимы кинематики: `legacy` (как в базе) и `dw2d` (по умолчанию)
   - раздельные ходы: `ход_штока_Ц1_перед_м/зад_м`, `ход_штока_Ц2_перед_м/зад_м`
   - 12 параметров креплений цилиндров (верх Y/Z, низ — доля рычага) по 4 группам (Ц1/Ц2 × перед/зад)
   - силы цилиндров/пружины считаются осевыми и переводятся в вертикаль через `ds/dδ` (виртуальная работа)

2) **UI по умолчанию** открывает v9-модель (можно выбрать любую вручную).
3) Добавлены диагностические сигналы в логи: ходы Ц2, motion ratio Ц1/Ц2, длины цилиндров.

Подробности: `docs/RELEASE_NOTES_R49_MECHANIKA.md`, `docs/MECH_DW2D_KINEMATICS_R49.md`.

---

# Pnevmatika R47 (base Obobshchenie R43)

Единое приложение (Streamlit) для моделирования/анализа пневмоподвески: расчёт baseline, детальные логи по тестам, графики и анимация (2D/3D).

> Релиз **R43** — производительность и стабильность анимации/playhead: троттлинг localStorage, явное разделение "FPS (браузер)" vs "синхронизация (сервер)" + авто‑троттлинг fallback‑refresh, чтобы не зависало при 4+ FPS/Hz.

> Релиз **R47** — добавлена библиотека реальных глушителей Camozzi (Series 29: 2901/2903/2921/2931/2928/2929) в паспорт компонентов с пересчётом Qn(6bar→ATM) → ISO 6358 C. Design Advisor теперь распознаёт эти коды и может предлагать апгрейд глушителя как «железного» узкого места.

> Релиз **R46** — уточнение физики выхлопа Р3 (раздельное моделирование SCO→глушитель 2905), расширенный паспорт глушителей и улучшенный Design Advisor: теперь он различает «не хватает прохода даже на максимуме» и «нужно просто открыть/увеличить коэффициент прохода», и предлагает замены по паспорту.


> Релиз **R45** — повышение физической достоверности: ISO 6358 для регуляторов/клапанов сброса, заполнение паспорта (MC/VMR/2905) без пустых полей, и новый модуль **Design Advisor** для автоматического выявления "узких мест" сети.


## Что нового в R47

### 1) Паспорт глушителей: добавлены реальные модели Camozzi Series 29

- ✅ В `pneumo_solver_ui/component_passport.json` добавлены отдельные позиции глушителей (как кандидаты замен): **2901/2903/2921/2931/2928/2929**.
- ✅ Для них записан паспортный расход `Qn_Nl_min_at_6bar_to_atm` (точка каталога) и пересчитан эквивалент ISO 6358 `C`.
- ✅ Важно: для глушителей каталог задаёт Q при 6 bar(g) → атмосфера, а не при Δp=1 bar (это отражено в meta/notes и в полях `test_conditions`).

### 2) Design Advisor: распознаёт коды новых глушителей

- ✅ Если в ветке выхлопа «узкое место» именно глушитель, советник теперь может предложить замену на 2921/2931/2928 и т.п. (по паспорту), а не только «крутить коэффициент».

Подробный ридми: `README_R47_DETAILED.md`.

---

## Что нового в R46

### 1) Раздельное моделирование выхлопа: **SCO → глушитель 2905 → атмосфера**

- ✅ Добавлен параметр `разделить_SCO_и_глушитель_2905` (по умолчанию **true**) — вместо одного «комбо‑элемента» `SCO ...+2905` модель строит **2 последовательных ребра**:
  1) `дроссель_выхлоп_*` (SCO)
  2) `глушитель_выхлоп_*` (2905)
- ✅ Это делает энергоаудит и выявление «узких мест» честнее: теперь видно отдельно, где теряем энергию (дроссель или глушитель).
- ✅ Добавлен параметр малого мёртвого объёма между элементами: `объём_узла_между_дросселем_и_глушителем`.

### 2) Паспорт глушителей: добавлены 2905 **по резьбам**

- ✅ В `component_passport.json` добавлены отдельные позиции:
  - `2905 1/8`
  - `2905 1/4`
- ✅ Для них заполнены оценочные параметры ISO6358 (`C,b,m,Δpc`) и точка `Qn_Nl_min_at_6bar_to_atm`.

### 3) Design Advisor стал «умнее» по регулировкам и заменам

- ✅ В таблицу добавлены поля `C_min`, `C_max`, `margin_C_max` и `sizing_hint`.
- ✅ Если при текущем открытии `margin_C < 1`, но `margin_C_max >= 1` — советник пишет: **«можно просто открыть/увеличить коэффициент прохода»**.
- ✅ Если `margin_C_max < 1` — советник предлагает **кандидаты замены** по паспорту (ближайшие типоразмеры с большим `C`).

Подробный ридми: `README_R46_DETAILED.md`.

---

## Что нового в R45 (история)

### 1) ISO 6358 для регуляторов и предохранительных (самое важное)

- ✅ Типы рёбер `reg_after` (регулятор "после себя") и `relief` (клапан сброса/регулятор "до себя") теперь **поддерживают ISO 6358** (параметры `C,b,m`) в режиме `модель_пассивного_расхода = iso6358`.
- ✅ До этого эти элементы всегда считались как простое отверстие (`orifice`) и игнорировали паспортные `C,b,m`, что делало сеть заметно менее реалистичной при больших перепадах.

### 2) Паспорт компонентов: MC/VMR/глушитель 2905 без `null`

- ✅ В `pneumo_solver_ui/component_passport.json` заполнены отсутствующие паспортные поля для:
  - **MC104-R00 (Series MC)**
  - **VMR 1/8-B10**
  - **2905 (Series 29 silencing bush)**
- ✅ Значения помечены как **оценочные**, чтобы их можно было потом заменить на снятые с даташита/стенда.

### 3) Настраиваемые сопротивления для пассивной адаптивности

- ✅ Добавлен параметр `коэф_прохода_сбор_в_магистраль` — масштабирует ветви **N_* → магистраль** (ваш "инерционный тормоз" для крена/тангажа).
- ✅ Добавлен параметр `коэф_прохода_заряд_аккумулятора` — позволяет отдельно регулировать скорость зарядки аккумулятора (ветка Р3 → аккумулятор) без изменения остальных режимов.

### 4) Design Advisor (авто-подсказки инженеру)

- ✅ Добавлен модуль `pneumo_solver_ui/design_advisor.py` и страница Streamlit `pages/03_Design_Advisor.py`.
- Он строит таблицу по рёбрам: пики расхода, пики Δp, энергия дросселирования, оценка требуемого `C_req` и запас `margin_C`.

Подробный ридми: `README_R46_DETAILED.md`.

## Что нового в R43

### Анимация / Playhead

- ✅ Добавлен троттлинг записи в `localStorage` в компоненте playhead (`components/playhead_ctrl`): по умолчанию 30 FPS (настраивается), что резко снижает нагрузку браузера и убирает "2 FPS"/зависания.
- ✅ В UI добавлен явный контрол **"FPS (браузер)"** и переименована серверная синхронизация в **"Синхронизация (сервер, тяжело)"** + предупреждение при значениях >2 Hz.
- ✅ В fallback-анимации добавлен авто‑троттлинг `st_autorefresh`: если скрипт не успевает, интервал автоматически увеличивается вместо накопления rerun'ов и зависаний.

### Документация

- ✅ Обновлены release notes и добавлен патч перехода R43_from_R42.

Подробно: `docs/RELEASE_NOTES_R43.md`.

## Быстрый старт (Windows)

1) **Установка зависимостей**
- Запусти `pneumo_solver_ui/INSTALL_DEPENDENCIES_WINDOWS.bat`
- Дождись окончания установки

2) **Запуск**
- Запусти `pneumo_solver_ui/RUN_PNEUMO_UI_WINDOWS.bat`
- Откроется Streamlit (обычно `http://127.0.0.1:8505` (alt: `http://localhost:8505`))

> Важно: закрытие вкладки браузера **не останавливает** сервер. Остановка — `Ctrl+C` в окне консоли.

## Структура проекта

- `pneumo_solver_ui/` — основной пакет приложения  
  - `pneumo_ui_app.py` — главный Streamlit‑скрипт (единая сборка)
  - `model_pneumo_*.py` — матмодель/солвер (несколько вариантов, выбран лучший)
  - `components/` — кастомные Streamlit‑компоненты (playhead, 2D/3D анимация)
  - `tools/` — утилиты диагностики, сборки артефактов, извлечения требований из контекста
  - `default_base.json`, `default_suite.json`, `mapping_ui.json` — дефолтные данные/маппинг
- `docs/` — подробная документация (что сделано, где лежит, TODO, требования, источники контекста)
- `diffs/` — патчи/диффы между релизами (R40 от R39 + исторические R39 от R38 и R35)
- `.venv/` — виртуальное окружение (создаётся на машине пользователя скриптом установки)

## Главное в R40

- Добавлены в проект ваши актуальные требования/бэклог: `docs/context/WISHLIST.md` и `docs/WISHLIST.json` (см. `docs/12_Wishlist.md`).
- Диагностика усилена: добавлены **static checks** (compileall + ruff F821) в `tools/run_full_diagnostics.py`.
- В зависимости добавлен `requests` (нужен для UI-smoke и HTTP-проверок в диагностике).
- Обновлены bat-скрипты установки/запуска и версия в UI (APP_RELEASE=R40).

## Главное в R39

### 1) Канонический ключ кэша детального прогона
Введён единый генератор ключа `make_detail_cache_key(...)` и он используется **везде**:
- одиночный детальный прогон,
- прогон всех тестов,
- экспорт NPZ/ZIP,
- кэш для анимации.

Это устраняет «промахи кэша» и повторные тяжёлые пересчёты из‑за разных форматов ключей.

### 2) Анимация: дорога без подрисовки физики
Если в `df_main` нет колонок дороги `дорога_*_м`, анимация **не придумывает физику**.  
Вместо этого профиль дороги восстанавливается из входного описания теста (через `road_func` из suite), чтобы:
- дорога в визуализации соответствовала реальному входу теста,
- динамика кузова/колёс всё равно бралась только из результата расчёта.

### 3) Дифы и патчи в комплекте
Добавлена папка `diffs/`:
- `R39_from_R38.patch` — компактный патч только изменений R39 поверх R38
- `R39_from_R35.patch` — полный патч от R35 до R39 (большой файл)

## Документация

Ориентиры по docs (начать отсюда):
- `docs/01_RequirementsFromContext.md` — требования, извлечённые из контекста (включая TODO)
- `docs/PROJECT_SOURCES.md` — локальные и внешние источники проекта, включая Google Drive папки с контекстом
- `docs/06_CalibrationAndAutopilot.md` — что такое калибровка и autopilot, как задумано
- `docs/02_LogAnalysis.md` и `docs/03_Architecture.md` — логи и архитектура

## Диагностика

- Из UI можно собрать диагностический ZIP (кнопка/раздел “Диагностика”).
- Для прогонов тестов есть CLI/GUI скрипты в `pneumo_solver_ui/tools/`:
  - `run_full_diagnostics.py`
  - `run_full_diagnostics_gui.py`

## Известные ограничения

- Если включить синхронизацию проигрывания с сервером (playhead → Python), частые rerun’ы Streamlit могут быть тяжёлыми на слабых машинах. Для «плавного Play» рекомендуется держать sync‑Hz = 0 и использовать проигрывание на фронтенде.
- Ряд требований (момент/тормоз между осями, уточнения по дифференту/крену, сопоставление с реальными замерами) зафиксирован в TODO и требует отдельной итерации матмодели.
