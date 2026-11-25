"""Localize GAMEINIT.CPK/AdvZip location banners, time-of-day graphics, and trophy unlock banner.

Every layer of sys_pl_file001/002/003 is rendered strictly inside its exact patched
GraphicARC.bin (u, v, w, h) rectangle so zero characters are clipped and zero stray lines appear.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive
from cpk.tim2 import crilayla_decompress, decode_tm2, unwrap_texture

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch_graphic_arc import patch_graphic_arc_bytes, read_sys_pl_layout
from render_helpers import clear_box, draw_gradient_outlined_text, draw_text_in_box, load_font


ADVZIP_NAMES = (
    "sys_pl_file001.zip",
    "sys_pl_file002.zip",
    "sys_pl_file003.zip",
    "trophy_f.zip",
)

# All 45 GraphicARC place IDs -> (title, optional subtitle override)
# Subtitles stay None to preserve native English subtitles where clean & non-duplicate,
# or override cleanly where native text had typos (Kujyo, Ryusei, Macaroon) or duplicated the title.
PLACE_LABELS: dict[str, tuple[str, str | None]] = {
    # sys_pl_file001.zip (22 locations)
    "001": ("Council Room", "Student Council"),
    "002": ("Old Hallway", None),             # Corridor-Oroiael-
    "003": ("Lolotte's Class", None),         # Lolotte's ClassRoom
    "004": ("Synn's Class", None),            # Synn's ClassRoom
    "005": ("Ria's Class", None),             # Ria's ClassRoom
    "205": ("School Route", None),            # School Zone
    "006": ("New Hallway", None),             # Corridor-Eleleth-
    "007": ("New Bldg Entrance", None),       # Entrance-Eleleth-
    "008": ("Academy Library", None),         # Library
    "009": ("Library Interior", "Ryuusei Library"),
    "010": ("Cafeteria Prier", None),         # Cafeteria-Prier-
    "011": ("Chairwoman's Office", "Chairwoman Room"),
    "012": ("Academy Grounds", "Ryuusei Academy"),
    "013": ("Academy Courtyard", None),       # Courtyard
    "014": ("Ryuusei Academy", None),         # School Building (no longer repeats "School Building"!)
    "015": ("Academy Gate", None),            # School Gate
    "016": ("St. Ophelia's Church", None),    # St.Ophelia's Church -> let's differentiate cleanly!
    "017": ("Church Interior", None),         # St.Ophelia's Church Interior
    "018": ("Kujou Estate", "Kujou Residence"),
    "019": ("Student Dorms", None),           # Student Dormitory
    "020": ("Indoor Pool", None),             # Indoor Swimming Pool
    "021": ("Culture Hall", "Ryuusei Hall"),
    # sys_pl_file002.zip (23 locations)
    "022": ("Athletic Field", None),          # Ground
    "023": ("Hilltop Plaza", None),           # High Place Square
    "024": ("Finis Tower", None),             # Tower-Finis-
    "050": ("Shio's Class", None),            # Shio's ClassRoom
    "051": ("Misa's Class", None),            # Misa's ClassRoom
    "100": ("Shiokumi Gate", None),           # Shopping Arcade
    "101": ("Shiokumi Street", None),         # Shopping Street
    "102": ("Yuugiri-an", None),              # Soba Shop Yuugiri-an
    "201": ("Grand Palace Entry", "Sakura Entrance"),
    "104": ("Tsukinoo Park", "Ryuusei Town"),
    "200": ("Grand Palace Sakura", "Sakura Residence"),
    "202": ("Grand Palace Kitchen", "Sakura Kitchen"),
    "103": ("Chocolat l'Or", "Sweets Shop"),
    "204": ("Residential Area", None),        # Residential Street
    "206": ("Asukai Shrine", None),           # Shrine Grounds
    "207": ("Mihoshizaka", None),             # Mihoshizaka Park
    "203": ("Synn's Room", "Sakura Home"),
    "402": ("Demon World", None),             # The Darkness
    "208": ("Azel's Room", "Dorm Room"),
    "301": ("Witch World", None),             # A Witch's World
    "209": ("Macaron's Room", "Macaron Room"),
    "400": ("Melilot's Room", "Tower Room"),
    "403": ("Nive Territory", "Region of Nive"),
}
# Make St. Ophelia's Church distinct from subtitle "St.Ophelia's Church"
PLACE_LABELS["016"] = ("Church Grounds", None)

# All 9 GraphicARC time IDs (sys_pl_file003.zip)
TIME_LABELS: dict[str, str] = {
    "001": "Early Morn",
    "002": "Morning",
    "003": "Lunchtime",
    "004": "Noon",
    "005": "Afternoon",
    "006": "After School",
    "007": "Evening",
    "008": "Night",
    "009": "Late Night",
}


def _make_soft_glow(src_alpha: np.ndarray, rgb: tuple[int, int, int], alpha_scale: float = 0.72) -> Image.Image:
    h, w = src_alpha.shape
    ga = np.zeros((h, w, 4), dtype=np.uint8)
    ga[:, :, 0] = rgb[0]
    ga[:, :, 1] = rgb[1]
    ga[:, :, 2] = rgb[2]
    ga[:, :, 3] = (src_alpha.astype(np.float32) * alpha_scale).astype(np.uint8)
    return Image.fromarray(ga, mode="RGBA").filter(ImageFilter.GaussianBlur(radius=0.6))


def _make_crisp_shadow(src_alpha: np.ndarray, rgb: tuple[int, int, int] = (112, 125, 242), alpha_scale: float = 0.85) -> np.ndarray:
    """Create a clean, non-blocky drop shadow directly from the text silhouette (no fat MaxFilter blobbing!)."""
    soft = np.array(Image.fromarray(src_alpha, mode="L").filter(ImageFilter.GaussianBlur(radius=0.35)), dtype=np.float32)
    comb = np.clip(np.maximum(src_alpha.astype(np.float32) * 0.78, soft * 0.92) * alpha_scale, 0, 255).astype(np.uint8)
    rgba = np.zeros((src_alpha.shape[0], src_alpha.shape[1], 4), dtype=np.uint8)
    rgba[:, :, 0] = rgb[0]
    rgba[:, :, 1] = rgb[1]
    rgba[:, :, 2] = rgb[2]
    rgba[:, :, 3] = comb
    return rgba


def _render_place_exact(
    im: Image.Image,
    orig_arr: np.ndarray,
    layers: dict[str, dict],
    title: str,
    subtitle: str | None,
) -> None:
    """Render all 5 layers of a place banner strictly inside its exact patched GraphicARC.bin (u,v,w,h) boxes."""
    jb = layers["jb"]
    jf = layers["jf"]
    eb = layers["eb"]
    ef = layers["ef"]
    sh = layers["sh"]

    # Clear Title (jb), Title glow (jf), and full Shadow band (sh, including 1px margin above to wipe stray y0+64!)
    clear_box(im, (jb["u"], max(0, jb["v"] - 1), jb["u"] + jb["w"], jb["v"] + jb["h"] + 1))
    clear_box(im, (jf["u"], max(0, jf["v"] - 1), jf["u"] + jf["w"], jf["v"] + jf["h"] + 1))
    clear_box(im, (sh["u"], max(0, sh["v"] - 2), sh["u"] + sh["w"], min(im.height, sh["v"] + sh["h"] + 4)))

    # 1. Crisp Title inside exact (jb.u, jb.v, jb.w, jb.h)
    tw, th = jb["w"], jb["h"]
    t_layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    draw_text_in_box(
        t_layer,
        (1, 0, tw - 1, th),
        title,
        14,
        (255, 255, 255, 255),
        (28, 116, 248, 255),
        1,
        min_size=7,
    )
    im.alpha_composite(t_layer, (jb["u"], jb["v"]))

    # 2. Soft cyan Title glow inside exact (jf.u, jf.v, jf.w, jf.h)
    t_alpha = np.array(t_layer, dtype=np.uint8)[:, :, 3]
    im.alpha_composite(_make_soft_glow(t_alpha, (215, 248, 255), 0.72), (jf["u"], jf["v"]))

    # 3 & 4. Subtitle inside exact (eb.u, eb.v, eb.w, eb.h) & (ef.u, ef.v, ef.w, ef.h)
    if subtitle is not None:
        clear_box(im, (eb["u"], max(0, eb["v"] - 1), eb["u"] + eb["w"], eb["v"] + eb["h"] + 1))
        clear_box(im, (ef["u"], max(0, ef["v"] - 1), ef["u"] + ef["w"], ef["v"] + ef["h"] + 1))
        sw, sh_sub = eb["w"], eb["h"]
        s_layer = Image.new("RGBA", (sw, sh_sub), (0, 0, 0, 0))
        draw_text_in_box(
            s_layer,
            (1, 0, sw - 1, sh_sub),
            subtitle,
            9,
            (255, 255, 255, 255),
            (28, 116, 248, 255),
            1,
            min_size=6,
        )
        im.alpha_composite(s_layer, (eb["u"], eb["v"]))
        s_alpha = np.array(s_layer, dtype=np.uint8)[:, :, 3]
        im.alpha_composite(_make_soft_glow(s_alpha, (215, 248, 255), 0.68), (ef["u"], ef["v"]))
    else:
        # Preserve native English subtitle pixels verbatim; sample its alpha for shadow
        s_alpha = orig_arr[eb["v"] : eb["v"] + eb["h"], eb["u"] : eb["u"] + eb["w"], 3].copy()

    # 5. Crisp drop shadow inside exact (sh.u, sh.v, sh.w, sh.h) aligned to true screen offsets!
    sh_canvas = np.zeros((sh["h"], sh["w"], 4), dtype=np.uint8)
    # Place title shadow at relative screen offset (jb.sx - sh.sx, 0)
    dx_t = int(round(jb["sx"] - sh["sx"]))
    t_sh_rgba = _make_crisp_shadow(t_alpha)
    for y in range(min(t_sh_rgba.shape[0], sh["h"])):
        for x in range(t_sh_rgba.shape[1]):
            tx = x + dx_t
            if 0 <= tx < sh["w"] and t_sh_rgba[y, x, 3] > sh_canvas[y, tx, 3]:
                sh_canvas[y, tx] = t_sh_rgba[y, x]

    # Place subtitle shadow at relative screen offset (eb.sx - sh.sx, eb.sy - sh.sy)
    dx_s = int(round(eb["sx"] - sh["sx"]))
    dy_s = max(0, int(round(eb["sy"] - sh["sy"])))
    s_sh_rgba = _make_crisp_shadow(s_alpha)
    for y in range(s_sh_rgba.shape[0]):
        ty = y + dy_s
        if 0 <= ty < sh["h"]:
            for x in range(s_sh_rgba.shape[1]):
                tx = x + dx_s
                if 0 <= tx < sh["w"] and s_sh_rgba[y, x, 3] > sh_canvas[ty, tx, 3]:
                    sh_canvas[ty, tx] = s_sh_rgba[y, x]

    im.alpha_composite(Image.fromarray(sh_canvas, mode="RGBA"), (sh["u"], sh["v"]))


def _render_time_exact(im: Image.Image, layers: dict[str, dict], label: str) -> None:
    """Render all 3 layers of a time-of-day graphic strictly inside its exact patched GraphicARC.bin UV boxes."""
    tb = layers["tb"]
    tf = layers["tf"]
    sh = layers["sh"]

    w, h = tb["w"], tb["h"]
    c_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_text_in_box(
        c_layer,
        (1, 0, w - 1, h),
        label,
        13,
        (255, 255, 255, 255),
        (28, 116, 248, 255),
        1,
        min_size=8,
    )
    im.alpha_composite(c_layer, (tb["u"], tb["v"]))

    ca = np.array(c_layer, dtype=np.uint8)[:, :, 3]
    im.alpha_composite(_make_soft_glow(ca, (165, 195, 252), 0.78), (tf["u"], tf["v"]))

    # Shadow layer at exact (sh.u, sh.v, sh.w, sh.h) — crisp, non-blocky!
    sh_rgba = _make_crisp_shadow(ca, (115, 130, 242), 0.85)
    sh_crop = sh_rgba[: sh["h"], : sh["w"]]
    im.alpha_composite(Image.fromarray(sh_crop, mode="RGBA"), (sh["u"], sh["v"]))


def ensure_originals_and_manifest(gameinit_cpk: Path, orig_dir: Path) -> None:
    gi = CpkArchive(str(gameinit_cpk))
    adv = {r["FileName"]: r for r in gi.entries() if r["DirName"] == "AdvZip"}
    manifest_path = orig_dir / "manifest.json"
    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_rel = {(m["cpk"], m["rel"]): m for m in manifest}
    changed = False
    for fn in ADVZIP_NAMES:
        rel = f"AdvZip/{fn}"
        png_rel = f"GAMEINIT/AdvZip/{fn}.png"
        dst = orig_dir / png_rel
        tm2, _, _ = unwrap_texture(gi.read_entry(adv[fn]), fn)
        im = decode_tm2(tm2)
        if not dst.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst)
        if ("GAMEINIT", rel) not in by_rel:
            manifest.append({"cpk": "GAMEINIT", "rel": rel, "png": png_rel, "w": im.width, "h": im.height})
            changed = True
    if changed:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def localize_place_and_time(
    orig_dir: Path,
    out_dir: Path,
    gameinit_cpk: Path = Path("work/iso_extract/GAMEINIT.CPK"),
) -> int:
    gi = CpkArchive(str(gameinit_cpk))
    gr_raw = crilayla_decompress(gi.read_entry([r for r in gi.entries() if r["FileName"] == "GraphicARC.bin"][0]))
    gr_patched, _ = patch_graphic_arc_bytes(gr_raw)
    places, times = read_sys_pl_layout(gr_patched)

    count = 0

    # 1 & 2. sys_pl_file001.zip & sys_pl_file002.zip (driven 100% by exact patched GraphicARC.bin UVs!)
    imgs = {
        "sys_pl_file001": Image.open(orig_dir / "GAMEINIT/AdvZip/sys_pl_file001.zip.png").convert("RGBA"),
        "sys_pl_file002": Image.open(orig_dir / "GAMEINIT/AdvZip/sys_pl_file002.zip.png").convert("RGBA"),
    }
    orig_arrs = {k: np.array(v, dtype=np.uint8) for k, v in imgs.items()}

    # Clear ALL Japanese title / title-glow / shadow bands cleanly across both sheets first so ZERO stray slivers remain!
    for k, im in imgs.items():
        for row_y in range(0, im.height, 96):
            clear_box(im, (0, row_y, im.width, row_y + 40))
            clear_box(im, (0, row_y + 62, im.width, min(im.height, row_y + 96)))

    for pid, (title, sub_ovr) in PLACE_LABELS.items():
        layers = places[pid]
        tex_key = layers["jb"]["tex"]
        _render_place_exact(imgs[tex_key], orig_arrs[tex_key], layers, title, sub_ovr)

    for tex_key, im in imgs.items():
        rel = f"GAMEINIT/AdvZip/{tex_key}.zip.png"
        (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        im.save(out_dir / rel)
        count += 1

    # 3. sys_pl_file003.zip (start from pure transparent canvas -> ZERO stray JP slivers!)
    rel3 = "GAMEINIT/AdvZip/sys_pl_file003.zip.png"
    orig3 = Image.open(orig_dir / rel3).convert("RGBA")
    im3 = Image.new("RGBA", orig3.size, (0, 0, 0, 0))
    for tid, label in TIME_LABELS.items():
        _render_time_exact(im3, times[tid], label)
    im3.save(out_dir / rel3)
    count += 1

    # 4. trophy_f.zip (480x104): keep "Congratulations!!" (y=0..32), replace "トロフィーゲット!" (y=34..104)
    rel4 = "GAMEINIT/AdvZip/trophy_f.zip.png"
    im4 = Image.open(orig_dir / rel4).convert("RGBA")
    clear_box(im4, (0, 34, 480, 104))
    p = Path("C:/Windows/Fonts/segoeuib.ttf")
    f_tr = ImageFont.truetype(str(p), 44) if p.is_file() else load_font(44)
    draw_gradient_outlined_text(
        im4,
        (240, 68),
        "Trophy Unlocked!!",
        f_tr,
        (255, 255, 255, 255),
        (255, 195, 235, 255),
        (235, 35, 155, 255),
        3,
        anchor="mm",
    )
    im4.save(out_dir / rel4)
    count += 1
    return count


def run_all(gameinit_cpk: Path, orig_dir: Path, out_dir: Path) -> None:
    ensure_originals_and_manifest(gameinit_cpk, orig_dir)
    n = localize_place_and_time(orig_dir, out_dir, gameinit_cpk)
    print(f"Localized GAMEINIT/AdvZip place/time/trophy textures (GraphicARC-exact): {n}")


if __name__ == "__main__":
    run_all(
        Path("work/iso_extract/GAMEINIT.CPK"),
        Path("work/p4_textures_orig"),
        Path("work/p4_textures_ui_v8"),
    )
