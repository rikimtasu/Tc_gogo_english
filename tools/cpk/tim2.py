"""TIM2 (4bpp/8bpp indexed RGBA32) and container codec for PJADV PSP textures."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from .crilayla import compress as crilayla_compress
    from .crilayla import decompress as crilayla_decompress
except ImportError:
    from crilayla import compress as crilayla_compress
    from crilayla import decompress as crilayla_decompress


def unwrap_texture(raw: bytes, filename: str) -> tuple[bytes, str, bytes]:
    """Unwrap a CPK texture entry into (tm2_bytes, container_kind, orig_prefix)."""
    if filename.lower().endswith(".zip"):
        comp_sz, uncomp_sz = struct.unpack_from(">II", raw, 0)
        tm2 = zlib.decompress(raw[8 : 8 + comp_sz])
        if len(tm2) != uncomp_sz:
            raise ValueError(f"{filename}: expected {uncomp_sz} bytes, got {len(tm2)}")
        return tm2, "zip", raw[:8]
    if raw[:4] == b"TIM2":
        return raw, "raw", b""
    if raw[:8] == b"CRILAYLA":
        return crilayla_decompress(raw), "crilayla", raw[:8]
    # Zeroed-magic CRILAYLA used by BATTLE.CPK root .tm2 files.
    return crilayla_decompress(b"CRILAYLA" + raw[8:]), "crilayla_zero", raw[:8]


def wrap_texture(tm2_bytes: bytes, kind: str, orig_prefix: bytes = b"") -> bytes:
    """Re-wrap TIM2 bytes into the original container format."""
    if kind == "zip":
        comp = zlib.compress(tm2_bytes, 9)
        return struct.pack(">II", len(comp), len(tm2_bytes)) + comp
    if kind == "raw":
        return tm2_bytes
    if kind == "crilayla":
        return crilayla_compress(tm2_bytes)
    if kind == "crilayla_zero":
        comp = crilayla_compress(tm2_bytes)
        if len(orig_prefix) != 8:
            raise ValueError("crilayla_zero requires 8-byte original prefix")
        return orig_prefix + comp[8:]
    raise ValueError(f"Unknown container kind: {kind}")


def parse_tm2_header(tm2: bytes) -> dict[str, int]:
    """Parse a single-picture TIM2 header."""
    if tm2[:4] != b"TIM2":
        raise ValueError(f"Invalid TIM2 magic: {tm2[:4]!r}")
    (
        total_sz,
        pal_sz,
        img_sz,
        hdr_sz,
        pal_colors,
        img_fmt,
        mipmaps,
        clut_type,
        img_type,
        width,
        height,
    ) = struct.unpack_from("<IIIHHBBBBHH", tm2, 16)
    return {
        "total_sz": total_sz,
        "pal_sz": pal_sz,
        "img_sz": img_sz,
        "hdr_sz": hdr_sz,
        "pal_colors": pal_colors,
        "img_fmt": img_fmt,
        "mipmaps": mipmaps,
        "clut_type": clut_type,
        "img_type": img_type,
        "width": width,
        "height": height,
        "img_off": 16 + hdr_sz,
        "pal_off": 16 + hdr_sz + img_sz,
    }


def _csm1_swizzle_palette(pal: np.ndarray) -> np.ndarray:
    """Apply PS2/PSP TIM2 CSM1 CLUT swizzle/unswizzle (involution on 32-entry blocks)."""
    out = pal.copy()
    for i in range(0, (len(pal) // 32) * 32, 32):
        out[i + 8 : i + 16] = pal[i + 16 : i + 24]
        out[i + 16 : i + 24] = pal[i + 8 : i + 16]
    return out


def decode_tm2(tm2: bytes) -> Image.Image:
    """Decode a 4bpp or 8bpp indexed RGBA32 TIM2 into a PIL RGBA Image."""
    h = parse_tm2_header(tm2)
    clut_fmt = h["clut_type"] & 0x3F
    if clut_fmt != 3 or h["img_type"] not in (4, 5):
        raise ValueError(f"Unsupported TIM2 format: img_type={h['img_type']}, clut_type={h['clut_type']}")

    w, height = h["width"], h["height"]
    img_data = tm2[h["img_off"] : h["img_off"] + h["img_sz"]]
    pal_data = tm2[h["pal_off"] : h["pal_off"] + h["pal_sz"]]
    palette = np.frombuffer(pal_data, dtype=np.uint8).reshape(-1, 4)
    if h["img_type"] == 5 and (h["clut_type"] & 0x80) == 0 and len(palette) >= 32:
        palette = _csm1_swizzle_palette(palette)

    if h["img_type"] == 5:
        indices = np.frombuffer(img_data, dtype=np.uint8).reshape(height, w)
    else:
        raw_bytes = np.frombuffer(img_data, dtype=np.uint8)
        lo = raw_bytes & 0x0F
        hi = (raw_bytes >> 4) & 0x0F
        indices = np.empty(raw_bytes.size * 2, dtype=np.uint8)
        indices[0::2] = lo
        indices[1::2] = hi
        indices = indices[: w * height].reshape(height, w)

    rgba = palette[indices]
    return Image.fromarray(rgba, mode="RGBA")


def encode_tm2(img: Image.Image, template_tm2: bytes) -> bytes:
    """Encode an RGBA Image into TIM2 bytes matching template_tm2's dimensions and bpp."""
    h = parse_tm2_header(template_tm2)
    w, height = h["width"], h["height"]
    if img.size != (w, height):
        raise ValueError(f"Size mismatch: expected {(w, height)}, got {img.size}")
    clut_fmt = h["clut_type"] & 0x3F
    if clut_fmt != 3 or h["img_type"] not in (4, 5):
        raise ValueError(f"Unsupported TIM2 template: img_type={h['img_type']}, clut_type={h['clut_type']}")

    rgba = img.convert("RGBA")
    max_colors = 16 if h["img_type"] == 4 else 256

    # Quantize with Pillow FASTOCTREE (supports RGBA alpha quantization)
    quant = rgba.quantize(colors=max_colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    indices = np.array(quant, dtype=np.uint8)

    raw_pal = quant.getpalette(rawmode="RGBA") or []
    pal_bytes = bytearray(h["pal_colors"] * 4)
    pal_bytes[: len(raw_pal)] = raw_pal[: len(pal_bytes)]
    if h["img_type"] == 5 and (h["clut_type"] & 0x80) == 0 and h["pal_colors"] >= 32:
        pal_arr = np.frombuffer(pal_bytes, dtype=np.uint8).reshape(-1, 4)
        pal_bytes = bytearray(_csm1_swizzle_palette(pal_arr).tobytes())

    if h["img_type"] == 5:
        img_bytes = indices.tobytes()
    else:
        flat = indices.reshape(-1)
        if flat.size % 2 != 0:
            flat = np.append(flat, 0)
        packed = (flat[0::2] & 0x0F) | ((flat[1::2] & 0x0F) << 4)
        img_bytes = packed.tobytes()

    if len(img_bytes) != h["img_sz"] or len(pal_bytes) != h["pal_sz"]:
        raise ValueError(
            f"Encoded size mismatch: img {len(img_bytes)}!={h['img_sz']} or pal {len(pal_bytes)}!={h['pal_sz']}"
        )

    out = bytearray(template_tm2)
    out[h["img_off"] : h["img_off"] + h["img_sz"]] = img_bytes
    out[h["pal_off"] : h["pal_off"] + h["pal_sz"]] = pal_bytes
    return bytes(out)
