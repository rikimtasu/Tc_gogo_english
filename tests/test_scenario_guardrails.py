"""Unit tests for P3 scenario key guardrails, CPK offset handling, and EBOOT string extraction."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.cpk.cpk import CpkArchive
from tools.eboot.extract_strings import extract_eboot_strings
from tools.pjadv.chunk_bin import ChunkedBinMeta, pack_chunked_bin
from tools.pjadv.scenario import extract_from_bytes, pack_from_dir

ROOT = Path(__file__).resolve().parents[1]
REAL_EBOOT = ROOT / "work" / "eboot" / "EBOOT_decrypted.bin"
REAL_EBOOT_JSON = ROOT / "glossary" / "eboot_strings.json"


def _pack_utf_table(table_name: str, columns: list[tuple[str, int, Any]], rows: list[dict[str, Any]]) -> bytes:
    strings = bytearray(b"<NULL>\x00")
    str_offsets: dict[str, int] = {"<NULL>": 0}

    def intern(text: str) -> int:
        if text not in str_offsets:
            str_offsets[text] = len(strings)
            strings.extend(text.encode("cp932") + b"\x00")
        return str_offsets[text]

    name_off = intern(table_name)
    col_specs: list[tuple[str, int, int, int, Any]] = []
    for col_name, typ, default_or_val in columns:
        cname_off = intern(col_name)
        col_specs.append((col_name, 0x50, typ, cname_off, default_or_val))
        for r in rows:
            if typ == 0xA:
                intern(str(r.get(col_name, default_or_val)))

    def encode_val(typ: int, val: Any) -> bytes:
        fmt = {0: ">B", 1: ">b", 2: ">H", 3: ">h", 4: ">I", 5: ">i", 6: ">Q", 7: ">q", 8: ">f"}
        if typ in fmt:
            return struct.pack(fmt[typ], val)
        if typ == 0xA:
            return struct.pack(">I", intern(str(val)))
        raise ValueError(f"Unsupported @UTF type {typ}")

    row_parts: list[bytes] = []
    row_len = 0
    for row in rows:
        rb = bytearray()
        for col_name, _storage, typ, _cname_off, default_val in col_specs:
            rb.extend(encode_val(typ, row.get(col_name, default_val)))
        row_len = len(rb)
        row_parts.append(bytes(rb))

    col_def_len = len(col_specs) * 5
    rows_off = 24 + col_def_len
    str_off = rows_off + sum(len(rp) for rp in row_parts)
    data_off = str_off + len(strings)
    header = struct.pack(
        ">4sIIIIIHHI",
        b"@UTF",
        data_off,
        rows_off,
        str_off,
        data_off,
        name_off,
        len(col_specs),
        row_len,
        len(rows),
    )
    col_defs = bytearray()
    for _col_name, storage, typ, cname_off, _default_val in col_specs:
        col_defs.append(storage | typ)
        col_defs.extend(struct.pack(">I", cname_off))
    return header + bytes(col_defs) + b"".join(row_parts) + bytes(strings)


def _cri_packet(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<IQ", 0xFF, len(payload)) + payload


def _build_synthetic_cpk(out_path: Path, entries: list[tuple[str, str, bytes]], *, toc_after_content: bool) -> None:
    align = 0x800
    toc_cols = [
        ("DirName", 0xA, ""),
        ("FileName", 0xA, ""),
        ("FileSize", 0x4, 0),
        ("ExtractSize", 0x4, 0),
        ("FileOffset", 0x6, 0),
        ("ID", 0x4, 0),
        ("UserString", 0xA, ""),
    ]
    if not toc_after_content:
        toc_offset = 0x800
        dummy_rows = [
            {"DirName": d, "FileName": f, "FileSize": len(p), "ExtractSize": len(p), "FileOffset": 0, "ID": i, "UserString": ""}
            for i, (d, f, p) in enumerate(entries)
        ]
        dummy_toc = _cri_packet(b"TOC ", _pack_utf_table("CpkTocInfo", toc_cols, dummy_rows))
        content_offset = ((toc_offset + len(dummy_toc) + align - 1) // align) * align
        file_base = toc_offset
        cur = content_offset
    else:
        content_offset = 0x800
        file_base = content_offset
        cur = content_offset

    buf = bytearray()
    toc_rows: list[dict[str, Any]] = []
    file_blobs: list[tuple[int, bytes]] = []
    for idx, (dir_name, file_name, payload) in enumerate(entries):
        file_blobs.append((cur, payload))
        toc_rows.append({
            "DirName": dir_name, "FileName": file_name,
            "FileSize": len(payload), "ExtractSize": len(payload),
            "FileOffset": cur - file_base, "ID": idx, "UserString": "",
        })
        cur = ((cur + len(payload) + align - 1) // align) * align

    if toc_after_content:
        toc_offset = cur

    toc_pkt = _cri_packet(b"TOC ", _pack_utf_table("CpkTocInfo", toc_cols, toc_rows))
    cpk_hdr_cols = [
        ("UpdateDateTime", 0x6, 0), ("FileSize", 0x6, 0),
        ("ContentOffset", 0x6, content_offset), ("ContentSize", 0x6, 0),
        ("TocOffset", 0x6, toc_offset), ("TocSize", 0x6, len(toc_pkt)),
        ("Files", 0x4, len(entries)), ("Align", 0x2, align),
        ("Version", 0x2, 7), ("Revision", 0x2, 0),
    ]
    total_end = max(toc_offset + len(toc_pkt), max((off + len(b) for off, b in file_blobs), default=0x800))
    buf.extend(b"\x00" * total_end)
    cpk_row = {
        "UpdateDateTime": 0, "FileSize": total_end,
        "ContentOffset": content_offset, "ContentSize": cur - content_offset,
        "TocOffset": toc_offset, "TocSize": len(toc_pkt),
        "Files": len(entries), "Align": align, "Version": 7, "Revision": 0,
    }
    cpk_pkt = _cri_packet(b"CPK ", _pack_utf_table("CpkHeader", cpk_hdr_cols, [cpk_row]))
    buf[0 : len(cpk_pkt)] = cpk_pkt
    buf[toc_offset : toc_offset + len(toc_pkt)] = toc_pkt
    for off, blob in file_blobs:
        buf[off : off + len(blob)] = blob
    out_path.write_bytes(bytes(buf))


def _build_synthetic_scenario_work(work_dir: Path) -> Path:
    strings = ["###title", "\u3000", "SCENE01_TEST", "[ステージ1_テスト]", "アリス", "こんにちは、テスト！"]
    offsets: list[int] = []
    pool = bytearray()
    cur = 16
    for s in strings:
        offsets.append(cur)
        enc = s.encode("cp932") + b"\x00\x00"
        pool.extend(enc)
        cur += len(enc)
    td_raw = struct.pack("<12sI", b"PJADV_TF0001", len(strings)) + bytes(pool)
    words = [
        0x01000D02, offsets[2],
        0xF0010005, offsets[3], 0x30000002, 0, 0,
        0x80000307, 0, offsets[4], offsets[5], 0x3, 0x20000, 0,
    ]
    sc_raw = struct.pack("<12sI16s", b"PJADV_SF0001", len(words), b"bbbbccccddddeeee") + struct.pack(f"<{len(words)}I", *words)
    td_meta = ChunkedBinMeta(names=["textdata000.zip"], chunk_size=0x7800, end_padding=b"")
    sc_meta = ChunkedBinMeta(names=["scenario000.zip"], chunk_size=0x7800, end_padding=b"")
    extract_from_bytes(pack_chunked_bin(td_raw, td_meta), pack_chunked_bin(sc_raw, sc_meta), work_dir)
    return work_dir


class ScenarioAndContainerTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_dialogue_allowed_and_structural_edits_guarded(self) -> None:
        work_dir = _build_synthetic_scenario_work(self.root / "work")
        trans_dir = self.root / "trans"
        trans_dir.mkdir()
        scene_file = sorted((work_dir / "gt_input").glob("*.json"))[0]
        rows = json.loads(scene_file.read_text(encoding="utf-8"))

        # Dialogue & speaker edits allowed by default
        edited = [dict(r) for r in rows]
        edited[2]["name"] = "Alice"
        edited[2]["message"] = "Hello, test!"
        (trans_dir / scene_file.name).write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
        td_out, sc_out, report = pack_from_dir(work_dir, trans_dir)
        self.assertEqual(report["warnings"], [])

        # Label and scene_title blocked unless explicitly opted in
        for idx, key, kw in ((1, "label", "allow_label_edits"), (0, "scene_title", "allow_scene_title_edits")):
            bad = [dict(r) for r in rows]
            bad[idx]["message"] = "Modified"
            (trans_dir / scene_file.name).write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, key):
                pack_from_dir(work_dir, trans_dir)
            td_out, sc_out, _ = pack_from_dir(work_dir, trans_dir, **{kw: True})
            re_out = self.root / f"re_{key}"
            extract_from_bytes(td_out, sc_out, re_out)
            re_file = sorted((re_out / "gt_input").glob("*.json"))[0]
            actual = json.loads(re_file.read_text(encoding="utf-8"))
            self.assertEqual(actual, bad)

    def test_cpk_toc_and_content_offset_layouts(self) -> None:
        toc_first = self.root / "toc_first.cpk"
        _build_synthetic_cpk(toc_first, [("", "alpha.bin", b"ALPHA"), ("sub", "beta.bin", b"BETA")], toc_after_content=False)
        cpk = CpkArchive(toc_first)
        self.assertEqual(cpk.file_base, cpk.toc_offset)
        rebuilt_path = self.root / "rebuilt.cpk"
        cpk.rebuild(rebuilt_path, {"alpha.bin": b"NEW_ALPHA"})
        rebuilt = CpkArchive(rebuilt_path)
        r_rows = {f"{r['DirName']}/{r['FileName']}".lstrip("/"): r for r in rebuilt.entries()}
        self.assertEqual(rebuilt.read_entry(r_rows["alpha.bin"]), b"NEW_ALPHA")
        self.assertEqual(rebuilt.read_entry(r_rows["sub/beta.bin"]), b"BETA")

        content_first = self.root / "content_first.cpk"
        _build_synthetic_cpk(content_first, [("", "btl_a.tm2", b"TIM2")], toc_after_content=True)
        cpk2 = CpkArchive(content_first)
        self.assertEqual(cpk2.file_base, cpk2.content_offset)
        self.assertEqual(cpk2.read_entry(cpk2.entries()[0]), b"TIM2")
        rebuilt_cf = self.root / "rebuilt_cf.cpk"
        cpk2.rebuild(rebuilt_cf, {"btl_a.tm2": b"NEW_TIM2"})
        cpk2_rebuilt = CpkArchive(rebuilt_cf)
        self.assertEqual(cpk2_rebuilt.read_entry(cpk2_rebuilt.entries()[0]), b"NEW_TIM2")

    def test_eboot_string_extraction(self) -> None:
        buf = bytearray(0x180000)
        buf[0x15C4A0 : 0x15C4A0 + len("セーブ".encode("cp932")) + 1] = "セーブ".encode("cp932") + b"\x00"
        buf[0x15D3E8 : 0x15D3E8 + len("年".encode("cp932")) + 1] = "年".encode("cp932") + b"\x00"
        buf[0x15D3F8 : 0x15D3F8 + len("／".encode("cp932")) + 1] = "／".encode("cp932") + b"\x00"
        res = extract_eboot_strings(bytes(buf))
        self.assertEqual([s["jp"] for s in res["strings"]], ["セーブ", "年"])
        self.assertEqual(res["strings"][0]["vaddr"], "0x0896044c")

        if REAL_EBOOT.exists() and REAL_EBOOT_JSON.exists():
            real_res = extract_eboot_strings(REAL_EBOOT.read_bytes())
            self.assertEqual(real_res["count"], 73)
            tracked = json.loads(REAL_EBOOT_JSON.read_text(encoding="utf-8"))
            for s in tracked["strings"]:
                s["en"] = ""
            self.assertEqual(tracked, real_res)


if __name__ == "__main__":
    unittest.main()
