# Проверка полноты и достаточности v32

Источник: `C:/Users/Admin/Downloads/pneumo_codex_tz_spec_connector_reconciled_v32.zip`.

Дата проверки: `2026-04-17`.

## Итог

Архив v32 достаточен как:

- self-contained слой ТЗ и GUI-spec для планирования работ;
- source-authority и reading-order слой;
- workspace/handoff/dependency contract layer;
- acceptance/release-gate/evidence planning layer;
- основа для параллельной декомпозиции работ по чатам.

Архив v32 не достаточен как:

- доказательство runtime closure;
- доказательство фактической работоспособности Windows GUI;
- замена живых tests/contracts в репозитории;
- основание считать закрытыми open gaps без новых runtime artifacts.

Коротко: v32 хорош как карта, контракт и acceptance план. Для закрытия релиза
нужны живые implementation patches, runtime evidence, bundle proof и тесты.

## Structural Checks

Проверено локальным чтением ZIP:

- ZIP содержит `325` файлов.
- `EXEC_SUMMARY.json` заявляет `files_total = 325`.
- `PACKAGE_MANIFEST.json` заявляет `file_count = 325`.
- `PACKAGE_MANIFEST.json` содержит `325` SHA256 entries.
- Все `324` non-manifest file checksums совпали с manifest.
- `PACKAGE_INDEX.csv` содержит `324` строки и покрывает все файлы, кроме самого
  `PACKAGE_INDEX.csv`.
- Обязательные top-level files присутствуют: `README_PROVENANCE.md`,
  `TECHNICAL_SPECIFICATION.md`, `GUI_SPEC.yaml`, `SOURCE_AUTHORITY_MATRIX.csv`,
  `REQUIREMENTS_MATRIX.csv`, `ACCEPTANCE_MATRIX.csv`,
  `WORKSPACE_CONTRACT_MATRIX.csv`, `WORKSPACE_DEPENDENCY_MATRIX.csv`,
  `WORKSPACE_HANDOFF_MATRIX.csv`, `ACCEPTANCE_PLAYBOOK_INDEX.csv`,
  `RELEASE_GATE_HARDENING_MATRIX.csv`, `RUNTIME_ARTIFACT_SCHEMA.yaml`,
  `EVIDENCE_REQUIRED_BY_GATE.csv`, `GAP_TO_EVIDENCE_ACTION_MAP.csv`,
  `OPEN_GAPS_REGISTER.csv`, `NEXT_STEP_DELTA_V32.md`.

## Coverage Checks

Покрытие ключевых матриц:

- `REQUIREMENTS_MATRIX.csv`: `45` rows.
- `ACCEPTANCE_MATRIX.csv`: `45` rows.
- Все `REQ_ID` из requirements имеют acceptance row.
- Нет acceptance rows без соответствующего `REQ_ID`.
- `WORKSPACE_CONTRACT_MATRIX.csv`: `12` workspaces.
- `WORKSPACE_DEPENDENCY_MATRIX.csv`: `12` dependency rows.
- `WORKSPACE_HANDOFF_MATRIX.csv`: `10` handoff rows.
- `SCREEN_CATALOG.csv`: `61` screens.
- `WINDOW_CATALOG.csv`: `12` windows.
- `UI_ELEMENT_CATALOG.csv`: `704` UI elements.
- `PARAMETER_CATALOG.csv`: `488` parameters.
- `ACCEPTANCE_PLAYBOOK_INDEX.csv`: `8` playbooks.
- `RELEASE_GATE_HARDENING_MATRIX.csv`: `20` hardening rows.
- `EVIDENCE_REQUIRED_BY_GATE.csv`: `16` evidence rows.
- `OPEN_GAPS_REGISTER.csv`: `6` open gaps.
- `GAP_TO_EVIDENCE_ACTION_MAP.csv`: `6` gap-to-action rows.

## Достаточно для реализации

v32 достаточно, чтобы параллельные чаты могли:

- понимать source priority и conflict policy;
- не терять web -> desktop parity;
- держать `WS-INPUTS` и `WS-RING` единственными editable source-of-truth;
- передавать frozen artifacts по handoff IDs `HO-001...HO-010`;
- проектировать UI по 12 workspaces без создания монолитов;
- привязывать работу к acceptance playbooks `PB-001...PB-008`;
- не объявлять closure без evidence из `EVIDENCE_REQUIRED_BY_GATE.csv`;
- различать current/historical/stale context;
- выводить truthful graphics states: `solver_confirmed`,
  `source_data_confirmed`, `approximate_inferred_with_warning`, `unavailable`;
- планировать SEND bundle и diagnostics evidence как release-blocking surface.

## Недостаточно для закрытия runtime

v32 прямо сохраняет runtime gaps:

- `OG-001`: hardpoints / solver_points truth closure;
- `OG-002`: cylinder packaging passport;
- `OG-003`: measured browser/runtime performance trace;
- `OG-004`: viewport gating;
- `OG-005`: Windows visual acceptance;
- `OG-006`: runtime proof границ imported layers.

`NEXT_STEP_DELTA_V32.md` указывает, что следующий правильный шаг после v32
должен опираться на живые runtime artifacts, а не на новый summary.

## Issues And Caveats

### ISSUE-V32-001: self-checksum manifest mismatch

`PACKAGE_MANIFEST.json` содержит SHA256 для самого себя, но фактический SHA256
локального `PACKAGE_MANIFEST.json` отличается.

Оценка:

- не ломает чтение package;
- не ломает остальные checksum checks;
- означает, что self-hash нельзя использовать как строгий integrity proof;
- для строгой supply-chain проверки нужен внешний digest всего ZIP или manifest
  без self-referential checksum.

### ISSUE-V32-002: `CODEx_CONSUMPTION_ORDER.md` labeled V30

Файл `CODEx_CONSUMPTION_ORDER.md` имеет заголовок `CODEX CONSUMPTION ORDER V30`.
При этом `EXEC_SUMMARY.json` содержит v32 primary reading order.

Оценка:

- не блокирует работу;
- создает риск, что будущий читатель возьмет старый V30 order вместо V32;
- в KB приоритет читать v32 order из `EXEC_SUMMARY.json` и текущего
  [README.md](./README.md).

### ISSUE-V32-003: PB-008 indexed without dedicated markdown playbook

`ACCEPTANCE_PLAYBOOK_INDEX.csv` содержит `PB-008` про
current / historical / stale provenance surfacing. Dedicated markdown
`PLAYBOOK_CURRENT_HISTORICAL_STALE...md` отсутствует.

Оценка:

- не блокирует работу, потому что PB-008 ссылается на
  `CURRENT_HISTORICAL_STALE_POLICY.csv`, `PROVENANCE_FIELDS_CATALOG.csv` и
  `PLAYBOOK_OBJECTIVE_CONTRACT.md`;
- для удобства будущего CODEX-чтения можно позже добавить отдельный PB-008
  markdown digest в repo KB.

### ISSUE-V32-004: package-level contract is not live repo proof

В `README_PROVENANCE.md` явно сказано, что пакет не объявляет закрытыми
producer-side truth, cylinder packaging, measured performance acceptance,
Windows visual acceptance и runtime P0 closure.

Оценка:

- это правильное ограничение, а не ошибка;
- все release/acceptance claims должны подтверждаться tests, runtime artifacts
  и SEND bundle evidence из текущего репозитория.

## Решение по использованию

Использовать v32 как активный detailed reference для:

- декомпозиции работ;
- prompt-ов для параллельных чатов;
- проверки source-of-truth границ;
- acceptance/release-gate planning;
- gap-to-evidence planning.

Не использовать v32 как:

- доказательство готовности runtime;
- разрешение на alias/remap;
- источник новых параметров без registry/data-contract update;
- замену живых тестов и фактического кода.

## Next Actions

- Для ускорения разработки использовать
  [PARALLEL_CHAT_WORKSTREAMS.md](./PARALLEL_CHAT_WORKSTREAMS.md).
- Для runtime closure запускать отдельные workstreams по `OG-001...OG-006`.
- После появления живых artifacts обновить KB не новым summary, а evidence note:
  какой artifact, какой gate, какой test, какой bundle proof.
