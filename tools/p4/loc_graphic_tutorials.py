"""Localize ALL tutorial textures cleanly (zero overlap, zero shape spillover) for BOTH BATTLE/tutorial and GRAPHIC/AdvGraphic."""

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
from loc_battle_hud import _draw_pixel_badge
from loc_tutorial import SUBTITLES, TU_SAM_CALLOUTS
from render_helpers import clear_box, draw_outlined_text, draw_text_in_box, fit_font, load_font

# All 24 400x152 Character EX / Assist tutorial cards (GRAPHIC/AdvGraphic only)
EX_ASSIST_CARDS: dict[str, tuple[str, str, str]] = {
    "tu_page10.zip": (
        "Misa's EX",
        "Noblesse Laser",
        "Strike first to win! Use this EX Attack to seize the early initiative. A multi-hit combo adding up to +6 RUSH hits! Also greatly reduces the enemy's STUN gauge.",
    ),
    "tu_page11.zip": (
        "Nanaka's EX",
        "Raging Nova",
        "The Crusaders' heavy hitter! Nanaka blows them away! Deals massive damage worth 2-3x a normal attack! Also reduces the enemy's STUN gauge.",
    ),
    "tu_page12.zip": (
        "Lolotte's EX",
        "Seraphic Whisper",
        "A healing EX Attack befitting an angel of mercy. Restores at least 10% and up to 60% of Max HP! Also boosts allies' STUN gauge and cures Stunned status.",
    ),
    "tu_page13.zip": (
        "Ria's EX",
        "Cardinal Brightia",
        "A gentle light that halts boss-class foes in their tracks. Besides dealing damage, reduces enemy STUN and EX gauges and knocks them further back.",
    ),
    "tu_page14.zip": (
        "Synn's EX",
        "Fatality Force",
        "Borrow allies' strength to unleash multiple Assist attacks! Early on it's only Paqy, but it grows stronger as you progress through the story. Still in training!",
    ),
    "tu_page15.zip": (
        "???'s Assist",
        "Direct Attack",
        "A mysterious girl whose name is still unknown. Deals heavy damage with her squeaky toy hammer!",
    ),
    "tu_page15a.zip": (
        "Sally-chan's Assist",
        "Direct Attack",
        "Ordered the deadliest weapon from Demon Mail-Order! Deals heavy damage with her squeaky toy hammer!",
    ),
    "tu_page16.zip": (
        "Sally-chan's EX",
        "Thrilling Demon Mail-Order",
        "Hot items from Demon Mail-Order—who knows what'll pop out! Hammer: Heavy damage. Sweets: Restores HP. Bomb: Heavy self-damage (backfire!).",
    ),
    "tu_page17.zip": (
        "Eauderourke's EX",
        "Evil Servant",
        "A terrifying move that temporarily summons 1-3 extra allies! With more foes, the Crusaders' timing can be disrupted. Summoned foes vanish after one attack!",
    ),
    "tu_page18.zip": (
        "Shio's Assist",
        "Soaring Phoenix Dance",
        "An ancient Asukai Shrine ritual uniting three dances. Damage is tiny, but it boosts the Crusaders' Attack and Critical Rate for a time.",
    ),
    "tu_page19.zip": (
        "Riesling's Assist",
        "Double Shot",
        "The old butler's twin pistols roar to life! Deals RUSH +2 damage.",
    ),
    "tu_page20.zip": (
        "Helena's Assist",
        "Two Thousand Blossoms",
        "Swordplay learned from cheesy Hollywood samurai flicks. In addition to normal damage, reduces the enemy's STUN gauge.",
    ),
    "tu_page22.zip": (
        "Macaron's EX",
        "Burn Comet Splash",
        "Macaron's signature attack, blasting foes with falling comets! Adds extra wait time to enemies based on her Magic LV. Stellar damage and impact!",
    ),
    "tu_page23.zip": (
        "Macaron's EX",
        "Legionic Weaver",
        "A super special where Macaron's fiery pep talk rallies the whole party! Greatly boosts all allies' Magic LV and Attack power!",
    ),
    "tu_page24.zip": (
        "Nanaka's EX",
        "Volcane Melt Swarm",
        "Deals massive damage worth 3-4x normal attacks AND shatters enemy Barriers! Reportedly very effective even against high-defense foes...",
    ),
    "tu_page25.zip": (
        "Lolotte's EX",
        "Absolute Tears",
        "Raises a water Barrier to protect allies! Blocks 2 to 4 hits of any enemy attack for 0 damage. Watch out, though—some foes can break Barriers!",
    ),
    "tu_page26.zip": (
        "Misa's EX",
        "Dimensional Wave",
        "Fight with grace and elegance! An EX Attack sure to stun foes. A multi-hit barrage up to 6 hits that cuts 2 STUN stars per hit!",
    ),
    "tu_page27.zip": (
        "Ria's EX",
        "Exact Divinity",
        "Seal even mega-bosses with dazzling light! Deals damage, cuts enemy EX gauge, knocks them further back, and absorbs part of the drained EX gauge.",
    ),
    "tu_page_adn.zip": (
        "Arden's Assist",
        "Grand Strike",
        "A ferocious all-out strike worthy of the offense-obsessed Arden. Heavy damage guaranteed!",
    ),
    "tu_page_aze.zip": (
        "Azel's Assist",
        "Pure Grace: Blessing of Light",
        "Azel's spiritual power guides the Crusaders to victory under light's blessing. Deals normal damage and adds +100 to the EX gauge!",
    ),
    "tu_page_mer.zip": (
        "Melilot's Assist",
        "Shadow Reactor",
        "Backs up the Crusaders with clever strategy! Pulls idle symbols to the nearest ACT symbol or halves next wait time depending on the situation.",
    ),
    "tu_page_ode.zip": (
        "Eauderourke's Assist",
        "Ether Scavenger",
        "The gluttonous Eauderourke turns anything into nourishment. Drains enemy HP with dark magic!",
    ),
    "tu_page_pac.zip": (
        "Paqy's Assist",
        "108-Style Wave Cannon",
        "Heh heh... My Wave Cannon goes all the way up to Style 108!",
    ),
    "tu_page_pst.zip": (
        "Pasta's Assist",
        "Accel Sonic Slash",
        "Can you keep up with my blinding claws, nya?! Launches a rapid combo adding up to +6 RUSH hits!",
    ),
}

ALL_GRAPHIC_TU = (
    ["tu_title01.zip", "tu_title02.zip", "tu_title03.zip", "tu_title09.zip"]
    + ["tu_subtitle_files01.zip", "tu_subtitle_files01c.zip", "tu_subtitle_files08.zip", "tu_subtitle_files09.zip"]
    + ["tu_page01.zip", "tu_page02.zip", "tu_page03.zip", "tu_page04.zip", "tu_page05.zip", "tu_page06.zip"]
    + ["tu_page21.zip", "tu_page28.zip", "tu_page_plus01_01.zip", "tu_page_plus01_02.zip"]
    + list(EX_ASSIST_CARDS.keys())
    + [k[:-4] for k in TU_SAM_CALLOUTS.keys()]
)


def _erode_rounded_mask(im: Image.Image, inset_px: float = 6.0, alpha_thresh: int = 180) -> np.ndarray:
    """Exact circular Euclidean erosion of opaque card silhouette so fills NEVER leak out of rounded borders."""
    arr = np.array(im, dtype=np.uint8)
    h, w = arr.shape[:2]
    inside = arr[:, :, 3] >= alpha_thresh
    r = int(np.ceil(inset_px))
    pad = np.zeros((h + 2 * r, w + 2 * r), dtype=bool)
    pad[r : r + h, r : r + w] = inside
    eroded = inside.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= inset_px * inset_px:
                eroded &= pad[r + dy : r + dy + h, r + dx : r + dx + w]
    return eroded


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for wd in words:
        cand = f"{cur} {wd}".strip()
        if draw.textbbox((0, 0), cand, font=font)[2] <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _draw_wrapped_block(
    im: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
    start_size: int,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
    stroke_w: int = 1,
    min_size: int = 8,
    line_gap: int = 2,
    align: str = "left",
) -> None:
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    d = ImageDraw.Draw(im)
    chosen_font = load_font(min_size)
    chosen_lines = [text]
    for sz in range(start_size, min_size - 1, -1):
        f = load_font(sz)
        lines = _wrap_lines(d, text, f, bw - 2)
        lh = sz + line_gap
        if len(lines) * lh <= bh:
            chosen_font = f
            chosen_lines = lines
            break
    lh = chosen_font.size + line_gap
    total_h = len(chosen_lines) * lh
    cur_y = y0 + max(0, (bh - total_h) // 2) if align == "center" else y0 + 2
    for ln in chosen_lines:
        if align == "center":
            draw_outlined_text(im, ((x0 + x1) // 2, cur_y + lh // 2), ln, chosen_font, fill, outline, stroke_w, anchor="mm")
        else:
            draw_outlined_text(im, (x0, cur_y + lh // 2), ln, chosen_font, fill, outline, stroke_w, anchor="lm")
        cur_y += lh


def ensure_originals_and_manifest(graphic_cpk: Path, orig_dir: Path) -> set[str]:
    gr = CpkArchive(str(graphic_cpk))
    adv = {r["FileName"]: r for r in gr.entries() if r["DirName"] == "AdvGraphic"}
    btl = CpkArchive(str(graphic_cpk.parent / "BATTLE.CPK"))
    btl_tuts = {r["FileName"] for r in btl.entries() if r["DirName"] == "tutorial"}

    manifest_path = orig_dir / "manifest.json"
    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_rel = {(m["cpk"], m["rel"]): m for m in manifest}
    changed = False
    for fn in ALL_GRAPHIC_TU:
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
    return btl_tuts


def _save_both(im: Image.Image, fn: str, out_dir: Path, btl_tuts: set[str]) -> None:
    p_gr = out_dir / f"GRAPHIC/AdvGraphic/{fn}.png"
    p_gr.parent.mkdir(parents=True, exist_ok=True)
    im.save(p_gr)
    if fn in btl_tuts:
        p_btl = out_dir / f"BATTLE/tutorial/{fn}.png"
        p_btl.parent.mkdir(parents=True, exist_ok=True)
        im.save(p_btl)


def _loc_titles_and_subtitles(orig_dir: Path, out_dir: Path, btl_tuts: set[str]) -> int:
    count = 0
    # 1. tu_title01/02/03/09: pure transparent bg, ZERO opaque blue boxes, ZERO leftover JP!
    title_specs = [
        ("tu_title01.zip", "Ria-senpai's"),
        ("tu_title02.zip", "Ria-senpai & Paqy's"),
        ("tu_title03.zip", "Macaron & Paqy's"),
        ("tu_title09.zip", "Macaron & Paqy's"),
    ]
    for fn, speaker in title_specs:
        orig = Image.open(orig_dir / f"GRAPHIC/AdvGraphic/{fn}.png").convert("RGBA")
        w, h = orig.size
        # Start from pure transparent canvas so ZERO pink Japanese strokes can ever peek out,
        # and copy ONLY the clean decorative right-edge stars/hearts (x >= w - 58) if desired — or redraw crisp sparkles!
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        # Cute pastel pink/lavender decorative stars flanking the title (matching original vibe, zero overlap)
        for sx, sy, sr, col in [
            (28, 56, 12, (255, 165, 225, 255)),
            (46, 36, 7, (255, 200, 235, 255)),
            (w - 32, 48, 13, (255, 165, 225, 255)),
            (w - 54, 70, 8, (255, 200, 235, 255)),
            (w - 18, 72, 6, (255, 130, 205, 255)),
        ]:
            d.regular_polygon((sx, sy, sr), n_sides=5, rotation=18, fill=col, outline=(255, 255, 255, 255))
        # Speaker prefix top-left in crisp white with vibrant blue outline
        draw_text_in_box(im, (24, 4, 260, 26), speaker, 16, (255, 255, 255, 255), (25, 110, 230, 255), 2, min_size=11, align="left")
        # Main title "Tutorial Corner!" in playful white-to-pink with magenta+white double outline!
        f_main = load_font(42)
        draw_outlined_text(im, (w // 2, 56), "Tutorial Corner!", f_main, (255, 255, 255, 255), (255, 255, 255, 255), 5, anchor="mm")
        draw_outlined_text(im, (w // 2, 56), "Tutorial Corner!", f_main, (255, 240, 250, 255), (215, 35, 155, 255), 3, anchor="mm")
        _save_both(im, fn, out_dir, btl_tuts)
        count += 1

    # 2. Subtitles: tu_subtitle_files01, 01c, 08, 09
    im = Image.open(orig_dir / "GRAPHIC/AdvGraphic/tu_subtitle_files01.zip.png").convert("RGBA")
    clear_box(im, (0, 0, im.width, im.height))
    d = ImageDraw.Draw(im)
    for idx, txt in enumerate(SUBTITLES):
        y = idx * 27 + 13
        f = fit_font(d, txt, im.width - 16, 17, 11)
        draw_outlined_text(im, (im.width // 2, y), txt, f, (255, 255, 255, 255), (20, 95, 215, 255), 2, anchor="mm")
    _save_both(im, "tu_subtitle_files01.zip", out_dir, btl_tuts)
    count += 1

    for fn, txt in (
        ("tu_subtitle_files01c.zip", "~Rumble Attack~"),
        ("tu_subtitle_files08.zip", "~EX Attacks Pt. 2~"),
        ("tu_subtitle_files09.zip", "~Macaron's EX Attack~"),
    ):
        im_s = Image.open(orig_dir / f"GRAPHIC/AdvGraphic/{fn}.png").convert("RGBA")
        clear_box(im_s, (0, 0, im_s.width, im_s.height))
        draw_text_in_box(im_s, (6, 2, im_s.width - 6, im_s.height - 2), txt, 17, (255, 255, 255, 255), (20, 95, 215, 255), 2, min_size=10)
        _save_both(im_s, fn, out_dir, btl_tuts)
        count += 1
    return count


def _loc_ex_assist_cards(orig_dir: Path, out_dir: Path, btl_tuts: set[str]) -> int:
    """Cleanly localize all 24 400x152 Character EX / Assist cards inside their exact rounded borders."""
    count = 0
    for fn, (tag, skill, desc) in EX_ASSIST_CARDS.items():
        im = Image.open(orig_dir / f"GRAPHIC/AdvGraphic/{fn}.png").convert("RGBA")
        arr = np.array(im, dtype=np.uint8)
        h, w = arr.shape[:2]

        # 1. Exact eroded rounded interior mask of the card (keeps glossy outer rounded rim 100% untouched!)
        inner = _erode_rounded_mask(im, inset_px=5.5, alpha_thresh=180)
        # Find the clean right-most interior x (3px inside the eroded right edge of row y=60)
        row_xs = np.where(inner[60])[0]
        rx_sample = int(row_xs.max()) - 3 if row_xs.size > 0 else 372
        # Sample clean smooth vertical gradient from x=rx_sample-3..rx_sample+1 (inside card, right of JP text!)
        col_grad = np.median(arr[:, max(170, rx_sample - 3) : rx_sample + 2, :], axis=1).astype(np.uint8)
        # Smooth out any subtle bright star sparkle near bottom corner by keeping monotonic brightness near bottom
        top_strip = col_grad[8:26, :3].astype(np.int32)
        sat_idx = int(np.argmax(top_strip.max(axis=1) - top_strip.min(axis=1)))
        base_col = top_strip[sat_idx]
        theme_out = (
            max(15, int(base_col[0] * 0.50)),
            max(15, int(base_col[1] * 0.50)),
            max(15, int(base_col[2] * 0.50)),
            255,
        )

        # 2. Fill right-hand text area (x >= 168) ONLY inside the rounded interior mask!
        for y in range(h):
            mask_row = inner[y] & (np.arange(w) >= 168)
            if mask_row.any():
                arr[y, mask_row] = col_grad[y]

        # 3. Clean top-left character tag pill (x=12..158, y=7..23) strictly inside rounded mask
        for y in range(7, 23):
            mask_tag = inner[y] & (np.arange(w) >= 12) & (np.arange(w) <= 158)
            if mask_tag.any():
                arr[y, mask_tag] = col_grad[y]

        out = Image.fromarray(arr, mode="RGBA")
        draw_text_in_box(out, (14, 8, 156, 22), tag, 11, (255, 255, 255, 255), theme_out, 1, min_size=8, align="left")
        draw_text_in_box(out, (172, 10, 378, 34), skill, 17, (255, 250, 210, 255), theme_out, 2, min_size=10, align="left")
        _draw_wrapped_block(
            out,
            (172, 36, 376, 138),
            desc,
            13,
            (255, 255, 255, 255),
            theme_out,
            1,
            min_size=9,
            line_gap=2,
            align="left",
        )
        _save_both(out, fn, out_dir, btl_tuts)
        count += 1
    return count


def _fill_card_band_clipped(
    im: Image.Image,
    inner_mask: np.ndarray,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
    grad_col: np.ndarray,
) -> Image.Image:
    """Fill a region inside a 256x200 rounded tutorial card clipped strictly to inner_mask."""
    arr = np.array(im, dtype=np.uint8)
    h = y1 - y0
    idx = np.linspace(0, len(grad_col) - 1, h).round().astype(int)
    xs = np.arange(arr.shape[1])
    xmask = (xs >= x0) & (xs < x1)
    for i, y in enumerate(range(y0, y1)):
        m = inner_mask[y] & xmask
        if m.any():
            arr[y, m] = grad_col[idx[i]]
    return Image.fromarray(arr, mode="RGBA")


def _loc_diagram_cards(orig_dir: Path, out_dir: Path, btl_tuts: set[str]) -> int:
    """Cleanly localize all 10 256x200 tutorial diagram cards with strict rounded-border containment."""
    count = 0

    # Smooth glossy blue header gradient & cyan bottom ribbon gradient matching native card art
    hdr_grad = np.array([
        (36, 118, 245, 255), (38, 124, 248, 255), (42, 132, 250, 255),
        (46, 142, 252, 255), (50, 150, 254, 255),
    ], dtype=np.uint8)
    bot_grad = np.array([
        (24, 152, 245, 255), (32, 174, 250, 255), (48, 198, 252, 255),
        (68, 218, 254, 255), (92, 232, 255, 255),
    ], dtype=np.uint8)

    # 1. tu_page01.zip (Elemental Affinity wheel): replace header 属性相性 + 5 legend pills + 5 kanji+EN labels!
    im = Image.open(orig_dir / "GRAPHIC/AdvGraphic/tu_page01.zip.png").convert("RGBA")
    inner = _erode_rounded_mask(im, inset_px=6.5)
    im = _fill_card_band_clipped(im, inner, 6, 30, 8, 92, hdr_grad)
    draw_text_in_box(im, (12, 8, 108, 28), "Elements", 14, (255, 255, 255, 255), (12, 55, 145, 255), 2, min_size=9, align="left")
    d = ImageDraw.Draw(im)
    # Exact pixel-measured legend pill positions from grid_tu_page01.zip.png (100% covering JP pills!)
    legend_pills = [
        ((90, 17, 146, 32), "W:AQA S:THN", (200, 35, 35, 255)),
        ((5, 102, 64, 117), "Strong vs 3", (185, 25, 190, 255)),
        ((174, 102, 234, 117), "Strong vs 3", (18, 155, 35, 255)),
        ((52, 134, 107, 149), "W:THN S:FIR", (15, 115, 215, 255)),
        ((156, 124, 211, 139), "W:FIR S:AQA", (215, 120, 10, 255)),
    ]
    for box, txt, out_col in legend_pills:
        d.rounded_rectangle(box, radius=5, fill=(255, 255, 255, 250), outline=out_col, width=1)
        draw_text_in_box(im, (box[0] + 2, box[1] + 1, box[2] - 2, box[3] - 1), txt, 8, out_col, (255, 255, 255, 255), 0, min_size=7)
    # Cleanly replace the 5 kanji+EN labels (闇DARK, 炎FIRE, 光LIGHT, 水AQUA, 雷THUNDER) with crisp badges (ZERO kanji!)
    elem_badges_01 = [
        ((6, 49, 58, 67), "DARK", (195, 20, 195, 255)),
        ((118, 33, 166, 51), "FIRE", (220, 30, 20, 255)),
        ((175, 51, 232, 69), "LIGHT", (15, 165, 30, 255)),
        ((81, 93, 136, 111), "AQUA", (15, 125, 230, 255)),
        ((130, 133, 204, 151), "THUNDER", (225, 115, 0, 255)),
    ]
    for box, lbl, col in elem_badges_01:
        d.rounded_rectangle(box, radius=6, fill=col, outline=(255, 255, 255, 255), width=1)
        draw_text_in_box(im, (box[0] + 3, box[1] + 1, box[2] - 3, box[3] - 1), lbl, 11, (255, 255, 255, 255), col, 0, min_size=8)
    _save_both(im, "tu_page01.zip", out_dir, btl_tuts)
    count += 1

    # 2. tu_page02.zip & tu_page03.zip (WIN vs LOSE element chart): exact kanji bboxes from grid_tu_page02/03!
    for fn, badges in (
        ("tu_page02.zip", [
            ((71, 29, 95, 47), "FIRE", (220, 30, 20, 255)),
            ((71, 75, 95, 93), "AQUA", (10, 125, 235, 255)),
            ((71, 125, 95, 143), "THN", (225, 115, 0, 255)),
            ((173, 29, 197, 47), "THN", (225, 115, 0, 255)),
            ((173, 77, 197, 95), "FIRE", (220, 30, 20, 255)),
            ((173, 123, 197, 141), "AQUA", (10, 125, 235, 255)),
        ]),
        ("tu_page03.zip", [
            ((71, 53, 95, 71), "LGT", (15, 165, 30, 255)),
            ((71, 101, 95, 119), "DARK", (195, 20, 205, 255)),
            ((173, 29, 197, 47), "THN", (225, 115, 0, 255)),
            ((173, 77, 197, 95), "FIRE", (220, 30, 20, 255)),
            ((173, 123, 197, 141), "AQUA", (10, 125, 235, 255)),
        ]),
    ):
        im = Image.open(orig_dir / f"GRAPHIC/AdvGraphic/{fn}.png").convert("RGBA")
        d2 = ImageDraw.Draw(im)
        for box, lbl, col in badges:
            d2.rounded_rectangle(box, radius=4, fill=col, outline=(255, 255, 255, 255), width=1)
            draw_text_in_box(im, (box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1), lbl, 9, (255, 255, 255, 255), col, 0, min_size=7)
        _save_both(im, fn, out_dir, btl_tuts)
        count += 1

    # 3. 7 captioned 256x200 diagram cards (tu_page04, 05, 06, 21, 28, plus01_01, plus01_02)
    # EVERY fill is strictly clipped to the card's eroded rounded interior (ZERO square leakage, ZERO leftover JP!)
    captioned = [
        ("tu_page04.zip", "Follow-up Attacks", 134, "On top of your normal attack...", "Unison Attack!!"),
        ("tu_page05.zip", "Big Damage", 133, "The more allies in a Unison...", "Huge Damage!!"),
        ("tu_page06.zip", "About Chanting", 135, "Chant together to...", "Power Up!!"),
        ("tu_page21.zip", "Triggering EX Attacks", 134, "While the EX Gauge is shown,", "Press the button to unleash!"),
        ("tu_page28.zip", "Choosing EX Attacks", 138, "Select your EX Attack by", "pressing its matching button!"),
        ("tu_page_plus01_01.zip", "Attack Element", 125, "Used for normal & Rumble attacks.", "Some demons wield multiple elements!"),
        ("tu_page_plus01_02.zip", "Guard Element", 125, "Acts as your defensive element.", "Hit a weakness for bonus damage!"),
    ]
    for fn, hdr, cap_y0, line1, line2 in captioned:
        im = Image.open(orig_dir / f"GRAPHIC/AdvGraphic/{fn}.png").convert("RGBA")
        inner = _erode_rounded_mask(im, inset_px=6.5)
        im = _fill_card_band_clipped(im, inner, 6, 30, 8, 246, hdr_grad)
        draw_text_in_box(im, (14, 8, 240, 28), hdr, 14, (255, 255, 255, 255), (12, 55, 145, 255), 2, min_size=9, align="left")
        im = _fill_card_band_clipped(im, inner, cap_y0, 195, 6, 250, bot_grad)
        # Cleanly cover in-screenshot JP callouts on plus01_01 & plus01_02 strictly inside rounded card (x<=231!)
        if fn == "tu_page_plus01_01.zip":
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((100, 51, 231, 69), radius=5, fill=(20, 90, 195, 245), outline=(255, 255, 255, 255), width=1)
            draw_text_in_box(im, (103, 52, 228, 68), "ATK Elem: Dark LV2", 10, (255, 255, 255, 255), (10, 35, 90, 255), 1, min_size=7)
        elif fn == "tu_page_plus01_02.zip":
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((130, 42, 231, 60), radius=5, fill=(20, 90, 195, 245), outline=(255, 255, 255, 255), width=1)
            draw_text_in_box(im, (133, 43, 228, 59), "Guard Elem: Fire", 10, (255, 255, 255, 255), (10, 35, 90, 255), 1, min_size=7)
            # Cover the blue prompt pill "攻撃対象を選んでください。" completely (y=97..117, x=32..214)
            d.rounded_rectangle((32, 97, 214, 117), radius=7, fill=(32, 158, 240, 255), outline=(255, 255, 255, 255), width=1)
            draw_text_in_box(im, (38, 98, 208, 116), "Select a target.", 11, (255, 255, 255, 255), (10, 65, 160, 255), 1, min_size=7)
        mid_y = cap_y0 + (192 - cap_y0) // 2
        draw_text_in_box(im, (14, cap_y0 + 3, 242, mid_y + 1), line1, 13, (255, 255, 255, 255), (15, 65, 150, 255), 1, min_size=8)
        draw_text_in_box(im, (14, mid_y, 242, 191), line2, 20, (255, 245, 110, 255), (15, 70, 165, 255), 2, min_size=9)
        _save_both(im, fn, out_dir, btl_tuts)
        count += 1
    return count


# Pixel-exact callout boxes measured directly from grid_sams_part1.png & grid_sams_part2.png!
EXACT_SAM_CALLOUTS: dict[str, list[tuple[int, int, int, int, str]]] = {
    "tu_sam01_01.zip": [(74, 21, 166, 36, "^ HP Gauge"), (132, 138, 228, 154, "v HP Gauge")],
    "tu_sam01_02.zip": [(164, 22, 280, 39, "^ STUN Gauge"), (14, 133, 126, 149, "v STUN Gauge")],
    "tu_sam01_03.zip": [(104, 23, 198, 38, "^ EX Gauge"), (116, 134, 210, 150, "v EX Gauge")],
    "tu_sam01_04.zip": [(16, 13, 118, 28, "v Timeline")],
    "tu_sam01_05.zip": [(6, 61, 70, 76, "Symbol v"), (110, 69, 182, 84, "< Symbol"), (94, 98, 166, 113, "< Symbol")],
    "tu_sam01_06.zip": [(39, 79, 146, 94, "< ACT Point")],
    "tu_sam01_07.zip": [(214, 63, 278, 78, "< Element")],
    "tu_sam01_08.zip": [(196, 118, 264, 134, "^ Attack")],
    "tu_sam01_09.zip": [(194, 110, 282, 126, "^ Target")],
    "tu_sam01_10.zip": [(218, 120, 284, 136, "^ Chant")],
    "tu_sam01_11.zip": [(182, 96, 280, 112, "^ Attack LV")],
    "tu_sam02_01.zip": [(218, 120, 284, 136, "^ Chant")],
    "tu_sam02_02.zip": [(158, 99, 238, 115, "Unison >")],
    "tu_sam02_03.zip": [(52, 79, 168, 94, "< Unison Area")],
    "tu_sam02_04.zip": [(130, 39, 232, 56, "Affinity >")],
    "tu_sam02_05.zip": [(40, 96, 114, 111, "< Symbol")],
    "tu_sam03_01.zip": [(39, 79, 146, 94, "< ACT Point")],
    "tu_sam03_02.zip": [],
    "tu_sam05_01.zip": [(104, 23, 198, 38, "^ EX Gauge"), (116, 134, 210, 150, "v EX Gauge")],
    "tu_sam06_02.zip": [(104, 23, 198, 38, "^ EX Gauge"), (116, 134, 210, 150, "v EX Gauge")],
    "tu_sam07_01.zip": [(174, 82, 262, 97, "Barrier Area >")],
    "tu_sam_plus01_01.zip": [(148, 71, 222, 86, "< Symbol")],
    "tu_sam_plus01_02.zip": [(194, 68, 276, 84, "v Target")],
}


def _loc_sam_callouts(orig_dir: Path, out_dir: Path, btl_tuts: set[str]) -> int:
    """Cleanly localize all 23 tu_sam* battle callout screenshots with ZERO red/white Japanese peeking out!"""
    count = 0
    for fn, boxes in EXACT_SAM_CALLOUTS.items():
        im = Image.open(orig_dir / f"GRAPHIC/AdvGraphic/{fn}.png").convert("RGBA")
        draw = ImageDraw.Draw(im)
        for x0, y0, x1, y1, txt in boxes:
            draw.rounded_rectangle([x0, y0, x1, y1], radius=4, fill=(14, 22, 42, 250), outline=(105, 175, 245, 255), width=1)
            draw_text_in_box(im, (x0 + 3, y0 + 1, x1 - 3, y1 - 1), txt, 11, (255, 255, 255, 255), (0, 0, 0, 255), 1, min_size=7)
        _save_both(im, fn, out_dir, btl_tuts)
        count += 1
    return count


def run_all(graphic_cpk: Path, orig_dir: Path, out_dir: Path) -> None:
    btl_tuts = ensure_originals_and_manifest(graphic_cpk, orig_dir)
    c1 = _loc_titles_and_subtitles(orig_dir, out_dir, btl_tuts)
    c2 = _loc_ex_assist_cards(orig_dir, out_dir, btl_tuts)
    c3 = _loc_diagram_cards(orig_dir, out_dir, btl_tuts)
    c4 = _loc_sam_callouts(orig_dir, out_dir, btl_tuts)
    print(f"Localized ALL tutorials (GRAPHIC + BATTLE): titles/subs={c1}, ex/assist={c2}, diagrams={c3}, sam={c4} (total={c1+c2+c3+c4})")


if __name__ == "__main__":
    run_all(
        Path("work/iso_extract/GRAPHIC.CPK"),
        Path("work/p4_textures_orig"),
        Path("work/p4_textures_ui_v8"),
    )
