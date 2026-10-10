"""Panel para elegir estilo, tamaño, grosor, color y transparencia."""

from __future__ import annotations

import queue
import sys
import tkinter as tk
from tkinter import colorchooser

from .render import checker, composite, render
from .settings import COLORS, STYLE_LABEL, STYLES, MiraSettings

BG = "#091019"
PANEL = "#111c28"
INK = "#e9f4f5"
MUTED = "#93a8b5"
LINE = "#2a3b48"
ACCENT = "#45e6bd"
BUTTON = "#1c3040"
DARK = (18, 28, 36)
LIGHT = (54, 70, 82)


class MiraApp:
    def __init__(self, settings: MiraSettings, overlay, events: queue.Queue | None = None) -> None:
        self.settings = settings.clamped()
        self.overlay = overlay
        self.events = events or queue.Queue()
        self.family = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
        self._loading = True
        self._photos: list[tk.PhotoImage] = []
        self._style_frames: dict[str, tk.Frame] = {}
        self._style_buttons: dict[str, tk.Button] = {}
        self.root = tk.Tk()
        self.root.title("YXI96 Mira")
        self.root.configure(bg=BG)
        self.root.minsize(680, 420)
        self._build()
        self._thumb_key = None
        self._loading = False
        self.set_monitors(_monitor_count())
        self._apply()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<F8>", lambda _event: self._toggle())
        self.root.after(200, self._place)
        self.root.after(400, self._tick)
        self.root.mainloop()

    def close(self) -> None:
        try:
            self.overlay.close()
        finally:
            self.root.destroy()

    def _build(self) -> None:
        root = self.root
        title = tk.Frame(root, bg=BG)
        title.pack(fill="x", padx=22, pady=(18, 8))
        tk.Label(title, text="YXI96 Mira", bg=BG, fg=INK, font=(self.family, 20, "bold")).pack(anchor="w")
        tk.Label(
            title,
            text="Punto de mira blanco encima de la pantalla. El clic lo atraviesa.",
            bg=BG,
            fg=MUTED,
            font=(self.family, 10),
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=8)
        left = tk.Frame(body, bg=BG)
        right = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        right.pack(side="right", fill="y")

        tk.Label(left, text="ESTILO", bg=BG, fg=MUTED, font=(self.family, 9, "bold")).pack(anchor="w")
        grid = tk.Frame(left, bg=BG)
        grid.pack(anchor="w", pady=(8, 4))
        for index, (key, _label) in enumerate(STYLES):
            frame = tk.Frame(grid, bg=LINE, padx=2, pady=2)
            frame.grid(row=index // 4, column=index % 4, padx=4, pady=4)
            button = tk.Button(
                frame,
                command=lambda name=key: self._set_style(name),
                bg=PANEL,
                activebackground=PANEL,
                relief="flat",
                bd=0,
                cursor="hand2",
            )
            button.pack()
            self._style_frames[key] = frame
            self._style_buttons[key] = button
        self.style_name = tk.Label(left, text="", bg=BG, fg=INK, font=(self.family, 11, "bold"))
        self.style_name.pack(anchor="w", pady=(2, 10))

        tk.Label(left, text="COLOR", bg=BG, fg=MUTED, font=(self.family, 9, "bold")).pack(anchor="w")
        colors = tk.Frame(left, bg=BG)
        colors.pack(anchor="w", pady=(8, 8))
        self._color_frames: dict[str, tk.Frame] = {}
        for hex_color, _name in COLORS:
            frame = tk.Frame(colors, bg=LINE, padx=2, pady=2)
            frame.pack(side="left", padx=(0, 6))
            chip = tk.Button(
                frame,
                bg=hex_color,
                activebackground=hex_color,
                width=3,
                height=1,
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda value=hex_color: self._set_color(value),
            )
            chip.configure(text=" ")
            chip.pack()
            self._color_frames[hex_color] = frame
        tk.Button(
            colors,
            text="Otro",
            command=self._pick_color,
            bg=BUTTON,
            fg=INK,
            activebackground="#264356",
            activeforeground=INK,
            relief="flat",
            bd=0,
            padx=10,
            cursor="hand2",
            font=(self.family, 9, "bold"),
        ).pack(side="left")

        self.outline_var = tk.BooleanVar(value=self.settings.outline)
        tk.Checkbutton(
            left,
            text="Contorno oscuro",
            variable=self.outline_var,
            command=self._from_controls,
            bg=BG,
            fg=INK,
            selectcolor=PANEL,
            activebackground=BG,
            activeforeground=INK,
            font=(self.family, 10),
        ).pack(anchor="w", pady=(4, 10))

        self.monitor_row = tk.Frame(left, bg=BG)
        self.monitor_var = tk.IntVar(value=self.settings.monitor + 1)
        self._monitor_count = 1

        actions = tk.Frame(left, bg=BG)
        actions.pack(anchor="w", pady=(8, 8))
        self.toggle_button = tk.Button(
            actions,
            command=self._toggle,
            bg=ACCENT,
            fg="#062526",
            activebackground="#80f2d7",
            activeforeground="#062526",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            font=(self.family, 10, "bold"),
        )
        self.toggle_button.pack(side="left", padx=(0, 8))
        tk.Button(
            actions,
            text="Centrar",
            command=self._center,
            bg=BUTTON,
            fg=INK,
            activebackground="#264356",
            activeforeground=INK,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            font=(self.family, 10, "bold"),
        ).pack(side="left")

        hint = (
            "F8 oculta o muestra la mira cuando este panel está enfocado. "
            "En Windows, Ctrl+Alt+M hace lo mismo con el juego delante.\n"
            "En pantalla completa exclusiva el juego puede tapar la mira. "
            "Ventana, o ventana sin bordes, la deja delante."
        )
        tk.Label(left, text=hint, bg=BG, fg=MUTED, justify="left", wraplength=360, font=(self.family, 9)).pack(
            anchor="w", pady=(8, 0)
        )
        self.status = tk.Label(left, text="", bg=BG, fg=ACCENT, justify="left", wraplength=360, font=(self.family, 9))
        self.status.pack(anchor="w", pady=(8, 0))

        preview_card = tk.Frame(right, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        preview_card.pack(fill="x")
        tk.Label(preview_card, text="VISTA PREVIA", bg=PANEL, fg=MUTED, font=(self.family, 9, "bold")).pack(
            anchor="w", padx=12, pady=(10, 0)
        )
        self.preview_caption = tk.Label(preview_card, text="", bg=PANEL, fg=INK, font=(self.family, 10))
        self.preview_caption.pack(anchor="w", padx=12)
        self.preview = tk.Label(preview_card, bg=PANEL)
        self.preview.pack(padx=12, pady=12)

        sliders = tk.Frame(right, bg=BG)
        sliders.pack(fill="x", pady=(14, 0))
        self.size_var = tk.IntVar(value=self.settings.size)
        self.thickness_var = tk.IntVar(value=self.settings.thickness)
        self.opacity_var = tk.IntVar(value=round(self.settings.opacity * 100))
        self.offset_x_var = tk.IntVar(value=self.settings.offset_x)
        self.offset_y_var = tk.IntVar(value=self.settings.offset_y)
        self.size_label = self._slider(sliders, "Tamaño", self.size_var, 2, 64, "px")
        self.thickness_label = self._slider(sliders, "Grosor", self.thickness_var, 1, 14, "px")
        self.opacity_label = self._slider(sliders, "Transparencia", self.opacity_var, 10, 100, "%")
        self.x_label = self._slider(sliders, "Centro horizontal", self.offset_x_var, -200, 200, "px")
        self.y_label = self._slider(sliders, "Centro vertical", self.offset_y_var, -200, 200, "px")

    def _slider(self, parent, caption: str, variable: tk.IntVar, low: int, high: int, unit: str) -> tk.Label:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        head = tk.Frame(row, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=caption, bg=BG, fg=MUTED, font=(self.family, 9, "bold")).pack(side="left")
        value = tk.Label(head, text="", bg=BG, fg=INK, font=(self.family, 9, "bold"))
        value.pack(side="right")
        value.unit = unit  # type: ignore[attr-defined]
        scale = tk.Scale(
            row,
            from_=low,
            to=high,
            orient="horizontal",
            variable=variable,
            showvalue=False,
            command=lambda _value: self._from_controls(),
            bg=BG,
            fg=INK,
            troughcolor="#1c3040",
            activebackground=ACCENT,
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            length=250,
        )
        scale.pack(fill="x")
        self._bind_jump(scale, variable, low, high)
        return value

    def _place(self) -> None:
        self.root.update_idletasks()
        width = max(680, self.root.winfo_reqwidth())
        height = self.root.winfo_reqheight()
        x = max(12, self.root.winfo_screenwidth() - width - 28)
        self.root.geometry(f"{width}x{height}+{x}+28")

    def _bind_jump(self, scale: tk.Scale, variable: tk.IntVar, low: int, high: int) -> None:
        def place(event, scale=scale, variable=variable, low=low, high=high):
            width = max(1, scale.winfo_width())
            fraction = min(1.0, max(0.0, event.x / float(width)))
            variable.set(int(round(low + fraction * (high - low))))
            self._from_controls()
            return "break"

        scale.bind("<Button-1>", place)
        scale.bind("<B1-Motion>", place)

    def _set_style(self, name: str) -> None:
        self.settings.style = name
        self._apply()

    def _set_color(self, value: str) -> None:
        self.settings.color = value
        self._apply()

    def _pick_color(self) -> None:
        _rgb, hex_color = colorchooser.askcolor(color=self.settings.color, parent=self.root, title="Color de la mira")
        if hex_color:
            self._set_color(hex_color)

    def _toggle(self) -> None:
        self.settings.visible = not self.settings.visible
        self._apply()

    def _center(self) -> None:
        self._loading = True
        self.offset_x_var.set(0)
        self.offset_y_var.set(0)
        self._loading = False
        self.settings.offset_x = 0
        self.settings.offset_y = 0
        self._apply()

    def _from_controls(self) -> None:
        if self._loading:
            return
        self.settings.size = self.size_var.get()
        self.settings.thickness = self.thickness_var.get()
        self.settings.opacity = self.opacity_var.get() / 100
        self.settings.offset_x = self.offset_x_var.get()
        self.settings.offset_y = self.offset_y_var.get()
        self.settings.outline = self.outline_var.get()
        self.settings.monitor = max(0, self.monitor_var.get() - 1)
        self._apply()

    def _apply(self) -> None:
        self.settings = self.settings.clamped()
        self._loading = True
        self.size_var.set(self.settings.size)
        self.thickness_var.set(self.settings.thickness)
        self.opacity_var.set(round(self.settings.opacity * 100))
        self.offset_x_var.set(self.settings.offset_x)
        self.offset_y_var.set(self.settings.offset_y)
        self.outline_var.set(self.settings.outline)
        self.monitor_var.set(self.settings.monitor + 1)
        self._loading = False
        self._paint_labels()
        thumb_key = (self.settings.thickness, self.settings.color, self.settings.outline)
        if thumb_key != self._thumb_key:
            self._thumb_key = thumb_key
            self._paint_styles()
        else:
            for key, frame in self._style_frames.items():
                frame.configure(bg=ACCENT if key == self.settings.style else LINE)
        self._paint_colors()
        self._paint_preview()
        self.toggle_button.configure(text="Ocultar mira" if self.settings.visible else "Mostrar mira")
        try:
            self.overlay.update(self.settings)
            self.status.configure(text="")
        except Exception as error:
            self.status.configure(text=str(error), fg="#ffb4be")

    def _paint_labels(self) -> None:
        pairs = (
            (self.size_label, self.settings.size),
            (self.thickness_label, self.settings.thickness),
            (self.opacity_label, round(self.settings.opacity * 100)),
            (self.x_label, self.settings.offset_x),
            (self.y_label, self.settings.offset_y),
        )
        for label, value in pairs:
            label.configure(text=f"{value} {label.unit}")
        self.style_name.configure(text=STYLE_LABEL.get(self.settings.style, "Punto"))
        self.preview_caption.configure(
            text=f"{STYLE_LABEL.get(self.settings.style, 'Punto')} · tamaño real"
        )

    def _paint_styles(self) -> None:
        photos: list[tk.PhotoImage] = []
        for key, _label in STYLES:
            sample = MiraSettings(
                style=key,
                size=14,
                thickness=self.settings.thickness,
                opacity=1,
                color=self.settings.color,
                outline=self.settings.outline,
            )
            photo = self._sprite(sample, 58)
            photos.append(photo)
            self._style_buttons[key].configure(image=photo)
            selected = key == self.settings.style
            self._style_frames[key].configure(bg=ACCENT if selected else LINE)
        self._photos = photos

    def _paint_colors(self) -> None:
        for hex_color, frame in self._color_frames.items():
            frame.configure(bg=ACCENT if hex_color == self.settings.color else LINE)

    def _paint_preview(self) -> None:
        photo = self._sprite(self.settings, 168, canvas=(200, 150))
        self._preview_photo = photo
        self.preview.configure(image=photo)

    def _sprite(self, settings: MiraSettings, max_side: int, canvas: tuple[int, int] | None = None) -> tk.PhotoImage:
        width, height, rgba = render(settings)
        rows = composite(width, height, rgba, checker(LIGHT, DARK))
        if canvas is None:
            fitted = _fit(rows, max_side)
            side = max(max_side, len(fitted), len(fitted[0]))
            plate = _paste(fitted, side, side, checker(LIGHT, DARK))
        else:
            fitted = _fit(rows, min(canvas) - 8)
            plate = _paste(fitted, canvas[0], canvas[1], checker(LIGHT, DARK, 10))
        return _photo(self.root, plate)

    def set_monitors(self, count: int) -> None:
        self._monitor_count = max(1, count)
        if self._monitor_count < 2:
            return
        self.monitor_row.pack(anchor="w", pady=(0, 8), before=self.toggle_button.master)
        tk.Label(self.monitor_row, text="PANTALLA", bg=BG, fg=MUTED, font=(self.family, 9, "bold")).pack(side="left")
        spin = tk.Spinbox(
            self.monitor_row,
            from_=1,
            to=self._monitor_count,
            width=4,
            textvariable=self.monitor_var,
            command=self._from_controls,
            bg=PANEL,
            fg=INK,
            buttonbackground=BUTTON,
            relief="flat",
            justify="center",
        )
        spin.pack(side="left", padx=(8, 0))
        self.monitor_var.trace_add("write", lambda *_args: self._from_controls())

    def _tick(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "toggle":
                    self._toggle()
                elif kind == "hotkey":
                    if payload:
                        self.status.configure(text="Atajo global: Ctrl+Alt+M", fg=ACCENT)
                    else:
                        self.status.configure(text="El atajo Ctrl+Alt+M no se pudo registrar.", fg="#ffd092")
        except queue.Empty:
            pass
        try:
            self.overlay.raise_top()
        except Exception:
            pass
        self.root.after(400, self._tick)


def _monitor_count() -> int:
    if sys.platform == "win32":
        try:
            from .overlay_windows import list_monitors

            return max(1, len(list_monitors()))
        except OSError:
            return 1
    try:
        import subprocess

        text = subprocess.check_output(["xrandr", "--listmonitors"], text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return 1
    for line in text.splitlines():
        if line.startswith("Monitors:"):
            try:
                return max(1, int(line.split()[-1]))
            except ValueError:
                return 1
    return 1


def _fit(rows: list[list[tuple[int, int, int]]], max_side: int) -> list[list[tuple[int, int, int]]]:
    height = len(rows)
    width = len(rows[0])
    largest = max(width, height)
    if largest <= max_side:
        return rows
    scale = max_side / largest
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    fitted: list[list[tuple[int, int, int]]] = []
    for y in range(new_h):
        source_y = min(height - 1, int(y / scale))
        row = []
        for x in range(new_w):
            source_x = min(width - 1, int(x / scale))
            row.append(rows[source_y][source_x])
        fitted.append(row)
    return fitted


def _paste(sprite, width: int, height: int, background) -> list[list[tuple[int, int, int]]]:
    plate = [[background(x, y) for x in range(width)] for y in range(height)]
    sprite_h = len(sprite)
    sprite_w = len(sprite[0])
    left = (width - sprite_w) // 2
    top = (height - sprite_h) // 2
    for y, row in enumerate(sprite):
        for x, color in enumerate(row):
            plate[top + y][left + x] = color
    return plate


def _photo(master: tk.Misc, rows: list[list[tuple[int, int, int]]]) -> tk.PhotoImage:
    height = len(rows)
    width = len(rows[0])
    image = tk.PhotoImage(master=master, width=width, height=height)
    image.put(" ".join("{" + " ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in row) + "}" for row in rows))
    return image
