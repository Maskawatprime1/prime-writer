"""Per-pixel-alpha (layered) top-most windows drawn from Pillow images. Pure ctypes."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
from typing import Callable

from PIL import Image, ImageChops

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST = 0x80000, 0x20, 0x8
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x08000000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
WM_MOUSEACTIVATE, MA_NOACTIVATE = 0x0021, 3
WM_LBUTTONUP, WM_SETCURSOR = 0x0202, 0x0020
HWND_TOPMOST = wt.HWND(-1)
SWP_NOACTIVATE, SWP_NOSIZE, SWP_NOMOVE = 0x10, 0x1, 0x2


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
                ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE), wt.HDC,
                                       ctypes.POINTER(wt.POINT), wt.COLORREF, ctypes.POINTER(BLENDFUNCTION), wt.DWORD]
user32.LoadCursorW.argtypes = [wt.HINSTANCE, wt.LPVOID]
user32.LoadCursorW.restype = wt.HANDLE
user32.SetCursor.argtypes = [wt.HANDLE]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
kernel32.GetModuleHandleW.restype = wt.HMODULE

_CLASS = "PrimeWriterLayer"
_windows: dict[int, "LayeredWindow"] = {}  # hwnd -> clickable window
WM_LBUTTONDOWN, WM_MOUSEMOVE, WM_CAPTURECHANGED = 0x0201, 0x0200, 0x0215
DRAG_THRESHOLD = 4  # pixels before a press becomes a drag
user32.SetCapture.argtypes = [wt.HWND]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]


def _cursor() -> tuple[int, int]:
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


@WNDPROC
def _wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_MOUSEACTIVATE:
        return MA_NOACTIVATE  # clicking never steals focus from the app you're typing in
    win = _windows.get(hwnd)
    if win is None:
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    try:
        if msg == WM_SETCURSOR:
            cur = 32646 if win.dragging else 32649  # IDC_SIZEALL while dragging, IDC_HAND otherwise
            user32.SetCursor(user32.LoadCursorW(None, ctypes.c_void_p(cur)))
            return 1
        if msg == WM_LBUTTONDOWN:
            win.press = (_cursor(), (win.x, win.y))
            user32.SetCapture(hwnd)
            return 0
        if msg == WM_MOUSEMOVE and win.press:
            (sx, sy), (wx, wy) = win.press
            cx, cy = _cursor()
            if not win.dragging and abs(cx - sx) + abs(cy - sy) >= DRAG_THRESHOLD:
                win.dragging = True
                if win.on_drag_start:
                    win.on_drag_start()
            if win.dragging:
                win.move(wx + cx - sx, wy + cy - sy)
            return 0
        if msg == WM_LBUTTONUP and win.press:
            dragged, win.press, win.dragging = win.dragging, None, False
            user32.ReleaseCapture()
            if dragged:
                if win.on_drag_end:
                    win.on_drag_end(win.x, win.y)
            elif win.on_click:
                win.on_click(hwnd)
            return 0
        if msg == WM_CAPTURECHANGED and win.dragging:
            win.press, win.dragging = None, False
            if win.on_drag_end:
                win.on_drag_end(win.x, win.y)
            return 0
    except Exception as e:  # noqa: BLE001
        print("layer mouse error:", e)
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_registered = False


def _register() -> None:
    global _registered
    if _registered:
        return
    wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=_wndproc,
                     hInstance=kernel32.GetModuleHandleW(None), lpszClassName=_CLASS)
    user32.RegisterClassExW(ctypes.byref(wc))
    _registered = True


def _premultiplied_bgra(img: Image.Image) -> bytes:
    r, g, b, a = img.split()
    r, g, b = (ImageChops.multiply(c, a) for c in (r, g, b))
    return Image.merge("RGBA", (b, g, r, a)).tobytes()


class LayeredWindow:
    """Top-most, never-activating window. click_through=True passes every click to the app below."""

    def __init__(self, click_through: bool, on_click: Callable[[int], None] | None = None,
                 on_drag_start: Callable[[], None] | None = None, on_drag_end: Callable[[int, int], None] | None = None):
        _register()
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if click_through:
            ex |= WS_EX_TRANSPARENT
        self.hwnd = user32.CreateWindowExW(ex, _CLASS, "", WS_POPUP, 0, 0, 1, 1, None, None,
                                           kernel32.GetModuleHandleW(None), None)
        self.on_click, self.on_drag_start, self.on_drag_end = on_click, on_drag_start, on_drag_end
        if on_click or on_drag_end:
            _windows[self.hwnd] = self
        self.visible = False
        self._last_key = None
        self.x = self.y = 0
        self.press = None       # ((cursor x, y), (window x, y)) while the mouse button is down
        self.dragging = False

    def move(self, x: int, y: int) -> None:
        self.x, self.y = x, y
        self._last_key = None
        user32.SetWindowPos(self.hwnd, None, x, y, 0, 0, SWP_NOACTIVATE | SWP_NOSIZE | 0x4)  # NOZORDER

    def update(self, img: Image.Image, x: int, y: int) -> None:
        if self.dragging:
            return  # the user is moving it; don't snap back
        self.x, self.y = x, y
        key = (x, y, img.size, img.tobytes())
        if key == self._last_key:
            if not self.visible:
                self.show()
            return
        self._last_key = key
        w, h = img.size
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        data = _premultiplied_bgra(img)
        ctypes.memmove(bits, data, len(data))
        old = gdi32.SelectObject(mem, hbmp)
        blend = BLENDFUNCTION(0, 0, 255, 1)  # AC_SRC_OVER, AC_SRC_ALPHA
        user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(wt.POINT(x, y)), ctypes.byref(wt.SIZE(w, h)),
                                   mem, ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), 2)  # ULW_ALPHA
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, screen)
        self.show()

    def show(self) -> None:
        # Raise only when it appears; raising every frame would cover the suggestion card.
        if not self.visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE)
            self.visible = True

    def hide(self) -> None:
        if self.visible:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False
