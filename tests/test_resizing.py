import unittest

from resizing import resized_geometry


class ResizeGeometryTests(unittest.TestCase):
    def test_all_eight_directions_hold_opposite_edges(self):
        origin = (100, 80, 340, 300)
        expected = {
            "e": (100, 80, 360, 300), "w": (120, 80, 320, 300),
            "s": (100, 80, 340, 330), "n": (100, 110, 340, 270),
            "ne": (100, 110, 360, 270), "nw": (120, 110, 320, 270),
            "se": (100, 80, 360, 330), "sw": (120, 80, 320, 330),
        }
        for direction, geometry in expected.items():
            with self.subTest(direction=direction):
                self.assertEqual(resized_geometry(origin, direction, 20, 30), geometry)

    def test_minimum_size_keeps_right_and_bottom_anchored(self):
        self.assertEqual(resized_geometry((100, 80, 340, 300), "nw", 1000, 1000), (180, 160, 260, 220))
        self.assertEqual(resized_geometry((100, 80, 340, 300), "se", -1000, -1000), (100, 80, 260, 220))
