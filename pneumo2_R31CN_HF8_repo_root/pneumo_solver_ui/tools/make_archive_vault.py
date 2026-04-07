# -*- coding: utf-8 -*-
"""
make_archive_vault.py

Создаёт единый "архив-хранилище" (ARCHIVE_VAULT.zip), внутри которого лежат
исходные релизы/пакеты (*.zip) как вложенные файлы + manifest.csv.

Зачем:
- когда есть ограничение по количеству файлов в папке/проекте — держим 1 файл vault вместо десятков;
- ничего не теряется: исходные архивы сохраняются как есть, с контрольными хэшами;
- можно перезаливать vault одним файлом (не плодить новые вложения).

Пример:
  python pneumo_solver_ui/tools/make_archive_vault.py --out ARCHIVE_VAULT.zip --dir ./incoming_zips

или:
  python pneumo_solver_ui/tools/make_archive_vault.py --out ARCHIVE_VAULT.zip MechanikaPnevmatikaR48.zip RealizatsiyaOptimizatsiiRelease59.zip

"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
from pathlib import Path
import time
import zipfile


def md5_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _iter_inputs(dir_path: Path | None, files: list[str]) -> list[Path]:
    out: list[Path] = []
    if dir_path:
        for p in sorted(dir_path.glob("*.zip")):
            if p.is_file():
                out.append(p)
    for f in files:
        p = Path(f)
        if p.is_file():
            out.append(p)
    # уникальные по абсолютному пути
    uniq = []
    seen = set()
    for p in out:
        ap = str(p.resolve())
        if ap in seen:
            continue
        seen.add(ap)
        uniq.append(p)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Путь выходного ARCHIVE_VAULT.zip")
    ap.add_argument("--dir", default="", help="Папка, где лежат входные *.zip")
    ap.add_argument("--no-dedupe", action="store_true", help="Не дедуплицировать по md5 (по умолчанию dedupe=ON)")
    ap.add_argument("files", nargs="*", help="Список входных zip")
    ns = ap.parse_args()

    out_path = Path(ns.out).resolve()
    in_dir = Path(ns.dir).resolve() if ns.dir else None

    inputs = _iter_inputs(in_dir, list(ns.files))
    if not inputs:
        print("Нет входных архивов.")
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    stored = []  # (arcname, path)
    md5_seen = set()

    for p in inputs:
        try:
            st = p.stat()
        except Exception:
            continue
        h = md5_file(p)
        if (not ns.no_dedupe) and (h in md5_seen):
            # пропускаем дубль
            rows.append({
                "input_name": p.name,
                "input_path": str(p),
                "size_bytes": st.st_size,
                "mtime_epoch": int(st.st_mtime),
                "md5": h,
                "stored": "DUPLICATE_SKIPPED",
                "stored_arcname": "",
            })
            continue

        md5_seen.add(h)
        arcname = f"src/{h}__{p.name}"
        stored.append((arcname, p))
        rows.append({
            "input_name": p.name,
            "input_path": str(p),
            "size_bytes": st.st_size,
            "mtime_epoch": int(st.st_mtime),
            "md5": h,
            "stored": "OK",
            "stored_arcname": arcname,
        })

    # Пишем vault
    tmp_manifest = out_path.with_suffix(".manifest.tmp.csv")
    with open(tmp_manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # архивы
        for arcname, p in stored:
            zf.write(p, arcname)
        # manifest + readme
        zf.write(tmp_manifest, "manifest.csv")
        readme = (
            "ARCHIVE_VAULT.zip\n\n"
            "Внутри:\n"
            "  src/<md5>__<original_name>.zip  - исходные архивы\n"
            "  manifest.csv                    - таблица (md5/mtime/size)\n\n"
            "Как обновлять:\n"
            "  1) добавь/замени исходные релизы в папке incoming\n"
            "  2) пересобери vault этой утилитой\n"
            "  3) загружай/перезаливай ОДИН файл vault вместо десятков\n"
        )
        zf.writestr("README.txt", readme)

    try:
        tmp_manifest.unlink()
    except Exception:
        pass

    print(f"OK: {out_path}  (архивов: {len(stored)}, всего входов: {len(inputs)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
