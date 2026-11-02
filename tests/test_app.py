import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

from app import NotesApp
from storage import NoteStore


class StickyNoteTests(unittest.TestCase):
    def pump(self, milliseconds=260):
        self.root.after(milliseconds, self.root.quit)
        self.root.mainloop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = NoteStore(Path(self.temp.name))
        self.note_id = self.store.create("旧标题", "原来的内容")
        self.root = tk.Tk()
        self.app = NotesApp(self.root, self.store)
        self.root.update()
        self.note = self.app.windows[self.note_id]

    def tearDown(self):
        self.app.quit()
        self.temp.cleanup()

    def test_old_content_is_preserved_and_autosaved(self):
        self.assertEqual(self.note.text.get("1.0", "end-1c"), "旧标题\n\n原来的内容")
        self.note.text.insert("end", "\n新增内容")
        self.root.update()
        self.root.after(650, self.root.quit)
        self.root.mainloop()
        saved = self.store.get(self.note_id)
        self.assertEqual(saved["body"], "旧标题\n\n原来的内容\n新增内容")
        self.assertEqual(saved["title"], "")

    def test_topmost_is_real_window_attribute_and_persists(self):
        self.note.toggle_topmost()
        self.root.update()
        self.assertTrue(self.note.window.attributes("-topmost"))
        self.assertEqual(self.store.get(self.note_id)["topmost"], 1)
        self.note.toggle_topmost()
        self.root.update()
        self.assertFalse(self.note.window.attributes("-topmost"))
        self.assertEqual(self.store.get(self.note_id)["topmost"], 0)

    def test_independent_windows_close_and_reopen(self):
        second = self.app.new_note()
        self.root.update()
        second.text.insert("1.0", "另一张便笺")
        second.window.geometry("300x280+220+180")
        self.root.update()
        second.toggle_topmost()
        second_id = second.note_id
        second.close()
        self.assertNotIn(second_id, self.app.windows)
        reopened = self.app.open_note(self.store.get(second_id))
        self.root.update()
        self.assertEqual(reopened.text.get("1.0", "end-1c"), "另一张便笺")
        self.assertTrue(reopened.window.attributes("-topmost"))
        self.assertEqual(reopened.window.geometry(), "300x280+220+180")
        self.assertFalse(self.note.window.attributes("-topmost"))

    def test_combined_formatting_survives_reopen(self):
        self.note.text.tag_add("sel", "1.0", "1.3")
        self.note.toggle_format(1)
        self.note.toggle_format(2)
        self.assertIn("fmt_3", self.note.text.tag_names("1.0"))
        self.app.new_note()
        self.note.close()
        self.note = self.app.open_note(self.store.get(self.note_id))
        self.assertEqual([str(i) for i in self.note.text.tag_ranges("fmt_3")], ["1.0", "1.3"])

    def test_images_keep_their_positions_after_reopen(self):
        directory = Path(self.temp.name)
        fixture = tk.PhotoImage(master=self.root, width=4, height=4)
        fixture.put("#FFCC00", to=(0, 0, 4, 4))
        (directory / "fixture.png").write_bytes(fixture.data(format="png"))
        self.note.text.delete("1.0", "end")
        self.note.text.insert("1.0", "甲乙丙丁")
        with patch("formatting.filedialog.askopenfilename", return_value=str(directory / "fixture.png")):
            self.note.text.mark_set("insert", "1.1")
            self.note.insert_image()
            self.note.text.mark_set("insert", "1.4")
            self.note.insert_image()
        before = [(kind, index) for kind, _, index in self.note.text.dump("1.0", "end-1c", image=True) if kind == "image"]
        self.app.new_note()
        self.note.close()
        self.note = self.app.open_note(self.store.get(self.note_id))
        after = [(kind, index) for kind, _, index in self.note.text.dump("1.0", "end-1c", image=True) if kind == "image"]
        self.assertEqual(before, after)
        self.assertEqual(len(after), 2)
        self.assertEqual(self.note.text.get("1.0", "end-1c"), "甲乙丙丁")

    def test_bullets_continue_and_empty_bullet_ends_list(self):
        self.note.text.delete("1.0", "end")
        self.note.text.insert("1.0", "任务")
        self.note.text.mark_set("insert", "1.end")
        self.note.toggle_bullets()
        self.assertEqual(self.note.text.get("1.0", "end-1c"), "• 任务")
        self.assertEqual(self.note.continue_bullet(None), "break")
        self.assertEqual(self.note.text.get("1.0", "end-1c"), "• 任务\n• ")
        self.note.continue_bullet(None)
        self.assertEqual(self.note.text.get("1.0", "end-1c"), "• 任务\n")

    def test_focus_slides_controls_without_moving_text_or_unpinning(self):
        self.note.toggle_topmost()
        self.root.update()
        original_bounds = (self.note.text.winfo_y(), self.note.text.winfo_height())
        with patch.object(self.note.window, "focus_get", return_value=self.note.text):
            self.note.check_focus()
            self.pump()
        self.assertEqual(self.note.controls_progress, 1.0)
        self.assertEqual(self.note.toolbar.winfo_y(), 0)
        self.assertTrue(self.note.footer.winfo_ismapped())
        with patch.object(self.note.window, "focus_get", return_value=None):
            self.note.check_focus()
            self.pump()
        self.assertEqual(self.note.controls_progress, 0.0)
        self.assertFalse(self.note.toolbar.winfo_ismapped())
        self.assertFalse(self.note.footer.winfo_ismapped())
        self.assertEqual((self.note.text.winfo_y(), self.note.text.winfo_height()), original_bounds)
        self.assertTrue(self.note.window.attributes("-topmost"))

    def test_popup_keeps_controls_visible_and_animation_can_reverse(self):
        with patch.object(self.note.window, "focus_get", return_value=None):
            self.note.menu_open = True
            self.note.check_focus()
            self.pump(50)
            self.assertGreater(self.note.controls_progress, 0)
            self.note.menu_open = False
            self.note.check_focus()
            self.pump(50)
            self.note.activate_controls()
            self.pump()
        self.assertEqual(self.note.controls_progress, 1.0)

    def test_edge_resizing_works_with_hidden_controls(self):
        self.note.show_controls(False, animate=False)
        self.note.window.geometry("340x300+120+100")
        self.root.update()
        left, top = self.note.window.winfo_rootx(), self.note.window.winfo_rooty()
        event = SimpleNamespace(x_root=left + 339, y_root=top + 150, widget=self.note.text)
        self.assertEqual(self.note.resizer.start(event), "break")
        event.x_root += 50
        self.note.resizer.motion(event)
        self.note.resizer.finish(event)
        self.root.update()
        self.assertEqual(self.note.window.geometry(), "390x300+120+100")
        # Move the top edge only; the bottom edge must stay fixed.
        event.x_root, event.y_root = left + 100, top + 1
        self.note.resizer.start(event)
        event.y_root -= 30
        self.note.resizer.motion(event)
        self.note.resizer.finish(event)
        self.root.update()
        self.assertEqual(self.note.window.geometry(), "390x330+120+70")

    def test_resize_hit_areas_and_interior_text_selection(self):
        self.note.window.geometry("340x300+120+100")
        self.root.update()
        left, top = self.note.window.winfo_rootx(), self.note.window.winfo_rooty()
        for x, y, direction in [(2, 150, "w"), (337, 150, "e"), (170, 2, "n"), (170, 297, "s"),
                                 (7, 7, "nw"), (332, 7, "ne"), (7, 292, "sw"), (332, 292, "se"),
                                 (100, 100, None)]:
            event = SimpleNamespace(x_root=left + x, y_root=top + y)
            self.assertEqual(self.note.resizer.direction(event), direction)
        event = SimpleNamespace(x_root=left + 100, y_root=top + 100, widget=self.note.text)
        self.assertIsNone(self.note.resizer.start(event))
        self.assertIsNone(self.note.resizer.active)

    def test_fast_vertical_resize_commits_release_position(self):
        self.note.window.geometry("340x300+120+100")
        self.root.update()
        event = SimpleNamespace(x_root=290, y_root=398, widget=self.note.footer)
        self.note.resizer.start(event)
        event.y_root -= 50
        self.note.resizer.finish(event)
        self.root.update()
        self.assertEqual(self.note.window.geometry(), "340x250+120+100")

    def test_mouse_motion_does_not_repeatedly_reset_cursor(self):
        self.note.window.geometry("340x300+120+100")
        self.root.update()
        event = SimpleNamespace(x_root=220, y_root=200, widget=self.note.text)
        with patch.object(self.note.text, "configure", wraps=self.note.text.configure) as configure:
            for _ in range(40):
                self.note.resizer.motion(event)
            self.assertEqual(configure.call_count, 0)
            event.x_root = 122
            for _ in range(40):
                self.note.resizer.motion(event)
            self.assertEqual(configure.call_count, 1)
            event.x_root = 220
            for _ in range(40):
                self.note.resizer.motion(event)
            self.assertEqual(configure.call_count, 2)

    def test_metadata_save_does_not_overwrite_newer_content(self):
        self.note.save()
        self.store.update(self.note_id, body="从另一个窗口保存的最新内容")
        self.note.window.geometry("350x300+120+100")
        self.root.update()
        self.note.save()
        self.assertEqual(self.store.get(self.note_id)["body"], "从另一个窗口保存的最新内容")

    def test_startup_restores_only_last_closed_note_even_when_empty(self):
        last = self.app.new_note()
        last_id = last.note_id
        self.app.quit()
        self.store = NoteStore(Path(self.temp.name))
        self.root = tk.Tk()
        self.app = NotesApp(self.root, self.store)
        self.root.update()
        self.note = self.app.windows[last_id]
        self.assertEqual(list(self.app.windows), [last_id])
        self.assertEqual(self.note.text.index("insert"), "1.0")
        self.assertIn("原来的内容", self.store.get(self.note_id)["body"])

    def test_exit_all_restores_active_note_not_last_created(self):
        self.app.new_note()
        self.app.open_note(self.store.get(self.note_id))
        self.app.quit()
        self.store = NoteStore(Path(self.temp.name))
        self.root = tk.Tk()
        self.app = NotesApp(self.root, self.store)
        self.root.update()
        self.note = self.app.windows[self.note_id]
        self.assertEqual(list(self.app.windows), [self.note_id])


if __name__ == "__main__":
    unittest.main()
