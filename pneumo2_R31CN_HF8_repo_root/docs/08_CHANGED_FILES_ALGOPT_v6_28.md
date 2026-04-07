# CHANGED_FILES (v6.28)

Base: AlgoritmyOptimizatsiiUnifiedPneumoAppVSixTwentySevenWinSafe.zip

## Modified
- pneumo_solver_ui/opt_worker_v3_margins_energy.py
  - baseline row (id=-1) auto-evaluated
  - seed_points_json + seed_only support
  - early-stop by accumulated penalty (stop_if_pen_gt)
  - optional test sorting by estimated cost (dt*t_end)
  - stable service columns (meta_source, pruned_early, etc.)

- pneumo_solver_ui/opt_stage_runner_v1.py
  - warmstart_mode: surrogate/archive/none
  - surrogate warm-start (ExtraTreesRegressor) on global archive
  - early-stop thresholds per stage (stop_pen_stage1/2) passed to worker
  - stage plan tuned: longer stage2, t_end_scale=2.0
  - baseline auto-update is now guarded by baseline_best_score.json

- pneumo_solver_ui/pneumo_ui_app.py
  - UI controls to configure warm-start + early-stop + sorting
  - passes new flags into StageRunner

## New / Added
- patches/patch_vsix_twenty_eight_worker.diff
- patches/patch_vsix_twenty_eight_stage_runner.diff
- patches/patch_vsix_twenty_eight_ui.diff
- BUILD_INFO_v6_28_ALGOPT.txt
- README_v6_28_ALGOPT.md
- TODO_v6_28.md
- WISHLIST_v6_28.md
