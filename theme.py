"""Windows acrylic design tokens and rounded Tkinter primitives."""

from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Optional


# ── Design tokens ─────────────────────────────────────────
BG_DEEP = "#0b0e14"
BG_SURFACE = "#121722"
BG_SURFACE_ALT = "#1a2130"
BG_ELEVATED = "#212a3a"
ACCENT = "#5b8cff"
ACCENT_HOVER = "#7aa3ff"
ACCENT_SOFT = "#2a3a66"
SUCCESS = "#3ddc84"
DANGER = "#ff5c5c"
DANGER_HOVER = "#ff7777"
WARNING = "#ffb020"
TEXT_PRIMARY = "#e8eef7"
TEXT_SECONDARY = "#8b97a8"
TEXT_MUTED = "#5c6779"
BORDER = "#2a3244"
BORDER_HOVER = "#3d4a63"

# Treeview tag tokens: intentionally subdued so the event table stays readable.
TREE_HOLD_BG = "#4a3a1d"
TREE_HOLD_FG = "#ffe0a0"
TREE_PRESS_BG = "#193a31"
TREE_PRESS_FG = "#c9f5dc"

RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 20

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_XXL = 32

FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_H2 = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)
FONT_BADGE = ("Segoe UI", 8, "bold")

HOVER_MS = 120
WINDOW_WIDTH = 1080
WINDOW_HEIGHT = 700


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"颜色必须是六位十六进制值: {value!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_hex(rgb: tuple[int, int, int]) -> str:
    channels = tuple(max(0, min(255, int(channel))) for channel in rgb)
    return "#%02x%02x%02x" % channels


def _lerp_color(start: str, end: str, progress: float) -> str:
    first = _hex_rgb(start)
    second = _hex_rgb(end)
    return _rgb_hex(
        tuple(round(a + (b - a) * progress) for a, b in zip(first, second))
    )


def enable_acrylic(root: tk.Misc, tint: str = BG_DEEP) -> bool:
    """Enable Windows acrylic, returning False when the platform cannot do so."""
    root.configure(bg=BG_DEEP)
    try:
        user32 = ctypes.windll.user32
        try:
            hwnd = user32.GetParent(root.winfo_id())
        except (AttributeError, OSError, RuntimeError):
            hwnd = root.winfo_id()
        if not hwnd:
            hwnd = root.winfo_id()

        red, green, blue = _hex_rgb(tint)
        accent_policy = (ctypes.c_int * 4)()
        accent_policy[0] = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent_policy[1] = 0
        # Windows expects the gradient color as 0xAABBGGRR.
        accent_policy[2] = (0xCC << 24) | (blue << 16) | (green << 8) | red
        accent_policy[3] = 0

        class WindowCompositionAttributeData(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        data = WindowCompositionAttributeData(
            19,
            ctypes.cast(accent_policy, ctypes.c_void_p),
            ctypes.sizeof(accent_policy),
        )
        setter = user32.SetWindowCompositionAttribute
        setter.argtypes = [ctypes.c_void_p, ctypes.POINTER(WindowCompositionAttributeData)]
        setter.restype = ctypes.c_int
        if not setter(hwnd, ctypes.byref(data)):
            return False
        root.attributes("-alpha", 0.98)
        return True
    except (AttributeError, OSError, RuntimeError, tk.TclError, ValueError):
        # The caller already has BG_DEEP, so this is a safe flat-theme fallback.
        return False


def round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    r: float,
    **kwargs: object,
) -> int:
    """Draw a smooth rounded polygon and return its canvas item id."""
    radius = max(0.0, min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2))
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=12, **kwargs)


class HoverButton(tk.Canvas):
    """Rounded canvas button with six-frame hover and press feedback."""

    _STYLES = {
        "primary": (ACCENT, ACCENT_HOVER, BG_DEEP),
        "ghost": (BG_SURFACE_ALT, BG_ELEVATED, TEXT_PRIMARY),
        "danger": (DANGER, DANGER_HOVER, TEXT_PRIMARY),
        "success": (SUCCESS, SUCCESS, BG_DEEP),
    }

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        style: str = "primary",
        icon: Optional[str] = None,
        width: Optional[int] = None,
        height: int = 36,
        **kwargs: object,
    ) -> None:
        if style not in self._STYLES:
            raise ValueError(f"未知按钮样式: {style}")
        self.command = command
        self.button_style = style
        self.icon = icon or ""
        self._text = text
        self._enabled = True
        self._hovered = False
        self._pressed = False
        self._animation_id: Optional[str] = None
        self._animation_frame = 0
        self._font = tkfont.Font(font=FONT_BODY)
        label = f"{self.icon} {text}".strip()
        self._button_width = width or max(64, self._font.measure(label) + SPACE_XL * 2)
        self._button_height = height
        background = kwargs.pop("bg", parent.cget("bg"))
        super().__init__(
            parent,
            width=self._button_width,
            height=self._button_height,
            bg=background,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=True,
            **kwargs,
        )
        self._draw(0.0)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Return>", self._on_key)
        self.bind("<space>", self._on_key)

    def _draw(self, progress: float) -> None:
        start, end, foreground = self._STYLES[self.button_style]
        if not self._enabled:
            start = end = BG_SURFACE_ALT
            foreground = TEXT_MUTED
        color = _lerp_color(start, end, progress)
        self.delete("all")
        offset = 1 if self._pressed and self._enabled else 0
        round_rect(
            self,
            1,
            1 + offset,
            self._button_width - 1,
            self._button_height - 1 + offset,
            RADIUS_MD,
            fill=color,
            outline=BORDER_HOVER if self._hovered and self._enabled else color,
            width=1,
        )
        label = f"{self.icon} {self._text}".strip()
        self.create_text(
            self._button_width / 2,
            self._button_height / 2 + offset,
            text=label,
            fill=foreground,
            font=FONT_BODY,
        )

    def _animate(self, target: int) -> None:
        if self._animation_id is not None:
            self.after_cancel(self._animation_id)
            self._animation_id = None
        start = self._animation_frame
        if target == start:
            self._draw(start / 6)
            return
        step = 1 if target > start else -1

        def tick() -> None:
            nonlocal start
            start += step
            self._animation_frame = start
            self._draw(start / 6)
            if start != target:
                self._animation_id = self.after(20, tick)
            else:
                self._animation_id = None

        tick()

    def _on_enter(self, _event: tk.Event[tk.Misc]) -> None:
        if self._enabled:
            self._hovered = True
            self._animate(6)

    def _on_leave(self, _event: tk.Event[tk.Misc]) -> None:
        self._hovered = False
        self._animate(0)

    def _on_press(self, _event: tk.Event[tk.Misc]) -> None:
        if self._enabled:
            self._pressed = True
            self._draw(self._animation_frame / 6)

    def _on_release(self, _event: tk.Event[tk.Misc]) -> None:
        if self._enabled and self._pressed:
            self._pressed = False
            self._draw(self._animation_frame / 6)
            self.command()

    def _on_key(self, _event: tk.Event[tk.Misc]) -> str:
        if self._enabled:
            self.command()
        return "break"

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the button and update its visual state."""
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw(self._animation_frame / 6)

    def set_text(self, text: str) -> None:
        """Change the label while preserving the button's minimum width."""
        self._text = text
        label = f"{self.icon} {text}".strip()
        self._button_width = max(self._button_width, self._font.measure(label) + SPACE_XL * 2)
        self.configure(width=self._button_width)
        self._draw(self._animation_frame / 6)


class Card(tk.Frame):
    """Rounded glass panel with an optional heading and child ``body`` frame."""

    def __init__(
        self,
        parent: tk.Misc,
        title: Optional[str] = None,
        padding: int = SPACE_LG,
        **kwargs: object,
    ) -> None:
        self.title = title
        self.padding = padding
        card_background = kwargs.pop("bg", parent.cget("bg"))
        super().__init__(parent, bg=card_background, highlightthickness=0, bd=0, **kwargs)
        self.canvas = tk.Canvas(self, bg=card_background, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.body = tk.Frame(self, bg=BG_SURFACE)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event: Optional[tk.Event[tk.Misc]] = None) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.canvas.delete("all")
        round_rect(
            self.canvas,
            1,
            1,
            width - 1,
            height - 1,
            RADIUS_LG,
            fill=BG_SURFACE,
            outline=BORDER,
            width=1,
        )
        top = self.padding + (SPACE_LG if self.title else 0)
        self.body.place(
            x=self.padding,
            y=top,
            relwidth=1,
            width=-self.padding * 2,
            relheight=1,
            height=-top - self.padding,
        )
        if self.title:
            self.canvas.create_text(
                self.padding,
                self.padding,
                text=self.title,
                anchor="nw",
                fill=TEXT_SECONDARY,
                font=FONT_H2,
            )


class GlassFrame(Card):
    """Semantic alias for callers that want to emphasize the glass treatment."""
