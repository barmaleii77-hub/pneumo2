# Pneumo GUI Codex — Preservation and Design Recovery v12

Этот пакет делает две вещи:

1. **Сохраняет все созданные ранее GUI/Codex-артефакты** с комментариями.
2. **Возвращает продолжение работ в правильную ветку** — design-first.

## Что внутри

### 1. Архив сохранённых наработок
Смотри:
- `artifact_lineage_v12.csv`
- `artifact_lineage_v12.json`
- каталог `preserved_outputs/`
- каталог `reference_inputs/`

### 2. Комментарии по веткам
Смотри:
- `continuation_decision_v12.md`

### 3. Новый delta-слой продолжения
Смотри:
- `pneumo_gui_codex_spec_v12_design_recovery.json`
- `ring_editor_canonical_contract_v12.json`
- `optimization_control_plane_contract_v12.json`
- `truthful_graphics_contract_v12.json`
- `workspace_delta_v12.json`

## Как теперь правильно продолжать работу

### Канонический маршрут
1. `preserved_outputs/prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md`
2. `preserved_outputs/pneumo_gui_codex_package_v5.zip`
3. `pneumo_gui_codex_spec_v12_design_recovery.json`

### Архивированный маршрут реализации
`V6–V11` сохранены, но считаются **вторичной побочной веткой**, а не основной design-базой.

## Главный смысл v12
- ничего из уже сделанного не потеряно;
- implementation-ветка не удалена;
- дальнейшее продолжение работ возвращено в проектную, а не кодовую логику.
