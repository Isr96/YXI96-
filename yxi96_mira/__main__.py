"""Arranque de YXI96 Mira."""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .settings import config_dir, load_settings, save_settings, settings_path
from .ui import MiraApp


def main() -> None:
    if sys.platform == "win32":
        from .overlay_windows import enable_dpi_awareness

        enable_dpi_awareness()
    lock = _acquire_lock()
    if lock is None:
        _tell("YXI96 Mira ya está abierto.")
        return
    atexit.register(_release_lock, lock)
    settings = load_settings()
    save_settings(settings)
    try:
        overlay = _overlay()
        overlay.update(settings)
    except Exception as error:
        _release_lock(lock)
        _tell(str(error))
        return
    try:
        app = MiraApp(settings, overlay, events=_events(overlay))
        _ = app
    finally:
        overlay.close()
        _release_lock(lock)


def _overlay():
    if sys.platform == "win32":
        from .overlay_windows import WinOverlay

        return WinOverlay()
    return LinuxOverlay(settings_path())


def _events(overlay):
    import queue

    events: queue.Queue = queue.Queue()
    if sys.platform == "win32":
        from .overlay_windows import GlobalHotkey

        overlay.hotkey = GlobalHotkey(events)
        original = overlay.close

        def close():
            overlay.hotkey.close()
            original()

        overlay.close = close
    return events


class LinuxOverlay:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.proc: subprocess.Popen | None = None
        self.log = None
        self._start()

    def update(self, settings) -> None:
        save_settings(settings, self.path)
        if self.proc is None or self.proc.poll() is not None:
            detail = self._log_tail()
            self._start()
            if self.proc is None or self.proc.poll() is not None:
                raise RuntimeError(detail or "No se pudo abrir la mira encima de la pantalla.")

    def raise_top(self) -> None:
        return

    def close(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.log is not None:
            self.log.close()
            self.log = None

    def _start(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            return
        root = Path(__file__).resolve().parents[1]
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        self.log = open(folder / "overlay.log", "w", encoding="utf-8", buffering=1)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "yxi96_mira.overlay_linux", str(self.path)],
            cwd=str(root),
            env=env,
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )

    def _log_tail(self) -> str:
        file = config_dir() / "overlay.log"
        try:
            lines = file.read_text(encoding="utf-8").strip().splitlines()
        except OSError:
            return ""
        return lines[-1] if lines else ""


def _acquire_lock() -> Path | None:
    folder = config_dir()
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / "mira.lock"
    if lock.exists():
        try:
            pid = int(lock.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = 0
        if pid and _alive(pid):
            return None
    lock.write_text(str(os.getpid()), encoding="utf-8")
    return lock


def _release_lock(lock: Path) -> None:
    try:
        if lock.exists() and lock.read_text(encoding="utf-8").strip() == str(os.getpid()):
            lock.unlink()
    except OSError:
        return


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _tell(message: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("YXI96 Mira", message)
        root.destroy()
    except tk.TclError:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    main()
