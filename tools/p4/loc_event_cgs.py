"""Localize untranslated Japanese-text event CG overlays in GRAPHIC.CPK/AdvGraphic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive
from cpk.tim2 import decode_tm2, unwrap_texture

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_helpers import clear_box, draw_gradient_outlined_text, draw_outlined_text, draw_text_in_box, load_font


EVENT_CG_NAMES = ("C006a.zip", "C006b10.zip", "C003_a.zip")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    p = Path("C:/Windows/Fonts") / name
    if p.is_file():
        return ImageFont.truetype(str(p), size)
    return load_font(size)


def _draw_rotated_handwritten(
    im: Image.Image,
    center: tuple[int, int],
    lines: list[str],
    size: int,
    angle: float = 3.0,
    fill: tuple[int, int, int, int] = (28, 22, 26, 255),
) -> None:
    """Render handwritten tilted multi-line marker text using 4x supersampling."""
    scale = 4
    f = _font("segoeprb.ttf", size * scale)
    tmp = Image.new("RGBA", (im.width * scale, im.height * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    line_h = int(size * scale * 1.15)
    start_y = int(center[1] * scale - (len(lines) - 1) * line_h / 2)
    for idx, line in enumerate(lines):
        d.text((center[0] * scale, start_y + idx * line_h), line, font=f, fill=fill, anchor="mm")
    rot = tmp.rotate(angle, resample=Image.Resampling.BICUBIC, center=(center[0] * scale, center[1] * scale))
    small = rot.resize(im.size, Image.Resampling.LANCZOS)
    im.alpha_composite(small)


def _repaint_paqy_sign(im: Image.Image, sign_box: tuple[int, int, int, int]) -> None:
    """Cleanly erase dark kanji ink inside Paqy's cardboard sign while preserving the pink heart & black outline."""
    x0, y0, x1, y1 = sign_box
    arr = np.array(im, dtype=np.uint8)
    sub = arr[y0:y1, x0:x1]
    # Preserve pink heart pixels (high R, noticeably lower G/B) and replace dark ink (low R,G,B) with cream paper
    r = sub[:, :, 0].astype(np.int16)
    g = sub[:, :, 1].astype(np.int16)
    b = sub[:, :, 2].astype(np.int16)
    a = sub[:, :, 3]
    is_pink = (r - g > 25) & (r > 160)
    is_ink = (a > 128) & (~is_pink) & ((r < 230) | (g < 225) | (b < 220))
    # Sample median clean paper color inside sign_box
    clean = (a > 240) & (~is_pink) & (r >= 240) & (g >= 235) & (b >= 230)
    paper = np.median(sub[clean], axis=0).astype(np.uint8) if clean.any() else np.array([251, 249, 244, 255], dtype=np.uint8)
    sub[is_ink] = paper
    arr[y0:y1, x0:x1] = sub
    im.paste(Image.fromarray(arr[y0:y1, x0:x1], mode="RGBA"), (x0, y0))


def ensure_originals_and_manifest(graphic_cpk: Path, orig_dir: Path) -> None:
    """Extract event CG originals and register them idempotently in orig_dir/manifest.json."""
    gr = CpkArchive(str(graphic_cpk))
    adv = {r["FileName"]: r for r in gr.entries() if r["DirName"] == "AdvGraphic"}
    manifest_path = orig_dir / "manifest.json"
    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_rel = {(m["cpk"], m["rel"]): m for m in manifest}
    changed = False
    for fn in EVENT_CG_NAMES:
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


def localize_event_cgs(orig_dir: Path, out_dir: Path) -> int:
    count = 0

    # 1. C006a.zip (224x152): Paqy holding "見せられないゼ ♡" sign
    rel = "GRAPHIC/AdvGraphic/C006a.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    # Sign interior stays well inside black border (x=114..206, y=54..116), avoiding Paqy's paw & heart
    _repaint_paqy_sign(im, (118, 54, 206, 114))
    _draw_rotated_handwritten(im, (158, 82), ["Can't show", "this!"], size=14, angle=3.5)
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 2. C006b10.zip (336x232): Full censor overlay ("ごめんなさい" + Paqy sign + apology subtitle)
    rel = "GRAPHIC/AdvGraphic/C006b10.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    # Top "ごめんなさい" (y=0..46) -> playful rounded pink "I'm Sorry!" with crisp white outline
    clear_box(im, (0, 0, 336, 46))
    f_sorry = _font("comicbd.ttf", 34)
    draw_outlined_text(
        im,
        (168, 22),
        "I'm Sorry!",
        f_sorry,
        (235, 25, 138, 255),
        (255, 255, 255, 255),
        3,
        anchor="mm",
    )
    # Sign interior (x=175..266, y=104..166) -> "Can't show / this!" keeping heart & black outline intact
    _repaint_paqy_sign(im, (176, 104, 265, 165))
    _draw_rotated_handwritten(im, (216, 132), ["Can't show", "this!"], size=14, angle=3.5)
    # Bottom subtitle (y=212..232) -> "We apologize for the unsightly content."
    clear_box(im, (0, 212, 336, 232))
    draw_text_in_box(
        im,
        (10, 213, 326, 231),
        "We apologize for the unsightly content.",
        13,
        (255, 255, 255, 255),
        (15, 15, 20, 255),
        2,
        min_size=9,
    )
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1

    # 3. C003_a.zip (480x272): "Congratulations!! / キラフェス開催 / おめでとう"
    rel = "GRAPHIC/AdvGraphic/C003_a.zip.png"
    im = Image.open(orig_dir / rel).convert("RGBA")
    # Keep "Congratulations!!" (y=0..82) intact; replace JP lines (y=83..245)
    clear_box(im, (0, 83, 480, 250))
    f_big = _font("segoeuib.ttf", 48)
    draw_gradient_outlined_text(
        im,
        (240, 128),
        "Happy KiraFes",
        f_big,
        (255, 255, 255, 255),
        (255, 195, 235, 255),
        (235, 35, 155, 255),
        3,
        anchor="mm",
    )
    draw_gradient_outlined_text(
        im,
        (240, 194),
        "Opening!!",
        f_big,
        (255, 255, 255, 255),
        (255, 195, 235, 255),
        (235, 35, 155, 255),
        3,
        anchor="mm",
    )
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_dir / rel)
    count += 1
    return count


def run_all(graphic_cpk: Path, orig_dir: Path, out_dir: Path) -> None:
    ensure_originals_and_manifest(graphic_cpk, orig_dir)
    n = localize_event_cgs(orig_dir, out_dir)
    print(f"Localized event CGs: {n}")


if __name__ == "__main__":
    run_all(
        Path("work/iso_extract/GRAPHIC.CPK"),
        Path("work/p4_textures_orig"),
        Path("work/p4_textures_ui_v8"),
    )
