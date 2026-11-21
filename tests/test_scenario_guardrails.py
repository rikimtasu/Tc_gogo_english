"""Unit tests for P3 scenario key guardrails, CPK offset handling, and EBOOT string extraction."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tools.cpk.cpk import CpkArchive
from tools.eboot.extract_strings import extract_eboot_strings
from tools.pjadv.chunk_bin import ChunkedBinMeta, pack_chunked_bin
from tools.pjadv.scenario import extract_from_bytes, main as scenario_main, pack_from_dir

ROOT = Path(__file__).resolve().parents[1]
REAL_EBOOT = ROOT / "work" / "eboot" / "EBOOT_decrypted.bin"
REAL_EBOOT_JSON = ROOT / "glossary" / "eboot_strings.json"


def _pack_utf_table(table_name: str, columns: list[tuple[str, int, Any]], rows: list[dict[str, Any]]) -> bytes:
    """Build a minimal unencrypted CRI @UTF table."""
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
        is_const = False
        # Columns present identically in every row can be stored per-row (0x50) for simplicity.
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
    tsize = data_off

    header = struct.pack(
        ">4sIIIIIHHI",
        b"@UTF",
        tsize,
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
    """Wrap a CRI CPK header/TOC @UTF payload in its 16-byte chunk packet."""
    return tag + struct.pack("<IQ", 0xFF, len(payload)) + payload


def _build_synthetic_cpk(
    out_path: Path,
    entries: list[tuple[str, str, bytes]],
    *,
    toc_after_content: bool,
) -> None:
    """Write a synthetic CPK archive with TocOffset either before or after ContentOffset."""
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
        # Build placeholder TOC first to determine content_offset alignment
        dummy_rows = [
            {
                "DirName": d,
                "FileName": f,
                "FileSize": len(p),
                "ExtractSize": len(p),
                "FileOffset": 0,
                "ID": i,
                "UserString": "",
            }
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
        toc_rows.append(
            {
                "DirName": dir_name,
                "FileName": file_name,
                "FileSize": len(payload),
                "ExtractSize": len(payload),
                "FileOffset": cur - file_base,
                "ID": idx,
                "UserString": "",
            }
        )
        cur = ((cur + len(payload) + align - 1) // align) * align

    if toc_after_content:
        toc_offset = cur

    toc_pkt = _cri_packet(b"TOC ", _pack_utf_table("CpkTocInfo", toc_cols, toc_rows))
    cpk_hdr_cols = [
        ("UpdateDateTime", 0x6, 0),
        ("FileSize", 0x6, 0),
        ("ContentOffset", 0x6, content_offset),
        ("ContentSize", 0x6, 0),
        ("TocOffset", 0x6, toc_offset),
        ("TocSize", 0x6, len(toc_pkt)),
        ("Files", 0x4, len(entries)),
        ("Align", 0x2, align),
        ("Version", 0x2, 7),
        ("Revision", 0x2, 0),
    ]
    total_end = max(toc_offset + len(toc_pkt), max((off + len(b) for off, b in file_blobs), default=0x800))
    buf.extend(b"\x00" * total_end)

    cpk_row = {
        "UpdateDateTime": 0,
        "FileSize": total_end,
        "ContentOffset": content_offset,
        "ContentSize": cur - content_offset,
        "TocOffset": toc_offset,
        "TocSize": len(toc_pkt),
        "Files": len(entries),
        "Align": align,
        "Version": 7,
        "Revision": 0,
    }
    cpk_pkt = _cri_packet(b"CPK ", _pack_utf_table("CpkHeader", cpk_hdr_cols, [cpk_row]))
    buf[0 : len(cpk_pkt)] = cpk_pkt
    buf[toc_offset : toc_offset + len(toc_pkt)] = toc_pkt
    for off, blob in file_blobs:
        buf[off : off + len(blob)] = blob

    out_path.write_bytes(bytes(buf))


def _build_synthetic_scenario_work(work_dir: Path) -> Path:
    """Build a minimal PJADV synthetic extraction workspace containing scene_title, label, and dialogue."""
    strings = [
        "###title",
        "\u3000",
        "SCENE01_TEST",
        "[ステージ1_テスト]",
        "アリス",
        "こんにちは、テスト！",
    ]
    offsets: list[int] = []
    pool = bytearray()
    cur = 16
    for s in strings:
        offsets.append(cur)
        enc = s.encode("cp932") + b"\x00\x00"
        pool.extend(enc)
        cur += len(enc)
    td_raw = struct.pack("<12sI", b"PJADV_TF0001", len(strings)) + bytes(pool)

    # Opcodes matching scenario.py scanner:
    # - OP_SCENE (0x01000d02, 2 words): word[1] = scene_title pool offset
    # - OP_LABEL (0xF0010005, 5 words): word[1] = label pool offset
    # - OP_DIALOGUE (0x80000307, 7 words): word[2] = speaker pool offset, word[3] = message pool offset
    words = [
        0x01000D02, offsets[2],
        0xF0010005, offsets[3], 0x30000002, 0, 0,
        0x80000307, 0, offsets[4], offsets[5], 0x3, 0x20000, 0,
    ]
    sc_raw = (
        struct.pack("<12sI16s", b"PJADV_SF0001", len(words), b"bbbbccccddddeeee")
        + struct.pack(f"<{len(words)}I", *words)
    )

    td_meta = ChunkedBinMeta(names=["textdata000.zip"], chunk_size=0x7800, end_padding=b"")
    sc_meta = ChunkedBinMeta(names=["scenario000.zip"], chunk_size=0x7800, end_padding=b"")
    td_bin = pack_chunked_bin(td_raw, td_meta)
    sc_bin = pack_chunked_bin(sc_raw, sc_meta)

    extract_from_bytes(td_bin, sc_bin, work_dir)
    return work_dir


class ScenarioGuardrailsTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.work_dir = _build_synthetic_scenario_work(self.root / "work")
        self.trans_dir = self.root / "trans"
        self.trans_dir.mkdir(parents=True, exist_ok=True)
        self.gt_files = sorted((self.work_dir / "gt_input").glob("*.json"))
        self.assertGreaterEqual(len(self.gt_files), 1)
        self.scene_name = self.gt_files[0].name
        self.rows = json.loads(self.gt_files[0].read_text(encoding="utf-8"))

    def _write_trans(self, rows: list[dict[str, Any]]) -> None:
        (self.trans_dir / self.scene_name).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _assert_reextract_matches(
        self,
        td_out: bytes,
        sc_out: bytes,
        expected_rows: list[dict[str, Any]],
        tag: str,
    ) -> None:
        re_out = self.root / f"re_extract_{tag}"
        extract_from_bytes(td_out, sc_out, re_out)
        re_files = sorted((re_out / "gt_input").glob("*.json"))
        self.assertEqual(len(re_files), 1)
        actual = json.loads(re_files[0].read_text(encoding="utf-8"))
        self.assertEqual(actual, expected_rows)

    def test_dialogue_and_speaker_edits_allowed_by_default(self) -> None:
        edited = [dict(r) for r in self.rows]
        edited[2]["name"] = "Alice"
        edited[2]["message"] = "Hello, test!"
        self._write_trans(edited)

        td_out, sc_out, report = pack_from_dir(self.work_dir, self.trans_dir)
        self.assertTrue(td_out and sc_out)
        self.assertEqual(report["warnings"], [])
        self._assert_reextract_matches(td_out, sc_out, edited, "dialogue")

    def test_label_edit_blocked_by_default_and_allowed_when_opted_in(self) -> None:
        edited = [dict(r) for r in self.rows]
        edited[1]["message"] = "Stage 1 Test"
        self._write_trans(edited)

        with self.assertRaisesRegex(ValueError, "label"):
            pack_from_dir(self.work_dir, self.trans_dir)

        td_out, sc_out, report = pack_from_dir(
            self.work_dir, self.trans_dir, allow_label_edits=True
        )
        self.assertTrue(td_out and sc_out)
        self.assertEqual(report["warnings"], [])
        self._assert_reextract_matches(td_out, sc_out, edited, "label")

    def test_scene_title_edit_blocked_by_default_and_allowed_when_opted_in(self) -> None:
        edited = [dict(r) for r in self.rows]
        edited[0]["message"] = "Scene 01 Test"
        self._write_trans(edited)

        with self.assertRaisesRegex(ValueError, "scene_title"):
            pack_from_dir(self.work_dir, self.trans_dir)

        td_out, sc_out, report = pack_from_dir(
            self.work_dir, self.trans_dir, allow_scene_title_edits=True
        )
        self.assertTrue(td_out and sc_out)
        self.assertEqual(report["warnings"], [])
        self._assert_reextract_matches(td_out, sc_out, edited, "scene_title")

    def test_cli_pack_accepts_allow_flags(self) -> None:
        edited = [dict(r) for r in self.rows]
        edited[0]["message"] = "Scene 01 Test"
        edited[1]["message"] = "Stage 1 Test"
        self._write_trans(edited)

        out_dir = self.root / "cli_out"
        base_argv = [
            "scenario.py",
            "pack",
            "--work", str(self.work_dir),
            "--trans", str(self.trans_dir),
            "--out-dir", str(out_dir),
        ]

        with patch.object(sys, "argv", base_argv):
            with self.assertRaisesRegex(ValueError, "scene_title|label"):
                scenario_main()

        with patch.object(
            sys,
            "argv",
            base_argv + ["--allow-label-edits", "--allow-scene-title-edits"],
        ):
            scenario_main()

        self.assertTrue((out_dir / "textdata.bin").exists())
        self.assertTrue((out_dir / "scenario.bin").exists())
        self._assert_reextract_matches(
            (out_dir / "textdata.bin").read_bytes(),
            (out_dir / "scenario.bin").read_bytes(),
            edited,
            "cli",
        )


class CpkOffsetLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_toc_before_content_read_and_rebuild(self) -> None:
        cpk_path = self.root / "toc_first.cpk"
        _build_synthetic_cpk(
            cpk_path,
            [("", "alpha.bin", b"ALPHA_PAYLOAD"), ("sub", "beta.bin", b"BETA_PAYLOAD")],
            toc_after_content=False,
        )
        cpk = CpkArchive(cpk_path)
        self.assertEqual(cpk.file_base, cpk.toc_offset)
        rows = cpk.entries()
        self.assertEqual([cpk.read_entry(r) for r in rows], [b"ALPHA_PAYLOAD", b"BETA_PAYLOAD"])

        ext_dir = self.root / "extracted_a"
        self.assertEqual(cpk.extract_all(ext_dir), 2)
        self.assertEqual((ext_dir / "alpha.bin").read_bytes(), b"ALPHA_PAYLOAD")
        self.assertEqual((ext_dir / "sub" / "beta.bin").read_bytes(), b"BETA_PAYLOAD")

        rebuilt_path = self.root / "rebuilt.cpk"
        cpk.rebuild(rebuilt_path, {"alpha.bin": b"NEW_ALPHA"})
        rebuilt = CpkArchive(rebuilt_path)
        r_rows = {f"{r['DirName']}/{r['FileName']}".lstrip("/"): r for r in rebuilt.entries()}
        self.assertEqual(rebuilt.read_entry(r_rows["alpha.bin"]), b"NEW_ALPHA")
        self.assertEqual(rebuilt.read_entry(r_rows["sub/beta.bin"]), b"BETA_PAYLOAD")

    def test_content_before_toc_read_extract_and_rebuild_guard(self) -> None:
        cpk_path = self.root / "content_first.cpk"
        _build_synthetic_cpk(
            cpk_path,
            [("", "btl_a.tm2", b"TIM2_ROOT_DATA"), ("EXName", "btl_b.zip", b"ZIP_SUB_DATA")],
            toc_after_content=True,
        )
        cpk = CpkArchive(cpk_path)
        self.assertGreater(cpk.toc_offset, cpk.content_offset)
        self.assertEqual(cpk.file_base, cpk.content_offset)
        rows = cpk.entries()
        self.assertEqual([cpk.read_entry(r) for r in rows], [b"TIM2_ROOT_DATA", b"ZIP_SUB_DATA"])

        ext_dir = self.root / "extracted_b"
        self.assertEqual(cpk.extract_all(ext_dir), 2)
        self.assertEqual((ext_dir / "btl_a.tm2").read_bytes(), b"TIM2_ROOT_DATA")
        self.assertEqual((ext_dir / "EXName" / "btl_b.zip").read_bytes(), b"ZIP_SUB_DATA")

        with self.assertRaises(NotImplementedError):
            cpk.rebuild(self.root / "should_fail.cpk", {"btl_a.tm2": b"X"})


class EbootStringExtractTests(unittest.TestCase):
    def test_synthetic_block_filters_non_jp_and_maps_vaddr(self) -> None:
        buf = bytearray(0x180000)
        buf[0x15C4A0 : 0x15C4A0 + len("セーブ".encode("cp932")) + 1] = "セーブ".encode("cp932") + b"\x00"
        # Place non-JP fullwidth string inside date_time block alongside a JP token
        buf[0x15D3E8 : 0x15D3E8 + len("年".encode("cp932")) + 1] = "年".encode("cp932") + b"\x00"
        buf[0x15D3F8 : 0x15D3F8 + len("／".encode("cp932")) + 1] = "／".encode("cp932") + b"\x00"

        res = extract_eboot_strings(bytes(buf))
        self.assertEqual(res["count"], 2)
        self.assertEqual([s["jp"] for s in res["strings"]], ["セーブ", "年"])
        self.assertEqual(res["strings"][0]["vaddr"], "0x0896044c")
        self.assertEqual(res["strings"][0]["slot_capacity"], 0x15C9A0 - 0x15C4A0 - 1)

    @unittest.skipUnless(REAL_EBOOT.exists(), "Local decrypted EBOOT.BIN not present")
    def test_real_eboot_matches_exported_manifest(self) -> None:
        res = extract_eboot_strings(REAL_EBOOT.read_bytes())
        self.assertEqual(res["count"], 73)
        by_cat: dict[str, int] = {}
        for item in res["strings"]:
            by_cat[item["category"]] = by_cat.get(item["category"], 0) + 1
        self.assertEqual(
            by_cat,
            {
                "save_metadata": 3,
                "date_time": 19,
                "save_dialog": 46,
                "install_metadata": 3,
                "install_dialog": 2,
            },
        )
        if REAL_EBOOT_JSON.exists():
            committed = json.loads(REAL_EBOOT_JSON.read_text(encoding="utf-8"))
            self.assertEqual(committed, res)


if __name__ == "__main__":
    unittest.main()
