"""CRI CPK v7 reader, extractor, and rebuilder (with @UTF in-place patching)."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Any


TYPE_FMT = {
    0: ">B",
    1: ">b",
    2: ">H",
    3: ">h",
    4: ">I",
    5: ">i",
    6: ">Q",
    7: ">q",
    8: ">f",
}


@dataclass
class UtfFieldRef:
    """Byte offset and format of a numeric field inside an @UTF buffer."""

    offset: int
    fmt: str


@dataclass
class UtfTable:
    """Parsed @UTF table along with exact byte offsets for numeric fields."""

    name: str
    columns: list[tuple[str, int, int, Any]]
    rows: list[dict[str, Any]]
    field_refs: list[dict[str, UtfFieldRef]]


def _read_val(buf: bytes, p: int, typ: int, get_str, base: int, data_off: int):
    if typ in TYPE_FMT:
        fmt = TYPE_FMT[typ]
        sz = struct.calcsize(fmt)
        return struct.unpack_from(fmt, buf, p)[0], p + sz, fmt
    if typ == 0xA:
        str_ptr = struct.unpack_from(">I", buf, p)[0]
        return get_str(str_ptr), p + 4, None
    if typ == 0xB:
        off, ln = struct.unpack_from(">II", buf, p)
        return ("data", base + data_off + off, ln), p + 8, None
    raise ValueError(f"Unsupported @UTF column type {typ:#x}")


def parse_utf(buf: bytes) -> UtfTable:
    """Parse an @UTF table and record byte offsets of all row/constant numeric fields."""
    if buf[:4] != b"@UTF":
        raise ValueError(f"Expected @UTF magic, got {buf[:4]!r}")
    _tsize, rows_off, str_off, data_off, name_off, ncols, row_len, nrows = struct.unpack_from(
        ">IIIIIHHI", buf, 4
    )
    base = 8
    strs = buf[base + str_off : base + data_off]

    def get_str(o: int) -> str:
        end = strs.index(b"\0", o)
        return strs[o:end].decode("cp932", "replace")

    cols: list[tuple[str, int, int, Any, UtfFieldRef | None]] = []
    p = 32
    for _ in range(ncols):
        flags = buf[p]
        nm_off = struct.unpack_from(">I", buf, p + 1)[0]
        p += 5
        storage, typ = flags & 0xF0, flags & 0x0F
        const = None
        ref = None
        if storage == 0x30:
            val_off = p
            const, p, fmt = _read_val(buf, p, typ, get_str, base, data_off)
            if fmt:
                ref = UtfFieldRef(val_off, fmt)
        cols.append((get_str(nm_off), storage, typ, const, ref))

    rows: list[dict[str, Any]] = []
    refs: list[dict[str, UtfFieldRef]] = []
    for r in range(nrows):
        q = base + rows_off + r * row_len
        row: dict[str, Any] = {}
        rref: dict[str, UtfFieldRef] = {}
        for nm, storage, typ, const, const_ref in cols:
            if storage == 0x50:
                val_off = q
                val, q, fmt = _read_val(buf, q, typ, get_str, base, data_off)
                row[nm] = val
                if fmt:
                    rref[nm] = UtfFieldRef(val_off, fmt)
            else:
                row[nm] = const
                if const_ref:
                    rref[nm] = const_ref
        rows.append(row)
        refs.append(rref)

    return UtfTable(
        name=get_str(name_off),
        columns=[(c[0], c[1], c[2], c[3]) for c in cols],
        rows=rows,
        field_refs=refs,
    )


def patch_utf_field(buf: bytearray, table: UtfTable, row_idx: int, col: str, value: int) -> None:
    """Update a numeric field in-place within an @UTF buffer."""
    ref = table.field_refs[row_idx].get(col)
    if ref is None:
        raise KeyError(f"Column {col!r} has no mutable numeric ref in row {row_idx}")
    struct.pack_into(ref.fmt, buf, ref.offset, value)


def _align(val: int, align: int) -> int:
    return (val + align - 1) // align * align


class CpkArchive:
    """Reader/extractor/rebuilder for CRI CPK v7 archives."""

    def __init__(self, path: str) -> None:
        self.path = path
        with open(path, "rb") as f:
            self.raw_hdr = bytearray(f.read(0x800))
            self.hdr_table = parse_utf(bytes(self.raw_hdr[0x10:]))
            self.hdr = self.hdr_table.rows[0]
            self.toc_offset: int = self.hdr["TocOffset"]
            self.content_offset: int = self.hdr["ContentOffset"]
            self.align: int = self.hdr["Align"] or 2048

            f.seek(self.toc_offset)
            self.toc_prefix = f.read(16)
            toc_body_sz = struct.unpack_from("<Q", self.toc_prefix, 8)[0]
            self.raw_toc_body = bytearray(f.read(toc_body_sz))
            self.toc_table = parse_utf(bytes(self.raw_toc_body))

            self.gtoc_offset = self.hdr.get("GtocOffset")
            self.gtoc_blob = b""
            if self.gtoc_offset:
                f.seek(self.gtoc_offset)
                gt_hdr = f.read(16)
                gt_sz = struct.unpack_from("<Q", gt_hdr, 8)[0]
                self.gtoc_blob = gt_hdr + f.read(gt_sz)

            self.etoc_offset = self.hdr.get("EtocOffset")
            self.etoc_blob = b""
            if self.etoc_offset:
                f.seek(self.etoc_offset)
                et_hdr = f.read(16)
                et_sz = struct.unpack_from("<Q", et_hdr, 8)[0]
                self.etoc_blob = et_hdr + f.read(et_sz)

    def entries(self) -> list[dict[str, Any]]:
        return self.toc_table.rows

    def read_entry(self, row: dict[str, Any]) -> bytes:
        with open(self.path, "rb") as f:
            f.seek(self.toc_offset + row["FileOffset"])
            return f.read(row["FileSize"])

    def extract_all(self, out_dir: str) -> int:
        os.makedirs(out_dir, exist_ok=True)
        with open(self.path, "rb") as f:
            for row in self.toc_table.rows:
                rel = os.path.join(row["DirName"], row["FileName"]) if row["DirName"] else row["FileName"]
                dst = os.path.join(out_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                f.seek(self.toc_offset + row["FileOffset"])
                with open(dst, "wb") as out:
                    out.write(f.read(row["FileSize"]))
        return len(self.toc_table.rows)

    def rebuild(self, out_path: str, replacements: dict[str, bytes]) -> None:
        """Rebuild CPK keeping exact TOC/GTOC/ETOC schemas and updating offsets/sizes."""
        hdr_buf = bytearray(self.raw_hdr)
        hdr_utf = bytearray(hdr_buf[0x10:])
        toc_buf = bytearray(self.raw_toc_body)

        # Preserve original disk order (sorted by FileOffset)
        indexed_rows = sorted(
            enumerate(self.toc_table.rows),
            key=lambda item: item[1]["FileOffset"],
        )

        cur_abs = self.content_offset
        payloads: list[tuple[int, bytes]] = []
        delta_enabled = 0

        with open(self.path, "rb") as src_f:
            for idx, row in indexed_rows:
                rel = f"{row['DirName']}/{row['FileName']}" if row["DirName"] else row["FileName"]
                if rel in replacements:
                    data = replacements[rel]
                    if data[:8] == b"CRILAYLA":
                        # CRILAYLA u32 at +8 is uncompressed body size after 0x100 prefix
                        ext_sz = struct.unpack_from("<I", data, 8)[0] + 0x100
                    else:
                        ext_sz = len(data)
                    delta_enabled += ext_sz - (row["ExtractSize"] or 0)
                else:
                    src_f.seek(self.toc_offset + row["FileOffset"])
                    data = src_f.read(row["FileSize"])
                    ext_sz = row["ExtractSize"]

                rel_off = cur_abs - self.toc_offset
                patch_utf_field(toc_buf, self.toc_table, idx, "FileOffset", rel_off)
                patch_utf_field(toc_buf, self.toc_table, idx, "FileSize", len(data))
                if ext_sz is not None:
                    patch_utf_field(toc_buf, self.toc_table, idx, "ExtractSize", ext_sz)

                padded_len = _align(len(data), self.align)
                payloads.append((padded_len, data))
                cur_abs += padded_len

        content_size = cur_abs - self.content_offset
        etoc_abs = cur_abs if self.etoc_blob else None

        patch_utf_field(hdr_utf, self.hdr_table, 0, "ContentSize", content_size)
        if etoc_abs is not None:
            patch_utf_field(hdr_utf, self.hdr_table, 0, "EtocOffset", etoc_abs)
        if self.hdr.get("EnabledDataSize") is not None:
            patch_utf_field(hdr_utf, self.hdr_table, 0, "EnabledDataSize", self.hdr["EnabledDataSize"] + delta_enabled)
        hdr_buf[0x10:] = hdr_utf

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "wb") as out:
            out.write(hdr_buf)
            out.seek(self.toc_offset)
            out.write(self.toc_prefix)
            out.write(toc_buf)
            if self.gtoc_offset and self.gtoc_blob:
                out.seek(self.gtoc_offset)
                out.write(self.gtoc_blob)
            out.seek(self.content_offset)
            for padded_len, data in payloads:
                out.write(data)
                pad = padded_len - len(data)
                if pad:
                    out.write(b"\x00" * pad)
            if self.etoc_blob:
                out.write(self.etoc_blob)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="CRI CPK v7 tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_x = sub.add_parser("extract")
    p_x.add_argument("cpk")
    p_x.add_argument("out_dir")
    p_r = sub.add_parser("verify-roundtrip")
    p_r.add_argument("cpk")
    p_r.add_argument("tmp_cpk")
    args = ap.parse_args()

    arc = CpkArchive(args.cpk)
    if args.cmd == "extract":
        n = arc.extract_all(args.out_dir)
        print(f"Extracted {n} files to {args.out_dir}")
    elif args.cmd == "verify-roundtrip":
        arc.rebuild(args.tmp_cpk, {})
        orig = open(args.cpk, "rb").read()
        rebuilt = open(args.tmp_cpk, "rb").read()
        print("orig:", len(orig), "rebuilt:", len(rebuilt), "byte_identical:", orig == rebuilt)
        if orig != rebuilt:
            # Check member-by-member equivalence
            arc2 = CpkArchive(args.tmp_cpk)
            assert len(arc.entries()) == len(arc2.entries())
            mismatches = 0
            for r1, r2 in zip(arc.entries(), arc2.entries()):
                if arc.read_entry(r1) != arc2.read_entry(r2):
                    mismatches += 1
            print("member mismatches:", mismatches)
