"""PJADV PSP (scenario.bin + textdata.bin) extractor, rebuilder, and verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive  # noqa: E402
from pjadv.chunk_bin import ChunkedBinMeta, pack_chunked_bin, unpack_chunked_bin  # noqa: E402


CTRL_RE = re.compile(r"\\(?:n|[sS]\d{2})")
SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f\u3000\s]+')

OP_MSG = 0x80000307
OP_MSG_ALT = 0x80000406
OP_OVERLAY = 0x3000303
OP_LABEL = 0xF0010005
OP_SCENE = 0x1000D02


def parse_textdata(td: bytes) -> tuple[bytes, int, list[tuple[int, bytes, str]], dict[int, int]]:
    """Parse PJADV_TF0001 textdata blob into (header16, declared_count, entries, offset->index)."""
    if td[:12] != b"PJADV_TF0001":
        raise ValueError(f"Unexpected textdata magic: {td[:12]!r}")
    declared_count = struct.unpack_from("<I", td, 12)[0]
    entries: list[tuple[int, bytes, str]] = []
    off_to_idx: dict[int, int] = {}
    pos = 16
    idx = 0
    while pos < len(td):
        end = td.find(b"\x00\x00", pos)
        if end < 0:
            raise ValueError(f"Missing 0x0000 terminator at {pos:#x}")
        raw_bytes = td[pos:end]
        text = raw_bytes.decode("cp932")
        off_to_idx[pos] = idx
        entries.append((pos, raw_bytes, text))
        pos = end + 2
        idx += 1
    if len(entries) != declared_count:
        raise ValueError(f"Parsed {len(entries)} strings, header declares {declared_count}")
    return td[:16], declared_count, entries, off_to_idx


def walk_scenario(sc: bytes) -> list[tuple[int, int, tuple[int, ...]]]:
    """Walk all PJADV_SF0001 instructions in scenario.bin."""
    if sc[:12] != b"PJADV_SF0001":
        raise ValueError(f"Unexpected scenario magic: {sc[:12]!r}")
    insns: list[tuple[int, int, tuple[int, ...]]] = []
    p = 32
    end = len(sc)
    while p < end:
        w0 = struct.unpack_from("<I", sc, p)[0]
        wlen = w0 & 0xFF
        if wlen == 0 or p + wlen * 4 > end:
            raise ValueError(f"Invalid instruction wordlen={wlen} at {p:#x}")
        words = struct.unpack_from(f"<{wlen}I", sc, p)
        insns.append((p, w0, words))
        p += wlen * 4
    if p != end:
        raise ValueError(f"Scenario walk ended at {p:#x} != {end:#x}")
    return insns


def _sanitize_slug(text: str) -> str:
    s = text.split("###", 1)[0].strip()
    s = SAFE_NAME_RE.sub("_", s).strip("_")
    return (s[:40] or "scene")


def _extract_ctrl(text: str) -> list[str]:
    return CTRL_RE.findall(text)


def extract_from_bytes(
    td_raw: bytes,
    sc_raw: bytes,
    out_dir: Path,
    source_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract GalTransl JSON files and metadata from raw textdata.bin and scenario.bin bytes."""
    td, td_meta = unpack_chunked_bin(td_raw)
    sc, sc_meta = unpack_chunked_bin(sc_raw)
    _, _, td_entries, off_to_idx = parse_textdata(td)
    insns = walk_scenario(sc)

    def get_str(off: int) -> tuple[int, str]:
        idx = off_to_idx[off]
        return idx, td_entries[idx][2]

    # Group instructions by 0x1000d02 scene markers
    blocks: list[dict[str, Any]] = []
    cur_block: dict[str, Any] = {"scene_op_off": None, "scene_td_off": None, "scene_raw": "preamble", "items": []}

    for sc_off, w0, words in insns:
        if w0 == OP_SCENE:
            if cur_block["items"] or cur_block["scene_op_off"] is not None:
                blocks.append(cur_block)
            td_off = words[1]
            _, title_raw = get_str(td_off)
            cur_block = {
                "scene_op_off": sc_off,
                "scene_td_off": td_off,
                "scene_raw": title_raw,
                "items": [],
            }
        elif w0 in (OP_MSG, OP_MSG_ALT):
            spk_off, msg_off = words[2], words[3]
            if msg_off == 0:
                continue
            _, msg_text = get_str(msg_off)
            if msg_text.startswith("###"):
                continue
            spk_text = get_str(spk_off)[1] if spk_off else None
            cur_block["items"].append(
                {
                    "kind": "dialogue",
                    "sc_off": sc_off,
                    "w0": w0,
                    "spk_off": spk_off,
                    "spk": spk_text,
                    "msg_off": msg_off,
                    "msg": msg_text,
                }
            )
        elif w0 == OP_OVERLAY:
            msg_off = words[2]
            if msg_off == 0:
                continue
            _, msg_text = get_str(msg_off)
            if msg_text.startswith("###"):
                continue
            cur_block["items"].append(
                {
                    "kind": "overlay",
                    "sc_off": sc_off,
                    "w0": w0,
                    "msg_off": msg_off,
                    "msg": msg_text,
                }
            )
        elif w0 == OP_LABEL:
            lbl_off = words[1]
            if lbl_off == 0:
                continue
            _, lbl_text = get_str(lbl_off)
            if lbl_text.startswith("###"):
                continue
            cur_block["items"].append(
                {
                    "kind": "label",
                    "sc_off": sc_off,
                    "w0": w0,
                    "msg_off": lbl_off,
                    "msg": lbl_text,
                }
            )

    if cur_block["items"] or cur_block["scene_op_off"] is not None:
        blocks.append(cur_block)

    gt_input_dir = out_dir / "gt_input"
    gt_output_dir = out_dir / "gt_output"
    orig_dir = out_dir / "original"
    meta_dir = out_dir / "metadata"
    reports_dir = out_dir / "reports"
    for d in (gt_input_dir, gt_output_dir, orig_dir, meta_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)

    (orig_dir / "textdata.bin").write_bytes(td_raw)
    (orig_dir / "scenario.bin").write_bytes(sc_raw)

    files_meta: list[dict[str, Any]] = []
    total_lines = 0
    total_chars = 0
    file_num = 0

    for blk in blocks:
        entries_json: list[dict[str, str]] = []
        slots_meta: list[dict[str, Any]] = []

        # Include visible scene title if present and translatable
        s_raw = blk["scene_raw"]
        if blk["scene_op_off"] is not None and not s_raw.startswith("###") and s_raw.strip("\u3000 \t"):
            if "###" in s_raw:
                vis, suffix = s_raw.split("###", 1)
                suffix = "###" + suffix
            else:
                vis, suffix = s_raw, ""
            if vis.strip("\u3000 \t"):
                entries_json.append({"message": vis})
                slots_meta.append(
                    {
                        "kind": "scene_title",
                        "sc_off": blk["scene_op_off"],
                        "w0": OP_SCENE,
                        "msg_slot": 1,
                        "orig_msg_off": blk["scene_td_off"],
                        "orig_msg": vis,
                        "suffix": suffix,
                    }
                )

        for it in blk["items"]:
            if it["kind"] == "dialogue":
                obj: dict[str, str] = {}
                if it["spk"] is not None:
                    obj["name"] = it["spk"]
                obj["message"] = it["msg"]
                entries_json.append(obj)
                slots_meta.append(
                    {
                        "kind": "dialogue",
                        "sc_off": it["sc_off"],
                        "w0": it["w0"],
                        "spk_slot": 2 if it["spk"] is not None else None,
                        "orig_spk_off": it["spk_off"],
                        "orig_spk": it["spk"],
                        "msg_slot": 3,
                        "orig_msg_off": it["msg_off"],
                        "orig_msg": it["msg"],
                        "ctrl": _extract_ctrl(it["msg"]),
                    }
                )
            elif it["kind"] == "overlay":
                entries_json.append({"message": it["msg"]})
                slots_meta.append(
                    {
                        "kind": "overlay",
                        "sc_off": it["sc_off"],
                        "w0": it["w0"],
                        "msg_slot": 2,
                        "orig_msg_off": it["msg_off"],
                        "orig_msg": it["msg"],
                        "ctrl": _extract_ctrl(it["msg"]),
                    }
                )
            elif it["kind"] == "label":
                entries_json.append({"message": it["msg"]})
                slots_meta.append(
                    {
                        "kind": "label",
                        "sc_off": it["sc_off"],
                        "w0": it["w0"],
                        "msg_slot": 1,
                        "orig_msg_off": it["msg_off"],
                        "orig_msg": it["msg"],
                        "ctrl": _extract_ctrl(it["msg"]),
                    }
                )

        if not entries_json:
            continue

        file_num += 1
        fname = f"{file_num:04d}_{_sanitize_slug(s_raw)}.json"
        (gt_input_dir / fname).write_text(
            json.dumps(entries_json, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        total_lines += len(entries_json)
        total_chars += sum(len(e["message"]) for e in entries_json)
        files_meta.append(
            {
                "file": fname,
                "scene_raw": s_raw,
                "count": len(entries_json),
                "slots": slots_meta,
            }
        )

    manifest = {
        "engine": "PJADV_PSP",
        "source": source_info or {},
        "original_hashes": {
            "textdata.bin": hashlib.sha256(td_raw).hexdigest(),
            "scenario.bin": hashlib.sha256(sc_raw).hexdigest(),
        },
        "td_chunk_meta": {
            "names": td_meta.names,
            "chunk_size": td_meta.chunk_size,
            "end_padding_hex": td_meta.end_padding.hex(),
        },
        "sc_chunk_meta": {
            "names": sc_meta.names,
            "chunk_size": sc_meta.chunk_size,
            "end_padding_hex": sc_meta.end_padding.hex(),
        },
        "summary": {
            "json_files": len(files_meta),
            "entries": total_lines,
            "jp_chars": total_chars,
            "pool_strings": len(td_entries),
        },
    }
    (meta_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (meta_dir / "scenario_slots.json").write_text(
        json.dumps(files_meta, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def pack_from_dir(
    work_dir: Path,
    trans_dir: Path | None = None,
    encoding: str = "cp932",
    strict_ctrl: bool = True,
) -> tuple[bytes, bytes, dict[str, Any]]:
    """Rebuild textdata.bin and scenario.bin from translated JSON files and metadata."""
    meta_dir = work_dir / "metadata"
    orig_dir = work_dir / "original"
    manifest = json.loads((meta_dir / "manifest.json").read_text(encoding="utf-8"))
    files_meta = json.loads((meta_dir / "scenario_slots.json").read_text(encoding="utf-8"))

    td_orig_raw = (orig_dir / "textdata.bin").read_bytes()
    sc_orig_raw = (orig_dir / "scenario.bin").read_bytes()
    if hashlib.sha256(td_orig_raw).hexdigest() != manifest["original_hashes"]["textdata.bin"]:
        raise ValueError("original/textdata.bin hash mismatch")
    if hashlib.sha256(sc_orig_raw).hexdigest() != manifest["original_hashes"]["scenario.bin"]:
        raise ValueError("original/scenario.bin hash mismatch")

    td_orig, td_meta = unpack_chunked_bin(td_orig_raw)
    sc_orig, sc_meta = unpack_chunked_bin(sc_orig_raw)
    td_hdr, _, td_entries, off_to_idx = parse_textdata(td_orig)

    if trans_dir is None:
        trans_dir = work_dir / "gt_output"

    # Track updates per pool index: pool_idx -> {new_text: [(sc_off, slot), ...]}
    edits_by_pool: dict[int, dict[str, list[tuple[int, int]]]] = {}
    warnings: list[str] = []

    for fmeta in files_meta:
        fname = fmeta["file"]
        tpath = trans_dir / fname
        if not tpath.exists():
            # Fallback to gt_input if partially translated
            tpath = work_dir / "gt_input" / fname
        rows = json.loads(tpath.read_text(encoding="utf-8"))
        if len(rows) != fmeta["count"]:
            raise ValueError(f"{fname}: expected {fmeta['count']} entries, got {len(rows)}")

        for row_idx, (row, slot) in enumerate(zip(rows, fmeta["slots"])):
            # Validate speaker slot
            if slot.get("spk_slot") is not None:
                if "name" not in row:
                    raise ValueError(f"{fname}[{row_idx}]: missing 'name' field")
                spk_val = row["name"]
                spk_pool_idx = off_to_idx[slot["orig_spk_off"]]
                edits_by_pool.setdefault(spk_pool_idx, {}).setdefault(spk_val, []).append(
                    (slot["sc_off"], slot["spk_slot"])
                )
            elif "name" in row:
                raise ValueError(f"{fname}[{row_idx}]: unexpected 'name' field on narration/label")

            if "message" not in row:
                raise ValueError(f"{fname}[{row_idx}]: missing 'message' field")
            msg_val = row["message"]
            if slot["kind"] == "scene_title" and slot.get("suffix"):
                msg_val = msg_val + slot["suffix"]

            if strict_ctrl and "ctrl" in slot:
                got_ctrl = _extract_ctrl(msg_val)
                if sorted(got_ctrl) != sorted(slot["ctrl"]):
                    warnings.append(
                        f"{fname}[{row_idx}]: control codes changed {slot['ctrl']} -> {got_ctrl}"
                    )

            msg_pool_idx = off_to_idx[slot["orig_msg_off"]]
            edits_by_pool.setdefault(msg_pool_idx, {}).setdefault(msg_val, []).append(
                (slot["sc_off"], slot["msg_slot"])
            )

    # Rebuild textdata pool in original order, appending split duplicates at end
    pool_bytes: list[bytes] = []
    extra_entries: list[tuple[bytes, list[tuple[int, int]]]] = []
    idx_to_new_off: dict[int, int] = {}

    cur_off = 16
    for idx, (_orig_off, orig_raw_bytes, orig_text) in enumerate(td_entries):
        idx_to_new_off[idx] = cur_off
        variants = edits_by_pool.get(idx)
        if not variants:
            b = orig_raw_bytes
        else:
            # Prefer original string as primary if present, else the first variant
            if orig_text in variants and len(variants) == 1:
                b = orig_raw_bytes
            else:
                v_items = list(variants.items())
                primary_text, _ = v_items[0]
                b = orig_raw_bytes if primary_text == orig_text else primary_text.encode(encoding)
                for extra_text, refs in v_items[1:]:
                    eb = extra_text.encode(encoding)
                    extra_entries.append((eb, refs))
        pool_bytes.append(b)
        cur_off += len(b) + 2  # + \x00\x00

    # Append split variants (when same original string received multiple translations)
    extra_patches: list[tuple[int, int, int]] = []
    for eb, refs in extra_entries:
        new_off = cur_off
        pool_bytes.append(eb)
        cur_off += len(eb) + 2
        for sc_off, slot_idx in refs:
            extra_patches.append((sc_off, slot_idx, new_off))

    total_strings = len(td_entries) + len(extra_entries)
    new_td_hdr = bytearray(td_hdr)
    struct.pack_into("<I", new_td_hdr, 12, total_strings)
    new_td = bytes(new_td_hdr) + b"\x00\x00".join(pool_bytes) + b"\x00\x00"

    # Patch all 5 text-referencing opcodes in scenario.bin
    new_sc = bytearray(sc_orig)
    for sc_off, w0, words in walk_scenario(sc_orig):
        if w0 in (OP_MSG, OP_MSG_ALT):
            for s in (2, 3):
                if words[s]:
                    new_off = idx_to_new_off[off_to_idx[words[s]]]
                    struct.pack_into("<I", new_sc, sc_off + s * 4, new_off)
        elif w0 == OP_OVERLAY:
            if words[2]:
                new_off = idx_to_new_off[off_to_idx[words[2]]]
                struct.pack_into("<I", new_sc, sc_off + 8, new_off)
        elif w0 in (OP_LABEL, OP_SCENE):
            if words[1]:
                new_off = idx_to_new_off[off_to_idx[words[1]]]
                struct.pack_into("<I", new_sc, sc_off + 4, new_off)

    for sc_off, slot_idx, new_off in extra_patches:
        struct.pack_into("<I", new_sc, sc_off + slot_idx * 4, new_off)

    packed_td = pack_chunked_bin(new_td, td_meta, prefix_hint="textdata")
    packed_sc = pack_chunked_bin(bytes(new_sc), sc_meta, prefix_hint="scenario")
    stats = {
        "total_pool_strings": total_strings,
        "split_duplicates": len(extra_entries),
        "warnings": warnings,
    }
    return packed_td, packed_sc, stats


def main() -> None:
    ap = argparse.ArgumentParser(description="PJADV PSP scenario extractor/rebuilder")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ex = sub.add_parser("extract")
    p_ex.add_argument("--cpk", required=True, help="Path to GAMEINIT.CPK")
    p_ex.add_argument("--out", required=True, help="Workspace output directory")

    p_pk = sub.add_parser("pack")
    p_pk.add_argument("--work", required=True, help="Workspace directory")
    p_pk.add_argument("--trans", help="Translation directory (defaults to <work>/gt_output)")
    p_pk.add_argument("--out-cpk", help="Optional rebuilt GAMEINIT.CPK path")
    p_pk.add_argument("--cpk", help="Original GAMEINIT.CPK (required with --out-cpk)")
    p_pk.add_argument("--out-dir", help="Optional dir to write textdata.bin and scenario.bin")

    p_vr = sub.add_parser("verify-roundtrip")
    p_vr.add_argument("--work", required=True, help="Extracted workspace directory")
    p_vr.add_argument("--verify-edits", action="store_true", help="Also run synthetic edit round-trip check")

    args = ap.parse_args()

    if args.cmd == "extract":
        cpk = CpkArchive(args.cpk)
        td_row = next(r for r in cpk.entries() if r["DirName"] == "scenario" and r["FileName"] == "textdata.bin")
        sc_row = next(r for r in cpk.entries() if r["DirName"] == "scenario" and r["FileName"] == "scenario.bin")
        td_raw = cpk.read_entry(td_row)
        sc_raw = cpk.read_entry(sc_row)
        cpk_sha = hashlib.sha256(Path(args.cpk).read_bytes()).hexdigest()
        manifest = extract_from_bytes(
            td_raw,
            sc_raw,
            Path(args.out),
            source_info={"cpk": str(args.cpk), "cpk_sha256": cpk_sha},
        )
        print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))

    elif args.cmd == "pack":
        work = Path(args.work)
        td_packed, sc_packed, stats = pack_from_dir(
            work, Path(args.trans) if args.trans else None
        )
        if args.out_dir:
            od = Path(args.out_dir)
            od.mkdir(parents=True, exist_ok=True)
            (od / "textdata.bin").write_bytes(td_packed)
            (od / "scenario.bin").write_bytes(sc_packed)
        if args.out_cpk:
            if not args.cpk:
                raise SystemExit("--cpk is required with --out-cpk")
            cpk = CpkArchive(args.cpk)
            cpk.rebuild(
                args.out_cpk,
                {"scenario/textdata.bin": td_packed, "scenario/scenario.bin": sc_packed},
            )
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.cmd == "verify-roundtrip":
        work = Path(args.work)
        td_orig = (work / "original" / "textdata.bin").read_bytes()
        sc_orig = (work / "original" / "scenario.bin").read_bytes()
        td_reb, sc_reb, stats = pack_from_dir(work, work / "gt_input")
        td_ok = td_orig == td_reb
        sc_ok = sc_orig == sc_reb
        print(f"Untouched JP round-trip: textdata.bin={td_ok}, scenario.bin={sc_ok}, stats={stats}")
        if not (td_ok and sc_ok):
            raise SystemExit(1)

        if args.verify_edits:
            import tempfile
            with tempfile.TemporaryDirectory() as td_tmp:
                tmp_path = Path(td_tmp)
                trans_copy = tmp_path / "trans"
                trans_copy.mkdir()
                # Copy gt_input and inject synthetic ASCII/SJIS edits into the first 2 JSONs
                manifest = json.loads((work / "metadata" / "manifest.json").read_text(encoding="utf-8"))
                files_meta = json.loads((work / "metadata" / "scenario_slots.json").read_text(encoding="utf-8"))
                target_files = [files_meta[0]["file"], files_meta[1]["file"]]
                for fm in files_meta:
                    fn = fm["file"]
                    src_json = work / "gt_input" / fn
                    if fn in target_files:
                        data = json.loads(src_json.read_text(encoding="utf-8"))
                        for idx, row in enumerate(data[:5]):
                            if "name" in row:
                                row["name"] = "Synn"
                            row["message"] = f"TEST_LINE_{idx}: Hello world!"
                        (trans_copy / fn).write_text(
                            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                    else:
                        (trans_copy / fn).write_bytes(src_json.read_bytes())

                td_ed, sc_ed, ed_stats = pack_from_dir(work, trans_copy)
                re_out = tmp_path / "re_extract"
                extract_from_bytes(td_ed, sc_ed, re_out)
                for fn in target_files:
                    expected = json.loads((trans_copy / fn).read_text(encoding="utf-8"))
                    actual = json.loads((re_out / "gt_input" / fn).read_text(encoding="utf-8"))
                    assert expected == actual, f"Edit round-trip mismatch in {fn}"
                print(f"Synthetic edit verification: PASSED (split_duplicates={ed_stats['split_duplicates']})")


if __name__ == "__main__":
    main()
