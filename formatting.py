"""Formatting and inline image persistence for a sticky-note page."""
import json
import shutil
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox


class NoteFormatting:
    def toggle_format(self, flag):
        try:
            start, end = self.text.index("sel.first"), self.text.index("sel.last")
        except tk.TclError:
            self.text.focus_set()
            return
        chars = []
        index = start
        while self.text.compare(index, "<", end):
            mask = next((int(tag[4:]) for tag in self.text.tag_names(index) if tag.startswith("fmt_")), 0)
            chars.append((index, mask))
            index = self.text.index(f"{index}+1c")
        remove = all(mask & flag for _, mask in chars)
        for index, mask in chars:
            stop = self.text.index(f"{index}+1c")
            for number in range(1, 16):
                self.text.tag_remove(f"fmt_{number}", index, stop)
            mask = mask & ~flag if remove else mask | flag
            if mask:
                self.text.tag_add(f"fmt_{mask}", index, stop)
        self.schedule_save()
        self.text.focus_set()

    def toggle_bullets(self):
        try:
            start, end = self.text.index("sel.first linestart"), self.text.index("sel.last-1c linestart")
        except tk.TclError:
            start = end = self.text.index("insert linestart")
        first, last = int(start.split(".")[0]), int(end.split(".")[0])
        remove = all(self.text.get(f"{line}.0", f"{line}.2") == "• " for line in range(first, last + 1))
        self.text.edit_separator()
        for line in range(first, last + 1):
            if remove:
                self.text.delete(f"{line}.0", f"{line}.2")
            elif self.text.get(f"{line}.0", f"{line}.2") != "• ":
                self.text.insert(f"{line}.0", "• ")
        self.text.edit_separator()
        self.text.focus_set()

    def continue_bullet(self, _):
        if self.text.tag_ranges("sel"):
            return
        line = self.text.get("insert linestart", "insert lineend")
        if line.startswith("• "):
            if line.strip() == "•":
                self.text.delete("insert linestart", "insert lineend")
            else:
                self.text.insert("insert", "\n• ")
            return "break"

    def insert_image(self):
        path = filedialog.askopenfilename(parent=self.window, title="插入图片", filetypes=[("PNG / GIF 图片", "*.png *.gif")])
        if not path:
            return
        try:
            photo = self.load_photo(path)
            directory = self.store.directory / "images"
            directory.mkdir(exist_ok=True)
            filename = uuid.uuid4().hex + Path(path).suffix.lower()
            shutil.copyfile(path, directory / filename)
            name = self.text.image_create("insert", image=photo, padx=2, pady=4)
            self.images[name] = (filename, photo)
            self.schedule_save()
        except (OSError, tk.TclError) as error:
            messagebox.showerror("无法插入图片", str(error), parent=self.window)

    def load_photo(self, path):
        # Let pathlib handle Unicode Windows paths, then decode the image in Tk.
        photo = tk.PhotoImage(master=self.window, data=Path(path).read_bytes())
        factor = max(1, (photo.width() + 239) // 240)
        return photo.subsample(factor) if factor > 1 else photo

    def formatting(self):
        tags = {f"fmt_{mask}": [str(index) for index in self.text.tag_ranges(f"fmt_{mask}")]
                for mask in range(1, 16) if self.text.tag_ranges(f"fmt_{mask}")}
        images = [{"index": index, "file": self.images[value][0]}
                  for kind, value, index in self.text.dump("1.0", "end-1c", image=True, text=False, mark=False, tag=False)
                  if kind == "image" and value in self.images]
        return json.dumps({"tags": tags, "images": images}, ensure_ascii=False)

    def restore_formatting(self, value):
        try:
            data = json.loads(value)
            for entry in data.get("images", []):
                filename = Path(entry["file"]).name
                try:
                    photo = self.load_photo(self.store.directory / "images" / filename)
                    name = self.text.image_create(entry["index"], image=photo, padx=2, pady=4)
                    self.images[name] = (filename, photo)
                except (OSError, tk.TclError):
                    self.text.insert(entry["index"], "[图片丢失]")
            for tag, ranges in data.get("tags", {}).items():
                if tag in {f"fmt_{mask}" for mask in range(1, 16)}:
                    for start, end in zip(ranges[::2], ranges[1::2]):
                        self.text.tag_add(tag, start, end)
        except (ValueError, TypeError, KeyError, tk.TclError):
            pass
