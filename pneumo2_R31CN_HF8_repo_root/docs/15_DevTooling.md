# Dev tooling (опционально)

Этот проект можно развивать и без dev‑инструментов.

Если нужно подтянуть качество кода (линт, форматирование, базовая типизация, тесты), используйте `pneumo_solver_ui/requirements_dev.txt`.

## Установка

В активированном venv:

```bash
python -m pip install -r pneumo_solver_ui/requirements_dev.txt
```

## Быстрый запуск линта (ruff)

```bash
ruff check .
```

## Базовые тесты

```bash
pytest -q
```

## pre-commit (по желанию)

```bash
pre-commit install
pre-commit run --all-files
```
