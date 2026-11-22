"""Localize GRAPHIC.CPK/AdvGraphic menu textures (Title Screen, Data Install, Controls, Trophies, Gallery, Free Battle)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from render_helpers import (
    clear_box,
    draw_gradient_outlined_text,
    draw_outlined_text,
    draw_text_in_box,
    fill_vertical_gradient_from_col,
    fit_font,
    inpaint_vertical_dither,
    load_font,
)

WHITE = (255, 255, 255, 255)
UI_BLUE_STROKE = (24, 120, 232, 255)
UI_DARK_STROKE = (55, 62, 74, 255)


def localize_graphic_menus(orig_dir: Path, out_dir: Path) -> int:
    src_root = orig_dir / "GRAPHIC/AdvGraphic"
    dst_root = out_dir / "GRAPHIC/AdvGraphic"
    dst_root.mkdir(parents=True, exist_ok=True)
    count = 0

    # 1. sys_ti_files01.zip (256x208): Title Screen Menu
    im = Image.open(src_root / "sys_ti_files01.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    BLUE_STROKE = (20, 130, 238, 255)
    GRAY_STROKE = (115, 118, 125, 255)
    SEL_STROKE = (238, 72, 178, 255)

    ti_items = [
        (2, 2, 122, 22, "New Game", BLUE_STROKE, 15),
        (130, 2, 250, 22, "Continue", BLUE_STROKE, 15),
        (24, 26, 100, 46, "Album", BLUE_STROKE, 15),
        (130, 26, 250, 46, "Helena's Room", BLUE_STROKE, 14),
        (20, 50, 104, 70, "Options", BLUE_STROKE, 15),
        (130, 50, 250, 70, "Continue", GRAY_STROKE, 15),
        (24, 74, 100, 94, "Album", GRAY_STROKE, 15),
        (130, 74, 250, 94, "Helena's Room", GRAY_STROKE, 14),
        (1, 97, 123, 119, "New Game", SEL_STROKE, 16),
        (130, 97, 251, 119, "Continue", SEL_STROKE, 16),
        (24, 121, 100, 143, "Album", SEL_STROKE, 16),
        (130, 121, 250, 143, "Helena's Room", SEL_STROKE, 15),
        (20, 145, 104, 167, "Options", SEL_STROKE, 16),
        (130, 145, 250, 167, "Data Install", GRAY_STROKE, 15),
        (2, 185, 122, 208, "Data Install", BLUE_STROKE, 15),
        (130, 185, 250, 208, "Data Install", SEL_STROKE, 16),
    ]
    for x0, y0, x1, y1, txt, st, sz in ti_items:
        clear_box(im, (x0, y0, x1, y1))
        f = fit_font(draw, txt, (x1 - x0) - 6, sz, 10)
        fg = (230, 232, 236, 255) if st == GRAY_STROKE else WHITE
        draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, fg, st, 1.65, anchor="mm")
    im.save(dst_root / "sys_ti_files01.zip.png")
    count += 1

    # 2. sys_media_base.zip (480x272): Data Install background banner (vertical dither-preserving inpaint!)
    im = Image.open(src_root / "sys_media_base.zip.png").convert("RGBA")
    inpaint_vertical_dither(im, (14, 10, 220, 44))
    draw_outlined_text(im, (22, 27), "DATA INSTALL", load_font(22), WHITE, UI_BLUE_STROKE, 1.85, anchor="lm")
    im.save(dst_root / "sys_media_base.zip.png")
    count += 1

    # 3. sys_media_files01.zip (448x48): Yes/No pills + [O]Next [X]Stop [X]Back
    im = Image.open(src_root / "sys_media_files01.zip.png").convert("RGBA")
    for x0, x1, txt, st in (
        (19, 79, "Yes", (18, 90, 185, 255)),
        (124, 184, "No", (18, 90, 185, 255)),
        (186, 246, "Yes", (15, 125, 195, 255)),
        (248, 308, "No", (15, 125, 195, 255)),
    ):
        fill_vertical_gradient_from_col(im, (x0 + 6, 26, x1 - 6, 43), sample_x=x0 + 6)
        draw_outlined_text(im, ((x0 + x1) // 2, 34), txt, load_font(11), WHITE, st, 1.15, anchor="mm")
    for x0, x1, txt in ((327, 353, "Next"), (373, 396, "Stop"), (415, 438, "Back")):
        clear_box(im, (x0, 24, x1, 45))
        draw_outlined_text(im, ((x0 + x1) // 2, 34), txt, load_font(10), WHITE, UI_DARK_STROKE, 1.25, anchor="mm")
    im.save(dst_root / "sys_media_files01.zip.png")
    count += 1

    # 4. sys_media_files02.zip (384x472): Data Install main text & prompts!
    im = Image.open(src_root / "sys_media_files02.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, im.width, im.height))
    # Header y=1..22 (x=7..262, center 135)
    draw_outlined_text(im, (135, 11), "<About Data Install>", load_font(15), (16, 108, 232, 255), WHITE, 1.1, anchor="mm")
    m2_rows = [
        # Block 1: y=29..117 (center 135, max_w 260)
        (37, 135, 256, "By saving part of the game data to"),
        (55, 135, 256, "storage media as <<Install Data>> and"),
        (73, 135, 256, "loading from both Install Data and UMD,"),
        (91, 135, 256, "you can use the <<Data Install>> feature"),
        (109, 135, 256, "to shorten loading times."),
        # Block 2: y=119..153 (center 177, max_w 216)
        (127, 177, 216, "At least 98MB of free space is required"),
        (145, 177, 216, "to save Install Data."),
        # Block 3: y=173..243 (center 177, max_w 350)
        (181, 177, 348, "*Requires storage media of 128MB or larger;"),
        (199, 177, 348, "smaller media lacks sufficient free space."),
        (217, 177, 352, "*At least 576KB of extra free space is needed"),
        (235, 177, 348, "to save system data and a save file."),
        # Prompt 1: y=245..261 (center 130)
        (253, 130, 240, "Save Install Data?"),
        # Block 4: y=309..361 (center 130, max_w 256)
        (317, 130, 256, "*Saving takes about 1 minute."),
        (335, 130, 256, "*We recommend charging the battery fully"),
        (353, 130, 256, "or using the AC adaptor before saving."),
        # Prompt 2: y=363..379 (center 118)
        (371, 118, 232, "Save settings to system data?"),
        # Block 5: y=381..451 (center 134, max_w 250)
        (389, 134, 248, "While Install Data is loading,"),
        (407, 134, 248, "the Memory Stick access LED"),
        (425, 134, 248, "will blink. During this time,"),
        (443, 134, 248, "do not remove the Memory Stick."),
        # Prompt 3: y=453..469 (center 132)
        (461, 132, 260, "Saving Install Data was canceled."),
    ]
    for cy, cx, mw, txt in m2_rows:
        f = fit_font(draw, txt, mw, 11, 8)
        draw_outlined_text(im, (cx, cy), txt, f, (16, 108, 232, 255), WHITE, 0.9, anchor="mm")
    im.save(dst_root / "sys_media_files02.zip.png")
    count += 1

    # 5. sys_media_files03.zip (352x328): Data Install follow-up screens & prompts!
    im = Image.open(src_root / "sys_media_files03.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, im.width, im.height))
    m3_rows = [
        # Block 1: y=1..53 (center 166, max_w 290)
        (9, 166, 288, "To use the Data Install feature,"),
        (27, 166, 288, "System Data and Install Data must be"),
        (45, 166, 288, "saved on the same storage media."),
        # Block 2: y=73..107 (center 166, max_w 290)
        (81, 166, 288, "*You can also copy System Data later onto"),
        (99, 166, 288, "storage media that has Install Data."),
        # Block 3: y=127..179 (center 154, max_w 280)
        (135, 154, 276, "To enable the Data Install feature,"),
        (153, 154, 276, "set <<Data Install>> in Options"),
        (171, 154, 276, "to <<ON>>."),
        # Line y=199..215 (center 154, max_w 296)
        (207, 154, 296, "Data Install has been set to <<ON>>."),
        # Left column y=217..287 (center 69, max_w 130)
        (225, 69, 120, "Saving..."),
        (261, 69, 132, "Do not remove the"),
        (279, 69, 132, "Memory Stick."),
        # Right column y=217..287 (center 244, max_w 210)
        (225, 244, 208, "At least 98MB is required"),
        (243, 244, 208, "to save Install Data."),
        (261, 244, 208, "Delete other data to"),
        (279, 244, 208, "free up space?"),
        # Bottom y=289..323 (center 113, max_w 220)
        (297, 113, 220, "Install Data already exists."),
        (315, 113, 220, "Overwrite it?"),
    ]
    for cy, cx, mw, txt in m3_rows:
        f = fit_font(draw, txt, mw, 11, 8)
        draw_outlined_text(im, (cx, cy), txt, f, (16, 108, 232, 255), WHITE, 0.9, anchor="mm")
    im.save(dst_root / "sys_media_files03.zip.png")
    count += 1

    # 6. sys_memory_files01.zip (512x96): Options -> Data Install sub-panel
    im = Image.open(src_root / "sys_memory_files01.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, 178, 25))
    draw_outlined_text(im, (88, 12), "Data Install", load_font(17), WHITE, UI_BLUE_STROKE, 1.65, anchor="mm")
    clear_box(im, (0, 26, 178, 50))
    draw_outlined_text(im, (88, 38), "Data Install", load_font(17), (16, 108, 232, 255), WHITE, 0.8, anchor="mm")
    clear_box(im, (178, 0, 512, 55))
    ORANGE = (242, 138, 12, 255)
    draw_outlined_text(im, (344, 9), "- Notice -", load_font(12), ORANGE, WHITE, 0.7, anchor="mm")
    draw_outlined_text(im, (344, 28), "First install data from Data Install", load_font(12), ORANGE, WHITE, 0.7, anchor="mm")
    draw_outlined_text(im, (344, 46), "on the Title Screen.", load_font(12), ORANGE, WHITE, 0.7, anchor="mm")
    clear_box(im, (0, 56, 512, 74))
    draw_outlined_text(
        im,
        (256, 65),
        "Loads from both UMD and storage to reduce load times.",
        load_font(12),
        (16, 108, 232, 255),
        WHITE,
        0.75,
        anchor="mm",
    )
    clear_box(im, (293, 74, 319, 93))
    draw_outlined_text(im, (306, 83), "Back", load_font(10), WHITE, UI_DARK_STROKE, 1.3, anchor="mm")
    im.save(dst_root / "sys_memory_files01.zip.png")
    count += 1

    # 7, 8, 9. sys_gc_base.zip, sys_gm_base.zip, sys_gs_base.zip (480x272): Gallery bottom bars
    for fn in ("sys_gc_base.zip.png", "sys_gm_base.zip.png", "sys_gs_base.zip.png"):
        im = Image.open(src_root / fn).convert("RGBA")
        fill_vertical_gradient_from_col(im, (160, 252, 262, 268), sample_x=135)
        draw_outlined_text(im, (162, 260), "Switch Gallery", load_font(11), WHITE, UI_DARK_STROKE, 1.3, anchor="lm")
        fill_vertical_gradient_from_col(im, (310, 252, 355, 268), sample_x=365)
        draw_outlined_text(im, (312, 260), "Back", load_font(11), WHITE, UI_DARK_STROKE, 1.3, anchor="lm")
        im.save(dst_root / fn)
        count += 1

    # 10 & 11. sys_hrbs_base1.zip (Free Battle) & sys_hrbs_base2.zip (Tutorial Select) (480x272)
    orig_hb1 = Image.open(src_root / "sys_hrbs_base1.zip.png").convert("RGBA")
    orig_hb2 = Image.open(src_root / "sys_hrbs_base2.zip.png").convert("RGBA")

    # sys_hrbs_base1.zip:
    im = orig_hb1.copy()
    # Top-right 'Select a stage!': vertical dither-preserving inpaint (zero horizontal streaks!)
    inpaint_vertical_dither(im, (334, 9, 473, 34))
    draw_outlined_text(im, (403, 21), "Select a stage!", load_font(14), WHITE, UI_BLUE_STROKE, 1.35, anchor="mm")
    # Wreath '最高評価' (x=326..383, y=168..185): copy clean gray panel directly from orig_hb2!
    im.paste(orig_hb2.crop((326, 168, 383, 185)), (326, 168))
    draw_outlined_text(im, (354, 176), "Best Rank", load_font(10), (95, 58, 22, 255), (255, 245, 220, 255), 0.9, anchor="mm")
    # Bottom bar (y=253..272): copy clean background from orig_hb2 where available + vertical inpaint!
    im.paste(orig_hb2.crop((98, 253, 215, 272)), (98, 253))
    inpaint_vertical_dither(im, (252, 253, 315, 271))
    im.paste(orig_hb2.crop((353, 253, 392, 272)), (353, 253))
    draw_outlined_text(im, (101, 262), "Reset High Scores", load_font(11), WHITE, UI_DARK_STROKE, 1.3, anchor="lm")
    draw_outlined_text(im, (255, 262), "Difficulty", load_font(11), WHITE, UI_DARK_STROKE, 1.3, anchor="lm")
    draw_outlined_text(im, (356, 262), "Back", load_font(11), WHITE, UI_DARK_STROKE, 1.3, anchor="lm")
    im.save(dst_root / "sys_hrbs_base1.zip.png")
    count += 1

    # sys_hrbs_base2.zip:
    im = orig_hb2.copy()
    # Top-right 'Select a tutorial!': copy clean 276..334 from orig_hb1, vertical inpaint 265..276 and 334..473!
    inpaint_vertical_dither(im, (265, 9, 276, 34))
    im.paste(orig_hb1.crop((276, 9, 334, 34)), (276, 9))
    inpaint_vertical_dither(im, (334, 9, 473, 34))
    draw_outlined_text(im, (369, 21), "Select a tutorial!", load_font(14), WHITE, UI_BLUE_STROKE, 1.35, anchor="mm")
    # Bottom bar 'Back' (x=238..275, y=253..272): inpaint vertically all the way to y=271!
    inpaint_vertical_dither(im, (238, 253, 276, 271))
    draw_outlined_text(im, (240, 262), "Back", load_font(11), WHITE, UI_DARK_STROKE, 1.3, anchor="lm")
    im.save(dst_root / "sys_hrbs_base2.zip.png")
    count += 1

    # 12. sys_sousa.zip (464x272): Controls Screen Diagram & Left Table Column
    im = Image.open(src_root / "sys_sousa.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (22, 6, 114, 34))
    draw_outlined_text(im, (68, 20), "Controls", load_font(18), WHITE, UI_BLUE_STROKE, 1.75, anchor="mm")
    PILL_BLUE = (24, 118, 240, 255)
    pills = [
        (134, 12, 191, 24, "L Button"),
        (284, 12, 341, 24, "R Button"),
        (52, 43, 110, 54, "D-Pad"),
        (23, 64, 111, 75, "Analog Stick"),
        (23, 85, 111, 96, "PS Button"),
        (21, 106, 114, 118, "SELECT"),
        (368, 19, 425, 30, "Square"),
        (368, 40, 425, 51, "Triangle"),
        (368, 61, 425, 72, "Circle"),
        (368, 82, 425, 93, "Cross"),
        (365, 103, 456, 115, "START"),
    ]
    for x0, y0, x1, y1, txt in pills:
        clear_box(im, (x0, y0, x1, y1), fill=PILL_BLUE)
        f = fit_font(draw, txt, (x1 - x0) - 4, 10, 8)
        draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, WHITE, PILL_BLUE, 0, anchor="mm")

    tbl_left = [
        "Circle",
        "Cross",
        "Square",
        "Triangle",
        "L Button",
        "R Button",
        "D-Pad",
        "START",
        "SELECT",
        "PS Button",
    ]
    for idx, txt in enumerate(tbl_left):
        y0 = 144 + idx * 11
        clear_box(im, (58, y0, 178, y0 + 10), fill=PILL_BLUE)
        draw_outlined_text(im, (118, y0 + 5), txt, load_font(9), WHITE, PILL_BLUE, 0, anchor="mm")

    clear_box(im, (237, 254, 266, 271))
    draw_outlined_text(im, (251, 262), "Back", load_font(10), WHITE, UI_DARK_STROKE, 1.3, anchor="mm")
    im.save(dst_root / "sys_sousa.zip.png")
    count += 1

    # 13. sys_sousa_02.zip (512x128): Controls Screen 3-Tab Table Text
    im = Image.open(src_root / "sys_sousa_02.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, im.width, im.height))
    # Row 0 (y=1..12): Exact UV window for each header is [8..107], [205..262], [377..442]!
    for x0, x1, hdr in ((8, 107, "Adventure Screen"), (205, 262, "Battle Screen"), (377, 442, "Menu Screen")):
        draw_text_in_box(im, (x0, 1, x1, 12), hdr, 10, WHITE, (20, 20, 25, 255), 0.75, min_size=6)

    cols_data = [
        (8, [
            "Advance",
            "Show / Hide Text Window",
            "Replay Voice",
            "Auto Mode",
            "Show Backlog",
            "Force Skip Messages",
            "",
            "Show Menu Window",
            "Message Skip",
            "Quit Game Screen",
        ]),
        (184, [
            "Confirm",
            "Back / Cancel",
            "",
            "Hide Status",
            "Alt. D-Pad Left / Up",
            "Alt. D-Pad Right / Down",
            "Select Target / Action",
            "Show Menu Window",
            "",
            "Quit Game Screen",
        ]),
        (360, [
            "Confirm / Advance",
            "Back / Cancel",
            "",
            "",
            "Previous Tab",
            "Next Tab",
            "",
            "Show Menu Window",
            "",
            "Quit Game Screen",
        ]),
    ]
    BLACK = (15, 18, 24, 255)
    for x0, rows in cols_data:
        for idx, txt in enumerate(rows):
            if not txt:
                continue
            y = 13 + idx * 11 + 5
            f = fit_font(draw, txt, 146, 9, 8)
            draw_outlined_text(im, (x0, y), txt, f, BLACK, BLACK, 0, anchor="lm")
    im.save(dst_root / "sys_sousa_02.zip.png")
    count += 1

    # 14. hetr_pack01.zip (384x232): Trophy Gallery UI
    im = Image.open(src_root / "hetr_pack01.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    # Left star ends at x=24, right star starts at x=295 -> clear (25, 0, 295, 35) completely!
    clear_box(im, (25, 0, 295, 35))
    draw_gradient_outlined_text(
        im,
        (160, 17),
        "Collect Trophies!",
        load_font(23),
        (255, 255, 255),
        (110, 200, 255),
        (235, 195, 20, 255),
        2.0,
        anchor="mm",
    )
    # Only the flat interior is repeatable; x>=218 includes the rounded border.
    fill_vertical_gradient_from_col(im, (14, 62, 216, 86), sample_x=12)
    draw_text_in_box(im, (14, 62, 216, 86), "I'll explain whatever you pick!", 13,
                     WHITE, (15, 70, 155, 255), 1.25)
    clear_box(im, (296, 54, 336, 72))
    draw_outlined_text(im, (316, 63), "Lovely!", load_font(10), WHITE, UI_BLUE_STROKE, 1.35, anchor="mm")
    clear_box(im, (353, 76, 380, 95))
    draw_outlined_text(im, (366, 85), "Back", load_font(10), WHITE, UI_DARK_STROKE, 1.3, anchor="mm")
    im.save(dst_root / "hetr_pack01.zip.png")
    count += 1

    print(f"Localized GRAPHIC menus: {count} textures")
    return count


if __name__ == "__main__":
    localize_graphic_menus(Path("work/p4_textures_orig"), Path("work/p4_textures_en"))
