"""Localize GAMEINIT.CPK/SystemZip UI textures with 4x-supersampled uniform game-style typography."""

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
    load_font,
)

# Uniform bright azure outline matching the original game's '0%', '100%', '50%', 'BGM' glyphs.
UI_BLUE_STROKE = (24, 120, 232, 255)
UI_DARK_STROKE = (55, 62, 74, 255)
WHITE = (255, 255, 255, 255)


def localize_systemzip(orig_dir: Path, out_dir: Path) -> int:
    src_root = orig_dir / "GAMEINIT/SystemZip"
    dst_root = out_dir / "GAMEINIT/SystemZip"
    dst_root.mkdir(parents=True, exist_ok=True)
    count = 0

    # 1. sys_o_files01.zip (480x312): Options menu labels
    im = Image.open(src_root / "sys_o_files01.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    col1_labels = [
        (1, 18, "Text Speed"),
        (19, 36, "Auto-Play Delay"),
        (38, 56, "Wait After Voice"),
        (58, 76, "Window Opacity"),
        (78, 96, "Event Window Opacity"),
        (98, 116, "Auto After Choices"),
        (120, 138, "Resume Skip"),
        (139, 156, "Message Skip"),
    ]
    for y0, y1, txt in col1_labels:
        clear_box(im, (0, y0, 146, y1))
        draw_text_in_box(im, (3, y0, 143, y1), txt, 12, WHITE, UI_BLUE_STROKE, 1.35, align="left")

    # Sliders: KEEP x=25..190 untouched!
    clear_box(im, (0, 160, 25, 178))
    draw_outlined_text(im, (12, 169), "Slow", fit_font(draw, "Slow", 23, 10, 8), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")
    clear_box(im, (191, 160, 217, 178))
    draw_outlined_text(im, (204, 169), "Fast", fit_font(draw, "Fast", 24, 10, 8), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")

    clear_box(im, (0, 180, 25, 198))
    draw_outlined_text(im, (12, 189), "Short", fit_font(draw, "Short", 23, 9, 7), WHITE, UI_BLUE_STROKE, 1.2, anchor="mm")
    clear_box(im, (191, 180, 217, 198))
    draw_outlined_text(im, (202, 189), "Long", fit_font(draw, "Long", 22, 9, 7), WHITE, UI_BLUE_STROKE, 1.2, anchor="mm")

    # Auto-Play Delay unit: static 's' sits at (262, 187) right below '%' at (262, 169),
    # and '(/char)' sits cleanly below at y=195..208.
    clear_box(im, (218, 180, 278, 208))
    draw_outlined_text(im, (262, 187), "s", load_font(12), WHITE, UI_BLUE_STROKE, 1.3, anchor="mm")
    draw_outlined_text(im, (248, 201), "(/char)", load_font(9), WHITE, UI_BLUE_STROKE, 1.2, anchor="mm")

    # Standalone '%' icons on slider rows (uniform with rest of UI)
    for px, py in ((262, 169), (262, 228), (262, 248), (245, 272)):
        clear_box(im, (px - 8, py - 8, px + 8, py + 8))
        draw_outlined_text(im, (px, py), "%", load_font(12), WHITE, UI_BLUE_STROKE, 1.35, anchor="mm")

    # Redraw 0%, 100%, Min, Max, Slow, High on bottom slider rows (keep arrows & bars untouched!)
    for y0, y1 in ((218, 238), (238, 258)):
        ym = (y0 + y1) // 2
        clear_box(im, (0, y0, 24, y1))
        draw_outlined_text(im, (12, ym), "0%", load_font(10), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")
        clear_box(im, (191, y0, 225, y1))
        draw_outlined_text(im, (207, ym), "100%", load_font(10), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")
    clear_box(im, (0, 262, 23, 282))
    draw_outlined_text(im, (11, 272), "Min", fit_font(draw, "Min", 21, 10, 8), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")
    clear_box(im, (179, 262, 207, 282))
    draw_outlined_text(im, (192, 272), "Max", fit_font(draw, "Max", 24, 10, 8), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")
    clear_box(im, (0, 286, 29, 306))
    draw_outlined_text(im, (14, 296), "Slow", fit_font(draw, "Slow", 26, 10, 8), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")
    clear_box(im, (197, 286, 226, 306))
    draw_outlined_text(im, (210, 296), "High", fit_font(draw, "High", 26, 10, 8), WHITE, UI_BLUE_STROKE, 1.25, anchor="mm")

    # Col 2 (x=144..296) — include BGM so every label is 100% uniform!
    col2_labels = [
        (1, 18, "Volume"),
        (19, 36, "BGM"),
        (36, 55, "Character Voice"),
        (58, 74, "SFX"),
        (78, 94, "System Voice"),
        (98, 115, "Movie"),
        (133, 152, "BGM During Voice"),
    ]
    for y0, y1, txt in col2_labels:
        clear_box(im, (144, y0, 296, y1))
        draw_text_in_box(im, (148, y0, 294, y1), txt, 12, WHITE, UI_BLUE_STROKE, 1.35, align="left")

    # Col 3 (x=300..422)
    col3_labels = [
        (1, 18, "Voice on Advance"),
        (21, 48, "Character Voices"),
        (102, 118, "System Voice Type"),
        (121, 137, "Difficulty"),
        (149, 165, "Battle Voices"),
        (179, 195, "Battle Speed"),
    ]
    for y0, y1, txt in col3_labels:
        clear_box(im, (300, y0, 422, y1))
        draw_text_in_box(im, (302, y0, 420, min(y1, y0 + 18)), txt, 12, WHITE, UI_BLUE_STROKE, 1.35, align="left")

    # Redraw the 3x5 digit & unit grid at each glyph's exact original UV box!
    # Note: '.' in the original sheet is at x=466..472, y=57..63 (cx=469), NOT cx=464!
    digit_cells = [
        ("0", 424, 1, 437, 17), ("1", 440, 1, 453, 17), ("2", 456, 1, 469, 17),
        ("3", 424, 17, 437, 33), ("4", 440, 17, 453, 33), ("5", 456, 17, 469, 33),
        ("6", 424, 33, 437, 49), ("7", 440, 33, 453, 49), ("8", 456, 33, 469, 49),
        ("9", 424, 49, 437, 65), ("%", 440, 49, 456, 65), (".", 465, 49, 473, 65),
        ("s", 424, 65, 440, 81),
    ]
    clear_box(im, (424, 0, 476, 84))
    for ch, x0, y0, x1, y1 in digit_cells:
        draw_text_in_box(im, (x0, y0, x1, y1), ch, 12, WHITE,
                         UI_BLUE_STROKE, 1.25, baseline=y0 + 12)

    # Page headers in Col 3 (x=304..)
    clear_box(im, (304, 200, 390, 222))
    draw_outlined_text(im, (306, 211), "Text Settings", fit_font(draw, "Text Settings", 82, 12, 9), WHITE, UI_BLUE_STROKE, 1.35, anchor="lm")
    clear_box(im, (392, 200, 470, 222))
    draw_outlined_text(im, (394, 211), "Battle Settings", fit_font(draw, "Battle Settings", 74, 12, 9), WHITE, UI_BLUE_STROKE, 1.35, anchor="lm")
    clear_box(im, (304, 222, 476, 246))
    draw_outlined_text(im, (306, 234), "Sound 1 / Volume", load_font(13), WHITE, UI_BLUE_STROKE, 1.35, anchor="lm")
    clear_box(im, (304, 246, 456, 270))
    draw_outlined_text(im, (306, 258), "Sound 2 / Voice", load_font(13), WHITE, UI_BLUE_STROKE, 1.35, anchor="lm")
    clear_box(im, (304, 270, 405, 306))
    draw_gradient_outlined_text(
        im, (306, 288), "OPTIONS", load_font(20), (255, 255, 255), (210, 238, 255), UI_BLUE_STROKE, 1.85, anchor="lm"
    )
    im.save(dst_root / "sys_o_files01.zip.png")
    count += 1

    # 2 & 3. sys_o_files02.zip (unselected) & sys_o_files03.zip (selected) (224x232)
    pill_rows: list[tuple[int, list[tuple[int, int, str]]]] = [
        (0, [(4, 97, "On"), (104, 197, "EASY")]),
        (1, [(4, 97, "Off"), (104, 197, "NORMAL")]),
        (2, [(4, 97, "Read Only"), (104, 197, "HARD")]),
        (3, [(4, 97, "All Text"), (126, 199, "Stop Now")]),
        (4, [(4, 58, "Nanaka"), (65, 119, "Sacchin"), (126, 199, "Fade Out")]),
        (5, [(4, 58, "Lolotte"), (65, 119, "Misasagi"), (126, 199, "Next Line")]),
        (6, [(4, 58, "Misa"), (65, 119, "Amyrina"), (126, 199, "Keep")]),
        (7, [(4, 58, "Ria"), (65, 119, "Melilot"), (126, 195, "Synn")]),
        (8, [(4, 58, "Azel"), (65, 119, "Macaron"), (126, 195, "Male")]),
        (9, [(4, 58, "Sally"), (65, 119, "Other F"), (126, 195, "Female")]),
        (10, [(4, 58, "Shio"), (65, 119, "Other M"), (126, 195, "Other")]),
        (11, [(4, 58, "Helena"), (65, 119, "Other"), (126, 180, "Synn")]),
        (12, [(4, 58, "Paqy"), (65, 119, "Generic"), (126, 180, "Male")]),
        (13, [(4, 58, "Riesling"), (65, 119, "Other"), (126, 180, "Female")]),
    ]
    for fn, st_col in (("sys_o_files02.zip.png", (18, 90, 185, 255)), ("sys_o_files03.zip.png", (15, 125, 195, 255))):
        im = Image.open(src_root / fn).convert("RGBA")
        # Extract clean 12px vertical pill gradient once from row 0 empty left margin (x=10, y=2..14)
        import numpy as np
        clean_col = np.array(im)[2:14, 10:11, :].copy()
        draw = ImageDraw.Draw(im)
        for r, cells in pill_rows:
            y0, y1 = r * 16, (r + 1) * 16
            for x0, x1, txt in cells:
                w_box = (x1 - 2) - (x0 + 1)
                patch = np.repeat(clean_col, w_box, axis=1)
                im.paste(Image.fromarray(patch, mode="RGBA"), (x0 + 1, y0 + 2))
                draw_text_in_box(im, (x0 + 3, y0 + 2, x1 - 3, y1 - 2), txt, 10, WHITE, st_col, 1.1)
        im.save(dst_root / fn)
        count += 1

    # 4. sys_o_files05.zip (384x24): 4 inactive tabs of 90px — replicate clean tab gradient from x=15!
    tabs = ["Text", "Sound 1", "Sound 2", "Battle"]
    im = Image.open(src_root / "sys_o_files05.zip.png").convert("RGBA")
    import numpy as np
    tab_col = np.array(im)[4:21, 15:16, :].copy()
    # Exact text interiors differ at the two end caps; do not flatten them.
    tab_interiors = [(15, 85), (104, 175), (192, 265), (284, 344)]
    for idx, txt in enumerate(tabs):
        x0 = 2 + idx * 90
        x1 = x0 + 90
        # The Japanese outlines extend beyond the former 12px inner margins.
        left, right = tab_interiors[idx]
        im.paste(Image.fromarray(np.repeat(tab_col, right - left, axis=1), mode="RGBA"), (left, 4))
        draw_text_in_box(im, (x0 + 12, 4, x1 - 10, 21), txt, 11, WHITE, (95, 102, 112, 255), 1.15)
    im.save(dst_root / "sys_o_files05.zip.png")
    count += 1

    # 5. sys_o_files05_b.zip (448x24): 4 active tabs (1..108, 113..220, 225..332, 337..444)
    im = Image.open(src_root / "sys_o_files05_b.zip.png").convert("RGBA")
    for idx, txt in enumerate(tabs):
        x0 = 1 + idx * 112
        x1 = x0 + 107
        clear_box(im, (x0 + 12, 4, x1 - 12, 21), fill=WHITE)
        draw_text_in_box(im, (x0 + 12, 4, x1 - 12, 21), txt, 11, (24, 120, 232, 255), WHITE, 0)
    im.save(dst_root / "sys_o_files05_b.zip.png")
    count += 1

    # 6. sys_o_files08.zip (400x104): KEEP [L][R][Sq][X][Synn][Paqy]
    im = Image.open(src_root / "sys_o_files08.zip.png").convert("RGBA")
    clear_box(im, (69, 82, 128, 102))
    draw_outlined_text(im, (72, 92), "Reset", load_font(11), WHITE, UI_DARK_STROKE, 1.35, anchor="lm")
    clear_box(im, (149, 82, 174, 102))
    draw_outlined_text(im, (151, 92), "Back", load_font(10), WHITE, UI_DARK_STROKE, 1.3, anchor="lm")
    im.save(dst_root / "sys_o_files08.zip.png")
    count += 1

    # 7. sys_sl_files04.zip (224x112): Save/Load status messages
    im = Image.open(src_root / "sys_sl_files04.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, im.width, im.height))
    sl_msgs = [
        (8, "Loading..."),
        (22, "Do not remove the Memory Stick."),
        (36, "Saving..."),
        (50, "Do not remove the Memory Stick."),
        (64, "Deleting..."),
        (78, "Do not remove the Memory Stick."),
        (92, "This is the autosave slot."),
        (106, "You cannot save here."),
    ]
    for y, txt in sl_msgs:
        row = (y - 8) // 14
        draw_text_in_box(im, (5, row * 14, im.width - 5, (row + 1) * 14), txt, 11, WHITE, UI_BLUE_STROKE, 1.25)
    im.save(dst_root / "sys_sl_files04.zip.png")
    count += 1

    # 8 & 9. sys_sl_lbase.zip & sys_sl_sbase.zip (480x272)
    sl_specs = [
        ("sys_sl_lbase.zip.png", "LOAD", "Select a slot to load.", (38, 158, 84, 255)),
        ("sys_sl_sbase.zip.png", "SAVE", "Select a slot to save.", (210, 62, 165, 255)),
    ]
    for fn, title, prompt, stroke_c in sl_specs:
        im = Image.open(src_root / fn).convert("RGBA")
        # Seamless gradient fill for top title area (y=4..40) & bottom legend text (y=252..271)!
        fill_vertical_gradient_from_col(im, (14, 4, 352, 40), sample_x=358)
        draw_outlined_text(im, (20, 18), title, load_font(20), WHITE, stroke_c, 1.85, anchor="lm")
        draw_outlined_text(im, (118, 18), prompt, load_font(13), WHITE, stroke_c, 1.35, anchor="lm")
        # KEEP [Triangle](172..186) and [X](267..281)!
        fill_vertical_gradient_from_col(im, (188, 252, 252, 271), sample_x=160)
        draw_outlined_text(im, (192, 260), "Delete", load_font(11), WHITE, UI_DARK_STROKE, 1.35, anchor="lm")
        fill_vertical_gradient_from_col(im, (283, 252, 336, 271), sample_x=160)
        draw_outlined_text(im, (286, 260), "Back", load_font(11), WHITE, UI_DARK_STROKE, 1.35, anchor="lm")
        im.save(dst_root / fn)
        count += 1

    # 10. sys_sw.zip (384x112): KEEP y=0..53 (star bar)! Clear y=54..112 to OPAQUE WHITE!
    im = Image.open(src_root / "sys_sw.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 54, im.width, im.height), fill=WHITE)
    sw_items = [(1, 108, "Trophies"), (108, 220, "Training"), (220, 332, "Title Screen")]
    for x0, x1, txt in sw_items:
        f = fit_font(draw, txt, (x1 - x0) - 8, 14, 10)
        draw_outlined_text(im, ((x0 + x1) // 2, 63), txt, f, (20, 115, 225, 255), (165, 225, 255, 255), 1.0, anchor="mm")
    for x0, x1, txt in sw_items:
        f = fit_font(draw, txt, (x1 - x0) - 8, 14, 10)
        draw_outlined_text(im, ((x0 + x1) // 2, 82), txt, f, (255, 90, 190, 255), (130, 225, 255, 255), 1.0, anchor="mm")
    draw_outlined_text(im, (18, 101), "Yes", load_font(13), (20, 115, 225, 255), (165, 225, 255, 255), 1.0, anchor="mm")
    draw_outlined_text(im, (58, 101), "No", load_font(13), (20, 115, 225, 255), (165, 225, 255, 255), 1.0, anchor="mm")
    draw_outlined_text(im, (101, 101), "Yes", load_font(13), (255, 90, 190, 255), (130, 225, 255, 255), 1.0, anchor="mm")
    draw_outlined_text(im, (141, 101), "No", load_font(13), (255, 90, 190, 255), (130, 225, 255, 255), 1.0, anchor="mm")
    im.save(dst_root / "sys_sw.zip.png")
    count += 1

    # 11. sys_tm_files01.zip (176x56): Trophy Unlocked!
    im = Image.open(src_root / "sys_tm_files01.zip.png").convert("RGBA")
    clear_box(im, (0, 36, im.width, im.height))
    draw_outlined_text(im, (88, 46), "Trophy Unlocked!", load_font(13), WHITE, (195, 35, 55, 255), 1.5, anchor="mm")
    im.save(dst_root / "sys_tm_files01.zip.png")
    count += 1

    # 12. sys_mn_files01.zip (448x56): In-game Pause Menu
    im = Image.open(src_root / "sys_mn_files01.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, 80, 28))
    draw_outlined_text(im, (38, 14), "MENU", load_font(19), WHITE, UI_BLUE_STROKE, 1.75, anchor="mm")
    mn_items = [
        (98, 0, 152, 16, "Save", False),
        (178, 0, 264, 16, "Load", False),
        (285, 0, 345, 16, "Options", False),
        (98, 17, 152, 34, "Controls", False),
        (178, 17, 264, 34, "Title Screen", False),
        # KEEP [X] icon at 272..289!
        (290, 17, 324, 34, "Close", True),
        (325, 17, 428, 34, "Data Install", False),
    ]
    for x0, y0, x1, y1, txt, is_close in mn_items:
        clear_box(im, (x0, y0, x1, y1))
        f = fit_font(draw, txt, (x1 - x0) - 4, 12, 9)
        if is_close:
            draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, WHITE, UI_DARK_STROKE, 1.25, anchor="mm")
        else:
            draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, (20, 115, 225, 255), WHITE, 1.0, anchor="mm")
    im.save(dst_root / "sys_mn_files01.zip.png")
    count += 1

    # 13. sys_k_files01.zip (224x24): Confirm Yes/No (4 cells of 56px)
    im = Image.open(src_root / "sys_k_files01.zip.png").convert("RGBA")
    clear_box(im, (0, 0, im.width, im.height))
    k1_cells = [
        (0, 56, "Yes", (20, 115, 225, 255)),
        (56, 112, "Yes", (255, 90, 190, 255)),
        (112, 168, "No", (20, 115, 225, 255)),
        (168, 224, "No", (255, 90, 190, 255)),
    ]
    for x0, x1, txt, col in k1_cells:
        draw_outlined_text(im, ((x0 + x1) // 2, 12), txt, load_font(15), col, (145, 225, 255, 255), 1.0, anchor="mm")
    im.save(dst_root / "sys_k_files01.zip.png")
    count += 1

    # 14. sys_k_files02.zip (224x160): Confirmation prompts (13 rows x 12px)
    im = Image.open(src_root / "sys_k_files02.zip.png").convert("RGBA")
    draw = ImageDraw.Draw(im)
    clear_box(im, (0, 0, im.width, im.height))
    k2_rows = [
        (6, 104, "Is this okay?"),
        (18, 104, "Reset all HARD mode scores."),
        (30, 104, "Reset all NORMAL mode scores."),
        (42, 104, "Reset all EASY mode scores."),
        (54, 80, "Is this okay?"),
        (66, 80, "Reset all settings to defaults."),
        (78, 80, "Quit the game."),
        (90, 80, "Delete this data."),
        (102, 80, "Overwrite save in this slot."),
        (114, 80, "Return to the title screen."),
        (126, 80, "Load this save data."),
        (138, 80, "Save data to this slot."),
        (150, 80, "Start this stage."),
    ]
    for y, cx, txt in k2_rows:
        max_w = 208 if cx == 104 else 156
        draw_text_in_box(im, (cx - max_w // 2, y - 6, cx + max_w // 2, y + 6), txt, 10,
                         (20, 115, 225, 255), (165, 230, 255, 255), 0.9, min_size=6)
    im.save(dst_root / "sys_k_files02.zip.png")
    count += 1

    print(f"Localized SystemZip: {count} textures")
    return count


if __name__ == "__main__":
    localize_systemzip(Path("work/p4_textures_orig"), Path("work/p4_textures_en"))
