"""In-place UV & screen-X patcher for GAMEINIT.CPK/scenario/GraphicARC.bin (SYS_PL_* place/time banners)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.tim2 import crilayla_compress, crilayla_decompress


# All 9 Time-of-Day widened UV specs (file003, 384x128):
# id -> (new_sx, new_u, new_w); TSHADOW automatically gets (new_sx+1, new_u+1, new_w).
TIME_UV_PATCHES: dict[str, tuple[int, int, int]] = {
    "001": (66, 138, 60),  # Early Morn   (cell 136..200)
    "002": (66, 138, 60),  # Morning      (cell 136..200)
    "003": (66, 208, 62),  # Lunchtime    (cell 204..272)
    "004": (66, 208, 60),  # Noon         (cell 204..272)
    "005": (66, 0, 61),    # Afternoon    (cell 0..64; fixes vanilla TSHADOW005 w=33 -> 61!)
    "006": (66, 2, 62),    # After School (cell 0..64)
    "007": (66, 70, 60),   # Evening      (cell 68..132)
    "008": (66, 70, 60),   # Night        (cell 68..132; was 17px -> 60px!)
    "009": (66, 276, 62),  # Late Night   (cell 274..344)
}

# Narrow Location Title banners widened in-place to use their full cell width (keeping center at ~102):
# suf -> (new_sx_jb, new_w_jb, new_sx_sh, new_w_sh)
PLACE_WIDTH_PATCHES: dict[str, tuple[int, int, int, int]] = {
    "205": (68, 68, 68, 68),  # School Route   (file001 x=440..512, was w=46)
    "102": (58, 84, 58, 84),  # Yuugiri-an     (file002 x=240..328, was w=46)
    "301": (68, 68, 68, 68),  # Witch World    (file002 x=96..168,  was w=47)
    "402": (72, 62, 72, 62),  # Demon World    (file002 x=368..432, was w=34)
    "403": (64, 78, 64, 78),  # Nive Territory (file002 x=384..464, was w=62)
}

# Free Battle character/enemy nameplate UV widths in sys_hrbe_tips1.zip:
# The game right-aligns player names via `screen_x = 331 - w` and clips both sides strictly to `w`.
# Patching the single-byte `w` field in-place eliminates all right-edge clipping (`Nanal`, `Macaro`, etc.)
# while keeping every player name flush against the portrait frame and every enemy name unclipped!
HRBE_NAME_WIDTH_PATCHES: dict[str, int] = {
    # Player names (SYS_HRBE_PN01..08C) — exact localized widths for flush right-alignment
    "SYS_HRBE_PN01": 47,   # Nanaka       (was 34)
    "SYS_HRBE_PN02": 44,   # Lolotte      (was 42)
    "SYS_HRBE_PN03": 31,   # Misa         (was 27)
    "SYS_HRBE_PN04": 22,   # Ria          (was 25)
    "SYS_HRBE_PN05": 31,   # Synn         (was 26)
    "SYS_HRBE_PN06": 52,   # Demon Synn   (was 45)
    "SYS_HRBE_PN07": 55,   # Demon Nanaka (was 54)
    "SYS_HRBE_PN08A": 52,  # Macaron      (was 46)
    "SYS_HRBE_PN08B": 53,  # Macaron      (was 46)
    "SYS_HRBE_PN08C": 53,  # Macaron      (was 46)
    # Enemy names whose English text exceeded original katakana width
    "SYS_HRBE_EN03": 51,   # Mochimochi   (was 45)
    "SYS_HRBE_EN06": 49,   # Daikichi     (was 44)
    "SYS_HRBE_EN07": 53,   # Yoshimura    (was 46)
    "SYS_HRBE_EN11": 46,   # Kal Kan      (was 43)
    "SYS_HRBE_EN12": 38,   # Sheba        (was 35)
    "SYS_HRBE_EN13": 55,   # Mon Petit    (was 45)
    "SYS_HRBE_EN14": 55,   # Waltham      (was 54)
    "SYS_HRBE_EN17": 51,   # Kurokan      (was 43)
    "SYS_HRBE_EN20": 37,   # Ichiya       (was 35)
    "SYS_HRBE_EN22": 54,   # Hatsugai     (was 44)
    "SYS_HRBE_EN25": 58,   # Eauderourke  (was 54)
    "SYS_HRBE_EN32": 50,   # Yasubee      (was 45)
    "SYS_HRBE_EN34": 54,   # Nagahama     (was 43)
}


def _f32_hi2(val: float) -> bytes:
    """Return high 2 bytes of IEEE-754 float32 (exact match for integer screen coords 0..255)."""
    raw = struct.pack("<f", float(val))
    assert raw[:2] == b"\x00\x00", f"Float {val} does not fit exact 16-bit mantissa"
    return raw[2:4]


def _iter_entries(gr: bytes) -> list[tuple[str, int, int]]:
    first_off = struct.unpack_from("<I", gr, 0)[0]
    n = first_off // 28
    offs: list[tuple[str, int]] = []
    for i in range(n):
        off, raw_name = struct.unpack_from("<I24s", gr, i * 28)
        offs.append((raw_name.split(b"\x00", 1)[0].decode("ascii", "replace"), off))
    res: list[tuple[str, int, int]] = []
    for i, (nm, off) in enumerate(offs):
        nxt = offs[i + 1][1] if i + 1 < len(offs) else len(gr)
        res.append((nm, off, nxt))
    return res


def _locate_fields_in_record(blob: bytes) -> dict | None:
    """Locate exact byte offsets of sx_hi2, u, v, w, h inside a SYS_PL_* GraphicARC record."""
    idx = blob.find(b"sys_pl_file")
    if idx < 0:
        return None
    tex = blob[idx : idx + 14].decode("ascii")

    # Variant A (standard byte-RLE): contains `24 00 00 01 01 00`
    p24 = blob.find(b"\x24\x00\x00\x01", idx)
    if p24 >= 0:
        sx_off = p24 - 7
        sy_off = p24 - 3
        sx = struct.unpack("<f", b"\x00\x00" + blob[sx_off : sx_off + 2])[0]
        sy = struct.unpack("<f", b"\x00\x00" + blob[sy_off : sy_off + 2])[0]
        pos = p24 + 6
        z0 = struct.unpack_from("<H", blob, pos)[0]
        pos += 2
        cur = z0 - 0x23
        out = bytearray(cur)
        # Map unpacked byte offset -> record byte offset (None if zero-run encoded)
        off_map: list[int | None] = [None] * cur
        while pos + 2 <= len(blob) and len(out) < 16:
            if blob[pos] == 0xFF:
                break
            if blob[pos] != 0x00:
                break
            lit_len = blob[pos + 1]
            pos += 2
            for k in range(lit_len):
                out.append(blob[pos + k])
                off_map.append(pos + k)
            pos += lit_len
            if pos >= len(blob) or blob[pos] == 0xFF:
                break
            if blob[pos] != 0x00 or pos + 3 > len(blob):
                break
            z = struct.unpack_from("<H", blob, pos + 1)[0]
            pos += 3
            out.extend(b"\x00" * z)
            off_map.extend([None] * z)
        while len(out) < 16:
            out.append(0)
            off_map.append(None)
        u, v, w, h = struct.unpack_from("<4I", out, 0)
        return {
            "tex": tex,
            "sx": sx,
            "sy": sy,
            "sx_off": sx_off,
            "u": u,
            "v": v,
            "w": w,
            "h": h,
            "off_map": off_map[:16],
        }

    # Variant B (word-RLE, e.g. SYS_PL_NAMEJB102): contains `00 12 00 00 00 01 01 00 00 11 00 00 00 0a`
    p12 = blob.find(b"\x12\x00\x00\x00\x01\x01\x00\x00\x11\x00\x00\x00\x0a", idx)
    if p12 >= 0:
        sx_off = p12 - 7
        sy_off = p12 - 3
        sx = struct.unpack("<f", b"\x00\x00" + blob[sx_off : sx_off + 2])[0]
        sy = struct.unpack("<f", b"\x00\x00" + blob[sy_off : sy_off + 2])[0]
        base = p12 + 13
        u, v, w, h = struct.unpack_from("<4I", blob, base)
        off_map = list(range(base, base + 16))
        return {
            "tex": tex,
            "sx": sx,
            "sy": sy,
            "sx_off": sx_off,
            "u": u,
            "v": v,
            "w": w,
            "h": h,
            "off_map": off_map,
        }
    return None


def _patch_u32_in_place(buf: bytearray, rec_off: int, off_map: list[int | None], field_byte_off: int, new_val: int) -> None:
    """Patch a u32 field strictly in-place (preserving exact RLE byte layout)."""
    val_bytes = struct.pack("<I", new_val)
    for b_i in range(4):
        src_off = off_map[field_byte_off + b_i]
        want = val_bytes[b_i]
        if src_off is None:
            if want != 0:
                raise ValueError(
                    f"Cannot write non-zero byte {want:#x} into zero-run byte {b_i} of field@{field_byte_off}"
                )
        else:
            buf[rec_off + src_off] = want


def patch_graphic_arc_bytes(gr_decompressed: bytes) -> tuple[bytes, int]:
    """Patch SYS_PL_TIME* and narrow SYS_PL_NAME* UV/screen-X fields in-place inside decompressed GraphicARC.bin."""
    buf = bytearray(gr_decompressed)
    patched = 0
    for name, off, nxt in _iter_entries(gr_decompressed):
        # 1. All 9 Time-of-Day sprites (TIMEB, TIMEF, TSHADOW)
        for pfx, is_shadow in (("SYS_PL_TIMEB", False), ("SYS_PL_TIMEF", False), ("SYS_PL_TSHADOW", True)):
            if name.startswith(pfx):
                suf = name[len(pfx) :]
                if suf in TIME_UV_PATCHES:
                    info = _locate_fields_in_record(bytes(buf[off:nxt]))
                    assert info is not None, f"Failed to parse {name}"
                    nsx, nu, nw = TIME_UV_PATCHES[suf]
                    if is_shadow:
                        nsx += 1
                        nu += 1
                    buf[off + info["sx_off"] : off + info["sx_off"] + 2] = _f32_hi2(nsx)
                    if info["u"] != nu:
                        _patch_u32_in_place(buf, off, info["off_map"], 0, nu)
                    if info["w"] != nw:
                        _patch_u32_in_place(buf, off, info["off_map"], 8, nw)
                    # Verify readback
                    chk = _locate_fields_in_record(bytes(buf[off:nxt]))
                    assert chk is not None and int(chk["sx"]) == nsx and chk["u"] == nu and chk["w"] == nw, (
                        f"Verify failed on {name}: got {chk}"
                    )
                    patched += 1

        # 2. Narrow Location banners (NAMEJB, NAMEJF, PSHADOW)
        for pfx, is_shadow in (("SYS_PL_NAMEJB", False), ("SYS_PL_NAMEJF", False), ("SYS_PL_PSHADOW", True)):
            if name.startswith(pfx):
                suf = name[len(pfx) :]
                if suf in PLACE_WIDTH_PATCHES:
                    info = _locate_fields_in_record(bytes(buf[off:nxt]))
                    assert info is not None, f"Failed to parse {name}"
                    sx_j, w_j, sx_s, w_s = PLACE_WIDTH_PATCHES[suf]
                    nsx = sx_s if is_shadow else sx_j
                    nw = w_s if is_shadow else w_j
                    buf[off + info["sx_off"] : off + info["sx_off"] + 2] = _f32_hi2(nsx)
                    _patch_u32_in_place(buf, off, info["off_map"], 8, nw)
                    chk = _locate_fields_in_record(bytes(buf[off:nxt]))
                    assert chk is not None and int(chk["sx"]) == nsx and chk["w"] == nw, (
                        f"Verify failed on {name}: got {chk}"
                    )
                    patched += 1

        # 3. Free Battle character/enemy nameplate widths (SYS_HRBE_EN*, SYS_HRBE_PN*)
        if name in HRBE_NAME_WIDTH_PATCHES:
            blob = bytes(buf[off:nxt])
            idx = blob.find(b"sys_hrbe_tips1")
            assert idx >= 0, f"sys_hrbe_tips1 missing in {name}"
            tail_idx = blob.find(b"\x00\x13\x00", idx + 14)
            assert tail_idx >= 7 and blob[tail_idx - 6 : tail_idx - 1] == b"\x00\x03\x00\x00\x01", (
                f"Unexpected RLE tail in {name}"
            )
            w_off = tail_idx - 7
            nw = HRBE_NAME_WIDTH_PATCHES[name]
            assert 1 <= nw <= 255
            buf[off + w_off] = nw
            patched += 1

    assert len(buf) == len(gr_decompressed)
    return bytes(buf), patched


def patch_graphic_arc_compressed(raw_crilayla: bytes) -> tuple[bytes, int]:
    """Decompress CRILAYLA GraphicARC.bin, apply in-place SYS_PL UV patches, and recompress."""
    dec = crilayla_decompress(raw_crilayla)
    patched_dec, count = patch_graphic_arc_bytes(dec)
    recomp = crilayla_compress(patched_dec)
    # Round-trip safety check
    assert crilayla_decompress(recomp) == patched_dec
    return recomp, count


def read_sys_pl_layout(gr_decompressed: bytes) -> tuple[dict[str, dict[str, dict]], dict[str, dict[str, dict]]]:
    """Return (places_by_id, times_by_id) with exact (tex, sx, sy, u, v, w, h) for every layer."""
    places: dict[str, dict[str, dict]] = {}
    times: dict[str, dict[str, dict]] = {}
    for name, off, nxt in _iter_entries(gr_decompressed):
        for pfx, key in (
            ("SYS_PL_NAMEJB", "jb"),
            ("SYS_PL_NAMEJF", "jf"),
            ("SYS_PL_NAMEEB", "eb"),
            ("SYS_PL_NAMEEF", "ef"),
            ("SYS_PL_PSHADOW", "sh"),
        ):
            if name.startswith(pfx):
                suf = name[len(pfx) :]
                info = _locate_fields_in_record(gr_decompressed[off:nxt])
                if info is not None:
                    places.setdefault(suf, {})[key] = info
        for pfx, key in (
            ("SYS_PL_TIMEB", "tb"),
            ("SYS_PL_TIMEF", "tf"),
            ("SYS_PL_TSHADOW", "sh"),
        ):
            if name.startswith(pfx):
                suf = name[len(pfx) :]
                info = _locate_fields_in_record(gr_decompressed[off:nxt])
                if info is not None:
                    times.setdefault(suf, {})[key] = info
    return places, times


if __name__ == "__main__":
    from cpk.cpk import CpkArchive

    gi = CpkArchive("work/iso_extract/GAMEINIT.CPK")
    raw = gi.read_entry([r for r in gi.entries() if r["FileName"] == "GraphicARC.bin"][0])
    recomp, n = patch_graphic_arc_compressed(raw)
    print(f"Patched GraphicARC.bin: {n} SYS_PL sprite records, comp {len(raw)} -> {len(recomp)} bytes")
