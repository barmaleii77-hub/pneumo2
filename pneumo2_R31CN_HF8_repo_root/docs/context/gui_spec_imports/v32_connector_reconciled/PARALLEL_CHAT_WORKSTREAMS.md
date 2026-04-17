# Параллельные чаты работ по v32

Этот документ раскладывает дальнейшую работу по проекту на независимые
workstreams для параллельной разработки разными чатами.

Основа разбиения:

- `pneumo_codex_tz_spec_connector_reconciled_v32.zip`;
- [README.md](./README.md) текущего v32 digest;
- [docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../../../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md);
- [docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../../../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md);
- `WORKSPACE_CONTRACT_MATRIX.csv`, `WORKSPACE_DEPENDENCY_MATRIX.csv`,
  `WORKSPACE_HANDOFF_MATRIX.csv`, `ACCEPTANCE_PLAYBOOK_INDEX.csv`,
  `RELEASE_GATE_HARDENING_MATRIX.csv`, `GAP_TO_EVIDENCE_ACTION_MAP.csv`
  внутри архива v32.

## Общий протокол для всех чатов

- Сначала читать absolute law, parameter registry, unified data contract,
  `17`, `18`, этот v32 digest и только потом свой workstream.
- Не делать web новым target. Web можно использовать только как parity/reference
  слой до полного переноса функций в desktop GUI.
- Не дублировать `Desktop Animator`, `Compare Viewer` и `Desktop Mnemo` внутри
  других окон; другие workspaces открывают их или передают им frozen context.
- Работать только в owned scope своего чата. Если нужен чужой файл, сначала
  оформить handoff/contract note или отдельный маленький PR-совместимый патч.
- Не заводить alias-слои, shadow keys и silent remap. Если нужен новый ключ,
  обновлять registry/data contract и тесты.
- Любой long-running action должен иметь progress/status, а diagnostics
  evidence должен быть собираемым в SEND bundle.
- Любой current/historical/stale mismatch должен быть видимым пользователю.
- Если появляются новые хотелки или планы, добавлять их в KB через
  `knowledge_base_sync`.
- Перед завершением чата запускать узкие тесты своего домена и проверять
  отсутствие mojibake в измененных документах.

## Матрица потоков

| ID | Название чата | Основной v32 scope | Owned files / modules | Не трогать без согласования |
| --- | --- | --- | --- | --- |
| V32-01 | Кабина проекта и главное окно | `WS-SHELL`, `WS-PROJECT`, `PB-005` | `desktop_shell/`, `desktop_qt_shell/`, `desktop_spec_shell/`, `desktop_ui_core.py`, `desktop_ui_help.py`, launchers `START_DESKTOP_*` | domain logic inputs/ring/optimizer/animator/mnemo |
| V32-02 | Исходные данные и визуальные двойники | `WS-INPUTS`, `HO-002`, `HO-003` | `desktop_input_model.py`, `desktop_input_graphics.py`, input panels/tests, input snapshot validation | solver/export truth, scenario geometry, optimizer internals |
| V32-03 | Кольцевой сценарий и дорожный маршрут | `WS-RING`, `HO-004`, `PB-003`, `GAP-005` | `desktop_ring_editor_model.py`, `desktop_ring_editor_panels.py`, `desktop_ring_editor_runtime.py`, `scenario_ring.py`, `scenario_generator.py`, `ring_visuals.py` | suite/baseline/optimization ownership of scenario copies |
| V32-04 | Настройка расчета и набор испытаний | `WS-SUITE`, `HO-005` | `desktop_run_setup_model.py`, `desktop_run_setup_runtime.py`, `default_suite*.json`, `suite_contract_migration.py`, `ui_suite_*` | ring source-of-truth, baseline active contract |
| V32-05 | Базовый прогон и active baseline | `WS-BASELINE`, `HO-006`, `PB-007` | `optimization_baseline_source.py`, `optimization_baseline_source_ui.py`, baseline selection/history helpers, run artifact baseline refs | objective optimizer loop, compare viewer rendering |
| V32-06 | Оптимизатор и objective contract | `WS-OPTIMIZATION`, `HO-007`, `PB-007` | `desktop_optimizer_*`, `desktop_optimizer_tabs/`, `optimization_*`, `optimization_objective_contract.py`, `optimization_input_contract.py` | ring editor source data, animator rendering, diagnostics bundle finalization |
| V32-07 | Results Center и validation | `WS-ANALYSIS`, validation/results surface | `desktop_results_model.py`, `desktop_results_runtime.py`, validation/test center modules, result summaries | compare viewer internals, optimizer write paths |
| V32-08 | Compare Viewer и integrity mismatch | `WS-ANALYSIS`, `PB-007`, `PB-008` | `qt_compare_viewer.py`, `compare_*.py`, `compare_session.py`, `compare_trust.py` | optimizer run mutation, animator scene implementation |
| V32-09 | Desktop Animator и честная визуализация | `WS-ANIMATOR`, `HO-008`, `HO-010`, `PB-001`, `PB-006` | `desktop_animator/`, `anim_export_contract.py`, `anim_export_meta.py`, animator-specific tests | mnemo, compare, solver model internals except via contract |
| V32-10 | Desktop Mnemo и пневмосхема | specialized `Desktop Mnemo`, graphics truth policy | `desktop_mnemo/`, `PNEUMO_SCHEME.json`, scheme fingerprint/mnemo launchers/tests | animator 3D scene, compare viewer, input master copy |
| V32-11 | Diagnostics и Send Bundle | `WS-DIAGNOSTICS`, `HO-009`, `HO-010`, `PB-002` | `desktop_diagnostics_model.py`, `desktop_diagnostics_runtime.py`, `diagnostics_*`, `diag/`, `send_bundle.py`, bundle tests | domain business logic except evidence adapters |
| V32-12 | Geometry, Catalogs и Reference Center | `WS-TOOLS`, geometry/reference, `GAP-002`, `GAP-006`, `GAP-008` | `desktop_geometry_reference_*`, `catalogs/`, `component_passport.json`, `packaging_surface_*`, `suspension_geometry_ui.py`, `spring_geometry_ui.py` | animator scene rendering and optimizer objective loop |
| V32-13 | Engineering Analysis, Calibration и Influence | `WS-ANALYSIS`, engineering analysis lane | `calibration/`, `influence_tools.py`, `compare_influence*.py`, `param_influence_ui.py`, engineering-analysis tests | core data contract keys unless explicitly required |
| V32-14 | Producer Truth и геометрические контракты | `PB-001`, `GAP-001`, `GAP-002`, `GAP-006` | `solver_points_contract.py`, `solver_points_geometry.py`, `geometry_acceptance_contract.py`, `visual_contract.py`, `data_contract.py`, exporter contract tests | GUI layout and domain window UX |
| V32-15 | Runtime Evidence и performance gates | `PB-005`, `PB-006`, `GAP-003`, `GAP-004`, `GAP-010` | `browser_perf_artifacts.py`, runtime evidence helpers, frame-budget/viewport-gating tests, Windows proof docs | feature UI redesign, domain model ownership |
| V32-16 | Release Gates, KB и acceptance map | source authority, release gates, KB automation | `release_gate.py`, `workspace_contract.py`, `docs/00_PROJECT_KNOWLEDGE_BASE.md`, `docs/PROJECT_SOURCES.md`, `docs/context/*`, `tests/test_gui_spec_docs_contract.py` | runtime feature implementation |

## Handoff карта

Использовать v32 handoff IDs как границы между чатами:

- `HO-001`: проектный shell передает current project в input workspace.
- `HO-002`: `WS-INPUTS -> WS-RING`, frozen `inputs_snapshot.json`.
- `HO-003`: `WS-INPUTS -> WS-SUITE`, validated input context.
- `HO-004`: `WS-RING -> WS-SUITE`, `ring_source_of_truth.json` и canonical export set.
- `HO-005`: `WS-SUITE -> WS-BASELINE`, `validated_suite_snapshot.json`.
- `HO-006`: `WS-BASELINE -> WS-OPTIMIZATION`, `active_baseline_contract.json`.
- `HO-007`: `WS-OPTIMIZATION -> WS-ANALYSIS`, selected optimization run.
- `HO-008`: `WS-ANALYSIS -> WS-ANIMATOR`, analysis context and artifact refs.
- `HO-009`: `WS-ANALYSIS -> WS-DIAGNOSTICS`, evidence manifest.
- `HO-010`: `WS-ANIMATOR -> WS-DIAGNOSTICS`, capture export manifest.

Правило: downstream workspace не редактирует upstream source-of-truth, а только
показывает stale/current/historical state и предлагает перейти к владельцу.

## Стартовые промты

### V32-01. Кабина проекта и главное окно

```text
Работай над главным desktop shell проекта. Сначала прочитай 00 law, parameter registry, DATA_CONTRACT, docs/17, docs/18, docs/context/gui_spec_imports/v32_connector_reconciled/README.md и PARALLEL_CHAT_WORKSTREAMS.md. Твой scope: WS-SHELL и WS-PROJECT, верхнее меню, command search, дерево проекта, routing, dock/layout save-restore, status/progress/messages strip и visible diagnostics action. Не меняй доменные окна inputs/ring/optimizer/animator/mnemo; они открываются через handoff/launcher. Делай маленькие изменения, добавляй/обновляй shell tests, сохраняй Windows-native titlebar/snap/DPI/keyboard-first contract.
```

### V32-02. Исходные данные и визуальные двойники

```text
Работай над удобным desktop вводом исходных данных. Прочитай канон 17/18, v32 README, этот workstreams-документ и docs/gui_chat_prompts/02_INPUT_DATA.md. Твой scope: WS-INPUTS, секции геометрия/пневматика/механика/массы/численные настройки, слайдеры, единицы, help/tooltips, paired numeric+graphic twins и frozen inputs_snapshot handoff в WS-RING/WS-SUITE. Не меняй сценарии, optimizer и solver truth без отдельного contract update. Покрой тестами input editor, snapshots, stale banners и отсутствие invented keys.
```

### V32-03. Кольцевой сценарий и дорожный маршрут

```text
Работай над Ring Editor как единственным source-of-truth для дороги и циклического сценария. Прочитай 17/18, v32 README, v13_ring_editor_migration и docs/gui_chat_prompts/04_RING_EDITOR.md. Твой scope: WS-RING, segment semantics, seam diagnostics, generator, unfolded cyclic preview, road/scenario export set и handoff HO-004 в WS-SUITE. Не рисуй сценарий как геометрическое кольцо и не давай downstream редактировать геометрию. Обновляй ring tests, lineage hashes, stale banners и no-hidden-closure behavior.
```

### V32-04. Настройка расчета и набор испытаний

```text
Работай над расчетной настройкой и validated test suite. Прочитай 17/18, v32 README, PARALLEL_CHAT_WORKSTREAMS и docs/gui_chat_prompts/03_RUN_SETUP.md. Твой scope: WS-SUITE, default_suite, test matrix, overrides, validation, preview, suite_snapshot_hash и handoff HO-005 в baseline. Не владей geometry/ring source-of-truth, только потребляй refs из WS-RING и WS-INPUTS. Добавляй tests на validated_suite_snapshot, stale suite banners, missing refs и command discoverability.
```

### V32-05. Базовый прогон и active baseline

```text
Работай над Baseline Center. Прочитай 17/18, v32 README и objective/compare playbook PB-007. Твой scope: WS-BASELINE, active_baseline_contract, baseline history, review/adopt/restore policy, mismatch banners и handoff HO-006 в optimizer. Не запускай optimizer logic и не меняй suite/ring ownership. Тестируй active vs historical baseline, suite_snapshot_hash, stale baseline banners и запрет silent rebinding.
```

### V32-06. Оптимизатор и objective contract

```text
Работай над Optimizer Center. Прочитай 17/18, v32 README, docs/gui_chat_prompts/08_OPTIMIZER_CENTER.md и playbook PB-007. Твой scope: WS-OPTIMIZATION, один active optimization mode, objective stack, hard gates, distributed/staged settings, run contract persistence, problem hash и handoff HO-007 в analysis. Не меняй ring/source inputs напрямую и не финализируй diagnostics bundle. Обновляй tests на objective contract, run history, resume mismatch, stop/cleanup и selected run export.
```

### V32-07. Results Center и validation

```text
Работай над Results/Validation Center. Прочитай 17/18, v32 README и docs/gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md. Твой scope: отображение validated results, run summaries, validation reports, selected context, current/historical/stale banners и evidence export для diagnostics. Не меняй optimizer run contracts и compare viewer internals без handoff. Покрой tests на result context, validation report visibility, stale state и diagnostics evidence manifest input.
```

### V32-08. Compare Viewer и integrity mismatch

```text
Работай над Compare Viewer. Прочитай 17/18, v32 README, compare contract matrix из v32 и docs/gui_chat_prompts/05_COMPARE_VIEWER.md. Твой scope: compare sessions, explicit compare contracts, mismatch banners, baseline/objective/run refs, readonly current_context_ref sidecar provenance, offline NPZ/anim diagnostics loading и dock/layout behavior. Не мутируй optimizer history и не подменяй animator truth. Добавляй tests на compare_contract_hash, current vs historical mismatch, session autoload, missing sidecar status и Windows dock object names.
```

### V32-09. Desktop Animator и честная визуализация

```text
Работай над Desktop Animator. Прочитай 17/18, v32 README, docs/gui_chat_prompts/07_DESKTOP_ANIMATOR.md, PB-001 и PB-006. Твой scope: WS-ANIMATOR, truthful graphics states, analysis/optimizer artifact refs, capture export manifest, frame budget, hidden dock gating и handoff HO-010 в diagnostics. Не выдумывай geometry, cylinders или hardpoints; если truth incomplete, показывай approximate/unavailable with warning. Тестируй anim_latest contract, truth badges, frame-budget evidence и provenance.
```

### V32-10. Desktop Mnemo и пневмосхема

```text
Работай над Desktop Mnemo как отдельным специализированным окном. Прочитай 17/18, v32 README и docs/gui_chat_prompts/06_DESKTOP_MNEMO.md. Твой scope: пневмосхема, SVG/scheme mapping, pressure/flow/state visualization, source markers, launch/open behavior и Windows layout. Не дублируй animator 3D scene, compare viewer и input editor. Добавляй tests на dataset contract, launcher, snapshot/provenance, settings bridge и честные unavailable states.
```

### V32-11. Diagnostics и Send Bundle

```text
Работай над Diagnostics / Send Bundle. Прочитай 17/18, v32 README, PB-002, RELEASE_GATE_HARDENING_MATRIX и docs/gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md. Твой scope: WS-DIAGNOSTICS, one-click collect, health/triage/latest pointer, evidence manifest, SEND bundle contents, crash/exit/manual modes и helper runtime provenance. Не меняй domain calculations; только собирай adapters/evidence. Тестируй bundle contents, health after final triage, latest pointer, encoding и missing evidence warnings.
```

### V32-12. Geometry, Catalogs и Reference Center

```text
Работай над Geometry/Catalogs/Reference Center. Прочитай 17/18, v32 README, docs/gui_chat_prompts/11_GEOMETRY_REFERENCE.md и gaps GAP-002/GAP-006/GAP-008. Твой scope: catalogs, component passport, geometry reference UI, packaging passport, road_width_m visibility and reference explanations. Не внедряй 3D animator rendering и не меняй optimizer objective loop. Добавляй tests на catalog/reference contracts, packaging completeness, geometry acceptance evidence и unit/help labels.
```

### V32-13. Engineering Analysis, Calibration и Influence

```text
Работай над Engineering Analysis / Calibration / Influence. Прочитай 17/18, v32 README и docs/gui_chat_prompts/12_ENGINEERING_ANALYSIS.md. Твой scope: calibration tools, influence analysis, compare_influence surfaces, engineering reports, sensitivity summaries and validated artifacts. Не меняй canonical keys без registry/data-contract update. Тестируй influence outputs, calibration artifacts, report provenance, units and diagnostics evidence export.
```

### V32-14. Producer Truth и геометрические контракты

```text
Работай над producer-side truth closure. Прочитай 00 law, parameter registry, DATA_CONTRACT, v32 README, PB-001, GAP-001/GAP-002/GAP-006 и geometry/anim export contracts. Твой scope: solver_points, hardpoints, geometry acceptance, visual contract, anim_latest/export contract and validators. Не занимайся GUI layout; GUI-чаты должны только потреблять твой contract. Тестируй missing/incomplete truth, no fake geometry, packaging passport, axis-only honesty mode и contract drift.
```

### V32-15. Runtime Evidence и performance gates

```text
Работай над runtime evidence и performance gates. Прочитай v32 README, PB-005, PB-006, GAP-003/GAP-004/GAP-010 и Windows desktop canon 17. Твой scope: measured trace artifacts, viewport/hidden surface gating, animator frame-budget evidence, Windows snap/DPI/second-monitor/path-budget proof and SEND-bundle evidence hooks. Не редизайни domain screens. Тестируй trace exporter presence, hidden pane budget, frame cadence, evidence files and release-gate hard fails.
```

### V32-16. Release Gates, KB и acceptance map

```text
Работай над knowledge base, release gates и acceptance map. Прочитай 00_PROJECT_KNOWLEDGE_BASE, PROJECT_SOURCES, v32 README, этот workstreams-документ, RELEASE_GATE_ACCEPTANCE_MAP.md, RELEASE_GATE_HARDENING_MATRIX.csv и GAP_TO_EVIDENCE_ACTION_MAP.csv. Твой scope: docs, KB logs, release_gate/workspace_contract helpers, source authority, acceptance docs/tests and prompt indexes. Не реализуй runtime features вместо domain-чатов. Обновляй knowledge_base_sync entries, tests/test_gui_spec_docs_contract.py, no-mojibake checks и ссылки на active reference layers.
```

## Минимальный Definition Of Done для любого чата

- Сохранены source-of-truth границы своего workspace.
- В README/docstrings/tests отражены handoff IDs, если работа касается обмена.
- Добавлен или обновлен хотя бы один узкий тест домена.
- Не добавлены новые кракозябры, alias keys или silent fallback.
- `git status` показывает только файлы своего owned scope и явно согласованные
  contract/KB files.
- Если работа меняет план или требование, KB обновлена в этом же чате.
