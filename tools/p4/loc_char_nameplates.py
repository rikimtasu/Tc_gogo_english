"""Localize all 54 character introduction nameplates (27 color + 27 _Child) in GRAPHIC.CPK/AdvGraphic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive
from cpk.tim2 import decode_tm2, unwrap_texture

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_helpers import clear_box, draw_text_in_box


# All 27 character nameplates: base_id -> (role_header_en, full_name_en)
# Checked directly against sheet_c_names.png and glossary/gpt_dict_characters.txt.
CHAR_NAMEPLATES: dict[str, tuple[str, str]] = {
    "C_NAME_A1": ("Ryuusei Council Treasurer (2nd Yr)", "Nanaka Yuugiri"),
    "C_NAME_A2": ("Ryuusei Council Secretary (1st Yr)", "Lolotte Rosenkreuz"),
    "C_NAME_A3": ("Ryuusei Council Vice-Pres (2nd Yr)", "Misa B. Cristelis"),
    "C_NAME_A4": ("Former Council President (3rd Yr)", "Ria Kujou"),
    "C_NAME_A5": ("Transfer Student from Sharo-Ma", "Azel"),
    "C_NAME_A6": ("Idol of the Demon World (?)", "Sally-chan"),
    "C_NAME_A7": ("Ryuusei Academy 1st Year", "Shio Asukai"),
    "C_NAME_A8": ("Ryuusei Academy Chairwoman", "Helena Kujou"),
    "C_NAME_A9": ("Lolotte's Childhood Friend", "Amyrina"),
    "C_NAME_AA": ("Great Sage of Old", "Paqy-sama"),
    "C_NAME_AB": ("Rosenkreuz Family Butler", "Riesling Tooyama"),
    "C_NAME_AC": ("Ryuusei Academy Librarian", "Melilot"),
    "C_NAME_AD": ("Ryuusei Academy 2nd Year", "Sacchin"),
    "C_NAME_AE": ("Ryuusei Academy 3rd Year", "Akane Misasagi"),
    "C_NAME_AF": ("Chocolat l'Or Ryuusei Owner", "Fuyuka Anenokouji"),
    "C_NAME_AG": ("Seven Demon Generals: Gluttony", "Eauderourke"),
    "C_NAME_AH": ("Seven Demon Generals: Lust", "Melphas"),
    "C_NAME_AJ": ("Seven Demon Generals: Greed", "Pasta"),
    "C_NAME_AJx": ("Prier's Rookie Waitress", "Pasta"),
    "C_NAME_AK": ("Seven Demon Generals: Envy", "Soltia"),
    "C_NAME_AKx": ("Student Teacher", "Kiyora Sengen'in"),
    "C_NAME_AL": ("Seven Demon Generals: Wrath", "Arden"),
    "C_NAME_AM": ("Seven Demon Generals: Pride", "Bylous"),
    "C_NAME_AU": ("Sakura Household Rooster", "Sasami"),
    "C_NAME_B1": ("???", "Macaron"),
    "C_NAME_B1X": ("Demon Lord (Apprentice)", "Macaron"),
    "C_NAME_B2": ("Carrier Bat", "Kyuu-chan"),
}


def _sample_colors(arr: np.ndarray) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Sample saturated outline color and light fill color from an original C_NAME nameplate."""
    opaque = arr[arr[:, :, 3] > 200]
    if opaque.size == 0:
        return (230, 245, 255, 255), (20, 120, 235, 255)
    rgb = opaque[:, :3].astype(np.int32)
    sat = rgb.max(axis=1) - rgb.min(axis=1)
    bright = rgb.mean(axis=1)
    # Outline: highest saturation pixels
    out_mask = sat >= max(40, int(np.percentile(sat, 75)))
    outline_rgb = np.median(rgb[out_mask], axis=0).astype(int) if out_mask.any() else np.array([25, 130, 235])
    # Fill: brightest pixels (pastel white/cream/pink/mint)
    fill_mask = bright >= int(np.percentile(bright, 88))
    fill_rgb = np.median(rgb[fill_mask], axis=0).astype(int) if fill_mask.any() else np.array([255, 255, 255])
    # Ensure high contrast between fill and outline
    if float(np.linalg.norm(fill_rgb - outline_rgb)) < 60:
        fill_rgb = np.clip((fill_rgb + 255) // 2, 225, 255)
    return (
        (int(fill_rgb[0]), int(fill_rgb[1]), int(fill_rgb[2]), 255),
        (int(outline_rgb[0]), int(outline_rgb[1]), int(outline_rgb[2]), 255),
    )


def _find_star_margins(arr: np.ndarray) -> tuple[int, int]:
    """Locate inner x-bounds between the left and right flanking star clusters."""
    h, w = arr.shape[:2]
    # Look at the name band (y=20..52) for connected x-runs; stars are 3 small blobs on left & right
    band = arr[18 : min(h, 54), :, 3] > 40
    col = band.any(axis=0)
    runs: list[tuple[int, int]] = []
    in_r, s = False, 0
    for x, v in enumerate(col):
        if v and not in_r:
            s = x
            in_r = True
        elif not v and in_r:
            runs.append((s, x))
            in_r = False
    if in_r:
        runs.append((s, w))
    # Left stars: up to 3 narrow runs (w<=26, allowing two close stars) on left; right stars on right
    left_end = 0
    for a, b in runs[:3]:
        if b - a <= 26 and b < w * 0.45:
            left_end = b + 2
        else:
            break
    right_start = w
    for a, b in reversed(runs[-3:]):
        if b - a <= 26 and a > w * 0.55:
            right_start = a - 2
        else:
            break
    # Only fall back if stars weren't separated properly and left almost no center room
    if right_start - left_end < 80:
        left_end = min(left_end, int(w * 0.25))
        right_start = max(right_start, int(w * 0.75))
    return left_end, right_start


def ensure_originals_and_manifest(graphic_cpk: Path, orig_dir: Path) -> None:
    gr = CpkArchive(str(graphic_cpk))
    adv = {r["FileName"]: r for r in gr.entries() if r["DirName"] == "AdvGraphic"}
    manifest_path = orig_dir / "manifest.json"
    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_rel = {(m["cpk"], m["rel"]): m for m in manifest}
    changed = False
    for base in CHAR_NAMEPLATES:
        for suffix in (".zip", "_Child.zip"):
            fn = f"{base}{suffix}"
            rel = f"AdvGraphic/{fn}"
            png_rel = f"GRAPHIC/AdvGraphic/{fn}.png"
            dst = orig_dir / png_rel
            tm2, _, _ = unwrap_texture(gr.read_entry(adv[fn]), fn)
            im = decode_tm2(tm2)
            if not dst.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                im.save(dst)
            if ("GRAPHIC", rel) not in by_rel:
                manifest.append({
                    "cpk": "GRAPHIC",
                    "rel": rel,
                    "png": png_rel,
                    "w": im.width,
                    "h": im.height,
                })
                changed = True
    if changed:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def localize_char_nameplates(orig_dir: Path, out_dir: Path) -> int:
    count = 0
    for base, (role, name) in CHAR_NAMEPLATES.items():
        # 1. Color nameplate (C_NAME_XX.zip)
        rel_main = f"GRAPHIC/AdvGraphic/{base}.zip.png"
        im = Image.open(orig_dir / rel_main).convert("RGBA")
        w, h = im.size
        orig_arr = np.array(im, dtype=np.uint8)
        fill_col, out_col = _sample_colors(orig_arr)
        lx, rx = _find_star_margins(orig_arr)

        # Preserve flanking stars on left (0..lx) and right (rx..w) in the name band; clear role row + center name + ruby
        clear_box(im, (0, 0, w, 20))
        clear_box(im, (lx, 18, rx, h))
        if h >= 68:
            # Clear bottom furigana row across full width (stars are above y=52)
            clear_box(im, (0, 54, w, h))

        # Role header at top (y=2..19)
        role_pad = 6
        draw_text_in_box(
            im,
            (role_pad, 2, w - role_pad, 19),
            role,
            13,
            (255, 255, 255, 255),
            out_col,
            1,
            min_size=7,
        )
        # Main character name centered between left & right stars (y=20..54)
        name_y1 = 56 if h >= 68 else 53
        draw_text_in_box(
            im,
            (lx + 2, 20, rx - 2, name_y1),
            name,
            26,
            fill_col,
            out_col,
            2,
            min_size=10,
        )
        (out_dir / rel_main).parent.mkdir(parents=True, exist_ok=True)
        im.save(out_dir / rel_main)
        count += 1

        # 2. Monochrome Child silhouette (C_NAME_XX_Child.zip: half width, 2 stacked copies on black)
        rel_child = f"GRAPHIC/AdvGraphic/{base}_Child.zip.png"
        orig_child = Image.open(orig_dir / rel_child).convert("RGBA")
        cw, ch = orig_child.size
        half_h = ch // 2
        # Build white-on-black alpha silhouette from the newly rendered color nameplate
        alpha = np.array(im, dtype=np.uint8)[:, :, 3]
        sil = Image.fromarray(alpha, mode="L").resize((cw, half_h), Image.Resampling.LANCZOS)
        sil_glow = sil.filter(ImageFilter.GaussianBlur(radius=0.8))
        comb_l = np.clip(np.maximum(np.array(sil, dtype=np.float32), np.array(sil_glow, dtype=np.float32) * 0.9), 0, 255).astype(np.uint8)
        child_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
        child_arr[:, :, 3] = 255
        # Stack crisp silhouette in top half and slightly brighter copy in bottom half (matching original)
        for ch_idx in range(3):
            child_arr[0:half_h, :, ch_idx] = (comb_l.astype(np.float32) * 0.85).astype(np.uint8)
            child_arr[half_h : half_h * 2, :, ch_idx] = comb_l
        Image.fromarray(child_arr, mode="RGBA").save(out_dir / rel_child)
        count += 1
    return count


def run_all(graphic_cpk: Path, orig_dir: Path, out_dir: Path) -> None:
    ensure_originals_and_manifest(graphic_cpk, orig_dir)
    n = localize_char_nameplates(orig_dir, out_dir)
    print(f"Localized C_NAME character nameplates: {n}")


if __name__ == "__main__":
    run_all(
        Path("work/iso_extract/GRAPHIC.CPK"),
        Path("work/p4_textures_orig"),
        Path("work/p4_textures_ui_v8"),
    )
