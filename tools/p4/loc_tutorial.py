"""Localize BATTLE/tutorial textures (titles, subtitles, pages, and callout overlays)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from render_helpers import (
    clear_box,
    draw_gradient_outlined_text,
    draw_outlined_text,
    fit_font,
    load_font,
)

SUBTITLES = [
    "~Basic Combat~",
    "~Unison Attack~",
    "~Rumble Attack~",
    "~Assist~",
    "~Beware Extra Attacks~",
    "~Attack with EX Attacks!~",
    "~EX Attacks Cont.~",
    "~Macaron's EX Attack~",
]

# Each entry: filename -> list of (x0, y0, x1, y1, text, anchor)
TU_SAM_CALLOUTS: dict[str, list[tuple[int, int, int, int, str, str]]] = {
    "tu_sam01_01.zip.png": [
        (92, 16, 175, 32, "HP Gauge", "lm"),
        (165, 146, 248, 162, "HP Gauge", "rm"),
    ],
    "tu_sam01_02.zip.png": [
        (120, 16, 205, 32, "STUN Gauge", "rm"),
        (12, 146, 98, 162, "STUN Gauge", "lm"),
    ],
    "tu_sam01_03.zip.png": [
        (78, 16, 162, 32, "EX Gauge", "lm"),
        (152, 146, 232, 162, "EX Gauge", "rm"),
    ],
    "tu_sam01_04.zip.png": [
        (18, 16, 110, 32, "Timeline", "lm"),
    ],
    "tu_sam01_05.zip.png": [
        (10, 74, 68, 90, "Symbol", "mm"),
        (120, 82, 180, 98, "Symbol", "lm"),
        (104, 110, 164, 126, "Symbol", "lm"),
    ],
    "tu_sam01_06.zip.png": [
        (36, 86, 126, 102, "ACT Point", "lm"),
    ],
    "tu_sam01_07.zip.png": [
        (220, 68, 272, 84, "Element", "lm"),
    ],
    "tu_sam01_08.zip.png": [
        (180, 132, 240, 148, "Attack", "mm"),
    ],
    "tu_sam01_09.zip.png": [
        (210, 126, 282, 142, "Target", "mm"),
    ],
    "tu_sam01_10.zip.png": [
        (206, 132, 266, 148, "Chant", "mm"),
    ],
    "tu_sam01_11.zip.png": [
        (204, 104, 288, 120, "Attack LV", "mm"),
    ],
    "tu_sam02_01.zip.png": [
        (206, 132, 266, 148, "Chant", "mm"),
    ],
    "tu_sam02_02.zip.png": [
        (168, 110, 234, 126, "Unison", "rm"),
    ],
    "tu_sam02_03.zip.png": [
        (36, 86, 126, 102, "Unison Area", "lm"),
    ],
    "tu_sam02_04.zip.png": [
        (145, 22, 245, 38, "Elemental Affinity", "rm"),
    ],
    "tu_sam02_05.zip.png": [
        (34, 116, 98, 132, "Symbol", "lm"),
    ],
    "tu_sam03_01.zip.png": [
        (36, 86, 126, 102, "ACT Point", "lm"),
    ],
    "tu_sam03_02.zip.png": [
        (160, 126, 255, 142, "Select Leader", "mm"),
    ],
    "tu_sam05_01.zip.png": [
        (106, 16, 188, 32, "EX Gauge", "lm"),
        (124, 146, 204, 162, "EX Gauge", "rm"),
    ],
    "tu_sam06_02.zip.png": [
        (96, 20, 178, 36, "EX Gauge", "lm"),
        (80, 144, 162, 160, "EX Gauge", "lm"),
    ],
    "tu_sam07_01.zip.png": [
        (160, 82, 248, 98, "Barrier Area", "rm"),
    ],
    "tu_sam_plus01_01.zip.png": [
        (132, 82, 198, 98, "Symbol", "lm"),
    ],
    "tu_sam_plus01_02.zip.png": [
        (208, 62, 276, 78, "Target", "mm"),
    ],
}


def localize_tutorial(orig_dir: Path, out_dir: Path) -> int:
    src_root = orig_dir / "BATTLE/tutorial"
    dst_root = out_dir / "BATTLE/tutorial"
    dst_root.mkdir(parents=True, exist_ok=True)
    count = 0

    # 1. tu_title01.zip & tu_title02.zip (480x96)
    for fn, top_txt in (
        ("tu_title01.zip.png", "Ria-senpai's"),
        ("tu_title02.zip.png", "Ria-senpai & Paqy's"),
    ):
        im = Image.open(src_root / fn).convert("RGBA")
        # Clear top-left speaker prefix (x=0..240, y=0..28) on blue bar
        clear_box(im, (10, 4, 240, 26), fill=(25, 65, 175, 255))
        draw_outlined_text(im, (14, 15), top_txt, load_font(15), (255, 255, 255, 255), (10, 30, 95, 255), 1, anchor="lm")
        # Clear main Japanese title band (x=45..435, y=28..76) on blue bar
        clear_box(im, (45, 28, 435, 76), fill=(25, 65, 175, 255))
        draw_gradient_outlined_text(
            im,
            (240, 52),
            "Tutorial Corner!",
            load_font(38),
            (255, 220, 245),
            (255, 110, 190),
            (255, 255, 255, 255),
            2,
            anchor="mm",
        )
        im.save(dst_root / fn)
        count += 1

    # 2. tu_subtitle_files01.zip (352x216) & tu_subtitle_files01c.zip (288x32)
    im = Image.open(src_root / "tu_subtitle_files01.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, im.width, im.height))
    for idx, txt in enumerate(SUBTITLES):
        y = idx * 27 + 13
        f = fit_font(draw, txt, im.width - 16, 17, 11)
        draw_outlined_text(im, (im.width // 2, y), txt, f, (255, 255, 255, 255), (15, 55, 130, 255), 2, anchor="mm")
    im.save(dst_root / "tu_subtitle_files01.zip.png")
    count += 1

    im_c = Image.open(src_root / "tu_subtitle_files01c.zip.png").convert("RGBA")
    clear_box(im_c, (0, 0, im_c.width, im_c.height))
    draw_outlined_text(im_c, (im_c.width // 2, 16), "~Rumble Attack~", load_font(17), (255, 255, 255, 255), (15, 55, 130, 255), 2, anchor="mm")
    im_c.save(dst_root / "tu_subtitle_files01c.zip.png")
    count += 1

    # 3. tu_page01, 04, 05, 06 (256x200)
    # tu_page01: top-left header
    im = Image.open(src_root / "tu_page01.zip.png").convert("RGBA")
    clear_box(im, (8, 8, 128, 28), fill=(15, 105, 195, 255))
    draw_outlined_text(im, (12, 18), "Elemental Affinity", load_font(13), (255, 255, 255, 255), (10, 40, 95, 255), 1, anchor="lm")
    im.save(dst_root / "tu_page01.zip.png")
    count += 1

    page_specs = [
        ("tu_page04.zip.png", "Follow-up Attacks", "On top of your normal attack...", "Unison Attack!!"),
        ("tu_page05.zip.png", "Big Damage", "The more allies in a Unison...", "Huge Damage!!"),
        ("tu_page06.zip.png", "About Chanting", "Chant together to...", "Power Up!!"),
    ]
    for fn, hdr, sub, big in page_specs:
        im = Image.open(src_root / fn).convert("RGBA")
        draw = ImageDraw.Draw(im)
        clear_box(im, (8, 8, 150, 28), fill=(15, 105, 195, 255))
        draw_outlined_text(im, (12, 18), hdr, load_font(13), (255, 255, 255, 255), (10, 40, 95, 255), 1, anchor="lm")
        clear_box(im, (12, 146, 240, 190), fill=(35, 155, 225, 255))
        f_sub = fit_font(draw, sub, 220, 12, 9)
        draw_outlined_text(im, (16, 156), sub, f_sub, (255, 255, 255, 255), (10, 50, 110, 255), 1, anchor="lm")
        f_big = fit_font(draw, big, 220, 24, 14)
        draw_outlined_text(im, (16, 176), big, f_big, (255, 255, 255, 255), (15, 75, 160, 255), 2, anchor="lm")
        im.save(dst_root / fn)
        count += 1

    # 4. All 23 tu_sam* callout overlays
    for fn, boxes in TU_SAM_CALLOUTS.items():
        im = Image.open(src_root / fn).convert("RGBA")
        draw = ImageDraw.Draw(im)
        for x0, y0, x1, y1, txt, anchor in boxes:
            draw.rounded_rectangle([x0, y0, x1, y1], radius=4, fill=(18, 22, 36, 225), outline=(90, 140, 210, 200), width=1)
            f = fit_font(draw, txt, (x1 - x0) - 6, 12, 8)
            draw_outlined_text(
                im,
                ((x0 + x1) // 2, (y0 + y1) // 2),
                txt,
                f,
                (255, 255, 255, 255),
                (0, 0, 0, 255),
                1,
                anchor="mm",
            )
        im.save(dst_root / fn)
        count += 1

    print(f"Localized tutorial: {count} textures")
    return count


if __name__ == "__main__":
    localize_tutorial(Path("work/p4_textures_orig"), Path("work/p4_textures_en"))
