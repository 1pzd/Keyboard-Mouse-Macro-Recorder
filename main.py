"""键鼠宏录制器 - 程序入口。

全局热键（在任何窗口下都有效）：
  F9  = 开始/停止录制
  F10 = 开始/停止回放
  F11 = 紧急停止（立即中止录制和回放）

用法：
  python main.py
"""

from __future__ import annotations

import sys
import tkinter as tk

from pynput import keyboard

from gui import MacroGUI
from slots import SlotManager
from theme import BG_DEEP, enable_acrylic


def main() -> int:
    # Windows DPI 适配必须在创建窗口之前，否则界面会模糊
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except OSError:
        pass

    root = tk.Tk()

    # 毛玻璃背景；失败时 theme 内部自动降级为纯色深色主题
    enable_acrylic(root, BG_DEEP)

    # 存档槽管理器：frozen 时落在 exe 同目录，源码运行时落在项目目录
    slot_manager = SlotManager()
    app = MacroGUI(root, slot_manager=slot_manager)

    # ── 全局热键 ──────────────────────────────────────────
    # pynput GlobalHotKeys 在独立线程运行，通过 root.after 调度到 GUI 线程
    hotkey_map = {
        "<f9>": lambda: root.after(0, app.toggle_record),
        "<f10>": lambda: root.after(0, app.toggle_play),
        "<f11>": lambda: root.after(0, app.emergency_stop),
    }
    hotkeys = keyboard.GlobalHotKeys(hotkey_map)
    hotkeys.start()

    def on_close():
        hotkeys.stop()
        app.emergency_stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
