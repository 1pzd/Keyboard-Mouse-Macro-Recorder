"""录制器：监听键鼠输入并按时间顺序记录为 InputEvent 列表。

长按 vs 点按的关键：不丢弃 release 事件。
press 和 release 各记一条，时间差即按住时长——回放时自然还原。
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from pynput import keyboard, mouse

from models import Action, EventType, InputEvent, MacroScript


def _key_name(key) -> Optional[str]:
    """把 pynput 按键对象转成可序列化的字符串名。"""
    try:
        if isinstance(key, keyboard.KeyCode):
            # 普通字符键，如 a, 1, ;
            return key.char if key.char else f"vk_{key.vk}"
        if isinstance(key, keyboard.Key):
            # 特殊键，如 space, shift, f9
            return key.name
    except AttributeError:
        pass
    return str(key)


def _button_name(button) -> Optional[str]:
    try:
        return button.name  # 'left', 'right', 'middle'
    except AttributeError:
        return str(button)


class Recorder:
    """键鼠宏录制器。

    用法：
        rec = Recorder()
        rec.start()
        ... 用户操作 ...
        script = rec.stop()
    """

    def __init__(
        self,
        record_mouse_move: bool = True,
        mouse_move_interval: float = 0.033,  # ~30 samples/sec
        on_event: Optional[Callable[[InputEvent], None]] = None,
    ):
        self.record_mouse_move = record_mouse_move
        self.mouse_move_interval = mouse_move_interval
        self.on_event = on_event  # 每录到一个事件的回调（GUI 实时刷新用）

        self._events: list[InputEvent] = []
        self._lock = threading.Lock()
        self._start_time: float = 0.0
        self._last_move_time: float = 0.0
        self._mouse_listener: Optional[mouse.Listener] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._running = False

    # ── 对外接口 ──────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        return self._running

    @property
    def elapsed(self) -> float:
        return time.time() - self._start_time if self._running else 0.0

    def start(self) -> None:
        if self._running:
            return
        with self._lock:
            self._events.clear()
        self._start_time = time.time()
        self._last_move_time = 0.0
        self._running = True

        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
            on_move=self._on_move if self.record_mouse_move else None,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self) -> MacroScript:
        """停止录制并返回宏脚本。"""
        self._running = False
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

        duration = time.time() - self._start_time
        with self._lock:
            events = list(self._events)
        return MacroScript(
            name=f"宏_{time.strftime('%Y%m%d_%H%M%S')}",
            events=events,
            record_duration=round(duration, 3),
        )

    # ── pynput 回调 ───────────────────────────────────────

    def _now(self) -> float:
        return round(time.time() - self._start_time, 4)

    def _append(self, ev: InputEvent) -> None:
        with self._lock:
            self._events.append(ev)
        if self.on_event:
            try:
                self.on_event(ev)
            except Exception:
                pass  # GUI 回调异常不影响录制

    def _on_key_press(self, key) -> None:
        if not self._running:
            return
        name = _key_name(key)
        if name is None:
            return
        self._append(
            InputEvent(
                timestamp=self._now(),
                event_type=EventType.KEY,
                action=Action.PRESS,
                key=name,
            )
        )

    def _on_key_release(self, key) -> None:
        if not self._running:
            return
        name = _key_name(key)
        if name is None:
            return
        self._append(
            InputEvent(
                timestamp=self._now(),
                event_type=EventType.KEY,
                action=Action.RELEASE,
                key=name,
            )
        )

    def _on_click(self, x, y, button, pressed) -> None:
        if not self._running:
            return
        self._append(
            InputEvent(
                timestamp=self._now(),
                event_type=EventType.MOUSE_CLICK,
                action=Action.PRESS if pressed else Action.RELEASE,
                key=_button_name(button),
                x=int(x),
                y=int(y),
            )
        )

    def _on_scroll(self, x, y, dx, dy) -> None:
        if not self._running:
            return
        self._append(
            InputEvent(
                timestamp=self._now(),
                event_type=EventType.MOUSE_SCROLL,
                action=Action.SCROLL,
                x=int(x),
                y=int(y),
                dx=int(dx),
                dy=int(dy),
            )
        )

    def _on_move(self, x, y) -> None:
        if not self._running:
            return
        now = time.time()
        # 节流：限制鼠标移动采样率，避免事件爆炸
        if now - self._last_move_time < self.mouse_move_interval:
            return
        self._last_move_time = now
        self._append(
            InputEvent(
                timestamp=self._now(),
                event_type=EventType.MOUSE_MOVE,
                action=Action.MOVE,
                x=int(x),
                y=int(y),
            )
        )
