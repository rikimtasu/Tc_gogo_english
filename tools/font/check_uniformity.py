"""Check actual atlas glyphs against the active Barlow presets and render a preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from .build_font import (DEFAULT_TTF, crilayla, decode_tim2_4bpp, font_specs,
                             load_font, parse_w_abc, render_outlined_glyph)
except ImportError:
    from build_font import (DEFAULT_TTF, crilayla, decode_tim2_4bpp, font_specs,
                            load_font, parse_w_abc, render_outlined_glyph)


def check_uniformity(font_root: Path, ttf: Path = DEFAULT_TTF) -> tuple[dict, Image.Image]:
    report = {}
    preview = Image.new("RGBA", (480, 272), (30, 48, 66, 255))
    draw = ImageDraw.Draw(preview)
    preview_y = 8
    samples = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz 0123456789",
               "I'll explain whatever you pick!", "Wide W, narrow i; g j p q y descend.")
    for name, spec in font_specs(tight_dialogue=True).items():
        root = font_root / "font" / name
        _, lookup, records = parse_w_abc(crilayla.decompress((root / "abc.w_abc").read_bytes()))
        sheets = [decode_tim2_4bpp(crilayla.decompress((root / s).read_bytes())) for s in spec["sheets"]]
        font = load_font(ttf, spec["ttf_size"])
        glyphs = {}
        bottoms = {}
        advances = {}
        for code in range(32, 127):
            char = chr(code)
            x0, y0, x1, y1, a, b, c, _, sheet = records[lookup[code]]
            pixels, width, _, _, palette = sheets[sheet]
            actual = bytes(v for y in range(y0, y1) for v in pixels[y * width + x0:y * width + x1])
            if code == 32:
                expected = Image.new("L", (4, spec["cell_h"]), 14)
                bearings = (0, spec["space_w"], 0)
            else:
                expected, ea, eb, ec = render_outlined_glyph(
                    font, char, spec["cell_h"], spec["threshold"], spec["y_offset"],
                    width_scale=spec.get("width_scale", 1.0), tight_spacing=spec.get("tight_spacing", False),
                    antialias=True, baseline_row=spec["baseline_row"],
                )
                bearings = (ea, eb, ec)
                ink_rows = [i // (x1 - x0) for i, value in enumerate(actual) if value not in (13, 14)]
                bottoms[char] = max(ink_rows)
            if expected.size != (x1 - x0, y1 - y0) or expected.tobytes() != actual or bearings != (a, b, c):
                raise ValueError(f"{name}: glyph {char!r} differs from active Barlow preset")
            rgba = bytes(channel for index in actual for channel in palette[index * 4:index * 4 + 4])
            glyphs[char] = Image.frombytes("RGBA", expected.size, rgba)
            advances[char] = a + b + c
        baseline_chars = "ABCDEFGHIJKLMNOPRSTUVWXYZ0123456789abcdefhiklmnorstuvwxz"
        baseline_rows = sorted({bottoms[ch] for ch in baseline_chars})
        # Q's tail and g/j/p/q/y descenders intentionally extend below the baseline.
        if name == "sulakyapi12" and baseline_rows != [spec["baseline_row"]]:
            raise ValueError(f"Dialogue baseline is not uniform: {baseline_rows}")
        report[name] = {"matched_ascii_glyphs": 95, "cell_height": spec["cell_h"],
                        "baseline_rows": baseline_rows, "word_space": advances[" "],
                        "advance_range": [min(advances.values()), max(advances.values())],
                        "descender_rows": {ch: bottoms[ch] for ch in "Qgjpqy"}}
        draw.text((8, preview_y), name, fill="white")
        preview_y += 14
        for text in samples[:2] if name != "sulakyapi12" else samples:
            x = 8
            for char in text:
                preview.alpha_composite(glyphs[char], (x, preview_y))
                x += advances[char]
            preview_y += spec["cell_h"] + 2
        preview_y += 5
    return report, preview


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", type=Path, required=True)
    parser.add_argument("--ttf", type=Path, default=DEFAULT_TTF)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report, preview = check_uniformity(args.fonts, args.ttf)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "uniformity.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    preview.save(args.out / "dialogue_preview.png")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
