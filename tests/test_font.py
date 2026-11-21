import unittest
from pathlib import Path

from tools.font.build_font import (FONT_SPECS, render_outlined_glyph, font_specs,
                                   DEFAULT_TTF, DEFAULT_FONT_AXES, load_font,
                                   antialias_clut, font_license_files)


TTF = DEFAULT_TTF


@unittest.skipUnless(TTF.is_file(), 'Barlow Semi Condensed font unavailable')
class FontTests(unittest.TestCase):
    def test_barlow_dialogue_glyphs_baseline_and_serif_i(self):
        specs = font_specs(tight_dialogue=True)
        spec = specs['sulakyapi12']
        self.assertEqual((spec['width_scale'], spec['space_w'], spec['cell_h'], spec['baseline_row']),
                         (1.0, 3, 19, 11))
        font = load_font(TTF, spec['ttf_size'])

        used_shades = set()
        for ch in ('H', 'I', 'W', 'a', 'e', 'g', 'i', 'l', '!'):
            img, a, b, c = render_outlined_glyph(
                font, ch, spec['cell_h'], spec['threshold'], spec['y_offset'],
                width_scale=spec['width_scale'], tight_spacing=spec['tight_spacing'],
                antialias=True, font_axes=DEFAULT_FONT_AXES or None,
                baseline_row=spec['baseline_row'],
            )
            self.assertGreater(a + b + c, 0)
            indices = {img.getpixel((x, y)) for y in range(img.height) for x in range(img.width)}
            self.assertIn(15, indices)
            self.assertIn(13, indices)
            used_shades.update(indices)
            if ch in ('H', 'a', 'e', 'i', 'l'):
                ink_ys = [y for y in range(img.height) for x in range(img.width)
                          if img.getpixel((x, y)) not in (13, 14)]
                self.assertEqual(max(ink_ys), spec['baseline_row'])
            if ch == 'I':
                img_l, _, _, _ = render_outlined_glyph(
                    font, 'l', spec['cell_h'], spec['threshold'], spec['y_offset'],
                    width_scale=spec['width_scale'], tight_spacing=spec['tight_spacing'],
                    antialias=True, baseline_row=spec['baseline_row'],
                )
                self.assertGreater(img.width, img_l.width)
                for y in range(img.height):
                    for x in range(img.width):
                        self.assertEqual(img.getpixel((x, y)), img.getpixel((img.width - 1 - x, y)))
        self.assertTrue(used_shades & set(range(7, 13)))

        files = font_license_files(TTF)
        self.assertEqual(files[0], Path('BarlowSemiCondensed/OFL.txt').resolve())
        self.assertIn('SIL OPEN FONT LICENSE', files[0].read_text(encoding='utf-8'))

    def test_antialias_palette_and_spec_guards(self):
        original = bytes([0, 0, 0, 255] * 13 + [0, 0, 0, 255, 255, 255, 255, 0, 255, 255, 255, 255])
        palette = antialias_clut(original, {13, 14, 15})
        self.assertEqual(palette[13 * 4:], original[13 * 4:])
        self.assertEqual(len(palette), 64)
        shades = [palette[i * 4] for i in range(13)]
        self.assertEqual(shades, sorted(set(shades)))
        with self.assertRaises(ValueError):
            antialias_clut(original, {0, 13, 14, 15})
        for size in (0, 9, 17):
            with self.assertRaises(ValueError):
                font_specs(dialogue_size=size)
        for names in ([], ['unknown']):
            with self.assertRaises(ValueError):
                font_specs(names)
