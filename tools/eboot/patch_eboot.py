"""Version-pinned PJADV proportional-layout proof of concept for ULJS00316 v1.01.

Only the main typewriter parser is wrapped. Ruby and direct-emission callers
still require runtime investigation; this is not a release-ready patch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
TITLE_TABLE_VA = 0x08A76C00  # 3 KB code region, followed by sorted scene-title lookup table.
SPRITE_POOL_VA = 0x08A80000  # Relocated glyph sprite pool (zero-initialized BSS in 2nd PT_LOAD).
SPRITE_POOL_COUNT = 0x800  # 2,048 sprites (4x original 0x200) to prevent English backlog exhaustion.
SPRITE_POOL_BYTES = SPRITE_POOL_COUNT * 0x28  # 0x14000 bytes (80 KB).
NEWLIB_HEAP_KB_VA = 0x089696E0  # sce_newlib_heap_kb_size (original: 21831 KB).
ORIG_NEWLIB_HEAP_KB = 21831
SLOT_FACTOR = 1.5  # 3/2 ratio keeps 3-line dialogue at 78 * 3 = 234 <= 0xF8 (248) for serializer 0x0887F2F8.


def djb2_hash32(data: bytes) -> int:
    h = 5381
    for b in data:
        h = (((h << 5) + h) ^ b) & 0xFFFFFFFF
    return h


def build_scene_title_table(entries: list[tuple[str, str]], base_va: int = TITLE_TABLE_VA) -> bytes:
    """Serialize sorted (hash32, jp_va, en_va) lookup table + NUL-terminated strings."""
    if not entries:
        return struct.pack("<I", 0)
    encoded: list[tuple[int, bytes, bytes]] = []
    seen: set[bytes] = set()
    for jp, en in entries:
        jp_b = jp.encode("cp932")
        en_b = en.encode("cp932")
        if len(en_b) > 0xFE:
            raise ValueError(f"Translated scene title exceeds 254 bytes: {en!r}")
        if jp_b in seen:
            continue
        seen.add(jp_b)
        encoded.append((djb2_hash32(jp_b), jp_b, en_b))
    encoded.sort(key=lambda item: (item[0], item[1]))
    count = len(encoded)
    str_base = base_va + 4 + count * 12
    str_buf = bytearray()
    header = bytearray(struct.pack("<I", count))
    for h, jp_b, en_b in encoded:
        jp_va = str_base + len(str_buf)
        str_buf.extend(jp_b)
        str_buf.append(0)
        en_va = str_base + len(str_buf)
        str_buf.extend(en_b)
        str_buf.append(0)
        header.extend(struct.pack("<III", h, jp_va, en_va))
    while (len(header) + len(str_buf)) % 4 != 0:
        str_buf.append(0)
    return bytes(header + str_buf)


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
        li t0, 0x81
        beq a1, t0, scan_sjis_punct
        nop
        sltiu t0, a1, 0x7f
        beqz t0, scan_done
        nop
        li t0, 0x5c
        beq a1, t0, scan_escape
        nop
        b scan_measure
        sw a1, 16(sp)
    scan_sjis_punct:
        lbu t0, 1(s2)
        beqz t0, scan_done
        nop
        addiu s2, s2, 1
        li a1, 0x8100
        b scan_measure
        sw zero, 16(sp)
    scan_escape:
        lbu t0, 1(s2)
        ori t0, t0, 0x20
        li t1, 0x73
        bne t0, t1, scan_done
        nop
        lbu t0, 2(s2)
        beqz t0, scan_done
        nop
        lbu t0, 3(s2)
        beqz t0, scan_done
        nop
        addiu s2, s2, 3
        li a1, 0xff00
        sw zero, 16(sp)
    scan_measure:
        jal advance
        move a0, s0
        addu s1, s1, v0
        lw t0, 16(sp)
        li t1, 0x2d
        bne t0, t1, scan_next
        nop
        lbu t0, 1(s2)
        beqz t0, scan_done
        nop
        li t1, 0x2d
        beq t0, t1, scan_next
        nop
        li t1, 0x81
        beq t0, t1, scan_next
        nop
        li t1, 0x5c
        bne t0, t1, scan_done
        nop
    scan_next:
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
        addiu t4, t2, 1
        slt t4, t4, t3
        beqz t4, bw_scan_ascii_only
        nop
        lbu t4, 1(s0)
        li a0, 0xff
        beq t4, a0, bw_scan_pair
        nop
        li a0, 0x81
        beq a1, a0, bw_scan_pair
        nop
    bw_scan_ascii_only:
        sltiu t4, a1, 0x7f
        beqz t4, bw_scan_done
        nop
        b bw_scan_measure
        nop
    bw_scan_pair:
        beqz t4, bw_scan_done
        nop
        addiu s0, s0, 1
        addiu t2, t2, 1
        sw t2, 4(sp)
        li a1, 0x8100
    bw_scan_measure:
        lw a0, 8(sp)
        lwc1 f0, 0x28(s5)
        jal advance_by_font
        nop
        lw t0, 0(sp)
        addu t0, t0, v0
        sw t0, 0(sp)
        lbu t0, 0(s0)
        li t4, 0x2d
        bne t0, t4, bw_scan_next
        nop
        lbu t0, 1(s0)
        li t4, 0x2d
        beq t0, t4, bw_scan_next
        nop
        li t4, 0x81
        bne t0, t4, bw_scan_done
        nop
    bw_scan_next:
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

    # Clear expanded 2048-entry glyph sprite pool (0x800 * 0x28 = 0x14000 bytes).
    # Called from 0x08880F90 with a0=SPRITE_POOL_VA, a1=0.
    memset_sprite_pool:
        lui a2, 0x0001
        j 0x088146ac
        ori a2, a2, 0x4000

    # Translate Save/Load chapter title in s5 (length s1) via sorted DJB2 table
    # at TITLE_TABLE_VA (0x08A76C00). Hooked at 0x08879460 after strncpy(s5, s0, s1).
    translate_scene_title:
        beqz s1, tst_done
        nop
        sltiu t0, s1, 0x100
        beqz t0, tst_done
        nop
        addu t0, s5, s1
        sb zero, 0(t0)
        lui t8, 0x08a7
        ori t8, t8, 0x6c00
        lw t9, 0(t8)
        beqz t9, tst_done
        addiu t8, t8, 4
        li t0, 5381
        move t1, s5
    tst_hash_loop:
        lbu t2, 0(t1)
        beqz t2, tst_bsearch_init
        nop
        sll t3, t0, 5
        addu t0, t3, t0
        xor t0, t0, t2
        b tst_hash_loop
        addiu t1, t1, 1
    tst_bsearch_init:
        move t1, zero
        move t2, t9
    tst_bsearch:
        sltu t3, t1, t2
        beqz t3, tst_done
        nop
        addu t3, t1, t2
        srl t3, t3, 1
        sll t4, t3, 1
        addu t4, t4, t3
        sll t4, t4, 2
        addu t4, t8, t4
        lw t5, 0(t4)
        beq t5, t0, tst_rewind
        nop
        sltu t6, t5, t0
        bnez t6, tst_go_right
        nop
        b tst_bsearch
        move t2, t3
    tst_go_right:
        b tst_bsearch
        addiu t1, t3, 1
    tst_rewind:
        beqz t3, tst_scan
        nop
        lw t5, -12(t4)
        bne t5, t0, tst_scan
        nop
        addiu t3, t3, -1
        b tst_rewind
        addiu t4, t4, -12
    tst_scan:
        sltu t6, t3, t9
        beqz t6, tst_done
        nop
        lw t5, 0(t4)
        bne t5, t0, tst_done
        nop
        lw a0, 4(t4)
        move a1, s5
    tst_cmp:
        lbu t6, 0(a0)
        lbu t7, 0(a1)
        bne t6, t7, tst_scan_next
        nop
        beqz t6, tst_copy
        nop
        addiu a0, a0, 1
        b tst_cmp
        addiu a1, a1, 1
    tst_scan_next:
        addiu t3, t3, 1
        b tst_scan
        addiu t4, t4, 12
    tst_copy:
        lw a0, 8(t4)
        move a1, s5
    tst_copy_loop:
        lbu t6, 0(a0)
        sb t6, 0(a1)
        beqz t6, tst_done
        addiu a0, a0, 1
        b tst_copy_loop
        addiu a1, a1, 1
    tst_done:
        j 0x08879498
        nop

    # Unpooled date/time literals for compiler-shared .rodata entries
    # ('日' Sun vs Day, '月' Mon vs Month, '朝' Morning inside '早朝', '深夜' Late Night vs '夜' Night).
    str_sun:
        .word 0x006e7553
    str_mon:
        .word 0x006e6f4d
    str_morning:
        .word 0x6e726f4d
        .word 0x00676e69
    str_late_night:
        .word 0x6574614c
        .word 0x67694e20
        .word 0x00007468
    """)
    return asm


def apply_eboot_strings(result: bytearray, strings_path: Path) -> int:
    """Patch translated CP932 strings from eboot_strings.json in-place."""
    manifest = json.loads(strings_path.read_text(encoding="utf-8"))
    if manifest.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("EBOOT strings manifest source_sha256 mismatch")
    patched_count = 0
    for entry in manifest["strings"]:
        en = entry.get("en")
        if en is None:
            continue
        offset = int(entry["file_offset"], 16)
        slot_capacity = int(entry["slot_capacity"])
        expected_jp = entry["jp"].encode("cp932")
        if result[offset:offset + len(expected_jp)] != expected_jp:
            raise ValueError(f"Unexpected original bytes at {entry['id']} ({entry['file_offset']})")
        encoded = en.encode("cp932")
        if len(encoded) > slot_capacity:
            raise ValueError(
                f"{entry['id']} exceeds slot_capacity ({len(encoded)} > {slot_capacity})"
            )
        result[offset:offset + slot_capacity + 1] = encoded + b"\x00" * (slot_capacity + 1 - len(encoded))
        patched_count += 1
    return patched_count


def load_scene_titles(path: Path) -> list[tuple[str, str]]:
    """Load (jp, en) chapter title mappings from glossary/scene_titles.json."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw["titles"] if isinstance(raw, dict) else raw
    out: list[tuple[str, str]] = []
    for item in items:
        jp = item["jp"]
        en = item.get("en")
        if en and en != jp:
            out.append((jp, en))
    return out


def patch_bytes(
    source: bytes,
    strings_path: Path | None = None,
    scene_titles_path: Path | None = None,
) -> tuple[bytes, dict[str, int]]:
    if len(source) != 1_527_040 or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("Expected the clean ULJS00316 v1.01 decrypted EBOOT; source identity mismatch")
    asm = build_payload()
    code = asm.assemble()
    code_budget = TITLE_TABLE_VA - PAYLOAD_VA
    if len(code) > code_budget:
        raise ValueError(f"Payload code ({len(code)} bytes) exceeds {code_budget} bytes before TITLE_TABLE_VA")
    title_entries = load_scene_titles(scene_titles_path) if scene_titles_path is not None else []
    title_table = build_scene_title_table(title_entries, TITLE_TABLE_VA)
    payload = code + bytes(code_budget - len(code)) + title_table
    if PAYLOAD_VA + len(payload) > SPRITE_POOL_VA:
        raise ValueError(
            f"Payload + title table end ({PAYLOAD_VA + len(payload):#x}) overlaps SPRITE_POOL_VA ({SPRITE_POOL_VA:#x})"
        )
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

    # Relocate and expand the global glyph sprite pool (0x08A21910, 0x200 sprites ->
    # SPRITE_POOL_VA 0x08A90000, 0x800 = 2048 sprites) so long English backlog
    # entries never exhaust the pool and collapse/overlap on scroll-up.
    pool_hi = SPRITE_POOL_VA >> 16
    assert (SPRITE_POOL_VA & 0xFFFF) == 0
    replace(0x08880F84, "lui a0, 0x08a2\naddiu a0, a0, 0x1910",
            f"lui a0, {pool_hi:#x}\naddiu a0, a0, 0")
    replace(0x08880F90, "jal 0x088146ac\naddiu a2, zero, 0x5000",
            f"jal {asm.labels['memset_sprite_pool']:#x}\nnop")
    replace(0x08881398, "lui v1, 0x08a2", f"lui v1, {pool_hi:#x}")
    replace(0x088813A0, "addiu v1, v1, 0x1910", "addiu v1, v1, 0")
    replace(0x088813AC, "addiu v0, zero, 0x200", f"addiu v0, zero, {SPRITE_POOL_COUNT:#x}")
    replace(0x088813B4, "slti v0, t4, 0x200", f"slti v0, t4, {SPRITE_POOL_COUNT:#x}")
    replace(0x088813C0, "addiu v0, zero, 0x200", f"addiu v0, zero, {SPRITE_POOL_COUNT:#x}")
    replace(0x088813DC, "lui v0, 0x08a2", f"lui v0, {pool_hi:#x}")
    replace(0x088813E4, "addiu v0, v0, 0x1910", "addiu v0, v0, 0")
    replace(0x0888143C, "lui a2, 0x08a2\nlui s0, 0x08a2",
            f"lui a2, {pool_hi:#x}\nlui s0, {pool_hi:#x}")
    replace(0x08881448, "addiu s0, s0, 0x1910", "addiu s0, s0, 0")
    replace(0x08881468, "sltiu v1, s1, 0x200", f"sltiu v1, s1, {SPRITE_POOL_COUNT:#x}")
    replace(0x08881480, "addiu a2, a2, 0x1910", "addiu a2, a2, 0")
    replace(0x08881488, "addiu v1, zero, 0x200", f"addiu v1, zero, {SPRITE_POOL_COUNT:#x}")
    replace(0x08881490, "sltiu v1, a1, 0x200", f"sltiu v1, a1, {SPRITE_POOL_COUNT:#x}")
    replace(0x0888149C, "addiu v1, zero, 0x200", f"addiu v1, zero, {SPRITE_POOL_COUNT:#x}")
    replace(0x088817AC, "lui s0, 0x08a2", f"lui s0, {pool_hi:#x}")
    replace(0x088817B4, "addiu s0, s0, 0x1910", "addiu s0, s0, 0")
    replace(0x08881808, "slti v1, s1, 0x200", f"slti v1, s1, {SPRITE_POOL_COUNT:#x}")
    replace(0x088819DC, "lui s2, 0x08a2", f"lui s2, {pool_hi:#x}")
    replace(0x088819E4, "addiu s2, s2, 0x1910", "addiu s2, s2, 0")
    replace(0x08881B0C, "sltiu v0, s3, 0x200", f"sltiu v0, s3, {SPRITE_POOL_COUNT:#x}")
    replace(0x08881B28, "lui s3, 0x08a2", f"lui s3, {pool_hi:#x}")
    replace(0x08881B30, "addiu s3, s3, 0x1910", "addiu s3, s3, 0")
    replace(0x08881C58, "sltiu v0, s2, 0x200", f"sltiu v0, s2, {SPRITE_POOL_COUNT:#x}")

    # Hook Save/Load chapter title getter (0x08879340 mode 1) for display-time
    # translation while keeping OP_SCENE & Grp_Title/%s.txt preloading intact.
    replace(0x08879460, "b 0x08879498\nnop",
            f"j {asm.labels['translate_scene_title']:#x}\nnop")

    # Keep the exact stock single-PT_LOAD PSP ELF layout (e_phoff=0x34, e_phnum=1,
    # p_offset=0x54, p_vaddr=0x08804000, p_paddr=0x146190 for .rodata.sceModuleInfo).
    # Real PSP hardware (loadcore.prx / CFW systemctrl) rejects relocated e_phoff or a
    # second PF_X PT_LOAD with virtual p_paddr via 0x80020148 (UNSUPPORTED_PRX_TYPE).
    # Extending PH[0] in-place keeps all virtual addresses intact and lets the kernel
    # load zeros for original .bss (0x08978630..0x08A76000) and zero-init the expanded
    # sprite pool BSS (0x08A80000..0x08A94000) past p_filesz.
    phoff = struct.unpack_from("<I", source, 28)[0]
    if phoff != 52:
        raise ValueError(f"Unexpected original e_phoff: {phoff:#x}")
    original_ph = source[phoff:phoff + 32]
    segment = struct.unpack("<8I", original_ph)
    if segment != (1, LOAD_OFFSET, LOAD_VA, 1_335_696, 1_525_296, 2_562_816, 7, 16):
        raise ValueError("Unexpected original PT_LOAD layout")
    orig_filesz = segment[4]
    orig_memsz = segment[5]
    orig_seg_file_end = LOAD_OFFSET + orig_filesz  # 0x174684

    # Preserve stock section header table + .shstrtab + .comment cleanly after PH[0] data.
    orig_shoff = struct.unpack_from("<I", source, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", source, 46)
    if orig_shoff != orig_seg_file_end or shentsize != 40 or shnum != 24:
        raise ValueError(f"Unexpected original section table layout (shoff={orig_shoff:#x}, shnum={shnum})")
    sh_table = bytearray(source[orig_shoff:orig_shoff + shnum * shentsize])
    orig_shstr_off = struct.unpack_from("<I", sh_table, shstrndx * shentsize + 16)[0]
    orig_shstr_sz = struct.unpack_from("<I", sh_table, shstrndx * shentsize + 20)[0]
    orig_comment_off = struct.unpack_from("<I", sh_table, (shnum - 1) * shentsize + 16)[0]
    orig_comment_sz = struct.unpack_from("<I", sh_table, (shnum - 1) * shentsize + 20)[0]
    tail_blob = source[orig_shstr_off:orig_comment_off + orig_comment_sz]

    new_memsz = (SPRITE_POOL_VA + SPRITE_POOL_BYTES) - LOAD_VA
    seg2_memsz = (SPRITE_POOL_VA + SPRITE_POOL_BYTES) - PAYLOAD_VA
    extra_memsz = new_memsz - orig_memsz
    # Trim sce_newlib_heap_kb_size (0x089696E0, originally 21831 KB) by the exact
    # p_memsz growth (+8 KB margin) so PSP-1000 24 MB User Partition retains full
    # original headroom for OS/CriThread stacks and buffers.
    heap_kb_off = NEWLIB_HEAP_KB_VA - LOAD_VA + LOAD_OFFSET
    cur_heap_kb = struct.unpack_from("<I", result, heap_kb_off)[0]
    if cur_heap_kb != ORIG_NEWLIB_HEAP_KB:
        raise ValueError(f"Unexpected sce_newlib_heap_kb_size: {cur_heap_kb} != {ORIG_NEWLIB_HEAP_KB}")
    new_heap_kb = cur_heap_kb - ((extra_memsz + 1023) // 1024 + 8)
    struct.pack_into("<I", result, heap_kb_off, new_heap_kb)

    # Rebuild file body: [ELF hdr + PH[0] + orig .text/.data] + [zero .bss gap] + [payload] + [relocated SH table + .shstrtab/.comment]
    bss_gap = (PAYLOAD_VA - LOAD_VA) - orig_filesz
    assert bss_gap > 0
    out_buf = bytearray(result[:orig_seg_file_end])
    out_buf.extend(bytes(bss_gap))
    assert len(out_buf) == LOAD_OFFSET + (PAYLOAD_VA - LOAD_VA)
    out_buf.extend(payload)
    new_filesz = len(out_buf) - LOAD_OFFSET
    while len(out_buf) % 4 != 0:
        out_buf.append(0)
    new_shoff = len(out_buf)
    new_shstr_off = new_shoff + len(sh_table)
    sh_delta = new_shstr_off - orig_shstr_off
    for idx in range(shnum):
        sh_off_pos = idx * shentsize + 16
        sec_off = struct.unpack_from("<I", sh_table, sh_off_pos)[0]
        if sec_off == orig_seg_file_end:
            # .bss (SHT_NOBITS, sh_size == 0)
            struct.pack_into("<I", sh_table, sh_off_pos, new_shoff)
        elif sec_off >= orig_shstr_off:
            # .shstrtab, empty .rel.* stubs, and .comment
            struct.pack_into("<I", sh_table, sh_off_pos, sec_off + sh_delta)
    out_buf.extend(sh_table)
    out_buf.extend(tail_blob)
    while len(out_buf) % 16 != 0:
        out_buf.append(0)

    # Update single PH[0] in-place at e_phoff=0x34 (keep p_paddr=0x146190 intact!) and e_shoff.
    struct.pack_into("<8I", out_buf, phoff, 1, LOAD_OFFSET, LOAD_VA, segment[3], new_filesz, new_memsz, 7, 16)
    struct.pack_into("<I", out_buf, 32, new_shoff)
    struct.pack_into("<H", out_buf, 44, 1)
    result = out_buf
    patched_strings = 0
    if strings_path is not None:
        patched_strings = apply_eboot_strings(result, strings_path)
        # Disable hardcoded Japanese byte-offset U+2122 ('™') insertion in
        # sceUtilityMsgDialog wrapper (0x089454ec), which otherwise injects '™'
        # into the middle of translated English words (e.g. "blin™k", "dur™ing").
        replace(0x0894552C, "move s6, t1", "move s6, zero")
        # Unpool compiler-deduplicated date/time literals in 0x0882c5f0..0x0882d0ac:
        # Sunday ('日' +0x08), Monday ('月' +0x04), Morning ('朝' +0x58 inside '早朝'),
        # and Night ('夜' +0x68 inside '深夜') vs Late Night ('深夜' +0x66).
        hi_va = PAYLOAD_VA >> 16
        for load_va, add_va, old_off, label in (
            (0x0882C5F0, 0x0882C600, 0x08, "str_sun"),
            (0x0882C6F4, 0x0882C704, 0x08, "str_sun"),
            (0x0882C60C, 0x0882C61C, 0x04, "str_mon"),
            (0x0882C710, 0x0882C720, 0x04, "str_mon"),
            (0x0882D02C, 0x0882D03C, 0x58, "str_morning"),
            (0x0882D09C, 0x0882D0AC, 0x66, "str_late_night"),
        ):
            replace(load_va, "lui v0, 0x0896\nlw v0, 0x1400(v0)", f"lui v0, {hi_va:#x}\nnop")
            replace(add_va, f"addiu a1, v0, {old_off:#x}", f"addiu a1, v0, {asm.labels[label] & 0xFFFF:#x}")
        replace(0x0882D090, "addiu a1, v0, 0x68", "addiu a1, v0, 0x66")
    return bytes(result), {"payload_va": PAYLOAD_VA, "payload_bytes": len(payload),
                           "seg2_memsz": seg2_memsz, "newlib_heap_kb": new_heap_kb,
                           "sprite_pool_va": SPRITE_POOL_VA,
                           "sprite_pool_count": SPRITE_POOL_COUNT,
                           "scene_title_count": len(title_entries),
                           "slot_factor": SLOT_FACTOR, "patched_strings": patched_strings, **asm.labels}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--strings", type=Path, default=None, help="Optional glossary/eboot_strings.json to patch in-place")
    ap.add_argument("--scene-titles", type=Path, default=None, help="Optional glossary/scene_titles.json for Save/Load chapter titles")
    args = ap.parse_args()
    if args.src.resolve() == args.out.resolve() or args.out.exists():
        raise SystemExit("Output must be a new file, separate from the clean EBOOT")
    patched, info = patch_bytes(args.src.read_bytes(), strings_path=args.strings, scene_titles_path=args.scene_titles)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as out:
        out.write(patched)
    print(f"Patched EBOOT: {len(patched)} bytes; payload={info['payload_bytes']} bytes at {PAYLOAD_VA:#x}")
    print("Proof of concept only: PPSSPP, ruby, direct emitters, and memory pressure remain unverified")


if __name__ == "__main__":
    main()
