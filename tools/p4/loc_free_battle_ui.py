"""Localize all 23 Free Battle & Tutorial Select UI sheets (sys_hrbe_* and sys_hrbs_*) in GRAPHIC.CPK/AdvGraphic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive
from cpk.tim2 import decode_tm2, unwrap_texture

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loc_battle_banners import RES_TITLES
from loc_battle_hud import _fill_rounded_pill_interior
from render_helpers import clear_box, draw_outlined_text, draw_text_in_box, fit_font, load_font

TARGET_FILES = [
    "sys_hrbe_bg.zip",
    "sys_hrbe_rankin1.zip",
    "sys_hrbe_rankin2.zip",
    "sys_hrbe_rankin3.zip",
    "sys_hrbe_tips1.zip",
    "sys_hrbe_tips3.zip",
    "sys_hrbe_tips4.zip",
    "sys_hrbe_tips5.zip",
    "sys_hrbe_tips6.zip",
    "sys_hrbe_tips7.zip",
    "sys_hrbs_base1.zip",
    "sys_hrbs_base2.zip",
    "sys_hrbs_btne1.zip",
    "sys_hrbs_btne2.zip",
    "sys_hrbs_btne3.zip",
    "sys_hrbs_btnh1.zip",
    "sys_hrbs_btnh2.zip",
    "sys_hrbs_btnh3.zip",
    "sys_hrbs_btnn1.zip",
    "sys_hrbs_btnn2.zip",
    "sys_hrbs_btnn3.zip",
    "sys_hrbs_btnt1.zip",
    "sys_hrbs_btnt2.zip",
]

BARRIER_STAGES = {40, 41, 47, 48, 49, 53, 61, 62, 64, 67, 68}

# Concise overrides for narrow 110px pill buttons (full titles still used on wide tips3..7 banners!)
PILL_TITLE_OVERRIDES: dict[int, str] = {
    3: "Ryuusei Crusaders!",
    12: "Pure Heart & Cloth",
    20: "Sonic Speed Fighter",
    38: "Silent Guardian Angel",
    43: "Steps Out of Sync",
    47: "Demon Trapped in Light",
    48: "Demon Lord Always Near",
    49: "Gazing at Scorched Sky",
    50: "World Hidden in a Fist",
    52: "Ria's Open-Air Class",
    54: "Demon Lord Macaron",
    60: "Avengers Gathering",
    64: "Bound by Star Rain",
}


def _pill_title(stg: int) -> str:
    return PILL_TITLE_OVERRIDES.get(stg, RES_TITLES[stg])

TUTORIAL_TITLES = [
    "Basic Battle",
    "Unison Attack",
    "Rumble Attack",
    "Assist",
    "Watch Out for EX Attacks",
    "Attack with EX Attacks",
    "Break Through Barriers",
    "EX Attacks Pt. 2",
    "Macaron's EX Attack",
]

# sys_hrbe_tips1.zip bottom enemy/character labels (exact row/col order verified visually)
TIPS1_TOP_RIGHT = [
    # (col 2, col 3) at y=176..190 and y=192..206
    (128, 174, 184, 190, "Macaron"),
    (184, 174, 240, 190, "Yasubee"),
    (128, 191, 184, 207, "Zetton"),
    (184, 191, 240, 207, "Nagahama"),
]

TIPS1_GRID_NAMES = [
    ["Synn", "Nanaka", "Lolotte", "Misa"],
    ["Ria", "Demon Synn", "Demon Nanaka", "Komen"],
    ["Jangara", "Mochimochi", "Tinun", "Rokkaku"],
    ["Daikichi", "Yoshimura", "Orion", "Paqy"],
    ["Sally", "Ippuu", "Taishou", "Eauderourke"],
    ["Kal Kan", "Sheba", "Mon Petit", "Waltham"],
    ["Pasta", "Carat", "Friskies", "Kurokan"],
    ["Chao", "Arden", "Melilot", "Melilot"],
    ["Melilot", "Melilot", "Soltia", "Soltia"],
    ["Soltia", "Soltia", "Azel", "Dot"],
    ["Ichiya", "Isshin", "Hatsugai", "Bylous"],
    ["Bylous", "Macaron", "Macaron", None],
]


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


def _tile_clean_patch(im: Image.Image, src_box: tuple[int, int, int, int], dst_box: tuple[int, int, int, int]) -> None:
    """Seamless repeating-pattern fill (e.g., cream/yellow checkerboard) preserving exact phase alignment."""
    arr = np.array(im, dtype=np.uint8)
    sx0, sy0, sx1, sy1 = src_box
    dx0, dy0, dx1, dy1 = dst_box
    tw, th = sx1 - sx0, sy1 - sy0
    tile = arr[sy0:sy1, sx0:sx1]
    for y in range(dy0, dy1):
        ty = (y - sy0) % th
        for x in range(dx0, dx1):
            tx = (x - sx0) % tw
            arr[y, x] = tile[ty, tx]
    im.paste(Image.fromarray(arr[dy0:dy1, dx0:dx1], mode="RGBA"), (dx0, dy0))


def _loc_hrbe_bg_and_rankin(orig_dir: Path, out_dir: Path) -> None:
    # 1. sys_hrbe_bg.zip (480x272)
    rel = "GRAPHIC/AdvGraphic/sys_hrbe_bg.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    arr = np.array(im, dtype=np.uint8)
    # Restore top gold border + checkerboard under 最高評価 (x=384..440, y=0..18)
    arr[0:7, 384:440] = arr[0:7, 370:371]
    arr[7:8, 384:440] = arr[7:8, 370:371]
    im = Image.fromarray(arr, mode="RGBA")
    _tile_clean_patch(im, (372, 16, 380, 24), (384, 8, 440, 18))
    draw_text_in_box(im, (380, 1, 444, 16), "Best Rank", 11, (90, 62, 16, 255), (255, 255, 255, 255), 2, min_size=8)

    # Bottom footer bar (y=252..271): preserve ○ (112..126), × (180..194), L (248..268), R (270..290)
    # Sample clean white/lavender footer bg row from x=90
    arr = np.array(im, dtype=np.uint8)
    for x0, x1 in ((128, 174), (196, 244), (294, 378)):
        arr[252:270, x0:x1] = arr[252:270, 90:91]
    im = Image.fromarray(arr, mode="RGBA")
    leg_out = (85, 85, 92, 255)
    draw_text_in_box(im, (130, 252, 176, 270), "Confirm", 11, (255, 255, 255, 255), leg_out, 1, min_size=8, align="left")
    draw_text_in_box(im, (198, 252, 244, 270), "Back", 11, (255, 255, 255, 255), leg_out, 1, min_size=8, align="left")
    draw_text_in_box(im, (297, 252, 378, 270), "Switch Page", 11, (255, 255, 255, 255), leg_out, 1, min_size=8, align="left")
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)

    # 2. sys_hrbe_rankin1..3.zip (480x272)
    rank_specs = [
        ("sys_hrbe_rankin1.zip", "Ranked 1st Place!", (255, 210, 245, 255), (195, 35, 130, 255)),
        ("sys_hrbe_rankin2.zip", "Ranked 2nd Place!", (210, 245, 255, 255), (20, 145, 195, 255)),
        ("sys_hrbe_rankin3.zip", "Ranked 3rd Place!", (210, 235, 255, 255), (25, 110, 215, 255)),
    ]
    for fn, txt, fill, out in rank_specs:
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        # Clear ONLY inside the white inner oval band (y=121..147, x=116..364) cleanly to white
        arr = np.array(im, dtype=np.uint8)
        # Keep the pink/cyan dotted border (outer edge x<117 or x>363) 100% untouched!
        arr[121:147, 117:363] = (255, 255, 255, 255)
        im = Image.fromarray(arr, mode="RGBA")
        draw_text_in_box(im, (124, 122, 356, 146), txt, 21, fill, out, 2, min_size=12)
        im.save(out_dir / rel)


def _loc_hrbe_tips(orig_dir: Path, out_dir: Path) -> None:
    # 1. sys_hrbe_tips1.zip (256x400): sample exact element stroke color from each cell before clearing!
    rel = "GRAPHIC/AdvGraphic/sys_hrbe_tips1.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    orig_arr = np.array(im, dtype=np.uint8)

    def _sample_cell_stroke(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
        sub = orig_arr[y0:y1, x0:x1]
        op = sub[sub[:, :, 3] > 200]
        if op.size == 0:
            return (225, 80, 20, 255)
        rgb = op[:, :3].astype(np.int32)
        sat = rgb.max(axis=1) - rgb.min(axis=1)
        m = sat >= max(40, int(np.percentile(sat, 75)))
        med = np.median(rgb[m], axis=0).astype(int) if m.any() else np.array([225, 80, 20])
        return (int(med[0]), int(med[1]), int(med[2]), 255)

    for x0, y0, x1, y1, name in TIPS1_TOP_RIGHT:
        sc = _sample_cell_stroke(x0, y0, x1, y1)
        clear_box(im, (x0, y0, x1, y1))
        draw_text_in_box(im, (x0, y0, x1 - 2, y1), name, 12, (255, 255, 255, 255), sc, 1, min_size=7, align="left")

    col_bounds = [(0, 56), (56, 112), (112, 168), (168, 232)]
    for r_idx, row_names in enumerate(TIPS1_GRID_NAMES):
        y0 = 208 + r_idx * 16
        y1 = y0 + 16
        for c_idx, name in enumerate(row_names):
            if name is None:
                continue
            x0, x1 = col_bounds[c_idx]
            sc = _sample_cell_stroke(x0, y0, x1, y1)
            clear_box(im, (x0, y0, x1, y1))
            draw_text_in_box(im, (x0 + 1, y0, x1 - 2, y1), name, 12, (255, 255, 255, 255), sc, 1, min_size=7, align="left")
    im.save(out_dir / rel)

    # 2. sys_hrbe_tips3..7.zip: all 68 Free Battle gold stage titles (transparent bg, exact 27px row stride!)
    tip_ranges = [
        ("sys_hrbe_tips3.zip", range(1, 16)),
        ("sys_hrbe_tips4.zip", range(16, 31)),
        ("sys_hrbe_tips5.zip", range(31, 46)),
        ("sys_hrbe_tips6.zip", range(46, 61)),
        ("sys_hrbe_tips7.zip", range(61, 69)),
    ]
    for fn, stg_range in tip_ranges:
        rel = f"GRAPHIC/AdvGraphic/{fn}.png"
        orig = Image.open(orig_dir / rel).convert("RGBA")
        out = Image.new("RGBA", orig.size, (0, 0, 0, 0))
        w = orig.width
        for idx, stg in enumerate(stg_range):
            y0 = 1 + idx * 27
            y1 = y0 + 26
            title = RES_TITLES[stg]
            if stg in BARRIER_STAGES:
                label = f"{stg:02d}  {title} (Barrier)"
            else:
                label = f"{stg:02d}  {title}"
            # Warm cream-gold fill + deep orange-brown outline matching original stage title banner
            draw_text_in_box(out, (6, y0, w - 6, y1), label, 18, (255, 245, 200, 255), (195, 75, 10, 255), 2, min_size=10)
        out.save(out_dir / rel)


def _loc_hrbs_bases(orig_dir: Path, out_dir: Path) -> None:
    # 1. sys_hrbs_base1.zip (480x272)
    rel = "GRAPHIC/AdvGraphic/sys_hrbs_base1.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    # Seamless checkerboard tile over top-right prompt (x=330..456, y=8..36)
    _tile_clean_patch(im, (460, 4, 468, 12), (330, 8, 456, 36))
    draw_text_in_box(im, (332, 8, 454, 24), "Pick a stage!", 14, (75, 175, 255, 255), (255, 255, 255, 255), 1, min_size=10)
    draw_text_in_box(im, (332, 24, 454, 35), "Select a Battle Stage", 9, (75, 175, 255, 255), (255, 255, 255, 255), 0, min_size=7)

    # Wreath header 最高評価 at x=326..382, y=169..187 (pure white bg inside wreath top!)
    arr = np.array(im, dtype=np.uint8)
    arr[169:187, 326:382] = (255, 255, 255, 255)
    im = Image.fromarray(arr, mode="RGBA")
    draw_text_in_box(im, (324, 169, 384, 187), "Best Rank", 11, (90, 62, 16, 255), (255, 255, 255, 255), 2, min_size=8)

    # Bottom footer (y=252..271): preserve □ (80..95), △ (232..246), × (336..350)
    # Sample clean white footer bg row from x=60
    arr = np.array(im, dtype=np.uint8)
    for x0, x1 in ((96, 224), (248, 326), (352, 404)):
        arr[252:270, x0:x1] = arr[252:270, 60:61]
    im = Image.fromarray(arr, mode="RGBA")
    leg_out = (50, 50, 58, 255)
    draw_text_in_box(im, (98, 252, 224, 270), "Reset High Scores", 11, (255, 255, 255, 255), leg_out, 1, min_size=8, align="left")
    draw_text_in_box(im, (249, 252, 326, 270), "Difficulty", 11, (255, 255, 255, 255), leg_out, 1, min_size=8, align="left")
    draw_text_in_box(im, (353, 252, 404, 270), "Back", 11, (255, 255, 255, 255), leg_out, 1, min_size=8, align="left")
    im.save(out_dir / rel)

    # 2. sys_hrbs_base2.zip (480x272)
    rel = "GRAPHIC/AdvGraphic/sys_hrbs_base2.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    _tile_clean_patch(im, (460, 4, 468, 12), (266, 8, 456, 36))
    draw_text_in_box(im, (268, 8, 454, 24), "Pick a tutorial!", 14, (75, 175, 255, 255), (255, 255, 255, 255), 1, min_size=10)
    draw_text_in_box(im, (268, 24, 454, 35), "Select a Tutorial to View", 9, (75, 175, 255, 255), (255, 255, 255, 255), 0, min_size=7)

    # Bottom × 戻る (preserve × at x=216..230; clear text x=232..276)
    arr = np.array(im, dtype=np.uint8)
    arr[252:270, 232:278] = arr[252:270, 60:61]
    im = Image.fromarray(arr, mode="RGBA")
    draw_text_in_box(im, (233, 252, 278, 270), "Back", 11, (255, 255, 255, 255), (50, 50, 58, 255), 1, min_size=8, align="left")
    im.save(out_dir / rel)


def _redraw_stage_pill(
    im: Image.Image,
    px0: int,
    py0: int,
    px1: int,
    py1: int,
    text: str,
    grad: np.ndarray,
    text_fill: tuple[int, int, int, int],
    text_out: tuple[int, int, int, int],
    keep_num_x: int = 24,
) -> None:
    """Redraw ONLY the text portion inside a rounded stage/tutorial pill while preserving its rounded border & number."""
    # Save original left number badge (px0..px0+keep_num_x) before pill fill, then restore it cleanly!
    num_crop = im.crop((px0, py0, px0 + keep_num_x, py1)).copy()
    _fill_rounded_pill_interior(im, (px0, py0, px1, py1), grad, inset_px=2.3, alpha_thresh=160)
    im.paste(num_crop, (px0, py0))
    # Draw crisp English title cleanly inside the remaining rounded pill interior (zero spillover!)
    draw_text_in_box(
        im,
        (px0 + keep_num_x + 2, py0 + 2, px1 - 6, py1 - 2),
        text,
        11,
        text_fill,
        text_out,
        1,
        min_size=7,
        align="left",
    )


def _loc_hrbs_pills(orig_dir: Path, out_dir: Path) -> None:
    cols = [(1, 142), (145, 286), (289, 430)]
    rows_1 = [
        (1, 21), (22, 42), (43, 63), (64, 84), (85, 105),
        (113, 133), (134, 154), (155, 175), (176, 196), (197, 217),
        (225, 245), (246, 266), (267, 287), (288, 308), (309, 329),
    ]
    rows_2 = [
        (1, 21), (22, 42), (43, 63), (64, 84), (85, 105),
        (113, 133), (134, 154), (155, 175), (176, 196), (197, 217),
    ]
    rows_3 = [
        (1, 21), (22, 42), (43, 63), (64, 84), (85, 105), (106, 126),
        (129, 149), (150, 170), (171, 191), (192, 212), (213, 233),
        (234, 254), (255, 275), (276, 296), (297, 317), (318, 338), (339, 359),
        (360, 380), (381, 401), (402, 422), (423, 443), (444, 464), (465, 485),
    ]

    # Sample clean pill interior gradient from the right-hand empty tail of pill (0, 0) at x=132!
    def _sample_grad(im: Image.Image, py0: int, py1: int) -> np.ndarray:
        arr = np.array(im, dtype=np.uint8)
        return arr[py0 + 3 : py1 - 3, 132, :].copy()

    # 1. Tutorial pills: sys_hrbs_btnt1.zip (9 pills in 2 cols x 5 rows) & sys_hrbs_btnt2.zip (9 pills in 1 col x 9 rows)
    rel_t1 = "GRAPHIC/AdvGraphic/sys_hrbs_btnt1.zip.png"
    im_t1 = Image.open(orig_dir / rel_t1).convert("RGBA")
    grad_t1 = _sample_grad(im_t1, 1, 21)
    for i, title in enumerate(TUTORIAL_TITLES):
        c, r = divmod(i, 5)
        px0, px1 = cols[c]
        py0, py1 = rows_1[r]
        _redraw_stage_pill(im_t1, px0, py0, px1, py1, title, grad_t1, (255, 255, 255, 255), (25, 60, 165, 255))
    im_t1.save(out_dir / rel_t1)

    rel_t2 = "GRAPHIC/AdvGraphic/sys_hrbs_btnt2.zip.png"
    im_t2 = Image.open(orig_dir / rel_t2).convert("RGBA")
    grad_t2 = _sample_grad(im_t2, 1, 21)
    for i, title in enumerate(TUTORIAL_TITLES):
        px0, px1 = cols[0]
        py0, py1 = 1 + i * 21, 21 + i * 21
        _redraw_stage_pill(im_t2, px0, py0, px1, py1, title, grad_t2, (255, 255, 255, 255), (20, 110, 185, 255))
    im_t2.save(out_dir / rel_t2)

    # 2. Easy / Hard / Normal Free Battle stage pills (9 sheets x 68 stages!)
    themes = [
        ("e", (15, 110, 50, 255), (45, 130, 25, 255)),   # Easy: dark teal-green / bright lime
        ("h", (155, 20, 75, 255), (175, 45, 105, 255)),  # Hard: deep magenta / bright pink
        ("n", (20, 65, 165, 255), (25, 115, 195, 255)),  # Normal: royal blue / bright sky blue
    ]
    for code, out_norm, out_sel in themes:
        # Sheet 1: stages 1..45 (3 blocks of 5 rows x 3 cols)
        rel1 = f"GRAPHIC/AdvGraphic/sys_hrbs_btn{code}1.zip.png"
        im1 = Image.open(orig_dir / rel1).convert("RGBA")
        grad1 = _sample_grad(im1, 1, 21)
        for blk in range(3):
            for col_i in range(3):
                for r_in in range(5):
                    stg = blk * 15 + col_i * 5 + r_in + 1
                    px0, px1 = cols[col_i]
                    py0, py1 = rows_1[blk * 5 + r_in]
                    _redraw_stage_pill(im1, px0, py0, px1, py1, _pill_title(stg), grad1, (255, 255, 255, 255), out_norm)
        im1.save(out_dir / rel1)

        # Sheet 2: stages 46..60 (block 0: 3 cols x 5 rows) + 61..68 (block 1: col 0 has 61..65, col 1 has 66..68)
        rel2 = f"GRAPHIC/AdvGraphic/sys_hrbs_btn{code}2.zip.png"
        im2 = Image.open(orig_dir / rel2).convert("RGBA")
        grad2 = _sample_grad(im2, 1, 21)
        for col_i in range(3):
            for r_in in range(5):
                stg = 46 + col_i * 5 + r_in
                px0, px1 = cols[col_i]
                py0, py1 = rows_2[r_in]
                _redraw_stage_pill(im2, px0, py0, px1, py1, _pill_title(stg), grad2, (255, 255, 255, 255), out_norm)
        for idx, stg in enumerate(range(61, 69)):
            col_i, r_in = divmod(idx, 5)
            px0, px1 = cols[col_i]
            py0, py1 = rows_2[5 + r_in]
            _redraw_stage_pill(im2, px0, py0, px1, py1, _pill_title(stg), grad2, (255, 255, 255, 255), out_norm)
        im2.save(out_dir / rel2)

        # Sheet 3: highlighted/selected pills for stages 1..68
        # Rows 0..16: col 0=1..17, col 1=18..34, col 2=35..51
        # Rows 17..22: col 0=52..57, col 1=58..63, col 2=64..68
        rel3 = f"GRAPHIC/AdvGraphic/sys_hrbs_btn{code}3.zip.png"
        im3 = Image.open(orig_dir / rel3).convert("RGBA")
        grad3 = _sample_grad(im3, 1, 21)
        for col_i in range(3):
            for r_i in range(17):
                stg = col_i * 17 + r_i + 1
                px0, px1 = cols[col_i]
                py0, py1 = rows_3[r_i]
                _redraw_stage_pill(im3, px0, py0, px1, py1, _pill_title(stg), grad3, (255, 255, 255, 255), out_sel)
        for col_i, base_stg, count in ((0, 52, 6), (1, 58, 6), (2, 64, 5)):
            for r_off in range(count):
                stg = base_stg + r_off
                px0, px1 = cols[col_i]
                py0, py1 = rows_3[17 + r_off]
                _redraw_stage_pill(im3, px0, py0, px1, py1, _pill_title(stg), grad3, (255, 255, 255, 255), out_sel)
        im3.save(out_dir / rel3)


def run_all(graphic_cpk: Path, orig_dir: Path, out_dir: Path) -> None:
    ensure_originals_and_manifest(graphic_cpk, orig_dir)
    _loc_hrbe_bg_and_rankin(orig_dir, out_dir)
    _loc_hrbe_tips(orig_dir, out_dir)
    _loc_hrbs_bases(orig_dir, out_dir)
    _loc_hrbs_pills(orig_dir, out_dir)
    print(f"Localized Free Battle & Tutorial Select UI sheets: {len(TARGET_FILES)}")


if __name__ == "__main__":
    run_all(
        Path("work/iso_extract/GRAPHIC.CPK"),
        Path("work/p4_textures_orig"),
        Path("work/p4_textures_ui_v8"),
    )
