from __future__ import annotations

import argparse
import cProfile
import io
import os
import pstats
import sys
import time
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve()
PKG_ROOT = HERE.parents[2]
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as worldroad_model


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark canonical worldroad hot-path scenario.")
    parser.add_argument("--dt", type=float, default=5e-3, help="Integrator step.")
    parser.add_argument("--t-end", type=float, default=4.0, help="Scenario duration.")
    parser.add_argument("--reps", type=int, default=7, help="Measured repetitions.")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup runs before timing.")
    parser.add_argument("--amplitude", type=float, default=0.015, help="Diagonal road amplitude, meters.")
    parser.add_argument("--freq-hz", type=float, default=1.5, help="Diagonal road frequency, Hz.")
    parser.add_argument("--profile-top", type=int, default=16, help="How many cProfile rows to print; 0 disables profiling.")
    return parser


def _build_test(amplitude: float, freq_hz: float):
    omega = 2.0 * np.pi * float(freq_hz)
    amp = float(amplitude)
    return {
        "road_func": lambda t: np.array([0.0, amp * np.sin(omega * t), -amp * np.sin(omega * t), 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _run_once(dt: float, t_end: float, test: dict) -> None:
    params = {
        "пружина_преднатяг_на_отбое_строго": False,
        "стабилизатор_вкл": False,
    }
    worldroad_model.simulate(params, test, dt=float(dt), t_end=float(t_end), record_full=False)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    reps = max(1, int(args.reps))
    warmup = max(0, int(args.warmup))
    test = _build_test(args.amplitude, args.freq_hz)

    for _ in range(warmup):
        _run_once(args.dt, args.t_end, test)

    timings: list[float] = []
    for _ in range(reps):
        t0 = time.perf_counter()
        _run_once(args.dt, args.t_end, test)
        timings.append(time.perf_counter() - t0)

    ordered = sorted(timings)
    print("simulate_reps_s=", ", ".join(f"{v:.4f}" for v in timings))
    print("simulate_best_s=", f"{ordered[0]:.4f}")
    print("simulate_median_s=", f"{ordered[len(ordered) // 2]:.4f}")

    profile_top = max(0, int(args.profile_top))
    if profile_top > 0:
        prof = cProfile.Profile()
        prof.enable()
        _run_once(args.dt, args.t_end, test)
        prof.disable()
        stream = io.StringIO()
        pstats.Stats(prof, stream=stream).sort_stats("cumtime").print_stats(profile_top)
        print(stream.getvalue())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
