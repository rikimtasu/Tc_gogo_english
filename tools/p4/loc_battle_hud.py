"""Localize BATTLE/res, BATTLE/etc, and BATTLE root HUD sheets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from render_helpers import (
    clear_box,
    draw_gradient_outlined_text,
    draw_outlined_text,
    draw_text_in_box,
    fit_font,
    load_font,
)

BTARGET_LEFT = [
    "Jangara", "Rokkaku", "Sally", "Ippuu", "Kal Kan",
    "Carat", "Arden", "Dot", "Melilot", "Soltia",
    "Macaron", "Nagahama", "Nanaka", "Komen", "Tinun",
    "Mon Petit", "Chao", "Pasta", "Melilot", "Soltia",
    "Isshin", "Zetton", "Misa", "Yoshimura", "Macaron",
]

BTARGET_RIGHT = [
    "Mochimochi", "Daikichi", "Orion", "Taishou", "Sheba",
    "Friskies", "Melilot", "Soltia", "Ichiya", "Yasubee",
    "Lolotte", "Soltia", "Azel", "Bylous", "Ria",
    "Paqy", "Eauderourke", "Melilot", "Bylous", "Macaron",
    "Waltham", "Kurokan", "Hatsugai", "Synn",
]


def _sample_pill_bg(im: Image.Image, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
    """Sample median non-transparent color near the left/right inner edge of a pill."""
    arr = np.array(im)[y0:y1, x0:x1]
    ys, xs = np.where(arr[:, :, 3] > 200)
    if ys.size == 0:
        return (20, 90, 140, 255)
    # Use pixels near y-center, slightly inside x0
    mid_y = (y1 - y0) // 2
    sample_x = min(x1 - x0 - 1, 4)
    px = tuple(int(v) for v in arr[mid_y, sample_x])
    if px[3] < 200:
        px = tuple(int(v) for v in np.median(arr[ys, xs], axis=0))
    return (px[0], px[1], px[2], 255)


def localize_res_and_etc(orig_dir: Path, out_dir: Path) -> int:
    count = 0

    # 1. btl_res_title00.zip: ○ 進む -> ○ Continue
    rel = "BATTLE/res/btl_res_title00.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    clear_box(im, (216, 200, 310, 222))
    f = load_font(14)
    draw_outlined_text(im, (218, 210), "Continue", f, (255, 255, 255, 255), (15, 60, 120, 255), 1, anchor="lm")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 2. btl_mvp_files01.zip: EAU DE ROURKE -> EAUDEROURKE, MACAROON -> MACARON
    rel = "BATTLE/res/btl_mvp_files01.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    # Clear EAU DE ROURKE (y=120..131, x=0..108) and MACAROON (y=131..142, x=0..72)
    clear_box(im, (0, 120, 110, 131))
    clear_box(im, (0, 131, 74, 142))
    f_mvp = load_font(10)
    draw_outlined_text(im, (2, 125), "EAUDEROURKE", f_mvp, (255, 245, 160, 255), (40, 30, 10, 255), 1, anchor="lm")
    draw_outlined_text(im, (2, 136), "MACARON", f_mvp, (255, 245, 160, 255), (40, 30, 10, 255), 1, anchor="lm")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 3. btl_total_vs_files01.zip: badges start AFTER the 4/9 digit row.
    rel = "BATTLE/etc/btl_total_vs_files01.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    badge_specs = [
        (0, 0, (255, 120, 40)),
        (0, 1, (40, 150, 255)),
        (0, 2, (235, 190, 20)),
        (1, 0, (40, 195, 70)),
        (1, 1, (195, 60, 225)),
        (1, 2, (255, 90, 60)),
        (2, 0, (40, 150, 255)),
        (2, 1, (235, 190, 20)),
        (2, 2, (40, 195, 70)),
        (3, 0, (195, 60, 225)),
    ]
    # Three 134px cells per row, each 29px tall; preserve the 24px icons.
    for r, c, stroke_rgb in badge_specs:
        x0 = c * 134 + 24
        y0 = 226 + r * 29
        box = (x0, y0, (c + 1) * 134 - 2, y0 + 29)
        clear_box(im, box)
        draw_text_in_box(im, box, "TOTAL ATK LV", 15,
                         (255, 255, 255, 255), (*stroke_rgb, 255), 2)
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 4. btl_btarget_name.zip: 2 columns x 14px rows
    rel = "BATTLE/etc/btl_btarget_name.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    draw = ImageDraw.Draw(im)
    for col_idx, names in enumerate((BTARGET_LEFT, BTARGET_RIGHT)):
        x0 = col_idx * 72
        for r_idx, name in enumerate(names):
            y0 = r_idx * 14
            # Sample dominant bright border color from original row before clearing
            sub = np.array(im)[y0 : y0 + 14, x0 : x0 + 72]
            opaque = sub[sub[:, :, 3] > 200]
            stroke_col = (180, 40, 120, 255)
            if opaque.size > 0:
                # Pick a saturated pixel if available
                med = np.median(opaque[:, :3], axis=0).astype(int)
                stroke_col = (int(med[0]), int(med[1]), int(med[2]), 255)
            clear_box(im, (x0, y0, x0 + 72, y0 + 14))
            f_bt = fit_font(draw, name, max_w=68, start_size=12, min_size=8)
            draw_outlined_text(
                im,
                (x0 + 36, y0 + 7),
                name,
                f_bt,
                (255, 255, 255, 255),
                stroke_col,
                1,
                anchor="mm",
            )
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1
    return count


def localize_battle_hud(orig_dir: Path, out_dir: Path) -> int:
    count = 0

    # 1. btl_files02.tm2 (384x432)
    rel = "BATTLE/btl_files02.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    draw = ImageDraw.Draw(im)
    # Top-left 6 character names (below their small English title, ~30px per slot)
    top_names = [
        (0, 11, 108, 30, "SYNN", (150, 35, 200, 255)),
        (0, 41, 108, 60, "SYNN", (150, 35, 200, 255)),
        (0, 71, 108, 90, "NANAKA", (210, 35, 90, 255)),
        (0, 101, 108, 120, "LOLOTTE", (15, 130, 210, 255)),
        (0, 131, 108, 150, "MISA", (210, 145, 10, 255)),
        (0, 161, 108, 180, "RIA", (25, 175, 45, 255)),
    ]
    for x0, y0, x1, y1, txt, st in top_names:
        clear_box(im, (x0, y0, x1, y1))
        f = fit_font(draw, txt, x1 - x0 - 4, 17, 10)
        draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, (255, 255, 255, 255), st, 2, anchor="mm")

    # Bottom character names (y=366..432)
    bot_names = [
        (114, 366, 206, 392, "EAUDEROURKE", (170, 30, 190, 255)),
        (0, 398, 92, 430, "MACARON", (170, 30, 190, 255)),
        (92, 398, 184, 430, "BYLOUS", (170, 30, 190, 255)),
        (246, 398, 314, 430, "SALLY", (190, 35, 130, 255)),
        (314, 398, 384, 430, "MELILOT", (135, 35, 200, 255)),
    ]
    for x0, y0, x1, y1, txt, st in bot_names:
        clear_box(im, (x0, y0, x1, y1))
        f = fit_font(draw, txt, x1 - x0 - 4, 19, 10)
        draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, (255, 255, 255, 255), st, 2, anchor="mm")

    # Action pills (keep pill background, replace top JP text inside pill)
    pill_edits = [
        (8, 190, 82, 216, "UNISON", (20, 135, 90, 255)),
        (96, 190, 168, 216, "HEALING", (25, 120, 155, 255)),
        (8, 232, 82, 258, "RUMBLE", (120, 35, 35, 255)),
        (96, 232, 168, 258, "POWER UP", (165, 65, 45, 255)),
        (8, 274, 82, 300, "CHANT", (135, 35, 65, 255)),
        (96, 274, 168, 300, "BARRIER DMG", (135, 35, 65, 255)),
    ]
    for x0, y0, x1, y1, txt, bg in pill_edits:
        clear_box(im, (x0, y0, x1, y1), fill=bg)
        f = fit_font(draw, txt, x1 - x0 - 4, 15, 9)
        draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, (255, 255, 255, 255), (20, 20, 30, 255), 1, anchor="mm")

    # バリア (top right) & 場外 (x2)
    clear_box(im, (336, 114, 376, 134), fill=(175, 45, 75, 255))
    draw_outlined_text(im, (356, 124), "BARRIER", load_font(10), (255, 255, 255, 255), (90, 15, 30, 255), 1, anchor="mm")
    for y0 in (142, 162):
        clear_box(im, (186, y0, 214, y0 + 16))
        draw_outlined_text(im, (200, y0 + 8), "OUT", load_font(10), (255, 255, 255, 255), (160, 20, 20, 255), 1, anchor="mm")

    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 2. btl_files03.tm2 (256x200): Command buttons (Attack, Chant, Unison, Confirm)
    rel = "BATTLE/btl_files03.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    draw = ImageDraw.Draw(im)
    # Row 0 (y=1..31): x=(25,63) Attack, (65,103) Chant, (105,143) Unison, (193,248) Attack
    # Row 1 (y=33..63): x=(1,56) Attack, (57,112) Chant, (113,172) Confirm, (198,253) Chant
    # Row 2 (y=65..95): x=(1,39) Attack, (41,79) Chant, (81,119) Unison, (121,180) Confirm, (182,220) Unison
    btns = [
        (29, 7, 59, 25, "Attack"),
        (69, 7, 99, 25, "Chant"),
        (109, 7, 139, 25, "Unison"),
        (199, 7, 242, 25, "Attack"),
        (7, 39, 50, 57, "Attack"),
        (63, 39, 106, 57, "Chant"),
        (119, 39, 166, 57, "Confirm"),
        (204, 39, 247, 57, "Chant"),
        (5, 71, 35, 89, "Attack"),
        (45, 71, 75, 89, "Chant"),
        (85, 71, 115, 89, "Unison"),
        (127, 71, 174, 89, "Confirm"),
        (186, 71, 216, 89, "Unison"),
    ]
    for x0, y0, x1, y1, txt in btns:
        bg = _sample_pill_bg(im, x0, y0, x1, y1)
        clear_box(im, (x0, y0, x1, y1), fill=bg)
        f = fit_font(draw, txt, x1 - x0 - 2, 13, 8)
        draw_outlined_text(im, ((x0 + x1) // 2, (y0 + y1) // 2), txt, f, (255, 255, 255, 255), (10, 35, 75, 255), 1, anchor="mm")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 3. btl_filesE2_1.tm2 (240x232): 6 badges (80x48 each) + 合計 (y=194..218)
    rel = "BATTLE/btl_filesE2_1.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    badge_bg = [
        (0, 0, (195, 65, 25, 255)),
        (1, 0, (25, 115, 195, 255)),
        (2, 0, (185, 140, 20, 255)),
        (0, 1, (35, 155, 65, 255)),
        (1, 1, (155, 45, 175, 255)),
        (2, 1, (155, 75, 55, 255)),
    ]
    f_atk = load_font(12)
    for col, row, bg in badge_bg:
        x0, y0 = col * 80 + 18, row * 48 + 25
        clear_box(im, (x0, y0, col * 80 + 76, row * 48 + 44), fill=bg)
        draw_outlined_text(im, (x0 + 28, y0 + 9), "ATK LV", f_atk, (255, 255, 255, 255), (15, 15, 25, 255), 1, anchor="mm")
    # 合計 x 5 (x=0..180, y=194..216)
    f_tot = load_font(11)
    for i in range(5):
        tx0 = i * 36
        clear_box(im, (tx0, 194, tx0 + 36, 214))
        draw_outlined_text(im, (tx0 + 18, 204), "TOTAL", f_tot, (255, 255, 255, 255), (20, 20, 30, 255), 1, anchor="mm")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 4. btl_filesE2_2.tm2 (160x160): alpha mask for TOTAL ATK LV
    rel = "BATTLE/btl_filesE2_2.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    f_mask = load_font(11)
    for y_base in (26, 106):
        clear_box(im, (4, y_base, 78, y_base + 22), fill=(0, 0, 0, 255))
        draw_outlined_text(im, (41, y_base + 11), "TOTAL ATK LV", f_mask, (255, 255, 255, 255), (0, 0, 0, 255), 0, anchor="mm")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 5. btl_filesE3.tm2 (224x288): 4 prompt banners
    rel = "BATTLE/btl_filesE3.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    draw = ImageDraw.Draw(im)
    prompts = [
        (0, 20, "Select an action."),
        (52, 72, "Select a target."),
        (104, 124, "Select a Unison Leader."),
        (124, 144, "Select a Rumble Leader."),
    ]
    for y0, y1, txt in prompts:
        clear_box(im, (14, y0 + 2, im.width - 14, y1 - 2), fill=(45, 145, 215, 255))
        f = fit_font(draw, txt, im.width - 34, 13, 9)
        draw_outlined_text(im, (im.width // 2, (y0 + y1) // 2), txt, f, (255, 255, 255, 255), (10, 45, 100, 255), 1, anchor="mm")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1
    return count


def run_all(orig_dir: Path, out_dir: Path) -> None:
    c1 = localize_res_and_etc(orig_dir, out_dir)
    c2 = localize_battle_hud(orig_dir, out_dir)
    print(f"Localized: res/etc={c1}, battle_hud={c2} (total={c1+c2})")


if __name__ == "__main__":
    run_all(Path("work/p4_textures_orig"), Path("work/p4_textures_en"))
