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


def _fill_vertical_gradient(im: Image.Image, dst_box: tuple[int, int, int, int], col_rgba: np.ndarray) -> None:
    """Fill dst_box row-by-row with a 1D (H, 4) vertical RGBA gradient."""
    x0, y0, x1, y1 = dst_box
    arr = np.array(im, dtype=np.uint8)
    h = y1 - y0
    if len(col_rgba) != h:
        idx = np.linspace(0, len(col_rgba) - 1, h).round().astype(int)
        col_rgba = col_rgba[idx]
    arr[y0:y1, x0:x1] = col_rgba[:, None, :]
    im.paste(Image.fromarray(arr[y0:y1, x0:x1], mode="RGBA"), (x0, y0))


def _fill_rounded_pill_interior(
    im: Image.Image,
    pill_box: tuple[int, int, int, int],
    col_rgba: np.ndarray,
    inset_px: float = 3.2,
    alpha_thresh: int = 180,
) -> tuple[int, int, int, int]:
    """Fill ONLY the true rounded/oval interior of a pill using exact circular Euclidean erosion."""
    px0, py0, px1, py1 = pill_box
    arr = np.array(im, dtype=np.uint8)
    sub = arr[py0:py1, px0:px1].copy()
    h, w = sub.shape[:2]

    # Exact Euclidean erosion of opaque pill silhouette by radius inset_px
    inside = sub[:, :, 3] >= alpha_thresh
    r = int(np.ceil(inset_px))
    pad = np.zeros((h + 2 * r, w + 2 * r), dtype=bool)
    pad[r : r + h, r : r + w] = inside
    eroded = inside.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= inset_px * inset_px:
                shifted = pad[r + dy : r + dy + h, r + dx : r + dx + w]
                eroded &= shifted

    ys, xs = np.where(eroded)
    if ys.size == 0:
        return (px0 + 2, py0 + 2, px1 - 2, py1 - 2)
    iy0, iy1 = int(ys.min()), int(ys.max()) + 1
    ix0, ix1 = int(xs.min()), int(xs.max()) + 1
    ih = iy1 - iy0
    idx = np.linspace(0, len(col_rgba) - 1, ih).round().astype(int)
    grad_full = np.zeros((h, 4), dtype=np.uint8)
    grad_full[iy0:iy1] = col_rgba[idx]
    for y in range(iy0, iy1):
        sub[y, eroded[y]] = grad_full[y]
    im.paste(Image.fromarray(sub, mode="RGBA"), (px0, py0))
    return (px0 + ix0, py0 + iy0, px0 + ix1, py0 + iy1)


def _clear_soft_pill_top(im: Image.Image, box: tuple[int, int, int, int]) -> None:
    """Erase crisp outlined Japanese text inside a soft glowing pill while preserving the pastel glow."""
    x0, y0, x1, y1 = box
    arr = np.array(im, dtype=np.uint8)
    sub = arr[y0:y1, x0:x1].copy()
    # Sample clean glow color from the top and bottom edges of the sub-box (outside text strokes)
    top_row = sub[0:1, :, :]
    bot_row = sub[-1:, :, :]
    # Linear vertical blend between top edge and bottom edge of the halo
    h = y1 - y0
    t = np.linspace(0.0, 1.0, h)[:, None, None]
    blended = np.clip((1.0 - t) * top_row.astype(np.float32) + t * bot_row.astype(np.float32), 0, 255).astype(np.uint8)
    arr[y0:y1, x0:x1] = blended
    im.paste(Image.fromarray(arr[y0:y1, x0:x1], mode="RGBA"), (x0, y0))


_PIXEL_FONT_3X5: dict[str, tuple[str, ...]] = {
    "A": ("010", "101", "111", "101", "101"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("1", "1", "1", "1", "1"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "N": ("110", "101", "101", "101", "101"),
    "Q": ("010", "101", "101", "111", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
}


def _draw_pixel_badge(
    im: Image.Image,
    cx: int,
    cy: int,
    text: str,
    outline_rgba: tuple[int, int, int, int],
    fill_rgba: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> None:
    """Stamp crisp 3x5 pixel bitmap text with a 1px solid outline centered at (cx, cy)."""
    glyphs = [_PIXEL_FONT_3X5[ch] for ch in text]
    tw = sum(len(g[0]) for g in glyphs) + max(0, len(glyphs) - 1)
    th = 5
    mask = np.zeros((th + 2, tw + 2), dtype=bool)
    x = 1
    for g in glyphs:
        gw = len(g[0])
        for r, row in enumerate(g):
            for c, bit in enumerate(row):
                if bit == "1":
                    mask[1 + r, x + c] = True
        x += gw + 1
    # 8-neighbor dilation for crisp 1px colored outline
    outline = np.zeros_like(mask)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ys0, ys1 = max(0, -dy), mask.shape[0] - max(0, dy)
            xs0, xs1 = max(0, -dx), mask.shape[1] - max(0, dx)
            yd0, yd1 = max(0, dy), mask.shape[0] - max(0, -dy)
            xd0, xd1 = max(0, dx), mask.shape[1] - max(0, -dx)
            outline[yd0:yd1, xd0:xd1] |= mask[ys0:ys1, xs0:xs1]

    arr = np.array(im, dtype=np.uint8)
    x0 = cx - (tw + 2) // 2
    y0 = cy - (th + 2) // 2
    for dy in range(th + 2):
        for dx in range(tw + 2):
            if mask[dy, dx]:
                arr[y0 + dy, x0 + dx] = fill_rgba
            elif outline[dy, dx]:
                arr[y0 + dy, x0 + dx] = outline_rgba
    im.paste(Image.fromarray(arr, mode="RGBA"), (0, 0))


def _clean_wheel_kanji(im: Image.Image) -> None:
    """Replace the 5 single element kanji on btl_files02.tm2 wheel with crisp pixel English."""
    arr = np.array(im, dtype=np.uint8)
    # 1. 闇 (x=246..261, y=190..205): keep purple diamond orb (x<=245) 100% intact!
    arr[190:203, 246:261] = (0, 0, 0, 0)
    for y in range(203, 206):
        left_px = arr[y, 245].astype(np.float32)
        right_px = arr[y, 261].astype(np.float32)
        for i, x in enumerate(range(246, 261)):
            t = (i + 1) / 16.0
            arr[y, x] = np.clip((1 - t) * left_px + t * right_px, 0, 255).astype(np.uint8)

    # 2. 炎 (x=229..242, y=200..214): y=200..207 overlaps inner red ring; y=208..214 is clear interior
    for y in range(200, 208):
        left_px = arr[y, 228].astype(np.float32)
        right_px = arr[y, 242].astype(np.float32)
        for i, x in enumerate(range(229, 242)):
            t = (i + 1) / 14.0
            arr[y, x] = np.clip((1 - t) * left_px + t * right_px, 0, 255).astype(np.uint8)
    arr[208:215, 228:242] = (0, 0, 0, 0)

    # 3. 雷 (x=248..262, y=218..233): y=218..223 is mostly clear interior beside bolt orb; y=224..233 is ring
    arr[218:224, 249:262] = (0, 0, 0, 0)
    for y in range(224, 233):
        left_px = arr[y, 247].astype(np.float32)
        right_px = arr[y, 262].astype(np.float32)
        for i, x in enumerate(range(248, 262)):
            t = (i + 1) / 15.0
            arr[y, x] = np.clip((1 - t) * left_px + t * right_px, 0, 255).astype(np.uint8)

    # 4. 水 (x=210..223, y=217..232): y=217..223 is clear white interior; y=224..232 is cyan/blue ring
    arr[217:224, 211:223] = (0, 0, 0, 0)
    for y in range(224, 232):
        left_px = arr[y, 209].astype(np.float32)
        right_px = arr[y, 223].astype(np.float32)
        for i, x in enumerate(range(210, 223)):
            t = (i + 1) / 14.0
            arr[y, x] = np.clip((1 - t) * left_px + t * right_px, 0, 255).astype(np.uint8)

    # 5. 光 (x=216..231, y=236..249): keep green star orb intact; clear stray green pixels below ring
    for y in range(236, 239):
        left_px = arr[y, 216].astype(np.float32)
        right_px = arr[y, 231].astype(np.float32)
        for i, x in enumerate(range(217, 231)):
            t = (i + 1) / 15.0
            arr[y, x] = np.clip((1 - t) * left_px + t * right_px, 0, 255).astype(np.uint8)
    arr[239:250, 215:231] = (0, 0, 0, 0)

    im.paste(Image.fromarray(arr, mode="RGBA"), (0, 0))

    # Stamp crisp 3x5 pixel-art English labels right where the 5 kanji sat
    _draw_pixel_badge(im, 255, 197, "DARK", (205, 0, 210, 255))
    _draw_pixel_badge(im, 236, 206, "FIRE", (220, 15, 20, 255))
    _draw_pixel_badge(im, 255, 223, "THN", (225, 110, 0, 255))
    _draw_pixel_badge(im, 217, 225, "AQUA", (0, 125, 235, 255))
    _draw_pixel_badge(im, 226, 242, "LIGHT", (0, 165, 25, 255))


def _clean_orb_kanji_e21(im: Image.Image) -> None:
    """Remove the 5 element kanji on btl_filesE2_1.tm2, restore each orb cleanly, and redraw crisp English."""
    arr = np.array(im, dtype=np.uint8)

    # 1. Symmetric orbs (AQUA, LIGHT, DARK): mirror clean left half onto occluded lower-right pixels!
    # Also clear the old kanji + small text zone (x=cx+4..cx+61, y=cy..cy+15) first, then restore orb
    sym_orbs = [
        # (cx_float, y_top, y_bot, clear_x0, clear_x1)
        (95.0, 2, 33, 98, 154),   # AQUA
        (18.5, 52, 83, 21, 77),   # LIGHT
        (95.0, 52, 83, 98, 154),  # DARK
    ]
    for cx, y0, y1, clx0, clx1 in sym_orbs:
        arr[y0 + 15 : y1 + 1, clx0:clx1] = (0, 0, 0, 0)
        for y in range(y0 + 15, y1 + 1):
            for x in range(int(np.ceil(cx)), int(np.ceil(cx)) + 16):
                mx = int(round(2 * cx - x))
                if 0 <= mx < arr.shape[1] and arr[y, mx, 3] > 0:
                    arr[y, x] = arr[y, mx]

    # 2. FIRE orb (x=3..34, y=2..33, center=(18.5, 17.5)):
    # Kanji 炎 overlaps x=21..35, y=18..33; restore outer circular orange rim smoothly from symmetric radius
    arr[17:34, 21:77] = (0, 0, 0, 0)
    cx, cy = 18.5, 17.5
    for y in range(17, 34):
        for x in range(21, 35):
            r = float(np.hypot(x - cx, y - cy))
            if r <= 15.8:
                # Mirror alpha & rim shading from symmetric upper-right/lower-left rim
                mx = int(round(2 * cx - x))
                my = int(round(2 * cy - y))
                if r >= 13.0:
                    # Outer crisp orange-red circle border (mirror left rim horizontally first!)
                    ref = arr[y, mx] if arr[y, mx, 3] > 0 else arr[my, x]
                    arr[y, x] = ref
                elif r >= 10.5:
                    # Mid bright orange ring
                    arr[y, x] = (255, 108, 12, 255)
                else:
                    # Warm golden-orange inner flame blend
                    t = max(0.0, min(1.0, (r - 4.0) / 7.0))
                    arr[y, x] = (
                        255,
                        int(round(205 * (1 - t) + 125 * t)),
                        int(round(115 * (1 - t) + 25 * t)),
                        255,
                    )

    # 3. THUNDER orb (x=156..187, y=2..33, center=(171.5, 17.5)):
    # Kanji 雷 overlaps x=175..189, y=17..33; restore golden-orange lower-right orb rim cleanly
    arr[17:34, 175:236] = (0, 0, 0, 0)
    cx, cy = 171.5, 17.5
    for y in range(17, 34):
        for x in range(175, 188):
            r = float(np.hypot(x - cx, y - cy))
            if r <= 15.6:
                mx = int(round(2 * cx - x))
                if r >= 13.2:
                    arr[y, x] = arr[y, mx]
                elif r >= 10.0:
                    arr[y, x] = (255, 170, 10, 255)
                else:
                    arr[y, x] = (255, 200, 35, 255)

    im.paste(Image.fromarray(arr, mode="RGBA"), (0, 0))

    # Draw crisp English element names (matching RANDOM's position & style, zero kanji!)
    elem_labels = [
        ((24, 19, 76, 33), "FIRE", (225, 45, 20, 255)),
        ((100, 19, 152, 33), "AQUA", (15, 145, 235, 255)),
        ((176, 19, 236, 33), "THUNDER", (225, 135, 10, 255)),
        ((24, 69, 76, 83), "LIGHT", (30, 175, 40, 255)),
        ((100, 69, 152, 83), "DARK", (205, 35, 215, 255)),
    ]
    for box, label, stroke in elem_labels:
        draw_text_in_box(im, box, label, 13, (255, 255, 255, 255), stroke, 1, min_size=9)


def localize_battle_hud(orig_dir: Path, out_dir: Path) -> int:
    from PIL import ImageFilter

    count = 0

    # 1. btl_files02.tm2 (384x432) — pixel-exact bboxes measured from original atlas
    rel = "BATTLE/btl_files02.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    draw = ImageDraw.Draw(im)

    # Top-left 6 character names (23px slots y=1+i*23, x=1..79; keep subtitle y0..y0+7 intact!)
    # Strictly stay inside x<=79 so SCORE digits at x>=80 are never touched.
    top_names = [
        (1, 8, 79, 22, "SYNN"),
        (1, 31, 79, 45, "SYNN"),
        (1, 54, 79, 68, "NANAKA"),
        (1, 77, 79, 91, "LOLOTTE"),
        (1, 100, 79, 114, "MISA"),
        (1, 123, 79, 137, "RIA"),
    ]
    for x0, y0, x1, y1, txt in top_names:
        clear_box(im, (x0, y0, x1, y1))
        draw_text_in_box(im, (x0, y0, x1, y1), txt, 13, (255, 255, 255, 255), (225, 40, 65, 255), 1, min_size=8)

    # Bottom 5 character names (exact measured JP-only rows below their English subtitles)
    bot_names = [
        (105, 392, 183, 406, "EAUDEROURKE"),
        (2, 416, 80, 430, "MACARON"),
        (82, 416, 160, 430, "BYLOUS"),
        (183, 416, 243, 430, "SALLY"),
        (242, 416, 320, 430, "MELILOT"),
    ]
    for x0, y0, x1, y1, txt in bot_names:
        clear_box(im, (x0, y0, x1, y1))
        draw_text_in_box(im, (x0, y0, x1, y1), txt, 13, (255, 255, 255, 255), (225, 40, 65, 255), 1, min_size=8)

    # 場外 ▶ badges (red at y=105..120, blue at y=122..137; keep arrow ▶ at x=163..173 intact!)
    for y0, y1, stroke in ((105, 120, (220, 30, 30, 255)), (122, 137, (20, 100, 225, 255))):
        clear_box(im, (139, y0, 162, y1))
        draw_text_in_box(im, (139, y0, 162, y1), "OUT", 10, (255, 255, 255, 255), stroke, 1, min_size=7)

    # バリア / BARRIER! glowing orange pill (x=310..371, y=78..121): keep BARRIER! below, replace バリア softly
    _clear_soft_pill_top(im, (318, 82, 366, 103))
    draw_text_in_box(im, (316, 84, 368, 102), "BARRIER", 12, (255, 255, 255, 255), (215, 70, 30, 255), 1, min_size=8)

    # 6 glowing action pills: preserve pastel glow halo + existing bottom English sub-label,
    # replace ONLY the top Japanese text cleanly!
    glow_pills = [
        ((7, 148, 76, 169), "UNISON", (30, 165, 65, 255)),
        ((109, 148, 152, 169), "HEAL", (20, 145, 195, 255)),
        ((9, 196, 76, 217), "RUMBLE", (210, 45, 55, 255)),
        ((96, 196, 164, 217), "POWER UP", (215, 95, 30, 255)),
        ((22, 244, 65, 265), "CHANT", (170, 50, 195, 255)),
        ((96, 244, 174, 265), "BARRIER DMG", (205, 40, 55, 255)),
    ]
    for box, txt, stroke in glow_pills:
        _clear_soft_pill_top(im, box)
        draw_text_in_box(im, box, txt, 14, (255, 255, 255, 255), stroke, 2, min_size=8)

    # Element wheel (x=182..276, y=168..252): replace 5 single kanji with crisp pixel English
    _clean_wheel_kanji(im)

    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 2. btl_files03.tm2 (256x200): Command buttons (Attack, Chant, Unison, Confirm)
    # Use each pill's exact eroded rounded/oval interior mask so no square corners ever cut into
    # the glossy oval borders, and sample the real vertical gradients (including gray disabled)!
    rel = "BATTLE/btl_files03.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    arr03 = np.array(im, dtype=np.uint8)
    # Row 0 x=10 (green blank cap), Row 0 x=180 (cyan blank cap)
    green_grad = arr03[5:27, 10, :].copy()
    cyan_grad = arr03[5:27, 180, :].copy()
    # Real silver-gray gradient sampled from disabled Unison pill (row 2 y=68..91)
    gray_vals = [
        (146, 145, 154), (154, 154, 158), (162, 162, 165), (171, 170, 178),
        (178, 178, 181), (132, 132, 138), (126, 125, 131), (128, 127, 133),
        (134, 133, 139), (140, 138, 144), (146, 145, 154), (150, 149, 156),
        (156, 156, 160), (164, 164, 168), (174, 174, 178), (184, 184, 188),
        (192, 192, 196), (198, 196, 204), (203, 200, 209), (204, 202, 211),
    ]
    gray_grad = np.array([(r, g, b, 255) for r, g, b in gray_vals], dtype=np.uint8)

    g_out = (20, 95, 10, 255)
    c_out = (10, 85, 155, 255)
    d_out = (50, 55, 65, 255)
    # Full pill outer bboxes (px0, py0, px1, py1, text, gradient, outline_rgba)
    btns = [
        # Row 0 (y=0..32)
        (25, 1, 63, 31, "Attack", green_grad, g_out),
        (65, 1, 103, 31, "Chant", green_grad, g_out),
        (105, 1, 143, 31, "Unison", green_grad, g_out),
        (193, 1, 248, 31, "Attack", cyan_grad, c_out),
        # Row 1 (y=32..64)
        (1, 33, 56, 63, "Attack", green_grad, g_out),
        (57, 33, 112, 63, "Chant", green_grad, g_out),
        (113, 33, 172, 63, "Confirm", green_grad, g_out),
        (198, 33, 253, 63, "Chant", cyan_grad, c_out),
        # Row 2 (y=64..96)
        (1, 65, 39, 95, "Attack", cyan_grad, c_out),
        (41, 65, 79, 95, "Chant", cyan_grad, c_out),
        (81, 65, 119, 95, "Unison", cyan_grad, c_out),
        (121, 65, 180, 95, "Confirm", cyan_grad, c_out),
        (182, 65, 220, 95, "Unison", gray_grad, d_out),
    ]
    for px0, py0, px1, py1, txt, grad, outline in btns:
        _fill_rounded_pill_interior(im, (px0, py0, px1, py1), grad, inset_px=3.2)
        tbox = (px0 + 4, py0 + 5, px1 - 4, py1 - 5)
        draw_text_in_box(im, tbox, txt, 13, (255, 255, 255, 255), outline, 1, min_size=7)
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 3. btl_filesE2_1.tm2 (240x232): 6 element ATK LV badges (transparent bg!) + 6 TOTAL labels
    rel = "BATTLE/btl_filesE2_1.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    # Remove the 5 single element kanji, restore each orb cleanly, and redraw crisp English labels
    _clean_orb_kanji_e21(im)
    # Replace 攻撃LV on a clean transparent background with matching element-colored outlines!
    badge_specs_e21 = [
        (0, 0, (225, 45, 20, 255)),    # Fire (red)
        (1, 0, (15, 145, 235, 255)),   # Aqua (cyan-blue)
        (2, 0, (225, 135, 10, 255)),   # Thunder (orange)
        (0, 1, (30, 175, 40, 255)),    # Light (green)
        (1, 1, (205, 35, 215, 255)),   # Dark (magenta)
        (2, 1, (95, 95, 100, 255)),    # Random (gray)
    ]
    for col, row, stroke in badge_specs_e21:
        bx0 = col * 80 + 18
        by0 = row * 50 + 34
        bx1 = col * 80 + 78
        by1 = row * 50 + 50
        clear_box(im, (bx0, by0, bx1, by1))
        draw_text_in_box(im, (col * 80 + 24, row * 50 + 33, bx1, by1 - 1), "ATK LV", 13, (255, 255, 255, 255), stroke, 1, min_size=9)
    # All 6 合計 slots at bottom (y=201..218, x = 2 + i*32 .. 28 + i*32)
    total_strokes = [
        (225, 45, 20, 255),
        (15, 145, 235, 255),
        (225, 135, 10, 255),
        (30, 175, 40, 255),
        (205, 35, 215, 255),
        (95, 95, 100, 255),
    ]
    for i, stroke in enumerate(total_strokes):
        tx0 = 1 + i * 32
        tx1 = tx0 + 29
        clear_box(im, (tx0, 200, tx1, 219))
        draw_text_in_box(im, (tx0, 201, tx1, 218), "TOTAL", 10, (255, 255, 255, 255), stroke, 1, min_size=7)

    # Zero out any stray RGB on alpha==0 pixels in the alpha-blended foreground regions
    # (y=0..100 and y=200..232, x=0..192) before generating the y=100..200 multiplicative shadows
    arr_e21 = np.array(im, dtype=np.uint8)
    fg_top = arr_e21[0:100, :]
    fg_top[fg_top[:, :, 3] == 0] = (0, 0, 0, 0)
    fg_bot = arr_e21[200:232, 0:192]
    fg_bot[fg_bot[:, :, 3] == 0] = (0, 0, 0, 0)

    # Regenerate the alpha==0 pink-red multiplicative drop-shadow silhouettes in y=100..200 (all 6 elements)
    # and x=192..222, y=200..219 (TOTAL shadow) directly from our newly rendered foreground cells!
    # In btl_filesE2_1.tm2, the engine draws y=100..200 with multiplicative blending (Dst * Src) where
    # (255,255,255,0) = 1.0 (transparent) and (241,127,136,0) = warm red-orange shadow core!
    for row in range(2):
        for col in range(3):
            fx0, fy0 = col * 80, row * 50
            sx0, sy0 = col * 80, 100 + row * 50
            cw = 76 if col < 2 else 74
            fg_a = arr_e21[fy0 : fy0 + 50, fx0 : fx0 + cw, 3]
            sil = Image.fromarray(((fg_a > 40).astype(np.uint8) * 255), mode="L")
            sil_d = sil.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(radius=0.85))
            t = np.array(sil_d, dtype=np.float32) / 255.0
            sh_cell = np.zeros((50, cw, 4), dtype=np.uint8)
            sh_cell[:, :, 0] = np.clip(np.round(255.0 * (1.0 - t) + 241.0 * t), 0, 255).astype(np.uint8)
            sh_cell[:, :, 1] = np.clip(np.round(255.0 * (1.0 - t) + 127.0 * t), 0, 255).astype(np.uint8)
            sh_cell[:, :, 2] = np.clip(np.round(255.0 * (1.0 - t) + 136.0 * t), 0, 255).astype(np.uint8)
            sh_cell[:, :, 3] = 0  # MUST stay alpha=0 to match original multiplicative shadow channel!
            # Fill entire 80x50 cell background with (255,255,255,0) up to x=230 (matching original white canvas)
            arr_e21[sy0 : sy0 + 50, sx0 : min(230, sx0 + 80)] = (255, 255, 255, 0)
            arr_e21[sy0 : sy0 + 50, sx0 : sx0 + cw] = sh_cell

    # Also regenerate the 7th bottom cell's TOTAL shadow (x=192..222, y=200..219; keep bar shadow at y=219..232 intact!)
    tot_a = arr_e21[200:219, 0:30, 3]
    tot_sil = Image.fromarray(((tot_a > 40).astype(np.uint8) * 255), mode="L")
    tot_d = tot_sil.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(radius=0.85))
    tt = np.array(tot_d, dtype=np.float32) / 255.0
    tot_sh = np.zeros((19, 30, 4), dtype=np.uint8)
    tot_sh[:, :, 0] = np.clip(np.round(255.0 * (1.0 - tt) + 241.0 * tt), 0, 255).astype(np.uint8)
    tot_sh[:, :, 1] = np.clip(np.round(255.0 * (1.0 - tt) + 127.0 * tt), 0, 255).astype(np.uint8)
    tot_sh[:, :, 2] = np.clip(np.round(255.0 * (1.0 - tt) + 136.0 * tt), 0, 255).astype(np.uint8)
    tot_sh[:, :, 3] = 0
    arr_e21[200:219, 192:222] = tot_sh

    im = Image.fromarray(arr_e21, mode="RGBA")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 4. btl_filesE2_2.tm2 (160x160): 16-color grayscale glow backplate for TOTAL ATK LV & ATK LV.
    # Strictly keep pure (0,0,0,255) background and alpha=0 cell dividers (row 0, 59, 118; col 0, 85)!
    rel = "BATTLE/btl_filesE2_2.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")

    def _draw_glow_text(target: Image.Image, box: tuple[int, int, int, int], text: str, start_sz: int) -> None:
        x0, y0, x1, y1 = box
        bw, bh = x1 - x0, y1 - y0
        layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 255))
        draw_text_in_box(layer, (1, 1, bw - 1, bh - 1), text, start_sz, (255, 255, 255, 255), (255, 255, 255, 255), 0, min_size=7)
        glow = layer.filter(ImageFilter.GaussianBlur(radius=1.15))
        a_core = np.array(layer, dtype=np.float32)
        a_glow = np.array(glow, dtype=np.float32)
        comb = np.clip(np.maximum(a_core, a_glow * 1.25), 0, 255).astype(np.uint8)
        comb[:, :, 3] = 255
        target.paste(Image.fromarray(comb, mode="RGBA"), (x0, y0))

    # Top cell (y=1..58): replace 合計攻撃LV at y=35..57, x=4..83
    _draw_glow_text(im, (4, 35, 83, 57), "TOTAL ATK LV", 11)
    # Middle cell (y=60..117): keep ━ bar at x=6..25, replace 攻撃LV at y=93..115, x=26..83
    _draw_glow_text(im, (26, 93, 83, 115), "ATK LV", 12)
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 5. btl_filesE3.tm2 (224x288): 4 rounded cyan-blue prompt pills.
    # Use eroded rounded-pill interior mask so the rounded corners & blue borders stay 100% intact!
    rel = "BATTLE/btl_filesE3.tm2.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    arrE3 = np.array(im, dtype=np.uint8)
    grad_e3 = arrE3[3:17, 40, :].copy()
    prompts = [
        (34, 1, 170, 19, "Select an action."),
        (28, 53, 175, 71, "Select a target."),
        (6, 105, 198, 123, "Select a Unison Leader."),
        (6, 125, 198, 143, "Select a Rumble Leader."),
    ]
    for px0, py0, px1, py1, txt in prompts:
        in_box = _fill_rounded_pill_interior(im, (px0, py0, px1, py1), grad_e3, inset_px=1.9)
        draw_text_in_box(im, (in_box[0] + 4, in_box[1], in_box[2] - 4, in_box[3]), txt, 12, (255, 255, 255, 255), (12, 95, 215, 255), 1, min_size=8)
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
