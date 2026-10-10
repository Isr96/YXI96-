"""Capa de Windows: ventana layered, siempre delante, el clic la atraviesa.

La pantalla completa exclusiva de un juego puede dibujar por encima de
cualquier ventana. En ventana o en ventana sin bordes la mira queda delante.
"""

from __future__ import annotations

import ctypes
import queue
import sys
import threading

from .render import premultiply_bgra, render
from .settings import MiraSettings

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
WM_DESTROY = 0x0002
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_M = 0x4D
HWND_TOPMOST = -1
HWND_MESSAGE = -3

_IS_64 = ctypes.sizeof(ctypes.c_void_p) == 8
_WPARAM = ctypes.c_uint64 if _IS_64 else ctypes.c_uint
_LPARAM = ctypes.c_int64 if _IS_64 else ctypes.c_long
_LRESULT = ctypes.c_int64 if _IS_64 else ctypes.c_long
_HWND = ctypes.c_void_p
_HDC = ctypes.c_void_p
_HBITMAP = ctypes.c_void_p
_WNDPROC = ctypes.WINFUNCTYPE(_LRESULT, _HWND, ctypes.c_uint, _WPARAM, _LPARAM)


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", _HWND),
        ("message", ctypes.c_uint),
        ("wParam", _WPARAM),
        ("lParam", _LPARAM),
        ("time", ctypes.c_uint32),
        ("pt", _POINT),
    ]


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
        ("hIconSm", ctypes.c_void_p),
    ]


def _win32():
    if sys.platform != "win32":
        raise OSError("La capa de Windows solo existe en Windows.")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return user32, gdi32, kernel32


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except (OSError, AttributeError):
        pass
    try:
        ctypes.WinDLL("user32").SetProcessDPIAware()
    except (OSError, AttributeError):
        return


def list_monitors() -> list[tuple[int, int, int, int]]:
    user32, _gdi32, _kernel32 = _win32()
    found: list[tuple[int, int, int, int]] = []

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_RECT), ctypes.c_ssize_t
    )

    def _collect(_monitor, _hdc, rect, _data):
        area = rect.contents
        found.append((area.left, area.top, area.right - area.left, area.bottom - area.top))
        return 1

    keeper = callback_type(_collect)
    user32.EnumDisplayMonitors(None, None, keeper, 0)
    return found or [(0, 0, 1920, 1080)]


class WinOverlay:
    def __init__(self) -> None:
        self.user32, self.gdi32, self.kernel32 = _win32()
        self._bind()
        self._proc = _WNDPROC(self._wndproc)
        self._class = "YXI96MiraOverlay"
        self.hwnd = self._create_window()
        self._shown = False

    def update(self, settings: MiraSettings) -> None:
        shape = settings.clamped()
        if not shape.visible:
            self.user32.ShowWindow(self.hwnd, SW_HIDE)
            self._shown = False
            return
        width, height, rgba = render(shape)
        monitors = list_monitors()
        index = shape.monitor if shape.monitor < len(monitors) else 0
        origin_x, origin_y, mon_w, mon_h = monitors[index]
        left = int(origin_x + mon_w / 2 + shape.offset_x - width / 2)
        top = int(origin_y + mon_h / 2 + shape.offset_y - height / 2)
        self._paint(premultiply_bgra(rgba), width, height, left, top)
        self.user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        self.user32.SetWindowPos(
            self.hwnd,
            ctypes.c_void_p(HWND_TOPMOST),
            left,
            top,
            width,
            height,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        self._shown = True

    def raise_top(self) -> None:
        if self._shown:
            self.user32.SetWindowPos(
                self.hwnd,
                ctypes.c_void_p(HWND_TOPMOST),
                0,
                0,
                0,
                0,
                0x0001 | 0x0002 | SWP_NOACTIVATE,
            )

    def close(self) -> None:
        if self.hwnd:
            self.user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def _bind(self) -> None:
        user32 = self.user32
        gdi32 = self.gdi32
        user32.DefWindowProcW.argtypes = [_HWND, ctypes.c_uint, _WPARAM, _LPARAM]
        user32.DefWindowProcW.restype = _LRESULT
        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint32,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            _HWND,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        user32.CreateWindowExW.restype = _HWND
        user32.UpdateLayeredWindow.argtypes = [
            _HWND,
            _HDC,
            ctypes.POINTER(_POINT),
            ctypes.POINTER(_SIZE),
            _HDC,
            ctypes.POINTER(_POINT),
            ctypes.c_uint32,
            ctypes.POINTER(_BLENDFUNCTION),
            ctypes.c_uint32,
        ]
        user32.UpdateLayeredWindow.restype = ctypes.c_int
        user32.SetWindowPos.argtypes = [
            _HWND,
            _HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        gdi32.CreateDIBSection.argtypes = [
            _HDC,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        gdi32.CreateDIBSection.restype = _HBITMAP

    def _create_window(self):
        instance = self.kernel32.GetModuleHandleW(None)
        info = _WNDCLASSEXW()
        info.cbSize = ctypes.sizeof(_WNDCLASSEXW)
        info.lpfnWndProc = self._proc
        info.hInstance = instance
        info.lpszClassName = self._class
        atom = self.user32.RegisterClassExW(ctypes.byref(info))
        if not atom and ctypes.get_last_error() not in (0, 1410):
            raise OSError(f"No se pudo registrar la ventana ({ctypes.get_last_error()}).")
        extra = (
            WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOPMOST
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
        )
        hwnd = self.user32.CreateWindowExW(
            extra,
            self._class,
            "YXI96 Mira",
            WS_POPUP,
            0,
            0,
            10,
            10,
            None,
            None,
            instance,
            None,
        )
        if not hwnd:
            raise OSError(f"No se pudo crear la mira ({ctypes.get_last_error()}).")
        return hwnd

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_DESTROY:
            return 0
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _paint(self, bgra: bytes, width: int, height: int, left: int, top: int) -> None:
        user32 = self.user32
        gdi32 = self.gdi32
        screen = user32.GetDC(None)
        memory = gdi32.CreateCompatibleDC(screen)
        header = _BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0
        header.biSizeImage = width * height * 4
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(screen, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits:
            gdi32.DeleteDC(memory)
            user32.ReleaseDC(None, screen)
            raise OSError(f"No se pudo dibujar la mira ({ctypes.get_last_error()}).")
        ctypes.memmove(bits, bgra, len(bgra))
        previous = gdi32.SelectObject(memory, bitmap)
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        origin = _POINT(0, 0)
        destination = _POINT(left, top)
        size = _SIZE(width, height)
        ok = user32.UpdateLayeredWindow(
            self.hwnd,
            screen,
            ctypes.byref(destination),
            ctypes.byref(size),
            memory,
            ctypes.byref(origin),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )
        gdi32.SelectObject(memory, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)
        if not ok:
            raise OSError(f"UpdateLayeredWindow falló ({ctypes.get_last_error()}).")


class GlobalHotkey:
    """Ctrl+Alt+M alterna la mira aunque el panel no tenga el foco."""

    def __init__(self, events: queue.Queue) -> None:
        self.events = events
        self.user32, _gdi, self.kernel32 = _win32()
        self._proc = _WNDPROC(self._wndproc)
        self._stop = threading.Event()
        self.available = False
        self._thread_id = 0
        self.thread = threading.Thread(target=self._loop, name="yxi96-mira-hotkey", daemon=True)
        self.thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread_id:
            self.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _loop(self) -> None:
        user32 = self.user32
        self.kernel32.GetCurrentThreadId.restype = ctypes.c_uint32
        self._thread_id = int(self.kernel32.GetCurrentThreadId())
        user32.PostThreadMessageW.argtypes = [ctypes.c_uint32, ctypes.c_uint, _WPARAM, _LPARAM]
        user32.DefWindowProcW.argtypes = [_HWND, ctypes.c_uint, _WPARAM, _LPARAM]
        user32.DefWindowProcW.restype = _LRESULT
        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint32,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            _HWND,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        user32.CreateWindowExW.restype = _HWND
        instance = self.kernel32.GetModuleHandleW(None)
        class_name = "YXI96MiraHotkey"
        info = _WNDCLASSEXW()
        info.cbSize = ctypes.sizeof(_WNDCLASSEXW)
        info.lpfnWndProc = self._proc
        info.hInstance = instance
        info.lpszClassName = class_name
        user32.RegisterClassExW(ctypes.byref(info))
        hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "YXI96 Mira hotkey",
            0,
            0,
            0,
            0,
            0,
            ctypes.c_void_p(HWND_MESSAGE),
            None,
            instance,
            None,
        )
        if hwnd and user32.RegisterHotKey(hwnd, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_M):
            self.available = True
            self.events.put(("hotkey", True))
        else:
            self.events.put(("hotkey", False))
            if hwnd:
                user32.DestroyWindow(hwnd)
            return
        message = _MSG()
        while not self._stop.is_set():
            code = user32.GetMessageW(ctypes.byref(message), hwnd, 0, 0)
            if code <= 0:
                break
            if message.message == WM_HOTKEY:
                self.events.put(("toggle", None))
        if hwnd:
            user32.UnregisterHotKey(hwnd, 1)
            user32.DestroyWindow(hwnd)
