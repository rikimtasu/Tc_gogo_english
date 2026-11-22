import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/p4"))
from loc_graphic_menus import localize_graphic_menus
from loc_systemzip import localize_systemzip
from loc_battle_hud import localize_res_and_etc
from render_helpers import draw_text_in_box


class BoundedTextTests(unittest.TestCase):
    def test_numeric_punctuation_shares_digit_baseline(self):
        bottoms = []
        for text in ("0", "1", ".", "%", "s"):
            image = Image.new("RGBA", (16, 16))
            draw_text_in_box(image, (0, 0, 16, 16), text, 12, baseline=12)
            pixels = np.array(image)
            ink = (pixels[:, :, :3] > 180).all(axis=2) & (pixels[:, :, 3] >= 200)
            bottoms.append(np.where(ink)[0].max())
        self.assertEqual(len(set(bottoms)), 1, bottoms)

    def test_outline_and_descenders_stay_inside_cell(self):
        for text, box in (("Settings", (12, 4, 78, 21)), ("Battle Screen", (12, 1, 69, 12)),
                          ("Overwrite save in this slot.", (2, 12, 158, 24))):
            with self.subTest(text=text):
                image = Image.new("RGBA", (200, 40))
                draw_text_in_box(image, box, text, 14, min_size=6)
                bounds = image.getbbox()
                self.assertIsNotNone(bounds)
                self.assertGreaterEqual(bounds[0], box[0])
                self.assertGreaterEqual(bounds[1], box[1])
                self.assertLessEqual(bounds[2], box[2])
                self.assertLessEqual(bounds[3], box[3])

    def test_unfittable_text_fails_without_clipping_or_writing(self):
        image = Image.new("RGBA", (40, 20))
        with self.assertRaisesRegex(ValueError, "Text does not fit"):
            draw_text_in_box(image, (1, 1, 4, 4), "Too long", 12)
        self.assertIsNone(image.getbbox())
        for box in ((-1, 0, 10, 10), (0, 0, 41, 10), (10, 10, 10, 20)):
            with self.assertRaisesRegex(ValueError, "Invalid text box"):
                draw_text_in_box(image, box, "A", 12)


ORIGINALS = ROOT / "work/p4_textures_orig"


@unittest.skipUnless(ORIGINALS.is_dir(), "Local game texture fixtures unavailable")
class MenuTextureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        localize_systemzip(ORIGINALS, cls.output)
        localize_graphic_menus(ORIGINALS, cls.output)
        localize_res_and_etc(ORIGINALS, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_inactive_tabs_remove_old_letter_fragments(self):
        rel = "GAMEINIT/SystemZip/sys_o_files05.zip.png"
        original = np.array(Image.open(ORIGINALS / rel).convert("RGBA"))
        localized = np.array(Image.open(self.output / rel).convert("RGBA"))
        # These margins are outside the English labels, but contained Japanese ink.
        for x0, x1 in ((77, 82), (192, 196)):
            with self.subTest(margin=(x0, x1)):
                expected = np.repeat(original[4:11, 15:16], x1 - x0, axis=1)
                np.testing.assert_array_equal(localized[4:11, x0:x1], expected)

    def test_options_decimal_point_uses_digit_baseline(self):
        rel = "GAMEINIT/SystemZip/sys_o_files01.zip.png"
        localized = np.array(Image.open(self.output / rel).convert("RGBA"))
        bottoms = []
        for x0, y0 in ((424, 1), (440, 1), (456, 49)):
            cell = localized[y0:y0 + 16, x0:x0 + 16]
            ink = (cell[:, :, :3] > 180).all(axis=2) & (cell[:, :, 3] >= 200)
            bottoms.append(np.where(ink)[0].max())
        self.assertEqual(len(set(bottoms)), 1, bottoms)

    def test_trophy_bubble_keeps_rounded_corner(self):
        rel = "GRAPHIC/AdvGraphic/hetr_pack01.zip.png"
        original = np.array(Image.open(ORIGINALS / rel).convert("RGBA"))
        localized = np.array(Image.open(self.output / rel).convert("RGBA"))
        # The text edit must not flatten the bubble's top-right border.
        np.testing.assert_array_equal(localized[62:66, 218:224], original[62:66, 218:224])

    def test_active_sound_tab_removes_japanese_edges(self):
        rel = "GAMEINIT/SystemZip/sys_o_files05_b.zip.png"
        localized = np.array(Image.open(self.output / rel).convert("RGBA"))
        np.testing.assert_array_equal(localized[4:11, 237:241], np.full((7, 4, 4), 255, dtype=np.uint8))

    def test_inactive_tab_shapes_are_preserved(self):
        rel = "GAMEINIT/SystemZip/sys_o_files05.zip.png"
        original = Image.open(ORIGINALS / rel).convert("RGBA")
        localized = Image.open(self.output / rel).convert("RGBA")
        for point in ((12, 4), (13, 4), (350, 4), (354, 4), (356, 4)):
            self.assertEqual(localized.getpixel(point), original.getpixel(point), point)

    def test_total_attack_badges_do_not_erase_score_digits(self):
        rel = "BATTLE/etc/btl_total_vs_files01.zip.png"
        original = np.array(Image.open(ORIGINALS / rel).convert("RGBA"))
        localized = np.array(Image.open(self.output / rel).convert("RGBA"))
        np.testing.assert_array_equal(localized[:226], original[:226])

    def test_controls_headers_fit_game_uv_windows(self):
        rel = "GRAPHIC/AdvGraphic/sys_sousa_02.zip.png"
        localized = np.array(Image.open(self.output / rel).convert("RGBA"))
        for x0, x1, region0, region1 in ((8, 107, 0, 176), (205, 262, 176, 352), (377, 442, 352, 512)):
            with self.subTest(header=(x0, x1)):
                self.assertFalse(localized[:13, region0:x0, 3].any())
                self.assertFalse(localized[:13, x1:region1, 3].any())
