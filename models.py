"""键鼠宏事件数据模型。

核心设计：键盘和鼠标统一用 InputEvent 表示，按时间戳排序。
长按 vs 点按的区别天然由 press/release 两个事件的时间差体现——
回放时精确复现这个时间差即可还原长按行为。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    KEY = "key"
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_SCROLL = "mouse_scroll"


class Action(str, Enum):
    PRESS = "press"
    RELEASE = "release"
    MOVE = "move"
    SCROLL = "scroll"


@dataclass
class InputEvent:
    """单个输入事件。

    Attributes:
        timestamp: 相对录制开始的秒数（浮点，毫秒精度）
        event_type: 事件类型（键盘/鼠标移动/鼠标点击/滚轮）
        action: 动作（按下/释放/移动/滚动）
        key: 键盘按键名或鼠标按钮名（如 'a', 'space', 'left', 'right'）
        x, y: 鼠标坐标（仅鼠标事件）
        dx, dy: 滚轮增量（仅滚轮事件）
    """

    timestamp: float
    event_type: EventType
    action: Action
    key: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    dx: Optional[int] = None
    dy: Optional[int] = None

    def hold_duration_to(self, other: "InputEvent") -> Optional[float]:
        """若 other 是本事件对应的 release，返回按住时长（秒）。"""
        if (
            self.action == Action.PRESS
            and other.action == Action.RELEASE
            and self.event_type == other.event_type
            and self.key == other.key
        ):
            return other.timestamp - self.timestamp
        return None

    def describe(self) -> str:
        """人类可读描述，用于 GUI 事件列表。"""
        t = f"[{self.timestamp:7.3f}s]"
        if self.event_type == EventType.KEY:
            verb = "按下" if self.action == Action.PRESS else "释放"
            return f"{t} 键盘{verb}: {self.key}"
        if self.event_type == EventType.MOUSE_CLICK:
            verb = "按下" if self.action == Action.PRESS else "释放"
            btn = {"left": "左键", "right": "右键", "middle": "中键"}.get(
                self.key or "", self.key
            )
            return f"{t} 鼠标{verb} {btn}: ({self.x}, {self.y})"
        if self.event_type == EventType.MOUSE_MOVE:
            return f"{t} 鼠标移动: ({self.x}, {self.y})"
        if self.event_type == EventType.MOUSE_SCROLL:
            return f"{t} 滚轮: dx={self.dx}, dy={self.dy}"
        return f"{t} 未知事件"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["action"] = self.action.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "InputEvent":
        return cls(
            timestamp=float(d["timestamp"]),
            event_type=EventType(d["event_type"]),
            action=Action(d["action"]),
            key=d.get("key"),
            x=d.get("x"),
            y=d.get("y"),
            dx=d.get("dx"),
            dy=d.get("dy"),
        )


@dataclass
class MacroScript:
    """一个完整的宏脚本 = 有序事件列表 + 元信息。"""

    name: str = "未命名宏"
    events: list[InputEvent] = field(default_factory=list)
    record_duration: float = 0.0

    def to_json(self) -> str:
        payload = {
            "name": self.name,
            "record_duration": self.record_duration,
            "events": [e.to_dict() for e in self.events],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "MacroScript":
        payload = json.loads(text)
        return cls(
            name=payload.get("name", "未命名宏"),
            record_duration=float(payload.get("record_duration", 0.0)),
            events=[InputEvent.from_dict(d) for d in payload.get("events", [])],
        )

    def hold_info(self) -> list[tuple[int, float]]:
        """返回 [(事件索引, 按住时长)]，用于 GUI 标注长按。"""
        result = []
        press_map: dict[tuple, int] = {}
        for i, ev in enumerate(self.events):
            tag = (ev.event_type, ev.key)
            if ev.action == Action.PRESS:
                press_map[tag] = i
            elif ev.action == Action.RELEASE and tag in press_map:
                pi = press_map.pop(tag)
                dur = ev.timestamp - self.events[pi].timestamp
                result.append((pi, dur))
        return result
