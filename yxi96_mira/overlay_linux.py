"""Ventana transparente, encima de todo y con el clic atravesándola."""

from __future__ import annotations

import os
import sys
from array import array
from pathlib import Path

from .render import premultiply_bgra, render
from .settings import MiraSettings, load_settings


def list_monitors() -> list[tuple[int, int, int, int]]:
    import gi

    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    Gdk.init([])
    display = Gdk.Display.get_default()
    if display is None:
        return [(0, 0, 1920, 1080)]
    found: list[tuple[int, int, int, int]] = []
    for index in range(display.get_n_monitors()):
        geo = display.get_monitor(index).get_geometry()
        found.append((geo.x, geo.y, geo.width, geo.height))
    return found or [(0, 0, 1920, 1080)]


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Uso: python -m yxi96_mira.overlay_linux RUTA.json", file=sys.stderr)
        sys.exit(2)
    path = Path(args[0])
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gdk, GLib, Gtk

    Overlay(path, Gtk, Gdk, GLib)
    Gtk.main()


class Overlay:
    def __init__(self, path: Path, gtk, gdk, glib) -> None:
        self.path = path
        self.gtk = gtk
        self.gdk = gdk
        self.parent = os.getppid()
        self.signature: tuple | None = None
        self.pixels: array | None = None
        self.surface = None
        window = gtk.Window(type=gtk.WindowType.TOPLEVEL)
        self.window = window
        window.set_title("YXI96 Mira overlay")
        window.set_decorated(False)
        window.set_app_paintable(True)
        window.set_keep_above(True)
        window.set_accept_focus(False)
        window.set_focus_on_map(False)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_type_hint(gdk.WindowTypeHint.POPUP_MENU)
        window.set_resizable(False)
        window.stick()
        self._use_rgba()
        window.connect("screen-changed", lambda *_args: self._use_rgba())
        window.connect("realize", lambda *_args: self._pass_through())
        window.connect("map-event", lambda *_args: self._pass_through())
        window.connect("draw", self._draw)
        window.set_default_size(1, 1)
        glib.timeout_add(70, self._sync)
        self._sync()

    def _use_rgba(self) -> None:
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual() if screen is not None else None
        if visual is not None and screen.is_composited():
            self.window.set_visual(visual)

    def _pass_through(self) -> None:
        native = self.window.get_window()
        if native is None:
            return
        if hasattr(native, "set_pass_through"):
            native.set_pass_through(True)
        if hasattr(native, "input_shape_combine_region"):
            import cairo

            native.input_shape_combine_region(cairo.Region(), 0, 0)

    def _draw(self, _widget, context) -> bool:
        import cairo

        context.set_operator(cairo.OPERATOR_SOURCE)
        context.set_source_rgba(0, 0, 0, 0)
        context.paint()
        if self.surface is not None:
            context.set_operator(cairo.OPERATOR_OVER)
            context.set_source_surface(self.surface, 0, 0)
            context.paint()
        return False

    def _sync(self) -> bool:
        if os.getppid() != self.parent:
            self.gtk.main_quit()
            return False
        settings = load_settings(self.path).clamped()
        monitors = list_monitors()
        monitor = settings.monitor if settings.monitor < len(monitors) else 0
        mark = (
            settings.style,
            settings.size,
            settings.thickness,
            round(settings.opacity, 3),
            settings.color,
            settings.outline,
            settings.offset_x,
            settings.offset_y,
            settings.visible,
            monitor,
        )
        if mark == self.signature:
            self.window.set_keep_above(True)
            self._pass_through()
            return True
        self.signature = mark
        if not settings.visible:
            self.window.hide()
            return True
        import cairo

        width, height, rgba = render(settings)
        raw = premultiply_bgra(rgba)
        self.pixels = array("B", raw)
        self.surface = cairo.ImageSurface.create_for_data(
            self.pixels, cairo.FORMAT_ARGB32, width, height, width * 4
        )
        origin_x, origin_y, mon_w, mon_h = monitors[monitor]
        left = int(origin_x + mon_w / 2 + settings.offset_x - width / 2)
        top = int(origin_y + mon_h / 2 + settings.offset_y - height / 2)
        self.window.resize(width, height)
        self.window.set_size_request(width, height)
        self.window.move(left, top)
        if not self.window.get_visible():
            self.window.show_all()
        self.window.set_keep_above(True)
        self._pass_through()
        self.window.queue_draw()
        return True


if __name__ == "__main__":
    main()
