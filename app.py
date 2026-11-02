"""Small, independent sticky-note windows with persistent always-on-top."""
from __future__ import annotations

import argparse
import ctypes
import json
import sqlite3
import tkinter as tk
import tkinter.font as tkfont
import time
from pathlib import Path
from tkinter import messagebox

from storage import NoteStore, default_data_dir
from runtime import InstanceLock, migrate_legacy
from caption import configure_borderless
from formatting import NoteFormatting
from resizing import WindowResizer

FONT = "Microsoft YaHei UI"
INK = "#39372F"
COLORS = {
    "奶油": ("#FFF8CE", "#FFF2A8"),
    "薄荷": ("#E1F1D5", "#C5DFAF"),
    "晴空": ("#E0EFFA", "#BBD9EF"),
    "蜜桃": ("#FCE2DF", "#F0BCB7"),
    "薰衣草": ("#EEE3F6", "#D7C2E6"),
}


def has_content(note):
    if note["title"].strip() or note["body"].strip():
        return True
    try:
        return bool(json.loads(note["formatting"]).get("images"))
    except (ValueError, TypeError, AttributeError):
        return False


class StickyNote(NoteFormatting):
    def __init__(self, app, note, index=0):
        self.app, self.store = app, app.store
        self.note_id = note["id"]
        self.topmost = bool(note["topmost"])
        self.color = note["color"]
        self.pending = None
        self.dirty = False
        self.controls_progress = 0.0
        self.controls_target = False
        self.animation_job = None
        self.focus_job = None
        self.menu_open = False
        self.closing = False
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("便笺")
        self.window.overrideredirect(True)
        self.images = {}
        self.fonts = {}
        self.window.minsize(260, 220)
        geometry = note["geometry"] or f"304x290+{120 + (index % 8) * 36}+{100 + (index % 8) * 36}"
        try:
            self.window.geometry(geometry)
        except tk.TclError:
            self.window.geometry("304x290")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.toolbar = tk.Frame(self.window, height=32)
        self.toolbar.pack_propagate(False)
        self.new_button = self.button("＋", app.new_note, side="left", font=("Segoe UI", 15))
        self.close_button = self.button("×", self.close, side="right", font=("Segoe UI Light", 16))
        self.menu_button = self.button("···", self.show_menu, side="right", font=("Segoe UI", 12))
        self.pin_image = tk.PhotoImage(master=self.window, width=16, height=16)
        self.pin_button = self.button("", self.toggle_topmost, side="right")
        self.pin_button.configure(image=self.pin_image, padx=7)
        self.toolbar.bind("<ButtonPress-1>", self.start_drag)
        self.toolbar.bind("<B1-Motion>", self.drag)
        self.footer = tk.Frame(self.window, height=39)
        self.footer.pack_propagate(False)
        tk.Frame(self.footer, height=1, bg="#E9E1B7").pack(side="top", fill="x")
        self.format_buttons = []
        for label, flag, font in [("B", 1, ("Segoe UI", 11, "bold")),
                                  ("I", 2, ("Georgia", 11, "italic")),
                                  ("U", 4, ("Segoe UI", 11, "underline")),
                                  ("ab", 8, ("Segoe UI", 10, "overstrike"))]:
            button = tk.Button(self.footer, text=label, command=lambda f=flag: self.toggle_format(f),
                               font=font, relief="flat", bd=0, fg="#66634F", width=3,
                               cursor="hand2", takefocus=False)
            button.pack(side="left", fill="y", padx=1, pady=4)
            self.format_buttons.append(button)
        for label, action in [("≡", self.toggle_bullets), ("▧", self.insert_image)]:
            button = tk.Button(self.footer, text=label, command=action, font=("Segoe UI", 14),
                               relief="flat", bd=0, fg="#66634F", width=2, cursor="hand2", takefocus=False)
            button.pack(side="left", fill="y", padx=2, pady=4)
            self.format_buttons.append(button)
        self.status = tk.Label(self.window, text="", anchor="w", font=(FONT, 8), fg="#756D50", padx=14, pady=4)
        self.text = tk.Text(self.window, wrap="word", undo=True, relief="flat", bd=0,
                            font=(FONT, 10), fg=INK, insertbackground=INK,
                            padx=11, pady=9, spacing1=0, spacing3=0,
                            highlightthickness=0, width=25, height=10)
        # Reserve the same paper margins in both states. Only the controls move.
        self.text.place(x=0, y=32, relwidth=1, relheight=1, height=-71)
        self.position_controls()
        for mask in range(1, 16):
            font = tkfont.Font(family=FONT, size=10, weight="bold" if mask & 1 else "normal",
                               slant="italic" if mask & 2 else "roman", underline=bool(mask & 4), overstrike=bool(mask & 8))
            self.fonts[mask] = font
            self.text.tag_configure(f"fmt_{mask}", font=font)
        # Fold titles from the previous version into the page, preserving all text.
        content = note["body"]
        if note["title"] and note["title"] != "无标题便笺":
            content = note["title"] + ("\n\n" + content if content else "")
        self.text.insert("1.0", content)
        self.restore_formatting(note["formatting"])
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")
        self.saved_document = (self.text.get("1.0", "end-1c"), self.formatting())
        self.legacy_title = bool(note["title"])
        self.saved_window_state = {"topmost": note["topmost"], "color": note["color"], "geometry": note["geometry"]}
        self.text.edit_modified(False)
        self.text.bind("<<Modified>>", self.changed)
        self.text.bind("<FocusOut>", lambda _: self.save())
        self.text.bind("<Return>", self.continue_bullet)
        self.window.bind("<Configure>", self.configured)
        self.window.bind("<FocusIn>", self.schedule_focus_check)
        self.window.bind("<FocusOut>", self.schedule_focus_check)
        self.window.bind("<ButtonPress-1>", self.activate_controls, add="+")
        self.window.bind("<Control-n>", lambda _: self.shortcut(app.new_note))
        self.window.bind("<Control-s>", lambda _: self.shortcut(self.save))
        self.window.bind("<Control-p>", lambda _: self.shortcut(self.toggle_topmost))
        self.resizer = WindowResizer(self.window, self.activate_controls)
        self.apply_color()
        self.apply_topmost()
        self.window.update_idletasks()
        # Recover windows if a monitor was removed or its resolution changed.
        x, y = self.window.winfo_x(), self.window.winfo_y()
        if x + self.window.winfo_width() < 40 or y < 0 or x > self.window.winfo_screenwidth() - 40 or y > self.window.winfo_screenheight() - 40:
            self.window.geometry("+120+100")
        configure_borderless(self.window)
        self.window.deiconify()
        self.text.focus_set()

    def position_controls(self):
        if self.controls_progress <= 0:
            self.toolbar.place_forget()
            self.footer.place_forget()
            return
        self.toolbar.place(x=0, y=round(-32 * (1 - self.controls_progress)), relwidth=1, height=32)
        self.footer.place(x=0, rely=1, y=round(39 * (1 - self.controls_progress)),
                          anchor="sw", relwidth=1, height=39)
        self.toolbar.lift()
        self.footer.lift()

    def show_controls(self, visible, animate=True):
        target = float(visible)
        if self.controls_target == bool(visible) and (self.animation_job or self.controls_progress == target):
            return
        self.controls_target = bool(visible)
        if self.animation_job:
            self.window.after_cancel(self.animation_job)
            self.animation_job = None
        if not animate:
            self.controls_progress = target
            self.position_controls()
            return
        start = self.controls_progress
        started = time.monotonic()

        def tick():
            self.animation_job = None
            elapsed = min(1.0, (time.monotonic() - started) / 0.18)
            eased = 1 - (1 - elapsed) ** 3
            self.controls_progress = start + (target - start) * eased
            self.position_controls()
            if elapsed < 1:
                self.animation_job = self.window.after(16, tick)

        tick()

    def activate_controls(self, _=None):
        self.app.last_active_id = self.note_id
        self.show_controls(True)
        self.text.focus_set()

    def schedule_focus_check(self, _=None):
        if self.closing:
            return
        if self.focus_job:
            self.window.after_cancel(self.focus_job)
        # Let focus settle between the editor, toolbar, and popup menu.
        self.focus_job = self.window.after(70, self.check_focus)

    def check_focus(self):
        self.focus_job = None
        focused = self.window.focus_get()
        inside = focused is not None and (focused == self.window or str(focused).startswith(str(self.window) + "."))
        if inside:
            self.app.last_active_id = self.note_id
        self.show_controls(inside or self.menu_open)

    def menu_closed(self, _=None):
        self.menu_open = False
        self.schedule_focus_check()

    def button(self, text, command, side, font=(FONT, 9)):
        button = tk.Button(self.toolbar, text=text, command=command, bd=0,
                           relief="flat", fg=INK, cursor="hand2", padx=7, pady=0,
                           font=font, takefocus=False)
        button.pack(side=side)
        return button

    @staticmethod
    def shortcut(action):
        action()
        return "break"

    def apply_color(self):
        paper, header = COLORS.get(self.color, COLORS["奶油"])
        self.window.configure(bg=paper)
        self.toolbar.configure(bg=header)
        self.text.configure(bg=paper)
        self.status.configure(bg=paper)
        self.footer.configure(bg=paper)
        for button in (self.new_button, self.pin_button, self.menu_button, self.close_button):
            button.configure(bg=header, activebackground=paper, activeforeground=INK)
        for button in self.format_buttons:
            button.configure(bg=paper, activebackground=header)

    def apply_topmost(self):
        self.window.attributes("-topmost", self.topmost)
        self.pin_image.blank()
        color = "#866000" if self.topmost else "#77715B"
        for rect in [(5, 2, 11, 3), (6, 3, 7, 7), (9, 3, 10, 7),
                     (5, 7, 6, 8), (10, 7, 11, 8), (4, 8, 12, 9), (7, 9, 8, 14)]:
            self.pin_image.put(color, to=rect)
        if self.topmost:
            self.pin_image.put(color, to=(6, 3, 10, 8))
        configure_borderless(self.window)

    def start_drag(self, event):
        self.drag_origin = (event.x_root, event.y_root, self.window.winfo_x(), self.window.winfo_y())

    def drag(self, event):
        x, y, left, top = self.drag_origin
        self.window.geometry(f"{left + event.x_root - x:+d}{top + event.y_root - y:+d}")

    def toggle_topmost(self):
        previous = self.topmost
        self.topmost = not previous
        if not self.save():
            self.topmost = previous
            return
        self.apply_topmost()

    def set_color(self, color):
        previous = self.color
        self.color = color
        if not self.save():
            self.color = previous
            return
        self.apply_color()

    def show_menu(self):
        menu = tk.Menu(self.window, tearoff=False, font=(FONT, 10))
        palette = tk.Menu(menu, tearoff=False)
        for name in COLORS:
            palette.add_command(label=("✓ " if name == self.color else "    ") + name,
                                command=lambda c=name: self.set_color(c))
        menu.add_cascade(label="颜色", menu=palette)
        other = tk.Menu(menu, tearoff=False)
        for note in self.store.list():
            label = (note["title"] or note["body"].split("\n")[0] or "空白便笺")[:24]
            other.add_command(label=label, command=lambda n=note: self.app.open_note(n))
        menu.add_cascade(label="打开便笺", menu=other)
        menu.add_separator()
        menu.add_command(label="删除这条便笺", command=self.delete)
        menu.add_command(label="退出所有便笺", command=self.app.quit)
        menu.bind("<Unmap>", self.menu_closed)
        try:
            self.menu_open = True
            self.show_controls(True)
            menu.tk_popup(self.menu_button.winfo_rootx(), self.menu_button.winfo_rooty() + self.menu_button.winfo_height())
        finally:
            menu.grab_release()

    def changed(self, _=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.dirty = True
        self.status.configure(text="正在保存…", fg="#756D50")
        self.schedule_save()

    def configured(self, event):
        if event.widget == self.window:
            self.schedule_save()

    def schedule_save(self):
        if self.pending:
            self.window.after_cancel(self.pending)
        self.pending = self.window.after(500, self.save)

    def save(self):
        if self.pending:
            self.window.after_cancel(self.pending)
            self.pending = None
        document = (self.text.get("1.0", "end-1c"), self.formatting())
        window_state = {"topmost": int(self.topmost), "color": self.color, "geometry": self.window.geometry()}
        values = {key: value for key, value in window_state.items() if value != self.saved_window_state[key]}
        if document != self.saved_document or self.legacy_title:
            values.update(title="", body=document[0], formatting=document[1])
        try:
            if values:
                self.store.update(self.note_id, **values)
        except (sqlite3.Error, OSError) as error:
            self.status.configure(text="保存失败 · Ctrl+S 重试", fg="#A33425")
            if not self.app.save_error_shown:
                self.app.save_error_shown = True
                messagebox.showerror("保存失败", f"请保留便笺窗口，稍后按 Ctrl+S 重试。\n\n{error}", parent=self.window)
            return False
        self.app.save_error_shown = False
        self.saved_document = document
        self.saved_window_state = window_state
        self.legacy_title = False
        self.dirty = False
        self.status.configure(text="", fg="#756D50")
        return True

    def close(self):
        if self.save():
            try:
                self.store.remember_closed(self.note_id)
            except (sqlite3.Error, OSError) as error:
                messagebox.showerror("无法记录关闭状态", str(error), parent=self.window)
                return False
            self.destroy()
            return True
        return False

    def destroy(self):
        self.closing = True
        self.resizer.close()
        for job in (self.animation_job, self.focus_job):
            if job:
                self.window.after_cancel(job)
        self.animation_job = self.focus_job = None
        if self.pending:
            self.window.after_cancel(self.pending)
            self.pending = None
        self.app.windows.pop(self.note_id, None)
        self.window.destroy()
        if not self.app.windows:
            self.store.close()
            self.app.root.destroy()

    def delete(self):
        if not messagebox.askyesno("删除便笺", "确定删除这条便笺吗？", parent=self.window):
            return
        if self.save():
            self.store.update(self.note_id, deleted=1)
            self.destroy()


class NotesApp:
    def __init__(self, root, store):
        self.root, self.store = root, store
        self.windows = {}
        self.save_error_shown = False
        self.last_active_id = None
        root.withdraw()
        note = store.last_closed()
        if note is None:
            notes = store.list()
            # Older versions did not record closure order. Migrate by selecting
            # one existing note, preferring the most recently edited writing.
            note = max(notes, key=lambda item: (has_content(item), item["updated_at"])) if notes else store.get(store.create())
        self.open_note(note)

    def open_note(self, note):
        self.last_active_id = note["id"]
        existing = self.windows.get(note["id"])
        if existing:
            existing.window.deiconify()
            existing.window.lift()
            existing.text.focus_set()
            return existing
        window = StickyNote(self, self.store.get(note["id"]), len(self.windows))
        self.windows[note["id"]] = window
        return window

    def new_note(self):
        try:
            return self.open_note(self.store.get(self.store.create()))
        except (sqlite3.Error, OSError) as error:
            messagebox.showerror("无法新建便笺", str(error), parent=self.root)

    def quit(self):
        for note in list(self.windows.values()):
            if not note.save():
                return
        # With "exit all", close the active note last so it is restored next time.
        notes = sorted(self.windows.values(), key=lambda note: note.note_id == self.last_active_id)
        for note in notes:
            if not note.close():
                return


def main():
    parser = argparse.ArgumentParser(description="桌面便笺 · 支持始终置顶")
    parser.add_argument("--data-dir", type=Path, help="自定义数据目录")
    args = parser.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    root.withdraw()
    icon = Path(__file__).resolve().parent / "assets" / "note.ico"
    if icon.exists():
        root.iconbitmap(default=str(icon))
    lock = None
    try:
        directory = args.data_dir.resolve() if args.data_dir else default_data_dir()
        lock = InstanceLock(directory)
        if args.data_dir is None:
            migrate_legacy(directory)
        store = NoteStore(directory)
    except (sqlite3.Error, OSError, RuntimeError) as error:
        messagebox.showerror("无法打开便笺", str(error), parent=root)
        if lock:
            lock.close()
        root.destroy()
        return
    try:
        NotesApp(root, store)
        root.mainloop()
    finally:
        lock.close()


if __name__ == "__main__":
    main()
