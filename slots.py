"""存档槽管理器：5 个快捷存档位，支持保存/载入/重命名/删除/枚举。

存储布局（与脚本/EXE 同级的 slots/ 目录，便于绿色移动）：
    slots/
        slot_1.json
        slot_2.json
        ...
        slot_5.json

每个文件就是一个 MacroScript JSON，另加一个 meta 字段记录槽位信息。
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from models import MacroScript

SLOT_COUNT = 5


def _default_base_dir() -> Path:
    """脚本模式用项目目录，打包模式用 EXE 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


@dataclass
class SlotInfo:
    """槽位概要，供 GUI 卡片展示。"""

    slot_id: int
    name: str
    event_count: int
    duration: float
    modified_at: float

    @property
    def modified_str(self) -> str:
        return time.strftime("%m-%d %H:%M", time.localtime(self.modified_at))


class SlotManager:
    """5 个固定槽位的读写管理。线程安全由调用方（GUI 主线程）保证。"""

    def __init__(self, base_dir: Optional[os.PathLike] = None, slot_count: int = SLOT_COUNT):
        self.slot_count = slot_count
        self.base_dir = Path(base_dir) if base_dir else _default_base_dir()
        self.slots_dir = self.base_dir / "slots"
        self.slots_dir.mkdir(parents=True, exist_ok=True)

    # ── 路径 ─────────────────────────────────────────────

    def _check_id(self, slot_id: int) -> int:
        if not 1 <= slot_id <= self.slot_count:
            raise ValueError(f"槽位编号必须在 1~{self.slot_count}，收到 {slot_id}")
        return slot_id

    def slot_path(self, slot_id: int) -> Path:
        return self.slots_dir / f"slot_{self._check_id(slot_id)}.json"

    # ── 核心读写 ─────────────────────────────────────────

    def save(self, slot_id: int, script: MacroScript) -> SlotInfo:
        """把当前脚本写入指定槽位，返回槽位概要。"""
        path = self.slot_path(slot_id)
        payload = {
            "slot_id": slot_id,
            "modified_at": time.time(),
            "script": json.loads(script.to_json()),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # 原子替换，避免写一半损坏
        return self.info(slot_id)  # type: ignore[return-value]

    def load(self, slot_id: int) -> MacroScript:
        """从槽位载入宏脚本。槽位为空则抛 FileNotFoundError。"""
        path = self.slot_path(slot_id)
        if not path.exists():
            raise FileNotFoundError(f"槽位 {slot_id} 是空的")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return MacroScript.from_json(json.dumps(payload.get("script", {}), ensure_ascii=False))

    def delete(self, slot_id: int) -> None:
        """清空槽位。空槽位静默成功。"""
        path = self.slot_path(slot_id)
        if path.exists():
            path.unlink()

    def rename(self, slot_id: int, name: str) -> SlotInfo:
        """改槽位内脚本名（即卡片标题）。"""
        script = self.load(slot_id)
        script.name = name.strip() or script.name
        return self.save(slot_id, script)

    def info(self, slot_id: int) -> Optional[SlotInfo]:
        """取槽位概要；空槽位返回 None。"""
        path = self.slot_path(slot_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            script_d = payload.get("script", {})
            events = script_d.get("events", [])
            return SlotInfo(
                slot_id=slot_id,
                name=script_d.get("name", f"存档 {slot_id}"),
                event_count=len(events),
                duration=float(script_d.get("record_duration", 0.0)),
                modified_at=float(payload.get("modified_at", path.stat().st_mtime)),
            )
        except (OSError, ValueError, KeyError):
            return None

    def list_slots(self) -> list[Optional[SlotInfo]]:
        """返回长度为 slot_count 的列表，空槽位为 None。"""
        return [self.info(i) for i in range(1, self.slot_count + 1)]
