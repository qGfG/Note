import tempfile
import unittest
from pathlib import Path

from storage import NoteStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = NoteStore(Path(self.temp.name))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_persists_unicode_and_literal_search(self):
        note = self.store.create("明天计划", "完成 100% 的目标_\n第二行")
        self.store.update(note, body="新内容：100%_", color="薄荷")
        self.store.close()
        self.store = NoteStore(Path(self.temp.name))
        self.assertEqual(self.store.get(note)["body"], "新内容：100%_")
        self.assertEqual(len(self.store.list("%_")), 1)
        self.assertEqual(self.store.list("无结果"), [])

    def test_pin_trash_restore_and_purge(self):
        first = self.store.create("重要")
        second = self.store.create("其他")
        self.store.update(first, pinned=1)
        self.assertEqual(self.store.list()[0]["id"], first)
        self.assertEqual(len(self.store.list(mode="pinned")), 1)
        self.store.purge(first)
        self.assertIsNotNone(self.store.get(first))
        self.store.update(first, deleted=1)
        self.assertEqual([n["id"] for n in self.store.list()], [second])
        self.assertEqual(len(self.store.list(mode="trash")), 1)
        self.store.update(first, deleted=0)
        self.assertEqual(len(self.store.list(mode="pinned")), 1)
        self.store.update(first, deleted=1)
        self.store.purge(first)
        self.assertIsNone(self.store.get(first))

    def test_rejects_unknown_fields(self):
        note = self.store.create()
        with self.assertRaises(ValueError):
            self.store.update(note, unexpected="value")

    def test_last_closed_is_persisted_and_skips_deleted_notes(self):
        first = self.store.create(body="先关闭的便笺")
        second = self.store.create()
        self.assertIsNone(self.store.last_closed())
        self.store.remember_closed(first)
        self.store.remember_closed(second)
        self.store.update(first, body="后来编辑的正文")
        self.store.close()
        self.store = NoteStore(Path(self.temp.name))
        self.assertEqual(self.store.last_closed()["id"], second)
        self.store.update(second, deleted=1)
        self.assertEqual(self.store.last_closed()["id"], first)


if __name__ == "__main__":
    unittest.main()
