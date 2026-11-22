"""Localize BATTLE/res_title (68), BATTLE/EXName (19), and btl_nld_*_name*.tm2 (18)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from render_helpers import (
    clear_box,
    draw_gradient_outlined_text,
    draw_outlined_text,
    fit_font,
    load_font,
)

RES_TITLES: dict[int, str] = {
    1: "Awaken, Guardian Angel!!",
    2: "Reclaim the Steamed Buns!",
    3: "Birth of the Ryuusei Crusaders!",
    4: "Naginata Maiden Enters!",
    5: "Paqy Loses His Temper",
    6: "Sally-chan's Fierce Clash",
    7: "Sally-chan's Desire",
    8: "Sally-chan's Hard Sell",
    9: "Sally-chan's Robbery",
    10: "Sally-chan's Flight",
    11: "Demons in Their Element",
    12: "With a Pure Heart and Cloth",
    13: "Delicious Food Squad",
    14: "A Cat Living for the Org",
    15: "Pasta's Ambush",
    16: "Cute Things Have Fangs",
    17: "Crimson Omen",
    18: "Unsettling Moves & Air",
    19: "At the End of Flight",
    20: "One Who Lives at Sonic Speed",
    21: "Pasta's Counterattack",
    22: "The Contract and Its Price",
    23: "Furious Arden",
    24: "A Best Friend to Protect",
    25: "Gale-Force Arden",
    26: "Ghost of a Cat?",
    27: "Divine-Wind Arden",
    28: "Waitress's Counterattack",
    29: "Dancing in Her Palm",
    30: "Become a Mighty Sword",
    31: "Rescue from the Darkness",
    32: "Academy Encirclement",
    33: "Pasta's Charge",
    34: "Enraptured Arden",
    35: "Guarding the Milady",
    36: "At Training's End",
    37: "Shadowed Rosary",
    38: "Unresponsive Guardian Angel",
    39: "The One Called a Witch",
    40: "Angel Fallen to Earth",
    41: "Scorching Eyes",
    42: "Unleash from Re-Crea",
    43: "Steps That Should've Matched",
    44: "Obsessive Arden",
    45: "With You, It'll Be Fine",
    46: "Surpass the Odds",
    47: "Demonhood Trapped in Light",
    48: "The Demon Lord Is Always Near",
    49: "Gazing Up at Scorched Skies",
    50: "The World Hidden in a Fist",
    51: "The Blessed Holy War",
    52: "Ria-senpai's Open-Air Class",
    53: "Fierce Joint Battle",
    54: "Her Name Is Demon Lord Macaron",
    55: "Sibling Quarrel Erupts!",
    56: "A New Threat",
    57: "Clash! The Warusaders!?",
    58: "The Waitress's Scheme",
    59: "Punishment Time",
    60: "Gathering of the Avengers",
    61: "Oath of the Two",
    62: "One Who Keeps Faith",
    63: "Intensive Training",
    64: "Bound by the Rain of Stars",
    65: "The Demon Lord's Triumph",
    66: "Seize That Power",
    67: "Believe in Hope",
    68: "God's Choice",
}

EXNAME_ROWS: dict[str, list[tuple[str, tuple[int, int, int, int]]]] = {
    "btl_exname_ch00a.zip": [("Fatality Force", (180, 100, 10, 255))] * 4,
    "btl_exname_ch00b.zip": [("Arcane Meteor S", (180, 100, 10, 255))] * 4,
    "btl_exname_ch01a.zip": [("Raging Nova", (185, 25, 25, 255))] * 4,
    "btl_exname_ch01b.zip": [("Volcane Melt S", (185, 25, 25, 255))] * 4,
    "btl_exname_ch02.zip": [
        ("Seraphic Whisper", (20, 150, 45, 255)),
        ("Seraphic Whisper", (20, 150, 45, 255)),
        ("Absolute Tears", (180, 100, 10, 255)),
        ("Absolute Tears", (180, 100, 10, 255)),
    ],
    "btl_exname_ch03a.zip": [("Noblesse Laser", (185, 25, 25, 255))] * 4,
    "btl_exname_ch03b.zip": [("D. Wave", (185, 25, 25, 255))] * 4,
    "btl_exname_ch04a.zip": [("C. Brightia", (180, 100, 10, 255))] * 4,
    "btl_exname_ch04b.zip": [("E. Divinity", (180, 100, 10, 255))] * 4,
    "btl_exname_ch05.zip": [
        ("Legionic Weaver", (180, 100, 10, 255)),
        ("Legionic Weaver", (180, 100, 10, 255)),
        ("Burn Comet S", (185, 25, 25, 255)),
        ("Burn Comet S", (185, 25, 25, 255)),
    ],
    "btl_exname_ch06.zip": [("Demon Mail-Order", (180, 100, 10, 255))] * 4,
    "btl_exname_ch07.zip": [("Evil Servant", (180, 100, 10, 255))] * 4,
    "btl_exname_ch08.zip": [("Accel Sonic S", (185, 25, 25, 255))] * 4,
    "btl_exname_ch09.zip": [("Chaotic Howler", (185, 25, 25, 255))] * 4,
    "btl_exname_ch10.zip": [
        ("Heaven's Note", (185, 25, 25, 255)),
        ("Aqua Salvation", (20, 150, 45, 255)),
        ("Boost Frenzy", (185, 25, 25, 255)),
        ("Volt Stinger", (185, 25, 25, 255)),
    ],
    "btl_exname_ch11.zip": [
        ("Shadow Reactor", (180, 100, 10, 255)),
        ("Aqua Salvation", (20, 150, 45, 255)),
        ("Boost Frenzy", (185, 25, 25, 255)),
        ("Volt Stinger", (185, 25, 25, 255)),
    ],
    "btl_exname_ch12.zip": [
        ("Astral Aegis: Light", (180, 100, 10, 255)),
        ("Astral Aegis: Light", (180, 100, 10, 255)),
        ("Astral Light Spiral", (185, 25, 25, 255)),
        ("Astral Light Spiral", (185, 25, 25, 255)),
    ],
    "btl_exname_ch13.zip": [("F. Vortex", (185, 25, 25, 255))] * 4,
    "btl_exname_ch14.zip": [
        ("Aether Banishment", (185, 25, 25, 255)),
        ("Aether Banishment", (185, 25, 25, 255)),
        ("Deadly Assault", (185, 25, 25, 255)),
        ("Deadly Assault", (185, 25, 25, 255)),
    ],
}

# (title_en_override_or_None, main_name, stroke_rgb, list_of_(cat_en, ex_en))
NLD_BANNERS: dict[str, tuple[str | None, str, tuple[int, int, int], list[tuple[str, str]]]] = {
    "btl_nld_byl_name.tm2": (
        "MORTAL DUELIST -7th GENERAL-",
        "BYLOUS",
        (170, 30, 190),
        [("Stun Attack", "Finality Vortex")],
    ),
    "btl_nld_llt_name.tm2": (
        None,
        "LOLOTTE ROSENKREUZ",
        (15, 130, 210),
        [("Healing", "Seraphic Whisper"), ("Support Barrier", "Absolute Tears")],
    ),
    "btl_nld_llt_name2.tm2": (None, "LOLOTTE ROSENKREUZ", (15, 130, 210), []),
    "btl_nld_mac_name.tm2": (
        None,
        "MACARON",
        (170, 30, 190),
        [("ATK Support", "Legionic Weaver"), ("Attack", "Burn Comet Splash")],
    ),
    "btl_nld_mac_name2.tm2": (None, "MACARON", (170, 30, 190), []),
    "btl_nld_mel_name.tm2": (
        None,
        "MELILOT",
        (135, 35, 200),
        [
            ("Speed Support", "Shadow Reactor"),
            ("Healing", "Aqua Salvation"),
            ("Attack", "Boost Frenzy"),
            ("Multi-Hit", "Volt Stinger"),
        ],
    ),
    "btl_nld_mis_name.tm2": (
        None,
        "MISA B. CRISTELIS",
        (210, 145, 10),
        [("Multi-Hit", "Noblesse Laser"), ("Enhanced (Chant)", "Dimensional Wave")],
    ),
    "btl_nld_mis_name2.tm2": (None, "MISA B. CRISTELIS", (210, 145, 10), []),
    "btl_nld_nan2_name.tm2": (
        None,
        "NANAKA YUUGIRI",
        (210, 35, 90),
        [("Attack", "Raging Nova"), ("Enhanced (Chant)", "Volcane Melt Swarm")],
    ),
    "btl_nld_nan_name.tm2": (
        None,
        "NANAKA YUUGIRI",
        (210, 35, 90),
        [("Attack", "Raging Nova"), ("Enhanced (Chant)", "Volcane Melt Swarm")],
    ),
    "btl_nld_nan_name2.tm2": (None, "NANAKA YUUGIRI", (210, 35, 90), []),
    "btl_nld_ode_name.tm2": (
        None,
        "EAUDEROURKE",
        (170, 30, 190),
        [("Drain Attack", "Aether Scavenger")],
    ),
    "btl_nld_ria_name.tm2": (
        None,
        "RIA KUJOU",
        (25, 175, 45),
        [("Support Attack", "Cardinal Brightia"), ("Enhanced (Chant)", "Exect Divinity")],
    ),
    "btl_nld_ria_name2.tm2": (None, "RIA KUJOU", (25, 175, 45), []),
    "btl_nld_sar_name.tm2": (
        None,
        "SALLY-CHAN",
        (190, 35, 130),
        [("Random", "Thrilling Demon Mail")],
    ),
    "btl_nld_sin2_name.tm2": (
        None,
        "SYNN SAKURA",
        (150, 35, 200),
        [("Ally Summon+", "Arcane Meteor Stream")],
    ),
    "btl_nld_sin_name.tm2": (
        None,
        "SYNN SAKURA",
        (150, 35, 200),
        [("Ally Summon", "Fatality Force")],
    ),
    "btl_nld_sin_name2.tm2": (None, "SYNN SAKURA", (150, 35, 200), []),
}


def localize_res_titles(orig_dir: Path, out_dir: Path) -> int:
    count = 0
    for idx, title in RES_TITLES.items():
        rel = f"BATTLE/res_title/btl_res_title{idx:02d}.zip.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        # Clear Japanese text area to the right of STAGE NN (x >= 148)
        clear_box(im, (148, 0, im.width, im.height))
        draw = ImageDraw.Draw(im)
        max_w = im.width - 154
        font = fit_font(draw, title, max_w=max_w, start_size=22, min_size=12)
        draw_gradient_outlined_text(
            im,
            (150, 26),
            title,
            font=font,
            top_color=(245, 252, 255),
            bot_color=(70, 195, 255),
            stroke_fill=(10, 45, 115, 255),
            stroke_width=2,
            anchor="lm",
        )
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst)
        count += 1
    return count


def _find_exname_icon_end(arr: np.ndarray, row_idx: int, bg_pixel: tuple[int, int, int, int]) -> int:
    """Detect the right edge of the circular button icon in an 18px EXName row."""
    y0, y1 = row_idx * 18, (row_idx + 1) * 18
    sub = arr[y0:y1, :]
    if bg_pixel[3] == 0:
        active = sub[:, :, 3] > 20
    else:
        diff = np.abs(sub[:, :, :3].astype(int) - np.array(bg_pixel[:3], dtype=int)).sum(axis=2)
        active = diff > 25
    cols = active.any(axis=0)
    xs = np.where(cols)[0]
    if xs.size == 0:
        return 20
    x_start = int(xs[0])
    # Button circle is ~16-18px wide; keep 19px to avoid clipping right edge
    return min(arr.shape[1] - 10, x_start + 19)


def localize_exnames(orig_dir: Path, out_dir: Path) -> int:
    count = 0
    for fn, rows in EXNAME_ROWS.items():
        rel = f"BATTLE/EXName/{fn}.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        arr = np.array(im)
        bg = im.getpixel((0, 0))
        bg_fill = (0, 0, 0, 0) if bg[3] == 0 else bg
        for r_idx, (label, stroke_col) in enumerate(rows):
            icon_end = _find_exname_icon_end(arr, r_idx, bg)
            y0, y1 = r_idx * 18, (r_idx + 1) * 18
            clear_box(im, (icon_end, y0, im.width, y1), fill=bg_fill)
            draw = ImageDraw.Draw(im)
            max_w = im.width - icon_end - 3
            font = fit_font(draw, label, max_w=max_w, start_size=13, min_size=8)
            draw_outlined_text(
                im,
                (icon_end + 1, y0 + 9),
                label,
                font=font,
                fill=(255, 255, 255, 255),
                stroke_fill=stroke_col,
                stroke_width=1,
                anchor="lm",
            )
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst)
        count += 1
    return count


def localize_nld_names(orig_dir: Path, out_dir: Path) -> int:
    count = 0
    for fn, (title_override, main_name, stroke_rgb, ex_list) in NLD_BANNERS.items():
        rel = f"BATTLE/{fn}.png"
        im = Image.open(orig_dir / rel).convert("RGBA")
        # Clear optional header typo if needed (top 18px)
        if title_override is not None:
            clear_box(im, (0, 0, im.width, 19))
            draw = ImageDraw.Draw(im)
            f_hdr = fit_font(draw, title_override, max_w=im.width - 12, start_size=12, min_size=9)
            draw_outlined_text(
                im,
                (8, 10),
                title_override,
                font=f_hdr,
                fill=(255, 255, 255, 255),
                stroke_fill=(0, 0, 0, 255),
                stroke_width=1,
                anchor="lm",
            )
        # Clear main JP name band (y=19..62)
        clear_box(im, (0, 19, im.width, 64))
        draw = ImageDraw.Draw(im)
        f_main = fit_font(draw, main_name, max_w=im.width - 14, start_size=34, min_size=16)
        draw_outlined_text(
            im,
            (8, 41),
            main_name,
            font=f_main,
            fill=(255, 255, 255, 255),
            stroke_fill=(*stroke_rgb, 255),
            stroke_width=2,
            anchor="lm",
        )
        # Clear and redraw EX attack rows below y=64 (keep left 42px button cluster)
        if ex_list:
            row_h = (im.height - 68) // len(ex_list)
            for idx, (cat_en, ex_en) in enumerate(ex_list):
                y0 = 66 + idx * row_h
                y1 = y0 + row_h
                clear_box(im, (42, y0, im.width, min(im.height, y1 + 2)))
                f_cat = fit_font(draw, cat_en, max_w=im.width - 48, start_size=12, min_size=9)
                draw_outlined_text(
                    im,
                    (44, y0 + 8),
                    cat_en,
                    font=f_cat,
                    fill=(235, 240, 255, 255),
                    stroke_fill=(*stroke_rgb, 255),
                    stroke_width=1,
                    anchor="lm",
                )
                f_ex = fit_font(draw, ex_en, max_w=im.width - 48, start_size=17, min_size=11)
                draw_outlined_text(
                    im,
                    (44, y0 + 24),
                    ex_en,
                    font=f_ex,
                    fill=(255, 255, 255, 255),
                    stroke_fill=(*stroke_rgb, 255),
                    stroke_width=2,
                    anchor="lm",
                )
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst)
        count += 1
    return count


def run_all(orig_dir: Path, out_dir: Path) -> None:
    c1 = localize_res_titles(orig_dir, out_dir)
    c2 = localize_exnames(orig_dir, out_dir)
    c3 = localize_nld_names(orig_dir, out_dir)
    print(f"Localized: res_title={c1}, EXName={c2}, nld_names={c3} (total={c1+c2+c3})")


if __name__ == "__main__":
    run_all(Path("work/p4_textures_orig"), Path("work/p4_textures_en"))
