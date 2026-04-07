# -*- coding: utf-8 -*-
"""ui_tooltips_ru.py

Единая система подсказок (help/tooltip) для Streamlit UI.

Требование проекта: у каждого элемента интерфейса должны быть понятные
всплывающие подсказки на русском языке.

Реализация: best‑effort патч методов Streamlit DeltaGenerator.
Если у виджета уже задан help=..., то он не изменяется.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, Dict, Optional

import streamlit as st

try:
    from streamlit.delta_generator import DeltaGenerator  # type: ignore
except Exception:  # pragma: no cover
    DeltaGenerator = None  # type: ignore


_INSTALLED = False
_ORIG: Dict[str, Callable[..., Any]] = {}


# Точные подсказки для критичных элементов — по key.
HELP_BY_KEY: Dict[str, str] = {
    # Фильтры/поиск
    "ui_params_group": "Выбор смысловой группы параметров (геометрия, пневматика, массы и т.д.).",
    "ui_params_search": "Поиск по названию параметра и по пояснению.",
    "ui_suite_preset": "Быстрый выбор шаблона тест-набора.",
    "ui_suite_stage_filter": "Фильтр тестов по стадиям.",
    "ui_suite_only_enabled": "Показывать только включённые тесты.",
    "ui_suite_search": "Поиск по имени теста и типу.",

    # Визуализация
    "use_rel0_for_plots": "Если в данных есть *_rel0_m, графики строятся относительно нулевой дороги (удобнее для сравнения).",
    "skip_heavy_on_play": "На Play (fallback) можно скрывать тяжёлые графики, чтобы анимация не тормозила.",

    # Диагностика
    "ui_diag_tag": "Тэг добавится в имя диагностического ZIP (чтобы различать архивы).",

    # Персистентность
    "ui_autosave_enabled": "Автосохранение введённых данных. Отключайте только если нужно "
                           "временно «чистое» состояние без загрузки прошлого профиля.",

    # Настройки приложения/путей/параллельности
    "ui_model_path": "Путь к файлу модели (Python). Обычно: model/model_pneumo_*.py",
    "ui_worker_path": "Путь к worker-скрипту оптимизатора. Обычно: pneumo_solver_ui/opt_worker_v3_*.py",
    "ui_jobs": "Сколько параллельных процессов использовать (ускоряет, но увеличивает нагрузку на CPU/RAM).",
    "ui_opt_minutes": "Ограничение по времени оптимизации (мин). По достижении — процесс завершится корректно.",
    "ui_flush_every": "Как часто записывать прогресс на диск (итерации/поколения). Меньше — безопаснее, но больше IO.",
    "ui_progress_every_sec": "Частота обновления статуса/логов оптимизации в UI (сек).",
    "ui_auto_refresh": "Автообновление страницы (удобно, когда оптимизация идёт в фоне).",
    "ui_refresh_sec": "Период автообновления UI (сек). Слишком маленький может грузить браузер/сервер.",
    "ui_out_prefix": "Папка/префикс для результатов (CSV/NPZ/отчёты).",
    "node_pressure_plot": "Какие узлы показывать на графиках давления (df_p). Можно выбрать несколько.",
    "mech_plot_corners": "Какие углы кузова выводить на графиках (ЛП/ПП/ЛЗ/ПЗ).",
    "ui_params_section": "Быстрый выбор раздела исходных данных (фильтрует группы параметров).",

    "opt_run_name": "Имя папки прогона оптимизации (workspace/opt_runs). Меняйте, чтобы хранить независимые эксперименты раздельно.",
    "opt_use_staged": "StageRunner: оптимизация по стадиям (обычно быстрее и устойчивее). Нумерация стадий 0-based: первая стадия = 0. Отключайте только если точно понимаете зачем.",
    "opt_autoupdate_baseline": "Если найден кандидат лучше текущего baseline — сохранить его в workspace/baselines/baseline_best.json.",
}
# Подсказки по префиксу key (покрывает много виджетов без ручного перечисления).
HELP_BY_KEY_PREFIX: Dict[str, str] = {
    "ui_scen_": "Генератор сценариев: настройка дороги/манёвров. Нажмите «Сгенерировать и добавить», чтобы создать CSV и тест.",
    "svg_": "Интерактивная схема пневматики: выбор элементов, подсветка путей/маршрутов, проверка соответствий.",
    "route_": "Маршрутизация на схеме: сопоставление веток/элементов и проверка связности.",
    "oneclick_": "OneClick: пакетные прогоны и подготовка NPZ/логов для калибровки.",
    "calib_": "Калибровка: управление пакетными прогонами и связью с Desktop Animator.",
    "csv_to_npz_": "Конвертер: собрать NPZ из CSV логов (для дальнейшего анализа/калибровки).",
    "osc_": "OSC/логи: папка и файлы для сопоставления тестов с измерениями (калибровка).",
    "pi_": "Анализ влияния параметров: настройки построения карт/теплокарт/выборок.",
    "pareto_": "Pareto/сравнение: выбор критериев и весов для сортировки результатов.",
}



# Подсказки по label (когда key не задан).
HELP_BY_LABEL: Dict[str, str] = {
    "Запустить baseline": "Считает выбранные тесты на текущих параметрах и показывает сводную таблицу.",
    "Запустить оптимизацию": "Запускает подбор параметров в фоне. Перед запуском убедитесь, что тест-набор и диапазоны корректны.",
    "Сохранить сейчас": "Принудительно записать текущие введённые данные в файл автосохранения.",

    # Параметры (массовые действия)
    "Опт. все": "Отметить все параметры как оптимизируемые (OPT=ON).",
    "Опт. ничего": "Снять отметку OPT у всех параметров (ничего не оптимизировать).",
    "Диапазоны авто": "Автоматически заполнить диапазоны min/max для выбранных параметров (по текущим значениям и типовым правилам).",
    "Сброс диапазонов": "Сбросить диапазоны min/max (очистить/вернуть к исходным значениям).",
    "Сбросить поиск": "Очистить строку поиска и показать полный список параметров.",

    # Сброс/подтверждение
    "Сбросить ввод": "Очистить введённые пользователем значения и автосохранение. Используйте, если нужно начать заново.",
    "Да, сбросить ввод": "Подтверждение полного сброса введённых пользователем значений и автосохранения.",
    "Отмена": "Отменить действие и вернуться без изменений.",
    "Включить все": "Включить все тесты в наборе (enabled=True). Убедитесь, что длительные тесты не включены случайно.",
    "Выключить все": "Выключить все тесты (enabled=False). Полезно, чтобы включить только нужные вручную.",
    "Дублировать выбранный": "Создать копию выбранного теста (можно быстро сделать несколько вариантов dt/t_end).",
    "Удалить выбранный": "Удалить выбранный тест из таблицы. Действие необратимо (если нужно — сначала скачайте CSV/JSON).",
    "Сгенерировать и добавить": "Создать CSV дороги/манёвра по заданным параметрам и добавить новый тест в таблицу тест‑набора.",
}

def _clean_label(label: Any) -> str:
    s = "" if label is None else str(label)
    # уберём markdown/эмодзи‑шум, оставим «суть»
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _short(s: str, max_len: int = 180) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _default_help(kind: str, label: str, kwargs: Dict[str, Any]) -> str:
    """Короткие дефолтные подсказки.

    Принцип:
    - важное не прятать в tooltip (важное — в тексте рядом);
    - tooltip должен коротко объяснять «что это» и «что вводить».
    """
    label = _clean_label(label)
    label_part = f"«{label}»" if label else "поле"

    if kind in {"text_input", "text_area"}:
        return _short(f"Введите текст для {label_part}. Если поле не требуется — оставьте пустым.")
    if kind == "number_input":
        return _short(f"Введите число для {label_part}. Единицы — в подписи/карточке параметра.")
    if kind in {"slider", "select_slider"}:
        return _short(f"Выберите значение для {label_part} ползунком. Точный ввод — в карточке параметра.")
    if kind in {"selectbox", "multiselect", "radio"}:
        return _short(f"Выберите вариант для {label_part}.")
    if kind in {"checkbox", "toggle"}:
        return _short(f"Переключатель для {label_part}: включить/выключить опцию.")
    if kind == "button":
        return _short(f"Действие: {label}. Если кнопка неактивна — сначала исправьте ошибки ввода.")
    if kind == "file_uploader":
        return _short(f"Загрузите файл для {label_part} с диска. После загрузки путь/данные подставятся автоматически.")
    if kind == "download_button":
        return "Скачать файл с текущими данными/результатами."

    # общий fallback
    return "Подсказка: если не ясно, почему действие недоступно — откройте раздел «Диагностика»."


def get_help(kind: str, label: Any, key: Optional[str], kwargs: Dict[str, Any]) -> str:
    """Выдать help-строку для виджета."""
    if key and key in HELP_BY_KEY:
        return HELP_BY_KEY[key]

    if key:
        for pref, msg in HELP_BY_KEY_PREFIX.items():
            try:
                if key.startswith(pref):
                    return msg
            except Exception:
                pass

    lbl = _clean_label(label)
    if lbl in HELP_BY_LABEL:
        return HELP_BY_LABEL[lbl]

    return _default_help(kind=kind, label=lbl, kwargs=kwargs)


def _wrap_method(method_name: str, kind: str) -> None:
    if DeltaGenerator is None:
        return
    if not hasattr(DeltaGenerator, method_name):
        return

    orig = getattr(DeltaGenerator, method_name)
    # Не патчим дважды
    if method_name in _ORIG:
        return

    try:
        sig = inspect.signature(orig)
        if "help" not in sig.parameters:
            return
    except Exception:
        # если сигнатура недоступна — не рискуем
        return

    def wrapped(self: Any, *args: Any, **kwargs: Any):
        try:
            if not kwargs.get("help"):
                label = args[0] if args else kwargs.get("label", "")
                key = kwargs.get("key")
                kwargs["help"] = get_help(kind=kind, label=label, key=key, kwargs=kwargs)
        except Exception:
            # best-effort: не ломаем UI
            pass
        return orig(self, *args, **kwargs)

    _ORIG[method_name] = orig
    setattr(DeltaGenerator, method_name, wrapped)


def install_tooltips_ru() -> bool:
    """Установить патч подсказок.

    Возвращает True, если патч применён (или уже был применён).
    """
    global _INSTALLED
    if _INSTALLED:
        return True

    # Список виджетов Streamlit, где есть параметр help.
    targets = {
        "text_input": "text_input",
        "text_area": "text_area",
        "number_input": "number_input",
        "slider": "slider",
        "select_slider": "select_slider",
        "selectbox": "selectbox",
        "multiselect": "multiselect",
        "radio": "radio",
        "checkbox": "checkbox",
        "toggle": "toggle",
        "button": "button",
        "form_submit_button": "button",
        "file_uploader": "file_uploader",
        "download_button": "download_button",
    }

    for m, k in targets.items():
        _wrap_method(m, k)

    _INSTALLED = True
    return True


def is_installed() -> bool:
    return bool(_INSTALLED)
