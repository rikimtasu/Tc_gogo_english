"""Build NewGoStyle-Ver1.000 PSP bitmap fonts (TIM2 + abc.w_abc, CRILAYLA-compressed)."""

from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive  # noqa: E402
from cpk import crilayla  # noqa: E402


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
        "ttf_size": 15,
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


def render_outlined_glyph(font: ImageFont.FreeTypeFont, ch: str, cell_h: int, threshold: int, y_off: int) -> tuple[Image.Image, int, int, int]:
    """Render a crisp 4bpp glyph (14=trans, 13=outline, 15=white) and return (idx_img, A, B, C)."""
    adv = max(1, round(font.getlength(ch)))
    pad = 4
    canvas_w = max(adv + pad * 2, 32)
    mask = Image.new("L", (canvas_w, cell_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.text((pad, y_off), ch, font=font, fill=255)
    mpx = mask.load()

    # Find horizontal ink bounds
    min_x, max_x = canvas_w, -1
    for y in range(cell_h):
        for x in range(canvas_w):
            if mpx[x, y] >= threshold:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x

    if max_x < min_x:
        # Whitespace
        img = Image.new("L", (4, cell_h), 14)
        return img, 0, adv, 0

    # Expand 1px on left and right for crisp outline
    bx0 = max(0, min_x - 1)
    bx1 = min(canvas_w - 1, max_x + 1)
    gw = bx1 - bx0 + 1

    gimg = Image.new("L", (gw, cell_h), 14)
    gpx = gimg.load()
    for y in range(cell_h):
        for x in range(gw):
            sx = bx0 + x
            if mpx[sx, y] >= threshold:
                gpx[x, y] = 15
            else:
                has_nb = False
                for dy in (-1, 0, 1):
                    ny = y + dy
                    if 0 <= ny < cell_h:
                        for dx in (-1, 0, 1):
                            if (dx or dy) and 0 <= sx + dx < canvas_w and mpx[sx + dx, ny] >= threshold:
                                has_nb = True
                                break
                    if has_nb:
                        break
                if has_nb:
                    gpx[x, y] = 13

    # A = left bearing (0), B = visual glyph width, C = trailing spacing so A+B+C = adv + 1 (outline room)
    a_bear = 0
    b_wid = gw
    c_bear = max(0, (adv + 1) - gw)
    return gimg, a_bear, b_wid, c_bear


def build_fonts(cpk_path: Path, ttf_path: Path, out_dir: Path) -> None:
    cpk = CpkArchive(str(cpk_path))
    rows_by_rel = {
        (f"{r['DirName']}/{r['FileName']}" if r["DirName"] else r["FileName"]): r
        for r in cpk.entries()
    }

    for fname, spec in FONT_SPECS.items():
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
        ttf = ImageFont.truetype(str(ttf_path), spec["ttf_size"])

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
                    ttf, ch, cell_h, spec["threshold"], spec["y_offset"]
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

        print(f"Built {fname}: glyphs={len(glyphs)}, target_sheet={t_idx} ({w}x{h}), end_xy=({cur_x},{cur_y})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build NewGoStyle PSP font assets")
    ap.add_argument("--cpk", required=True, help="Original GAMEINIT.CPK")
    ap.add_argument("--ttf", default="NewGoStyle-Ver1.000/NewGoStyle-Regular.ttf")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()
    build_fonts(Path(args.cpk), Path(args.ttf), Path(args.out))


if __name__ == "__main__":
    main()
