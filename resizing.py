"""Eight-direction resizing for borderless Tk windows."""


def resized_geometry(origin, direction, dx, dy, minimum=(260, 220)):
    left, top, width, height = origin
    x, y, w, h = origin
    if "e" in direction:
        w = max(minimum[0], width + dx)
    elif "w" in direction:
        w = max(minimum[0], width - dx)
        x = left + width - w
    if "s" in direction:
        h = max(minimum[1], height + dy)
    elif "n" in direction:
        h = max(minimum[1], height - dy)
        y = top + height - h
    return x, y, w, h


class WindowResizer:
    CURSORS = {"n": "sb_v_double_arrow", "s": "sb_v_double_arrow",
               "e": "sb_h_double_arrow", "w": "sb_h_double_arrow",
               "nw": "size_nw_se", "se": "size_nw_se",
               "ne": "size_ne_sw", "sw": "size_ne_sw"}

    def __init__(self, window, activate):
        self.window, self.activate = window, activate
        self.active = None
        self.grab_widget = None
        self.cursor_widget = None
        self.cursor_direction = None
        self.original_cursors = {}
        self.tag = f"NoteResize_{id(self)}"
        self.bindings = {}
        for sequence, action in [("<Motion>", self.motion), ("<Leave>", self.leave),
                                 ("<ButtonPress-1>", self.start),
                                 ("<B1-Motion>", self.motion), ("<ButtonRelease-1>", self.finish)]:
            self.bindings[sequence] = window.bind_class(self.tag, sequence, action)
        self.install(window)

    def install(self, widget):
        # Handle a border press before button commands or text selection begin.
        widget.bindtags((self.tag, *widget.bindtags()))
        self.original_cursors[widget] = widget.cget("cursor")
        for child in widget.winfo_children():
            self.install(child)

    def direction(self, event):
        w, h = self.window.winfo_width(), self.window.winfo_height()
        x, y = event.x_root - self.window.winfo_rootx(), event.y_root - self.window.winfo_rooty()
        if not (0 <= x < w and 0 <= y < h):
            return None
        horizontal = "w" if x < 10 else "e" if x >= w - 10 else ""
        vertical = "n" if y < 10 else "s" if y >= h - 10 else ""
        if horizontal and vertical:
            return vertical + horizontal
        if x < 5 or x >= w - 5:
            return horizontal
        if y < 5 or y >= h - 5:
            return vertical
        return None

    def set_cursor(self, widget, direction):
        # Resetting a Tk cursor on every mouse-move makes it flicker on Windows.
        if self.cursor_widget == widget and self.cursor_direction == direction:
            return
        if self.cursor_widget is not None and (self.cursor_widget != widget or direction is None):
            self.cursor_widget.configure(cursor=self.original_cursors[self.cursor_widget])
        if direction:
            widget.configure(cursor=self.CURSORS[direction])
        self.cursor_widget = widget if direction else None
        self.cursor_direction = direction

    def start(self, event):
        direction = self.direction(event)
        if not direction:
            return
        self.active = (direction, event.x_root, event.y_root,
                       (self.window.winfo_x(), self.window.winfo_y(),
                        self.window.winfo_width(), self.window.winfo_height()))
        self.activate()
        self.grab_widget = event.widget
        self.grab_widget.grab_set()
        self.set_cursor(self.window, direction)
        return "break"

    def motion(self, event):
        if self.active:
            direction, x, y, origin = self.active
            left, top, width, height = resized_geometry(
                origin, direction, event.x_root - x, event.y_root - y, self.window.minsize())
            self.window.geometry(f"{width}x{height}{left:+d}{top:+d}")
            return "break"
        self.set_cursor(event.widget, self.direction(event))

    def leave(self, event):
        if not self.active and self.cursor_widget == event.widget:
            self.set_cursor(event.widget, None)

    def finish(self, event):
        if self.active:
            # Fast gestures can coalesce motion events while focus changes.
            # Always commit the release position as the final resize point.
            self.motion(event)
            self.active = None
            self.grab_widget.grab_release()
            self.grab_widget = None
            self.set_cursor(self.window, None)
            return "break"

    def close(self):
        if self.active:
            self.grab_widget.grab_release()
        for sequence, function_id in self.bindings.items():
            self.window.unbind_class(self.tag, sequence)
            # bind_class registers callbacks with the Tcl interpreter's root.
            self.window._root().deletecommand(function_id)
