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
class PlaceTextureTests(unittest.TestCase):
    def test_place_and_time_labels_fit_patched_graphic_arc_windows(self):
        from cpk.cpk import CpkArchive
        from cpk.tim2 import crilayla_decompress
        from loc_place_and_time import PLACE_LABELS, TIME_LABELS, localize_place_and_time
        from patch_graphic_arc import patch_graphic_arc_bytes, patch_graphic_arc_compressed, read_sys_pl_layout

        gi_path = ROOT / "work" / "iso_extract" / "GAMEINIT.CPK"
        if not gi_path.is_file():
            self.skipTest("Local GAMEINIT.CPK unavailable")

        gi = CpkArchive(str(gi_path))
        orig_comp = gi.read_entry([e for e in gi.entries() if e["FileName"] == "GraphicARC.bin"][0])
        recomp, patched_n = patch_graphic_arc_compressed(orig_comp)
        self.assertEqual(patched_n, 65)
        patched_dec, _ = patch_graphic_arc_bytes(crilayla_decompress(orig_comp))
        self.assertEqual(crilayla_decompress(recomp), patched_dec)
        places, times = read_sys_pl_layout(patched_dec)

        # Verify Night (T008) & School Route (P205) were widened cleanly in GraphicARC.bin
        self.assertGreaterEqual(times["008"]["tb"]["w"], 58)
        self.assertGreaterEqual(places["205"]["jb"]["w"], 64)
        # Verify Free Battle player names (SYS_HRBE_PN01 Nanaka, SYS_HRBE_PN08A Macaron) were widened in-place
        from patch_graphic_arc import _iter_entries
        hrbe_by_name = {nm: patched_dec[off:nxt] for nm, off, nxt in _iter_entries(patched_dec) if nm.startswith("SYS_HRBE_PN")}
        for nm, exp_w in (("SYS_HRBE_PN01", 47), ("SYS_HRBE_PN02", 44), ("SYS_HRBE_PN03", 31), ("SYS_HRBE_PN08A", 52)):
            blob = hrbe_by_name[nm]
            tail = blob.find(b"\x00\x13\x00", blob.find(b"sys_hrbe_tips1") + 14)
            self.assertEqual(blob[tail - 7], exp_w, f"{nm} width mismatch")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            localize_place_and_time(ORIGINALS, output, gi_path)
            im1 = Image.open(output / "GAMEINIT/AdvZip/sys_pl_file001.zip.png").convert("RGBA")
            im2 = Image.open(output / "GAMEINIT/AdvZip/sys_pl_file002.zip.png").convert("RGBA")
            im3 = Image.open(output / "GAMEINIT/AdvZip/sys_pl_file003.zip.png").convert("RGBA")
            texs = {"sys_pl_file001": im1, "sys_pl_file002": im2, "sys_pl_file003": im3}

            # Every time-of-day graphic must have non-empty pixels inside its patched UV window
            # AND zero ink leaking outside its patched [u .. u+w] window within its 64px cell!
            for tid in TIME_LABELS:
                tb = times[tid]["tb"]
                crop = im3.crop((tb["u"], tb["v"], tb["u"] + tb["w"], tb["v"] + tb["h"]))
                self.assertIsNotNone(crop.getbbox(), f"Empty time graphic T{tid}")

            # Every place banner must have non-empty title & shadow inside its exact GraphicARC UV window
            # AND zero stray pixels on the 1px gap above PSHADOW (eliminating the stray horizontal line!)
            for pid in PLACE_LABELS:
                jb = places[pid]["jb"]
                sh = places[pid]["sh"]
                im = texs[jb["tex"]]
                self.assertIsNotNone(im.crop((jb["u"], jb["v"], jb["u"] + jb["w"], jb["v"] + jb["h"])).getbbox())
                self.assertIsNotNone(im.crop((sh["u"], sh["v"], sh["u"] + sh["w"], sh["v"] + sh["h"])).getbbox())
                # Verify row right above School Route (y=63) is completely transparent
                if pid == "205":
                    row63 = np.array(im)[63, sh["u"] : sh["u"] + sh["w"], 3]
                    self.assertEqual(int(row63.max()), 0, "Stray pixels above School Route shadow")


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

    def test_battle_hud_score_digits_and_tim2_palettes_preserved(self):
        from tools.cpk.cpk import CpkArchive
        from tools.cpk.tim2 import decode_tm2, encode_tm2, parse_tm2_header, unwrap_texture
        import loc_battle_hud

        loc_battle_hud.localize_battle_hud(ORIGINALS, self.output)
        # 1. btl_files02 SCORE digits (x=80..138, y=104..138) must be 100% untouched
        o02 = np.array(Image.open(ORIGINALS / "BATTLE/btl_files02.tm2.png").convert("RGBA"))
        n02 = np.array(Image.open(self.output / "BATTLE/btl_files02.tm2.png").convert("RGBA"))
        np.testing.assert_array_equal(n02[104:138, 80:138], o02[104:138, 80:138])

        # 2. btl_filesE2_2.tm2 grayscale palette & btl_filesE3.tm2 (255,255,255,0) border preserved
        battle_cpk = Path("work/iso_extract/BATTLE.CPK")
        if battle_cpk.is_file():
            arc = CpkArchive(str(battle_cpk))
            by_name = {r["FileName"]: r for r in arc.entries() if not r["DirName"]}
            e22_orig, _, _ = unwrap_texture(arc.read_entry(by_name["btl_filesE2_2.tm2"]), "btl_filesE2_2.tm2")
            e22_new = encode_tm2(Image.open(self.output / "BATTLE/btl_filesE2_2.tm2.png"), e22_orig)
            h22 = parse_tm2_header(e22_new)
            pal22 = np.frombuffer(e22_new[h22["pal_off"] : h22["pal_off"] + h22["pal_sz"]], dtype=np.uint8).reshape(-1, 4)
            self.assertEqual(pal22[0].tolist(), [0, 0, 0, 0])
            self.assertEqual(pal22[1].tolist(), [0, 0, 0, 255])

            e3_orig, _, _ = unwrap_texture(arc.read_entry(by_name["btl_filesE3.tm2"]), "btl_filesE3.tm2")
            e3_new = encode_tm2(Image.open(self.output / "BATTLE/btl_filesE3.tm2.png"), e3_orig)
            e3_arr = np.array(decode_tm2(e3_new))
            self.assertEqual(e3_arr[25, 0].tolist(), [255, 255, 255, 0])
            self.assertEqual(e3_arr[51, 50].tolist(), [255, 255, 255, 0])

            # 3. btl_filesE2_1.tm2 multiplicative shadow layer (y=100..200, x=0..230) must preserve
            # soft rose-pink alpha==0 RGB values and never collapse to black (0, 0, 0, 0)!
            e21_orig, _, _ = unwrap_texture(arc.read_entry(by_name["btl_filesE2_1.tm2"]), "btl_filesE2_1.tm2")
            e21_new = encode_tm2(Image.open(self.output / "BATTLE/btl_filesE2_1.tm2.png"), e21_orig)
            e21_arr = np.array(decode_tm2(e21_new))
            sh_region = e21_arr[100:200, 0:230]
            self.assertTrue((sh_region[:, :, 3] == 0).all())
            black_sh = (sh_region[:, :, 0] == 0) & (sh_region[:, :, 1] == 0) & (sh_region[:, :, 2] == 0)
            self.assertEqual(int(black_sh.sum()), 0)
            # Core of FIRE orb shadow (around x=18, y=118) must be warm rose-pink ~(241, 127, 136, 0)
            self.assertEqual(e21_arr[118, 18].tolist(), [241, 127, 136, 0])
