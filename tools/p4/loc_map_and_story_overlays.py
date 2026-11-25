"""Localize Overworld Map UI + Story/Event/Ending/Monologue Overlays in GRAPHIC.CPK/AdvGraphic."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive
from cpk.tim2 import decode_tm2, unwrap_texture

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_helpers import clear_box, draw_outlined_text, draw_text_in_box, fit_font, load_font

TARGET_FILES = [
    "map_files01.zip",
    "map_paki_files01.zip",
    "EXG_ED.zip",
    "stamp_base.zip",
    "stamp_comp.zip",
    "C007_jara1.zip",
    "C007_jara2.zip",
    "C007_jara3.zip",
    "TEXT_SOL1_a.zip",
    "TEXT_SOL2_a.zip",
    "TEXT_SOL3_a.zip",
    "TEXT_SOL4_a.zip",
    "TEXT_SOL5_a.zip",
    "C001_1nenmae.zip",
    "C001_kaisou.zip",
    "C001_mousou.zip",
    "C001_shinboku.zip",
    "C001_tenshi.zip",
    "C001_round1.zip",
    "C001_round2.zip",
    "C001_round3.zip",
    "C001_round4.zip",
    "C001_round5.zip",
    "MONO_C01_TX01.zip",
    "MONO_C02_TX01.zip",
    "MONO_C03_TX01.zip",
    "MONO_C04_TX01.zip",
]


def _load_serif(size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            r"C:\Windows\Fonts\georgiaz.ttf",
            r"C:\Windows\Fonts\timesbi.ttf",
            r"C:\Windows\Fonts\georgiai.ttf",
        ]
        if italic
        else [
            r"C:\Windows\Fonts\georgiab.ttf",
            r"C:\Windows\Fonts\timesbd.ttf",
            r"C:\Windows\Fonts\georgia.ttf",
        ]
    )
    for p in candidates:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return load_font(size)


def _load_clean_sans(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
        if bold
        else [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]
    )
    for p in candidates:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return load_font(size)


def ensure_originals_and_manifest(graphic_cpk: Path, orig_dir: Path) -> None:
    gr = CpkArchive(str(graphic_cpk))
    adv = {r["FileName"]: r for r in gr.entries() if r["DirName"] == "AdvGraphic"}
    manifest_path = orig_dir / "manifest.json"
    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_rel = {(m["cpk"], m["rel"]): m for m in manifest}
    changed = False
    for fn in TARGET_FILES:
        rel = f"AdvGraphic/{fn}"
        png_rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        dst = orig_dir / png_rel
        tm2, _, _ = unwrap_texture(gr.read_entry(adv[fn]), fn)
        im = decode_tm2(tm2)
        if not dst.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst)
        if ("GRAPHIC", rel) not in by_rel:
            manifest.append({"cpk": "GRAPHIC", "rel": rel, "png": png_rel, "w": im.width, "h": im.height})
            changed = True
    if changed:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _draw_curved_text(
    base: Image.Image,
    text: str,
    cx: float,
    cy: float,
    radius: float,
    arc_deg: float,
    top_arc: bool,
    font_size: int,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
    outer_glow: tuple[int, int, int, int] | None = None,
) -> None:
    """Draw character-by-character text along a gentle circular arc cleanly inside a badge."""
    f = load_font(font_size)
    tmp_d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    widths = [max(4, tmp_d.textbbox((0, 0), ch, font=f)[2] - tmp_d.textbbox((0, 0), ch, font=f)[0]) for ch in text]
    total_w = sum(widths) + max(0, len(text) - 1) * 1
    if total_w <= 0:
        return
    cur = -total_w / 2.0
    for ch, gw in zip(text, widths):
        mid = cur + gw / 2.0
        frac = mid / (total_w / 2.0)  # -1..+1
        ang_deg = frac * (arc_deg / 2.0)
        ang = math.radians(ang_deg)
        if top_arc:
            px = cx + radius * math.sin(ang)
            py = cy - radius * math.cos(ang)
            rot = -ang_deg
        else:
            px = cx + radius * math.sin(ang)
            py = cy + radius * math.cos(ang)
            rot = ang_deg
        if ch.strip():
            pad = 16
            patch = Image.new("RGBA", (gw + pad * 2, font_size + pad * 2), (0, 0, 0, 0))
            pc = (patch.width // 2, patch.height // 2)
            if outer_glow is not None:
                draw_outlined_text(patch, pc, ch, f, outer_glow, outer_glow, 4, anchor="mm")
            draw_outlined_text(patch, pc, ch, f, fill, outline, 2, anchor="mm")
            rot_patch = patch.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
            base.alpha_composite(rot_patch, (int(round(px - rot_patch.width / 2)), int(round(py - rot_patch.height / 2))))
        cur += gw + 1


def _loc_map_files01(orig_dir: Path, out_dir: Path) -> None:
    rel = "GRAPHIC/AdvGraphic/map_files01.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")

    # 1. 7 Weekdays (exact original UV boxes)
    wd_specs = [
        ((107, 1, 142, 15), "Mon.", (255, 255, 255, 255), (25, 110, 235, 255)),
        ((146, 1, 181, 15), "Tue.", (255, 255, 255, 255), (25, 110, 235, 255)),
        ((186, 1, 221, 15), "Wed.", (255, 255, 255, 255), (25, 110, 235, 255)),
        ((107, 17, 142, 31), "Thu.", (255, 255, 255, 255), (25, 110, 235, 255)),
        ((146, 17, 181, 31), "Fri.", (255, 255, 255, 255), (25, 110, 235, 255)),
        ((186, 17, 221, 31), "Sat.", (255, 255, 255, 255), (25, 145, 240, 255)),
        ((107, 33, 142, 47), "Sun.", (255, 235, 245, 255), (210, 65, 165, 255)),
    ]
    for box, txt, fill, out in wd_specs:
        clear_box(im, box)
        draw_text_in_box(im, box, txt, 12, fill, out, 1, min_size=8)

    # 2. 2 Area switch buttons (x=248..362)
    for box, txt in (
        ((248, 0, 362, 17), "To Ryuusei Academy"),
        ((248, 19, 362, 36), "To Ryuusei Town"),
    ):
        clear_box(im, box)
        draw_text_in_box(im, box, txt, 12, (255, 255, 255, 255), (30, 105, 225, 255), 1, min_size=8)

    # 3. 2 Area headers (keep thin white underline intact if desired, redraw cleanly)
    clear_box(im, (106, 45, 247, 75))
    draw_text_in_box(im, (108, 46, 245, 65), "Ryuusei Academy", 16, (255, 255, 255, 255), (25, 105, 225, 255), 2, min_size=10)
    draw_text_in_box(im, (112, 65, 242, 75), "Academy Campus", 9, (255, 255, 255, 255), (25, 105, 225, 255), 1, min_size=7)

    clear_box(im, (110, 76, 242, 104))
    draw_text_in_box(im, (112, 77, 240, 95), "Ryuusei Town", 16, (255, 255, 255, 255), (25, 105, 225, 255), 2, min_size=10)
    draw_text_in_box(im, (118, 94, 234, 104), "Downtown Area", 9, (255, 255, 255, 255), (25, 105, 225, 255), 1, min_size=7)

    # 4. 14 Character names (white with warm orange-red outline, matching original)
    ch_out = (210, 75, 15, 255)
    char_boxes = [
        ((0, 113, 73, 126), "Nanaka"),
        ((0, 126, 73, 139), "Lolotte"),
        ((0, 138, 73, 151), "Rosenkreuz"),
        ((0, 151, 73, 168), "Misa B."),
        ((0, 168, 73, 185), "Cristelis"),
        ((0, 185, 73, 198), "Ria Kujou"),
        ((0, 198, 73, 211), "Azel"),
        ((0, 211, 73, 224), "Sally-chan"),
        ((0, 224, 73, 237), "Shio Asukai"),
        ((0, 237, 73, 250), "Helena"),
        ((0, 250, 73, 263), "Melilot"),
        ((0, 263, 73, 276), "Sachiho"),
        ((0, 276, 73, 289), "Akane"),
        ((0, 348, 72, 362), "Macaron"),
        ((86, 348, 152, 362), "Amyrina"),
    ]
    for box, txt in char_boxes:
        clear_box(im, box)
        draw_text_in_box(im, box, txt, 11, (255, 255, 255, 255), ch_out, 1, min_size=8)

    # 5. All 32 ★ location labels — keep EVERY yellow ★ untouched; replace ONLY text strictly inside measured UV boxes!
    loc_specs = [
        # Row 0 (y=114..132)
        ((90, 114, 204, 132), "Grand Palace Sakura"),
        ((240, 114, 306, 132), "Ria's Class"),
        ((329, 114, 374, 132), "Library"),
        # Row 1 (y=133..151)
        ((90, 133, 184, 151), "Hilltop Plaza"),
        ((198, 133, 226, 151), "Chapel"),
        ((240, 133, 306, 151), "Culture Hall"),
        ((329, 133, 374, 151), "Dormitory"),
        # Row 2 (y=152..170)
        ((90, 152, 184, 170), "Kujou Estate"),
        ((198, 152, 226, 170), "Gate"),
        ((240, 152, 306, 170), "Misa's Class"),
        ((329, 152, 374, 170), "Homes"),
        # Row 3 (y=171..189)
        ((90, 171, 184, 189), "Lolotte's Class"),
        ((198, 171, 226, 189), "Path"),
        ((240, 171, 306, 189), "Asukai Shrine"),
        ((329, 171, 382, 189), "Chocolat"),
        # Row 4 (y=190..208)
        ((90, 190, 184, 208), "Finis Tower"),
        ((198, 190, 226, 208), "Yard"),
        ((240, 190, 306, 208), "Synn's Class"),
        ((329, 190, 383, 208), "Council Rm"),
        # Row 5 (y=209..227)
        ((90, 209, 165, 227), "Inside Library"),
        ((179, 209, 220, 227), "Yuugiri-an"),
        ((240, 209, 306, 227), "Tsukinoo Park"),
        ((329, 209, 383, 227), "Chair Office"),
        # Row 6 (y=228..246)
        ((90, 228, 165, 246), "Mihoshizaka"),
        ((179, 228, 220, 246), "School"),
        ((240, 228, 306, 246), "Synn's Room"),
        ((320, 228, 383, 246), "In Chapel"),
        # Row 7 (y=247..265)
        ((90, 247, 165, 265), "Shiokumi Mall"),
        ((179, 247, 220, 265), "Prier"),
        ((240, 247, 306, 265), "Sports Field"),
        ((320, 247, 383, 265), "Indoor Pool"),
        # Rows 8..11 (left of the blue arrow which begins at x=223!)
        ((90, 266, 164, 284), "Shio's Class"),
        ((179, 266, 220, 284), "Entrance"),
        ((90, 285, 164, 303), "Old Hallway"),
        ((179, 285, 220, 303), "New Bldg"),
        ((90, 304, 164, 322), "Mall Entry"),
        ((179, 304, 220, 322), "Old Bldg"),
        ((90, 323, 164, 341), "New Hallway"),
        ((179, 323, 220, 341), "Commute"),
    ]
    for box, txt in loc_specs:
        clear_box(im, box)
        draw_text_in_box(im, box, txt, 12, (255, 255, 255, 255), ch_out, 1, min_size=7, align="left")

    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)


def _loc_map_paki(orig_dir: Path, out_dir: Path) -> None:
    """Cleanly replace 移動画面 & 行き先をえらぶっす! on map_paki_files01.zip with seamless radial oval shading."""
    rel = "GRAPHIC/AdvGraphic/map_paki_files01.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    arr = np.array(im, dtype=np.uint8)
    h, w = arr.shape[:2]

    # Exact ellipse of the glossy blue oval: cx=152, cy=103.5, rx=146.5, ry=68.5
    cx, cy, rx, ry = 152.0, 103.5, 146.5, 68.5
    yy, xx = np.mgrid[0:h, 0:w]
    ell = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    rad = np.sqrt(np.maximum(0.0, ell))

    # Build radial color LUT directly from clean mid-left scanline y=96, x=6..106 (zero text, zero Paqy, zero stars!)
    lut_r = np.zeros(105, dtype=np.float32)
    lut_g = np.zeros(105, dtype=np.float32)
    lut_b = np.zeros(105, dtype=np.float32)
    lut_cnt = np.zeros(105, dtype=np.float32)
    for x in range(6, 108):
        for y in range(74, 104):
            r_px, g_px, b_px, a_px = arr[y, x]
            # Exclude bright cyan stars (G > 235 and R < 60) and pink star
            if a_px > 240 and b_px > 220 and r_px < 180:
                bin_i = min(104, int(round(rad[y, x] * 100)))
                lut_r[bin_i] += r_px
                lut_g[bin_i] += g_px
                lut_b[bin_i] += b_px
                lut_cnt[bin_i] += 1
    valid = lut_cnt > 0
    xs_v = np.where(valid)[0]
    lut_r = np.interp(np.arange(105), xs_v, lut_r[valid] / lut_cnt[valid])
    lut_g = np.interp(np.arange(105), xs_v, lut_g[valid] / lut_cnt[valid])
    lut_b = np.interp(np.arange(105), xs_v, lut_b[valid] / lut_cnt[valid])

    def _oval_rgb(d_val: float) -> tuple[int, int, int, int]:
        bi = min(104, max(0, int(round(d_val * 100))))
        return (int(round(lut_r[bi])), int(round(lut_g[bi])), int(round(lut_b[bi])), 255)

    # 1. Clear top text 移動画面 above/on top rim (y=0..56, x=48..256), preserving Paqy's ear/paw
    top_zone = (yy < 56) & (xx >= 48) & (xx <= 256)
    arr[top_zone & (ell > 1.0)] = (0, 0, 0, 0)
    # Paqy mask in top zone: non-cyan pixels around Paqy's head/paw (x=108..204, y>=44)
    r0, g0, b0 = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    is_paqy_top = (yy >= 44) & (xx >= 108) & (xx <= 204) & ((b0 - r0 < 50) | (r0 > 180))
    # Only touch top-rim pixels that were part of 移動画面 (yellow/white/dark-blue outline)
    is_top_txt = (
        (r0 > 130) | (b0 - g0 > 50) | ((r0 > 70) & (g0 > 150) & (b0 < 230))
    )
    # Dilate text mask by 2px so anti-aliased fringe is erased too
    top_fix = top_zone & (ell <= 1.0) & (~is_paqy_top) & is_top_txt
    for _ in range(2):
        padded = np.pad(top_fix, 1, mode="constant")
        top_fix = (
            padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:] | top_fix
        ) & top_zone & (ell <= 1.0) & (~is_paqy_top)
    ys, xs = np.where(top_fix)
    for y, x in zip(ys, xs):
        arr[y, x] = _oval_rgb(float(rad[y, x]))

    # 2. Clear bottom text 行き先をえらぶっす! seamlessly using dilated text-color mask (ZERO seam, stars intact!)
    bot_zone = (yy >= 108) & (yy <= 165) & (xx >= 24) & (xx <= 280) & (ell <= 0.94)
    is_paqy_bot = (yy <= 136) & (xx >= 122) & (xx <= 176) & (
        ((r0 > 170) & (g0 > 150) & (b0 > 150))  # white belly
        | ((r0 < 120) & (g0 < 120) & (b0 < 130))  # charcoal paws/feet
        | ((r0 > 180) & (g0 > 140) & (b0 < 120))  # gold badge
    )
    # Dilate Paqy mask by 2px so Paqy's crisp dark-blue outline around feet stays untouched
    for _ in range(2):
        p = np.pad(is_paqy_bot, 1, mode="constant")
        is_paqy_bot = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:] | is_paqy_bot
    is_bot_txt = bot_zone & (~is_paqy_bot) & (
        ((r0 > 125) & (g0 > 165) & (b0 > 220))  # white/light-blue text interior
        | ((b0 > 210) & (g0 < 175) & (r0 < 120))  # royal-blue text outline
    )
    for _ in range(3):
        p = np.pad(is_bot_txt, 1, mode="constant")
        is_bot_txt = (
            p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:] | is_bot_txt
        ) & bot_zone & (~is_paqy_bot)
    ys, xs = np.where(is_bot_txt)
    for y, x in zip(ys, xs):
        arr[y, x] = _oval_rgb(float(rad[y, x]))

    out_im = Image.fromarray(arr, mode="RGBA")
    # Draw arched yellow/blue/white "MAP SELECT" at top
    _draw_curved_text(
        out_im,
        "MAP SELECT",
        cx=152,
        cy=248,
        radius=220,
        arc_deg=44,
        top_arc=True,
        font_size=26,
        fill=(255, 250, 95, 255),
        outline=(20, 125, 245, 255),
        outer_glow=(255, 255, 255, 255),
    )
    # Draw arched white/blue "Pick where to go!" cleanly along bottom inside oval
    _draw_curved_text(
        out_im,
        "Pick where to go!",
        cx=152,
        cy=-76,
        radius=224,
        arc_deg=54,
        top_arc=False,
        font_size=21,
        fill=(255, 255, 255, 255),
        outline=(25, 115, 245, 255),
    )
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    out_im.save(out_dir / rel)


def _loc_stamp_and_ending(orig_dir: Path, out_dir: Path) -> None:
    # 1. EXG_ED.zip (224x32): おしまい…? おしまい☆ -> The End...?  The End!
    rel = "GRAPHIC/AdvGraphic/EXG_ED.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    clear_box(im, (0, 0, im.width, im.height))
    draw_text_in_box(im, (4, 2, 114, 30), "The End...?", 19, (255, 255, 255, 255), (15, 145, 250, 255), 2, min_size=12)
    draw_text_in_box(im, (118, 2, 220, 30), "The End!", 19, (255, 255, 255, 255), (15, 145, 250, 255), 2, min_size=12)
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)

    # 2. stamp_base.zip (304x272): tilted ~10.4 deg CCW (+10.4 in PIL rotate)
    rel = "GRAPHIC/AdvGraphic/stamp_base.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    arr = np.array(im, dtype=np.uint8)
    # Sample clean mint header color from x=210, y=30
    mint_col = tuple(int(v) for v in arr[30, 210])
    # Erase dark text pixels of スタンプカード inside tilted polygon (keeping mushroom at x=92..105 intact!)
    d = ImageDraw.Draw(im)
    d.polygon([(105, 42), (174, 29), (178, 43), (109, 56)], fill=mint_col)
    # Draw rotated "STAMP CARD" cleanly in exact dark charcoal-teal
    hdr_patch = Image.new("RGBA", (110, 26), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hdr_patch)
    hf = _load_clean_sans(13, bold=True)
    hd.text((55, 13), "STAMP CARD", font=hf, fill=(45, 60, 58, 255), anchor="mm")
    hdr_rot = hdr_patch.rotate(10.5, resample=Image.Resampling.BICUBIC, expand=True)
    im.alpha_composite(hdr_rot, (148 - hdr_rot.width // 2, 41 - hdr_rot.height // 2))

    # Erase bottom note ※スタンプをためると良いことがあります☆ on clean white sky polygon
    white_col = tuple(int(v) for v in arr[215, 50])
    d.polygon([(41, 206), (168, 183), (171, 198), (44, 221)], fill=white_col)
    note_patch = Image.new("RGBA", (130, 18), (0, 0, 0, 0))
    nd = ImageDraw.Draw(note_patch)
    nf = _load_clean_sans(8, bold=True)
    nd.text((65, 9), "*Collect stamps for a reward!*", font=nf, fill=(45, 55, 65, 255), anchor="mm")
    note_rot = note_patch.rotate(10.5, resample=Image.Resampling.BICUBIC, expand=True)
    im.alpha_composite(note_rot, (108 - note_rot.width // 2, 203 - note_rot.height // 2))
    im.save(out_dir / rel)

    # 3. stamp_comp.zip (480x272): keep *Congratulations!!* at y=0..82, replace 目標達成☆ / おめでとう
    rel = "GRAPHIC/AdvGraphic/stamp_comp.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    clear_box(im, (0, 82, im.width, im.height))
    f1 = load_font(54)
    f2 = load_font(48)
    # Soft white outer glow + vibrant magenta outline + white-to-pink gradient feel
    for text, y_pos, f in (("GOAL COMPLETE!", 128, f1), ("CONGRATS!!", 196, f2)):
        draw_outlined_text(im, (240, y_pos), text, f, (255, 255, 255, 255), (255, 255, 255, 255), 5, anchor="mm")
        draw_outlined_text(im, (240, y_pos), text, f, (255, 240, 250, 255), (235, 35, 165, 255), 3, anchor="mm")
    im.save(out_dir / rel)

    # 4. C007_jara1..3.zip: じゃら… -> Jingle...
    for fn, fsz in (("C007_jara1.zip", 32), ("C007_jara2.zip", 40), ("C007_jara3.zip", 52)):
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        w, h = im.size
        clear_box(im, (0, 0, w, h))
        draw_text_in_box(im, (6, 4, w - 6, h - 4), "Jingle...", fsz, (150, 195, 255, 255), (255, 255, 255, 255), 3, min_size=16)
        im.save(out_dir / rel)


def _hblur(im: Image.Image, radius: int, alpha_scale: float = 1.0) -> Image.Image:
    """Horizontal motion blur for Soltia's TEXT_SOL* animation frames."""
    if radius <= 0:
        return im
    arr = np.array(im, dtype=np.float32)
    h, w, _ = arr.shape
    k = 2 * radius + 1
    out = np.zeros_like(arr)
    pad = np.pad(arr, ((0, 0), (radius, radius), (0, 0)), mode="constant")
    csum = np.cumsum(pad, axis=1)
    # Box filter along x
    out[:, 0, :] = csum[:, k - 1, :] / k
    out[:, 1:, :] = (csum[:, k:, :] - csum[:, :-k, :]) / k
    out[:, :, 3] = np.clip(out[:, :, 3] * alpha_scale, 0, 255)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="RGBA")


def _loc_text_sol(orig_dir: Path, out_dir: Path) -> None:
    """Recreate all 5 Soltia dark whisper motion-blur sprite sheets inside exact original frame rects."""
    # (filename, english_text, list of (x0, y0, x1, y1, blur_radius, alpha_scale))
    specs = [
        ("TEXT_SOL1_a.zip", "— Struggle.", [
            (10, 0, 362, 24, 34, 0.70),
            (6, 24, 282, 48, 22, 0.85),
            (322, 24, 508, 48, 12, 0.95),
            (2, 48, 175, 72, 6, 1.00),
            (193, 48, 359, 72, 0, 1.00),
        ]),
        ("TEXT_SOL2_a.zip", "— Resist.", [
            (13, 0, 333, 24, 32, 0.70),
            (9, 24, 258, 48, 20, 0.85),
            (290, 24, 444, 48, 10, 0.95),
            (3, 48, 170, 72, 5, 1.00),
            (193, 48, 340, 72, 0, 1.00),
        ]),
        ("TEXT_SOL3_a.zip", "— Seek power.", [
            (8, 0, 400, 24, 36, 0.70),
            (5, 24, 317, 48, 22, 0.85),
            (2, 48, 212, 72, 10, 0.95),
            (218, 48, 425, 72, 5, 1.00),
            (1, 72, 194, 96, 0, 1.00),
        ]),
        ("TEXT_SOL4_a.zip", "— And surrender yourself.", [
            (7, 0, 477, 24, 38, 0.70),
            (5, 24, 389, 48, 24, 0.85),
            (2, 48, 276, 72, 12, 0.95),
            (1, 72, 262, 96, 5, 1.00),
            (1, 96, 254, 120, 0, 1.00),
        ]),
        ("TEXT_SOL5_a.zip", "— Now, awaken.", [
            (13, 0, 414, 24, 36, 0.70),
            (9, 24, 331, 48, 22, 0.85),
            (2, 48, 243, 72, 10, 0.95),
            (2, 72, 229, 96, 5, 1.00),
            (257, 48, 478, 72, 0, 1.00),
        ]),
    ]
    for fn, text, frames in specs:
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        orig = Image.open(orig_dir / rel).convert("RGBA")
        out = Image.new("RGBA", orig.size, (0, 0, 0, 0))
        for x0, y0, x1, y1, rad, ascale in frames:
            fw, fh = x1 - x0, y1 - y0
            patch = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
            pd = ImageDraw.Draw(patch)
            f = _load_serif(16, italic=False)
            while f.size > 10:
                bb = pd.textbbox((0, 0), text, font=f)
                if (bb[2] - bb[0]) <= fw - 8:
                    break
                f = _load_serif(f.size - 1, italic=False)
            pd.text((fw // 2, fh // 2), text, font=f, fill=(245, 245, 245, 255), anchor="mm")
            patch = _hblur(patch, rad, ascale)
            out.alpha_composite(patch, (x0, y0))
        out.save(out_dir / rel)


def _loc_c001_cards(orig_dir: Path, out_dir: Path) -> None:
    """Localize C001_* intermission title cards (pure white center, pastel stars in corners)."""
    pink = (228, 16, 122, 255)
    blue = (20, 115, 215, 255)

    # 1. 3 simple title cards (keep existing small italic English subtitle below, replace JP above!)
    simple = [
        ("C001_1nenmae.zip", "One Year Ago"),
        ("C001_kaisou.zip", "Recollection"),
        ("C001_mousou.zip", "Daydream"),
    ]
    for fn, title in simple:
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        d = ImageDraw.Draw(im)
        # Clear pure white center around main JP title (y=82..162, x=90..390) cleanly above English subtitle
        d.rectangle((90, 82, 390, 162), fill=(255, 255, 255, 255))
        f = _load_serif(42, italic=True)
        d.text((240, 122), title, font=f, fill=pink, anchor="mm")
        im.save(out_dir / rel)

    # 2. C001_shinboku.zip & C001_tenshi.zip ("Today's Topic" cards)
    for fn, main_txt, sub_txt, main_sz in (
        ("C001_shinboku.zip", "Let's Throw a Mixer!", "Let's have a party!", 36),
        ("C001_tenshi.zip", "An Angel", "An angel", 44),
    ):
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        d = ImageDraw.Draw(im)
        # Clear full central white band (y=68..208, x=10..470) without touching corner stars (y<68 or y>208)
        d.rectangle((10, 68, 470, 208), fill=(255, 255, 255, 255))
        fb = _load_clean_sans(22, bold=True)
        d.text((240, 92), "— Today's Topic —", font=fb, fill=blue, anchor="mm")
        fm = _load_serif(main_sz, italic=True)
        d.text((240, 145), main_txt, font=fm, fill=pink, anchor="mm")
        fs = _load_serif(15, italic=True)
        d.text((240, 186), sub_txt, font=fs, fill=pink, anchor="mm")
        im.save(out_dir / rel)

    # 3. C001_round1..5.zip (keep "Round 1..5", replace ONLY Japanese café subtitle below!)
    cafes = [
        ("C001_round1.zip", "- Café Rose Blanche -"),
        ("C001_round2.zip", "- Unter den Linden -"),
        ("C001_round3.zip", "- Burgstadt -"),
        ("C001_round4.zip", "- Tricolore -"),
        ("C001_round5.zip", "- Peace Tanimura Patisserie -"),
    ]
    for fn, sub in cafes:
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        d = ImageDraw.Draw(im)
        d.rectangle((60, 152, 420, 188), fill=(255, 255, 255, 255))
        f = _load_serif(18, italic=True)
        d.text((240, 168), sub, font=f, fill=pink, anchor="mm")
        im.save(out_dir / rel)


def _loc_monologues(orig_dir: Path, out_dir: Path) -> None:
    """Localize the 4 heroine route scrolling monologues (MONO_C01..04_TX01.zip)."""
    monos: dict[str, tuple[tuple[int, int, int, int], list[str]]] = {
        # Nanaka (512x432, warm dark brown ink)
        "MONO_C01_TX01.zip": ((92, 58, 42, 255), [
            "I once boarded a round-the-world luxury cruise ship with him.",
            "And we had the whole thing to ourselves! (Well, a former cruise ship.)",
            "Far from sailing the world, it's permanently moored at Tsukinoo Park.",
            "Only because it was a lame weekday tourist spot, though.",
            "Still, everything went just as I planned.",
            "There really was nobody around... and before I knew it, the exit.",
            "W-what do I do?! My heart was pounding, and in a panic, I blurted it out.",
            "Even as he kept chatting, all I could manage was 'Yeah, yeah.'",
            "When he asked 'What's wrong?', I laughed it off with an 'Ahaha.'",
            "'I'd love to spend a whole year on a ship touring sweets around the world.'",
            "'Going alone would be boring, so I'll bring you along too,' I told him.",
            "Whoa, I was actually pretty bold!",
            "A young guy and girl traveling all alone for an entire year!",
            "While my heart hammered away, he said in his usual carefree voice,",
            "he'd feel bad letting me pay for everything, so once he earns his own money.",
            "What the heck?! Why's he acting like we're just hitting the next town's festival?!",
            "When I asked, 'You're really okay being alone with me for a whole year?'",
            "he had the nerve to say he'd be fine if it's with me! That clueless blockhead!",
            "...Though I guess it was my fault for lacking the courage.",
            "And so the years slipped by just like that...",
            "But this time—this time for sure! I'm gonna confess!! I-I really will!",
        ]),
        # Lolotte (288x368, deep indigo-navy ink)
        "MONO_C02_TX01.zip": ((52, 55, 118, 255), [
            "Until the day I met you—",
            "A monochrome world. A world without polychrome.",
            "A world with no color to fade.",
            "A world that never changed.",
            "A hollow world.",
            "At least, that is how it looked to me.",
            "Walking and walking through endless white.",
            "Even the people passing by were white.",
            "Looking back, everyone dissolved into white.",
            "A dull, stifling, empty world.",
            "So I leaped right out of it.",
            "Because I learned of other colors.",
            "Of a full, living place where people truly live.",
            "Ever since the day I met you—",
            "Everything within me has bloomed with color.",
            "Soon it will shine brilliantly, sparkling bright.",
            "All because I met you—",
        ]),
        # Misa (320x368, warm sepia-brown ink)
        "MONO_C03_TX01.zip": ((92, 68, 44, 255), [
            "More than winning my parents' approval,",
            "perhaps I only ever wanted you to acknowledge me.",
            "That's why I wanted to win, ever since the day I tasted defeat.",
            "That's why I cared—yet kept denying it.",
            "That's why I couldn't stop watching, even though I'm used to holding back.",
            "There's no way I could ever",
            "fall in love with you—",
            "Yet simply being by your side",
            "made both of us shine all the brighter.",
            "Still, I couldn't see that sparkle,",
            "because I feared that if I admitted it,",
            "I could never beat you again.",
            "Maybe that's why I locked these feelings away.",
            "Yet without even realizing it,",
            "I kept hurting the people dearest to me...",
            "I'm so used to enduring everything—",
            "so why do I always end up hurting someone?",
        ]),
        # Ria (320x416, muted olive-brown ink)
        "MONO_C04_TX01.zip": ((62, 68, 42, 255), [
            "Ever since the day Mother told me",
            "the Kujou clan walks beside the Demon Lord,",
            "I had longed for that arrival.",
            "Wishing for Re-Crea may have been",
            "foolish and improper of me,",
            "yet my sister and I often spoke of it with sparkling eyes.",
            "We were told the Demon Lord is a hero who saves the world.",
            "So I thought he could never be my hero alone.",
            "Really, though, that was just to hide my embarrassment.",
            "Deep down, I wanted to be protected.",
            "Still, afraid of being teased—",
            "wanting to act like a dependable senior—",
            "I scolded him, 'You have to be everyone's Demon Lord.'",
            "I never imagined things would turn out like this.",
            "I only thought he was making a gentle joke.",
            "Appearing in my hour of need—the Demon Lord was my ideal.",
            "The one I had waited for so long.",
            "Far more wonderful a hero",
            "than the one I had ever pictured in my heart.",
        ]),
    }
    for fn, (ink, lines) in monos.items():
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        orig = Image.open(orig_dir / rel).convert("RGBA")
        w, h = orig.size
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(out)
        n = len(lines)
        row_h = (h - 16) / max(1, n)
        # Pick largest font that fits ALL lines cleanly within w - 16
        fsz = min(14, max(9, int(row_h * 0.72)))
        f = _load_clean_sans(fsz, bold=True)
        while fsz > 8:
            f = _load_clean_sans(fsz, bold=True)
            max_w = max(d.textbbox((0, 0), ln, font=f)[2] for ln in lines)
            if max_w <= w - 14:
                break
            fsz -= 1
        for i, ln in enumerate(lines):
            cy = int(round(8 + (i + 0.5) * row_h))
            # Subtle white halo for readability over light/dark backgrounds (matches soft anti-aliased original)
            d.text((w // 2, cy), ln, font=f, fill=ink, anchor="mm")
        out.save(out_dir / rel)


def run_all(graphic_cpk: Path, orig_dir: Path, out_dir: Path) -> None:
    ensure_originals_and_manifest(graphic_cpk, orig_dir)
    _loc_map_files01(orig_dir, out_dir)
    _loc_map_paki(orig_dir, out_dir)
    _loc_stamp_and_ending(orig_dir, out_dir)
    _loc_text_sol(orig_dir, out_dir)
    _loc_c001_cards(orig_dir, out_dir)
    _loc_monologues(orig_dir, out_dir)
    print(f"Localized map & story overlays: {len(TARGET_FILES)}")


if __name__ == "__main__":
    run_all(
        Path("work/iso_extract/GRAPHIC.CPK"),
        Path("work/p4_textures_orig"),
        Path("work/p4_textures_ui_v8"),
    )
