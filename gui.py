"""Premium acrylic Tkinter interface for the keyboard/mouse macro recorder."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable, Optional

from models import Action, EventType, InputEvent, MacroScript
from player import Player
from recorder import Recorder
from slots import SlotInfo, SlotManager
from theme import (
    ACCENT,
    ACCENT_SOFT,
    BG_DEEP,
    BG_ELEVATED,
    BG_SURFACE,
    BG_SURFACE_ALT,
    BORDER,
    BORDER_HOVER,
    FONT_BADGE,
    FONT_BODY,
    FONT_H2,
    FONT_SMALL,
    FONT_TITLE,
    RADIUS_SM,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    SPACE_XL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TREE_HOLD_BG,
    TREE_HOLD_FG,
    TREE_PRESS_BG,
    TREE_PRESS_FG,
    Card,
    HoverButton,
    enable_acrylic,
    round_rect,
)


class MacroGUI:
    """宏录制器主窗口，保留 ``main.py`` 使用的公开控制 API。"""

    def __init__(self, root: tk.Tk, slot_manager: Optional[SlotManager] = None) -> None:
        self.root = root
        self.root.title("键鼠宏录制器")
        self.root.geometry("1080x700")
        self.root.minsize(900, 600)
        enable_acrylic(self.root, BG_DEEP)

        self.script: MacroScript = MacroScript(name="未命名宏")
        self.slot_manager = slot_manager or SlotManager()
        self.recorder = Recorder(record_mouse_move=True, on_event=self._on_recorded_event)
        self.player = Player(on_progress=self._on_play_progress)
        self._indicator: Optional[tk.Toplevel] = None
        self._indicator_label: Optional[tk.Label] = None
        self._recorded_count = 0
        self._slot_body: Optional[tk.Frame] = None
        self._play_watch_id: Optional[str] = None

        self._configure_treeview_style()
        self._build_toolbar()
        self._build_params()
        self._build_event_list()
        self._build_statusbar()
        self._refresh_events()
        self._refresh_slots()

    # ── UI 构建 ──────────────────────────────────────────

    def _configure_treeview_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            style.theme_use(style.theme_names()[0])
        style.configure(
            "Macro.Treeview",
            background=BG_SURFACE_ALT,
            fieldbackground=BG_SURFACE_ALT,
            foreground=TEXT_PRIMARY,
            rowheight=28,
            borderwidth=0,
            relief="flat",
            font=FONT_BODY,
        )
        style.map(
            "Macro.Treeview",
            background=[("selected", ACCENT_SOFT)],
            foreground=[("selected", TEXT_PRIMARY)],
        )
        style.configure(
            "Macro.Treeview.Heading",
            background=BG_ELEVATED,
            foreground=TEXT_SECONDARY,
            relief="flat",
            borderwidth=0,
            font=FONT_SMALL,
        )
        style.map("Macro.Treeview.Heading", background=[("active", BORDER_HOVER)])
        style.configure(
            "Macro.Vertical.TScrollbar",
            background=BG_ELEVATED,
            troughcolor=BG_SURFACE,
            bordercolor=BG_SURFACE,
            arrowcolor=TEXT_SECONDARY,
        )

    def _build_toolbar(self) -> None:
        self.toolbar = Card(self.root, padding=SPACE_MD)
        self.toolbar.pack(fill=tk.X, padx=SPACE_XL, pady=(SPACE_XL, SPACE_MD))
        body = self.toolbar.body

        tk.Label(
            body,
            text="宏工作台",
            bg=BG_SURFACE,
            fg=TEXT_PRIMARY,
            font=FONT_TITLE,
        ).pack(side=tk.LEFT, padx=(0, SPACE_LG))

        self.btn_record = HoverButton(body, "开始录制 (F9)", self.toggle_record, style="primary", icon="⏺")
        self.btn_record.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        self.btn_play = HoverButton(body, "开始回放 (F10)", self.toggle_play, style="success", icon="▶")
        self.btn_play.pack(side=tk.LEFT, padx=SPACE_SM)
        self.btn_emergency = HoverButton(body, "紧急停止 (F11)", self.emergency_stop, style="danger", icon="⏹")
        self.btn_emergency.pack(side=tk.LEFT, padx=SPACE_SM)

        tk.Frame(body, width=1, bg=BORDER).pack(
            side=tk.LEFT, fill=tk.Y, padx=SPACE_MD, pady=SPACE_SM
        )

        self.btn_save = HoverButton(body, "保存到文件", self.save_macro, style="ghost", icon="💾")
        self.btn_save.pack(side=tk.LEFT, padx=SPACE_SM)
        self.btn_load = HoverButton(body, "打开文件", self.load_macro, style="ghost", icon="📂")
        self.btn_load.pack(side=tk.LEFT, padx=SPACE_SM)
        self.btn_clear = HoverButton(body, "清空", self.clear_macro, style="ghost", icon="🗑")
        self.btn_clear.pack(side=tk.LEFT, padx=SPACE_SM)

    def _build_params(self) -> None:
        card = Card(self.root, title="回放参数", padding=SPACE_MD)
        card.pack(fill=tk.X, padx=SPACE_XL, pady=(0, SPACE_MD))
        body = card.body

        self.var_loops = tk.StringVar(value="0")
        self.var_interval = tk.StringVar(value="1.0")
        self.var_speed = tk.StringVar(value="1.0")
        inputs = (
            ("循环次数", "0=无限", self.var_loops),
            ("轮间间隔 (秒)", "1.0", self.var_interval),
            ("速度倍率", "1.0", self.var_speed),
        )
        for label, value, variable in inputs:
            group = tk.Frame(body, bg=BG_SURFACE)
            group.pack(side=tk.LEFT, padx=(0, SPACE_XL))
            tk.Label(group, text=label, bg=BG_SURFACE, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(
                anchor=tk.W
            )
            entry = tk.Entry(
                group,
                textvariable=variable,
                width=10,
                bg=BG_SURFACE_ALT,
                fg=TEXT_PRIMARY,
                insertbackground=ACCENT,
                selectbackground=ACCENT_SOFT,
                selectforeground=TEXT_PRIMARY,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=1,
                highlightbackground=BORDER,
                highlightcolor=ACCENT,
                font=FONT_BODY,
            )
            entry.pack(pady=(SPACE_XS, 0), ipady=SPACE_XS)

        options = tk.Frame(body, bg=BG_SURFACE)
        options.pack(side=tk.LEFT, padx=(SPACE_SM, 0), fill=tk.Y)
        self.var_skip_move = tk.BooleanVar(value=False)
        self.var_record_move = tk.BooleanVar(value=True)
        self.var_hide_window = tk.BooleanVar(value=True)
        self._make_checkbutton(options, "跳过鼠标移动", self.var_skip_move)
        self._make_checkbutton(options, "录制鼠标移动", self.var_record_move, self._toggle_record_move)
        self._make_checkbutton(options, "录制时隐藏主窗口", self.var_hide_window)

    def _make_checkbutton(
        self,
        parent: tk.Misc,
        text: str,
        variable: tk.BooleanVar,
        command: Optional[Callable[[], None]] = None,
    ) -> tk.Checkbutton:
        button = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            bg=BG_SURFACE,
            fg=TEXT_SECONDARY,
            activebackground=BG_SURFACE,
            activeforeground=TEXT_PRIMARY,
            selectcolor=ACCENT_SOFT,
            highlightthickness=0,
            bd=0,
            padx=SPACE_SM,
            pady=SPACE_XS,
            anchor=tk.W,
            font=FONT_SMALL,
        )
        button.pack(anchor=tk.W)
        button.bind("<Enter>", lambda _event: button.configure(fg=TEXT_PRIMARY))
        button.bind("<Leave>", lambda _event: button.configure(fg=TEXT_SECONDARY))
        return button

    def _build_event_list(self) -> None:
        content = tk.Frame(self.root, bg=BG_DEEP)
        content.pack(fill=tk.BOTH, expand=True, padx=SPACE_XL, pady=(0, SPACE_MD))
        content.grid_columnconfigure(0, weight=72, uniform="content")
        content.grid_columnconfigure(1, weight=28, uniform="content")
        content.grid_rowconfigure(0, weight=1)

        event_card = Card(content, title="事件列表", padding=SPACE_MD)
        event_card.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_SM))
        tree_frame = tk.Frame(event_card.body, bg=BG_SURFACE)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("idx", "time", "type", "detail")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="Macro.Treeview",
        )
        headings = {"idx": "#", "time": "时间 (s)", "type": "类型", "detail": "详情"}
        for column, heading in headings.items():
            self.tree.heading(column, text=heading)
        self.tree.column("idx", width=48, anchor=tk.CENTER, stretch=False)
        self.tree.column("time", width=84, anchor=tk.E, stretch=False)
        self.tree.column("type", width=90, anchor=tk.CENTER, stretch=False)
        self.tree.column("detail", width=380, anchor=tk.W, stretch=True)
        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.tree.yview, style="Macro.Vertical.TScrollbar"
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.tag_configure("hold", background=TREE_HOLD_BG, foreground=TREE_HOLD_FG)
        self.tree.tag_configure("press", background=TREE_PRESS_BG, foreground=TREE_PRESS_FG)

        slot_card = Card(content, title="快捷存档", padding=SPACE_MD)
        slot_card.grid(row=0, column=1, sticky="nsew", padx=(SPACE_SM, 0))
        self._slot_body = slot_card.body

    def _build_statusbar(self) -> None:
        card = Card(self.root, padding=SPACE_SM)
        card.pack(fill=tk.X, padx=SPACE_XL, pady=(0, SPACE_LG))
        self.var_status = tk.StringVar(value="就绪 | F9=录制  F10=回放  F11=紧急停止")
        tk.Label(
            card.body,
            textvariable=self.var_status,
            anchor=tk.W,
            bg=BG_SURFACE,
            fg=TEXT_SECONDARY,
            font=FONT_SMALL,
        ).pack(fill=tk.X)

    # ── 录制 ─────────────────────────────────────────────

    def toggle_record(self) -> None:
        if self.recorder.is_recording:
            self._stop_record()
        elif self.player.is_playing:
            self.var_status.set("⚠ 请先停止回放，再开始录制")
        else:
            self._start_record()

    def _start_record(self) -> None:
        self.recorder.record_mouse_move = self.var_record_move.get()
        self._recorded_count = 0
        self.recorder.start()
        self.btn_record.set_text("停止录制 (F9)")
        self.btn_play.set_enabled(False)
        self.var_status.set("🔴 录制中... 执行你要记录的操作")
        self._refresh_events()
        if self.var_hide_window.get():
            self._show_recording_indicator()

    def _stop_record(self) -> None:
        self.script = self.recorder.stop()
        self.btn_record.set_text("开始录制 (F9)")
        self.btn_play.set_enabled(True)
        self.var_status.set(
            f"✅ 录制完成：{len(self.script.events)} 个事件，时长 {self.script.record_duration:.1f}s"
        )
        self._close_recording_indicator()
        self._refresh_events()
        self._refresh_slots()

    def _on_recorded_event(self, ev: InputEvent) -> None:
        """pynput 线程只投递任务，所有控件更新都发生在 Tk 主线程。"""
        self.root.after(0, self._append_event_row, ev)

    # ── 回放 ─────────────────────────────────────────────

    def toggle_play(self) -> None:
        if self.player.is_playing:
            self.player.stop()
            self._set_play_stopped()
        elif self.recorder.is_recording:
            self.var_status.set("⚠ 请先停止录制，再开始回放")
        else:
            self._start_play()

    def _start_play(self) -> None:
        self._play_script(self.script)

    def _play_script(self, script: MacroScript) -> None:
        if self.recorder.is_recording:
            self.var_status.set("⚠ 请先停止录制，再开始回放")
            return
        if not script.events:
            messagebox.showwarning("提示", "还没有录制任何事件，请先录制。")
            return
        try:
            loops = int(self.var_loops.get() or "0")
            interval = float(self.var_interval.get() or "0")
            speed = float(self.var_speed.get() or "1.0")
        except ValueError:
            messagebox.showerror("参数错误", "请检查循环次数/间隔/速度是否为有效数字。")
            return

        try:
            self.player.play(
                script,
                loop_count=max(0, loops),
                loop_interval=max(0.0, interval),
                speed=min(10.0, max(0.1, speed)),
                skip_mouse_move=self.var_skip_move.get(),
            )
        except RuntimeError as error:
            messagebox.showerror("回放失败", str(error))
            return
        self.btn_play.set_text("停止回放 (F10)")
        self.btn_record.set_enabled(False)
        self.var_status.set(
            f"▶ 回放中：{script.name} | 循环 {'无限' if loops == 0 else loops} 次"
        )
        self._watch_playback()

    def _watch_playback(self) -> None:
        if self.player.is_playing:
            self._play_watch_id = self.root.after(100, self._watch_playback)
        else:
            self._play_watch_id = None
            self._set_play_stopped()

    def _set_play_stopped(self) -> None:
        if self._play_watch_id is not None:
            try:
                self.root.after_cancel(self._play_watch_id)
            except tk.TclError:
                self._play_watch_id = None
            self._play_watch_id = None
        self.btn_play.set_text("开始回放 (F10)")
        self.btn_record.set_enabled(True)
        self.var_status.set("⏹ 回放已停止")

    def _on_play_progress(self, loop_idx: int, ev_idx: int, total: int) -> None:
        self.root.after(
            0,
            lambda: self.var_status.set(
                f"▶ 回放中... 第 {loop_idx + 1} 轮 | 事件 {ev_idx}/{total}"
            ),
        )

    # ── 紧急停止 ─────────────────────────────────────────

    def emergency_stop(self) -> None:
        self.player.stop()
        if self.recorder.is_recording:
            self._stop_record()
        else:
            self._close_recording_indicator()
            self._restore_main_window()
        self._set_play_stopped()
        self.var_status.set("🛑 已紧急停止所有操作")

    # ── 存档槽 ───────────────────────────────────────────

    def _refresh_slots(self) -> None:
        if self._slot_body is None:
            return
        for child in self._slot_body.winfo_children():
            child.destroy()
        try:
            slots = self.slot_manager.list_slots()
        except (OSError, ValueError) as error:
            self.var_status.set(f"槽位读取失败：{error}")
            slots = [None] * self.slot_manager.slot_count
        for slot_id, info in enumerate(slots, start=1):
            slot = Card(self._slot_body, padding=SPACE_SM)
            slot.pack(fill=tk.X, pady=(0, SPACE_SM))
            body = slot.body
            if info is None:
                tk.Label(
                    body, text="空槽位", bg=BG_SURFACE, fg=TEXT_MUTED, font=FONT_SMALL
                ).pack(side=tk.LEFT, expand=True, padx=SPACE_SM)
                HoverButton(
                    body,
                    "保存到此处",
                    lambda number=slot_id: self._save_to_slot(number, overwrite=False),
                    style="ghost",
                    icon="＋",
                    width=110,
                    height=30,
                ).pack(side=tk.RIGHT)
                continue
            self._build_occupied_slot(body, slot_id, info)

    def _build_occupied_slot(self, body: tk.Frame, slot_id: int, info: SlotInfo) -> None:
        header = tk.Frame(body, bg=BG_SURFACE)
        header.pack(fill=tk.X)
        badge = tk.Canvas(header, width=28, height=24, bg=BG_SURFACE, highlightthickness=0)
        badge.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        round_rect(badge, 1, 1, 27, 23, RADIUS_SM, fill=ACCENT_SOFT, outline=ACCENT_SOFT)
        badge.create_text(14, 12, text=str(slot_id), fill=TEXT_PRIMARY, font=FONT_BADGE)
        tk.Label(
            header,
            text=getattr(info, "name", f"存档 {slot_id}"),
            bg=BG_SURFACE,
            fg=TEXT_PRIMARY,
            font=FONT_H2,
            anchor=tk.W,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        meta = (
            f"{info.event_count} 事件 · {info.duration:.1f}s · {info.modified_str}"
        )
        tk.Label(body, text=meta, bg=BG_SURFACE, fg=TEXT_MUTED, font=FONT_SMALL).pack(
            anchor=tk.W, pady=(SPACE_XS, SPACE_SM)
        )
        actions = tk.Frame(body, bg=BG_SURFACE)
        actions.pack(fill=tk.X)
        buttons = (
            ("▶", "success", lambda number=slot_id: self._play_slot(number)),
            ("✎", "ghost", lambda number=slot_id: self._rename_slot(number)),
            ("🗑", "danger", lambda number=slot_id: self._delete_slot(number)),
            ("💾", "ghost", lambda number=slot_id: self._save_to_slot(number, overwrite=True)),
        )
        for text, style, command in buttons:
            HoverButton(actions, text, command, style=style, width=34, height=28).pack(
                side=tk.LEFT, padx=(0, SPACE_XS)
            )

    def _save_to_slot(self, slot_id: int, overwrite: bool) -> None:
        if not self.script.events:
            messagebox.showwarning("提示", "没有可保存的事件。")
            return
        if overwrite and not messagebox.askyesno("确认覆盖", f"覆盖存档槽 {slot_id}？"):
            return
        try:
            self.slot_manager.save(slot_id, self.script)
        except (OSError, ValueError) as error:
            messagebox.showerror("保存失败", str(error))
            return
        self.var_status.set(f"💾 已保存到快捷存档 {slot_id}")
        self._refresh_slots()

    def _play_slot(self, slot_id: int) -> None:
        if self.slot_manager.info(slot_id) is None:
            return
        try:
            script = self.slot_manager.load(slot_id)
        except (FileNotFoundError, OSError, ValueError, KeyError) as error:
            messagebox.showerror("读取失败", str(error))
            return
        self._play_script(script)

    def _rename_slot(self, slot_id: int) -> None:
        name = simpledialog.askstring("重命名存档", f"存档槽 {slot_id} 的名称：", parent=self.root)
        if name is None:
            return
        try:
            self.slot_manager.rename(slot_id, name)
        except (FileNotFoundError, OSError, ValueError, KeyError) as error:
            messagebox.showerror("重命名失败", str(error))
            return
        self._refresh_slots()

    def _delete_slot(self, slot_id: int) -> None:
        if not messagebox.askyesno("确认删除", f"删除存档槽 {slot_id}？"):
            return
        try:
            self.slot_manager.delete(slot_id)
        except (OSError, ValueError) as error:
            messagebox.showerror("删除失败", str(error))
            return
        self.var_status.set(f"🗑 已清空快捷存档 {slot_id}")
        self._refresh_slots()

    # ── 自动隐藏 ─────────────────────────────────────────

    def _show_recording_indicator(self) -> None:
        self._close_recording_indicator()
        self.root.withdraw()
        indicator = tk.Toplevel(self.root)
        indicator.overrideredirect(True)
        indicator.attributes("-topmost", True)
        indicator.configure(bg=BG_DEEP)
        indicator.geometry(
            f"220x56+{indicator.winfo_screenwidth() - 244}+{SPACE_XL}"
        )
        enable_acrylic(indicator, BG_SURFACE)
        shell = Card(indicator, padding=SPACE_SM)
        shell.pack(fill=tk.BOTH, expand=True)
        self._indicator_label = tk.Label(
            shell.body,
            text="🔴 录制中 · 0 事件",
            bg=BG_SURFACE,
            fg=TEXT_PRIMARY,
            font=FONT_SMALL,
        )
        self._indicator_label.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        HoverButton(
            shell.body, "停止", self.toggle_record, style="danger", icon="⏹", width=64, height=28
        ).pack(side=tk.RIGHT)
        self._indicator = indicator

    def _close_recording_indicator(self) -> None:
        indicator = self._indicator
        self._indicator = None
        self._indicator_label = None
        if indicator is not None and indicator.winfo_exists():
            indicator.destroy()
        self._restore_main_window()

    def _restore_main_window(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            return

    def _update_recording_indicator(self) -> None:
        if self._indicator_label is not None and self._indicator_label.winfo_exists():
            self._indicator_label.configure(text=f"🔴 录制中 · {self._recorded_count} 事件")

    # ── 文件 IO ──────────────────────────────────────────

    def save_macro(self) -> None:
        if not self.script.events:
            messagebox.showwarning("提示", "没有可保存的事件。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("宏脚本", "*.json"), ("所有文件", "*.*")],
            initialfile=f"{self.script.name}.json",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.script.to_json())
            self.var_status.set(f"💾 已保存到 {os.path.basename(path)}")
        except OSError as error:
            messagebox.showerror("保存失败", str(error))

    def load_macro(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("宏脚本", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                self.script = MacroScript.from_json(file.read())
            self._refresh_events()
            self._refresh_slots()
            self.var_status.set(f"📂 已加载：{self.script.name} ({len(self.script.events)} 事件)")
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            messagebox.showerror("加载失败", str(error))

    def clear_macro(self) -> None:
        if messagebox.askyesno("确认", "清空当前所有事件？"):
            self.script = MacroScript(name="未命名宏")
            self._refresh_events()
            self._refresh_slots()
            self.var_status.set("🗑 已清空")

    # ── 事件列表辅助 ─────────────────────────────────────

    def _refresh_events(self) -> None:
        self.tree.delete(*self.tree.get_children())
        hold_map = dict(self.script.hold_info())
        for index, ev in enumerate(self.script.events):
            detail = ev.describe().split("] ", 1)[-1]
            tags: tuple[str, ...] = ()
            if index in hold_map:
                duration = hold_map[index]
                detail += f"  ⏱ 按住 {duration:.2f}s" + (" (长按)" if duration >= 0.3 else " (点按)")
                tags = ("hold",)
            elif ev.action == Action.PRESS:
                tags = ("press",)
            self.tree.insert(
                "",
                tk.END,
                values=(index + 1, f"{ev.timestamp:.3f}", self._event_type_label(ev), detail),
                tags=tags,
            )

    def _append_event_row(self, ev: InputEvent) -> None:
        self._recorded_count += 1
        idx = len(self.tree.get_children()) + 1
        detail = ev.describe().split("] ", 1)[-1]
        tags = ("press",) if ev.action == Action.PRESS else ()
        self.tree.insert(
            "", tk.END, values=(idx, f"{ev.timestamp:.3f}", self._event_type_label(ev), detail), tags=tags
        )
        self.tree.yview_moveto(1.0)
        self._update_recording_indicator()

    @staticmethod
    def _event_type_label(ev: InputEvent) -> str:
        return {
            EventType.KEY: "键盘",
            EventType.MOUSE_CLICK: "鼠标",
            EventType.MOUSE_MOVE: "移动",
            EventType.MOUSE_SCROLL: "滚轮",
        }.get(ev.event_type, "?")

    def _toggle_record_move(self) -> None:
        self.recorder.record_mouse_move = self.var_record_move.get()
