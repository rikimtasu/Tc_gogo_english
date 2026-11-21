"""Build Inrond PSP Latin bitmap fonts while preserving the original Japanese glyphs."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive  # noqa: E402
from cpk import crilayla  # noqa: E402


DEFAULT_TTF = Path("Inrond-1.0/fonts/variable/Inrond[ROND,opsz,wght].ttf")
DEFAULT_FONT_AXES = {"opsz": 14.0, "wght": 500.0, "ROND": 50.0}
AA_SUPERSAMPLE = 4

# Font sizes tuned for each sulakyapi cell height (12px, 19px, 26px)
FONT_SPECS = {
    "sulakyapi8": {
        "cell_h": 12,
        "ttf_size": 10,
        "threshold": 105,
        "space_w": 3,
        "y_offset": 1,
        "sheets": ["font8_0.tm2"],
        "target_sheet": 0,
        "resize_sheet": (256, 256),  # original 256x128 -> 256x256
    },
    "sulakyapi12": {
        "cell_h": 19,
        "ttf_size": 14,
        "threshold": 115,
        "space_w": 4,
        "y_offset": 1,
        "sheets": ["font12_0.tm2", "font12_1.tm2", "font12_2.tm2", "font12_3.tm2"],
        "target_sheet": 3,  # font12_3.tm2 has y=400..512 completely unused!
        "resize_sheet": None,
    },
    "sulakyapi18": {
        "cell_h": 26,
        "ttf_size": 21,
        "threshold": 115,
        "space_w": 6,
        "y_offset": 2,
        "sheets": ["font18_0.tm2"],
        "target_sheet": 0,
        "resize_sheet": (512, 256),  # original 256x256 -> 512x256
    },
}


def decode_tim2_4bpp(tm2: bytes) -> tuple[bytearray, int, int, bytes, bytes]:
    """Decode a 4bpp indexed TIM2 into (pixel_grid_bytes, w, h, header, clut)."""
    if tm2[:4] != b"TIM2":
        raise ValueError("Not a TIM2 file")
    tot_sz, clut_sz, img_sz, hdr_sz, _clut_cnt, _fmt, _mip, _clut_t, _img_t = struct.unpack_from(
        "<IIIHHHHBB", tm2, 16
    )
    w, h = struct.unpack_from("<HH", tm2, 16 + 20)
    hdr = tm2[: 16 + hdr_sz]
    img = tm2[16 + hdr_sz : 16 + hdr_sz + img_sz]
    clut = tm2[16 + hdr_sz + img_sz : 16 + hdr_sz + img_sz + clut_sz]
    pixels = bytearray(w * h)
    # 4bpp TIM2 stores low nibble = even x, high nibble = odd x
    for y in range(h):
        row_off = y * (w // 2)
        out_row = y * w
        for xb in range(w // 2):
            b = img[row_off + xb]
            pixels[out_row + xb * 2] = b & 0x0F
            pixels[out_row + xb * 2 + 1] = (b >> 4) & 0x0F
    return pixels, w, h, hdr, clut


def encode_tim2_4bpp(pixels: bytearray, w: int, h: int, orig_hdr: bytes, clut: bytes) -> bytes:
    """Encode a 4bpp pixel array (values 0..15) back into TIM2."""
    hdr = bytearray(orig_hdr)
    img_sz = (w * h) // 2
    hdr_sz = len(orig_hdr) - 16
    tot_sz = hdr_sz + img_sz + len(clut)
    struct.pack_into("<III", hdr, 16, tot_sz, len(clut), img_sz)
    struct.pack_into("<HH", hdr, 16 + 20, w, h)

    img = bytearray(img_sz)
    for y in range(h):
        row_off = y * (w // 2)
        in_row = y * w
        for xb in range(w // 2):
            lo = pixels[in_row + xb * 2] & 0x0F
            hi = pixels[in_row + xb * 2 + 1] & 0x0F
            img[row_off + xb] = lo | (hi << 4)
    return bytes(hdr) + bytes(img) + clut


def parse_w_abc(raw: bytes) -> tuple[tuple[int, float, float, float, float, int], list[int], list[list[int]]]:
    """Parse abc.w_abc into (header_tuple, lut_list, glyph_records)."""
    ver, f1, f2, f3, f4, max_code = struct.unpack_from("<IffffH", raw, 0)
    if ver != 5:
        raise ValueError(f"Unsupported w_abc version {ver}")
    lut_cnt = max_code + 1
    lut = list(struct.unpack_from(f"<{lut_cnt}H", raw, 0x16))
    p = 0x16 + lut_cnt * 2
    if p % 4:
        p += 2
    gcnt = struct.unpack_from("<I", raw, p)[0]
    gbase = p + 4
    glyphs = [list(struct.unpack_from("<4H3h2H", raw, gbase + i * 18)) for i in range(gcnt)]
    return (ver, f1, f2, f3, f4, max_code), lut, glyphs


def build_w_abc(hdr_tuple, lut: list[int], glyphs: list[list[int]]) -> bytes:
    """Serialize abc.w_abc back into binary format."""
    ver, f1, f2, f3, f4, max_code = hdr_tuple
    out = bytearray(struct.pack("<IffffH", ver, f1, f2, f3, f4, max_code))
    out += struct.pack(f"<{len(lut)}H", *lut)
    if len(out) % 4:
        out += b"\x00\x00"
    out += struct.pack("<I", len(glyphs))
    for rec in glyphs:
        out += struct.pack("<4H3h2H", *rec)
    return bytes(out)


def resolve_font_axes(ttf_path: Path, requested: dict[str, float] | None = None) -> dict[str, float]:
    """Resolve axes in the font's actual fvar order and reject unsupported values."""
    with TTFont(ttf_path, lazy=True) as source:
        axes = source['fvar'].axes if 'fvar' in source else []
        tags = {axis.axisTag for axis in axes}
        values = {tag: value for tag, value in DEFAULT_FONT_AXES.items() if tag in tags}
        if requested is not None:
            if requested.keys() - tags:
                raise ValueError(f"Unsupported font axes: {sorted(requested.keys() - tags)}")
            values.update(requested)
        result = {}
        for axis in axes:
            value = values.get(axis.axisTag, axis.defaultValue)
            if not axis.minValue <= value <= axis.maxValue:
                raise ValueError(f"{axis.axisTag} must be in {axis.minValue}..{axis.maxValue}")
            result[axis.axisTag] = value
    return result


def load_font(ttf_path: Path, size: int, axes: dict[str, float] | None = None) -> ImageFont.FreeTypeFont:
    resolved = resolve_font_axes(ttf_path, axes)
    font = ImageFont.truetype(str(ttf_path), size)
    if resolved:
        font.set_variation_by_axes(list(resolved.values()))
    return font


def font_license_files(ttf_path: Path) -> list[Path]:
    """Find the license in a font package, including nested static/variable directories."""
    for parent in ttf_path.resolve().parents:
        license_path = parent / 'OFL.txt'
        if license_path.is_file():
            files = [license_path]
            notice = parent / 'THIRD_PARTY_NOTICES.txt'
            if notice.is_file():
                files.append(notice)
            return files
    raise FileNotFoundError(f"No OFL.txt found for {ttf_path}")


def antialias_clut(original: bytes, used_indices: set[int]) -> bytes:
    """Use only previously unused palette entries for opaque grayscale ink edges."""
    if len(original) != 64 or used_indices & set(range(13)):
        raise ValueError("Antialiasing needs thirteen unused 4bpp palette entries")
    palette = bytearray(original)
    for index in range(13):
        shade = round((index + 1) * 255 / 14)
        palette[index * 4:index * 4 + 4] = bytes((shade, shade, shade, 255))
    # Black outline, transparent background, and white ink are not changed.
    return bytes(palette)


def antialiased_ink(font: ImageFont.FreeTypeFont, ch: str, cell_h: int, y_off: int,
                    width_scale: float, axes: dict[str, float] | None) -> tuple[Image.Image, int]:
    """Rasterize and condense from a 4x outline before reducing to native PSP pixels."""
    scale = AA_SUPERSAMPLE
    large = load_font(Path(font.path), font.size * scale, axes)
    left, top, right, bottom = large.getbbox(ch)
    pad = 4 * scale
    ox, oy = pad - min(0, left), pad - min(0, top)
    mask = Image.new('L', (max(32 * scale, ox + right + pad), max(cell_h * scale + pad, oy + bottom + pad)), 0)
    ImageDraw.Draw(mask).text((ox, oy), ch, font=large, fill=255)
    bounds = mask.getbbox()
    if bounds is None:
        return Image.new('L', (1, 1), 0), 1
    ink = mask.crop(bounds)
    target_w = max(1, round(ink.width * width_scale / scale))
    target_h = max(1, min(cell_h - 2, round(ink.height / scale)))
    ink = ink.resize((target_w, target_h), Image.Resampling.LANCZOS)
    peak = ink.getextrema()[1]
    if peak:
        # Keep thin punctuation and stems bright without throwing away edge coverage.
        ink = ink.point([0 if value < 24 else min(255, round(value * 255 / peak)) for value in range(256)])
    visible = ink.getbbox()
    if visible is not None:
        ink = ink.crop(visible)
    desired_top = y_off + round((bounds[1] - oy) / scale) + (visible[1] if visible else 0)
    return ink, max(1, min(desired_top, cell_h - ink.height - 1))


def condense_ink(ink: Image.Image, width_scale: float) -> Image.Image:
    """Narrow binary ink without dropping single-pixel strokes or changing height."""
    if not 0 < width_scale <= 1:
        raise ValueError("Glyph width scale must be greater than zero and at most one")
    width = max(1, round(ink.width * width_scale))
    result = Image.new("L", (width, ink.height), 0)
    src, dst = ink.load(), result.load()
    # Non-overlapping column buckets cover every source column. Taking their
    # maximum keeps thin stems that nearest-neighbor shrinking can discard.
    for x in range(width):
        start = x * ink.width // width
        end = (x + 1) * ink.width // width
        for y in range(ink.height):
            dst[x, y] = max(src[sx, y] for sx in range(start, end))
    return result


def render_outlined_glyph(font: ImageFont.FreeTypeFont, ch: str, cell_h: int, threshold: int, y_off: int, *,
                          width_scale: float = 1.0, tight_spacing: bool = False,
                          antialias: bool = False, font_axes: dict[str, float] | None = None) -> tuple[Image.Image, int, int, int]:
    """Render 4bpp ink (0..12=AA grays, 13=outline, 14=clear, 15=white) and A/B/C metrics."""
    if not 0 < width_scale <= 1:
        raise ValueError("Glyph width scale must be greater than zero and at most one")
    adv = max(1, round(font.getlength(ch) * width_scale))
    if antialias:
        ink, ink_y = antialiased_ink(font, ch, cell_h, y_off, width_scale, font_axes)
    else:
        pad = 4
        left, top, right, bottom = font.getbbox(ch)
        origin_x = pad - min(0, left)
        origin_y = pad - min(0, top)
        canvas_w = max(origin_x + right + pad, adv + pad * 2, 32)
        canvas_h = max(origin_y + bottom + pad, cell_h + pad * 2)
        mask = Image.new("L", (canvas_w, canvas_h), 0)
        draw = ImageDraw.Draw(mask)
        draw.text((origin_x, origin_y), ch, font=font, fill=255)
        mask = mask.point([0 if i < threshold else 255 for i in range(256)])
        bounds = mask.getbbox()
        if bounds is None:
            img = Image.new("L", (4, cell_h), 14)
            return img, 0, adv, 0
        ink = mask.crop(bounds)
        # Render outside the cell first so negative bearings cannot lose ink.
        if ink.height > cell_h - 2:
            ink = ink.resize((ink.width, cell_h - 2), Image.Resampling.NEAREST)
        if width_scale != 1:
            ink = condense_ink(ink, width_scale)
        desired_top = y_off + bounds[1] - origin_y
        ink_y = max(1, min(desired_top, cell_h - ink.height - 1))
    gw = ink.width + 2
    cell = Image.new("L", (gw, cell_h), 0)
    cell.paste(ink, (1, ink_y))
    outline = cell.filter(ImageFilter.MaxFilter(3))
    gimg = Image.new("L", (gw, cell_h), 14)
    mpx, opx = cell.load(), outline.load()
    gpx = gimg.load()
    for y in range(cell_h):
        for x in range(gw):
            if mpx[x, y]:
                value = mpx[x, y]
                gpx[x, y] = 15 if not antialias or value >= 247 else max(0, min(12, round(value * 14 / 255) - 1))
            elif opx[x, y]:
                gpx[x, y] = 13

    # Tight letters share an outline column, leaving one blank pixel between
    # ink bounds. Keep a minimum 3px advance for the existing EBOOT slot budget.
    # C may be -1: the wrapping patch already reads signed A/B/C bearings.
    a_bear = 0
    b_wid = gw
    c_bear = max(3, ink.width + 1) - gw if tight_spacing else max(0, (adv + 1) - gw)
    return gimg, a_bear, b_wid, c_bear


def font_specs(font_names: list[str] | None = None, dialogue_size: int | None = None,
                tight_dialogue: bool = False, dialogue_width_scale: float | None = None) -> dict:
    """Resolve per-build Inrond settings without mutating the reference presets."""
    names = list(FONT_SPECS) if font_names is None else font_names
    if not names or any(name not in FONT_SPECS for name in names):
        raise ValueError("Select at least one known font set")
    if dialogue_size is not None and not 10 <= dialogue_size <= 16:
        raise ValueError("Dialogue font size must be between 10 and 16 pixels")
    if dialogue_width_scale is not None and not 0 < dialogue_width_scale <= 1:
        raise ValueError("Dialogue width scale must be greater than zero and at most one")
    specs = {name: dict(FONT_SPECS[name]) for name in names}
    if dialogue_size is not None and "sulakyapi12" in specs:
        original = FONT_SPECS["sulakyapi12"]
        spec = specs["sulakyapi12"]
        spec["ttf_size"] = dialogue_size
        spec["space_w"] = max(1, round(original["space_w"] * dialogue_size / original["ttf_size"]))
        spec["y_offset"] = max(0, original["y_offset"] + (original["ttf_size"] - dialogue_size) // 2)
    if tight_dialogue and "sulakyapi12" in specs:
        specs["sulakyapi12"].update(width_scale=0.90, tight_spacing=True, space_w=2)
    if dialogue_width_scale is not None and "sulakyapi12" in specs:
        specs["sulakyapi12"]["width_scale"] = dialogue_width_scale
    return specs


def build_fonts(cpk_path: Path, ttf_path: Path, out_dir: Path, *,
                font_names: list[str] | None = None, dialogue_size: int | None = None,
                tight_dialogue: bool = False, dialogue_width_scale: float | None = None,
                font_axes: dict[str, float] | None = None, antialias: bool = True) -> None:
    specs = font_specs(font_names, dialogue_size, tight_dialogue, dialogue_width_scale)
    axes = resolve_font_axes(ttf_path, font_axes)
    if (out_dir / "font").exists():
        raise FileExistsError(f"Refusing to overwrite existing font assets: {out_dir / 'font'}")
    cpk = CpkArchive(str(cpk_path))
    rows_by_rel = {
        (f"{r['DirName']}/{r['FileName']}" if r["DirName"] else r["FileName"]): r
        for r in cpk.entries()
    }

    for fname, spec in specs.items():
        w_abc_rel = f"font/{fname}/abc.w_abc"
        w_abc_raw = crilayla.decompress(cpk.read_entry(rows_by_rel[w_abc_rel]))
        hdr_tuple, lut, glyphs = parse_w_abc(w_abc_raw)

        sheets_decoded: list[tuple[bytearray, int, int, bytes, bytes]] = []
        for sname in spec["sheets"]:
            tm2_rel = f"font/{fname}/{sname}"
            tm2_raw = crilayla.decompress(cpk.read_entry(rows_by_rel[tm2_rel]))
            pixels, w, h, hdr, clut = decode_tim2_4bpp(tm2_raw)
            sheets_decoded.append((pixels, w, h, hdr, clut))

        t_idx = spec["target_sheet"]
        pixels, w, h, hdr, clut = sheets_decoded[t_idx]
        if antialias:
            clut = antialias_clut(clut, set(pixels))

        if spec["resize_sheet"]:
            new_w, new_h = spec["resize_sheet"]
            new_px = bytearray([14] * (new_w * new_h))
            for yy in range(h):
                src_row = yy * w
                dst_row = yy * new_w
                new_px[dst_row : dst_row + w] = pixels[src_row : src_row + w]
            pixels, w, h = new_px, new_w, new_h

        # Determine safe packing region on target sheet
        if spec["resize_sheet"] and spec["resize_sheet"][0] > sheets_decoded[t_idx][1]:
            # Expanded horizontally: pack starting at x=256, y=1
            start_x, min_x, max_x_bound, start_y = 257, 257, w - 1, 1
        else:
            # Find max_y used by existing glyphs on target sheet
            max_y_used = max((g[3] for g in glyphs if g[8] == t_idx), default=0)
            start_x, min_x, max_x_bound, start_y = 1, 1, w - 1, max_y_used + 2

        cell_h = spec["cell_h"]
        ttf = load_font(ttf_path, spec["ttf_size"], axes)

        cur_x = start_x
        cur_y = start_y

        # Render space (0x20) + all printable ASCII (0x21..0x7E)
        # Also map curly quotes / dash / ellipsis in SJIS if needed; ASCII 0x20..0x7E is primary.
        for code in range(0x20, 0x7F):
            ch = chr(code)
            if code == 0x20:
                gimg = Image.new("L", (4, cell_h), 14)
                a_bear, b_wid, c_bear = 0, spec["space_w"], 0
            else:
                gimg, a_bear, b_wid, c_bear = render_outlined_glyph(
                    ttf, ch, cell_h, spec["threshold"], spec["y_offset"],
                    width_scale=spec.get("width_scale", 1.0), tight_spacing=spec.get("tight_spacing", False),
                    antialias=antialias, font_axes=axes
                )

            gw, gh = gimg.size
            if cur_x + gw + 1 > max_x_bound:
                cur_x = min_x
                cur_y += cell_h + 1
            if cur_y + gh > h:
                raise RuntimeError(f"{fname}: ran out of atlas height at U+{code:04X} (cur_y={cur_y}, h={h})")

            gpx = gimg.load()
            for yy in range(gh):
                row_off = (cur_y + yy) * w
                for xx in range(gw):
                    pixels[row_off + cur_x + xx] = gpx[xx, yy]

            new_rec = [cur_x, cur_y, cur_x + gw, cur_y + gh, a_bear, b_wid, c_bear, 0, t_idx]
            existing_gi = lut[code]
            if existing_gi:
                glyphs[existing_gi] = new_rec
            else:
                lut[code] = len(glyphs)
                glyphs.append(new_rec)

            cur_x += gw + 2

        sheets_decoded[t_idx] = (pixels, w, h, hdr, clut)

        out_font_dir = out_dir / "font" / fname
        out_font_dir.mkdir(parents=True, exist_ok=True)
        new_w_abc = build_w_abc(hdr_tuple, lut, glyphs)
        (out_font_dir / "abc.w_abc").write_bytes(crilayla.compress(new_w_abc))

        for i, sname in enumerate(spec["sheets"]):
            px_i, w_i, h_i, hdr_i, clut_i = sheets_decoded[i]
            tm2_bytes = encode_tim2_4bpp(px_i, w_i, h_i, hdr_i, clut_i)
            (out_font_dir / sname).write_bytes(crilayla.compress(tm2_bytes))

        print(f"Built {fname}: ttf_size={spec['ttf_size']}, glyphs={len(glyphs)}, target_sheet={t_idx} ({w}x{h}), end_xy=({cur_x},{cur_y})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Inrond PSP font assets")
    ap.add_argument("--cpk", required=True, help="Original GAMEINIT.CPK")
    ap.add_argument("--ttf", default=str(DEFAULT_TTF))
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--only", action="append", choices=FONT_SPECS, help="Build only the selected font set(s)")
    ap.add_argument("--dialogue-size", type=int, help="Latin dialogue raster size, 10..16px (default: 14px); line height stays 19px")
    ap.add_argument("--tight-dialogue", action="store_true", help="Tight Latin dialogue spacing, 90%% width and 2px spaces")
    ap.add_argument("--dialogue-width-scale", type=float, help="Override Latin dialogue horizontal scale (0 < scale <= 1)")
    ap.add_argument("--font-weight", type=float, help="Variable font weight (default: 500)")
    ap.add_argument("--font-roundness", type=float, help="Inrond roundness (default: 50)")
    ap.add_argument("--font-optical-size", type=float, help="Variable optical size (default: 14)")
    ap.add_argument("--no-antialias", action="store_true", help="Use legacy binary rasterization instead of supersampled grayscale")
    args = ap.parse_args()
    axes = {tag: value for tag, value in (("wght", args.font_weight), ("ROND", args.font_roundness), ("opsz", args.font_optical_size)) if value is not None}
    build_fonts(Path(args.cpk), Path(args.ttf), Path(args.out), font_names=args.only,
                dialogue_size=args.dialogue_size, tight_dialogue=args.tight_dialogue,
                dialogue_width_scale=args.dialogue_width_scale, font_axes=axes or None,
                antialias=not args.no_antialias)


if __name__ == "__main__":
    main()
