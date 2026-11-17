"""Desktop app: tray icon + global hotkeys + quick popup + the Writer window.

Select text in any app, press Ctrl+Alt+G (check) or Ctrl+Alt+P (paraphrase); the popup shows
results and "Replace in app" pastes them back. Per-app on/off lives in Settings.

Dev run:   .venv\\Scripts\\python -m writer.desktop
Exe build: build_exe.ps1
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# The packaged exe has no console; give uvicorn/prints somewhere to write.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import httpx
import pystray
import uvicorn
import webview
from PIL import Image, ImageDraw, ImageFont

from shared import ollama
from writer import config, server, win32
from writer.server import app

PREFERRED_PORT = 8765
POPUP_W, POPUP_H = 500, 600
STARTUP_LNK = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "PrimeWriter.lnk"
MUTEX_NAME = "Local\\PrimeWriterDesktopApp"


def make_icon(on: bool = True, size: int = 64) -> Image.Image:
    from writer.brand import make_logo
    return make_logo(size, "square", on=on)


def ensure_ollama() -> None:
    """Start Ollama in the background if it is installed but not running."""
    if ollama.is_up():
        return
    import shutil
    candidates = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
                  Path(shutil.which("ollama") or "")]
    exe = next((p for p in candidates if p.is_file()), None)
    if exe:
        subprocess.Popen([str(exe), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def port_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


class PopupApi:
    """Methods callable from popup.js as window.pywebview.api.*"""

    def __init__(self, desk: "Desktop"):
        self._desk = desk

    def replace(self, text: str) -> bool:
        print(f"popup: replace ({len(text)} chars)", flush=True)
        return self._desk.paste_back(text)

    def log(self, msg: str) -> None:
        print("popup js:", msg, flush=True)

    def close(self) -> None:
        self._desk.hide_popup(refocus=True)

    def disable_app(self) -> None:
        exe = self._desk.target_exe
        if exe:
            config.set_app_enabled(exe, False)
            self._desk.notify(f"Turned off in {exe}. Turn it back on in Settings.")
        self._desk.hide_popup(refocus=True)


class CardApi:
    """Methods callable from card.html (the hover suggestion card)."""

    def __init__(self, desk: "Desktop"):
        self._desk = desk

    def apply(self, i: int) -> None:
        if self._desk.overlay:
            self._desk.overlay.post(self._desk.overlay.apply_fix, int(i))

    def ignore(self) -> None:
        if self._desk.overlay:
            self._desk.overlay.post(self._desk.overlay.ignore_current)

    def disable_app(self) -> None:
        ov = self._desk.overlay
        exe = ov.field.exe if ov and ov.field else ""
        if exe:
            config.set_app_enabled(exe, False)
            self._desk.notify(f"Turned off in {exe}. Turn it back on in Settings.")
        if ov:
            ov.post(ov.clear)

    def add_word(self) -> None:
        if self._desk.overlay:
            self._desk.overlay.post(self._desk.overlay.add_word_current)

    def rewrite(self) -> None:
        if self._desk.overlay:
            self._desk.overlay.post(self._desk.overlay.start_rewrite)

    def use_rewrite(self) -> None:
        if self._desk.overlay:
            self._desk.overlay.post(self._desk.overlay.apply_rewrite)

    def fit(self, height: float) -> None:
        self._desk.fit_card(float(height))


OFFSCREEN = -32000
CARD_W, CARD_H = 360, 190


class Desktop:
    def __init__(self, base_url: str, background: bool):
        self.base = base_url
        self.background = background
        self.main: webview.Window | None = None
        self.popup: webview.Window | None = None
        self.card: webview.Window | None = None
        self.card_hwnd = 0
        self.card_ready = threading.Event()
        self.overlay = None
        self.select_hook = None  # set by the floating button: selects the whole text box before Replace
        self.tray: pystray.Icon | None = None
        self.hotkeys: win32.HotkeyThread | None = None
        self.quitting = False
        self.target_hwnd = 0
        self.target_exe = ""
        self.popup_ready = threading.Event()
        self._busy = threading.Lock()

    # ----- hooks used by writer.server -----
    def set_startup(self, on: bool) -> str | None:
        if not getattr(sys, "frozen", False):
            return "Start with Windows works only in PrimeWriter.exe"
        try:
            if on:
                exe = sys.executable.replace("'", "''")
                lnk = str(STARTUP_LNK).replace("'", "''")
                ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
                      f"$s.TargetPath='{exe}';$s.Arguments='--background';"
                      f"$s.WorkingDirectory='{Path(exe).parent}';$s.Description='Prime Writer';$s.Save()")
                subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True,
                               capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            elif STARTUP_LNK.exists():
                STARTUP_LNK.unlink()
        except (OSError, subprocess.CalledProcessError) as e:
            return f"Could not update the Startup folder: {e}"
        return None

    def reload_hotkeys(self) -> None:
        if self.hotkeys:
            self.hotkeys.hotkeys = config.get()["hotkeys"]
            self.hotkeys.dirty = True

    def hotkey_errors(self) -> list[str]:
        return list(self.hotkeys.errors) if self.hotkeys else []

    def show_main(self, path: str = "/") -> None:
        if not self.main:
            return
        url = self.base + path
        try:
            current = self.main.get_current_url() or ""
        except Exception:  # noqa: BLE001
            current = ""
        if current.rstrip("/") != url.rstrip("/"):
            self.main.load_url(url)
        self.main.show()
        self.main.restore()

    # ----- tray -----
    def notify(self, msg: str) -> None:
        try:
            if self.tray:
                self.tray.notify(msg, "Prime Writer")
        except Exception:  # noqa: BLE001
            pass

    def toggle_enabled(self, *_):
        on = not config.get()["enabled"]
        config.update(enabled=on)
        self.refresh_tray()
        self.notify("On in all apps" if on else "Off everywhere. Hotkeys go to your apps untouched.")

    def toggle_live(self, *_):
        config.update(live=not config.get()["live"])

    def refresh_tray(self) -> None:
        if self.tray:
            on = config.get()["enabled"]
            self.tray.icon = make_icon(on)
            self.tray.title = "Prime Writer" + ("" if on else " (off)")

    def start_tray(self) -> None:
        hk = config.get()["hotkeys"]
        menu = pystray.Menu(
            pystray.MenuItem("Open Writer", lambda *_: self.show_main("/"), default=True),
            pystray.MenuItem("Settings (apps on/off)", lambda *_: self.show_main("/settings")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("On in all apps", self.toggle_enabled, checked=lambda _: config.get()["enabled"]),
            pystray.MenuItem("Live underlines while typing", self.toggle_live, checked=lambda _: config.get()["live"]),
            pystray.MenuItem(f"Check: {hk['check']}   Paraphrase: {hk['paraphrase']}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda *_: self.quit()),
        )
        self.tray = pystray.Icon("PrimeWriter", make_icon(config.get()["enabled"]), "Prime Writer", menu)
        threading.Thread(target=self.tray.run, daemon=True, name="tray").start()

    # ----- hotkey flow -----
    def allowed(self, exe: str, pid: int) -> bool:
        return pid != win32.OWN_PID and config.app_enabled(exe)

    def on_hotkey(self, action: str) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            win32.mask_alt()
            hwnd, exe, title, _ = win32.foreground()
            win32.wait_modifiers_released()
            saved = win32.get_clipboard()
            before = win32.clipboard_seq()
            win32.send_ctrl("c")
            text = None
            for _ in range(30):  # up to ~0.6 s for the app to copy
                time.sleep(0.02)
                if win32.clipboard_seq() != before:
                    time.sleep(0.03)
                    text = win32.get_clipboard()
                    break
            if text is not None and saved is not None:
                win32.set_clipboard(saved)  # leave the user's clipboard as it was
            print(f"hotkey {action} in {exe}: copied {len(text) if text else 0} chars", flush=True)
            self.target_hwnd, self.target_exe, self.select_hook = hwnd, exe, None
            if exe:
                config.remember_app(exe, title)
            payload = {
                "text": (text or "").replace("\r\n", "\n"),
                "hadSelection": bool(text and text.strip()),
                "action": action,
                "exe": exe,
                "mode": config.get()["popup_mode"],
            }
            t0 = time.perf_counter()
            x, y = win32.popup_position(POPUP_W, POPUP_H)
            self.popup_ready.wait(15)
            self.popup.evaluate_js(f"window.openWith({json.dumps(payload)})")
            t1 = time.perf_counter()
            self.popup.move(x, y)
            self.popup.show()
            t2 = time.perf_counter()
            self.focus_popup()
            print(f"popup timing: js {t1 - t0:.2f}s, show {t2 - t1:.2f}s, focus {time.perf_counter() - t2:.2f}s", flush=True)
        finally:
            self._busy.release()

    def focus_popup(self) -> None:
        """pywebview focuses the web view only on the first show; do it every time so keys work."""
        form = getattr(self.popup, "native", None)
        if form is None:
            return
        try:
            from System import Func, Type  # pythonnet, loaded by pywebview

            hwnd = int(form.Handle.ToInt64())

            def _focus():
                form.Activate()
                form.browser.webview.Focus()

            # Windows sometimes hands focus back to the previous app; re-assert for ~1 s.
            for _ in range(12):
                if win32.user32.GetForegroundWindow() != hwnd:
                    win32.activate(hwnd)
                form.Invoke(Func[Type](_focus))
                time.sleep(0.1)
                if win32.user32.GetForegroundWindow() == hwnd and _ >= 3:
                    break
            self.popup.evaluate_js("document.getElementById('src').focus()")
        except Exception as e:  # noqa: BLE001
            print("focus error:", e)

    def hide_popup(self, refocus: bool) -> None:
        if self.popup:
            self.popup.hide()
        if refocus:
            win32.activate(self.target_hwnd)

    # ----- hover card (shown without taking focus from the app you're typing in) -----
    def _setup_card(self) -> None:
        form = getattr(self.card, "native", None)
        if form is None:
            return
        self.card_hwnd = int(form.Handle.ToInt64())
        u = win32.user32
        u.ShowWindow(self.card_hwnd, 0)  # hide, add WS_EX_TOOLWINDOW (no taskbar button), show again off-screen
        ex = u.GetWindowLongW(self.card_hwnd, -20)
        u.SetWindowLongW(self.card_hwnd, -20, ex | 0x80 | 0x08000000 | 0x8)
        self._place_card(OFFSCREEN, OFFSCREEN)
        u.ShowWindow(self.card_hwnd, 4)  # SW_SHOWNOACTIVATE
        self.card_ready.set()

    def _place_card(self, x: int, y: int) -> None:
        win32.user32.SetWindowPos(self.card_hwnd, -1, x, y, 0, 0, 0x10 | 0x1)  # TOPMOST, NOACTIVATE|NOSIZE

    def show_card(self, payload: dict, rect: tuple[int, int, int, int]) -> None:
        if not self.card_ready.is_set():
            return
        fn = "showSynonymsLoading" if payload.get("mode") == "synonyms" else "showIssue"
        self.card.evaluate_js(f"window.{fn}({json.dumps(payload)})")
        r = ctypes.wintypes.RECT()
        win32.user32.GetWindowRect(self.card_hwnd, ctypes.byref(r))
        cw, ch = r.right - r.left, r.bottom - r.top
        x, y, w, h = rect
        mon = win32.user32.MonitorFromPoint(ctypes.wintypes.POINT(x, y), 2)
        mi = win32.MONITORINFO(cbSize=ctypes.sizeof(win32.MONITORINFO))
        win32.user32.GetMonitorInfoW(mon, ctypes.byref(mi))
        wa = mi.rcWork
        cx = min(max(wa.left, x), wa.right - cw)
        cy = y + h + 8 if y + h + 8 + ch <= wa.bottom else max(wa.top, y - ch - 8)
        self._place_card(cx, cy)

    def hide_card(self) -> None:
        if self.card_hwnd:
            self._place_card(OFFSCREEN, OFFSCREEN)

    def card_js(self, script: str) -> None:
        if self.card_ready.is_set():
            threading.Thread(target=self.card.evaluate_js, args=(script,), daemon=True).start()

    def fit_card(self, css_height: float) -> None:
        """Resize the card to its content (CSS px -> physical px)."""
        if not self.card_hwnd:
            return
        try:
            scale = win32.user32.GetDpiForWindow(self.card_hwnd) / 96 or 1.0
        except Exception:  # noqa: BLE001
            scale = 1.0
        h = int(min(max(css_height, 80), 640) * scale) + 2
        w = int(CARD_W * scale)
        win32.user32.SetWindowPos(self.card_hwnd, None, 0, 0, w, h, 0x10 | 0x2 | 0x4)  # NOACTIVATE|NOMOVE|NOZORDER

    def cursor_on_card(self, x: int, y: int) -> bool:
        if not self.card_hwnd:
            return False
        r = ctypes.wintypes.RECT()
        win32.user32.GetWindowRect(self.card_hwnd, ctypes.byref(r))
        return r.left - 8 <= x <= r.right + 8 and r.top - 12 <= y <= r.bottom + 8

    # ----- floating button -> panel for the whole text box -----
    def open_panel(self, text: str, exe: str, hwnd: int, select_hook) -> None:
        self.target_hwnd, self.target_exe, self.select_hook = hwnd, exe, select_hook
        payload = {"text": text, "hadSelection": True, "action": "check", "exe": exe,
                   "mode": config.get()["popup_mode"]}
        x, y = win32.popup_position(POPUP_W, POPUP_H)
        self.popup_ready.wait(15)
        self.popup.evaluate_js(f"window.openWith({json.dumps(payload)})")
        self.popup.move(x, y)
        self.popup.show()
        self.focus_popup()

    def paste_back(self, text: str) -> bool:
        self.hide_popup(refocus=False)
        time.sleep(0.08)
        hook, self.select_hook = self.select_hook, None
        if hook:
            hook()  # activates the app and selects all text in the box
        else:
            win32.activate(self.target_hwnd)
        time.sleep(0.15)
        print("paste_back: front is", win32.foreground()[1], flush=True)
        saved = win32.get_clipboard()
        if not win32.set_clipboard(text.replace("\r\n", "\n").replace("\n", "\r\n")):
            return False
        win32.send_ctrl("v")
        time.sleep(0.5)  # let the app read the clipboard before restoring it
        if saved is not None:
            win32.set_clipboard(saved)
        return True

    # ----- lifecycle -----
    def _hide_instead_of_close(self, window: webview.Window):
        def handler():
            if self.quitting:
                return True
            threading.Thread(target=window.hide, daemon=True).start()
            return False
        window.events.closing += handler

    def after_start(self) -> None:
        self.start_tray()
        self.hotkeys = win32.HotkeyThread(config.get()["hotkeys"], self.allowed, self.on_hotkey)
        self.hotkeys.start()
        try:
            from writer.overlay import Overlay
            self.card_ready.clear()
            self.card_loaded.wait(20)
            self._setup_card()
            self.overlay = Overlay(self)
            self.overlay.start()
        except Exception as e:  # noqa: BLE001
            print("live underlines unavailable:", e, flush=True)
        hk = config.get()["hotkeys"]
        if self.background:
            time.sleep(1.5)
            self.notify(f"Running in the tray. Select text anywhere and press {hk['check']} or {hk['paraphrase']}.")

    def quit(self) -> None:
        self.quitting = True
        if self.hotkeys:
            self.hotkeys.stop()
        if self.overlay:
            self.overlay.stop()
        if self.tray:
            self.tray.stop()
        for w in (self.card, self.popup, self.main):
            try:
                w.destroy()
            except Exception:  # noqa: BLE001
                pass


def already_running() -> bool:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    already_running.handle = k32.CreateMutexW(None, False, MUTEX_NAME)  # keep a reference
    return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


APP_ID = "MaskawatAlSium.PrimeWriter"  # Windows app identity: taskbar grouping, icon and pinning


def main() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--background", action="store_true", help="start in the tray without opening a window")
    args, _ = parser.parse_known_args()

    if already_running():
        if not args.background:
            try:
                httpx.Client(trust_env=False).post(f"http://127.0.0.1:{PREFERRED_PORT}/api/show", timeout=3)
            except httpx.HTTPError:
                pass
        return

    config.APP_DATA.mkdir(parents=True, exist_ok=True)
    if getattr(sys, "frozen", False) and config.get()["start_with_windows"] != STARTUP_LNK.exists():
        config.update(start_with_windows=STARTUP_LNK.exists())  # the installer may have added/removed it
    threading.Thread(target=ensure_ollama, daemon=True).start()

    port = PREFERRED_PORT if port_free(PREFERRED_PORT) else 0
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    deadline = time.time() + 90
    while not srv.started and time.time() < deadline and t.is_alive():
        time.sleep(0.1)
    if port == 0 and srv.servers:
        port = srv.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    desk = Desktop(base, args.background)
    server.DESKTOP = desk
    desk.main = webview.create_window("Prime Writer", base + "/", width=1320, height=860,
                                      min_size=(720, 520), hidden=args.background)
    desk.popup = webview.create_window("Prime Writer", base + "/popup", width=POPUP_W, height=POPUP_H,
                                       min_size=(380, 360), hidden=True, on_top=True, js_api=PopupApi(desk))
    desk.popup.events.loaded += lambda: desk.popup_ready.set()
    desk.card = webview.create_window("Prime Writer Suggestion", base + "/card", width=CARD_W, height=CARD_H,
                                      x=OFFSCREEN, y=OFFSCREEN, frameless=True, easy_drag=False, on_top=True,
                                      focus=False, js_api=CardApi(desk))
    card_loaded = threading.Event()
    desk.card.events.loaded += lambda: card_loaded.set()
    desk._hide_instead_of_close(desk.main)
    desk._hide_instead_of_close(desk.popup)
    desk._hide_instead_of_close(desk.card)
    desk.card_loaded = card_loaded

    webview.start(desk.after_start, private_mode=False, storage_path=str(config.APP_DATA / "webview"))

    desk.quitting = True
    if desk.hotkeys:
        desk.hotkeys.stop()
    srv.should_exit = True  # lifespan shutdown stops LanguageTool
    t.join(timeout=10)


if __name__ == "__main__":
    main()
