#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clipboard_file.py

Копирование *файла* в буфер обмена.

Зачем это нужно
--------------
Пользователь просит: "ОДНА кнопка — скопировать ZIP в буфер обмена".
Это не про копирование пути (текста), а про попытку скопировать файл как объект,
чтобы затем можно было вставить (Ctrl+V) в файловый менеджер/приложение.

Мы делаем best-effort:
  - Windows: CF_HDROP (DROPFILES + double-null-terminated список путей)
  - macOS: AppleScript через Finder (POSIX file)
  - Linux: wl-copy/xclip с MIME text/uri-list

Если "файловый" clipboard недоступен, падаем обратно на копирование пути как текста.

Ссылки (на уровень протоколов/форматов):
  - DROPFILES/CF_HDROP: Microsoft Learn (структура DROPFILES определяет CF_HDROP).
  - Linux: распространённый подход — text/uri-list в X11/Wayland.

"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import sys
from pathlib import Path
from typing import Tuple


def copy_file_to_clipboard(path: Path) -> Tuple[bool, str]:
    """Скопировать файл в clipboard.

    Возвращает: (ok, message)
    """
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        return False, f"File not found: {p}"

    if sys.platform.startswith("win"):
        ok, msg = _copy_windows_cf_hdrop(p)
        if ok:
            return True, msg
        ok_ps, msg_ps = _copy_windows_powershell_filelist(p)
        if ok_ps:
            return True, msg + "\nFallback(PowerShell FileDropList): " + msg_ps
        # fallback: text
        ok2, msg2 = _copy_text_fallback(str(p))
        return ok2, msg + "\nFallback(PowerShell FileDropList): " + msg_ps + "\nFallback(text): " + msg2

    if sys.platform == "darwin":
        ok, msg = _copy_macos_finder(p)
        if ok:
            return True, msg
        ok2, msg2 = _copy_text_fallback(str(p))
        return ok2, msg + "\nFallback(text): " + msg2

    # Linux / others
    ok, msg = _copy_linux_uri_list(p)
    if ok:
        return True, msg

    ok2, msg2 = _copy_text_fallback(str(p))
    return ok2, msg + "\nFallback(text): " + msg2


# -----------------------------
# Windows: CF_HDROP
# -----------------------------

def _copy_windows_cf_hdrop(path: Path) -> Tuple[bool, str]:
    """Windows: положить в clipboard CF_HDROP (Explorer-style file copy)."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32


        # IMPORTANT (Windows / 64‑bit): ctypes defaults WinAPI return types to
        # c_int. For handles/pointers this can truncate values on 64‑bit Python,
        # which manifests as "GlobalLock failed" even though GlobalAlloc succeeded.
        # We explicitly declare signatures for the functions we use.
        kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
        kernel32.GlobalFree.restype = wintypes.HGLOBAL

        user32.OpenClipboard.argtypes = (wintypes.HWND,)
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = ()
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = ()
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
        user32.SetClipboardData.restype = wintypes.HANDLE

        CF_HDROP = 15
        GMEM_MOVEABLE = 0x0002
        GMEM_ZEROINIT = 0x0040

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class DROPFILES(ctypes.Structure):
            _fields_ = [
                ("pFiles", wintypes.DWORD),
                ("pt", POINT),
                ("fNC", wintypes.BOOL),
                ("fWide", wintypes.BOOL),
            ]

        # double-null-terminated list of filenames (UTF-16LE)
        file_list = (str(path) + "\0\0").encode("utf-16le")

        df = DROPFILES()
        df.pFiles = ctypes.sizeof(DROPFILES)
        df.pt = POINT(0, 0)
        df.fNC = 0
        df.fWide = 1

        buf_size = ctypes.sizeof(DROPFILES) + len(file_list)
        h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, buf_size)
        if not h_global:
            return False, "GlobalAlloc failed"

        locked = kernel32.GlobalLock(h_global)
        if not locked:
            kernel32.GlobalFree(h_global)
            return False, "GlobalLock failed"

        try:
            ctypes.memmove(locked, ctypes.byref(df), ctypes.sizeof(DROPFILES))
            ctypes.memmove(locked + ctypes.sizeof(DROPFILES), file_list, len(file_list))
        finally:
            kernel32.GlobalUnlock(h_global)

        opened = False
        for _attempt in range(10):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.05)
        if not opened:
            kernel32.GlobalFree(h_global)
            return False, "OpenClipboard failed"

        transferred = False
        try:
            if not user32.EmptyClipboard():
                return False, "EmptyClipboard failed"
            if not user32.SetClipboardData(CF_HDROP, h_global):
                return False, "SetClipboardData(CF_HDROP) failed"
            # IMPORTANT: after SetClipboardData succeeds, system owns h_global
            transferred = True
            h_global = None
        finally:
            user32.CloseClipboard()
            # If we failed before transferring ownership, free the buffer.
            if not transferred and h_global:
                try:
                    kernel32.GlobalFree(h_global)
                except Exception:
                    pass

        return True, f"Copied file to clipboard (CF_HDROP): {path}"

    except Exception as e:
        return False, f"Windows CF_HDROP copy failed: {e}"


def _copy_windows_powershell_filelist(path: Path) -> Tuple[bool, str]:
    """Windows fallback: use .NET Clipboard.SetFileDropList via PowerShell."""
    try:
        exe = shutil.which("powershell") or shutil.which("pwsh")
        if not exe:
            return False, "PowerShell not found"
        p = str(path).replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$files = New-Object System.Collections.Specialized.StringCollection; "
            f"$files.Add('{p}'); "
            "[System.Windows.Forms.Clipboard]::SetFileDropList($files)"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [exe, "-NoProfile"]
        if Path(exe).name.lower().startswith("powershell"):
            cmd.append("-STA")
        cmd += ["-Command", ps]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=creationflags)
        if int(r.returncode) == 0:
            return True, f"Copied file to clipboard via PowerShell FileDropList: {path}"
        err = (r.stderr or r.stdout or "").strip()
        if len(err) > 400:
            err = err[:400] + "…"
        return False, f"PowerShell FileDropList failed rc={r.returncode}: {err or 'unknown error'}"
    except Exception as e:
        return False, f"PowerShell FileDropList failed: {e}"


# -----------------------------
# macOS: Finder AppleScript
# -----------------------------

def _copy_macos_finder(path: Path) -> Tuple[bool, str]:
    """macOS: try to ask Finder to put a POSIX file onto clipboard."""
    try:
        # Escape quotes for AppleScript string
        p = str(path).replace('"', '\\"')
        script = f'tell application "Finder" to set the clipboard to (POSIX file "{p}")'
        subprocess.run(["osascript", "-e", script], check=True)
        return True, f"Copied file to clipboard via Finder: {path}"
    except Exception as e:
        return False, f"macOS Finder clipboard copy failed: {e}"


# -----------------------------
# Linux: text/uri-list via wl-copy/xclip
# -----------------------------

def _copy_linux_uri_list(path: Path) -> Tuple[bool, str]:
    """Linux: copy file URI into clipboard with MIME text/uri-list.

    Many file managers treat text/uri-list as 'copied files'.
    """
    try:
        uri = path.resolve().as_uri() + "\n"
        data = uri.encode("utf-8")

        wl_copy = shutil.which("wl-copy")
        xclip = shutil.which("xclip")

        if wl_copy:
            subprocess.run([wl_copy, "-t", "text/uri-list"], input=data, check=True)
            return True, f"Copied file URI to clipboard via wl-copy: {uri.strip()}"

        if xclip:
            subprocess.run([xclip, "-selection", "clipboard", "-t", "text/uri-list"], input=data, check=True)
            return True, f"Copied file URI to clipboard via xclip: {uri.strip()}"

        return False, "Neither wl-copy nor xclip found"

    except Exception as e:
        return False, f"Linux uri-list clipboard copy failed: {e}"


# -----------------------------
# Text fallback (tkinter)
# -----------------------------

def _copy_text_fallback(text: str) -> Tuple[bool, str]:
    """Fallback: copy plain text to clipboard using tkinter."""
    try:
        import tkinter as tk

        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()  # keeps data after window closed
        r.destroy()
        return True, "Copied path as text"
    except Exception as e:
        return False, f"Text clipboard fallback failed: {e}"


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ns = ap.parse_args()
    ok, msg = copy_file_to_clipboard(Path(ns.path))
    print(msg)
    raise SystemExit(0 if ok else 1)
