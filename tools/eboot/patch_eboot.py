"""Version-pinned PJADV proportional-layout proof of concept for ULJS00316 v1.01.

Only the main typewriter parser is wrapped. Ruby and direct-emission callers
still require runtime investigation; this is not a release-ready patch.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from .mips_asm import MipsAsm
except ImportError:
    from mips_asm import MipsAsm


SOURCE_SHA256 = "96f2556cad518943ab0203f2ffe7d471b92e29fae4f8a7fab62a577355ca3de8"
LOAD_VA = 0x08804000
LOAD_OFFSET = 84
PAYLOAD_VA = 0x08A76000  # After the original PT_LOAD memory end, 0x08A75B00.
SLOT_FACTOR = 4


def build_payload(base_va: int = PAYLOAD_VA) -> MipsAsm:
    asm = MipsAsm(base_va)
    asm.add_lines("""
    # a0=context, a1=byte or little-endian SJIS pair. Return advance in v0.
    # Only printable ASCII uses proportional metrics. Japanese/emotes retain
    # the original full-cell advance. f0/f1 and t0..t4 are scratch registers.
    advance:
        sltiu t0, a1, 0x20
        bnez t0, half_cell
        nop
        sltiu t0, a1, 0x7f
        beqz t0, non_ascii
        nop
        lw t0, 0x60(a0)
        li t1, 7
        beq t0, t1, font_large
        li t2, 1
        li t1, 8
        bne t0, t1, font_ready
        nop
        b font_ready
        move t2, zero
    font_large:
        li t2, 2
    font_ready:
        sll t2, t2, 5
        lui t0, 0x08a2
        addiu t0, t0, 0x6924
        addu t0, t0, t2
        lhu t1, 0(t0)
        sltu t1, t1, a1
        bnez t1, half_cell
        nop
        lw t1, 4(t0)
        lw t2, 12(t0)
        beqz t1, half_cell
        nop
        beqz t2, half_cell
        sll t3, a1, 1
        addu t1, t1, t3
        lhu t1, 0(t1)
        sll t3, t1, 3
        addu t3, t3, t1
        sll t3, t3, 1
        addu t2, t2, t3
        lh v0, 8(t2)
        lh t3, 10(t2)
        lh t4, 12(t2)
        addu v0, v0, t3
        addu v0, v0, t4
        bgtz v0, advance_done
        nop
    half_cell:
        lwc1 f0, 0x44(a0)
        trunc.w.s f0, f0
        mfc1 v0, f0
        bgtz v0, advance_done
        nop
        li v0, 1
    advance_done:
        jr ra
        nop
    non_ascii:
        sltiu t0, a1, 0x100
        bnez t0, half_cell
        nop
        lwc1 f0, 0x44(a0)
        li t0, 2
        mtc1 t0, f1
        cvt.s.w f1, f1
        mul.s f0, f0, f1
        trunc.w.s f0, f0
        jr ra
        mfc1 v0, f0

    # Recompute the current line's pixel advance from its byte buffer.
    # No global/per-context extra state: clear, rebuild, and skip use the same
    # original cursor. Stop before the glyph currently being positioned.
    measure:
        addiu sp, sp, -32
        sw ra, 28(sp)
        sw s0, 24(sp)
        sw s1, 20(sp)
        sw s2, 16(sp)
        sw s3, 12(sp)
        move s0, a0
        lw t0, 0x10(s0)
        lw s2, 0x40(s0)
        div s2, t0
        mfhi t1
        subu s1, s2, t1
        lw t0, 0x3c(s0)
        addu s1, s1, t0
        addu s2, s2, t0
        move s3, zero
    measure_loop:
        sltu t0, s1, s2
        beqz t0, measure_done
        nop
        lbu a1, 0(s1)
        beqz a1, measure_next
        nop
        sltiu t0, a1, 0x81
        bnez t0, measure_byte
        nop
        sltiu t0, a1, 0xa0
        bnez t0, measure_pair
        nop
        sltiu t0, a1, 0xe0
        bnez t0, measure_byte
        nop
    measure_pair:
        lbu t0, 1(s1)
        sll t0, t0, 8
        or a1, a1, t0
        b measure_width
        addiu s1, s1, 1
    measure_byte:
        # PJADV emotes use FFxx little-endian pairs, whose low byte can
        # otherwise look like ASCII. Never inspect beyond the cursor.
        addiu t0, s1, 1
        sltu t1, t0, s2
        beqz t1, measure_width
        nop
        lbu t0, 1(s1)
        li t1, 0xff
        bne t0, t1, measure_width
        nop
        ori a1, a1, 0xff00
        addiu s1, s1, 1
    measure_width:
        jal advance
        move a0, s0
        addu s3, s3, v0
    measure_next:
        b measure_loop
        addiu s1, s1, 1
    measure_done:
        move v0, s3
        lw ra, 28(sp)
        lw s0, 24(sp)
        lw s1, 20(sp)
        lw s2, 16(sp)
        lw s3, 12(sp)
        jr ra
        addiu sp, sp, 32

    # Preserve the original pixel capacity despite expanded byte-slot storage.
    budget:
        lw t0, 0x10(a0)
        srl t0, t0, 2
        mtc1 t0, f1
        cvt.s.w f1, f1
        lwc1 f0, 0x44(a0)
        mul.s f0, f0, f1
        trunc.w.s f0, f0
        jr ra
        mfc1 v0, f0

    # Wide emission keeps character wrapping, including emotes, but uses the
    # pixel budget. ASCII gets word lookahead using the parser's s2 source.
    emit_wide:
        li t9, 2
        b emit_begin
        nop
    emit_ascii:
        li t9, 1
    emit_begin:
        addiu sp, sp, -64
        sw a1, 28(sp)
        sw ra, 60(sp)
        sw s0, 56(sp)
        sw s1, 52(sp)
        sw s2, 48(sp)
        sw s3, 44(sp)
        sw s4, 40(sp)
        sw s5, 36(sp)
        sw s6, 32(sp)
        move s0, a0
        move s1, a1
        move s4, a2
        move s5, t9
        jal measure
        nop
        move s3, v0
        jal budget
        move a0, s0
        move s6, v0
        move a0, s0
        jal advance
        move a1, s1
        sw v0, 24(sp)
        beqz s3, emit_call
        nop
        li t0, 1
        bne s5, t0, check_character
        nop
        # Spaces at the end of a full line are consumed without inserting
        # another line or rendering leading whitespace on the next line.
        li t0, 0x20
        beq s1, t0, check_space
        nop
        # Only look ahead at a word's first byte, not on every character.
        lw t0, 0x40(s0)
        lw t1, 0x3c(s0)
        addu t1, t1, t0
        lbu t1, -1(t1)
        lw t0, 48(sp)
        li t2, 0x20
        beq t1, t2, scan_word
        nop
        li t2, 0x2d
        beq t1, t2, scan_word
        nop
        li t2, 0xff
        beq t1, t2, scan_word
        nop
        b check_character
        nop
    scan_word:
        move s2, t0
        move s1, zero
        li t0, 1024
        sw t0, 20(sp)
    scan_loop:
        lbu a1, 0(s2)
        sltiu t0, a1, 0x21
        bnez t0, scan_done
        nop
        sltiu t0, a1, 0x7f
        beqz t0, scan_done
        nop
        li t0, 0x5c
        beq a1, t0, scan_done
        nop
        sw a1, 16(sp)
        jal advance
        move a0, s0
        addu s1, s1, v0
        lw t0, 16(sp)
        li t1, 0x2d
        beq t0, t1, scan_done
        nop
        lw t0, 20(sp)
        addiu t0, t0, -1
        sw t0, 20(sp)
        bnez t0, scan_loop
        addiu s2, s2, 1
    scan_done:
        # A word wider than the whole box must use character fallback.
        slt t0, s6, s1
        bnez t0, check_character
        nop
        addu t0, s3, s1
        slt t0, s6, t0
        bnez t0, insert_newline
        nop
    check_character:
        lw t0, 24(sp)
        addu t0, t0, s3
        slt t0, s6, t0
        beqz t0, emit_call
        nop
    insert_newline:
        jal 0x0887c400
        move a0, s0
        b emit_call
        nop
    check_space:
        addu t0, s3, v0
        slt t0, s6, t0
        beqz t0, emit_call
        nop
        jal 0x0887c400
        move a0, s0
        b emit_return
        li v0, 1
    emit_call:
        move a0, s0
        # s1 may have been reused as the lookahead sum. Read the original
        # character saved at entry, never alter the source or its controls.
        lw a1, 28(sp)
        move a2, s4
        li t0, 1
        bne s5, t0, call_wide
        nop
        jal 0x0887bfd4
        nop
        b emit_return
        nop
    call_wide:
        jal 0x0887b97c
        nop
    emit_return:
        lw ra, 60(sp)
        lw s0, 56(sp)
        lw s1, 52(sp)
        lw s2, 48(sp)
        lw s3, 44(sp)
        lw s4, 40(sp)
        lw s5, 36(sp)
        lw s6, 32(sp)
        jr ra
        addiu sp, sp, 64

    # Call sites in both emitters use s1=context. The original positioning
    # function still sets all four sprite bounds, with our corrected x.
    position:
        addiu sp, sp, -32
        sw ra, 28(sp)
        sw a0, 24(sp)
        sw a2, 20(sp)
        jal measure
        move a0, s1
        lw t0, 0x4c(s1)
        addu a1, t0, v0
        lw a0, 24(sp)
        jal 0x08881828
        lw a2, 20(sp)
        lw ra, 28(sp)
        jr ra
        addiu sp, sp, 32
    """)
    return asm


def patch_bytes(source: bytes) -> tuple[bytes, dict[str, int]]:
    if len(source) != 1_527_040 or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("Expected the clean ULJS00316 v1.01 decrypted EBOOT; source identity mismatch")
    asm = build_payload()
    payload = asm.assemble()
    result = bytearray(source)

    def replace(va: int, expected: str, replacement: str) -> None:
        old = MipsAsm(va)
        old.add_lines(expected)
        new = MipsAsm(va)
        new.add_lines(replacement)
        offset = va - LOAD_VA + LOAD_OFFSET
        before, after = old.assemble(), new.assemble()
        if len(before) != len(after) or result[offset:offset + len(before)] != before:
            raise ValueError(f"Unexpected instructions at {va:#x}")
        result[offset:offset + len(after)] = after

    # Four times as many byte slots, allocated through the original arithmetic.
    # Geometry and original pixel width are unchanged. This also increases
    # per-context buffers; memory pressure must be measured on PSP/PPSSPP.
    replace(0x0887B3DC, "sll s0, v0, 1", "sll s0, v0, 3")
    replace(0x0887DB8C, "jal 0x0887bfd4", f"jal {asm.labels['emit_ascii']:#x}")
    replace(0x0887D7D0, "jal 0x0887bfd4", f"jal {asm.labels['emit_ascii']:#x}")
    for va in (0x0887DB70, 0x0887DA14, 0x0887DA28, 0x0887DA44,
               0x0887DAB0, 0x0887DAC4, 0x0887DAFC, 0x0887DB14):
        replace(va, "jal 0x0887b97c", f"jal {asm.labels['emit_wide']:#x}")
    for va in (0x0887C3B0, 0x0887BF84):
        replace(va, "jal 0x08881828", f"jal {asm.labels['position']:#x}")

    # Keep the original PT_LOAD's file and memory bounds intact. Adding another
    # segment avoids filling/reusing BSS or overwriting alleged code caves.
    phoff = struct.unpack_from("<I", source, 28)[0]
    original_ph = source[phoff:phoff + 32]
    segment = struct.unpack("<8I", original_ph)
    if segment != (1, LOAD_OFFSET, LOAD_VA, 1_335_696, 1_525_296, 2_562_816, 7, 16):
        raise ValueError("Unexpected original PT_LOAD layout")
    new_phoff = (len(result) + 15) & ~15
    payload_offset = new_phoff + 64
    result.extend(bytes(new_phoff - len(result)))
    result.extend(original_ph)
    result.extend(struct.pack("<8I", 1, payload_offset, PAYLOAD_VA, PAYLOAD_VA,
                              len(payload), len(payload), 5, 16))
    result.extend(payload)
    struct.pack_into("<I", result, 28, new_phoff)
    struct.pack_into("<H", result, 44, 2)
    return bytes(result), {"payload_va": PAYLOAD_VA, "payload_bytes": len(payload),
                           "slot_factor": SLOT_FACTOR, **asm.labels}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if args.src.resolve() == args.out.resolve() or args.out.exists():
        raise SystemExit("Output must be a new file, separate from the clean EBOOT")
    patched, info = patch_bytes(args.src.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as out:
        out.write(patched)
    print(f"Patched EBOOT: {len(patched)} bytes; payload={info['payload_bytes']} bytes at {PAYLOAD_VA:#x}")
    print("Proof of concept only: PPSSPP, ruby, direct emitters, and memory pressure remain unverified")


if __name__ == "__main__":
    main()
