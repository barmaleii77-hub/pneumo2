# -*- coding: utf-8 -*-
"""
opt_worker_v3_margins_energy.py

Фоновый оптимизатор (можно считать хоть неделю) для модели пневмоподвески.

Особенности:
- критерии физичности через "запасы"/штрафы (не булевы флаги),
- расширенный тест‑набор (инерция + микроколебания + одиночная кочка + диагональ + комбо),
- энергетический аудит (по всем сопротивлениям и отдельно по дросселям),
- инкрементальная запись результатов (чтобы не потерять прогресс при остановке),
- поддержка остановки через "stop‑файл" (опционально) и/или через kill процесса.

ВАЖНО: этот файл запускается НЕ вручную, а из UI (кнопка "Запустить оптимизацию").
Но при желании можно запустить и из консоли.

Запуск вручную (пример):
    python opt_worker_v3_margins_energy.py ^
        --model model_pneumo_v8_energy_audit_vacuum.py ^
        --out results_opt.csv ^
        --minutes 10 --seed 1 --jobs 2

"""

import argparse
import os
import time
import math
import copy
import importlib.util
import json
import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
import sys
# Ensure project package is importable even when this script is launched directly
_THIS = Path(__file__).resolve()
if _THIS.parent.name == "calibration":
    _PNEUMO_ROOT = _THIS.parent.parent  # .../pneumo_solver_ui
else:
    _PNEUMO_ROOT = _THIS.parent  # .../pneumo_solver_ui
_PROJECT_ROOT = _PNEUMO_ROOT.parent  # .../project root
for _p in (str(_PROJECT_ROOT), str(_PNEUMO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pneumo_solver_ui.name_sanitize import sanitize_id
from pneumo_solver_ui.optimization_baseline_source import (
    baseline_problem_scope_dir as _baseline_problem_scope_dir,
    resolve_workspace_baseline_override_path as _resolve_workspace_baseline_override_path,
    workspace_baseline_dir as _shared_workspace_baseline_dir,
)
from pneumo_solver_ui.optimization_input_contract import sanitize_ranges_for_optimization
from pneumo_solver_ui.optimization_result_rows import BASELINE_ROLE
from pneumo_solver_ui.atomic_write_retry import atomic_write_json_retry
from pneumo_solver_ui.anim_export_contract import build_packaging_block, summarize_anim_export_objective_metrics
from pneumo_solver_ui.data_contract import build_geometry_meta_from_base
from pneumo_solver_ui.module_loading import load_python_module_from_path
from pneumo_solver_ui.project_path_resolution import resolve_project_py_path
from pneumo_solver_ui.suspension_family_contract import normalize_component_family_contract
from typing import Dict, List, Tuple, Any, Optional, Iterable, Mapping

import numpy as np
import pandas as pd


BASELINE_RESULT_ID = 0
SEED_ID_OFFSET = 2_000_000_001
SEED_ID_MOD = 2_000_000_000


def _mark_candidate_role(row: Dict[str, Any], role: str) -> Dict[str, Any]:
    out = dict(row or {})
    out["candidate_role"] = str(role or "")
    out["is_baseline"] = 1 if str(role or "") == BASELINE_ROLE else 0
    return out


# ---------------------------------------------------------------------------
# Performance / CPU utilization helpers
# ---------------------------------------------------------------------------
# Цели:
# - задействовать все ядра CPU при параллельных расчётах (jobs>1)
# - не попасть в «оверсабскрипцию» (когда каждый процесс ещё и распараллеливает BLAS/OpenMP внутри)
#
# Примечание: здесь только helpers. Фактическое применение лимитов для воркеров
# делаем в _init_pool_worker(), чтобы это работало и в subprocess-режиме из UI.

def _cpu_count_logical() -> int:
    """Логическое число CPU (hyper-threads)."""
    try:
        import psutil  # type: ignore
        n = psutil.cpu_count(logical=True)
        if n:
            return int(n)
    except Exception:
        pass
    try:
        n2 = os.cpu_count()
        if n2:
            return int(n2)
    except Exception:
        pass
    return 1


def _default_jobs_auto(cap: int = 128) -> int:
    """Дефолтная параллельность: все доступные логические ядра (с разумным cap)."""
    n = int(_cpu_count_logical())
    # На Windows у ProcessPoolExecutor есть лимит max_workers<=61.
    if os.name == 'nt':
        n = min(n, 61)
    if cap is not None:
        try:
            cap_i = int(cap)
            if cap_i > 0:
                n = min(n, cap_i)
        except Exception:
            pass
    return max(1, int(n))


def _force_native_thread_limits(n_threads: int = 1) -> None:
    """Ограничить потоки OpenMP/BLAS внутри процесса.

    Это важно при multiprocessing: иначе суммарное число потоков станет
    jobs * <BLAS_threads> и CPU уйдёт в оверсабскрипцию (в итоге медленнее).
    """
    try:
        n = max(1, int(n_threads))
    except Exception:
        n = 1

    # env vars (работают, если выставлены до инициализации runtime библиотек)
    for var in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "BLIS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        try:
            os.environ[var] = str(n)
        except Exception:
            pass

    # runtime API (если доступно) — более надёжно, чем env vars.
    try:
        from threadpoolctl import threadpool_limits  # type: ignore

        threadpool_limits(limits=n)
    except Exception:
        # threadpoolctl — опционально; в этом проекте добавлен в requirements.
        pass


# ---------------------------------------------------------------------------
# Penalty targets contract (R59 P0): UI must expose EXACTLY these target keys.
# ---------------------------------------------------------------------------
# The continuous penalty function `candidate_penalty()` below uses only a
# specific set of keys (without the `target_` prefix).
#
# Suite rows store them as columns:  target_<key>
# Example: target_макс_доля_отрыва
#
# If UI shows other targets (e.g. target_clearance/target_pmax_atm/...) and the
# penalty function does not read them, the optimization becomes misleading
# (penalty stays 0). Therefore, the UI should build its editable target list
# from this registry.

PENALTY_TARGET_SPECS: List[Dict[str, str]] = [
    {
        "key": "макс_доля_отрыва",
        "label": "Макс. доля отрыва",
        "unit": "доля",
        "help": "Доля времени, когда хотя бы одно колесо в отрыве (0..1).",
    },
    {
        "key": "мин_запас_до_Pmid_бар",
        "label": "Мин. запас до Pmid",
        "unit": "бар",
        "help": "Запас по давлению pR3_max до Pmid (бар). Положительный => ниже Pmid.",
    },
    {
        "key": "мин_Fmin_Н",
        "label": "Мин. прижимная сила шин (Fmin)",
        "unit": "Н",
        "help": "Минимальная нормальная реакция шин.",
    },
    {
        "key": "мин_запас_до_пробоя_крен_град",
        "label": "Мин. запас до пробоя (крен)",
        "unit": "град",
        "help": "Запас до пробоя по крену.",
    },
    {
        "key": "мин_запас_до_пробоя_тангаж_град",
        "label": "Мин. запас до пробоя (тангаж)",
        "unit": "град",
        "help": "Запас до пробоя по тангажу.",
    },
    {
        "key": "мин_запас_до_упора_штока_м",
        "label": "Мин. запас до упора штока",
        "unit": "м",
        "help": "Минимальный запас до упора штока (минимум по всем углам).",
    },
    {
        "key": "лимит_скорости_штока_м_с",
        "label": "Лимит скорости штока",
        "unit": "м/с",
        "help": "Максимальная скорость штока (макс. по всем углам).",
    },
    {
        "key": "мин_зазор_пружина_цилиндр_м",
        "label": "Мин. зазор пружина-цилиндр",
        "unit": "м",
        "help": "Минимальный радиальный зазор между пружиной и её цилиндром-хостом по всем семействам. Отрицательное значение означает интерференцию.",
    },
    {
        "key": "мин_зазор_пружина_пружина_м",
        "label": "Мин. зазор пружина-пружина",
        "unit": "м",
        "help": "Минимальный зазор между пружинами Ц1 и Ц2 на одном углу по геометрии осей и наружных диаметров.",
    },
    {
        "key": "макс_ошибка_midstroke_t0_м",
        "label": "Макс. ошибка midstroke t0",
        "unit": "м",
        "help": "Абсолютное отклонение поршня от середины хода в начале расчёта.",
    },
    {
        "key": "мин_запас_до_coil_bind_пружины_м",
        "label": "Мин. запас до coil-bind пружины",
        "unit": "м",
        "help": "Минимальный запас до coil-bind по всем активным семействам пружин с family-aware runtime fallback для старых bundle-схем.",
    },
    {
        "key": "макс_ошибка_энергии_газа_отн",
        "label": "Макс. ошибка энергии газа (отн.)",
        "unit": "отн",
        "help": "Абсолютная относительная ошибка энергетического баланса газа.",
    },
    {
        "key": "макс_эксергия_разрушена_Дж",
        "label": "Макс. эксергия разрушена",
        "unit": "Дж",
        "help": "Ограничение по эксергии разрушенной (2-й закон).",
    },
    {
        "key": "макс_энтропия_генерация_Дж_К",
        "label": "Макс. генерация энтропии",
        "unit": "Дж/К",
        "help": "Ограничение по генерации энтропии (2-й закон).",
    },
    {
        "key": "макс_эксергия_падение_давления_Дж",
        "label": "Макс. эксергия (падение давления)",
        "unit": "Дж",
        "help": "Декомпозиция 2-го закона: эксергия от падения давления/дросселирования.",
    },
    {
        "key": "макс_эксергия_смешение_Дж",
        "label": "Макс. эксергия (смешение)",
        "unit": "Дж",
        "help": "Декомпозиция 2-го закона: эксергия от смешения потоков.",
    },
    {
        "key": "макс_эксергия_остаток_без_тепло_без_смешения_Дж",
        "label": "Макс. эксергия (остаток)",
        "unit": "Дж",
        "help": "Декомпозиция 2-го закона: прочие необратимости (без тепло и без смешения).",
    },
    {
        "key": "макс_энтропия_падение_давления_Дж_К",
        "label": "Макс. энтропия (падение давления)",
        "unit": "Дж/К",
        "help": "Декомпозиция 2-го закона: энтропия от падения давления/дросселирования.",
    },
    {
        "key": "макс_энтропия_смешение_Дж_К",
        "label": "Макс. энтропия (смешение)",
        "unit": "Дж/К",
        "help": "Декомпозиция 2-го закона: энтропия от смешения потоков.",
    },
    {
        "key": "макс_энтропия_остаток_без_тепло_без_смешения_Дж_К",
        "label": "Макс. энтропия (остаток)",
        "unit": "Дж/К",
        "help": "Декомпозиция 2-го закона: прочие необратимости (без тепло и без смешения).",
    },
]


def penalty_target_keys() -> List[str]:
    """Список ключей targets (без префикса target_)."""
    return [d.get("key", "") for d in PENALTY_TARGET_SPECS if d.get("key")]


# ---------------------------
# JSON helpers
# ---------------------------

def load_json(path: str):
    """Прочитать JSON (UTF-8) и вернуть объект."""
    import json
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(obj, path: str):
    """Записать JSON (UTF-8) атомарно."""
    import json, os
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------------------
# Вспомогательное: LHS/рандом
# ---------------------------

def lhs(n: int, d: int, seed: int = 0) -> np.ndarray:
    """Latin Hypercube Sampling в [0;1]."""
    rng = np.random.default_rng(seed)
    X = np.zeros((n, d))
    for j in range(d):
        perm = rng.permutation(n)
        X[:, j] = (perm + rng.random(n)) / n
    return X


def load_model(py_path: str):
    here = Path(__file__).resolve().parent
    resolved_path, messages = resolve_project_py_path(
        py_path,
        here=here,
        kind="модель",
        default_path=None,
    )
    for msg in messages:
        try:
            print(msg)
        except Exception:
            pass
    return load_python_module_from_path(Path(resolved_path), 'pneumo_model')



# ---------------------------
# Multiprocessing (Windows-safe)
# ---------------------------
# ProcessPoolExecutor в Windows использует pickle. Поэтому:
# - функции воркера должны быть на уровне модуля (не вложенные),
# - модель лучше грузить один раз в каждом процессе через initializer.

_GLOBAL_MODEL = None
_GLOBAL_CFG = None

def _init_pool_worker(model_path: str, cfg: Dict[str, Any]):
    global _GLOBAL_MODEL, _GLOBAL_CFG

    # В воркерах multiprocessing принудительно ограничиваем OpenMP/BLAS threadpools до 1,
    # чтобы N процессов не пытались каждый использовать все ядра (оверсабскрипция).
    # Это повышает реальную загрузку CPU и ускоряет wall-time.
    _force_native_thread_limits(1)

    _GLOBAL_MODEL = load_model(model_path)
    _GLOBAL_CFG = cfg

def _pool_worker(payload: Tuple[int, Dict[str, Any]]):
    """Оценка одного кандидата в отдельном процессе.

    Возвращаем строку-словарь всегда (даже при ошибке), чтобы не ронять пул.
    """
    idx, p = payload
    try:
        return eval_candidate(_GLOBAL_MODEL, idx, p, _GLOBAL_CFG)
    except Exception as e:
        return make_error_row(idx, p, e)


# ---------------------------
# Генераторы профиля дороги
# ---------------------------

def smootherstep5(u: float) -> float:
    """5‑й порядок smootherstep: C2‑гладкая стыковка 0→1.

    s(u)=6u^5-15u^4+10u^3, u∈[0,1]
    На концах: s'=0 и s''=0 (нет скачка скорости/ускорения профиля).
    """
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    return (u*u*u) * (u*(u*6.0 - 15.0) + 10.0)


def bump_C2_time(
    t: float,
    t0: float,
    dur: float,
    A: float,
    ramp_ratio: float = 0.25,
    flat_ratio: float = None
) -> float:
    """C2‑гладкая 'кочка/яма' во времени.

    ramp_ratio — доля длительности на один плавный участок (подъём/спуск).
    flat_ratio (если задан) — доля длительности на горизонтальную полку.
    """
    if dur <= 0.0:
        return 0.0

    rr = float(ramp_ratio)
    rr = max(0.0, min(0.49, rr))  # два рампа не должны «съесть» весь интервал
    t_ramp = rr * dur

    if flat_ratio is None:
        t_flat = dur - 2.0 * t_ramp
    else:
        fr = max(0.0, min(1.0, float(flat_ratio)))
        t_flat = fr * dur
        # если пользователь дал flat_ratio, поджимаем рампы, чтобы всё влезло
        t_ramp = max(1e-6, 0.5 * (dur - t_flat))

    if t_flat < 0.0:
        t_ramp = 0.5 * dur
        t_flat = 0.0

    t1 = t0 + t_ramp
    t2 = t1 + t_flat
    t3 = t2 + t_ramp

    if t < t0 or t > t3:
        return 0.0
    if t <= t1:
        u = (t - t0) / max(1e-9, t_ramp)
        return A * smootherstep5(u)
    if t <= t2:
        return A

    u = (t - t2) / max(1e-9, t_ramp)
    return A * (1.0 - smootherstep5(u))


# ---------------------------
# Генераторы профиля дороги
# ---------------------------

def road_bump_single_wheel(idx: int, A: float, t0: float, dur: float, ramp_ratio: float = 0.25):
    """C2‑гладкая кочка на одном колесе."""
    def r(t):
        z = np.zeros(4, dtype=float)
        z[idx] = bump_C2_time(t, t0=t0, dur=dur, A=A, ramp_ratio=ramp_ratio)
        return z
    return r


def road_bump_diag_tracks(
    A: float,
    t0: float,
    dur: float,
    v: float,
    angle_deg_from_perp: float,
    track_m: float,
    wheelbase_m: float,
    ramp_ratio: float = 0.25,
):
    """Диагональная кочка через два профиля колеи (левый/правый) + задержка по базе.

    Это соответствует твоей концепции:
    - есть rL(x) и rR(x) (две колеи),
    - задние колёса получают тот же профиль, но со сдвигом x−wheelbase,
    - диагональность задаём *сдвигом профилей*, а не «поднять два колеса».

    angle_deg_from_perp — угол линии кочки относительно линии, перпендикулярной движению.
      0°  => поперечная кочка (лево/право синхронно), dx=0
      >0° => правая колея встречает кочку позже (dx>0)
      <0° => правая колея встречает кочку раньше (dx<0)

    dx_lr = track * tan(angle)
    """
    v = max(1e-6, float(v))
    ang = math.radians(float(angle_deg_from_perp))
    dx_lr = float(track_m) * math.tan(ang)

    # Хотим, чтобы первое ПЕРЕДНЕЕ колесо начинало кочку ровно в t0.
    # Поэтому переносим обе колеи так, чтобы min(xL0, xR0)=0.
    xL0 = max(0.0, -dx_lr)   # если dx_lr<0 (правая раньше) — левую сдвигаем вперёд
    xR0 = max(0.0, +dx_lr)   # если dx_lr>0 (правая позже) — правую сдвигаем вперёд

    t_LF = t0 + xL0 / v
    t_RF = t0 + xR0 / v
    dt_fb = float(wheelbase_m) / v
    t_LR = t_LF + dt_fb
    t_RR = t_RF + dt_fb

    def r(t):
        z = np.zeros(4, dtype=float)
        # индексация колёс: 0=ЛП, 1=ПП, 2=ЛЗ, 3=ПЗ
        z[0] = bump_C2_time(t, t0=t_LF, dur=dur, A=A, ramp_ratio=ramp_ratio)
        z[1] = bump_C2_time(t, t0=t_RF, dur=dur, A=A, ramp_ratio=ramp_ratio)
        z[2] = bump_C2_time(t, t0=t_LR, dur=dur, A=A, ramp_ratio=ramp_ratio)
        z[3] = bump_C2_time(t, t0=t_RR, dur=dur, A=A, ramp_ratio=ramp_ratio)
        return z

    return r


def road_bump_diag(A: float, t0: float, dur: float):
    """Совместимость со старым форматом: если угол/скорость не заданы.

    По умолчанию берём:
    - v=10 м/с (~36 км/ч)
    - угол=+35° от перпендикуляра (правая колея позже)
    - геометрию: колея 1.2, база 2.3
    """
    return road_bump_diag_tracks(
        A=A, t0=t0, dur=dur,
        v=10.0,
        angle_deg_from_perp=35.0,
        track_m=1.2,
        wheelbase_m=2.3,
        ramp_ratio=0.25,
    )


# ---------------------------
# Формирование тестов
# ---------------------------

def make_test_roll(t_step: float, ay: float):
    return {
        'ay': float(ay),
        "ay_func": (lambda t: ay if t > t_step else 0.0),
        "ax_func": (lambda t: 0.0),
        "road_func": (lambda t: np.zeros(4)),
        "t_step": t_step,
        "описание": f"Ступень ay={ay} м/с² после {t_step} с"
    }


def make_test_pitch(t_step: float, ax: float):
    return {
        'ax': float(ax),
        "ay_func": (lambda t: 0.0),
        "ax_func": (lambda t: ax if t > t_step else 0.0),
        "road_func": (lambda t: np.zeros(4)),
        "t_step": t_step,
        "описание": f"Ступень ax={ax} м/с² после {t_step} с"
    }


def make_test_micro_sin(A: float, f: float):
    return {
        'A': float(A),
        'f': float(f),
        "ay_func": (lambda t: 0.0),
        "ax_func": (lambda t: 0.0),
        "road_func": (lambda t: (A * math.sin(2 * math.pi * f * t)) * np.ones(4)),
        "t_step": 0.0,
        "описание": f"Синфазная синусоида дороги A={A} м, f={f} Гц"
    }


def make_test_micro_antiphase(A: float, f: float):
    def road(t):
        s = A * math.sin(2 * math.pi * f * t)
        return np.array([+s, -s, +s, -s], dtype=float)
    return {
        'A': float(A),
        'f': float(f),
        "ay_func": (lambda t: 0.0),
        "ax_func": (lambda t: 0.0),
        "road_func": road,
        "t_step": 0.0,
        "описание": f"Лево/право разнофазная синусоида A={A} м, f={f} Гц"
    }


def make_test_combo_roll_plus_micro(t_step: float, ay: float, A: float, f: float):
    def road(t):
        return (A * math.sin(2 * math.pi * f * t)) * np.ones(4)
    return {
        'ay': float(ay),
        'A': float(A),
        'f': float(f),
        "ay_func": (lambda t: ay if t > t_step else 0.0),
        "ax_func": (lambda t: 0.0),
        "road_func": road,
        "t_step": t_step,
        "описание": f"Комбо: ay={ay} + синфаза A={A} f={f}"
    }


def make_test_bump_single(idx: int, A: float, t0: float, dur: float, ramp_ratio: float = 0.25):
    """Кочка/яма на одном колесе (C2‑гладко)."""
    return {
        'idx': int(idx),
        'A': float(A),
        't0': float(t0),
        'dur': float(dur),
        'ramp_ratio': float(ramp_ratio),
        "ay_func": (lambda t: 0.0),
        "ax_func": (lambda t: 0.0),
        "road_func": road_bump_single_wheel(idx=idx, A=A, t0=t0, dur=dur, ramp_ratio=ramp_ratio),
        "t_step": t0,
        "описание": f"Кочка колесо={idx}, A={A} м, dur={dur} c, ramp={ramp_ratio:.2f}"
    }


def make_test_bump_diag(
    A: float,
    t0: float,
    dur: float,
    v: float,
    angle_deg_from_perp: float,
    track_m: float,
    wheelbase_m: float,
    ramp_ratio: float = 0.25,
):
    """Диагональная кочка как сдвиг левой/правой колеи + задержка по базе."""
    return {
        'A': float(A),
        't0': float(t0),
        'dur': float(dur),
        'v': float(v),
        'angle_deg_from_perp': float(angle_deg_from_perp),
        'track_m': float(track_m),
        'wheelbase_m': float(wheelbase_m),
        'ramp_ratio': float(ramp_ratio),
        "ay_func": (lambda t: 0.0),
        "ax_func": (lambda t: 0.0),
        "road_func": road_bump_diag_tracks(
            A=A, t0=t0, dur=dur,
            v=v,
            angle_deg_from_perp=angle_deg_from_perp,
            track_m=track_m,
            wheelbase_m=wheelbase_m,
            ramp_ratio=ramp_ratio,
        ),
        "t_step": t0,
        "описание": f"Диагональная кочка A={A} м, dur={dur} c, v={v} м/с, угол={angle_deg_from_perp}°"
    }


# ---------------------------
# Метрики/запасы
# ---------------------------

def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def first_cross_time(t: np.ndarray, y: np.ndarray, thr: float, t_after: float, margin: float = 0.0) -> float:
    """Время первого превышения y > thr+margin после t_after."""
    mask = (t >= t_after) & (y > (thr + margin))
    if np.any(mask):
        return float(t[np.argmax(mask)])
    return float("inf")


def compute_body_acc_rms(df: pd.DataFrame, col_z: str = "перемещение_рамы_z_м", t_skip: float = 0.2) -> float:
    t = df["время_с"].to_numpy()
    z = df[col_z].to_numpy()
    if len(t) < 5:
        return float("nan")
    dt = float(np.mean(np.diff(t)))
    zdd = np.gradient(np.gradient(z, dt), dt)
    i0 = int(max(0, t_skip / dt))
    return rms(zdd[i0:])


def energy_from_frames(df_energy_drossel: Optional[pd.DataFrame], df_energy_edges: Optional[pd.DataFrame]) -> Tuple[float, float, float]:
    E_d = float(df_energy_drossel["энергия_рассеяна_Дж"].sum()) if df_energy_drossel is not None else 0.0
    E_tot = float(df_energy_edges["энергия_Дж"].sum()) if df_energy_edges is not None else 0.0
    share = (E_d / E_tot) if E_tot > 1e-9 else 0.0
    return E_d, E_tot, share


def tire_lift_metrics(df: pd.DataFrame) -> Tuple[float, float]:
    """(доля времени когда хотя бы одно колесо в воздухе, минимальная нормальная сила)"""
    cols_air = ["колесо_в_воздухе_ЛП", "колесо_в_воздухе_ПП", "колесо_в_воздухе_ЛЗ", "колесо_в_воздухе_ПЗ"]
    cols_F = ["нормальная_сила_шины_ЛП_Н", "нормальная_сила_шины_ПП_Н", "нормальная_сила_шины_ЛЗ_Н", "нормальная_сила_шины_ПЗ_Н"]
    air = df[cols_air].to_numpy()
    frac_any = float((air.max(axis=1) > 0).mean())
    Fmin = float(df[cols_F].to_numpy().min())
    return frac_any, Fmin


def tire_lift_metrics_per_wheel(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, float]:
    """Подробные метрики по контакту/отрыву для каждого колеса.

    Важно: делаем НЕ флажки, а «запасы» (непрерывные величины), чтобы оптимизатор мог работать градиентно/эвристически.

    Обозначения:
    - Fz(t) = нормальная сила шины (Н). Отрыв соответствует Fz<=0 (или флагу колесо_в_воздухе).
    - «Запас до отрыва» = min_t Fz(t)  (Н). Если отрицательный — контакт реально терялся.
    - Проценты считаем относительно статической нагрузки без учёта пневмо‑сил:
        F_stat = (m_рамы/4 + m_неподрессоренная)*g
    """
    g = 9.81
    m_body = float(params.get("масса_рамы", 600.0))
    m_w = float(params.get("масса_неподрессоренная_на_угол", 15.0))
    F_stat = (m_body * g / 4.0) + (m_w * g)

    out: Dict[str, float] = {}
    mins = []
    for c in ["ЛП", "ПП", "ЛЗ", "ПЗ"]:
        F = df[f"нормальная_сила_шины_{c}_Н"].to_numpy(dtype=float)
        air = df[f"колесо_в_воздухе_{c}"].to_numpy(dtype=float)

        Fmin = float(np.min(F))
        mins.append(Fmin)

        out[f"запас_до_отрыва_{c}_Н"] = Fmin
        out[f"запас_до_отрыва_{c}_доля_стат"] = float(Fmin / max(1e-6, F_stat))
        out[f"доля_времени_отрыв_{c}"] = float(np.mean(air))

        # то, что вы просили явно в KPI:
        out[f"контакт_потерян_{c}"] = float(1.0 if np.any(air > 0.5) else 0.0)
        out[f"мин_зазор_до_отрыва_{c}_Н"] = Fmin
        out[f"мин_зазор_до_отрыва_{c}_%стат"] = float(100.0 * Fmin / max(1e-6, F_stat))

    # агрегаты по всем колёсам
    out["мин_зазор_до_отрыва_все_Н"] = float(np.min(np.array(mins, dtype=float))) if len(mins) else float("nan")
    out["мин_зазор_до_отрыва_все_%стат"] = float(100.0 * out["мин_зазор_до_отрыва_все_Н"] / max(1e-6, F_stat))

    return out


def _get_float_first(params: Dict[str, Any], keys: list[str], fallback: float) -> float:
    """Return first parseable float from params for any key in keys, otherwise fallback."""
    for k in keys:
        if k in params:
            v = params.get(k)
            if v is None:
                continue
            try:
                return float(v)
            except Exception:
                continue
    return float(fallback)


def rod_margin_and_speed(df: pd.DataFrame, params: Dict[str, Any], stroke_m_default: float = 0.250) -> Dict[str, float]:
    """Метрики по штокам: запас до упора и скорость (учёт Ц1/Ц2).

    Поддерживаем два формата колонок в df_main:
      1) Старый (один шток на угол):
           положение_штока_ЛП_м ... положение_штока_ПЗ_м
           скорость_штока_ЛП_м_с ... скорость_штока_ПЗ_м_с
      2) Новый (отдельно по группам цилиндров):
           положение_штока_Ц1_ЛП_м, положение_штока_Ц2_ЛП_м, ...
           скорость_штока_Ц1_ЛП_м_с, скорость_штока_Ц2_ЛП_м_с, ...

    Параметры хода:
      - ход_штока (fallback)
      - ход_штока_Ц1_перед_м / ход_штока_Ц1_зад_м
      - ход_штока_Ц2_перед_м / ход_штока_Ц2_зад_м
    Если модель не отдаёт Ц2-колонки — метрики считаются только по доступным данным.

    запас до упора (м) = min_t min(s(t), stroke - s(t)).

    Возвращаем:
      - старые ключи (без префикса Ц1/Ц2) как "worst-case" по доступным группам
      - дополнительные ключи с префиксом Ц1_/Ц2_ для диагностики
    """
    out: Dict[str, float] = {}

    # Ходы по группам (front/rear). Сохраняем совместимость с альтернативными ключами.
    stroke_global = _get_float_first(params, ["ход_штока", "stroke_m"], stroke_m_default)
    stroke_C1_front = _get_float_first(params, ["ход_штока_Ц1_перед_м", "ход_Ц1_перед_м"], stroke_global)
    stroke_C1_rear  = _get_float_first(params, ["ход_штока_Ц1_зад_м",  "ход_Ц1_зад_м"],  stroke_global)
    stroke_C2_front = _get_float_first(params, ["ход_штока_Ц2_перед_м", "ход_Ц2_перед_м"], stroke_global)
    stroke_C2_rear  = _get_float_first(params, ["ход_штока_Ц2_зад_м",  "ход_Ц2_зад_м"],  stroke_global)

    def stroke_for(cyl: str, corner: str) -> float:
        front = corner in ("ЛП", "ПП")
        if cyl == "Ц1":
            return float(stroke_C1_front if front else stroke_C1_rear)
        if cyl == "Ц2":
            return float(stroke_C2_front if front else stroke_C2_rear)
        return float(stroke_global)

    corners = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    cyls = ["Ц1", "Ц2"]

    # Внутренние накопители для агрегатов
    per_corner_margin = {}  # corner -> float
    per_corner_speed = {}   # corner -> float
    per_cyl_margins = {"Ц1": [], "Ц2": []}
    per_cyl_speeds = {"Ц1": [], "Ц2": []}

    for c in corners:
        corner_margins = []
        corner_speeds = []

        # --- Ц1 ---
        s_c1 = df.get(f"положение_штока_Ц1_{c}_м")
        v_c1 = df.get(f"скорость_штока_Ц1_{c}_м_с")
        if s_c1 is None:
            s_c1 = df.get(f"положение_штока_{c}_м")
        if v_c1 is None:
            v_c1 = df.get(f"скорость_штока_{c}_м_с")
        if s_c1 is not None and v_c1 is not None:
            s = s_c1.to_numpy(dtype=float)
            v = v_c1.to_numpy(dtype=float)
            L = stroke_for("Ц1", c)
            if L > 0:
                m = float(np.min(np.minimum(s, L - s)))
            else:
                m = float("nan")
            sp = float(np.max(np.abs(v)))
            out[f"мин_запас_до_упора_штока_Ц1_{c}_м"] = m
            out[f"макс_скорость_штока_Ц1_{c}_м_с"] = sp
            corner_margins.append(m)
            corner_speeds.append(sp)
            per_cyl_margins["Ц1"].append(m)
            per_cyl_speeds["Ц1"].append(sp)
        else:
            out[f"мин_запас_до_упора_штока_Ц1_{c}_м"] = float("nan")
            out[f"макс_скорость_штока_Ц1_{c}_м_с"] = float("nan")

        # --- Ц2 (если модель отдаёт колонки) ---
        s_c2 = df.get(f"положение_штока_Ц2_{c}_м")
        v_c2 = df.get(f"скорость_штока_Ц2_{c}_м_с")
        if s_c2 is not None and v_c2 is not None:
            s = s_c2.to_numpy(dtype=float)
            v = v_c2.to_numpy(dtype=float)
            L = stroke_for("Ц2", c)
            if L > 0:
                m = float(np.min(np.minimum(s, L - s)))
            else:
                m = float("nan")
            sp = float(np.max(np.abs(v)))
            out[f"мин_запас_до_упора_штока_Ц2_{c}_м"] = m
            out[f"макс_скорость_штока_Ц2_{c}_м_с"] = sp
            corner_margins.append(m)
            corner_speeds.append(sp)
            per_cyl_margins["Ц2"].append(m)
            per_cyl_speeds["Ц2"].append(sp)
        else:
            out[f"мин_запас_до_упора_штока_Ц2_{c}_м"] = float("nan")
            out[f"макс_скорость_штока_Ц2_{c}_м_с"] = float("nan")

        # --- Worst-case по углу (совместимость со старым форматом) ---
        cm = float(np.nanmin(np.array(corner_margins, dtype=float))) if corner_margins else float("nan")
        cs = float(np.nanmax(np.array(corner_speeds, dtype=float))) if corner_speeds else float("nan")
        out[f"мин_запас_до_упора_штока_{c}_м"] = cm
        out[f"макс_скорость_штока_{c}_м_с"] = cs
        per_corner_margin[c] = cm
        per_corner_speed[c] = cs

    # Агрегаты
    out["мин_запас_до_упора_штока_все_м"] = float(np.nanmin(np.array(list(per_corner_margin.values()), dtype=float)))
    out["макс_скорость_штока_все_м_с"] = float(np.nanmax(np.array(list(per_corner_speed.values()), dtype=float)))

    for cyl in cyls:
        mm = float(np.nanmin(np.array(per_cyl_margins[cyl], dtype=float))) if per_cyl_margins[cyl] else float("nan")
        ss = float(np.nanmax(np.array(per_cyl_speeds[cyl], dtype=float))) if per_cyl_speeds[cyl] else float("nan")
        out[f"мин_запас_до_упора_штока_{cyl}_все_м"] = mm
        out[f"макс_скорость_штока_{cyl}_все_м_с"] = ss

    # Кто лимитирует по ходу (удобно для отладки)
    # Выбираем по минимальному агрегату (игнорируя NaN).
    lim = {cyl: out.get(f"мин_запас_до_упора_штока_{cyl}_все_м", float("nan")) for cyl in cyls}
    try:
        best = min((cyl for cyl in cyls if np.isfinite(lim.get(cyl, float("nan")))), key=lambda k: float(lim[k]))
    except Exception:
        best = ""
    out["шток_лимитирующий_группа"] = str(best)

    return out
def запас_до_пробоя_крен_тангаж(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, float]:
    """Непрерывные метрики запаса до «пробоя» по крену/тангажу.

    ДВА уровня порога:
      1) Геометрический порог опрокидывания (проекция ЦМ выходит за опору).
      2) Эксплуатационный лимит (комфорт/управляемость), задаётся параметрами:
           - лимит_пробоя_крен_град
           - лимит_пробоя_тангаж_град

    Если эксплуатационный лимит задан — используем MIN(геометрия, эксплуатационный),
    чтобы не получить «лимит» выше реального опрокидывания.

    Выход:
      - критический_крен_геом_град, критический_тангаж_геом_град
      - критический_крен_град, критический_тангаж_град (используемые для запаса)
      - запас_до_пробоя_крен_град, запас_до_пробоя_тангаж_град (может быть < 0)
      - запас_до_пробоя_крен_проц, запас_до_пробоя_тангаж_проц (может быть < 0)

    Важно: это KPI/штраф через «запас», а не стоп‑условие.
    """
    track = float(params.get('колея', 1.2))
    wheelbase = float(params.get('база', 2.3))

    # те же допущения по габаритам/ЦМ, что и в модели
    W = float(params.get('ширина_рамы', 0.3 * track))
    H = float(params.get('высота_рамы', 2.0 * W))
    h_cg = float(params.get('высота_центра_масс', H / 2.0))

    # 1) Геометрический порог опрокидывания
    phi_crit_geom = math.atan((track / 2.0) / max(1e-6, h_cg))
    theta_crit_geom = math.atan((wheelbase / 2.0) / max(1e-6, h_cg))
    phi_crit_geom_deg = float(np.degrees(phi_crit_geom))
    theta_crit_geom_deg = float(np.degrees(theta_crit_geom))

    # 2) Эксплуатационные лимиты (если заданы пользователем)
    phi_user = params.get('лимит_пробоя_крен_град', None)
    theta_user = params.get('лимит_пробоя_тангаж_град', None)

    if phi_user is None:
        phi_crit_deg = phi_crit_geom_deg
    else:
        phi_crit_deg = min(phi_crit_geom_deg, float(phi_user))

    if theta_user is None:
        theta_crit_deg = theta_crit_geom_deg
    else:
        theta_crit_deg = min(theta_crit_geom_deg, float(theta_user))

    roll_max = max_abs_deg(df, 'крен_phi_рад')
    pitch_max = max_abs_deg(df, 'тангаж_theta_рад')

    margin_roll = float(phi_crit_deg - roll_max)
    margin_pitch = float(theta_crit_deg - pitch_max)

    out = {
        'критический_крен_геом_град': phi_crit_geom_deg,
        'критический_тангаж_геом_град': theta_crit_geom_deg,
        'критический_крен_град': float(phi_crit_deg),
        'критический_тангаж_град': float(theta_crit_deg),
        'запас_до_пробоя_крен_град': margin_roll,
        'запас_до_пробоя_тангаж_град': margin_pitch,
        'запас_до_пробоя_крен_проц': float(100.0 * margin_roll / max(1e-6, phi_crit_deg)),
        'запас_до_пробоя_тангаж_проц': float(100.0 * margin_pitch / max(1e-6, theta_crit_deg)),
    }
    return out
def settle_time_roll(df: pd.DataFrame, t_step: float, band_min_deg: float = 0.5, band_ratio: float = 0.20) -> Dict[str, float]:
    """Время успокоения крена после t_step.

    Идея: после ступеньки инерции крен должен не только "включить Pmid", но и реально уменьшиться.
    Определение:
      - считаем пик |phi| после t_step
      - задаём полосу: band = max(band_min_deg, band_ratio * peak)
      - время успокоения = последний момент времени, когда |phi| > band, минус t_step
        (то есть после этого момента крен остаётся в полосе до конца теста).
    """
    t = df["время_с"].to_numpy(dtype=float)
    phi_deg = df["крен_phi_рад"].to_numpy(dtype=float) * 180.0 / math.pi
    mask = t >= t_step
    if not np.any(mask):
        return {
            "крен_peak_град": float(np.max(np.abs(phi_deg))) if len(phi_deg) else 0.0,
            "крен_остаточный_град": float(abs(phi_deg[-1])) if len(phi_deg) else 0.0,
            "время_успокоения_крен_с": float("inf"),
            "полоса_успокоения_град": float("nan"),
        }
    phi_abs = np.abs(phi_deg[mask])
    peak = float(np.max(phi_abs))
    band = max(float(band_min_deg), float(band_ratio) * peak)
    # если пика нет — значит крена нет
    if peak <= 1e-12:
        return {
            "крен_peak_град": 0.0,
            "крен_остаточный_град": float(abs(phi_deg[-1])) if len(phi_deg) else 0.0,
            "время_успокоения_крен_с": 0.0,
            "полоса_успокоения_град": band,
        }
    # последний выход из полосы
    out_of_band = np.abs(phi_deg) > band
    out_of_band &= (t >= t_step)
    if not np.any(out_of_band):
        t_settle = 0.0
    else:
        t_last = float(t[np.where(out_of_band)[0][-1]])
        t_settle = max(0.0, t_last - t_step)
    return {
        "крен_peak_град": peak,
        "крен_остаточный_град": float(abs(phi_deg[-1])) if len(phi_deg) else 0.0,
        "время_успокоения_крен_с": float(t_settle),
        "полоса_успокоения_град": band,
    }


def max_abs_deg(df: pd.DataFrame, col: str) -> float:
    return float(np.max(np.abs(df[col].to_numpy())) * 180.0 / math.pi)


# ---------------------------
# Оценка кандидата
# ---------------------------



# ---------------------------
# Optional time-series inputs from CSV (road / maneuvers)
# ---------------------------
#
# Motivation:
# - Optimization test suites should be able to reference real road profiles
#   and maneuvers captured from logs.
# - We cannot pass callables (road_func/ax_func/...) through multiprocessing
#   payloads on Windows (pickle), so we pass only file paths in the test dict.
# - The worker process compiles these CSV profiles into callables locally,
#   right before calling model.simulate().
#
# Supported fields in a suite record (rec) -> test dict:
#   - road_csv: path to CSV with time + 1 or 4 wheel vertical profiles
#   - axay_csv: path to CSV with time + ax/ay longitudinal/lateral acc
#
# CSV columns detection (case-insensitive):
#   time:  t, time, time_s, время, время_с
#   road:  z0..z3 OR z_lf,z_rf,z_lr,z_rr OR z_fl,z_fr,z_rl,z_rr
#          OR a single z column -> applied to all wheels
#   accel: ax, ay (or ax_mps2/ay_mps2)

_TS_CACHE: Dict[str, Dict[str, Any]] = {}


def _read_csv_cached(path: str) -> pd.DataFrame:
    """Read CSV with a very small in-process cache (mtime-based)."""
    p = os.path.abspath(path)
    try:
        st = os.stat(p)
        mtime = float(st.st_mtime)
        size = int(st.st_size)
    except Exception:
        mtime = -1.0
        size = -1

    key = p
    hit = _TS_CACHE.get(key)
    if hit and hit.get("mtime") == mtime and hit.get("size") == size and isinstance(hit.get("df"), pd.DataFrame):
        return hit["df"]

    # Try comma, then semicolon
    try:
        df = pd.read_csv(p, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(p, encoding="utf-8-sig", sep=";")

    _TS_CACHE[key] = {"mtime": mtime, "size": size, "df": df}
    return df


def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = list(df.columns)
    low = {str(c).strip().lower(): str(c) for c in cols}
    for c in candidates:
        k = str(c).strip().lower()
        if k in low:
            return low[k]
    return None


def _compile_timeseries_inputs(test: Dict[str, Any]) -> Dict[str, Any]:
    """Compile CSV references into callables inside the worker process."""
    if not isinstance(test, dict):
        return test

    # --- Road profile ---
    road_csv = str(test.get("road_csv") or "").strip()
    if road_csv and (not callable(test.get("road_func"))):
        df = _read_csv_cached(road_csv)
        tcol = _find_col(df, ["t", "time", "time_s", "время", "время_с", "времяс"]) or df.columns[0]
        t = np.asarray(df[tcol], dtype=float)

        # Wheel columns
        # priority: z0..z3
        zcols = [
            [_find_col(df, ["z0"]), _find_col(df, ["z1"]), _find_col(df, ["z2"]), _find_col(df, ["z3"])],
            [_find_col(df, ["z_lf", "z_fl", "z_lfront", "z_front_left"]),
             _find_col(df, ["z_rf", "z_fr", "z_rfront", "z_front_right"]),
             _find_col(df, ["z_lr", "z_rl", "z_lrear", "z_rear_left"]),
             _find_col(df, ["z_rr", "z_rright", "z_rear_right"])],
        ]

        use = None
        for cand in zcols:
            if all(c is not None for c in cand):
                use = cand
                break

        if use is None:
            # single-column fallback
            zsingle = _find_col(df, ["z", "road", "road_z", "z_m", "профиль", "профиль_м"])
            if zsingle is None:
                # last resort: second column
                zsingle = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            use = [zsingle, zsingle, zsingle, zsingle]

        Z = [np.asarray(df[c], dtype=float) for c in use]
        dZ = [np.gradient(z, t, edge_order=1) if len(t) >= 3 else np.zeros_like(z) for z in Z]

        def road_func(tt: float):
            x = float(tt)
            return np.array([np.interp(x, t, z) for z in Z], dtype=float)

        def road_dfunc(tt: float):
            x = float(tt)
            return np.array([np.interp(x, t, dz) for dz in dZ], dtype=float)

        test["road_func"] = road_func
        test["road_dfunc"] = road_dfunc

    # --- Maneuver profile (ax/ay) ---
    axay_csv = str(test.get("axay_csv") or "").strip()
    if axay_csv and ((not callable(test.get("ax_func"))) or (not callable(test.get("ay_func")))):
        df = _read_csv_cached(axay_csv)
        tcol = _find_col(df, ["t", "time", "time_s", "время", "время_с", "времяс"]) or df.columns[0]
        t = np.asarray(df[tcol], dtype=float)
        axcol = _find_col(df, ["ax", "ax_mps2", "a_x", "ускор_x", "ускорение_x"])
        aycol = _find_col(df, ["ay", "ay_mps2", "a_y", "ускор_y", "ускорение_y"])
        if axcol is None and len(df.columns) > 1:
            axcol = df.columns[1]
        if aycol is None and len(df.columns) > 2:
            aycol = df.columns[2]
        ax = np.asarray(df[axcol], dtype=float) if axcol is not None else np.zeros_like(t)
        ay = np.asarray(df[aycol], dtype=float) if aycol is not None else np.zeros_like(t)

        def ax_func(tt: float) -> float:
            return float(np.interp(float(tt), t, ax))

        def ay_func(tt: float) -> float:
            return float(np.interp(float(tt), t, ay))

        test.setdefault("ax_func", ax_func)
        test.setdefault("ay_func", ay_func)

    return test


def _collect_packaging_penalty_metrics(params: Dict[str, Any], df_main: pd.DataFrame) -> Dict[str, Any]:
    if not isinstance(df_main, pd.DataFrame) or df_main.empty:
        return {}
    meta = {
        "geometry": build_geometry_meta_from_base(params),
    }
    meta["packaging"] = build_packaging_block(meta, df_main)
    return summarize_anim_export_objective_metrics(meta)


def eval_candidate_once(model, params: Dict[str, Any], test: Dict[str, Any], dt: float, t_end: float, targets: Dict[str, float] | None = None) -> Dict[str, Any]:
    """Запуск одного теста; возвращает словарь метрик."""
    params_local = copy.deepcopy(params)
    test_local = copy.deepcopy(test)

    # Compile time-series inputs (road_csv / axay_csv) inside this worker process
    # (important for Windows multiprocessing / pickle safety).
    # Важно: НЕ проглатываем ошибки компиляции, иначе легко «тихо» запустить не тот сценарий.
    ts_compile_ok = 1
    ts_compile_error = ""
    try:
        test_local = _compile_timeseries_inputs(test_local)
    except Exception as e:
        ts_compile_ok = 0
        ts_compile_error = (f"{type(e).__name__}: {e}")[:300]
        # По умолчанию это фатально (strict), чтобы не оптимизировать/считать «не то».
        if bool(test_local.get('timeseries_strict', True)):
            raise RuntimeError("Time-series input compile failed: " + ts_compile_error) from e

    out = model.simulate(params_local, test_local, dt=dt, t_end=t_end)
    df_main = out[0]
    df_Ed = out[2]
    df_Eedges = out[5]
    df_Egroups = out[6]
    df_atm = out[7]

    Pmid = float(params["давление_Pmid_сброс"])
    t_step = float(test.get("t_step", 0.0))

    pR3 = df_main["давление_ресивер3_Па"].to_numpy()
    t = df_main["время_с"].to_numpy()
    pR3_max = float(np.max(pR3))

    # запасы по уставке
    margin_to_Pmid_bar = float((Pmid - pR3_max) / 1e5)      # >0 = НЕ дошли до жёсткого
    margin_over_Pmid_bar = float((pR3_max - Pmid) / 1e5)    # >0 = дошли/перешли

    t_cross = first_cross_time(t, pR3, Pmid, t_after=t_step, margin=300.0)
    has_cross = bool(np.isfinite(t_cross))

    # механика
    roll_max = max_abs_deg(df_main, "крен_phi_рад")
    pitch_max = max_abs_deg(df_main, "тангаж_theta_рад")

    # запас до пробоя по крену/тангажу (непрерывный KPI)
    breakdown = запас_до_пробоя_крен_тангаж(df_main, params)
    acc_rms = compute_body_acc_rms(df_main)

    lift_frac, Fmin = tire_lift_metrics(df_main)

    # подробные метрики отрыва по каждому колесу
    lift_per = tire_lift_metrics_per_wheel(df_main, params)

    # штоки: запас до упора + скорости
    # (учитываем Ц1/Ц2 и разные ходы перед/зад, если модель их отдаёт)
    rod_metrics = rod_margin_and_speed(df_main, params_local)

    # метрика "как быстро крен уменьшился" после t_step
    settle_metrics = settle_time_roll(df_main, t_step=t_step, band_min_deg=float(test.get('settle_band_min_deg', 0.5)), band_ratio=float(test.get('settle_band_ratio', 0.20)))

    # энергия
    E_d, E_tot, share_d = energy_from_frames(df_Ed, df_Eedges)

    # атмосфера
    m_to = float(df_atm["масса_в_атмосферу_кг"].iloc[0]) if (df_atm is not None and "масса_в_атмосферу_кг" in df_atm.columns) else 0.0
    m_from = float(df_atm["масса_из_атмосферы_кг"].iloc[0]) if (df_atm is not None and "масса_из_атмосферы_кг" in df_atm.columns) else 0.0

    # баланс энергии газа (если модель вернула соответствующие поля)
    Ebal_err = float(df_atm["баланс_энергии_ошибка_Дж"].iloc[0]) if (df_atm is not None and "баланс_энергии_ошибка_Дж" in df_atm.columns) else 0.0
    Ebal_err_rel = float(df_atm["баланс_энергии_ошибка_отн"].iloc[0]) if (df_atm is not None and "баланс_энергии_ошибка_отн" in df_atm.columns) else 0.0

    # 2‑й закон (если модель вернула соответствующие поля)
    Sgen_end = float(df_atm["энтропия_генерация_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_Дж_К" in df_atm.columns) else 0.0
    Xdest_end = float(df_atm["эксергия_разрушена_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_Дж" in df_atm.columns) else 0.0
    Xto_atm = float(df_atm["эксергия_в_атмосферу_Дж"].iloc[0]) if (df_atm is not None and "эксергия_в_атмосферу_Дж" in df_atm.columns) else 0.0
    Xfrom_atm = float(df_atm["эксергия_из_атмосферы_Дж"].iloc[0]) if (df_atm is not None and "эксергия_из_атмосферы_Дж" in df_atm.columns) else 0.0

    # остатки (неучтённые/численные/смешение)
    Srest_end = float(df_atm["энтропия_генерация_остаток_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_остаток_Дж_К" in df_atm.columns) else 0.0
    Xrest_end = float(df_atm["эксергия_разрушена_остаток_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_остаток_Дж" in df_atm.columns) else 0.0
    Sedges_end = float(df_atm["энтропия_генерация_по_элементам_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_по_элементам_Дж_К" in df_atm.columns) else 0.0
    Xedges_end = float(df_atm["эксергия_разрушена_по_элементам_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_по_элементам_Дж" in df_atm.columns) else 0.0
    # Декомпозиция необратимостей: теплопередача и остаток без теплопередачи (если модель вернула поля)
    Sheat_end = float(df_atm["энтропия_генерация_теплопередача_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_теплопередача_Дж_К" in df_atm.columns) else 0.0
    Xheat_end = float(df_atm["эксергия_разрушена_теплопередача_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_теплопередача_Дж" in df_atm.columns) else 0.0
    Srest_no_heat_end = float(df_atm["энтропия_генерация_остаток_без_теплопередачи_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_остаток_без_теплопередачи_Дж_К" in df_atm.columns) else float(Srest_end)
    Xrest_no_heat_end = float(df_atm["эксергия_разрушена_остаток_без_теплопередачи_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_остаток_без_теплопередачи_Дж" in df_atm.columns) else float(Xrest_end)
    top_heat_nodes = str(df_atm["топ_узлы_теплопередача"].iloc[0]) if (df_atm is not None and "топ_узлы_теплопередача" in df_atm.columns) else ""

    # Доп. декомпозиция 2‑го закона: падение давления и смешение
    S_pdrop_end = float(df_atm["энтропия_генерация_падение_давления_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_падение_давления_Дж_К" in df_atm.columns) else 0.0
    X_pdrop_end = float(df_atm["эксергия_разрушена_падение_давления_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_падение_давления_Дж" in df_atm.columns) else 0.0
    S_mix_end = float(df_atm["энтропия_генерация_смешение_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_смешение_Дж_К" in df_atm.columns) else 0.0
    X_mix_end = float(df_atm["эксергия_разрушена_смешение_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_смешение_Дж" in df_atm.columns) else 0.0
    S_rest_clean_end = float(df_atm["энтропия_генерация_остаток_без_тепло_без_смешения_Дж_К"].iloc[0]) if (df_atm is not None and "энтропия_генерация_остаток_без_тепло_без_смешения_Дж_К" in df_atm.columns) else 0.0
    X_rest_clean_end = float(df_atm["эксергия_разрушена_остаток_без_тепло_без_смешения_Дж"].iloc[0]) if (df_atm is not None and "эксергия_разрушена_остаток_без_тепло_без_смешения_Дж" in df_atm.columns) else 0.0
    top_mix_nodes = str(df_atm["топ_узлы_смешение"].iloc[0]) if (df_atm is not None and "топ_узлы_смешение" in df_atm.columns) else ""

    # механическая самопроверка (если модель возвращает)
    mech_sc_ok = int(df_atm["mech_selfcheck_ok"].iloc[0]) if (df_atm is not None and "mech_selfcheck_ok" in df_atm.columns) else 1
    mech_sc_msg = str(df_atm["mech_selfcheck_msg"].iloc[0]) if (df_atm is not None and "mech_selfcheck_msg" in df_atm.columns) else ""


    # энергия по категориям (выхлоп/дроссели/клапаны/регуляторы)
    E_exhaust = 0.0
    E_drossels = 0.0
    E_valves = 0.0
    E_regs = 0.0
    if df_Egroups is not None and ("группа" in df_Egroups.columns):
        def pick(group_name: str) -> float:
            sel = df_Egroups[df_Egroups["группа"].astype(str).str.lower().str.strip() == group_name]
            if len(sel) == 0:
                return 0.0
            return float(sel["энергия_Дж"].sum())

        E_exhaust = pick("выхлоп")
        E_drossels = pick("дроссель")
        E_valves = pick("клапан")
        E_regs = pick("регулятор")
    E_total_cat = float(E_exhaust + E_drossels + E_valves + E_regs)
    if E_total_cat <= 1e-12:
        E_total_cat = float(E_tot)
    share_exhaust = float(E_exhaust / E_total_cat) if E_total_cat > 0 else 0.0
    share_drossels = float(E_drossels / E_total_cat) if E_total_cat > 0 else 0.0
    share_valves = float(E_valves / E_total_cat) if E_total_cat > 0 else 0.0
    share_regs = float(E_regs / E_total_cat) if E_total_cat > 0 else 0.0
    share_max_cat = float(max(share_exhaust, share_drossels, share_valves, share_regs))

    # Эксергетический аудит по категориям (аналогично энергии)
    X_exhaust = 0.0
    X_drossels = 0.0
    X_valves = 0.0
    X_regs = 0.0
    X_heat = 0.0
    X_resid2 = 0.0
    X_mix_cat = 0.0
    X_resid3 = 0.0
    if df_Egroups is not None and ("группа" in df_Egroups.columns) and ("эксергия_разрушена_Дж" in df_Egroups.columns):
        def pickX(group_name: str) -> float:
            sel = df_Egroups[df_Egroups["группа"].astype(str).str.lower().str.strip() == group_name]
            if len(sel) == 0:
                return 0.0
            return float(sel["эксергия_разрушена_Дж"].sum())

        X_exhaust = pickX("выхлоп")
        X_drossels = pickX("дроссель")
        X_valves = pickX("клапан")
        X_regs = pickX("регулятор")
        X_heat = pickX("теплопередача")
        X_resid2 = pickX("остаток_без_теплопередачи")
        X_mix_cat = pickX("смешение")
        X_resid3 = pickX("остаток_без_тепло_без_смешения")

    # Доли эксергии считаем относительно полной разрушенной эксергии Xdest_end
    # (включая теплопередачу и остаток). Это более физически осмысленно для root-cause.
    X_total_all = float(Xdest_end)
    if X_total_all <= 1e-12:
        X_total_all = float(X_exhaust + X_drossels + X_valves + X_regs + X_heat + X_resid2 + X_mix_cat + X_resid3)

    shareX_exhaust = float(X_exhaust / X_total_all) if X_total_all > 0 else 0.0
    shareX_drossels = float(X_drossels / X_total_all) if X_total_all > 0 else 0.0
    shareX_valves = float(X_valves / X_total_all) if X_total_all > 0 else 0.0
    shareX_regs = float(X_regs / X_total_all) if X_total_all > 0 else 0.0
    shareX_heat = float(X_heat / X_total_all) if X_total_all > 0 else 0.0
    shareX_resid2 = float(X_resid2 / X_total_all) if X_total_all > 0 else 0.0
    shareX_mix = float(X_mix_cat / X_total_all) if X_total_all > 0 else 0.0
    shareX_resid3 = float(X_resid3 / X_total_all) if X_total_all > 0 else 0.0
    shareX_max_cat = float(max(shareX_exhaust, shareX_drossels, shareX_valves, shareX_regs, shareX_heat, shareX_resid2, shareX_mix, shareX_resid3))

    # Топ по эксергии (группа и элементы) — для объяснения «почему плохо»
    top_X_group = ""
    top_X_group_share = 0.0
    if df_Egroups is not None and ("эксергия_разрушена_Дж" in df_Egroups.columns):
        try:
            g = df_Egroups.sort_values("эксергия_разрушена_Дж", ascending=False).iloc[0]
            top_X_group = str(g.get("группа", ""))
            if "доля_эксергии" in df_Egroups.columns:
                top_X_group_share = float(g.get("доля_эксергии", 0.0))
            else:
                top_X_group_share = float(float(g.get("эксергия_разрушена_Дж", 0.0)) / max(1e-12, float(Xdest_end)))
        except Exception:
            top_X_group = ""
            top_X_group_share = 0.0

    top_X_edges_str = ""
    if df_Eedges is not None and ("эксергия_разрушена_Дж" in df_Eedges.columns):
        try:
            topE = df_Eedges.sort_values("эксергия_разрушена_Дж", ascending=False).head(5)
            parts = []
            for _, r in topE.iterrows():
                xj = float(r.get("эксергия_разрушена_Дж", 0.0))
                if xj <= 0:
                    continue
                nm = str(r.get("элемент", ""))
                grp = str(r.get("группа", ""))
                parts.append(f"{nm}:{xj:.3g}J({grp})")
            top_X_edges_str = "; ".join(parts)
        except Exception:
            top_X_edges_str = ""

    metrics = {
        "pR3_max_бар": pR3_max / 1e5,
        "запас_до_Pmid_бар": margin_to_Pmid_bar,
        "запас_свыше_Pmid_бар": margin_over_Pmid_bar,
        "t_пересечения_Pmid_с": t_cross,
        "пересечение_Pmid_есть": has_cross,
        "ts_compile_ok": float(ts_compile_ok),
        "ts_compile_error": str(ts_compile_error),
        "крен_max_град": roll_max,
        "тангаж_max_град": pitch_max,
        "крен_peak_град": float(settle_metrics["крен_peak_град"]),
        "крен_остаточный_град": float(settle_metrics["крен_остаточный_град"]),
        "время_успокоения_крен_с": float(settle_metrics["время_успокоения_крен_с"]),
        "полоса_успокоения_крен_град": float(settle_metrics["полоса_успокоения_град"]),
        "RMS_ускор_рамы_м_с2": acc_rms,
        "доля_времени_отрыв": lift_frac,
        "Fmin_шины_Н": Fmin,
        # Энергетический аудит (категории)
        "энергия_все_сопр_Дж": E_tot,
        "энергия_выхлоп_Дж": E_exhaust,
        "энергия_дроссели_Дж": E_drossels,
        "энергия_клапаны_Дж": E_valves,
        "энергия_регуляторы_Дж": E_regs,
        "доля_энергии_выхлоп": share_exhaust,
        "доля_энергии_дроссели": share_drossels,
        "доля_энергии_клапаны": share_valves,
        "доля_энергии_регуляторы": share_regs,
        "доля_энергии_макс_категория": share_max_cat,

        # Диагностика: «все дроссели» как сумма по выбранному списку дросселей модели
        # (может включать и выхлопные SCO, если они в списке drossel_edges)
        "энергия_дроссели_включая_выхлоп_Дж": E_d,
        "доля_энергии_дроссели_включая_выхлоп": share_d,
        "масса_в_атмосферу_кг": m_to,
        "масса_из_атмосферы_кг": m_from,
        "ошибка_энергии_газа_Дж": Ebal_err,
        "ошибка_энергии_газа_отн": Ebal_err_rel,
        # 2‑й закон (диагностика необратимостей)
        "энтропия_генерация_Дж_К": Sgen_end,
        "эксергия_разрушена_Дж": Xdest_end,
        "эксергия_в_атмосферу_Дж": Xto_atm,
        "эксергия_из_атмосферы_Дж": Xfrom_atm,
        "энтропия_остаток_Дж_К": Srest_end,
        "эксергия_остаток_Дж": Xrest_end,
        "энтропия_теплопередача_Дж_К": Sheat_end,
        "эксергия_теплопередача_Дж": Xheat_end,
        "энтропия_остаток_без_теплопередачи_Дж_К": Srest_no_heat_end,
        "эксергия_остаток_без_теплопередачи_Дж": Xrest_no_heat_end,
        "топ_узлы_теплопередача": top_heat_nodes,
        "топ_узлы_смешение": top_mix_nodes,
        "энтропия_падение_давления_Дж_К": S_pdrop_end,
        "эксергия_падение_давления_Дж": X_pdrop_end,
        "энтропия_смешение_Дж_К": S_mix_end,
        "эксергия_смешение_Дж": X_mix_end,
        "энтропия_остаток_без_тепло_без_смешения_Дж_К": S_rest_clean_end,
        "эксергия_остаток_без_тепло_без_смешения_Дж": X_rest_clean_end,
        "энтропия_по_элементам_Дж_К": Sedges_end,
        "эксергия_по_элементам_Дж": Xedges_end,

        # Механическая самопроверка (если модель вернула)
        "mech_selfcheck_ok": int(mech_sc_ok),
        "mech_selfcheck_msg": str(mech_sc_msg),

        # Эксергетический аудит (категории)
        "эксергия_выхлоп_Дж": X_exhaust,
        "эксергия_дроссели_Дж": X_drossels,
        "эксергия_клапаны_Дж": X_valves,
        "эксергия_регуляторы_Дж": X_regs,
        "эксергия_теплопередача_Дж": X_heat,
        "эксергия_остаток_без_теплопередачи_Дж": X_resid2,
        "эксергия_смешение_Дж": X_mix_cat,
        "эксергия_остаток_без_тепло_без_смешения_Дж": X_resid3,
        "доля_эксергии_выхлоп": shareX_exhaust,
        "доля_эксергии_дроссели": shareX_drossels,
        "доля_эксергии_клапаны": shareX_valves,
        "доля_эксергии_регуляторы": shareX_regs,
        "доля_эксергии_теплопередача": shareX_heat,
        "доля_эксергии_остаток_без_теплопередачи": shareX_resid2,
        "доля_эксергии_смешение": shareX_mix,
        "доля_эксергии_остаток_без_тепло_без_смешения": shareX_resid3,
        "доля_эксергии_макс_категория": shareX_max_cat,

        # Топ «где теряем эксергию»
        "топ_эксергия_группа": top_X_group,
        "доля_эксергии_топ_группа": top_X_group_share,
        "топ_эксергия_элементы": top_X_edges_str,
    }

    # добавить запас до пробоя по крену/тангажу
    metrics.update(breakdown)

    # добавить по-колёсные запасы/отрывы
    metrics.update(lift_per)
    # добавить штоки
    metrics.update(rod_metrics)
    try:
        metrics.update(_collect_packaging_penalty_metrics(params_local, df_main))
        metrics["anim_export_packaging_metrics_ok"] = 1
        metrics["anim_export_packaging_metrics_error"] = ""
    except Exception as e:
        metrics["anim_export_packaging_metrics_ok"] = 0
        metrics["anim_export_packaging_metrics_error"] = (f"{type(e).__name__}: {e}")[:300]


    # ---- Root-cause: нарушения по target_* + физические причины ----
    # Собираем targets прямо из test (если тест пришёл из suite.json).
    targets_local = dict(targets) if isinstance(targets, dict) else {}
    if not targets_local:
        # fallback: если targets не передали, пытаемся взять их из test (на случай ручных вызовов)
        targets_local = {
            str(k).replace('target_', ''): float(v)
            for k, v in (test or {}).items()
            if isinstance(k, str) and k.startswith('target_') and (v is not None)
        }

    viol = {}  # name -> нормированная величина нарушения (как вклад в penalty)

    # 1) отрыв
    if 'макс_доля_отрыва' in targets_local:
        lift_max = float(targets_local['макс_доля_отрыва'])
        lift_frac = float(metrics.get('доля_времени_отрыв', 0.0))
        if lift_frac > lift_max:
            viol['отрыв_колёс'] = (lift_frac - lift_max) / max(0.05, (1.0 - lift_max))

    # 2) запас до Pmid
    if 'мин_запас_до_Pmid_бар' in targets_local:
        margin_min = float(targets_local['мин_запас_до_Pmid_бар'])
        margin_to = float(metrics.get('запас_до_Pmid_бар', 1e9))
        if margin_to < margin_min:
            viol['давление_Pmid'] = (margin_min - margin_to) / max(0.05, abs(margin_min) + 0.05)

    # 3) Fmin
    if 'мин_Fmin_Н' in targets_local:
        Fmin_min = float(targets_local['мин_Fmin_Н'])
        Fmin_val = float(metrics.get('Fmin_шины_Н', 0.0))
        if Fmin_val < Fmin_min:
            viol['низкая_прижимная_сила'] = (Fmin_min - Fmin_val) / max(100.0, abs(Fmin_min) + 100.0)

    # 4) пробой крена/тангажа
    if 'мин_запас_до_пробоя_крен_град' in targets_local:
        mr = float(metrics.get('запас_до_пробоя_крен_град', 0.0))
        mr_min = float(targets_local['мин_запас_до_пробоя_крен_град'])
        if mr < mr_min:
            viol['пробой_крен'] = (mr_min - mr) / max(1.0, abs(mr_min) + 1.0)

    if 'мин_запас_до_пробоя_тангаж_град' in targets_local:
        mp = float(metrics.get('запас_до_пробоя_тангаж_град', 0.0))
        mp_min = float(targets_local['мин_запас_до_пробоя_тангаж_град'])
        if mp < mp_min:
            viol['пробой_тангаж'] = (mp_min - mp) / max(1.0, abs(mp_min) + 1.0)

    # 5) упор штока
    if 'мин_запас_до_упора_штока_м' in targets_local:
        ms = float(metrics.get('мин_запас_до_упора_штока_все_м', 0.0))
        ms_min = float(targets_local['мин_запас_до_упора_штока_м'])
        if ms < ms_min:
            viol['упор_штока'] = (ms_min - ms) / max(0.001, abs(ms_min) + 0.001)

    # 6) скорость штока
    if 'лимит_скорости_штока_м_с' in targets_local:
        vmax = float(metrics.get('макс_скорость_штока_все_м_с', 0.0))
        vmax_lim = float(targets_local['лимит_скорости_штока_м_с'])
        if vmax > vmax_lim:
            viol['скорость_штока'] = (vmax - vmax_lim) / max(0.1, abs(vmax_lim) + 0.1)

    # 6b) Packaging / spring family geometry
    if 'мин_зазор_пружина_цилиндр_м' in targets_local:
        host_clearance = float(metrics.get('мин_зазор_пружина_цилиндр_м', float("nan")))
        host_clearance_min = float(targets_local['мин_зазор_пружина_цилиндр_м'])
        if np.isfinite(host_clearance) and host_clearance < host_clearance_min:
            viol['зазор_пружина_цилиндр'] = (host_clearance_min - host_clearance) / max(1e-4, abs(host_clearance_min) + 1e-4)

    if 'мин_зазор_пружина_пружина_м' in targets_local:
        pair_clearance = float(metrics.get('мин_зазор_пружина_пружина_м', float("nan")))
        pair_clearance_min = float(targets_local['мин_зазор_пружина_пружина_м'])
        if np.isfinite(pair_clearance) and pair_clearance < pair_clearance_min:
            viol['зазор_пружина_пружина'] = (pair_clearance_min - pair_clearance) / max(1e-4, abs(pair_clearance_min) + 1e-4)

    if 'макс_ошибка_midstroke_t0_м' in targets_local:
        midstroke_err = float(metrics.get('макс_ошибка_midstroke_t0_м', float("nan")))
        midstroke_lim = float(targets_local['макс_ошибка_midstroke_t0_м'])
        if np.isfinite(midstroke_err) and midstroke_err > midstroke_lim:
            viol['midstroke_t0'] = (midstroke_err - midstroke_lim) / max(1e-4, abs(midstroke_lim) + 1e-4)

    if 'мин_запас_до_coil_bind_пружины_м' in targets_local:
        coil_margin = float(metrics.get('мин_запас_до_coil_bind_пружины_м', float("nan")))
        coil_margin_min = float(targets_local['мин_запас_до_coil_bind_пружины_м'])
        if np.isfinite(coil_margin) and coil_margin < coil_margin_min:
            viol['coil_bind_пружины'] = (coil_margin_min - coil_margin) / max(1e-4, abs(coil_margin_min) + 1e-4)

    # 7) 1-й закон (баланс энергии газа)
    if 'макс_ошибка_энергии_газа_отн' in targets_local:
        err_rel = abs(float(metrics.get('ошибка_энергии_газа_отн', 0.0)))
        lim = float(targets_local['макс_ошибка_энергии_газа_отн'])
        if err_rel > lim:
            viol['баланс_энергии_газа'] = (err_rel - lim) / max(1e-6, lim)

    # 8) 2-й закон (необратимости)
    if 'макс_эксергия_разрушена_Дж' in targets_local:
        X = float(metrics.get('эксергия_разрушена_Дж', 0.0))
        limX = float(targets_local['макс_эксергия_разрушена_Дж'])
        if X > limX:
            viol['эксергия_разрушена'] = (X - limX) / max(1.0, abs(limX) + 1.0)

    if 'макс_энтропия_генерация_Дж_К' in targets_local:
        S = float(metrics.get('энтропия_генерация_Дж_К', 0.0))
        limS = float(targets_local['макс_энтропия_генерация_Дж_К'])
        if S > limS:
            viol['энтропия_генерация'] = (S - limS) / max(1e-6, abs(limS) + 1.0)


    # 8b) Декомпозиция 2-го закона: отдельные ограничения на теплопередачу/остаток (если нужны)
    if 'макс_эксергия_теплопередача_Дж' in targets_local:
        Xh = float(metrics.get('эксергия_теплопередача_Дж', 0.0))
        limXh = float(targets_local['макс_эксергия_теплопередача_Дж'])
        if Xh > limXh:
            viol['эксергия_теплопередача'] = (Xh - limXh) / max(1.0, abs(limXh) + 1.0)

    if 'макс_эксергия_остаток_без_теплопередачи_Дж' in targets_local:
        Xr2 = float(metrics.get('эксергия_остаток_без_теплопередачи_Дж', 0.0))
        limXr2 = float(targets_local['макс_эксергия_остаток_без_теплопередачи_Дж'])
        if Xr2 > limXr2:
            viol['эксергия_остаток_без_тепла'] = (Xr2 - limXr2) / max(1.0, abs(limXr2) + 1.0)

    if 'макс_энтропия_теплопередача_Дж_К' in targets_local:
        Sh = float(metrics.get('энтропия_теплопередача_Дж_К', 0.0))
        limSh = float(targets_local['макс_энтропия_теплопередача_Дж_К'])
        if Sh > limSh:
            viol['энтропия_теплопередача'] = (Sh - limSh) / max(1e-6, abs(limSh) + 1.0)

    if 'макс_энтропия_остаток_без_теплопередачи_Дж_К' in targets_local:
        Sr2 = float(metrics.get('энтропия_остаток_без_теплопередачи_Дж_К', 0.0))
        limSr2 = float(targets_local['макс_энтропия_остаток_без_теплопередачи_Дж_К'])
        if Sr2 > limSr2:
            viol['энтропия_остаток_без_тепла'] = (Sr2 - limSr2) / max(1e-6, abs(limSr2) + 1.0)


    # 8c) Декомпозиция 2-го закона: падение давления / смешение / остаток без тепло+смешения (опционально)
    if 'макс_эксергия_падение_давления_Дж' in targets_local:
        Xp = float(metrics.get('эксергия_падение_давления_Дж', 0.0))
        lim = float(targets_local['макс_эксергия_падение_давления_Дж'])
        if Xp > lim:
            viol['эксергия_падение_давления'] = (Xp - lim) / max(1.0, abs(lim) + 1.0)

    if 'макс_эксергия_смешение_Дж' in targets_local:
        Xm = float(metrics.get('эксергия_смешение_Дж', 0.0))
        lim = float(targets_local['макс_эксергия_смешение_Дж'])
        if Xm > lim:
            viol['эксергия_смешение'] = (Xm - lim) / max(1.0, abs(lim) + 1.0)

    if 'макс_эксергия_остаток_без_тепло_без_смешения_Дж' in targets_local:
        Xr = float(metrics.get('эксергия_остаток_без_тепло_без_смешения_Дж', 0.0))
        lim = float(targets_local['макс_эксергия_остаток_без_тепло_без_смешения_Дж'])
        if Xr > lim:
            viol['эксергия_остаток_без_тепло_без_смешения'] = (Xr - lim) / max(1.0, abs(lim) + 1.0)

    if 'макс_энтропия_падение_давления_Дж_К' in targets_local:
        Sp = float(metrics.get('энтропия_падение_давления_Дж_К', 0.0))
        lim = float(targets_local['макс_энтропия_падение_давления_Дж_К'])
        if Sp > lim:
            viol['энтропия_падение_давления'] = (Sp - lim) / max(1e-6, abs(lim) + 1.0)

    if 'макс_энтропия_смешение_Дж_К' in targets_local:
        Sm = float(metrics.get('энтропия_смешение_Дж_К', 0.0))
        lim = float(targets_local['макс_энтропия_смешение_Дж_К'])
        if Sm > lim:
            viol['энтропия_смешение'] = (Sm - lim) / max(1e-6, abs(lim) + 1.0)

    if 'макс_энтропия_остаток_без_тепло_без_смешения_Дж_К' in targets_local:
        Sr = float(metrics.get('энтропия_остаток_без_тепло_без_смешения_Дж_К', 0.0))
        lim = float(targets_local['макс_энтропия_остаток_без_тепло_без_смешения_Дж_К'])
        if Sr > lim:
            viol['энтропия_остаток_без_тепло_без_смешения'] = (Sr - lim) / max(1e-6, abs(lim) + 1.0)


    # Дополнительные физические объяснения (без targets): где «сжигаем» эксергию
    tags = []
    Xtot = float(metrics.get('эксергия_разрушена_Дж', 0.0))

    # доминирование выхлопа по эксергии
    if float(metrics.get('доля_эксергии_выхлоп', 0.0)) > 0.6 and Xtot > 1e-6:
        tags.append('эксергия_выхлоп_доминирует')

    # доминирование необратимостей теплопередачи (finite ΔT)
    if float(metrics.get('доля_эксергии_теплопередача', 0.0)) > 0.6 and Xtot > 1e-6:
        tags.append('эксергия_теплопередача_доминирует')

    # доминирование необратимостей смешения (много теплового/струйного смешения в узлах)
    if float(metrics.get('доля_эксергии_смешение', 0.0)) > 0.6 and Xtot > 1e-6:
        tags.append('эксергия_смешение_доминирует')

    # большой остаток эксергии БЕЗ тепло/смешения (численная необратимость/недоучтённые процессы)
    Xrest3 = float(metrics.get('эксергия_остаток_без_тепло_без_смешения_Дж', 0.0))
    if Xtot > 1e-12 and (Xrest3 / Xtot) > 0.25:
        tags.append('необратимости_остаток_без_тепло_без_смешения_высок')

    # большой остаток эксергии БЕЗ теплопередачи (смешение/численная необратимость/недоучтённые процессы)
    Xrest2 = float(metrics.get('эксергия_остаток_без_теплопередачи_Дж', 0.0))
    if Xtot > 1e-12 and (Xrest2 / Xtot) > 0.25:
        tags.append('необратимости_остаток_без_теплопередачи_высок')

    if float(metrics.get('число_пересечений_пружина_цилиндр', 0.0)) > 0.0:
        tags.append('пружина_цилиндр_интерференция')
    if float(metrics.get('число_пересечений_пружина_пружина', 0.0)) > 0.0:
        tags.append('пружина_пружина_интерференция')
    coil_margin = float(metrics.get('мин_запас_до_coil_bind_пружины_м', float("nan")))
    if np.isfinite(coil_margin) and coil_margin < 0.0:
        tags.append('coil_bind_пружины')

    # Итоговые поля
    if viol:
        top_name = max(viol, key=lambda k: float(viol[k]))
        metrics['топ_нарушение'] = str(top_name)
        metrics['топ_нарушение_оценка'] = float(viol[top_name])
        metrics['причины_нарушений'] = ';'.join(sorted([k for k,v in viol.items() if float(v) > 0.0]))
    else:
        metrics['топ_нарушение'] = ''
        metrics['топ_нарушение_оценка'] = 0.0
        metrics['причины_нарушений'] = ''

    metrics['причины_физика'] = ';'.join(tags)

    # --- Автономная верификация (автопроверки) ---
    try:
        try:
            from .verif_autochecks import check_candidate_metrics  # type: ignore
        except Exception:
            from verif_autochecks import check_candidate_metrics  # type: ignore

        v = check_candidate_metrics(metrics, params_local, test_local)
        if isinstance(v, dict):
            metrics.update(v)
    except Exception as e:
        # не валим оптимизацию из-за сбоя в модуле верификации: переводим в штраф
        metrics['верификация_ok'] = 0
        metrics['верификация_штраф'] = float(params_local.get('autoverif_penalty_nonfinite', 1e6))
        metrics['верификация_флаги'] = 'autoverif_exception'
        metrics['верификация_сообщение'] = (f"{type(e).__name__}: {e}")[:800]

    return metrics


def _stride_df(df: Any, stride: int) -> Any:
    """Best-effort downsample a pandas DataFrame by row stride.

    Используется только для логирования/осциллограмм (уменьшение размера файлов).
    Метрики/штрафы считаются по полному разрешению, поэтому здесь допускается
    упрощённое прореживание по времени.
    """
    try:
        s = int(stride)
    except Exception:
        s = 1
    if s <= 1:
        return df
    try:
        if isinstance(df, pd.DataFrame) and len(df) > 0:
            return df.iloc[::s].reset_index(drop=True)
    except Exception:
        return df
    return df


def _apply_stride_to_out(out: Any, stride: int) -> Any:
    """Return a copy of model.simulate(..., record_full=True) output with strided time-series tables."""
    try:
        s = int(stride)
    except Exception:
        s = 1
    if s <= 1:
        return out

    try:
        out_list = list(out)
    except Exception:
        return out

    # Наиболее важные тайм-серии:
    # 0=df_main, 1=df_drossel, 2=df_energy, 8=df_p, 9=df_mdot, 10=df_open
    for idx in (0, 1, 2, 8, 9, 10):
        if 0 <= idx < len(out_list):
            out_list[idx] = _stride_df(out_list[idx], s)
    return tuple(out_list)


def eval_candidate_once_full(
    model,
    params: Dict[str, Any],
    test: Dict[str, Any],
    dt: float,
    t_end: float,
    record_stride: int = 1,
    targets: Dict[str, float] | None = None,
) -> Tuple[Dict[str, Any], Any]:
    """Запуск одного теста с записью «осциллограмм».

    Зачем:
      - UI может сохранять осциллограммы (NPZ/CSV) для последующей калибровки.
      - Для этого нужен полный выход `model.simulate(..., record_full=True)`.

    Возвращает:
      (metrics_dict, out_full_like)
    где out_full_like — тот же формат, что возвращает модель при record_full=True,
    но с опциональным прореживанием по строкам (record_stride).

    ВАЖНО:
      - Метрики считаются **по полному** out (без прореживания), чтобы не терять пики.
      - Прореживание применяется только к сохраняемым тайм-сериям, чтобы уменьшить размер логов.
    """

    # 1) Полный прогон модели с записью узлов/рёбер.
    params_local = copy.deepcopy(params)
    test_local = copy.deepcopy(test)
    out_full = model.simulate(params_local, test_local, dt=dt, t_end=t_end, record_full=True)

    # 2) Метрики считаем, переиспользуя существующий eval_candidate_once()
    #    без повторного моделирования: подменяем model.simulate() на заранее вычисленный out.
    class _ModelProxy:
        def __init__(self, out_ref):
            self._out_ref = out_ref

        def simulate(self, _params, _test, dt: float = 0.0, t_end: float = 0.0):
            return self._out_ref

    metrics = eval_candidate_once(_ModelProxy(out_full), params, test, dt=dt, t_end=t_end, targets=targets)

    # 3) Прореживание для логов.
    out_save = _apply_stride_to_out(out_full, int(record_stride))
    return metrics, out_save


def candidate_penalty(m: Dict[str, float], targets: Dict[str, float]) -> float:
    """Непрерывный штраф за нарушения.

    ВАЖНО: штраф считается **только** по тем ограничениям, которые явно заданы в `targets`
    (т.е. присутствуют в строке теста как `target_*`). Если `targets` пустой — штраф = 0.

    Замечание по ключам:
      - `eval_candidate_once()` возвращает метрики с конкретными именами (например
        `доля_времени_отрыв`, `Fmin_шины_Н`, `запас_до_Pmid_бар`,
        `мин_запас_до_упора_штока_все_м`, `макс_скорость_штока_все_м_с`).
      - Здесь мы используем **те же** имена, иначе штраф становится некорректным.
    """
    pen = 0.0
    w = 1.0

    # 1) Контакт колёс (доля времени, когда хотя бы одно колесо "в отрыве")
    if 'макс_доля_отрыва' in targets:
        lift_frac = float(m.get('доля_времени_отрыв', 0.0))
        lift_max = float(targets['макс_доля_отрыва'])
        if lift_frac > lift_max:
            pen += w * (lift_frac - lift_max) / max(0.05, (1.0 - lift_max))

    # 2) Диагностика Pmid: запас по давлению в Ресивере3 до Pmid (в барах)
    #    + положительный запас  => pR3_max ниже Pmid
    #    + отрицательный запас  => pR3_max выше Pmid (перешли в "жёсткую" ветку)
    if 'мин_запас_до_Pmid_бар' in targets:
        margin_to_Pmid = float(m.get('запас_до_Pmid_бар', 1.0e9))
        margin_min = float(targets['мин_запас_до_Pmid_бар'])
        if margin_to_Pmid < margin_min:
            pen += w * (margin_min - margin_to_Pmid) / max(0.05, abs(margin_min) + 0.05)

    # 3) Минимальная прижимная сила (минимальная нормальная реакция шин)
    if 'мин_Fmin_Н' in targets:
        Fmin = float(m.get('Fmin_шины_Н', 0.0))
        Fmin_min = float(targets['мин_Fmin_Н'])
        if Fmin < Fmin_min:
            pen += w * (Fmin_min - Fmin) / max(100.0, abs(Fmin_min) + 100.0)

    # 4) Запасы до пробоя по крену/тангажу
    if 'мин_запас_до_пробоя_крен_град' in targets:
        margin_roll = float(m.get('запас_до_пробоя_крен_град', 0.0))
        margin_roll_min = float(targets['мин_запас_до_пробоя_крен_град'])
        if margin_roll < margin_roll_min:
            pen += w * (margin_roll_min - margin_roll) / max(1.0, abs(margin_roll_min) + 1.0)

    if 'мин_запас_до_пробоя_тангаж_град' in targets:
        margin_pitch = float(m.get('запас_до_пробоя_тангаж_град', 0.0))
        margin_pitch_min = float(targets['мин_запас_до_пробоя_тангаж_град'])
        if margin_pitch < margin_pitch_min:
            pen += w * (margin_pitch_min - margin_pitch) / max(1.0, abs(margin_pitch_min) + 1.0)

    # 5) Запас до упора штока (минимум по всем углам)
    if 'мин_запас_до_упора_штока_м' in targets:
        min_margin = float(m.get('мин_запас_до_упора_штока_все_м', 0.0))
        min_margin_min = float(targets['мин_запас_до_упора_штока_м'])
        if min_margin < min_margin_min:
            pen += w * (min_margin_min - min_margin) / max(0.001, abs(min_margin_min) + 0.001)

    # 6) Скорость штока (максимум по всем углам)
    if 'лимит_скорости_штока_м_с' in targets:
        vmax = float(m.get('макс_скорость_штока_все_м_с', 0.0))
        vmax_lim = float(targets['лимит_скорости_штока_м_с'])
        if vmax > vmax_lim:
            pen += w * (vmax - vmax_lim) / max(0.1, abs(vmax_lim) + 0.1)

    # 6b) Family-aware spring/cylinder geometry and static packaging
    if 'мин_зазор_пружина_цилиндр_м' in targets:
        host_clearance = float(m.get('мин_зазор_пружина_цилиндр_м', float("nan")))
        host_clearance_min = float(targets['мин_зазор_пружина_цилиндр_м'])
        if np.isfinite(host_clearance) and host_clearance < host_clearance_min:
            pen += w * (host_clearance_min - host_clearance) / max(1e-4, abs(host_clearance_min) + 1e-4)

    if 'мин_зазор_пружина_пружина_м' in targets:
        pair_clearance = float(m.get('мин_зазор_пружина_пружина_м', float("nan")))
        pair_clearance_min = float(targets['мин_зазор_пружина_пружина_м'])
        if np.isfinite(pair_clearance) and pair_clearance < pair_clearance_min:
            pen += w * (pair_clearance_min - pair_clearance) / max(1e-4, abs(pair_clearance_min) + 1e-4)

    if 'макс_ошибка_midstroke_t0_м' in targets:
        midstroke_err = float(m.get('макс_ошибка_midstroke_t0_м', float("nan")))
        midstroke_lim = float(targets['макс_ошибка_midstroke_t0_м'])
        if np.isfinite(midstroke_err) and midstroke_err > midstroke_lim:
            pen += w * (midstroke_err - midstroke_lim) / max(1e-4, abs(midstroke_lim) + 1e-4)

    if 'мин_запас_до_coil_bind_пружины_м' in targets:
        coil_margin = float(m.get('мин_запас_до_coil_bind_пружины_м', float("nan")))
        coil_margin_min = float(targets['мин_запас_до_coil_bind_пружины_м'])
        if np.isfinite(coil_margin) and coil_margin < coil_margin_min:
            pen += w * (coil_margin_min - coil_margin) / max(1e-4, abs(coil_margin_min) + 1e-4)

    # 7) Физический контроль: ошибка баланса энергии газа (если явно задано в targets)
    # Важно: по умолчанию (если target_* не задан) штраф НЕ применяется — обратная совместимость.
    if 'макс_ошибка_энергии_газа_отн' in targets:
        err_rel = abs(float(m.get('ошибка_энергии_газа_отн', 0.0)))
        lim = float(targets['макс_ошибка_энергии_газа_отн'])
        if err_rel > lim:
            pen += w * (err_rel - lim) / max(1e-6, lim)


    # 8) 2-й закон (если явно задано): ограничения по необратимостям
    if 'макс_эксергия_разрушена_Дж' in targets:
        Xdest = float(m.get('эксергия_разрушена_Дж', 0.0))
        limX = float(targets['макс_эксергия_разрушена_Дж'])
        if Xdest > limX:
            pen += w * (Xdest - limX) / max(1.0, abs(limX) + 1.0)

    if 'макс_энтропия_генерация_Дж_К' in targets:
        Sgen = float(m.get('энтропия_генерация_Дж_К', 0.0))
        limS = float(targets['макс_энтропия_генерация_Дж_К'])
        if Sgen > limS:
            pen += w * (Sgen - limS) / max(1e-6, abs(limS) + 1.0)

    # 8b) Опциональная декомпозиция 2-го закона (если пороги заданы в targets)
    if 'макс_эксергия_падение_давления_Дж' in targets:
        Xp = float(m.get('эксергия_падение_давления_Дж', 0.0))
        lim = float(targets['макс_эксергия_падение_давления_Дж'])
        if Xp > lim:
            pen += w * (Xp - lim) / max(1.0, abs(lim) + 1.0)

    if 'макс_эксергия_смешение_Дж' in targets:
        Xm = float(m.get('эксергия_смешение_Дж', 0.0))
        lim = float(targets['макс_эксергия_смешение_Дж'])
        if Xm > lim:
            pen += w * (Xm - lim) / max(1.0, abs(lim) + 1.0)

    if 'макс_эксергия_остаток_без_тепло_без_смешения_Дж' in targets:
        Xr = float(m.get('эксергия_остаток_без_тепло_без_смешения_Дж', 0.0))
        lim = float(targets['макс_эксергия_остаток_без_тепло_без_смешения_Дж'])
        if Xr > lim:
            pen += w * (Xr - lim) / max(1.0, abs(lim) + 1.0)

    if 'макс_энтропия_падение_давления_Дж_К' in targets:
        Sp = float(m.get('энтропия_падение_давления_Дж_К', 0.0))
        lim = float(targets['макс_энтропия_падение_давления_Дж_К'])
        if Sp > lim:
            pen += w * (Sp - lim) / max(1e-6, abs(lim) + 1.0)

    if 'макс_энтропия_смешение_Дж_К' in targets:
        Sm = float(m.get('энтропия_смешение_Дж_К', 0.0))
        lim = float(targets['макс_энтропия_смешение_Дж_К'])
        if Sm > lim:
            pen += w * (Sm - lim) / max(1e-6, abs(lim) + 1.0)

    if 'макс_энтропия_остаток_без_тепло_без_смешения_Дж_К' in targets:
        Sr = float(m.get('энтропия_остаток_без_тепло_без_смешения_Дж_К', 0.0))
        lim = float(targets['макс_энтропия_остаток_без_тепло_без_смешения_Дж_К'])
        if Sr > lim:
            pen += w * (Sr - lim) / max(1e-6, abs(lim) + 1.0)
    return float(pen)


def fix_consistency(params: Dict[str, Any]) -> Dict[str, Any]:
    """Pmin < Pmid < Pmax"""
    Pmax = float(params["давление_Pmax_предохран"])
    Pmin = float(params["давление_Pmin_сброс"])
    Pmid = float(params["давление_Pmid_сброс"])
    dp = 0.1e5

    Pmin = min(Pmin, Pmax - 2 * dp)
    Pmid = min(max(Pmid, Pmin + dp), Pmax - dp)

    params["давление_Pmin_сброс"] = Pmin
    params["давление_Pmid_сброс"] = Pmid
    return params




def build_test_suite(cfg: dict):
    """Собрать список тестов.

    Варианты:
      1) Если cfg содержит ключ 'suite' (список словарей), то тесты полностью задаются из него.
         Это основной режим (все пороги/уставки/времена редактируются из UI).
      2) Если 'suite' не задан — используем старые значения (совместимость).

    Формат строки suite (пример):
        {
          "имя": "инерция_крен_ay2",
          "включен": true,
          "тип": "инерция_крен",
          "dt": 0.003,
          "t_end": 1.2,
          "t_step": 0.4,
          "ay": 2.0,
          "target_макс_доля_отрыва": 0.0,
          "target_мин_Fmin_Н": 50.0,
          ...
        }

    Важно: target_* автоматически превращаются в словарь targets, где ключ = без префикса.
    """

    # cfg может быть dict {'suite': [...]} (новый формат) или просто список тестов (старый формат)
    if isinstance(cfg, list):
        cfg = {"suite": cfg}
    elif not isinstance(cfg, dict):
        cfg = {}
    suite = cfg.get("suite", cfg.get("tests", None))
    suite_explicit = bool(cfg.get("__suite_explicit__", False))
    suite_path = str(cfg.get("__suite_json_path__", "") or "").strip()

    # --- безопасные конвертеры ---
    # В st.data_editor пустые ячейки часто возвращаются как None, а пользователь может
    # вводить числа с запятой ("0,5"). Поэтому приведение к float/int делаем устойчивым.
    def _to_float(v, default: float) -> float:
        if v is None:
            return float(default)
        # pandas/pyarrow иногда дают nan, его лучше заменять на default
        try:
            # numpy.nan сравнение через != работает
            if isinstance(v, float) and (v != v):
                return float(default)
        except Exception:
            pass
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return float(default)
            s = s.replace(',', '.')
            try:
                return float(s)
            except Exception:
                return float(default)
        try:
            return float(v)
        except Exception:
            return float(default)

    def _to_int(v, default: int) -> int:
        if v is None:
            return int(default)
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return int(v)
        if isinstance(v, float):
            if v != v:
                return int(default)
            return int(round(v))
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return int(default)
            s = s.replace(',', '.')
            try:
                return int(float(s))
            except Exception:
                return int(default)
        try:
            return int(v)
        except Exception:
            return int(default)


    def _to_bool(v, default: bool) -> bool:
        """Устойчивое приведение к bool для данных из UI/JSON.

        Поддерживает:
        - bool/int/float
        - строки: '1','0','true','false','yes','no','on','off','да','нет'
        """
        if v is None:
            return bool(default)
        if isinstance(v, bool):
            return bool(v)
        if isinstance(v, int):
            return bool(int(v) != 0)
        if isinstance(v, float):
            try:
                if v != v:  # nan
                    return bool(default)
            except Exception:
                return bool(default)
            return bool(float(v) != 0.0)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("1", "true", "yes", "y", "on", "да"):
                return True
            if s in ("0", "false", "no", "n", "off", "нет"):
                return False
            if s == "":
                return bool(default)
            try:
                return bool(float(s) != 0.0)
            except Exception:
                return bool(default)
        try:
            return bool(v)
        except Exception:
            return bool(default)
    # --- режим из suite.json ---
    if suite_explicit and isinstance(suite, list) and len(suite) == 0:
        raise ValueError(f"Явно переданный suite_json пустой: {suite_path or '<unknown>'}")

    if isinstance(suite, list) and len(suite) > 0:
        tests = []
        for row in suite:
            if not isinstance(row, dict):
                continue
            enabled = _to_bool(row.get('включен', row.get('enabled', True)), True)
            if not bool(enabled):
                continue

            _name = row.get('имя', None)
            if _name is None:
                _name = row.get('name', None)
            if _name is None:
                _name = row.get('id', None)
            name = str(_name) if _name is not None else 'тест'

            _typ = row.get('тип', None)
            if _typ is None:
                _typ = row.get('type', None)
            typ = str(_typ or '').strip().lower()

            # Времена/шаги
            dt_default = _to_float(cfg.get('dt', 0.003), 0.003)
            t_end_default = _to_float(cfg.get('t_end_short', 1.2), 1.2)
            t_step_default = _to_float(cfg.get('t_step', 0.4), 0.4)
            dt = _to_float(row.get('dt', None), dt_default)
            t_end = _to_float(row.get('t_end', None), t_end_default)
            t_step = _to_float(row.get('t_step', None), t_step_default)

            # Параметры событий
            ay = _to_float(row.get('ay', None), 0.0)
            ax = _to_float(row.get('ax', None), 0.0)
            A = _to_float(row.get('A', None), 0.0)
            f = _to_float(row.get('f', None), 0.0)
            idx = _to_int(row.get('idx', None), 0)
            dur = _to_float(row.get('dur', None), 0.1)
            t0 = _to_float(row.get('t0', None), t_step)

            if typ in ['инерция_крен', 'roll', 'inertia_roll']:
                test = make_test_roll(t_step=t_step, ay=ay)
            elif typ in ['инерция_тангаж', 'pitch', 'inertia_pitch']:
                test = make_test_pitch(t_step=t_step, ax=ax)
            elif typ in ['микро_синфаза', 'micro_sin', 'micro_sinphase']:
                test = make_test_micro_sin(A=A, f=f)
            elif typ in ['микро_разнофаза', 'micro_antiphase', 'micro_antiphase_lr']:
                test = make_test_micro_antiphase(A=A, f=f)
            elif typ in ['комбо_крен_плюс_микро', 'combo_roll_plus_micro', 'комбо_ay3_плюс_микро', 'combo_roll_micro']:
                # Комбо: ступень по крену + синфазная микронеровность дороги
                ay_c = _to_float(row.get('ay', None), 3.0)
                A_c = _to_float(row.get('A', None), 0.003)
                f_c = _to_float(row.get('f', None), 3.0)
                test = make_test_combo_roll_plus_micro(t_step=t_step, ay=ay_c, A=A_c, f=f_c)
            elif typ in ['кочка_одно_колесо', 'bump_single']:
                ramp_ratio = _to_float(row.get('доля_плавной_стыковки', row.get('ramp_ratio', None)), 0.25)
                test = make_test_bump_single(idx=idx, A=A, t0=t0, dur=dur, ramp_ratio=ramp_ratio)
            elif typ in ['кочка_диагональ', 'bump_diag']:
                # Диагональ делаем через два профиля (левая/правая колея) + задержка по базе.
                # Это даёт реальные последовательности ЛП→(ПП+ЛЗ)→ПЗ и т.п. при соответствующем угле.
                v_test = _to_float(
                    row.get('vx0_м_с', None),
                    _to_float(cfg.get('скорость_м_с_по_умолчанию', 10.0), 10.0)
                )
                ang_test = _to_float(row.get('угол_град', row.get('angle_deg', None)), 35.0)
                ramp_ratio = _to_float(row.get('доля_плавной_стыковки', row.get('ramp_ratio', None)), 0.25)
                track_m = _to_float(cfg.get('колея', 1.2), 1.2)
                wheelbase_m = _to_float(cfg.get('база', 2.3), 2.3)
                test = make_test_bump_diag(
                    A=A, t0=t0, dur=dur,
                    v=v_test,
                    angle_deg_from_perp=ang_test,
                    track_m=track_m,
                    wheelbase_m=wheelbase_m,
                    ramp_ratio=ramp_ratio,
                )
            elif typ in {
                "worldroad",
                "world_road",
                "road_surface",
                "road_profile_csv",
                "profile_csv",
                "maneuver_csv",
                "csv",
            }:
                # Реальные профили дороги / WorldRoad / CSV (без аналитического генератора)
                # Важно: не используем track_m/wheelbase_m из ветки bump_diag (они могут быть не определены).
                track_m_loc = _to_float(
                    row.get('track_m', row.get('колея', row.get('track', None))),
                    _to_float(cfg.get('колея', cfg.get('track_m', 1.2)), 1.2)
                )
                wheelbase_m_loc = _to_float(
                    row.get('wheelbase_m', row.get('база', row.get('wheelbase', None))),
                    _to_float(cfg.get('база', cfg.get('wheelbase_m', 2.3)), 2.3)
                )
                

                vx0_loc = _to_float(
                    row.get('vx0_м_с', None),
                    _to_float(cfg.get('vx0_м_с', 0.0), 0.0),
                )

                # ABSOLUTE LAW: speed uses a single canonical key: vx0_м_с
                # Длина участка (для авто-режима t_end), м
                road_len_m_loc = _to_float(
                    row.get('road_len_m', None),
                    float('nan'),
                )

                # Авто-режим: t_end = road_len_m / vx0
                auto_t_end_from_len = _to_bool(
                    row.get('auto_t_end_from_len', None),
                    False,
                )
                if auto_t_end_from_len and (road_len_m_loc == road_len_m_loc) and (road_len_m_loc > 0.0):
                    if vx0_loc > 1e-9:
                        t_end = float(road_len_m_loc) / max(1e-9, float(vx0_loc))
                    else:
                        # Нельзя вычислить t_end без скорости; оставляем как есть.
                        pass

                yaw0_loc = _to_float(row.get('yaw0', row.get('yaw0_рад', None)), 0.0)

                test = {
                    'тип': typ,
                    't_step': t_step,
                    't0': t0,
                    'dur': dur,
                    'track_m': track_m_loc,
                    'wheelbase_m': wheelbase_m_loc,
                    # для world-road кинематики (если модель это использует)
                    'vx0_м_с': float(vx0_loc),
                    'yaw0': yaw0_loc,
                    'shape': 'worldroad',
                    'auto_t_end_from_len': bool(auto_t_end_from_len),
                }
                # road_len_m полезен для воспроизводимости (особенно CSV/WorldRoad),
                # даже если t_end задан вручную.
                if (road_len_m_loc == road_len_m_loc) and (road_len_m_loc > 0.0):
                    test['road_len_m'] = float(road_len_m_loc)
            else:
                # неизвестный тип
                continue

            # Параметры метрики "время успокоения" тоже из UI
            test['settle_band_min_deg'] = _to_float(row.get('settle_band_min_deg', None), _to_float(cfg.get('settle_band_min_deg', 0.5), 0.5))
            test['settle_band_ratio'] = _to_float(row.get('settle_band_ratio', None), _to_float(cfg.get('settle_band_ratio', 0.20), 0.20))

            # targets: все поля target_*
            targets = {}
            for k, v in row.items():
                if isinstance(k, str) and k.startswith('target_'):
                    kk = k[len('target_'):]
                    # Пустые ячейки из UI приходят как None, их просто пропускаем.
                    if v is None:
                        continue
                    if isinstance(v, str) and v.strip() == "":
                        continue
                    fv = _to_float(v, float('nan'))
                    # если не удалось распарсить -> nan -> пропустить
                    if fv != fv:
                        continue
                    targets[kk] = fv

            # ------------------------------------------------------------------
            # Optional per-test additions (extended suite schema).
            #
            # These fields are ignored by the classic analytic test generators above,
            # but they are important for staged / real-profile suites:
            #   - road_surface / road_surface_json: worldroad surface spec (dict or JSON string)
            #   - road_csv: path to CSV with 4-wheel road height time series
            #   - axay_csv: path to CSV with longitudinal/lateral accel time series
            #   - params_override / params_override_json: dict with per-test parameter overrides
            #
            # Notes:
            #   * Functions (road_func/ax_func) must NOT be stored here because this list is
            #     sent to multiprocessing workers (pickle). Instead we store only file paths;
            #     they are compiled to callables inside eval_candidate_once().
            # ------------------------------------------------------------------
            def _parse_jsonish(x):
                if x is None:
                    return None
                if isinstance(x, (dict, list)):
                    return x
                if not isinstance(x, str):
                    return x
                s = x.strip()
                if not s:
                    return None
                if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
                    try:
                        return json.loads(s)
                    except Exception as e:
                        raise ValueError(f"invalid JSON: {e}") from e
                return x

            # world-road surface
            rs = row.get('road_surface', row.get('road_surface_json', None))
            try:
                rs_parsed = _parse_jsonish(rs)
            except Exception as e:
                raise ValueError(f"Тест '{name}': road_surface JSON не разобран: {e}") from e
            if rs_parsed is not None and rs_parsed != "":
                test['road_surface'] = rs_parsed

            # time-series sources
            road_csv = row.get('road_csv', None)
            if isinstance(road_csv, str) and road_csv.strip():
                test['road_csv'] = road_csv.strip()

            axay_csv = row.get('axay_csv', None)
            if isinstance(axay_csv, str) and axay_csv.strip():
                test['axay_csv'] = axay_csv.strip()

            # per-test param overrides (scenario matrix)
            po = row.get('params_override', row.get('params_override_json', None))
            try:
                po_parsed = _parse_jsonish(po)
            except Exception as e:
                raise ValueError(f"Тест '{name}': params_override JSON не разобран: {e}") from e
            if isinstance(po_parsed, dict) and po_parsed:
                test['params_override'] = po_parsed

            tests.append((name, test, dt, t_end, targets))

        # Защита от коллизий: имена тестов в suite должны быть уникальны.
        # Иначе при агрегации метрик/кэше легко «перезаписать» результаты.
        name_counts: Dict[str, int] = {}
        for nm, *_ in tests:
            nm_s = str(nm)
            name_counts[nm_s] = name_counts.get(nm_s, 0) + 1
        dups = sorted([nm for nm, c in name_counts.items() if c > 1])
        if dups:
            raise ValueError("Дубли имён тестов в suite: " + ", ".join(dups))
        if suite_explicit and len(tests) == 0:
            raise ValueError(
                f"Явно переданный suite_json не содержит ни одного включённого/поддерживаемого теста: {suite_path or '<unknown>'}"
            )

        return tests

    if suite_explicit:
        raise ValueError(
            f"Явно переданный suite_json отсутствует или имеет неверный формат: {suite_path or '<unknown>'}"
        )

    # --- fallback: старые настройки (на случай ручного запуска без suite_json) ---
    dt = _to_float(cfg.get('dt', 0.003), 0.003)
    t_end_short = _to_float(cfg.get('t_end_short', 1.2), 1.2)
    t_end_micro = _to_float(cfg.get('t_end_micro', 1.6), 1.6)
    t_end_inertia = _to_float(cfg.get('t_end_inertia', 1.2), 1.2)
    t_step = _to_float(cfg.get('t_step', 0.4), 0.4)

    tests = [
        ("инерция_крен_ay2", make_test_roll(t_step=t_step, ay=2.0), dt, t_end_inertia,
         {"макс_доля_отрыва": 0.00, "мин_запас_до_Pmid_бар": -999.0, "мин_Fmin_Н": 50.0,
          "мин_запас_до_пробоя_крен_град": 0.0, "мин_запас_до_пробоя_тангаж_град": 0.0, "мин_запас_до_упора_штока_м": 0.005, "лимит_скорости_штока_м_с": 2.0}),
        ("инерция_крен_ay3", make_test_roll(t_step=t_step, ay=3.0), dt, t_end_inertia,
         {"макс_доля_отрыва": 0.00, "мин_запас_до_Pmid_бар": -999.0, "мин_Fmin_Н": 50.0,
          "мин_запас_до_пробоя_крен_град": 0.0, "мин_запас_до_пробоя_тангаж_град": 0.0, "мин_запас_до_упора_штока_м": 0.005, "лимит_скорости_штока_м_с": 2.0}),
        ("инерция_тангаж_ax3", make_test_pitch(t_step=t_step, ax=3.0), dt, t_end_inertia,
         {"макс_доля_отрыва": 0.00, "мин_запас_до_Pmid_бар": -999.0, "мин_Fmin_Н": 50.0,
          "мин_запас_до_пробоя_крен_град": 0.0, "мин_запас_до_пробоя_тангаж_град": 0.0, "мин_запас_до_упора_штока_м": 0.005, "лимит_скорости_штока_м_с": 2.0}),
        ("микро_синфаза", make_test_micro_sin(A=0.004, f=3.0), dt, t_end_micro,
         {"макс_доля_отрыва": 0.05, "мин_запас_до_Pmid_бар": 0.2, "мин_Fmin_Н": 0.0,
          "мин_запас_до_упора_штока_м": 0.010, "лимит_скорости_штока_м_с": 2.0}),
        ("микро_разнофаза", make_test_micro_antiphase(A=0.004, f=3.0), dt, t_end_micro,
         {"макс_доля_отрыва": 0.05, "мин_запас_до_Pmid_бар": 0.1, "мин_Fmin_Н": 0.0,
          "мин_запас_до_упора_штока_м": 0.010, "лимит_скорости_штока_м_с": 2.0}),
        ("кочка_ЛП_короткая", make_test_bump_single(idx=0, A=0.02, t0=t_step, dur=0.08), dt, t_end_short,
         {"макс_доля_отрыва": 0.20, "мин_запас_до_Pmid_бар": 0.0, "мин_Fmin_Н": 0.0,
          "мин_запас_до_упора_штока_м": 0.001, "лимит_скорости_штока_м_с": 3.0}),
        ("кочка_ЛП_длинная", make_test_bump_single(idx=0, A=0.02, t0=t_step, dur=0.35), dt, t_end_short,
         {"макс_доля_отрыва": 0.20, "мин_запас_до_Pmid_бар": -0.2, "мин_Fmin_Н": 0.0,
          "мин_запас_до_упора_штока_м": 0.001, "лимит_скорости_штока_м_с": 2.0}),
        ("кочка_диагональ", make_test_bump_diag(A=0.03, t0=t_step, dur=0.20, v=_to_float(cfg.get("скорость_м_с_по_умолчанию", 10.0), 10.0), angle_deg_from_perp=35.0, track_m=_to_float(cfg.get("колея", 1.2), 1.2), wheelbase_m=_to_float(cfg.get("база", 2.3), 2.3)), dt, t_end_short,
         {"макс_доля_отрыва": 0.20, "мин_запас_до_Pmid_бар": -0.2, "мин_Fmin_Н": 0.0,
          "мин_запас_до_упора_штока_м": 0.001, "лимит_скорости_штока_м_с": 2.5}),
        ("комбо_ay3_плюс_микро", make_test_combo_roll_plus_micro(t_step=t_step, ay=3.0, A=0.003, f=3.0), dt, t_end_inertia,
         {"макс_доля_отрыва": 0.00, "мин_запас_до_Pmid_бар": -999.0, "мин_Fmin_Н": 50.0,
          "мин_запас_до_упора_штока_м": 0.005, "лимит_скорости_штока_м_с": 2.5}),
    ]
    return tests


def _finite_float_or_none(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        if not math.isfinite(f):
            return None
        return float(f)
    except Exception:
        return None


def _collect_test_metric_values(
    row: Dict[str, Any],
    suffixes: Iterable[str],
    *,
    exclude_keys: Iterable[str] | None = None,
) -> List[Tuple[str, float]]:
    vals: List[Tuple[str, float]] = []
    suffixes_t = tuple(str(s) for s in suffixes)
    excluded = {str(x) for x in (exclude_keys or []) if str(x)}
    for k, v in row.items():
        if not isinstance(k, str):
            continue
        if k in excluded:
            continue
        if k.startswith('метрика_') or k.startswith('цель') or k.startswith('meta_aggregate_source__'):
            continue
        if "__" not in k:
            continue
        for suf in suffixes_t:
            if k.endswith(suf):
                fv = _finite_float_or_none(v)
                if fv is not None:
                    vals.append((k, fv))
                break
    return vals


def _agg_pick(values: List[Tuple[str, float]], mode: str) -> float | None:
    if not values:
        return None
    nums = [float(v) for _, v in values]
    if not nums:
        return None
    mode_s = str(mode or 'max').strip().lower()
    if mode_s == 'min':
        return float(min(nums))
    if mode_s == 'sum':
        return float(sum(nums))
    if mode_s == 'mean':
        return float(sum(nums) / max(1, len(nums)))
    return float(max(nums))


def _set_fallback_metric_if_missing(
    row: Dict[str, Any],
    *,
    target_key: str,
    suffixes: Iterable[str],
    mode: str,
    source_key: str,
    canonical_source_keys: Iterable[str] | None = None,
    missing_sentinels: Iterable[float] | None = None,
) -> None:
    src_keys = [str(x) for x in (canonical_source_keys or []) if str(x)]
    sentinel_vals = [float(x) for x in (missing_sentinels or [])]
    # If the canonical source metric is already present and finite, keep the original aggregate.
    for sk in src_keys:
        if _finite_float_or_none(row.get(sk)) is not None:
            return
    cur = _finite_float_or_none(row.get(target_key))
    if cur is not None and all(abs(cur - sv) > 1e-12 for sv in sentinel_vals):
        return
    vals = _collect_test_metric_values(row, suffixes, exclude_keys=[target_key])
    agg = _agg_pick(vals, mode)
    if agg is None:
        return
    row[target_key] = float(agg)
    if source_key:
        row[source_key] = ';'.join(k for k, _ in vals)


def synthesize_aggregate_objectives_from_available_tests(row: Dict[str, Any]) -> Dict[str, Any]:
    """Fill canonical aggregate objectives from any available explicit suite metrics.

    Why:
    - Historical code assumed built-in tests like ``микро_синфаза`` and ``инерция_крен_ay3``.
    - For custom suites (e.g. ``ring_test_01`` only), those canonical columns stay NaN/inf,
      which makes optimization ranking degenerate even when per-test metrics are present.

    Policy:
    - Preserve existing finite canonical values.
    - Otherwise synthesize conservative aggregates from all available per-test metrics:
      * comfort RMS  -> max across ``__RMS_ускор_рамы_м_с2``
      * energy       -> sum across ``__энергия_дроссели_Дж``
      * roll metric  -> max across ``__крен_peak_град`` / ``__крен_max_град``
      * settle time  -> max across ``__время_успокоения_крен_с``
      * early stiff  -> min across ``__запас_свыше_Pmid_бар``

    This keeps stage-local comparisons meaningful without inventing any new signals.
    """
    _set_fallback_metric_if_missing(
        row,
        target_key='метрика_комфорт__RMS_ускор_рамы_микро_м_с2',
        suffixes=['__RMS_ускор_рамы_м_с2'],
        mode='max',
        source_key='meta_aggregate_source__comfort',
        canonical_source_keys=['микро_синфаза__RMS_ускор_рамы_м_с2'],
    )
    _set_fallback_metric_if_missing(
        row,
        target_key='метрика_энергия_дроссели_микро_Дж',
        suffixes=['__энергия_дроссели_Дж'],
        mode='sum',
        source_key='meta_aggregate_source__energy',
        canonical_source_keys=['микро_синфаза__энергия_дроссели_Дж'],
        missing_sentinels=[0.0],
    )
    _set_fallback_metric_if_missing(
        row,
        target_key='метрика_крен_ay3_град',
        suffixes=['__крен_peak_град', '__крен_max_град'],
        mode='max',
        source_key='meta_aggregate_source__roll',
        canonical_source_keys=['инерция_крен_ay3__крен_max_град'],
    )
    _set_fallback_metric_if_missing(
        row,
        target_key='цель1_устойчивость_инерция__с',
        suffixes=['__время_успокоения_крен_с'],
        mode='max',
        source_key='meta_aggregate_source__settle',
        canonical_source_keys=['инерция_крен_ay3__время_успокоения_крен_с'],
        missing_sentinels=[999.0],
    )
    _set_fallback_metric_if_missing(
        row,
        target_key='метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар',
        suffixes=['__запас_свыше_Pmid_бар'],
        mode='min',
        source_key='meta_aggregate_source__early_stiff',
        missing_sentinels=[-999.0],
    )
    # Goal-2 is an alias of comfort objective in the current optimizer contract.
    cur_goal2 = _finite_float_or_none(row.get('цель2_комфорт__RMS_ускор_м_с2'))
    cur_comfort = _finite_float_or_none(row.get('метрика_комфорт__RMS_ускор_рамы_микро_м_с2'))
    if cur_goal2 is None and cur_comfort is not None:
        row['цель2_комфорт__RMS_ускор_м_с2'] = float(cur_comfort)
    return row


def eval_candidate(model, idx: int, params: Dict[str, Any], cfg: Dict[str, float]) -> Dict[str, Any]:
    """Оценка кандидата на всём тест‑наборе."""
    tests = build_test_suite(cfg)
    # Дешёвые тесты сначала (помогает early-stop на длинных наборах)
    try:
        if bool(cfg.get("sort_tests_by_cost", False)):
            tests = sorted(tests, key=lambda t: float(t[2]) * float(t[3]))
    except Exception:
        pass

    stop_if_pen_gt = float(cfg.get("stop_if_pen_gt", float("inf")))

    params = fix_consistency(params)

    row: Dict[str, Any] = {"id": int(idx)}
    for k, v in params.items():
        if isinstance(v, (float, int, np.floating, np.integer)):
            row[f"параметр__{k}"] = float(v)

    pen_total = 0.0
    early_stiff_metric = None


    # --- агрегаты по всем тестам (сводные KPI) ---
    corners = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    min_gap_N = {c: float('inf') for c in corners}
    min_gap_pct = {c: float('inf') for c in corners}
    contact_lost_any = {c: 0.0 for c in corners}
    min_breakdown_roll_deg = float('inf')
    min_breakdown_pitch_deg = float('inf')


    for test_name, test, dt_i, t_end_i, targets in tests:
        # Per-test parameter overrides (scenario matrix)
        params_use = params
        if isinstance(test, dict):
            po = test.get('params_override', None)
            if isinstance(po, dict) and po:
                params_use = dict(params)
                params_use.update(po)
                try:
                    params_use = fix_consistency(params_use)
                except Exception:
                    pass

        try:
            m = eval_candidate_once(model, params_use, test, dt=dt_i, t_end=t_end_i, targets=targets)
        except Exception as e:
            raise RuntimeError(f"[{test_name}] {e}") from e


        # сводные метрики: отрыв и запасы по углам
        for c in corners:
            v_lost = float(m.get(f"контакт_потерян_{c}", 0.0))
            contact_lost_any[c] = max(contact_lost_any[c], v_lost)
            vN = float(m.get(f"мин_зазор_до_отрыва_{c}_Н", float('inf')))
            vP = float(m.get(f"мин_зазор_до_отрыва_{c}_%стат", float('inf')))
            if vN < min_gap_N[c]:
                min_gap_N[c] = vN
            if vP < min_gap_pct[c]:
                min_gap_pct[c] = vP

        # сводные запасы до пробоя по крену/тангажу
        br = float(m.get("запас_до_пробоя_крен_град", float('inf')))
        bp = float(m.get("запас_до_пробоя_тангаж_град", float('inf')))
        if br < min_breakdown_roll_deg:
            min_breakdown_roll_deg = br
        if bp < min_breakdown_pitch_deg:
            min_breakdown_pitch_deg = bp

        for mk, mv in m.items():
            row[f"{test_name}__{mk}"] = float(mv) if isinstance(mv, (float, int, np.floating, np.integer)) else mv
        pen = candidate_penalty(m, targets)
        # Добавляем штрафы автономной верификации поверх целевой функции
        verif_pen = float(m.get('верификация_штраф', 0.0)) if isinstance(m, dict) else 0.0
        if math.isfinite(verif_pen) and verif_pen > 0.0:
            pen = float(pen) + float(verif_pen)
        row[f"{test_name}__штраф"] = pen
        pen_total += pen

        # Early-stop: если уже набрали слишком большой штраф, не тратим время на оставшиеся тесты
        try:
            if (math.isfinite(stop_if_pen_gt) and (pen_total > stop_if_pen_gt)):
                row["pruned_early"] = 1.0
                row["pruned_after_test"] = str(test_name)
                pen_total = max(pen_total, stop_if_pen_gt)
                break
        except Exception:
            pass

        # метрика 'раньше-жёстко': если уже на малом ay (обычно 2) пересекли Pmid, это плохо
        if early_stiff_metric is None:
            try:
                ay_val = None
                if isinstance(test, dict):
                    v = test.get('ay', None)
                    if isinstance(v, (int, float, np.floating, np.integer)):
                        ay_val = float(v)
                if ay_val is not None and abs(ay_val - 2.0) < 1e-9:
                    early_stiff_metric = float(m.get('запас_свыше_Pmid_бар', float('nan')))
            except Exception:
                pass


    # --- сводные KPI по всем тестам ---
    for c in corners:
        row[f"свод__контакт_потерян_{c}"] = float(contact_lost_any[c])
        row[f"свод__мин_зазор_до_отрыва_{c}_Н"] = float(min_gap_N[c]) if min_gap_N[c] < float('inf') else float('nan')
        row[f"свод__мин_зазор_до_отрыва_{c}_%стат"] = float(min_gap_pct[c]) if min_gap_pct[c] < float('inf') else float('nan')

    row["свод__запас_до_пробоя_крен_град"] = float(min_breakdown_roll_deg) if min_breakdown_roll_deg < float('inf') else float('nan')
    row["свод__запас_до_пробоя_тангаж_град"] = float(min_breakdown_pitch_deg) if min_breakdown_pitch_deg < float('inf') else float('nan')

    row["штраф_физичности_сумма"] = float(pen_total)
    row["метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар"] = float(early_stiff_metric if early_stiff_metric is not None else -999.0)
    row["метрика_комфорт__RMS_ускор_рамы_микро_м_с2"] = float(row.get("микро_синфаза__RMS_ускор_рамы_м_с2", float("nan")))
    row["метрика_энергия_дроссели_микро_Дж"] = float(row.get("микро_синфаза__энергия_дроссели_Дж", 0.0))
    row["метрика_крен_ay3_град"] = float(row.get("инерция_крен_ay3__крен_max_град", float("nan")))

    # Цель 1: устойчивость по крену на инерциальной ступеньке (ay=3).
    # Важно: это НЕ «порог для отбрасывания», а просто одна из осей сравнения.
    t_settle = float(row.get("инерция_крен_ay3__время_успокоения_крен_с", float("inf")))
    if not math.isfinite(t_settle):
        t_settle = 999.0
    row["цель1_устойчивость_инерция__с"] = float(t_settle)

    # Цель 2: комфорт на микроколебаниях (RMS ускорение рамы по z).
    row["цель2_комфорт__RMS_ускор_м_с2"] = float(row.get("метрика_комфорт__RMS_ускор_рамы_микро_м_с2", float("nan")))
    row = synthesize_aggregate_objectives_from_available_tests(row)
    return row


def _workspace_baseline_dir() -> Path:
    return _shared_workspace_baseline_dir(env=os.environ)


def _scoped_baseline_override_path(problem_hash: str | None, baseline_dir: Path | None = None) -> Optional[Path]:
    base_dir = Path(baseline_dir) if baseline_dir is not None else _workspace_baseline_dir()
    path = _baseline_problem_scope_dir(base_dir, problem_hash) / "baseline_best.json"
    return path if path.exists() else None


def resolve_workspace_baseline_override_path(
    problem_hash: str | None = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    baseline_dir: Path | None = None,
) -> Optional[Path]:
    current_baseline_dir = Path(baseline_dir) if baseline_dir is not None else _workspace_baseline_dir()
    return _resolve_workspace_baseline_override_path(
        problem_hash=problem_hash,
        env=env,
        baseline_dir=current_baseline_dir,
    )


def make_base_and_ranges(P_ATM: float) -> Tuple[Dict[str, Any], Dict[str, Tuple[float, float]]]:
    """
    Источник значений/диапазонов НЕ захардкожен в коде.

    По умолчанию читаем два файла рядом со скриптом:
      - default_base.json   (базовые параметры, в СИ: Па (абс), м³, кг, м, …)
      - default_ranges.json (диапазоны оптимизации, в СИ: [мин, макс])

    Если файлов нет — просим передать --base_json/--ranges_json.
    """
    base_path = os.path.join(os.path.dirname(__file__), "default_base.json")
    ranges_path = os.path.join(os.path.dirname(__file__), "default_ranges.json")

    if (not os.path.exists(base_path)) or (not os.path.exists(ranges_path)):
        raise FileNotFoundError(
            "Не найдены default_base.json / default_ranges.json рядом со скриптом. "
            "Передайте --base_json и --ranges_json, или положите файлы по умолчанию рядом."
        )

    base = load_json(base_path)

    # ------------------------------------------------------------------
    # Workspace baseline override (auto-updated after successful optimizations)
    #
    # If workspace/baselines/baseline_best.json exists, we merge it on top
    # of default_base.json. This lets the app automatically keep improving
    # the baseline between optimization runs without modifying code files.
    # ------------------------------------------------------------------
    ws_base_path = resolve_workspace_baseline_override_path()
    if ws_base_path is not None:
        try:
            ws_base = load_json(ws_base_path)
            if isinstance(ws_base, dict):
                base.update(ws_base)
        except Exception:
            pass
    ranges_raw = load_json(ranges_path)

    ranges: Dict[str, Tuple[float, float]] = {}
    for k, v in ranges_raw.items():
        if (not isinstance(v, (list, tuple))) or len(v) != 2:
            raise ValueError(f"Диапазон '{k}' должен быть списком [мин, макс], получено: {v}")
        ranges[str(k)] = (float(v[0]), float(v[1]))
    base, ranges_norm, _family_audit = normalize_component_family_contract(base, ranges)
    ranges_typed: Dict[str, Tuple[float, float]] = {}
    for k, v in ranges_norm.items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            ranges_typed[str(k)] = (float(v[0]), float(v[1]))
    return base, ranges_typed


def read_csv_header_cols(path: str) -> List[str]:
    """Прочитать список колонок из первой строки CSV.

    Важно: при инкрементальной записи (append) порядок колонок ДОЛЖЕН быть одинаковым,
    иначе строки «поедут» и файл станет нечитаем.
    """
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        header = f.readline().strip()
    # простое разбиение, т.к. заголовок пишется pandas и не содержит запятых в именах
    return header.split(",")


def build_columns_schema(model, base: Dict[str, Any], cfg: Dict[str, float]) -> List[str]:
    """Стабильный порядок колонок для CSV.

    Делается один раз в начале:
    - прогоняем один baseline-кандидат (base) через eval_candidate, чтобы получить полный набор ключей;
    - добавляем системные поля ошибки/диагностики;
    - раскладываем в читаемый порядок: id/ошибка/штрафы/цели/параметры/всё остальное.
    """
    try:
        row0 = eval_candidate(model, idx=0, params=dict(base), cfg=cfg)
    except Exception as _e:
        # Fallback: даже если baseline не прогнался, всё равно делаем полезную схему.
        row0 = {"id": 0, "штраф_физичности_сумма": float("nan")}
        try:
            row0.update(_params_to_row_fields(base))
        except Exception:
            pass
        # Минимальный набор KPI (чтобы CSV не развалился до 5 колонок)
        row0.setdefault("метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар", float("nan"))
        row0.setdefault("метрика_комфорт__RMS_ускор_рамы_микро_м_с2", float("nan"))
        row0.setdefault("цель1_устойчивость_инерция__с", float("nan"))
        row0.setdefault("цель2_комфорт__RMS_ускор_м_с2", float("nan"))
        row0.setdefault("метрика_энергия_дроссели_микро_Дж", float("nan"))
        row0.setdefault("метрика_крен_ay3_град", float("nan"))
        row0.setdefault("свод__запас_до_пробоя_крен_град", float("nan"))
        row0.setdefault("свод__запас_до_пробоя_тангаж_град", float("nan"))

    keys = list(row0.keys())

    cols: List[str] = ["id", "ошибка", "ошибка_тест", "ошибка_тип"]

    def add(k: str):
        if (k in row0) and (k not in cols):
            cols.append(k)

    # приоритетные KPI/цели (в верх таблицы)
    for k in [
        "штраф_физичности_сумма",
        "метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар",
        "метрика_комфорт__RMS_ускор_рамы_микро_м_с2",
        "цель1_устойчивость_инерция__с",
        "цель2_комфорт__RMS_ускор_м_с2",
    ]:
        add(k)

    # другие «метрика_» и «цель»
    for k in keys:
        if (k.startswith("метрика_") or k.startswith("цель")) and (k not in cols) and (k != "id"):
            cols.append(k)

    # параметры — отдельным блоком, сортируем по имени
    param_cols = sorted([k for k in keys if k.startswith("параметр__")])
    cols.extend([k for k in param_cols if k not in cols])

    # остаток — сортируем (чтобы порядок был повторяемый)
    rest = sorted([k for k in keys if k not in cols])
    cols.extend(rest)

    # Доп. служебные колонки (чтобы они всегда присутствовали в CSV схеме)
    for k in [
        "meta_source",
        "meta_stage",
        "meta_budget",
        "candidate_role",
        "is_baseline",
        "pruned_early",
        "pruned_after_test",
    ]:
        if k not in cols:
            cols.append(k)

    return cols


def append_csv(df: pd.DataFrame, path: str, cols_schema: List[str]):
    """Инкрементально писать CSV, но ВСЕГДА в одном порядке колонок."""
    df2 = df.reindex(columns=cols_schema)
    if os.path.exists(path):
        df2.to_csv(path, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        df2.to_csv(path, index=False, encoding="utf-8-sig")


def write_progress_json(path: str, payload: Dict[str, Any]) -> bool:
    """Best-effort atomic progress write with Windows lock retry."""
    return atomic_write_json_retry(
        path,
        payload,
        ensure_ascii=False,
        indent=2,
        encoding="utf-8",
        max_wait_sec=3.0,
        retry_sleep_sec=0.05,
        label="worker-progress",
    )


def _params_to_row_fields(params: Dict[str, Any]) -> Dict[str, float]:
    """Плоское представление параметров (для CSV), только численные."""
    out: Dict[str, float] = {}
    for k, v in params.items():
        if isinstance(v, (float, int, np.floating, np.integer)):
            out[f"параметр__{k}"] = float(v)
    return out


def make_error_row(idx: int, params: Dict[str, Any], e: Exception) -> Dict[str, Any]:
    """Единый формат строки результата при ошибке, с сохранением параметров."""
    msg = str(e)
    test_fail = ""
    m0 = re.match(r"^\[(.*?)\]\s*(.*)$", msg)
    if m0:
        test_fail = str(m0.group(1)).strip()
        msg = str(m0.group(2)).strip()

    row: Dict[str, Any] = {"id": int(idx)}
    row.update(_params_to_row_fields(params))
    row.update({
        "ошибка": msg,
        "ошибка_тест": test_fail,
        "ошибка_тип": type(e).__name__,
        "штраф_физичности_сумма": 1e9,
        # «страховочные» поля, чтобы ошибочные кандидаты всегда были заведомо плохими
        "метрика_раньше_жёстко_ay2__запас_свыше_Pmid_бар": -999.0,
        "метрика_комфорт__RMS_ускор_рамы_микро_м_с2": float("inf"),
        "цель1_устойчивость_инерция__с": float("inf"),
        "цель2_комфорт__RMS_ускор_м_с2": float("inf"),
        "метрика_энергия_дроссели_микро_Дж": float("inf"),
        "метрика_крен_ay3_град": float("inf"),
    })
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Файл модели .py")
    ap.add_argument("--out", required=True, help="Куда писать результаты: .csv")
    ap.add_argument("--minutes", type=float, default=10.0, help="Сколько минут считать (wall time)")
    ap.add_argument("--max_n", type=int, default=1000000, help="Жёсткий лимит кандидатов (на всякий случай)")
    ap.add_argument("--seed_candidates", type=int, default=1, help="Seed для генерации кандидатов (влияет на выбор комбинаций параметров)")
    ap.add_argument("--seed_conditions", type=int, default=1, help="Seed для генерации условий (дорога/масса/погода). Можно фиксировать для воспроизводимости.")
    ap.add_argument("--seed", type=int, default=None, help="(устар.) алиас для --seed_candidates")
    ap.add_argument("--jobs", type=int, default=_default_jobs_auto(), help="Параллельность: число процессов. По умолчанию = все доступные ядра (cap=128, Windows<=61).")
    ap.add_argument("--flush_every", type=int, default=20, help="Как часто писать результаты (кандидатов)")
    ap.add_argument("--progress_every_sec", type=float, default=1.0, help="Как часто обновлять progress.json по времени (сек)")
    ap.add_argument("--dt", type=float, default=0.003)
    ap.add_argument("--t_end_inertia", type=float, default=1.2)
    ap.add_argument("--t_end_micro", type=float, default=1.6)
    ap.add_argument("--t_end_short", type=float, default=1.2)
    ap.add_argument("--t_step", type=float, default=0.4)
    ap.add_argument("--stop_file", default="STOP_OPTIMIZATION.txt", help="Если файл существует — остановиться")
    ap.add_argument("--base_json", default=None, help="JSON с базовыми параметрами (override)")
    ap.add_argument("--ranges_json", default=None, help="JSON с диапазонами оптимизации (override)")
    ap.add_argument("--suite_json", default=None, help="JSON с тест-набором (override из UI)")
    ap.add_argument("--settle_band_min_deg", type=float, default=0.5, help="Параметр метрики 'время успокоения': минимальная полоса, град")
    ap.add_argument("--settle_band_ratio", type=float, default=0.20, help="Параметр метрики 'время успокоения': доля от пика, 0..1")
    ap.add_argument("--stop_if_pen_gt", type=float, default=float("inf"), help="Early-stop: если накопленный штраф > порога — прервать оставшиеся тесты (ускоряет длинные стадии)")
    ap.add_argument("--sort_tests_by_cost", type=int, default=1, help="Сортировать тесты по оценке стоимости (dt*t_end) — дешёвые первыми, полезно для early-stop")
    ap.add_argument("--seed_points_json", default=None, help="JSON со списком seed-точек (dict параметров), которые нужно посчитать первыми")
    ap.add_argument("--seed_only", type=int, default=0, help="Если 1 — посчитать только seed-точки и завершиться (без поиска)")
    ap.add_argument("--skip_baseline", type=int, default=0, help="Если 1 — не писать baseline-anchor в CSV этой стадии")
    args = ap.parse_args()

    # jobs=0 (или отрицательное) трактуем как 'auto'
    try:
        if int(getattr(args, "jobs", 1)) <= 0:
            args.jobs = _default_jobs_auto()
    except Exception:
        pass

    # Платформенные ограничения на число процессов (ProcessPoolExecutor).
    # На Windows max_workers должен быть <= 61 (иначе ValueError).
    try:
        j = int(getattr(args, 'jobs', 1))
        if os.name == 'nt':
            if j > 61:
                args.jobs = 61
        else:
            # Стабильность: не даём случайно поднять сотни процессов.
            if j > 128:
                args.jobs = 128
    except Exception:
        pass

    # Прогресс bootstrapping должен появляться до тяжёлого startup (autoselfcheck/load_model),
    # иначе staged-runner может ложно решить, что worker не стартовал.
    t_start = time.time()
    t_limit = t_start + float(args.minutes) * 60.0
    progress_path = os.path.splitext(args.out)[0] + "_progress.json"
    try:
        write_progress_json(progress_path, {
            "статус": "bootstrapping",
            "phase": "startup",
            "ts_start": float(t_start),
            "ts_last_write": float(time.time()),
            "готово_кандидатов": 0,
            "готово_кандидатов_в_файле": 0,
            "прошло_сек": 0.0,
            "лимит_минут": float(args.minutes),
            "последний_batch": 0,
        })
    except Exception:
        pass

    # Быстрый selfcheck (один раз на процесс).
    # По умолчанию НЕ падаем, но можно включить строгий режим через env PNEUMO_AUTOCHECK_STRICT=1.
    try:
        from pneumo_solver_ui.tools.autoselfcheck import ensure_autoselfcheck_once
        ensure_autoselfcheck_once(strict=False)
    except Exception:
        # Не мешаем оптимизатору стартовать, даже если selfcheck временно недоступен.
        pass

    model = load_model(args.model)
    P_ATM = float(getattr(model, "P_ATM", 101325.0))

    base, ranges = make_base_and_ranges(P_ATM)

    # --- override из UI (если передали JSON) ---
    if args.base_json and os.path.exists(args.base_json):
        try:
            with open(args.base_json, "r", encoding="utf-8") as f:
                base_override = json.load(f)
            if isinstance(base_override, dict):
                base.update(base_override)
        except Exception:
            pass

    if args.ranges_json and os.path.exists(args.ranges_json):
        try:
            with open(args.ranges_json, "r", encoding="utf-8") as f:
                ranges_override = json.load(f)
            if isinstance(ranges_override, dict):
                # ожидаем: {"параметр":[lo,hi], ...}
                for k, v in ranges_override.items():
                    if isinstance(v, (list, tuple)) and len(v) == 2:
                        ranges[str(k)] = (float(v[0]), float(v[1]))
        except Exception:
            pass

    ranges, _ranges_audit = sanitize_ranges_for_optimization(base, ranges)

    names = list(ranges.keys())
    d = len(names)

    suite = None
    suite_explicit = bool(args.suite_json)
    if args.suite_json:
        if not os.path.exists(args.suite_json):
            raise SystemExit(f"suite_json not found: {args.suite_json}")
        try:
            suite = load_json(args.suite_json)
        except Exception as exc:
            raise SystemExit(f"failed to load suite_json {args.suite_json}: {exc}")
        if not isinstance(suite, list):
            raise SystemExit(f"suite_json must contain a JSON list: {args.suite_json}")

    cfg = {
        "dt": float(args.dt),
        "t_end_inertia": float(args.t_end_inertia),
        "t_end_micro": float(args.t_end_micro),
        "t_end_short": float(args.t_end_short),
        "t_step": float(args.t_step),
        "suite": suite,
        "__suite_explicit__": bool(suite_explicit),
        "__suite_json_path__": str(args.suite_json or ""),
        "settle_band_min_deg": float(args.settle_band_min_deg),
        "settle_band_ratio": float(args.settle_band_ratio),
        "stop_if_pen_gt": float(args.stop_if_pen_gt) if args.stop_if_pen_gt is not None else float("inf"),
        "sort_tests_by_cost": bool(int(args.sort_tests_by_cost)),
    }

    # Геометрия шасси (нужна для дорожных профилей с фазовыми сдвигами)
    cfg.setdefault("колея", float(base.get("колея", 1.2)))
    cfg.setdefault("база", float(base.get("база", 2.3)))
    # Скорость по умолчанию для коротких дорожных тестов (если в тесте не задано)
    cfg.setdefault("скорость_м_с_по_умолчанию", 10.0)


    # Resume: считаем уже существующие id (если есть)
    done_ids = set()
    if os.path.exists(args.out) and os.path.getsize(args.out) > 0:
        try:
            df_done = pd.read_csv(args.out, usecols=["id"], encoding="utf-8-sig")
            done_ids = set(int(x) for x in df_done["id"].dropna().unique())
        except Exception:
            done_ids = set()

    total_done = int(len(done_ids))
    total_written = int(total_done)  # уже записано в CSV (до старта)
    total_computed = int(total_done) # уже посчитано (до старта)
    batch_id = 0

    # -------------------------
    # Стабильная схема колонок CSV (исправляет «поехавшие» строки)
    # -------------------------
    if os.path.exists(args.out) and os.path.getsize(args.out) > 0:
        try:
            cols_schema = read_csv_header_cols(args.out)
        except Exception:
            cols_schema = build_columns_schema(model, base, cfg)
    else:
        cols_schema = build_columns_schema(model, base, cfg)

    def write_live_progress(status: str, *, batch: int = 0, ok: int = 0, err: int = 0, extra: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "статус": status,
            "ts_start": float(t_start),
            "ts_last_write": float(time.time()),
            "готово_кандидатов": int(total_computed),
            "готово_кандидатов_в_файле": int(total_written),
            "прошло_сек": float(max(0.0, time.time() - t_start)),
            "лимит_минут": float(args.minutes),
            "последний_batch": int(batch),
            "ok": int(ok),
            "err": int(err),
        }
        if extra:
            payload.update(dict(extra))
        write_progress_json(progress_path, payload)

    # стартовая запись прогресса (чтобы UI сразу видел файл)
    write_live_progress("запущено", batch=0, ok=0, err=0)

    # --- Базовая точка: service-row anchor for stage0 only (later stages may skip it) ---
    baseline_present = any(int(bid) in done_ids for bid in {BASELINE_RESULT_ID, -1})
    if int(getattr(args, "skip_baseline", 0) or 0):
        try:
            write_live_progress("baseline_skipped", extra={"phase": "baseline_skipped", "seed_index": 0, "seed_total": 0})
        except Exception:
            pass
    elif not baseline_present:
        try:
            write_live_progress("baseline_eval", extra={"phase": "baseline", "seed_index": 0, "seed_total": 0})
        except Exception:
            pass
        try:
            row_base = eval_candidate(model, idx=BASELINE_RESULT_ID, params=dict(base), cfg=cfg)
            row_base["meta_source"] = "baseline"
        except Exception as e:
            row_base = make_error_row(BASELINE_RESULT_ID, dict(base), e)
            row_base["meta_source"] = "baseline_error"
        row_base = _mark_candidate_role(row_base, BASELINE_ROLE)
        try:
            append_csv(pd.DataFrame([row_base]), args.out, cols_schema)
        except Exception:
            pass
        done_ids.add(BASELINE_RESULT_ID)
        total_done += 1
        total_written += 1
        total_computed += 1
        try:
            write_live_progress("baseline_done", extra={"phase": "baseline_done", "seed_index": 0, "seed_total": 0})
        except Exception:
            pass
        if args.stop_file and os.path.exists(args.stop_file):
            write_live_progress("остановлено_пользователем", extra={"phase": "baseline_stop"})
            return
        if time.time() >= t_limit:
            write_live_progress("остановлено_по_времени", extra={"phase": "baseline_time_limit"})
            return

    # --- Seed точки: оцениваем заранее заданные кандидаты (warm-start / лидеры из внешнего предиктора) ---
    seed_points = []
    if args.seed_points_json and os.path.exists(str(args.seed_points_json)):
        try:
            seed_points = load_json(str(args.seed_points_json))
        except Exception:
            seed_points = []
    if isinstance(seed_points, dict):
        seed_points = [seed_points]
    if not isinstance(seed_points, list):
        seed_points = []

    def _stable_seed_id(p_full: Dict[str, Any]) -> int:
        try:
            # Хэшируем только оптимизируемые параметры (names), чтобы id не зависел от лишних полей.
            # Seed ids stay strictly positive and in a dedicated range above random-search ids.
            vec = {nm: float(p_full.get(nm, base.get(nm))) for nm in names}
            s = json.dumps(vec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
            sid = int(SEED_ID_OFFSET + (int(h, 16) % SEED_ID_MOD))
            return int(sid)
        except Exception:
            return int(SEED_ID_OFFSET)

    if seed_points:
        seed_total = int(len(seed_points))
        for seed_index, sp in enumerate(seed_points, start=1):
            if args.stop_file and os.path.exists(args.stop_file):
                write_live_progress("остановлено_пользователем", extra={"phase": "seed_eval", "seed_index": int(seed_index - 1), "seed_total": int(seed_total)})
                return
            if time.time() >= t_limit:
                write_live_progress("остановлено_по_времени", extra={"phase": "seed_eval", "seed_index": int(seed_index - 1), "seed_total": int(seed_total)})
                return
            if not isinstance(sp, dict):
                continue
            p = dict(base)
            p.update(sp)
            sid = _stable_seed_id(p)
            if sid in done_ids:
                continue
            try:
                write_live_progress("seed_eval", extra={"phase": "seed_eval", "seed_index": int(seed_index), "seed_total": int(seed_total), "seed_id": int(sid)})
            except Exception:
                pass
            try:
                row_seed = eval_candidate(model, idx=sid, params=p, cfg=cfg)
                row_seed["meta_source"] = "seed_points_json"
            except Exception as e:
                row_seed = make_error_row(sid, p, e)
                row_seed["meta_source"] = "seed_points_json_error"
            row_seed = _mark_candidate_role(row_seed, "seed")
            try:
                append_csv(pd.DataFrame([row_seed]), args.out, cols_schema)
            except Exception:
                pass
            done_ids.add(sid)
            total_done += 1
            total_written += 1
            total_computed += 1
            try:
                write_live_progress("seed_eval", extra={"phase": "seed_eval", "seed_index": int(seed_index), "seed_total": int(seed_total), "seed_id": int(sid)})
            except Exception:
                pass
            if args.stop_file and os.path.exists(args.stop_file):
                write_live_progress("остановлено_пользователем", extra={"phase": "seed_eval", "seed_index": int(seed_index), "seed_total": int(seed_total)})
                return
            if time.time() >= t_limit:
                write_live_progress("остановлено_по_времени", extra={"phase": "seed_eval", "seed_index": int(seed_index), "seed_total": int(seed_total)})
                return

    if int(args.seed_only) == 1:
        # Только seed'ы: выходим (удобно для successive-halving/ASHA на внешнем планировщике)
        try:
            write_live_progress("seed_only_done")
        except Exception:
            pass
        return

    # Счётчики и RNG
    seed_candidates = int(args.seed_candidates if args.seed_candidates is not None else (args.seed if args.seed is not None else 1))
    seed_conditions = int(args.seed_conditions if args.seed_conditions is not None else 1)
    rng = np.random.default_rng(seed_candidates)

    # Векторы диапазонов (для быстрой генерации/мутации)
    lo_vec = np.array([ranges[nm][0] for nm in names], dtype=float)
    hi_vec = np.array([ranges[nm][1] for nm in names], dtype=float)
    span_vec = np.maximum(1e-12, hi_vec - lo_vec)

    # -------------------------
    # «Обучающийся» генератор кандидатов:
    # - на старте: равномерное покрытие (LHS),
    # - затем: локализация вокруг «интересных» областей (мульти‑целевая скаляризация + мутации).
    # Скорость не приоритет, важнее реализм и осмысленное исследование пространства.
    # -------------------------

    # История уже посчитанных (для guided‑поиска)
    hist_X: List[np.ndarray] = []
    hist_pen: List[float] = []
    hist_obj: List[np.ndarray] = []

    # Параметры guided‑генератора (можно переопределять через env, UI их не трогает)
    guided_ratio = float(os.environ.get("PNEUMO_GUIDED_RATIO", "0.7"))   # доля guided в batch (0..1)
    init_random = int(os.environ.get("PNEUMO_INIT_RANDOM", "200"))       # сколько первых кандидатов только LHS
    min_hist = int(os.environ.get("PNEUMO_MIN_HIST", "80"))              # минимум истории для включения guided
    lam_pen = float(os.environ.get("PNEUMO_LAMBDA_PEN", "10.0"))         # «жёсткость» штрафа в скаляризации
    elite_frac = float(os.environ.get("PNEUMO_ELITE_FRAC", "0.05"))      # доля «элиты» при выборе родителей
    mut_scale0 = float(os.environ.get("PNEUMO_MUT_SCALE0", "0.15"))      # базовая амплитуда мутации (доля диапазона)
    mut_scale_min = float(os.environ.get("PNEUMO_MUT_SCALE_MIN", "0.03"))
    reset_prob = float(os.environ.get("PNEUMO_RESET_PROB", "0.05"))      # вероятность «ресета» координаты в случайное значение
    hist_max = int(os.environ.get("PNEUMO_HIST_MAX", "20000"))           # ограничение памяти по истории (строк)

    # Guided mode (алгоритм локализации):
    #   mutation  — текущая схема (crossover + нормальная мутация + случайный reset)
    #   cem_diag  — Cross-Entropy Method (диагональная ковариация) в нормированном [0..1] пространстве
    #   cem_full  — CEM с полной ковариацией (может быть нестабильным при маленькой истории)
    #   mixed     — часть guided через CEM (diag), часть через mutation
    #   auto      — адаптивный режим: сам выбирает mutation/mixed/cem_* и делает reheat при стагнации
    guided_mode = str(os.environ.get("PNEUMO_GUIDED_MODE", "mutation")).strip().lower()
    if guided_mode not in ["mutation", "cem_diag", "cem_full", "mixed", "auto"]:
        guided_mode = "mutation"

    # Параметры CEM (используются только если guided_mode в {cem_*, mixed})
    cem_alpha = float(os.environ.get("PNEUMO_CEM_ALPHA", "0.25"))            # скорость обновления распределения (0..1)
    cem_sigma_init = float(os.environ.get("PNEUMO_CEM_SIGMA_INIT", "0.35"))  # начальная сигма в нормированном пространстве
    cem_sigma_min = float(os.environ.get("PNEUMO_CEM_SIGMA_MIN", "0.05"))    # нижняя граница сигмы (защита от преждевр. схлопывания)
    cem_jitter = float(os.environ.get("PNEUMO_CEM_JITTER", "1e-6"))          # численная добавка к диагонали ковариации
    cem_mix = float(os.environ.get("PNEUMO_CEM_MIX", "0.5"))                 # доля CEM в mixed
    cem_mix = max(0.0, min(1.0, cem_mix))

    # Auto-guided (используется если guided_mode == "auto")
    auto_patience = int(os.environ.get("PNEUMO_AUTO_PATIENCE", "25"))
    auto_min_improve_rel = float(os.environ.get("PNEUMO_AUTO_MIN_IMPROVE_REL", "0.01"))
    auto_reheat_sigma = float(os.environ.get("PNEUMO_AUTO_REHEAT_SIGMA", str(cem_sigma_init)))
    auto_full_cov_max_d = int(os.environ.get("PNEUMO_AUTO_FULL_COV_MAX_D", "40"))
    auto_mixed_min_hist = int(os.environ.get("PNEUMO_AUTO_MIXED_MIN_HIST", str(max(120, 8 * d))))
    auto_cemfull_min_hist = int(os.environ.get("PNEUMO_AUTO_CEMFULL_MIN_HIST", str(max(200, 20 * d))))
    auto_best_score = None  # type: Optional[float]
    auto_no_improve_batches = 0
    auto_restart_count = 0

    cem_state_path = os.path.splitext(args.out)[0] + "_cem_state.json"
    cem_mu = np.full(d, 0.5, dtype=float)                     # нормированное среднее
    cem_cov = np.eye(d, dtype=float) * (cem_sigma_init ** 2)   # ковариация в нормированном пространстве

    def load_cem_state() -> None:
        """Загрузка состояния CEM (если есть) для resume."""
        nonlocal cem_mu, cem_cov, auto_best_score, auto_no_improve_batches, auto_restart_count
        try:
            if os.path.exists(cem_state_path) and os.path.getsize(cem_state_path) > 0:
                with open(cem_state_path, "r", encoding="utf-8") as f:
                    st_cem = json.load(f)
                mu = st_cem.get("mu", None)
                cov = st_cem.get("cov", None)
                if isinstance(mu, list) and len(mu) == d:
                    mu_arr = np.asarray(mu, dtype=float)
                    if np.isfinite(mu_arr).all():
                        cem_mu = np.clip(mu_arr, 0.0, 1.0)
                if isinstance(cov, list) and len(cov) == d and all(isinstance(row, list) and len(row) == d for row in cov):
                    cov_arr = np.asarray(cov, dtype=float)
                    if np.isfinite(cov_arr).all():
                        # симметризуем на всякий случай
                        cem_cov = 0.5 * (cov_arr + cov_arr.T)

                # Подхватываем auto-state (если был)
                auto = st_cem.get("auto", None)
                if isinstance(auto, dict):
                    try:
                        bs = auto.get("best_score", None)
                        if bs is not None:
                            auto_best_score = float(bs)
                    except Exception:
                        pass
                    try:
                        ni = auto.get("no_improve_batches", None)
                        if ni is not None:
                            auto_no_improve_batches = int(ni)
                    except Exception:
                        pass
                    try:
                        rc = auto.get("restart_count", None)
                        if rc is not None:
                            auto_restart_count = int(rc)
                    except Exception:
                        pass
        except Exception:
            pass

    def save_cem_state(extra: Optional[Dict[str, Any]] = None) -> None:
        """Сохранение состояния CEM. Файл маленький, можно писать хоть раз в батч."""
        try:
            st = {
                "guided_mode": guided_mode,
                "mu": [float(x) for x in np.clip(cem_mu, 0.0, 1.0).tolist()],
                "cov": [[float(v) for v in row] for row in cem_cov.tolist()],
                "meta": {
                    "d": int(d),
                    "names": names,
                    "alpha": float(cem_alpha),
                    "sigma_init": float(cem_sigma_init),
                    "sigma_min": float(cem_sigma_min),
                    "jitter": float(cem_jitter),
                    "mix": float(cem_mix),
                },
                "auto": {
                    "patience": int(auto_patience),
                    "min_improve_rel": float(auto_min_improve_rel),
                    "reheat_sigma": float(auto_reheat_sigma),
                    "full_cov_max_d": int(auto_full_cov_max_d),
                    "mixed_min_hist": int(auto_mixed_min_hist),
                    "cemfull_min_hist": int(auto_cemfull_min_hist),
                    "best_score": None if auto_best_score is None else float(auto_best_score),
                    "no_improve_batches": int(auto_no_improve_batches),
                    "restart_count": int(auto_restart_count),
                },
            }
            if isinstance(extra, dict):
                st["extra"] = extra
            tmp = cem_state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False, indent=2)
            os.replace(tmp, cem_state_path)
        except Exception:
            return

    # Resume: пробуем подхватить прошлое состояние CEM
    load_cem_state()

    def _row_has_error(r: Dict[str, Any]) -> bool:
        try:
            v = r.get("ошибка", None)
            if v is None:
                return False
            s = str(v).strip()
            return s not in ["", "nan", "None"]
        except Exception:
            return True

    def update_history_from_row(r: Dict[str, Any]) -> None:
        """Сохраняем в историю только успешные строки и только нужные поля."""
        if _row_has_error(r):
            return
        try:
            x = np.array([float(r.get(f"параметр__{nm}", np.nan)) for nm in names], dtype=float)
            if not np.isfinite(x).all():
                return
            pen = float(r.get("штраф_физичности_сумма", np.nan))
            obj1 = float(r.get("цель1_устойчивость_инерция__с", np.nan))
            obj2 = float(r.get("цель2_комфорт__RMS_ускор_м_с2", np.nan))
            eng = float(r.get("метрика_энергия_дроссели_микро_Дж", np.nan))
            if not np.isfinite([pen, obj1, obj2, eng]).all():
                return
            hist_X.append(x)
            hist_pen.append(float(pen))
            hist_obj.append(np.array([obj1, obj2, eng], dtype=float))
        except Exception:
            return

    # Resume: загружаем хвост истории из CSV (если есть)
    if os.path.exists(args.out) and os.path.getsize(args.out) > 0:
        try:
            need_cols = [f"параметр__{nm}" for nm in names] + [
                "штраф_физичности_сумма",
                "цель1_устойчивость_инерция__с",
                "цель2_комфорт__RMS_ускор_м_с2",
                "метрика_энергия_дроссели_микро_Дж",
                "ошибка",
            ]
            usecols = [c for c in need_cols if c in cols_schema]
            if usecols:
                df_hist = pd.read_csv(args.out, usecols=usecols, encoding="utf-8-sig")
                if "ошибка" in df_hist.columns:
                    df_hist = df_hist[df_hist["ошибка"].isna() | (df_hist["ошибка"].astype(str).str.strip() == "")]
                if len(df_hist) > hist_max:
                    df_hist = df_hist.tail(hist_max)
                for _, rr in df_hist.iterrows():
                    rdict = rr.to_dict()
                    update_history_from_row(rdict)
        except Exception:
            pass

    # Функция генерации batch кандидатов
    def generate_batch(n_batch: int, seed_batch: int) -> List[Tuple[int, Dict[str, Any]]]:
        nonlocal cem_mu, cem_cov
        rng_local = np.random.default_rng(seed_batch)
        items: List[Tuple[int, Dict[str, Any]]] = []

        # Решаем сколько брать guided
        have_hist = (len(hist_X) >= max(min_hist, init_random))
        n_guided = int(round(n_batch * guided_ratio)) if have_hist else 0
        n_guided = max(0, min(n_guided, n_batch))
        n_random = int(n_batch - n_guided)

        # --- 1) Random/LHS (широкое покрытие пространства) ---
        if n_random > 0:
            X = lhs(n_random, d, seed=seed_batch + 12345)
            for i in range(n_random):
                idx = int(rng.integers(0, 2_000_000_000))
                while idx in done_ids:
                    idx = int(rng.integers(0, 2_000_000_000))
                p = dict(base)
                for j, nm in enumerate(names):
                    lo, hi = ranges[nm]
                    p[nm] = float(lo + X[i, j] * (hi - lo))
                items.append((idx, p))
                done_ids.add(idx)

        # --- 2) Guided (локализация вокруг «интересных» комбинаций) ---
        if n_guided > 0:
            Xh = np.asarray(hist_X, dtype=float)
            pen = np.asarray(hist_pen, dtype=float)
            obj = np.asarray(hist_obj, dtype=float)  # [obj1, obj2, energy]

            mask = np.isfinite(pen) & np.isfinite(obj).all(axis=1)
            if int(mask.sum()) < min_hist:
                # fallback: просто LHS
                X = lhs(n_guided, d, seed=seed_batch + 54321)
                for i in range(n_guided):
                    idx = int(rng.integers(0, 2_000_000_000))
                    while idx in done_ids:
                        idx = int(rng.integers(0, 2_000_000_000))
                    p = dict(base)
                    for j, nm in enumerate(names):
                        lo, hi = ranges[nm]
                        p[nm] = float(lo + X[i, j] * (hi - lo))
                    items.append((idx, p))
                    done_ids.add(idx)
            else:
                Xh = Xh[mask]
                pen = pen[mask]
                obj = obj[mask]

                # Нормировка целей (min..max → 0..1)
                obj_min = obj.min(axis=0)
                obj_ptp = np.maximum(1e-12, obj.max(axis=0) - obj_min)
                obj_n = (obj - obj_min) / obj_ptp

                # Штраф: лог‑нормировка (чтобы «жёстко» отсекать невалидные)
                pen_n = np.log1p(np.maximum(0.0, pen))
                pen_n = pen_n / np.maximum(1e-12, pen_n.max())

                # Размер элиты
                K = int(max(10, math.ceil(elite_frac * len(pen))))
                K = max(2, min(K, len(pen)))

                # «Охлаждение» мутаций по мере накопления данных
                anneal = 0.985 ** (float(total_computed) / 200.0)
                mut_scale = max(mut_scale_min, mut_scale0 * anneal)
                sigma = mut_scale * span_vec

                def _mirror01(z: np.ndarray) -> np.ndarray:
                    """Отражение значений в нормированном диапазоне [0..1].

                    Полезно для CEM: вместо жёсткого clip уменьшаем "прилипание" к границам.
                    """
                    a = np.asarray(z, dtype=float)
                    for _ in range(4):
                        a = np.where(a < 0.0, -a, a)
                        a = np.where(a > 1.0, 2.0 - a, a)
                    return np.clip(a, 0.0, 1.0)

                # Auto-guided: контроль стагнации и выбор режима (mutation/mixed/cem_*)
                if guided_mode == "auto":
                    try:
                        w_track = np.array([0.45, 0.45, 0.10], dtype=float)
                        w_track = w_track / max(1e-12, float(np.sum(w_track)))
                        pen_track = np.log1p(np.maximum(0.0, pen))
                        score_track = (obj_n @ w_track) + lam_pen * pen_track
                        best_now = float(np.min(score_track))

                        if (auto_best_score is None) or (best_now < (1.0 - auto_min_improve_rel) * float(auto_best_score)):
                            auto_best_score = best_now
                            auto_no_improve_batches = 0
                        else:
                            auto_no_improve_batches += 1

                        # Reheat: если долго нет улучшений — сбрасываем CEM вокруг текущего лучшего
                        if (auto_patience > 0) and (auto_no_improve_batches >= auto_patience):
                            best_i = int(np.argmin(score_track))
                            Xn_all = (Xh - lo_vec) / span_vec
                            Xn_all = np.clip(Xn_all, 0.0, 1.0)
                            cem_mu = np.clip(Xn_all[best_i], 0.0, 1.0)
                            sig_r = max(float(auto_reheat_sigma), float(cem_sigma_min))
                            cem_cov = np.eye(d, dtype=float) * (sig_r ** 2)
                            cem_cov = cem_cov + cem_jitter * np.eye(d)
                            auto_restart_count += 1
                            auto_no_improve_batches = 0
                            save_cem_state({
                                "event": "auto_reheat",
                                "ts": float(time.time()),
                                "best_now": float(best_now),
                                "restart_count": int(auto_restart_count),
                                "sig_r": float(sig_r),
                            })
                    except Exception:
                        pass

                # Сколько guided делать CEM, а сколько mutation
                mode = guided_mode
                if mode == "auto":
                    hn = int(len(hist_X))
                    if hn < int(auto_mixed_min_hist):
                        mode = "mutation"
                    elif hn < int(auto_cemfull_min_hist):
                        mode = "mixed"
                    else:
                        if int(d) <= int(auto_full_cov_max_d):
                            mode = "cem_full"
                        else:
                            mode = "cem_diag"

                n_cem = 0
                n_mut = int(n_guided)
                mode_cem = "cem_diag"

                if mode == "mixed":
                    n_cem = int(round(float(n_guided) * cem_mix))
                    n_cem = max(0, min(int(n_guided), n_cem))
                    n_mut = int(n_guided - n_cem)
                    mode_cem = "cem_diag"
                elif mode in ["cem_diag", "cem_full"]:
                    n_cem = int(n_guided)
                    n_mut = 0
                    mode_cem = str(mode)
                else:
                    n_cem = 0
                    n_mut = int(n_guided)

                # --- 2a) CEM (Cross-Entropy Method) ---
                if n_cem > 0:
                    w_batch = rng_local.dirichlet(np.ones(3))
                    score = obj_n @ w_batch + lam_pen * pen_n
                    elite_idx = np.argsort(score)[:K]

                    # Нормированное пространство [0..1]^d
                    Xn = (Xh - lo_vec) / span_vec
                    Xn = np.clip(Xn, 0.0, 1.0)
                    mu_elite = np.mean(Xn[elite_idx], axis=0)

                    # Update mean
                    cem_mu = np.clip((1.0 - cem_alpha) * cem_mu + cem_alpha * mu_elite, 0.0, 1.0)

                    # Update covariance
                    if (mode_cem == "cem_full") and (len(elite_idx) >= max(5, d + 1)):
                        try:
                            cov_elite = np.cov(Xn[elite_idx].T, bias=True)
                        except Exception:
                            cov_elite = np.diag(np.var(Xn[elite_idx], axis=0) + 1e-12)
                        if not isinstance(cov_elite, np.ndarray) or cov_elite.shape != (d, d):
                            cov_elite = np.diag(np.var(Xn[elite_idx], axis=0) + 1e-12)
                        cov_elite = 0.5 * (cov_elite + cov_elite.T)
                        cem_cov = (1.0 - cem_alpha) * cem_cov + cem_alpha * cov_elite
                    else:
                        var_elite = np.var(Xn[elite_idx], axis=0) + 1e-12
                        diag_prev = np.diag(cem_cov)
                        diag_new = (1.0 - cem_alpha) * diag_prev + cem_alpha * var_elite
                        cem_cov = np.diag(diag_new)

                    # Защиты: sigma_min + симметрия + jitter
                    diag = np.clip(np.diag(cem_cov), cem_sigma_min ** 2, None)
                    cem_cov[np.diag_indices(d)] = diag
                    cem_cov = 0.5 * (cem_cov + cem_cov.T)
                    cem_cov = cem_cov + cem_jitter * np.eye(d)

                    # Семплирование
                    try:
                        samp = rng_local.multivariate_normal(mean=cem_mu, cov=cem_cov, size=int(n_cem))
                    except Exception:
                        sig = np.sqrt(np.clip(np.diag(cem_cov), 1e-12, None))
                        samp = rng_local.normal(loc=cem_mu, scale=sig, size=(int(n_cem), d))

                    samp = _mirror01(samp)

                    save_cem_state({
                        "ts": float(time.time()),
                        "hist": int(len(hist_X)),
                        "K": int(K),
                        "w_batch": [float(x) for x in w_batch.tolist()],
                        "score_elite_min": float(np.min(score[elite_idx])) if len(elite_idx) > 0 else None,
                        "score_elite_max": float(np.max(score[elite_idx])) if len(elite_idx) > 0 else None,
                    })

                    for i in range(int(n_cem)):
                        x = lo_vec + samp[i] * span_vec

                        idx = int(rng.integers(0, 2_000_000_000))
                        while idx in done_ids:
                            idx = int(rng.integers(0, 2_000_000_000))

                        p = dict(base)
                        for j, nm in enumerate(names):
                            p[nm] = float(x[j])
                        items.append((idx, p))
                        done_ids.add(idx)

                # --- 2b) Mutation (текущая схема) ---
                for i in range(int(n_mut)):
                    # Случайная скаляризация целей — даёт покрытие Парето‑фронта
                    w = rng_local.dirichlet(np.ones(3))
                    score = obj_n @ w + lam_pen * pen_n

                    elite_idx = np.argsort(score)[:K]
                    i1, i2 = rng_local.choice(elite_idx, size=2, replace=True)

                    x = 0.5 * (Xh[i1] + Xh[i2])

                    # Мутация
                    x = x + rng_local.normal(0.0, 1.0, size=d) * sigma

                    # Небольшая вероятность «ресета» отдельных координат (чтобы не застрять локально)
                    if reset_prob > 0.0:
                        m_reset = (rng_local.random(d) < reset_prob)
                        if np.any(m_reset):
                            x[m_reset] = lo_vec[m_reset] + rng_local.random(int(np.sum(m_reset))) * span_vec[m_reset]

                    x = np.clip(x, lo_vec, hi_vec)

                    idx = int(rng.integers(0, 2_000_000_000))
                    while idx in done_ids:
                        idx = int(rng.integers(0, 2_000_000_000))

                    p = dict(base)
                    for j, nm in enumerate(names):
                        p[nm] = float(x[j])
                    items.append((idx, p))
                    done_ids.add(idx)

        return items

    def eval_one(idx: int, p: Dict[str, Any]) -> Dict[str, Any]:
        try:
            row = eval_candidate(model, idx, p, cfg)
        except Exception as e:
            row = make_error_row(idx, p, e)
        return _mark_candidate_role(row, "search")

        # Главный цикл
    # Важно: progress.json обновляем ПО ВРЕМЕНИ (а не только при flush), чтобы UI видел живой прогресс.
    progress_every_sec = float(getattr(args, "progress_every_sec", 1.0))
    last_progress_write = time.time()

    ok_total = 0
    err_total = 0

    def is_err_row(r: Dict[str, Any]) -> bool:
        try:
            v = r.get("ошибка", None)
            if v is None:
                return False
            sv = str(v).strip()
            return sv not in ["", "nan", "None"]
        except Exception:
            return True

    def maybe_progress(status: str, batch: int, force: bool = False):
        nonlocal last_progress_write
        now = time.time()
        if (not force) and (now - last_progress_write < progress_every_sec):
            return
        last_progress_write = now
        write_progress_json(progress_path, {
            "статус": status,
            "ts_last_write": float(now),
            # «готово_кандидатов» — сколько УЖЕ ПОСЧИТАНО (для «живого» UI)
            "готово_кандидатов": int(total_computed),
            # сколько гарантированно записано в CSV
            "готово_кандидатов_в_файле": int(total_written),
            "прошло_сек": float(now - t_start),
            "лимит_минут": float(args.minutes),
            "последний_batch": int(batch),
            "ok": int(ok_total),
            "err": int(err_total),
        })

    # Пул процессов держим живым: иначе на Windows огромный overhead на создание/закрытие процессов
    ex = None
    _as_completed = None
    _wait_futures = None
    _first_completed = None

    def _terminate_process_pool_fast(executor: Any) -> None:
        """Аварийно останавливает ProcessPoolExecutor без долгого wait=True.

        Нужен для staged/time-limited run: если дедлайн стадии достигнут посреди большого batch,
        worker должен быстро вернуть уже посчитанные строки, а не висеть до завершения всех tasks.
        """
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        try:
            procs = getattr(executor, "_processes", {}) or {}
        except Exception:
            procs = {}
        for proc in list(getattr(procs, 'values', lambda: [])()):
            try:
                if proc.is_alive():
                    proc.terminate()
            except Exception:
                pass
        for proc in list(getattr(procs, 'values', lambda: [])()):
            try:
                proc.join(timeout=2.0)
            except Exception:
                pass
        for proc in list(getattr(procs, 'values', lambda: [])()):
            try:
                if proc.is_alive():
                    proc.kill()
            except Exception:
                pass

    if int(args.jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed as _ac, wait as _wait, FIRST_COMPLETED as _fc
        _as_completed = _ac
        _wait_futures = _wait
        _first_completed = _fc
        ex = ProcessPoolExecutor(
            max_workers=int(args.jobs),
            initializer=_init_pool_worker,
            initargs=(args.model, cfg),
        )

    early_stop_requested = False
    early_stop_reason = ""

    try:
        while (time.time() < t_limit) and (total_computed < int(args.max_n)):
            if args.stop_file and os.path.exists(args.stop_file):
                break

            batch_id += 1

            # ВАЖНО (CPU utilization):
            # flush_every — это про частоту записи на диск, а не про «размер параллельной работы».
            # Если jobs > flush_every, то часть процессов простаивает => CPU < 100%.
            # Поэтому в параллельном режиме держим n_batch >= jobs.
            #
            # Для воспроизводимости можно вернуть «старое» поведение (n_batch==flush_every),
            # выставив env: PNEUMO_LEGACY_BATCH_BY_FLUSH=1
            legacy_batch = bool(int(os.environ.get("PNEUMO_LEGACY_BATCH_BY_FLUSH", "0") or "0"))

            n_batch = int(max(1, int(args.flush_every)))
            try:
                if (int(args.jobs) > 1) and (not legacy_batch):
                    n_batch = int(max(n_batch, int(args.jobs)))
            except Exception:
                pass

            items = generate_batch(n_batch, seed_batch=seed_candidates + 10_000 * batch_id)

            # flush_every — частота записи на диск (надёжность).
            # В параллельном режиме n_batch может быть > flush_every (для загрузки CPU),
            # поэтому записи делаем по отдельному буферу.
            flush_n = int(max(1, int(args.flush_every)))
            rows_buf: List[Dict[str, Any]] = []

            def _flush_rows_buf():
                nonlocal rows_buf, total_written
                if not rows_buf:
                    return
                df_buf = pd.DataFrame(rows_buf)
                append_csv(df_buf, args.out, cols_schema)
                total_written += int(len(rows_buf))
                rows_buf = []

            if int(args.jobs) <= 1:
                for idx, p in items:
                    r = eval_one(idx, p)
                    rows_buf.append(r)
                    update_history_from_row(r)

                    total_computed += 1
                    if is_err_row(r):
                        err_total += 1
                    else:
                        ok_total += 1

                    # Пишем каждые flush_n строк (как просил пользователь/UI)
                    if len(rows_buf) >= flush_n:
                        _flush_rows_buf()

                    maybe_progress("идёт", batch_id, force=False)

                    if args.stop_file and os.path.exists(args.stop_file):
                        _flush_rows_buf()
                        maybe_progress("идёт", batch_id, force=True)
                        early_stop_requested = True
                        early_stop_reason = "stop_file"
                        break
                    if time.time() >= t_limit:
                        _flush_rows_buf()
                        maybe_progress("идёт", batch_id, force=True)
                        early_stop_requested = True
                        early_stop_reason = "time_limit"
                        break

            else:
                assert ex is not None and _wait_futures is not None and _first_completed is not None
                fut_map = {ex.submit(_pool_worker, it): it for it in items}
                pending = set(fut_map.keys())
                while pending:
                    done, pending = _wait_futures(pending, timeout=max(0.25, float(progress_every_sec)), return_when=_first_completed)
                    if not done:
                        maybe_progress("идёт", batch_id, force=False)
                        if args.stop_file and os.path.exists(args.stop_file):
                            early_stop_requested = True
                            early_stop_reason = "stop_file"
                            for pfu in list(pending):
                                try:
                                    pfu.cancel()
                                except Exception:
                                    pass
                            _flush_rows_buf()
                            maybe_progress("идёт", batch_id, force=True)
                            break
                        if time.time() >= t_limit:
                            early_stop_requested = True
                            early_stop_reason = "time_limit"
                            for pfu in list(pending):
                                try:
                                    pfu.cancel()
                                except Exception:
                                    pass
                            _flush_rows_buf()
                            maybe_progress("идёт", batch_id, force=True)
                            break
                        continue

                    for fu in done:
                        try:
                            r = fu.result()
                        except Exception as e:
                            idx_, p_ = fut_map.get(fu, (-1, {}))
                            r = _mark_candidate_role(make_error_row(int(idx_), dict(p_), e), "search")

                        rows_buf.append(r)
                        update_history_from_row(r)

                        total_computed += 1
                        if is_err_row(r):
                            err_total += 1
                        else:
                            ok_total += 1

                        # Пишем каждые flush_n строк (сохраняем надёжность даже при n_batch>flush_every)
                        if len(rows_buf) >= flush_n:
                            _flush_rows_buf()

                        maybe_progress("идёт", batch_id, force=False)

                        if args.stop_file and os.path.exists(args.stop_file):
                            _flush_rows_buf()
                            maybe_progress("идёт", batch_id, force=True)
                            early_stop_requested = True
                            early_stop_reason = "stop_file"
                            for pfu in list(pending):
                                try:
                                    pfu.cancel()
                                except Exception:
                                    pass
                            pending = set()
                            break
                        if time.time() >= t_limit:
                            _flush_rows_buf()
                            maybe_progress("идёт", batch_id, force=True)
                            early_stop_requested = True
                            early_stop_reason = "time_limit"
                            for pfu in list(pending):
                                try:
                                    pfu.cancel()
                                except Exception:
                                    pass
                            pending = set()
                            break

            # дописываем хвост буфера
            _flush_rows_buf()

            total_done = total_computed  # сохраняем старое имя переменной для нижнего кода

            # «жёсткое» обновление прогресса после записи
            maybe_progress("идёт", batch_id, force=True)

            if early_stop_requested:
                break


    finally:
        if ex is not None:
            if early_stop_requested:
                _terminate_process_pool_fast(ex)
            else:
                try:
                    ex.shutdown(wait=True, cancel_futures=False)
                except Exception:
                    try:
                        ex.shutdown(wait=True)
                    except Exception:
                        pass

# -------------------------
    # Финальный статус прогресса
    # -------------------------
    status = "завершено"
    if early_stop_reason == "stop_file" or (args.stop_file and os.path.exists(args.stop_file)):
        status = "остановлено_пользователем"
    elif early_stop_reason == "time_limit" or (time.time() >= t_limit):
        status = "остановлено_по_времени"
    elif total_done >= int(args.max_n):
        status = "остановлено_по_лимиту"

    write_progress_json(progress_path, {
        "статус": status,
        "ts_last_write": float(time.time()),
        "готово_кандидатов": int(total_done),
        "готово_кандидатов_в_файле": int(total_written),
        "прошло_сек": float(time.time() - t_start),
        "лимит_минут": float(args.minutes),
        "последний_batch": int(batch_id),
    })

    # Итоговый Pareto + TOP10 + финалы (удобно для ручного выбора)
    try:
        df_all = pd.read_csv(args.out, encoding="utf-8-sig")
        if "штраф_физичности_сумма" in df_all.columns:
            df_all = df_all.sort_values(["штраф_физичности_сумма"], ascending=True)
        obj1 = "цель1_устойчивость_инерция__с" if "цель1_устойчивость_инерция__с" in df_all.columns else None
        obj2 = "цель2_комфорт__RMS_ускор_м_с2" if "цель2_комфорт__RMS_ускор_м_с2" in df_all.columns else None
        if obj1 is not None and obj2 is not None:
            df_f = df_all.replace([np.inf, -np.inf], np.nan).dropna(subset=[obj1, obj2])

            # Pareto фронт 2D
            if len(df_f) > 0:
                df_sorted = df_f.sort_values(obj1, ascending=True)
                best2 = float("inf")
                keep = []
                for i, r in df_sorted.iterrows():
                    v2 = float(r[obj2])
                    if v2 < best2:
                        keep.append(i)
                        best2 = v2
                df_p = df_f.loc[df_f.index.isin(keep)].copy().sort_values([obj1, obj2])

                # TOP10 по балансному скору
                eps = 1e-12
                o1 = df_p[obj1].astype(float).to_numpy()
                o2 = df_p[obj2].astype(float).to_numpy()
                o1n = (o1 - np.min(o1)) / max(eps, (np.max(o1) - np.min(o1)))
                o2n = (o2 - np.min(o2)) / max(eps, (np.max(o2) - np.min(o2)))
                df_p["балансный_скор"] = (o1n + o2n)
                df_top10 = df_p.sort_values("балансный_скор", ascending=True).head(10).drop(columns=["балансный_скор"], errors="ignore")

                # финалы (все с ‘раньше‑жёстко’ по ay2)
                df_req = df_p
                if len(df_req) == 0:
                    df_req = df_p

                o1 = df_req[obj1].astype(float).to_numpy()
                o2 = df_req[obj2].astype(float).to_numpy()
                o1n = (o1 - np.min(o1)) / max(eps, (np.max(o1) - np.min(o1)))
                o2n = (o2 - np.min(o2)) / max(eps, (np.max(o2) - np.min(o2)))
                df_req = df_req.copy()
                df_req["балансный_скор"] = (o1n + o2n)
                aggressive = df_req.sort_values([obj1, obj2], ascending=[True, True]).head(1).drop(columns=["балансный_скор"], errors="ignore")
                comfort = df_req.sort_values([obj2, obj1], ascending=[True, True]).head(1).drop(columns=["балансный_скор"], errors="ignore")
                balanced = df_req.sort_values(["балансный_скор"], ascending=True).head(1).drop(columns=["балансный_скор"], errors="ignore")

                rep_path = os.path.splitext(args.out)[0] + "_pareto_top10_finals.xlsx"
                with pd.ExcelWriter(rep_path, engine="openpyxl") as w:
                    df_p.drop(columns=["балансный_скор"], errors="ignore").to_excel(w, sheet_name="pareto", index=False)
                    df_top10.to_excel(w, sheet_name="top10", index=False)
                    aggressive.to_excel(w, sheet_name="final_aggressive", index=False)
                    balanced.to_excel(w, sheet_name="final_balanced", index=False)
                    comfort.to_excel(w, sheet_name="final_comfort", index=False)
    except Exception:
        pass


if __name__ == "__main__":
    main()
