# V38 KB Import Audit 2026-04-18

Purpose: local audit for
`pneumo_codex_tz_spec_connector_reconciled_v38_github_kb_commit_ready.zip`
before using it as the current imported knowledge-base layer.

This note is a repository-side clarification layer. It does not rewrite the
archive artifacts and does not claim runtime closure.

## Read Coverage

The archive was expanded locally and machine-read as text/CSV/JSON/YAML/DOT.
No file category was intentionally skipped.

- Archive path:
  `C:/Users/Admin/Downloads/pneumo_codex_tz_spec_connector_reconciled_v38_github_kb_commit_ready.zip`
- Expanded root:
  `pneumo_codex_tz_spec_connector_reconciled_v38_github_kb_commit_ready/`
- Total archive files read: 96
- `PACKAGE_INDEX.csv` rows: 96; all rows match actual archive files.
- `PACKAGE_MANIFEST.json` rows: 94; the two expected unlisted self-artifacts
  are `PACKAGE_MANIFEST.json` and `PACKAGE_SELFCHECK_REPORT.json`, consistent
  with the package integrity policy that the manifest does not hash itself.
- Imported repository subtree copied from
  `REPO_IMPORT_READY/docs/context/gui_spec_imports/v38_github_kb_commit_ready/`.
- Imported repository files copied: 33

## Imported Layer Counts

The committed V38 imported layer contains:

- 45 requirements in `REQUIREMENTS_MATRIX.csv`.
- 45 acceptance rows in `ACCEPTANCE_MATRIX.csv`.
- 61 screens in `SCREEN_CATALOG.csv`.
- 704 UI elements in `UI_ELEMENT_CATALOG.csv`.
- 488 parameters in `PARAMETER_CATALOG.csv`.
- 5368 parameter-pipeline rows in `PARAMETER_PIPELINE_MATRIX.csv`.
- 12 windows in `WINDOW_CATALOG.csv`.
- 12 workspaces in `WORKSPACE_CONTRACT_MATRIX.csv`.
- 4 explicitly open gaps in `REPO_OPEN_GAPS_TO_KEEP_OPEN.csv`.

Duplicate ID checks for requirements, acceptance rows, screens, UI elements,
parameters, windows and workspaces found no duplicate primary IDs.

## Local Authority Rule

V38 is now the current imported successor layer for GUI/TZ/spec and
knowledge-base reconciliation.

The unambiguous local read order is:

1. `00_READ_FIRST__ABSOLUTE_LAW.md`.
2. `01_PARAMETER_REGISTRY.md`.
3. `DATA_CONTRACT_UNIFIED_KEYS.md`.
4. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`.
5. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`.
6. `docs/context/gui_spec_imports/foundations/*`.
7. `docs/context/gui_spec_imports/v38_github_kb_commit_ready/*`.
8. `docs/context/gui_spec_imports/v37_github_kb_supplement/*` as predecessor
   provenance.
9. `docs/context/gui_spec_imports/v33_connector_reconciled/*` and
   `docs/context/gui_spec_imports/v32_connector_reconciled/*` as
   connector/release-gate/evidence layers.
10. `docs/context/gui_spec_imports/v3/*`.
11. `docs/context/gui_spec_imports/v13_ring_editor_migration/*` for `WS-RING`
    and `WS-RING -> WS-SUITE`.
12. `docs/context/gui_spec_imports/v12_design_recovery/*` and older lineage.

If V38 conflicts with `17/18`, the human-readable canon wins and the conflict
must be recorded as an assumption/gap. V38 must not be treated as runtime,
producer-truth, browser-performance or Windows visual acceptance proof.

## Resolved Ambiguities In The Archive

These points were found while reading all archive files and are resolved here
to keep the local KB unambiguous:

- `REPO_APPLY_ORDER.md` and the root-level `REPO_KB_MAINTAINER_CHECKLIST.md`
  have V37 headings, but their body and paths target
  `v38_github_kb_commit_ready`. Treat the headings as packaging typos.
- The root package is named commit-ready and dated 2026-04-18, while the
  import-ready `GUI_SPEC.yaml` still carries a V38 supplement package id and
  package date 2026-04-17. Treat this as wrapper-vs-imported-layer identity:
  the committed folder is the V38 successor imported layer prepared by the
  2026-04-18 commit-ready package.
- `STRUCTURE_LINT_REPORT.md` still contains older labels such as V35 and
  references to some historical top-level guidance filenames. Treat those as
  lineage text, not as the active repository read order.
- `TECHNICAL_SPECIFICATION.md` contains carried-forward annex references such
  as `SOURCE_AUTHORITY_MATRIX.csv`, `WORKSPACE_HANDOFF_MATRIX.csv` and
  `CODEx_CONSUMPTION_ORDER.md` that are not present in this V38 import-ready
  subtree. The active committed mandatory set is the 33-file
  `REPO_IMPORT_READY` layer plus this local audit; missing carried-forward
  annex names remain future backlog/lineage references, not hidden closed
  deliverables.
- Repeated section numbers inside `TECHNICAL_SPECIFICATION.md` are inherited
  historical appendices. The active V38 package status block and the local
  authority rule above determine how to use the file.

## Open Gaps Preserved

The following V38 gaps stay open and must not be marked covered without fresh
evidence:

- producer-side hardpoints / solver-points truth;
- cylinder packaging passport;
- measured browser performance trace and viewport gating;
- final Windows visual/runtime acceptance.

## Prompt Impact

The 10 parallel chat prompts must use V38 as the current visual and
knowledge-base layer. They must still preserve the post-quarantine baseline,
V37 service-jargon cleanup, optimized pipeline navigation, no-WEB-expansion
rule and separate ownership of Desktop Animator, Compare Viewer and Desktop
Mnemo.
