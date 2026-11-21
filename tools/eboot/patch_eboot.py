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
SLOT_FACTOR = 1.5  # 3/2 ratio keeps 3-line dialogue at 78 * 3 = 234 <= 0xF8 (248) for serializer 0x0887F2F8.


def build_payload(base_va: int = PAYLOAD_VA) -> MipsAsm:
    asm = MipsAsm(base_va)
    asm.add_lines("""
    # a0=context, a1=byte or little-endian SJIS pair. Return advance in v0.
    # Only printable ASCII uses proportional metrics. Japanese/emotes retain
    # the original full-cell advance. f0/f1 and t0..t4 are scratch registers.
    advance:
        lwc1 f0, 0x44(a0)
        lw a0, 0x60(a0)
    # a0=font_id (0=normal, 7=large, 8=small), a1=char, f0=half_cell. Return advance in v0.
    advance_by_font:
        sltiu t0, a1, 0x20
        bnez t0, half_cell
        nop
        sltiu t0, a1, 0x7f
        beqz t0, non_ascii
        nop
        li t1, 7
        beq a0, t1, font_large
        li t2, 1
        li t1, 8
        bne a0, t1, font_ready
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

    # Preserve the original pixel capacity despite 1.5x expanded byte-slot storage.
    budget:
        lw t0, 0x10(a0)
        sll t0, t0, 1
        li t1, 3
        div t0, t1
        mflo t0
        mtc1 t0, f1
        cvt.s.w f1, f1
        lwc1 f0, 0x44(a0)
        mul.s f0, f0, f1
        trunc.w.s f0, f0
        jr ra
        mfc1 v0, f0

    # Expand line slots from 2x (set by delay slot sll s0, v0, 1) to 3x (1.5x original).
    # Delay slot computes LO = s0 * s1 for 0x0887B3E4: mflo a0.
    expand_slots:
        addu s0, s0, v0
        jr ra
        mult s0, s1

    # Defensive guard for fixed 0xF8-slot serializer records at 0x0887F2F8.
    clamp_save_slots:
        sltiu t0, s0, 0xf9
        bnez t0, clamp_save_done
        nop
        li s0, 0xf8
    clamp_save_done:
        jr ra
        lw a1, 0x3c(v0)

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
        # Preserve the space byte in ctx->text_buf before jumping lines so backlog
        # capture (0x0887F924) does not join wrapped words when 0x00 padding is skipped.
        lw t0, 0x40(s0)
        lw t1, 0x10(s0)
        lw t2, 0x14(s0)
        mult t1, t2
        mflo t1
        slt t2, t0, t1
        beqz t2, check_space_nl
        nop
        lw t1, 0x3c(s0)
        addu t1, t1, t0
        li t2, 0x20
        sb t2, 0(t1)
    check_space_nl:
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

    # Bounds-check fade_add_main (0x0887E500) so oversized contexts cannot
    # write past fade_obj->0x10 and corrupt adjacent heap allocations.
    fade_add_checked:
        beqz a2, fade_add_reject
        nop
        lw v1, 4(a0)
        lw t0, 0xc(a0)
        slt t0, v1, t0
        beqz t0, fade_add_reject
        nop
        j 0x0887e514
        nop
    fade_add_reject:
        jr ra
        move v0, zero

    # Guard load_text_ctxs (0x0887F5D8) against old SLOT_FACTOR=4 saves (> 0xF8 slots)
    # whose saved line buffers exceed the fixed 0x1458-byte save record.
    guard_load_ctx:
        blez a2, load_ctx_empty
        move s2, zero
        lw v0, 0x10(s5)
        blez v0, load_ctx_empty
        nop
        mult v0, a2
        mflo t0
        sltiu t1, t0, 0xf9
        bnez t1, load_ctx_ok
        nop
        # Skip emit loop and advance s4 past 0xF8 * 0x14 = 0x1360 bytes.
        li v0, 0x1360
        lw a1, 0(s5)
        move a0, s0
        j 0x0887f8dc
        nop
    load_ctx_ok:
        j 0x0887f780
        nop
    load_ctx_empty:
        j 0x0887f8b4
        nop

    # Backlog speaker ASCII advance (replaces fixed half_cell at 0x0888052C).
    # Returns advance in v1; preserves v0 = lw 0x4c(sp) set at call site.
    backlog_speaker_adv:
        addiu sp, sp, -16
        sw ra, 12(sp)
        sw v0, 8(sp)
        lw a0, 0x44(s5)
        jal advance_by_font
        lbu a1, 0(s0)
        move v1, v0
        lw v0, 8(sp)
        lw ra, 12(sp)
        jr ra
        addiu sp, sp, 16

    # Backlog body ASCII advance (replaces fixed half_cell at 0x08880B08).
    # Returns advance in v0 and char_w in t0 for the right-edge check.
    backlog_body_adv:
        addiu sp, sp, -16
        sw ra, 12(sp)
        lw a0, 0x48(s5)
        jal advance_by_font
        lbu a1, 0(s4)
        lw t0, 0x50(s5)
        lw ra, 12(sp)
        jr ra
        addiu sp, sp, 16

    # Backlog body ASCII word wrap (hooked at 0x088809FC with lw t1, 0x48(s5)).
    # Preserves s0, s3..s7, fp, a0 unless wrapping updates s1/s2 or exits.
    backlog_body_wrap:
        lbu t0, 0(s4)
        bne s2, s6, bw_check_wrap
        nop
        li t2, 0x20
        beq t0, t2, bw_consume_space
        nop
        b bw_done
        nop
    bw_check_wrap:
        lw t2, 0x50(sp)
        lw t3, 0x3c(sp)
        addiu sp, sp, -32
        sw ra, 28(sp)
        sw a0, 24(sp)
        sw s0, 20(sp)
        sw t2, 16(sp)
        sw t3, 12(sp)
        sw t1, 8(sp)
        li t4, 0x20
        bne t0, t4, bw_word
        nop
        lw a0, 8(sp)
        lwc1 f0, 0x28(s5)
        jal advance_by_font
        move a1, t0
        lw t4, 0x50(s5)
        addu t4, fp, t4
        addu t0, s2, v0
        slt t0, t4, t0
        beqz t0, bw_restore
        nop
        lw v1, 0x30(s5)
        lw t3, 12(sp)
        addu s1, s1, v1
        slt t0, t3, s1
        bnez t0, bw_overflow
        nop
        move s2, s6
        lw ra, 28(sp)
        lw a0, 24(sp)
        lw s0, 20(sp)
        j 0x08880b40
        addiu sp, sp, 32
    bw_word:
        beqz s7, bw_at_boundary
        nop
        lbu t2, -1(s4)
        li t4, 0x20
        beq t2, t4, bw_at_boundary
        nop
        li t4, 0x2d
        beq t2, t4, bw_at_boundary
        nop
        beqz t2, bw_at_boundary
        nop
        b bw_char_check
        nop
    bw_at_boundary:
        move s0, s4
        sw s7, 4(sp)
        sw zero, 0(sp)
    bw_scan_loop:
        lw t2, 4(sp)
        lw t3, 16(sp)
        slt t4, t2, t3
        beqz t4, bw_scan_done
        nop
        lbu a1, 0(s0)
        sltiu t4, a1, 0x21
        bnez t4, bw_scan_done
        nop
        sltiu t4, a1, 0x7f
        beqz t4, bw_scan_done
        nop
        lw a0, 8(sp)
        lwc1 f0, 0x28(s5)
        jal advance_by_font
        nop
        lw t0, 0(sp)
        addu t0, t0, v0
        sw t0, 0(sp)
        lbu t0, 0(s0)
        li t4, 0x2d
        beq t0, t4, bw_scan_done
        nop
        lw t2, 4(sp)
        addiu t2, t2, 1
        sw t2, 4(sp)
        b bw_scan_loop
        addiu s0, s0, 1
    bw_scan_done:
        lw t0, 0(sp)
        lw t4, 0x50(s5)
        addu t4, fp, t4
        subu t1, t4, s6
        slt t1, t1, t0
        bnez t1, bw_char_check
        nop
        addu t1, s2, t0
        slt t1, t4, t1
        bnez t1, bw_newline
        nop
    bw_char_check:
        lw a0, 8(sp)
        lwc1 f0, 0x28(s5)
        jal advance_by_font
        lbu a1, 0(s4)
        lw t4, 0x50(s5)
        addu t4, fp, t4
        addu t0, s2, v0
        slt t0, t4, t0
        beqz t0, bw_restore
        nop
    bw_newline:
        lw v1, 0x30(s5)
        lw t3, 12(sp)
        addu s1, s1, v1
        slt t0, t3, s1
        bnez t0, bw_overflow
        nop
        move s2, s6
    bw_restore:
        lw ra, 28(sp)
        lw a0, 24(sp)
        lw s0, 20(sp)
        addiu sp, sp, 32
    bw_done:
        lui v0, 0x8a2
        lw v0, 0x18b4(v0)
        lw t1, 0x48(s5)
        j 0x08880a04
        nop
    bw_consume_space:
        j 0x08880b40
        nop
    bw_overflow:
        lw ra, 28(sp)
        lw a0, 24(sp)
        lw s0, 20(sp)
        j 0x08880b88
        addiu sp, sp, 32

    # Clamp backlog capture copy length (0x0887FA74) to caller's max_bytes (a3:
    # 0x40 for speaker, 0xF8 for body) so 1.5x expanded contexts cannot overflow
    # the fixed 0x58-byte speaker backlog record into adjacent heap chunks.
    clamp_backlog_copy:
        sltu t0, a3, v0
        beqz t0, cbc_ok
        nop
        move v0, a3
    cbc_ok:
        jr ra
        sw v0, 0xc(s2)
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

    # Expand byte slots by 1.5x (78 * 3 = 234 <= 248 = 0xF8) so proportional
    # lines fit without overflowing the fixed 0xF8-slot state serializer.
    replace(0x0887B3DC, "sll s0, v0, 1\nmult s0, s1",
            f"jal {asm.labels['expand_slots']:#x}\nsll s0, v0, 1")
    replace(0x0887F4B0, "mflo s0\nlw a1, 0x3c(v0)",
            f"jal {asm.labels['clamp_save_slots']:#x}\nmflo s0")
    replace(0x0887DB8C, "jal 0x0887bfd4", f"jal {asm.labels['emit_ascii']:#x}")
    replace(0x0887D7D0, "jal 0x0887bfd4", f"jal {asm.labels['emit_ascii']:#x}")
    for va in (0x0887DB70, 0x0887DA14, 0x0887DA28, 0x0887DA44,
               0x0887DAB0, 0x0887DAC4, 0x0887DAFC, 0x0887DB14):
        replace(va, "jal 0x0887b97c", f"jal {asm.labels['emit_wide']:#x}")
    for va in (0x0887C3B0, 0x0887BF84):
        replace(va, "jal 0x08881828", f"jal {asm.labels['position']:#x}")

    # Guard fade_add_main against out-of-bounds sprite writes and skip/guard
    # corrupted SLOT_FACTOR=4 saves in load_text_ctxs.
    replace(0x0887E500, "lw a2, 0x10(a0)\nbnel a2, zero, 0x0887e514",
            f"j {asm.labels['fade_add_checked']:#x}\nlw a2, 0x10(a0)")
    replace(0x0887F774, "addiu s4, s4, 0x15c\nblez a2, 0x0887f8b4",
            f"j {asm.labels['guard_load_ctx']:#x}\naddiu s4, s4, 0x15c")
    replace(0x0887F880, "jal 0x0887b97c", "jal 0x0887bfd4")

    # Backlog renderer (0x0887FE40): proportional spacing + word wrap.
    replace(0x0888052C, "lwc1 f0, 0x24(s5)\nlw v0, 0x4c(sp)\ntrunc.w.s f0, f0\nmfc1 v1, f0",
            f"jal {asm.labels['backlog_speaker_adv']:#x}\nlwc1 f0, 0x24(s5)\nlw v0, 0x4c(sp)\nnop")
    replace(0x088809FC, "lw v0, 0x18b4(v0)\nlw t1, 0x48(s5)",
            f"j {asm.labels['backlog_body_wrap']:#x}\nlw t1, 0x48(s5)")
    replace(0x08880B08, "lwc1 f0, 0x28(s5)\ntrunc.w.s f0, f0\nmfc1 v0, f0\naddu s2, s2, v0\nslt at, fp, s2",
            f"jal {asm.labels['backlog_body_adv']:#x}\nlwc1 f0, 0x28(s5)\naddu s2, s2, v0\naddu v0, fp, t0\nslt at, v0, s2")

    # Clamp backlog capture (0x0887F924) copy/ruby length to max_bytes (a3: 0x40 speaker / 0xF8 body).
    replace(0x0887FA74, "lw v0, 0x18(s0)\nsw v0, 0xc(s2)",
            f"jal {asm.labels['clamp_backlog_copy']:#x}\nlw v0, 0x18(s0)")
    replace(0x0887FA88, "lw a2, 0x18(s0)", "lw a2, 0xc(s2)")
    replace(0x0887FA94, "lw v0, 0x18(s0)", "lw v0, 0xc(s2)")

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
