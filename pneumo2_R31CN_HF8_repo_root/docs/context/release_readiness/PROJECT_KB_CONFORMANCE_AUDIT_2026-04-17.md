# Project KB Conformance Audit 2026-04-17

Purpose: audit the synchronized repository against the active knowledge base and
turn the result into a practical improvement plan.

This document is not a runtime closure claim. It records repository sync state,
knowledge-base authority, executable evidence and remaining work. Runtime
closure still requires named artifacts, SEND-bundle evidence or measured
Windows/runtime proof where the gates require it.

## Sync Snapshot

Repository container:

- `C:/Users/Admin/Documents/GitHub/pneumo2`

Application/documentation root:

- `C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root`

Git state after `git fetch --all --prune --prune-tags`:

- current branch: `codex/work`;
- `codex/work...origin/codex/work`: `0 0`;
- `codex/work...origin/main`: `73 0`;
- local `main`: `1e99b07`, aligned with `origin/main`;
- working tree: clean before this audit note was written.

Active local worktrees/branches seen during audit:

- `codex/runtime-evidence-gates`;
- `codex/ws-ring-ho004-suite-handoff`;
- `codex/save-autoselfcheck-disk-cache-1b07`;
- `codex/save-autoselfcheck-disk-cache-b637`;
- `codex/save-mnemo-dataset-contract-c6a4`.

Integration implication: `codex/work` is synchronized with its remote branch but
is not merged into `origin/main`. Future merge/release work must treat the 73
commits as a lane-packaged integration branch, not as already-mainline state.

## Knowledge Base Read Order Used

The audit used this effective priority stack:

1. `00_READ_FIRST__ABSOLUTE_LAW.md`
2. `01_PARAMETER_REGISTRY.md`
3. `DATA_CONTRACT_UNIFIED_KEYS.md`
4. `docs/00_PROJECT_KNOWLEDGE_BASE.md`
5. `docs/PROJECT_SOURCES.md`
6. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
7. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
8. `docs/context/gui_spec_imports/v37_github_kb_supplement/*`
9. `docs/context/gui_spec_imports/v33_connector_reconciled/*`
10. `docs/context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md`
11. `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md`
12. `docs/context/release_readiness/*`
13. executable contracts in `pneumo_solver_ui/*contract*.py`, `pneumo_solver_ui/contracts/*` and `tests/test_*contract*`

Important boundary: `v37_github_kb_supplement` is the current successor
KB/TZ/spec layer, but it explicitly remains reference-first and does not prove
producer-side truth or runtime acceptance.

## Executable Evidence

Repository surface observed:

- 491 tracked test files under `tests`;
- separate desktop modules for shell, input editor, ring editor, run setup,
  optimizer, results center, diagnostics, geometry/reference, engineering
  analysis, Desktop Mnemo, Desktop Animator and Compare Viewer;
- release-gate helpers exist in `pneumo_solver_ui/release_gate.py` and
  `pneumo_solver_ui/workspace_contract.py`;
- KB automation exists in `pneumo_solver_ui/tools/knowledge_base_sync.py`.

Focused audit command:

```powershell
python -m pytest tests/test_gui_spec_docs_contract.py tests/test_knowledge_base_sync_contract.py tests/test_desktop_main_shell_qt_contract.py tests/test_desktop_input_editor_contract.py tests/test_desktop_ring_editor_contract.py tests/test_desktop_run_setup_center_contract.py tests/test_desktop_optimizer_center_contract.py tests/test_desktop_diagnostics_center_contract.py tests/test_desktop_geometry_reference_center_contract.py tests/test_desktop_engineering_analysis_center_contract.py tests/test_desktop_mnemo_launcher_contract.py tests/test_qt_compare_viewer_compare_contract.py tests/test_v32_desktop_animator_truth_contract.py tests/test_v32_diagnostics_send_bundle_evidence.py tests/test_v32_runtime_evidence_gates.py -q
```

Result:

- `218 passed in 36.80s`.

Interpretation: the repository currently has strong docs/contracts coverage for
the active GUI migration lanes. This does not replace runtime startup/manual
Windows visual proof, nor final SEND-bundle evidence.

## Conformance Matrix

| Lane | Current repo evidence | Conformance status | Remaining work |
| --- | --- | --- | --- |
| V32-01 Shell / Project | `desktop_shell`, `desktop_qt_shell`, launchers and shell tests exist. | Contract present. | Prove real Windows startup, titlebar/snap/DPI behavior, launcher stability and project routing with runtime evidence. |
| V32-02 Inputs | `desktop_input_model.py`, `desktop_input_graphics.py`, input editor launcher and tests exist. | Contract present. | Harden user-facing UX for sectioned input, sliders, stale state, graphic twins and startup latency; no invented keys. |
| V32-03 Ring Editor | Ring model/panels/runtime, scenario modules and handoff tests exist. | Contract present with separate HO-004 branch still visible. | Decide integration order for `codex/ws-ring-ho004-suite-handoff`, then close seam/handoff evidence without downstream mutation. |
| V32-04 Run Setup / Suite | Run setup model/runtime, suite snapshot helpers and tests exist. | Contract present. | Complete validated-suite snapshot UX, missing-ref explanations and handoff to baseline. |
| V32-05 Baseline | Baseline source/history helpers and tests exist. | Partial desktop workflow. | Build/verify explicit Baseline Center UX: adopt/restore policy, stale banners and no silent rebinding. |
| V32-06 Optimizer | Optimizer center, tabs, objective/input contracts and many tests exist. | Strong contract coverage. | Consolidate all settings into a clear desktop center, keep one active mode selector and prove objective/run history integrity on real artifacts. |
| V32-07 Results / Validation | Results model/runtime and validation-related tests exist. | Partial desktop workflow. | Finish Results Center as the user-visible validation hub and make diagnostics evidence export first-class. |
| V32-08 Compare Viewer | `qt_compare_viewer.py`, compare contract/session/trust modules and tests exist. | Contract present. | Prove real-bundle runtime loading, mismatch banners and layout restore; do not mutate optimizer artifacts. |
| V32-09 Desktop Animator | Large animator module, truth contract and many regression tests exist. | Feature-rich, but truth gaps remain open. | Close only after producer truth, cylinder passport and measured frame/runtime evidence are available. |
| V32-10 Desktop Mnemo | Mnemo package, settings bridge, launcher and tests exist. | Contract present, runtime confidence not enough. | Reproduce and fix real startup/open failures reported by the user, then add runtime proof and visual non-overlap checks. |
| V32-11 Diagnostics / Send Bundle | Diagnostics model/runtime, bundle tools, health helpers and tests exist. | Contract present. | Produce final SEND bundle proof with latest pointer, helper runtime provenance and explicit warnings for missing producer evidence. |
| V32-12 Geometry / Catalogs / Reference | Geometry/reference modules, catalogs and tests exist. | Partial. | Finish packaging passport, cylinder/reference completeness and imported-layer assumption evidence. |
| V32-13 Engineering Analysis / Calibration / Influence | Calibration/influence modules, engineering analysis model/runtime and tests exist. | Contract present. | Consolidate legacy calibration/influence tools into a coherent desktop analysis workflow with provenance and units. |
| V32-14 Producer Truth | Solver-points, geometry acceptance and visual contract tests exist. | Critical open gap. | Close hardpoints/solver_points truth, anim export metadata and geometry acceptance from producer-side artifacts, not viewer guesses. |
| V32-15 Runtime Evidence / Perf | Runtime evidence helpers and tests exist. | Validators present, evidence not closed. | Collect measured Windows/runtime traces, viewport gating evidence and frame budget artifacts; package them into diagnostics/SEND flow. |
| V32-16 Release Gates / KB | KB docs, source map, release gate helpers and docs tests exist. | Strong. | Keep new chat plans/requirements recorded and block closure claims that lack named runtime/evidence artifacts. |

## Open Gaps That Must Stay Visible

From `v37_github_kb_supplement/REPO_OPEN_GAPS_TO_KEEP_OPEN.csv` and the v32
release-gate map:

- `GAP-001`: producer-side `hardpoints / solver_points` truth remains open.
- `GAP-002`: complete cylinder packaging passport remains open.
- `GAP-003`: measured browser/runtime performance trace and viewport gating remain open.
- `GAP-004`: Windows visual/runtime acceptance remains open.
- `OG-005`: diagnostics/SEND closure still requires final bundle, health after triage and latest pointer proof.
- `OG-006`: imported-layer assumptions must remain explicit where runtime proof is absent.

## Project-Level Audit Result

The project is aligned with the knowledge base at the documentation, source map,
contract-module and focused-test level. The current codebase already has the
expected modular desktop GUI lanes and avoids a single monolithic GUI target.

The project is not yet release-closed against the knowledge base because the
most important gates require runtime/user-visible proof: real Windows shell
startup, Desktop Mnemo startup, real-bundle Compare/Animator behavior, measured
runtime/performance traces, final SEND bundle evidence and producer-side truth
for geometry/cylinders.

## Improvement Plan

### Phase 0: Repository Hygiene And Merge Strategy

- Keep `codex/work` synchronized with `origin/codex/work`.
- Treat the 73 commits above `origin/main` as an integration branch requiring
  review before mainline merge.
- Review active side branches by lane: runtime evidence, HO-004 ring handoff,
  autoselfcheck cache and Mnemo dataset contract.
- Do not mix lane work in one commit unless it is KB/source-map-only.

### Phase 1: User-Visible Desktop Startup Stabilization

- Start with V32-01 and V32-10 because the user directly observed hangs/failures.
- Add runtime proof for shell open, stage open and Desktop Mnemo open.
- Fix visual overlap/non-response issues before adding new GUI features.
- Keep WEB as legacy/reference only; do not continue WEB UI development beyond launch buttons.

### Phase 2: Producer Truth And Geometry Closure

- Prioritize V32-14, V32-12 and V32-09 together.
- Produce solver-side hardpoints/solver_points artifacts.
- Complete cylinder packaging passport and geometry acceptance report.
- Let Animator consume truth-state contracts; do not invent missing geometry in the viewer.

### Phase 3: Operator Workflow Completion

- Complete the desktop chain: Inputs -> Ring -> Run Setup -> Baseline -> Optimizer -> Results/Compare.
- Each handoff must carry immutable refs/hashes and stale/current status.
- Finish Baseline Center and Results Center, which are weaker than shell/optimizer contracts today.

### Phase 4: Diagnostics, SEND Bundle And Runtime Evidence

- Use V32-11 and V32-15 as the release evidence backbone.
- Collect measured Windows/runtime traces and frame-budget artifacts.
- Ensure SEND bundle includes latest pointer, health-after-triage, helper provenance and explicit open-gap warnings.

### Phase 5: Release Gate Review

- Re-run docs/KB/no-mojibake tests after every KB update.
- Run lane-specific targeted tests for each accepted package.
- Do not mark a gap closed unless the closure names the artifact path, test command and evidence source.
- Prepare a final release-readiness report that separates contract coverage, runtime proof and still-open gaps.

## Next Best Work Item

The next practical implementation step should be a focused V32-01/V32-10
runtime-stability pass: reproduce shell/stage/Mnemo startup from the same
launcher path the user uses, fix hangs or blocking constructors, and store a
small runtime proof artifact that Diagnostics can include later.
