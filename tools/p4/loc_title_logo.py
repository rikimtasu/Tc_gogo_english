"""Redraw Title Screen logo textures (sys_ti_files02, sys_ti_logo, sys_ti_logo02) at exact 1:1 original coordinates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from render_helpers import clear_box

LOGO_FONT = Path(r"C:\Windows\Fonts\arialbi.ttf")
if not LOGO_FONT.is_file():
    LOGO_FONT = Path(r"C:\Windows\Fonts\segoeuib.ttf")


def render_title_word(
    text: str,
    target_w: int,
    target_h: int,
    left_rgb: tuple[int, int, int],
    mid_rgb: tuple[int, int, int],
    right_rgb: tuple[int, int, int],
    ss: int = 4,
) -> tuple[Image.Image, Image.Image]:
    """Render a bold italic anime-style logo word with horizontal gradient + white/blue double outline.

    Returns (foreground_rgba, dark_blue_silhouette_rgba) at exact (target_w, target_h).
    """
    hi_h = target_h * ss
    font_sz = int(hi_h * 0.78)
    font = ImageFont.truetype(str(LOGO_FONT), font_sz)
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    sw_outer = int(round(3.2 * ss))
    sw_white = int(round(1.7 * ss))
    bx0, by0, bx1, by1 = dummy.textbbox((0, 0), text, font=font, stroke_width=sw_outer)
    raw_w = (bx1 - bx0) + sw_outer * 2 + 8
    raw_h = (by1 - by0) + sw_outer * 2 + 8

    fg = Image.new("RGBA", (raw_w, raw_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(fg)
    tx, ty = -bx0 + sw_outer + 4, -by0 + sw_outer + 4
    d.text((tx, ty), text, font=font, fill=(10, 130, 232, 255), stroke_width=sw_outer, stroke_fill=(10, 130, 232, 255))
    d.text((tx, ty), text, font=font, fill=(255, 255, 255, 255), stroke_width=sw_white, stroke_fill=(255, 255, 255, 255))

    mask_im = Image.new("RGBA", (raw_w, raw_h), (0, 0, 0, 0))
    ImageDraw.Draw(mask_im).text((tx, ty), text, font=font, fill=(255, 255, 255, 255))
    m_arr = np.array(mask_im)
    alpha = m_arr[:, :, 3]
    xs = np.where(alpha > 0)[1]
    if xs.size > 0:
        x0, x1 = int(xs.min()), int(xs.max())
        span = max(1, x1 - x0)
        grad = np.zeros_like(m_arr)
        for x in range(x0, x1 + 1):
            t = (x - x0) / span
            if t < 0.5:
                u = t * 2.0
                c = tuple(int(left_rgb[i] * (1 - u) + mid_rgb[i] * u) for i in range(3))
            else:
                u = (t - 0.5) * 2.0
                c = tuple(int(mid_rgb[i] * (1 - u) + right_rgb[i] * u) for i in range(3))
            grad[:, x, 0] = c[0]
            grad[:, x, 1] = c[1]
            grad[:, x, 2] = c[2]
        grad[:, :, 3] = alpha
        fg.alpha_composite(Image.fromarray(grad, mode="RGBA"))

    sil = Image.new("RGBA", (raw_w, raw_h), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sil)
    ds.text((tx, ty), text, font=font, fill=(14, 92, 182, 255), stroke_width=sw_outer + ss, stroke_fill=(14, 92, 182, 255))

    fg_out = fg.resize((target_w, target_h), Image.Resampling.LANCZOS)
    sil_out = sil.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return fg_out, sil_out


def localize_title_logos(orig_dir: Path, out_dir: Path) -> int:
    src_root = orig_dir / "GRAPHIC/AdvGraphic"
    dst_root = out_dir / "GRAPHIC/AdvGraphic"
    dst_root.mkdir(parents=True, exist_ok=True)

    # Exact word dimensions matching the original Japanese word slots:
    # In sys_ti_files02: TWINKLE at x=1..125 (w=124, h=34), CRUSADERS at x=150..326 (w=176, h=34)
    # In sys_ti_logo/02: shifted by +22px horizontally -> TWINKLE at x=23..147, CRUSADERS at x=172..348
    tw_fg, tw_sil = render_title_word(
        "TWINKLE",
        124,
        34,
        left_rgb=(255, 240, 28),
        mid_rgb=(210, 238, 32),
        right_rgb=(95, 218, 42),
    )
    cr_fg, cr_sil = render_title_word(
        "CRUSADERS",
        176,
        34,
        left_rgb=(32, 208, 60),
        mid_rgb=(16, 195, 222),
        right_rgb=(32, 152, 255),
    )

    orig_f2 = Image.open(src_root / "sys_ti_files02.zip.png").convert("RGBA")
    orig_l1 = Image.open(src_root / "sys_ti_logo.zip.png").convert("RGBA")
    orig_l2 = Image.open(src_root / "sys_ti_logo02.zip.png").convert("RGBA")

    # 1. sys_ti_files02.zip (368x392) — Animated Title Screen layers
    im_f2 = orig_f2.copy()
    # Keep ONLY the upper star tips & 3 motion bars (y=0..32, x=122..186) in the top shadow band
    # so no solid dark-blue Japanese kana shadow block remains between TWINKLE and CRUSADERS!
    star_top_sil = orig_f2.crop((122, 0, 186, 33))
    clear_box(im_f2, (0, 0, 340, 68))
    im_f2.alpha_composite(tw_sil, (2, 33))
    im_f2.alpha_composite(cr_sil, (151, 33))
    im_f2.alpha_composite(star_top_sil, (122, 0))
    # Foreground word band (y=68..105)
    clear_box(im_f2, (0, 68, 340, 105))
    im_f2.alpha_composite(tw_fg, (1, 69))
    im_f2.alpha_composite(cr_fg, (150, 69))
    im_f2.save(dst_root / "sys_ti_files02.zip.png")

    # Clean un-occluded layers from orig_f2 for reconstructing the text band of sys_ti_logo & sys_ti_logo02
    swoosh_band = orig_f2.crop((0, 122 + (45 - 19), 336, 122 + (93 - 19)))  # y_logo=45..93 -> y_f2=148..196
    sub_logo = orig_f2.crop((1, 110, 136, 120))  # orange 'TWINKLE CRUSADERS'
    rule_line = orig_f2.crop((1, 106, 327, 109))  # horizontal blue rule line
    # Full 1:1 winged star + 3 motion bars (x=177..258, y=318..386 -> 81x68)
    wing_star_full = orig_f2.crop((177, 318, 258, 386))

    # 2. sys_ti_logo02.zip (384x120) — Start from original image so all sparkles & swoosh tail stay 1:1!
    im_l2 = orig_l2.copy()
    clear_box(im_l2, (18, 45, 360, 93))
    im_l2.alpha_composite(swoosh_band, (51, 45))
    im_l2.alpha_composite(sub_logo, (227, 45))
    im_l2.alpha_composite(rule_line, (23, 90))
    im_l2.alpha_composite(tw_sil, (24, 56))
    im_l2.alpha_composite(cr_sil, (173, 56))
    im_l2.alpha_composite(tw_fg, (23, 55))
    im_l2.alpha_composite(cr_fg, (172, 55))
    im_l2.alpha_composite(wing_star_full, (142, 39))
    im_l2.save(dst_root / "sys_ti_logo02.zip.png")

    # 3. sys_ti_logo.zip (448x128) — Same exact 1:1 base + exact original GoGo! overlay from orig_l1!
    im_l1 = Image.new("RGBA", (448, 128), (0, 0, 0, 0))
    im_l1.paste(im_l2, (0, 0))
    # Extract the exact GoGo! pixels from orig_l1 where it differs from orig_l2 (x>=268, y>=35)
    arr_l1 = np.array(orig_l1)
    arr_l2_pad = np.zeros_like(arr_l1)
    arr_l2_pad[:120, :384] = np.array(orig_l2)
    diff_mask = np.abs(arr_l1.astype(int) - arr_l2_pad.astype(int)).sum(axis=2) > 28
    diff_mask[:35, :] = False
    diff_mask[:, :268] = False
    gogo_layer = np.zeros_like(arr_l1)
    gogo_layer[diff_mask] = arr_l1[diff_mask]
    im_l1.alpha_composite(Image.fromarray(gogo_layer, mode="RGBA"))
    im_l1.save(dst_root / "sys_ti_logo.zip.png")

    print("Localized title logos at exact 1:1 original coordinates: 3 textures")
    return 3


if __name__ == "__main__":
    localize_title_logos(Path("work/p4_textures_orig"), Path("work/p4_textures_en"))
