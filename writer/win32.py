"""Windows helpers (ctypes only): active app, window list, clipboard, key input, global hotkeys."""
from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes as wt
from typing import Callable

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    shcore = ctypes.WinDLL("shcore")
except OSError:  # pragma: no cover
    shcore = None

OWN_PID = os.getpid()

# ---------- signatures ----------
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.OpenClipboard.argtypes = [wt.HWND]
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.GetClipboardSequenceNumber.restype = wt.DWORD
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
user32.MonitorFromPoint.restype = wt.HMONITOR
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, wt.LONG]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.c_void_p]
user32.GetDpiForWindow.argtypes = [wt.HWND]
user32.GetDpiForWindow.restype = wt.UINT
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalFree.argtypes = [wt.HGLOBAL]
kernel32.GetCurrentThreadId.restype = wt.DWORD

# ---------- apps & windows ----------
def _pid_of(hwnd) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_exe(pid: int) -> str:
    h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def window_title(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def foreground() -> tuple[int, str, str, int]:
    """(hwnd, exe name, title, pid) of the active window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0, "", "", 0
    pid = _pid_of(hwnd)
    return hwnd, process_exe(pid), window_title(hwnd), pid


def list_window_apps() -> dict[str, str]:
    """exe name -> one window title, for every app with a visible top-level window."""
    apps: dict[str, str] = {}
    WS_EX_TOOLWINDOW, GWL_EXSTYLE, GW_OWNER = 0x80, -20, 4

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, GW_OWNER):
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        title = window_title(hwnd)
        pid = _pid_of(hwnd)
        if not title or pid == OWN_PID:
            return True
        exe = process_exe(pid)
        if exe and exe not in apps:
            apps[exe] = title
        return True

    user32.EnumWindows(cb, 0)
    return apps


def activate(hwnd) -> bool:
    """Bring a window to the front, working around Windows' focus-stealing protection."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    me = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)
    return user32.GetForegroundWindow() == hwnd


# ---------- clipboard ----------
CF_UNICODETEXT = 13


def _open_clipboard() -> bool:
    for _ in range(25):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def get_clipboard() -> str | None:
    if not _open_clipboard():
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def set_clipboard(text: str) -> bool:
    data = text.encode("utf-16-le") + b"\x00\x00"
    h = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    p = kernel32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    kernel32.GlobalUnlock(h)
    if not _open_clipboard():
        kernel32.GlobalFree(h)
        return False
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            kernel32.GlobalFree(h)
            return False
        return True
    finally:
        user32.CloseClipboard()


def clipboard_seq() -> int:
    return user32.GetClipboardSequenceNumber()


# ---------- keyboard input ----------
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C
KEYEVENTF_KEYUP = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _key(vk: int, up: bool = False) -> INPUT:
    return INPUT(type=1, u=_U(ki=KEYBDINPUT(wVk=vk, dwFlags=KEYEVENTF_KEYUP if up else 0)))


def send_ctrl(letter: str) -> None:
    """Press Ctrl+<letter> in the active app."""
    vk = ord(letter.upper())
    seq = [_key(VK_CONTROL), _key(vk), _key(vk, True), _key(VK_CONTROL, True)]
    arr = (INPUT * len(seq))(*seq)
    user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))


def send_key(vk: int) -> None:
    seq = [_key(vk), _key(vk, True)]
    user32.SendInput(2, (INPUT * 2)(*seq), ctypes.sizeof(INPUT))


def mask_alt() -> None:
    """Tap an unassigned key (vkE8) while Alt is held so releasing Alt doesn't open the app's menu bar."""
    seq = [_key(0xE8), _key(0xE8, True)]
    arr = (INPUT * 2)(*seq)
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def wait_modifiers_released(timeout: float = 2.0) -> None:
    """The hotkey's Ctrl/Alt/Shift may still be held; Ctrl+C would then become Ctrl+Alt+C."""
    end = time.time() + timeout
    while time.time() < end:
        if not any(user32.GetAsyncKeyState(k) & 0x8000 for k in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)):
            return
        time.sleep(0.02)


# ---------- screen ----------
def cursor_pos() -> tuple[int, int]:
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def popup_position(w_logical: int, h_logical: int) -> tuple[int, int]:
    """Logical (DPI-independent) x,y for a popup near the mouse, kept inside the monitor's work area."""
    x, y = cursor_pos()
    mon = user32.MonitorFromPoint(wt.POINT(x, y), 2)  # MONITOR_DEFAULTTONEAREST
    scale = 1.0
    if shcore:
        dx, dy = wt.UINT(), wt.UINT()
        if shcore.GetDpiForMonitor(mon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
            scale = dx.value / 96
    mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(mon, ctypes.byref(mi))
    wa = mi.rcWork
    w, h = int(w_logical * scale), int(h_logical * scale)
    px = min(max(wa.left, x + 12), wa.right - w)
    py = y + 18 if y + 18 + h <= wa.bottom else max(wa.top, y - h - 12)
    return int(px / scale), int(py / scale)


# ---------- global hotkeys ----------
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY, WM_TIMER, WM_QUIT = 0x0312, 0x0113, 0x0012


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("message", wt.UINT), ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
                ("time", wt.DWORD), ("pt", wt.POINT)]


def parse_hotkey(spec: str) -> tuple[int, int]:
    """'Ctrl+Alt+G' -> (modifiers, vk)."""
    mods, vk = MOD_NOREPEAT, 0
    for part in spec.replace(" ", "").split("+"):
        p = part.lower()
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "alt":
            mods |= MOD_ALT
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p == "space":
            vk = 0x20
        elif len(p) == 1 and p.isalnum():
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit():
            vk = 0x6F + int(p[1:])
    if not vk:
        raise ValueError(f"Bad hotkey: {spec}")
    return mods, vk


class HotkeyThread(threading.Thread):
    """Registers hotkeys only while an allowed app is in front, so blocked apps get the keys untouched."""

    def __init__(self, hotkeys: dict[str, str], allowed: Callable[[str, int], bool], on_hotkey: Callable[[str], None]):
        super().__init__(daemon=True, name="hotkeys")
        self.hotkeys = hotkeys          # action -> "Ctrl+Alt+G"
        self.allowed = allowed          # (exe, pid) -> bool
        self.on_hotkey = on_hotkey
        self.tid = 0
        self.registered = False
        self.dirty = False              # set True after changing self.hotkeys
        self.errors: list[str] = []
        self._ids: dict[int, str] = {}

    def _register(self, on: bool) -> None:
        if on == self.registered:
            return
        if on:
            self.errors = []
            for i, (action, spec) in enumerate(self.hotkeys.items(), start=1):
                mods, vk = parse_hotkey(spec)
                if user32.RegisterHotKey(None, i, mods, vk):
                    self._ids[i] = action
                else:
                    self.errors.append(f"{spec} is used by another program")
        else:
            for i in list(self._ids):
                user32.UnregisterHotKey(None, i)
            self._ids.clear()
        self.registered = on

    def run(self) -> None:
        self.tid = kernel32.GetCurrentThreadId()
        user32.SetTimer(None, 0, 200, None)
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_TIMER:
                if self.dirty:
                    self._register(False)
                    self.dirty = False
                _, exe, _, pid = foreground()
                try:
                    self._register(bool(exe) and self.allowed(exe, pid))
                except Exception:  # noqa: BLE001
                    pass
            elif msg.message == WM_HOTKEY:
                action = self._ids.get(msg.wParam)
                if action:
                    try:
                        self.on_hotkey(action)
                    except Exception as e:  # noqa: BLE001
                        print("hotkey error:", e)
        self._register(False)

    def stop(self) -> None:
        if self.tid:
            user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)
