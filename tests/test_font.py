import unittest
from pathlib import Path

from PIL import Image
from tools.font.build_font import (FONT_SPECS, render_outlined_glyph, font_specs, condense_ink,
                                   DEFAULT_TTF, DEFAULT_FONT_AXES, load_font, resolve_font_axes,
                                   antialias_clut, font_license_files)


TTF = DEFAULT_TTF


@unittest.skipUnless(TTF.is_file(), 'Barlow Semi Condensed font unavailable')
class FontTests(unittest.TestCase):
    def test_every_printable_glyph_has_unclipped_ink(self):
        for name, spec in FONT_SPECS.items():
            font = load_font(TTF, spec['ttf_size'])
            for code in range(33, 127):
                with self.subTest(font=name, glyph=chr(code)):
                    img, a, b, c = render_outlined_glyph(font, chr(code), spec['cell_h'], spec['threshold'], spec['y_offset'])
                    pixels = img.load()
                    self.assertTrue(any(pixels[x, y] == 15 for y in range(img.height) for x in range(img.width)))
                    self.assertTrue(all(pixels[x, y] != 15 for y in (0, img.height - 1) for x in range(img.width)))
                    self.assertTrue(all(pixels[x, y] != 15 for x in (0, img.width - 1) for y in range(img.height)))
                    self.assertGreater(a + b + c, 0)

    def test_smaller_dialogue_font_preserves_layout_and_other_presets(self):
        specs = font_specs(dialogue_size=13)
        self.assertEqual(specs['sulakyapi12']['ttf_size'], 13)
        self.assertEqual(specs['sulakyapi12']['cell_h'], 19)
        self.assertEqual(specs['sulakyapi12']['space_w'], 4)
        self.assertEqual(specs['sulakyapi12']['y_offset'], 1)
        for name in ('sulakyapi8', 'sulakyapi18'):
            self.assertEqual(specs[name], FONT_SPECS[name])
        self.assertEqual(FONT_SPECS['sulakyapi12']['ttf_size'], 14)

    def test_selected_font_build(self):
        self.assertEqual(list(font_specs(['sulakyapi12'], 13)), ['sulakyapi12'])

    def test_invalid_sizes_and_selections_rejected(self):
        for size in (0, 9, 17):
            with self.assertRaises(ValueError):
                font_specs(dialogue_size=size)
        for names in ([], ['unknown']):
            with self.assertRaises(ValueError):
                font_specs(names)

    def test_smaller_dialogue_glyphs_are_complete_and_take_less_space(self):
        spec = font_specs(dialogue_size=13)['sulakyapi12']
        old = FONT_SPECS['sulakyapi12']
        small = load_font(TTF, 13)
        large = load_font(TTF, old['ttf_size'])
        smaller_total = larger_total = 0
        for code in range(33, 127):
            with self.subTest(glyph=chr(code)):
                img, a, b, c = render_outlined_glyph(small, chr(code), spec['cell_h'], spec['threshold'], spec['y_offset'])
                pixels = img.load()
                self.assertTrue(any(pixels[x, y] == 15 for y in range(img.height) for x in range(img.width)))
                self.assertTrue(all(pixels[x, y] != 15 for y in (0, img.height - 1) for x in range(img.width)))
                smaller_total += a + b + c
                _, a, b, c = render_outlined_glyph(large, chr(code), old['cell_h'], old['threshold'], old['y_offset'])
                larger_total += a + b + c
        self.assertLess(smaller_total, larger_total)

    def test_tight_preset_changes_only_dialogue(self):
        normal = font_specs(dialogue_size=13)
        tight = font_specs(dialogue_size=13, tight_dialogue=True)
        self.assertEqual(tight['sulakyapi12']['width_scale'], 1.0)
        self.assertEqual(tight['sulakyapi12']['space_w'], 3)
        self.assertEqual(tight['sulakyapi12']['cell_h'], 19)
        self.assertEqual(tight['sulakyapi12']['y_offset'], normal['sulakyapi12']['y_offset'])
        for name in ('sulakyapi8', 'sulakyapi18'):
            self.assertEqual(tight[name], normal[name])

    def test_condensing_preserves_single_pixel_strokes(self):
        ink = Image.new('L', (8, 3), 0)
        for y, x in enumerate((1, 3, 6)):
            ink.putpixel((x, y), 255)
        narrow = condense_ink(ink, 0.75)
        self.assertEqual(narrow.size, (6, 3))
        for y in range(3):
            self.assertEqual(sum(narrow.getpixel((x, y)) == 255 for x in range(6)), 1)

    def test_invalid_width_scales_rejected(self):
        for scale in (0, -0.5, 1.1):
            with self.assertRaises(ValueError):
                condense_ink(Image.new('L', (3, 3)), scale)

    def test_tight_glyphs_preserve_height_and_separate_ink(self):
        spec = font_specs(dialogue_size=13)['sulakyapi12']
        font = load_font(TTF, 13)
        normal_total = tight_total = 0
        def ink_bounds(img):
            coords = [(x, y) for y in range(img.height) for x in range(img.width) if img.getpixel((x, y)) == 15]
            return min(x for x, y in coords), min(y for x, y in coords), max(x for x, y in coords), max(y for x, y in coords)
        for code in range(33, 127):
            with self.subTest(glyph=chr(code)):
                normal, a, b, c = render_outlined_glyph(font, chr(code), 19, spec['threshold'], spec['y_offset'])
                normal_total += a + b + c
                tight, a, b, c = render_outlined_glyph(font, chr(code), 19, spec['threshold'], spec['y_offset'], width_scale=0.75, tight_spacing=True)
                tight_total += a + b + c
                nb, tb = ink_bounds(normal), ink_bounds(tight)
                self.assertEqual(nb[1::2], tb[1::2])
                ink_width = tb[2] - tb[0] + 1
                self.assertGreaterEqual(a + b + c - ink_width, 1)
                self.assertEqual(a + b + c, max(3, ink_width + 1))
                self.assertGreaterEqual(c, -1)
        self.assertLess(tight_total, normal_total)

    def test_inrond_axes_use_actual_font_order_and_validate_values(self):
        self.assertEqual(resolve_font_axes(TTF), {})
        inrond = Path('Inrond-1.0/fonts/variable/Inrond[ROND,opsz,wght].ttf')
        if inrond.is_file():
            self.assertEqual(list(resolve_font_axes(inrond)), ['opsz', 'wght', 'ROND'])
            for axes in ({'wght': 1000}, {'ROND': -1}, {'opsz': 1}, {'wdth': 90}):
                with self.assertRaises(ValueError):
                    resolve_font_axes(inrond, axes)

    def test_nested_font_package_license(self):
        files = font_license_files(TTF)
        self.assertEqual(files[0], Path('BarlowSemiCondensed/OFL.txt').resolve())
        self.assertIn('SIL OPEN FONT LICENSE', files[0].read_text(encoding='utf-8'))

    def test_antialias_palette_preserves_every_original_used_color(self):
        original = bytes([0, 0, 0, 255] * 13 + [0, 0, 0, 255, 255, 255, 255, 0, 255, 255, 255, 255])
        palette = antialias_clut(original, {13, 14, 15})
        self.assertEqual(palette[13 * 4:], original[13 * 4:])
        self.assertEqual(len(palette), 64)
        shades = [palette[i * 4] for i in range(13)]
        self.assertEqual(shades, sorted(set(shades)))
        with self.assertRaises(ValueError):
            antialias_clut(original, {0, 13, 14, 15})

    def test_antialias_glyphs_have_complete_ink_and_outline_at_all_sizes(self):
        total_shades = set()
        for name, spec in font_specs(tight_dialogue=True).items():
            font = load_font(TTF, spec['ttf_size'])
            for code in range(33, 127):
                with self.subTest(font=name, glyph=chr(code)):
                    img, a, b, c = render_outlined_glyph(font, chr(code), spec['cell_h'], spec['threshold'], spec['y_offset'],
                        width_scale=spec.get('width_scale', 1.0), tight_spacing=spec.get('tight_spacing', False),
                        antialias=True, font_axes=DEFAULT_FONT_AXES or None, baseline_row=spec.get('baseline_row'))
                    indices = {img.getpixel((x, y)) for y in range(img.height) for x in range(img.width)}
                    self.assertIn(15, indices)
                    self.assertIn(13, indices)
                    self.assertGreater(a + b + c, 0)
                    self.assertTrue(all(img.getpixel((x, y)) in (13, 14) for y in (0, img.height - 1) for x in range(img.width)))
                    self.assertTrue(all(img.getpixel((x, y)) in (13, 14) for x in (0, img.width - 1) for y in range(img.height)))
                    total_shades.update(indices & set(range(13)))
        self.assertGreater(len(total_shades), 5)

    def test_width_override_retains_tight_spacing(self):
        self.assertEqual(font_specs(tight_dialogue=True, dialogue_width_scale=1.0)['sulakyapi12']['width_scale'], 1.0)
        for scale in (0, -1, 1.1):
            with self.assertRaises(ValueError):
                font_specs(dialogue_width_scale=scale)

    def test_inrond_antialias_keeps_letter_counters_open(self):
        font = load_font(TTF, 14)
        for ch, expected in (('O', 1), ('o', 1), ('0', 1), ('8', 2), ('B', 2), ('R', 1)):
            with self.subTest(glyph=ch):
                img, _, _, _ = render_outlined_glyph(font, ch, 19, 115, 1,
                    width_scale=1.0, tight_spacing=True, antialias=True, baseline_row=11)
                ink = {(x, y) for y in range(img.height) for x in range(img.width)
                       if img.getpixel((x, y)) not in (13, 14)}
                free = {(x, y) for y in range(img.height) for x in range(img.width)} - ink
                def component(seed, remaining):
                    found, stack = set(), [seed]
                    while stack:
                        point = stack.pop()
                        if point not in remaining or point in found:
                            continue
                        found.add(point)
                        x, y = point
                        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
                    return found
                holes = free - component((0, 0), free)
                count = 0
                while holes:
                    holes -= component(next(iter(holes)), holes)
                    count += 1
                self.assertEqual(count, expected)

    def test_antialiased_capital_i_has_symmetric_serifs(self):
        for name, spec in font_specs(tight_dialogue=True).items():
            with self.subTest(font=name):
                font = load_font(TTF, spec['ttf_size'])
                img_i, _, _, _ = render_outlined_glyph(
                    font, 'I', spec['cell_h'], spec['threshold'], spec['y_offset'],
                    width_scale=spec.get('width_scale', 1.0), tight_spacing=spec.get('tight_spacing', False),
                    antialias=True, font_axes=DEFAULT_FONT_AXES or None,
                    ink_lift=spec.get('ink_lift', 0), baseline_row=spec.get('baseline_row'),
                )
                img_l, _, _, _ = render_outlined_glyph(
                    font, 'l', spec['cell_h'], spec['threshold'], spec['y_offset'],
                    width_scale=spec.get('width_scale', 1.0), tight_spacing=spec.get('tight_spacing', False),
                    antialias=True, font_axes=DEFAULT_FONT_AXES or None,
                    ink_lift=spec.get('ink_lift', 0), baseline_row=spec.get('baseline_row'),
                )
                self.assertGreater(img_i.width, img_l.width)
                indices = {img_i.getpixel((x, y)) for y in range(img_i.height) for x in range(img_i.width)}
                self.assertIn(15, indices)
                self.assertIn(13, indices)
                for y in range(img_i.height):
                    for x in range(img_i.width):
                        self.assertEqual(img_i.getpixel((x, y)), img_i.getpixel((img_i.width - 1 - x, y)))

    def test_dialogue_baseline_is_uniform_and_uses_upper_aa_shades(self):
        spec = font_specs(tight_dialogue=True)['sulakyapi12']
        font = load_font(TTF, spec['ttf_size'])
        for ch in ('H', 'a', 'e', 'f', 'i', 'h', 'l', 't'):
            with self.subTest(glyph=ch):
                img, _, _, _ = render_outlined_glyph(
                    font, ch, spec['cell_h'], spec['threshold'], spec['y_offset'],
                    width_scale=spec['width_scale'], tight_spacing=spec['tight_spacing'],
                    antialias=True, baseline_row=spec['baseline_row'],
                )
                ink_ys = [y for y in range(img.height) for x in range(img.width) if img.getpixel((x, y)) not in (13, 14)]
                self.assertEqual(max(ink_ys), spec['baseline_row'])
        used_shades = set()
        for code in range(33, 127):
            img, _, _, _ = render_outlined_glyph(
                font, chr(code), spec['cell_h'], spec['threshold'], spec['y_offset'],
                width_scale=spec['width_scale'], tight_spacing=spec['tight_spacing'],
                antialias=True, baseline_row=spec['baseline_row'],
            )
            used_shades.update(img.getpixel((x, y)) for y in range(img.height) for x in range(img.width))
        self.assertTrue(used_shades & set(range(7, 13)))
