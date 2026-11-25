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
    arr = np.array(rgba, dtype=np.uint8)
    max_colors = 16 if h["img_type"] == 4 else 256

    # Inspect template's unswizzled original palette to preserve special entries
    # (grayscale glow masks like btl_filesE2_2, pal[0] transparent, exact black/white).
    orig_pal = np.frombuffer(
        template_tm2[h["pal_off"] : h["pal_off"] + h["pal_sz"]], dtype=np.uint8
    ).reshape(-1, 4).copy()
    if h["img_type"] == 5 and (h["clut_type"] & 0x80) == 0 and len(orig_pal) >= 32:
        orig_pal = _csm1_swizzle_palette(orig_pal)

    is_gray_ramp = (
        h["img_type"] == 4
        and len(orig_pal) == 16
        and bool(np.all(orig_pal[:, 0] == orig_pal[:, 1]) and np.all(orig_pal[:, 1] == orig_pal[:, 2]))
    )
    if is_gray_ramp:
        pal_arr = orig_pal.copy()
        trans_idxs = np.where(pal_arr[:, 3] == 0)[0]
        opaque_idxs = np.where(pal_arr[:, 3] > 0)[0]
        trans_idx = int(trans_idxs[0]) if trans_idxs.size else 0
        opaque_lums = pal_arr[opaque_idxs, 0].astype(np.int32)
        pix_lum = arr[:, :, 0].astype(np.int32)
        nearest = np.abs(pix_lum[:, :, None] - opaque_lums[None, None, :]).argmin(axis=2)
        indices = opaque_idxs[nearest].astype(np.uint8)
        if trans_idxs.size:
            indices[arr[:, :, 3] < 128] = trans_idx
    else:
        orig_set = {tuple(int(x) for x in c) for c in orig_pal}
        pinned: list[tuple[int, int, int, int]] = []
        if int(orig_pal[0, 3]) == 0:
            pinned.append(tuple(int(x) for x in orig_pal[0]))
        for special in ((0, 0, 0, 0), (255, 255, 255, 0), (0, 0, 0, 255), (255, 255, 255, 255)):
            if special in orig_set and special not in pinned:
                m = (
                    (arr[:, :, 0] == special[0])
                    & (arr[:, :, 1] == special[1])
                    & (arr[:, :, 2] == special[2])
                    & (arr[:, :, 3] == special[3])
                )
                if m.any():
                    pinned.append(special)

        # Preserve any non-black/non-white alpha==0 palette entries from orig_pal that are used
        # in the image (e.g. btl_filesE2_1 pink-red multiplicative shadow ramp & btl_mvp gold glow,
        # which PIL.FASTOCTREE would otherwise collapse to (0,0,0,0) black!).
        orig_a0 = [tuple(int(x) for x in c) for c in orig_pal if int(c[3]) == 0]
        orig_a0_unique = list(dict.fromkeys(orig_a0))

        indices = np.zeros((height, w), dtype=np.uint8)
        pinned_mask = np.zeros((height, w), dtype=bool)
        for p_idx, col in enumerate(pinned):
            m = (
                (arr[:, :, 0] == col[0])
                & (arr[:, :, 1] == col[1])
                & (arr[:, :, 2] == col[2])
                & (arr[:, :, 3] == col[3])
            )
            indices[m] = p_idx
            pinned_mask |= m

        # Match any remaining alpha==0 pixels to their nearest RGB entry in orig_a0_unique
        rem_zero = (arr[:, :, 3] == 0) & (~pinned_mask)
        if rem_zero.any():
            if len(orig_a0_unique) > 1 and max_colors >= 64:
                a0_rgbs = np.array([c[:3] for c in orig_a0_unique], dtype=np.int32)
                rem_rgbs = arr[rem_zero][:, :3].astype(np.int32)
                dists = ((rem_rgbs[:, None, :] - a0_rgbs[None, :, :]) ** 2).sum(axis=2)
                nearest_a0 = dists.argmin(axis=1)
                # Register each matched orig_a0 entry in pinned (up to half the palette)
                a0_to_pidx: dict[int, int] = {}
                for a0_i in np.unique(nearest_a0):
                    col = orig_a0_unique[int(a0_i)]
                    if col not in pinned and len(pinned) < max_colors // 2:
                        pinned.append(col)
                    a0_to_pidx[int(a0_i)] = pinned.index(col) if col in pinned else 0
                mapped_pidx = np.array([a0_to_pidx[int(i)] for i in nearest_a0], dtype=np.uint8)
                indices[rem_zero] = mapped_pidx
                pinned_mask |= rem_zero
            elif pinned and pinned[0][3] == 0:
                indices[rem_zero] = 0
                pinned_mask |= rem_zero

        pal_arr = np.zeros((h["pal_colors"], 4), dtype=np.uint8)
        for p_idx, col in enumerate(pinned):
            pal_arr[p_idx] = col

        rem_colors = max_colors - len(pinned)
        unpinned = ~pinned_mask
        if unpinned.any() and rem_colors > 0:
            # Pack unpinned pixels into a 1D strip for clean FASTOCTREE quantization
            flat_px = arr[unpinned]
            strip = Image.fromarray(flat_px.reshape(1, -1, 4), mode="RGBA")
            quant = strip.quantize(colors=rem_colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
            q_idx = np.array(quant, dtype=np.uint8).reshape(-1)
            q_pal = np.array(quant.getpalette(rawmode="RGBA") or [], dtype=np.uint8).reshape(-1, 4)
            n_q = min(len(q_pal), rem_colors)
            pal_arr[len(pinned) : len(pinned) + n_q] = q_pal[:n_q]
            indices[unpinned] = q_idx + len(pinned)

    if h["img_type"] == 5 and (h["clut_type"] & 0x80) == 0 and h["pal_colors"] >= 32:
        pal_arr = _csm1_swizzle_palette(pal_arr)
    pal_bytes = bytearray(pal_arr.tobytes())

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
