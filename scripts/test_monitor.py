#!/usr/bin/env python3
"""Display selection and logical-coordinate checks; no attached screens required."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "share/pylib"))
from amigaxdev.monitor import Display, position


class Monitors(unittest.TestCase):
    def test_arrangement(self):
        displays = [Display(1, 0, 0, 1728, 1117, True),
                    Display(2, -1920, -200, 1920, 1080, False),
                    Display(3, 1728, 100, 2560, 1440, False)]
        self.assertEqual(position(displays, "left"), (-1880, -160))
        self.assertEqual(position(displays, "right"), (1768, 140))
        self.assertEqual(position(displays, "primary"), (40, 40))
        self.assertEqual(position(displays, "auto"), (-1880, -160))

    def test_single_and_no_displays(self):
        single = [Display(1, 0, 0, 1728, 1117, True)]
        self.assertIsNone(position(single, "auto"))
        self.assertIsNone(position([], "auto"))
        for selection in ("left", "right", "primary"):
            self.assertEqual(position(single, selection), (40, 40))
            with self.assertRaises(RuntimeError):
                position([], selection)

    def test_stacked_and_mirrored(self):
        displays = [Display(2, 0, 0, 1920, 1080, False),
                    Display(1, 0, 0, 1728, 1117, True),
                    Display(3, 0, -1080, 1920, 1080, False)]
        self.assertEqual(position(displays, "left"), (40, -1040))
        self.assertEqual(position(displays, "right"), (40, -1040))
        self.assertEqual(position(displays, "primary"), (40, 40))

    def test_bad_selection(self):
        with self.assertRaises(ValueError):
            position([], "typo")


if __name__ == "__main__":
    unittest.main()
