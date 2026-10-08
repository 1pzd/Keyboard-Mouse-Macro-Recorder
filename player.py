"""回放器：按录制时的时间差精确复现键鼠事件。

长按还原原理：press 事件在 t1 执行，release 事件在 t2 执行，
中间的时间差就是按住时长——无需额外逻辑，天然还原。

支持：无限循环 / 指定次数、轮间间隔、速度倍率、随时紧急停止。
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from pynput import keyboard, mouse

from models import Action, EventType, InputEvent, MacroScript

# pynput 全局控制器（单例即可，全进程共享）
_kb_controller = keyboard.Controller()
_mouse_controller = mouse.Controller()


def _resolve_key(name: str):
    """把字符串键名转回 pynput 按键对象。"""
    # 先试特殊键（space, shift, f9 ...）
    try:
        return keyboard.Key[name]
    except KeyError:
        pass
    # 再试普通字符键
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    # vk_ 开头的虚拟键码
    if name.startswith("vk_"):
        try:
            return keyboard.KeyCode.from_vk(int(name[3:]))
        except ValueError:
            pass
    # 兜底：直接当字符
    return keyboard.KeyCode.from_char(name)


def _resolve_button(name: str):
    try:
        return mouse.Button[name]
    except KeyError:
        return mouse.Button.left


class Player:
    """宏回放器。

    用法：
        p = Player()
        p.play(script, loop_count=0, loop_interval=1.0, speed=1.0)
        ...
        p.stop()   # 随时可从另一线程/热键调用
    """

    def __init__(
        self,
        on_progress: Optional[Callable[[int, int, int], None]] = None,
        # on_progress(loop_index, event_index, total_events)
    ):
        self.on_progress = on_progress
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── 状态 ─────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        """紧急停止回放（线程安全）。"""
        self._stop_event.set()

    # ── 主入口 ───────────────────────────────────────────

    def play(
        self,
        script: MacroScript,
        loop_count: int = 0,
        loop_interval: float = 1.0,
        speed: float = 1.0,
        skip_mouse_move: bool = False,
    ) -> None:
        """在后台线程启动回放。

        Args:
            script: 要回放的宏脚本
            loop_count: 循环次数，0 = 无限
            loop_interval: 每轮之间间隔（秒）
            speed: 速度倍率（2.0 = 两倍速）
            skip_mouse_move: 跳过鼠标移动事件（点击更精准时有用）
        """
        if self.is_playing:
            raise RuntimeError("已在回放中，请先停止")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(script, loop_count, loop_interval, speed, skip_mouse_move),
            daemon=True,
        )
        self._thread.start()

    def play_sync(
        self,
        script: MacroScript,
        loop_count: int = 1,
        loop_interval: float = 0.0,
        speed: float = 1.0,
        skip_mouse_move: bool = False,
    ) -> None:
        """同步回放（阻塞当前线程）。测试/脚本化调用用。"""
        self._stop_event.clear()
        self._run(script, loop_count, loop_interval, speed, skip_mouse_move)

    # ── 内部执行 ─────────────────────────────────────────

    def _run(
        self,
        script: MacroScript,
        loop_count: int,
        loop_interval: float,
        speed: float,
        skip_mouse_move: bool,
    ) -> None:
        events = script.events
        if not events:
            return
        if speed <= 0:
            speed = 1.0

        iteration = 0
        while not self._stop_event.is_set():
            # loop_count=0 → 无限
            if loop_count > 0 and iteration >= loop_count:
                break

            base = time.perf_counter()
            for i, ev in enumerate(events):
                if self._stop_event.is_set():
                    return

                # 目标时间 = 起点 + 事件时间戳 / 速度倍率
                target = base + ev.timestamp / speed
                wait = target - time.perf_counter()
                if wait > 0:
                    # 可中断的 sleep
                    if self._stop_event.wait(wait):
                        return

                self._execute(ev, skip_mouse_move)

                if self.on_progress:
                    try:
                        self.on_progress(iteration, i + 1, len(events))
                    except Exception:
                        pass

            iteration += 1

            # 轮间间隔
            if loop_interval > 0 and not self._stop_event.is_set():
                if self._stop_event.wait(loop_interval):
                    return

    def _execute(self, ev: InputEvent, skip_mouse_move: bool) -> None:
        if ev.event_type == EventType.KEY:
            key = _resolve_key(ev.key or "")
            if ev.action == Action.PRESS:
                _kb_controller.press(key)
            else:
                _kb_controller.release(key)

        elif ev.event_type == EventType.MOUSE_CLICK:
            button = _resolve_button(ev.key or "left")
            # 先移到目标位置再点击，保证坐标准确
            if ev.x is not None and ev.y is not None:
                _mouse_controller.position = (ev.x, ev.y)
            if ev.action == Action.PRESS:
                _mouse_controller.press(button)
            else:
                _mouse_controller.release(button)

        elif ev.event_type == EventType.MOUSE_MOVE:
            if skip_mouse_move:
                return
            if ev.x is not None and ev.y is not None:
                _mouse_controller.position = (ev.x, ev.y)

        elif ev.event_type == EventType.MOUSE_SCROLL:
            if ev.dx or ev.dy:
                _mouse_controller.scroll(ev.dx or 0, ev.dy or 0)
