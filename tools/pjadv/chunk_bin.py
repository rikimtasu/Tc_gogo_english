"""Unpack and repack PJADV PSP zlib-chunked .bin containers (textdata.bin, scenario.bin, etc.)."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass


@dataclass
class ChunkedBinMeta:
    """Layout metadata for lossless round-trip repacking."""

    names: list[str]
    chunk_size: int
    end_padding: bytes


def unpack_chunked_bin(blob: bytes) -> tuple[bytes, ChunkedBinMeta]:
    """Decompress a chunked .bin container into a contiguous payload plus metadata."""
    if len(blob) < 32:
        raise ValueError("Chunked .bin too small")
    first_off = struct.unpack_from("<I", blob, 0)[0]
    if first_off < 56 or first_off % 28 != 0:
        raise ValueError(f"Unexpected first chunk offset {first_off:#x}")
    n = first_off // 28 - 1

    names: list[str] = []
    parts: list[bytes] = []
    chunk_size = 0
    for i in range(n):
        off = struct.unpack_from("<I", blob, i * 28)[0]
        raw_name = blob[i * 28 + 4 : i * 28 + 28].split(b"\x00", 1)[0]
        names.append(raw_name.decode("ascii"))
        csz, dsz = struct.unpack_from(">II", blob, off)
        if i == 0:
            chunk_size = dsz
        dec = zlib.decompress(blob[off + 8 : off + 8 + csz])
        if len(dec) != dsz:
            raise ValueError(f"Chunk {i} decompressed to {len(dec)}, expected {dsz}")
        parts.append(dec)

    sentinel_off = struct.unpack_from("<I", blob, n * 28)[0]
    end_padding = blob[sentinel_off:]
    return b"".join(parts), ChunkedBinMeta(names=names, chunk_size=chunk_size, end_padding=end_padding)


def pack_chunked_bin(payload: bytes, meta: ChunkedBinMeta, prefix_hint: str = "") -> bytes:
    """Re-chunk and zlib-compress payload into PJADV chunked .bin format."""
    csize = meta.chunk_size or 0x7800
    chunks_raw = [payload[i : i + csize] for i in range(0, len(payload), csize)]
    n = len(chunks_raw)
    if not chunks_raw:
        chunks_raw = [b""]
        n = 1

    # Reuse original chunk names if count matches; otherwise extend deterministically
    if len(meta.names) >= n:
        names = meta.names[:n]
    else:
        if not prefix_hint and meta.names:
            # e.g. textdata000.zip -> textdata
            import re
            m = re.match(r"^(.*?)(\d+)\.zip$", meta.names[0])
            prefix_hint = m.group(1) if m else "chunk"
        names = list(meta.names) + [f"{prefix_hint}{i:03d}.zip" for i in range(len(meta.names), n)]

    header_len = n * 28 + 28  # n entries of (u32 + 24s) + 28-byte sentinel (u32 total_len + 24 zero bytes)
    out = bytearray(header_len)

    cur_off = header_len
    body_parts: list[bytes] = []
    for i, raw in enumerate(chunks_raw):
        comp = zlib.compress(raw, 9)
        entry_hdr = struct.pack(">II", len(comp), len(raw))
        rec = entry_hdr + comp
        pad = (4 - (len(rec) % 4)) % 4
        if pad:
            rec += b"\xff" * pad

        struct.pack_into("<I", out, i * 28, cur_off)
        nm_bytes = names[i].encode("ascii")[:23]
        out[i * 28 + 4 : i * 28 + 4 + len(nm_bytes)] = nm_bytes
        body_parts.append(rec)
        cur_off += len(rec)

    struct.pack_into("<I", out, n * 28, cur_off)
    return bytes(out) + b"".join(body_parts) + meta.end_padding


if __name__ == "__main__":
    import sys

    for path in sys.argv[1:]:
        orig = open(path, "rb").read()
        raw, meta = unpack_chunked_bin(orig)
        rebuilt = pack_chunked_bin(raw, meta)
        print(f"{path}: chunks={len(meta.names)} raw={len(raw)} byte_identical={orig == rebuilt}")
        if orig != rebuilt:
            raise SystemExit(1)
