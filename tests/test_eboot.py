"""Synthetic MIPS execution tests; optional local EBOOT tests use no tracked dumps."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from tools.eboot.mips_asm import MipsAsm
from tools.eboot.patch_eboot import PAYLOAD_VA, build_payload, patch_bytes

try:
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    from unicorn import mips_const as regs
except ImportError:
    Uc = None


CONTEXT = 0x09000000
BUFFER = CONTEXT + 0x1000
SOURCE = CONTEXT + 0x2000
SPRITES = CONTEXT + 0x3000
STACK = CONTEXT + 0xF000
STOP = CONTEXT + 0xFF00


class AssemblerAndBinaryTests(unittest.TestCase):
    def test_assembler_and_patch_guards(self):
        asm = MipsAsm(0x08800000)
        asm.add_lines("lwc1 f0, 0x44(a0)\nmtc1 t0, f1\ncvt.s.w f1, f1\nmul.s f0, f0, f1\ntrunc.w.s f0, f0\nmfc1 v0, f0")
        self.assertEqual(struct.unpack("<6I", asm.assemble()),
                         (0xC4800044, 0x44880800, 0x46800860, 0x46010002, 0x4600000D, 0x44020000))
        for bad in ("beq zero, zero, 0x08840000", "j 0x08800001"):
            a = MipsAsm(0x08800000)
            a.emit(bad)
            with self.assertRaises(ValueError):
                a.assemble()
        with self.assertRaises(ValueError):
            patch_bytes(bytes(1_527_040))

        eboot = Path('work/eboot/EBOOT_decrypted.bin')
        if eboot.is_file():
            source = eboot.read_bytes()
            patched, info = patch_bytes(source)
            new_phoff = struct.unpack_from('<I', patched, 28)[0]
            self.assertEqual(patched[new_phoff:new_phoff + 32], source[52:84])
            self.assertEqual(struct.unpack_from('<H', patched, 44)[0], 2)
            self.assertGreater(info['payload_va'], 0x08A75B00)
            with self.assertRaises(ValueError):
                patch_bytes(patched)


@unittest.skipIf(Uc is None, "Install unicorn to execute MIPS tests")
class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        self.uc.mem_map(0x08800000, 0x300000)
        self.uc.mem_map(CONTEXT, 0x10000)
        self.asm = build_payload()
        self.uc.mem_write(PAYLOAD_VA, self.asm.assemble())
        self.widths = {code: 7 for code in range(32, 127)}
        self.widths.update({32: 4, ord('i'): 3, ord('W'): 12, ord('-'): 5})
        self.install_fonts()
        self.context()
        self.emitted = []
        self.positions = []
        self.breaks = 0
        self.hook = self.uc.hook_add(UC_HOOK_CODE, self.stub)

    def word(self, addr, val=None):
        if val is not None:
            self.uc.mem_write(addr, struct.pack("<I", val & 0xFFFFFFFF))
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def install_fonts(self):
        for i in range(3):
            lut, glyphs = CONTEXT + 0x5000 + i * 0x1000, CONTEXT + 0x8000 + i * 0x1000
            base = 0x08A26924 + i * 32
            self.uc.mem_write(base, struct.pack("<H", 127))
            self.word(base + 4, lut)
            self.word(base + 12, glyphs)
            for code, width in self.widths.items():
                self.uc.mem_write(lut + code * 2, struct.pack("<H", code - 31))
                self.uc.mem_write(glyphs + (code - 31) * 18, struct.pack("<4H3h2H", 1, 1, width + 1, 20, 0, width, 0, 0, 0))

    def context(self, slots=40, lines=5, half_cell=9.5, font=0):
        self.word(CONTEXT + 0x10, (slots * 3) // 2)
        self.word(CONTEXT + 0x14, lines)
        self.word(CONTEXT + 0x3C, BUFFER)
        self.word(CONTEXT + 0x40, 0)
        self.uc.mem_write(CONTEXT + 0x44, struct.pack("<f", half_cell))
        self.word(CONTEXT + 0x4C, 20)
        self.word(CONTEXT + 0x60, font)
        self.word(CONTEXT + 0x70, SPRITES)

    def run_label(self, label, char=0, source=SOURCE):
        self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
        self.uc.reg_write(regs.UC_MIPS_REG_A0, CONTEXT)
        self.uc.reg_write(regs.UC_MIPS_REG_A1, char)
        self.uc.reg_write(regs.UC_MIPS_REG_A2, CONTEXT + 0x100)
        self.uc.reg_write(regs.UC_MIPS_REG_S2, source)
        self.uc.emu_start(self.asm.labels[label], STOP, count=100000)
        self.assertEqual(self.uc.reg_read(regs.UC_MIPS_REG_PC), STOP, "MIPS instruction budget exhausted")
        return self.uc.reg_read(regs.UC_MIPS_REG_V0)

    def stub(self, uc, address, size, _):
        if address not in (0x0887BFD4, 0x0887B97C, 0x0887C400, 0x08881828):
            return
        if address == 0x08881828:
            self.positions.append((uc.reg_read(regs.UC_MIPS_REG_A1), uc.reg_read(regs.UC_MIPS_REG_A2)))
        elif address == 0x0887C400:
            self.breaks += 1
            slots, cursor = self.word(CONTEXT + 0x10), self.word(CONTEXT + 0x40)
            self.word(CONTEXT + 0x40, min((cursor // slots + 1) * slots,
                                       slots * self.word(CONTEXT + 0x14)))
            uc.reg_write(regs.UC_MIPS_REG_V0, 1)
        else:
            cursor, slots = self.word(CONTEXT + 0x40), self.word(CONTEXT + 0x10)
            char = uc.reg_read(regs.UC_MIPS_REG_A1) & 0xFFFF
            wide = address == 0x0887B97C
            length = 2 if wide else 1
            if cursor + length > slots * self.word(CONTEXT + 0x14):
                uc.reg_write(regs.UC_MIPS_REG_V0, 0)
            else:
                self.emitted.append((cursor // slots, char))
                self.uc.mem_write(BUFFER + cursor, struct.pack("<H", char) if wide else bytes([char]))
                self.word(CONTEXT + 0x40, cursor + length)
                uc.reg_write(regs.UC_MIPS_REG_V0, 1)
        uc.reg_write(regs.UC_MIPS_REG_PC, uc.reg_read(regs.UC_MIPS_REG_RA))

    def emit_text(self, text):
        self.uc.mem_write(SOURCE, text + b'\0\0')
        for i, char in enumerate(text):
            if not self.run_label('emit_ascii', char, SOURCE + i):
                break

    def seed(self, text):
        self.uc.mem_write(BUFFER, text)
        self.word(CONTEXT + 0x40, len(text))

    def test_metrics_measure_budget_and_clamp(self):
        for font in (0, 7, 8):
            self.word(CONTEXT + 0x60, font)
            self.assertEqual(self.run_label('advance', ord('i')), 3)
            self.assertEqual(self.run_label('advance', ord('W')), 12)
        self.assertEqual(self.run_label('budget'), 380)
        self.seed(b'Wi\x81\x40\x0a\xff')
        self.assertEqual(self.run_label('measure'), 12 + 3 + 19 + 19)

        ctx_ptr = CONTEXT + 0x400
        self.word(ctx_ptr + 0x3C, BUFFER)
        for raw_slots, expected in ((234, 234), (248, 248), (624, 248)):
            self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
            self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
            self.uc.reg_write(regs.UC_MIPS_REG_V0, ctx_ptr)
            self.uc.reg_write(regs.UC_MIPS_REG_S0, raw_slots)
            self.uc.emu_start(self.asm.labels['clamp_save_slots'], STOP, count=1000)
            self.assertEqual(self.uc.reg_read(regs.UC_MIPS_REG_S0), expected)

    def test_payload_word_wrap_and_fallbacks(self):
        self.context(slots=8, half_cell=5.0)
        self.emit_text(b'WW iiiiii')
        self.assertEqual(self.emitted[:3], [(0, ord('W')), (0, ord('W')), (0, 32)])
        self.assertEqual(self.emitted[3:], [(1, ord('i'))] * 6)

        self.emitted.clear()
        self.context(slots=8, half_cell=4.75)
        self.emit_text(b'WWW iii')
        self.assertEqual(self.emitted[3:], [(1, ord('i'))] * 3)
        self.assertEqual(bytes(self.uc.mem_read(BUFFER, 4)), b'WWW ')

        self.emitted.clear()
        self.context(slots=8, half_cell=5.0)
        self.emit_text(b'WW-iiii')
        self.assertEqual(self.emitted[3:], [(1, ord('i'))] * 4)

        self.emitted.clear()
        self.context(slots=8, half_cell=5.0)
        self.emit_text(b'WWWWWWWW')
        self.assertEqual([line for line, _ in self.emitted], [0, 0, 0, 1, 1, 1, 2, 2])


@unittest.skipUnless(Uc is not None and Path('work/eboot/EBOOT_decrypted.bin').is_file(),
                     "Local EBOOT and unicorn required")
class LocalParserTests(unittest.TestCase):
    """Execute the real patched parser/emitters/backlog/serializer in Unicorn."""

    def setUp(self):
        self.support = PayloadTests('test_metrics_measure_budget_and_clamp')
        self.support.setUp()
        self.uc = self.support.uc
        self.uc.hook_del(self.support.hook)
        patched, _ = patch_bytes(Path('work/eboot/EBOOT_decrypted.bin').read_bytes())
        phoff = struct.unpack_from('<I', patched, 28)[0]
        for i in range(2):
            _, off, va, _, filesz, _, _, _ = struct.unpack_from('<8I', patched, phoff + 32 * i)
            self.uc.mem_write(va, patched[off:off + filesz])
        self.support.install_fonts()
        self.support.context(slots=8, half_cell=5.0)
        self.support.word(CONTEXT + 0x48, 20)
        self.support.word(0x08A218B4, 1)
        self.support.word(0x08A05F94, 1)
        self.support.word(0x08A26910, 1)
        self.uc.mem_map(0x09100000, 0x10000)
        self.next_sprite = 0x09100000
        self.created = []
        self.allocations = []
        self.uc.hook_add(UC_HOOK_CODE, self.stub)

    def stub(self, uc, address, size, _):
        if address == 0x088142CC:
            dest = uc.reg_read(regs.UC_MIPS_REG_A0)
            src = uc.reg_read(regs.UC_MIPS_REG_A1)
            length = uc.reg_read(regs.UC_MIPS_REG_A2)
            uc.mem_write(dest, bytes(uc.mem_read(src, length)))
            uc.reg_write(regs.UC_MIPS_REG_V0, dest)
        elif address == 0x08881360:
            sprite = self.next_sprite
            self.next_sprite += 40
            char = uc.reg_read(regs.UC_MIPS_REG_A0) & 0xFFFF
            low = char & 0xFF
            if char >> 8 != 0xFF and not (0x81 <= low < 0xA0 or 0xE0 <= low):
                char = low
            self.created.append((sprite, char))
            uc.mem_write(sprite + 0x20, struct.pack('<2h', 10, 20))
            uc.reg_write(regs.UC_MIPS_REG_V0, sprite)
        elif address == 0x08881424:
            pass
        elif address == 0x088D5690:
            self.allocations.append(uc.reg_read(regs.UC_MIPS_REG_A1))
            uc.reg_write(regs.UC_MIPS_REG_V0, CONTEXT)
        elif address == 0x088146AC:
            dest = uc.reg_read(regs.UC_MIPS_REG_A0)
            value = uc.reg_read(regs.UC_MIPS_REG_A1) & 0xFF
            length = uc.reg_read(regs.UC_MIPS_REG_A2)
            uc.mem_write(dest, bytes([value]) * length)
            uc.reg_write(regs.UC_MIPS_REG_V0, dest)
        elif address == 0x088047C8:
            uc.reg_write(regs.UC_MIPS_REG_V0, 0)
        else:
            return
        uc.reg_write(regs.UC_MIPS_REG_PC, uc.reg_read(regs.UC_MIPS_REG_RA))

    def parse(self, text):
        self.uc.mem_write(SOURCE, text + b'\0\0')
        self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
        self.uc.reg_write(regs.UC_MIPS_REG_A0, CONTEXT)
        self.uc.reg_write(regs.UC_MIPS_REG_A1, SOURCE)
        self.uc.emu_start(0x0887D678, STOP, count=500000)
        self.assertEqual(self.uc.reg_read(regs.UC_MIPS_REG_PC), STOP)
        return self.uc.reg_read(regs.UC_MIPS_REG_V0)

    def positions(self):
        return [(char, self.support.word(sprite + 0x10), self.support.word(sprite + 0x14))
                for sprite, char in self.created]

    def test_real_parser_word_wrap_and_emotes(self):
        self.assertEqual(self.parse(b'WW iiiiii'), 9)
        self.assertEqual(self.positions(), [(87, 20, 0), (87, 32, 0), (32, 44, 0)] +
                         [(105, 20 + 3 * i, 20) for i in range(6)])
        self.created.clear()
        self.support.context(slots=8, half_cell=5.0)
        self.assertEqual(self.parse(b'Wi\\S10ii'), 5)
        self.assertEqual([char for char, _, _ in self.positions()], [87, 105, 0xFF0A, 105, 105])

    def test_dialogue_context_and_fade_bounds(self):
        config = CONTEXT + 0x4000
        for offset, value in ((0x10, 364), (0x14, 57), (0x18, 14), (0x1C, 19), (0x20, 14)):
            self.support.word(config + offset, value)
        self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
        self.uc.reg_write(regs.UC_MIPS_REG_A0, config)
        self.uc.reg_write(regs.UC_MIPS_REG_A1, 0)
        self.uc.emu_start(0x0887B340, STOP, count=100000)
        self.assertEqual(self.uc.reg_read(regs.UC_MIPS_REG_PC), STOP)
        slots, lines = self.support.word(CONTEXT + 0x10), self.support.word(CONTEXT + 0x14)
        self.assertEqual((slots, lines), (78, 3))
        self.assertLessEqual(slots * lines, 0xF8)
        self.assertEqual(self.support.run_label('budget'), 364)

        fade_obj, slots_ptr, slot_item = CONTEXT + 0x4000, CONTEXT + 0x4200, CONTEXT + 0x4300
        self.support.word(fade_obj + 0x04, 2)
        self.support.word(fade_obj + 0x0C, 2)
        self.support.word(fade_obj + 0x10, slots_ptr)
        self.support.word(slots_ptr + 8, slot_item)
        self.support.word(slot_item, 0xDEADBEEF)
        self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
        self.uc.reg_write(regs.UC_MIPS_REG_A0, fade_obj)
        self.uc.reg_write(regs.UC_MIPS_REG_A1, 0x12345678)
        self.uc.emu_start(0x0887E500, STOP, count=1000)
        self.assertEqual((self.uc.reg_read(regs.UC_MIPS_REG_V0), self.support.word(slot_item)), (0, 0xDEADBEEF))

        self.support.word(fade_obj + 0x04, 1)
        self.support.word(slots_ptr + 4, slot_item)
        self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
        self.uc.reg_write(regs.UC_MIPS_REG_A0, fade_obj)
        self.uc.reg_write(regs.UC_MIPS_REG_A1, 0x12345678)
        self.uc.emu_start(0x0887E500, STOP, count=1000)
        self.assertEqual((self.uc.reg_read(regs.UC_MIPS_REG_V0), self.support.word(slot_item)), (1, 0x12345678))

    def test_save_load_guard_and_ascii_restore(self):
        save_buf = CONTEXT + 0x5000
        self.support.word(0x08A218B0, 1)
        self.support.word(0x08A21870, CONTEXT)
        self.support.word(CONTEXT + 0x08, 1)
        emitted = []

        def save_hook(uc, addr, size, _):
            if addr in (0x0887B090, 0x0887B7A0):
                uc.reg_write(regs.UC_MIPS_REG_V0, 1)
            elif addr in (0x0887B97C, 0x0887BFD4):
                emitted.append((addr, uc.reg_read(regs.UC_MIPS_REG_A1) & 0xFFFF))
                uc.reg_write(regs.UC_MIPS_REG_V0, 1)
            else:
                return
            uc.reg_write(regs.UC_MIPS_REG_PC, uc.reg_read(regs.UC_MIPS_REG_RA))

        hk = self.uc.hook_add(UC_HOOK_CODE, save_hook)
        try:
            # Oversized old SLOT_FACTOR=4 record (208 * 3 = 624 > 0xF8) is skipped safely
            self.uc.mem_write(save_buf, bytes(0x2000))
            self.support.word(save_buf + 0x00, 1)
            rec = save_buf + 0x04
            for off, val in ((0x08, 1), (0x10, 208), (0x14, 3), (0x18, 20), (0x1C, 20)):
                self.support.word(rec + off, val)
            self.uc.mem_write(rec + 0x40, struct.pack('<f', 10.0))
            self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
            self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
            self.uc.reg_write(regs.UC_MIPS_REG_A0, save_buf)
            self.uc.emu_start(0x0887F5D8, STOP, count=100000)
            self.assertEqual((self.uc.reg_read(regs.UC_MIPS_REG_V0), emitted), (1, []))

            # Valid <= 0xF8 record restores ASCII via emit_ascii (0x0887BFD4)
            self.support.word(rec + 0x10, 4)
            self.support.word(rec + 0x14, 1)
            self.uc.mem_write(rec + 0x64, b'Wi\x00\x00')
            self.uc.mem_write(rec + 0x15C + 0 * 0x14, struct.pack('<H', 1))
            self.uc.mem_write(rec + 0x15C + 1 * 0x14, struct.pack('<H', 1))
            self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
            self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
            self.uc.reg_write(regs.UC_MIPS_REG_A0, save_buf)
            self.uc.emu_start(0x0887F5D8, STOP, count=100000)
            self.assertEqual(emitted, [(0x0887BFD4, ord('W')), (0x0887BFD4, ord('i'))])
        finally:
            self.uc.hook_del(hk)

    def test_real_backlog_wrap_and_capture_clamp(self):
        # 1. Backlog renderer (0x0887FE40): proportional speaker + body word wrap
        bl, sprites, speaker, body = CONTEXT + 0x4000, CONTEXT + 0x4200, CONTEXT + 0x4600, CONTEXT + 0x4700
        self.uc.mem_write(bl, bytes(0x100))
        self.uc.mem_write(sprites, bytes(0x200))
        self.uc.mem_write(speaker, b'Wi\x00')
        self.uc.mem_write(body, b'WW iiiiii\x00\x00WW')
        for off, val in ((0x00, 1), (0x08, 0xFFFF), (0x0C, 0), (0x2C, 20), (0x30, 20),
                         (0x34, 20), (0x38, 0), (0x3C, 40), (0x40, 80), (0x4C, 10),
                         (0x50, 10), (0x54, 20), (0x58, sprites)):
            self.support.word(bl + off, val)
        self.uc.mem_write(bl + 0x24, struct.pack('<f', 5.0))
        self.uc.mem_write(bl + 0x28, struct.pack('<f', 5.0))
        self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
        self.uc.reg_write(regs.UC_MIPS_REG_A0, bl)
        self.uc.reg_write(regs.UC_MIPS_REG_A1, 2)
        self.uc.reg_write(regs.UC_MIPS_REG_A2, speaker)
        self.uc.reg_write(regs.UC_MIPS_REG_A3, 13)
        self.uc.reg_write(regs.UC_MIPS_REG_T0, body)
        self.uc.reg_write(regs.UC_MIPS_REG_T1, 0)
        self.uc.emu_start(0x0887FE40, STOP, count=200000)
        pos = self.positions()
        self.assertEqual(pos[:2], [(87, 20, 0), (105, 32, 0)])
        self.assertEqual(pos[2:11], [(87, 20, 20), (87, 32, 20), (32, 44, 20)] + [(105, 20 + 3 * i, 40) for i in range(6)])
        self.assertEqual(pos[11:], [(87, 20, 60), (87, 32, 60)])

        # 2. Backlog capture (0x0887F924): clamps speaker > 0x40 without heap overflow
        self.support.word(0x08A218B0, 1)
        self.support.word(0x08A21870, CONTEXT)
        self.support.word(CONTEXT + 0x08, 1)
        self.support.word(CONTEXT + 0x3C, BUFFER)
        self.support.word(CONTEXT + 0x64, 0)
        self.uc.mem_write(CONTEXT + 0x80, b'\x00')
        self.support.word(CONTEXT + 0x18, 80)
        self.support.word(CONTEXT + 0x40, 6)
        self.uc.mem_write(BUFFER, b'Nanaka' + b'\x00' * 74)
        dst_spk = CONTEXT + 0x4800
        self.uc.mem_write(dst_spk, bytes(0x58))
        self.uc.mem_write(dst_spk + 0x58, struct.pack('<II', 0x11223344, 0x096F5818))
        self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
        self.uc.reg_write(regs.UC_MIPS_REG_A0, 1)
        self.uc.reg_write(regs.UC_MIPS_REG_A1, 0)
        self.uc.reg_write(regs.UC_MIPS_REG_A2, dst_spk)
        self.uc.reg_write(regs.UC_MIPS_REG_A3, 0x40)
        self.uc.emu_start(0x0887F924, STOP, count=100000)
        self.assertEqual(self.support.word(dst_spk + 0x0C), 0x40)
        self.assertEqual(struct.unpack('<II', self.uc.mem_read(dst_spk + 0x58, 8)), (0x11223344, 0x096F5818))

    @unittest.skipUnless(Path('build/p3_batch1_backlogfix2/fonts/font').is_dir(), 'Local font build unavailable')
    def test_dialogue_and_backlog_spacing_match_actual_font_metrics(self):
        from tools.font.build_font import crilayla, parse_w_abc
        self.uc.mem_map(0x09200000, 0x100000)
        fonts = {}
        for index, name in enumerate(('sulakyapi8', 'sulakyapi12', 'sulakyapi18')):
            path = Path('build/p3_batch1_backlogfix2/fonts/font') / name / 'abc.w_abc'
            _, lut, glyphs = parse_w_abc(crilayla.decompress(path.read_bytes()))
            base = 0x09200000 + index * 0x40000
            self.uc.mem_write(base, struct.pack(f'<{len(lut)}H', *lut))
            self.uc.mem_write(base + 0x20000, b''.join(struct.pack('<4H3h2H', *g) for g in glyphs))
            slot = 0x08A26924 + index * 32
            self.uc.mem_write(slot, struct.pack('<H', len(lut) - 1))
            self.support.word(slot + 4, base)
            self.support.word(slot + 12, base + 0x20000)
            fonts[name] = (lut, glyphs)
        text = b'Wi I l mw gjpqy 01239'
        for font_id, name, half_cell in ((0, 'sulakyapi12', 7.0), (7, 'sulakyapi18', 10.5), (8, 'sulakyapi8', 5.0)):
            with self.subTest(font=name):
                lut, glyphs = fonts[name]
                expected_x = []
                x = 20
                for char in text:
                    expected_x.append(x)
                    x += sum(glyphs[lut[char]][4:7])
                self.created.clear()
                self.support.context(slots=52, lines=3, half_cell=half_cell, font=font_id)
                self.assertEqual(self.parse(text), len(text))
                self.assertEqual([x for _, x, _ in self.positions()], expected_x)

                self.created.clear()
                bl, sprites, speaker, body = CONTEXT + 0x4000, CONTEXT + 0x4200, CONTEXT + 0x4600, CONTEXT + 0x4700
                self.uc.mem_write(bl, bytes(0x100))
                self.uc.mem_write(sprites, bytes(0x300))
                self.uc.mem_write(speaker, b'\0')
                self.uc.mem_write(body, text + b'\0\0')
                for off, value in ((0x00, 1), (0x08, 0xFFFF), (0x2C, 20), (0x30, 20),
                                   (0x34, 20), (0x3C, 380), (0x40, 80), (0x44, font_id),
                                   (0x48, font_id), (0x4C, 14), (0x50, 14), (0x54, 20), (0x58, sprites)):
                    self.support.word(bl + off, value)
                self.uc.mem_write(bl + 0x24, struct.pack('<2f', half_cell, half_cell))
                self.uc.reg_write(regs.UC_MIPS_REG_SP, STACK)
                self.uc.reg_write(regs.UC_MIPS_REG_RA, STOP)
                self.uc.reg_write(regs.UC_MIPS_REG_A0, bl)
                self.uc.reg_write(regs.UC_MIPS_REG_A1, 2)
                self.uc.reg_write(regs.UC_MIPS_REG_A2, speaker)
                self.uc.reg_write(regs.UC_MIPS_REG_A3, len(text))
                self.uc.reg_write(regs.UC_MIPS_REG_T0, body)
                self.uc.reg_write(regs.UC_MIPS_REG_T1, 0)
                self.uc.emu_start(0x0887FE40, STOP, count=200000)
                self.assertEqual(self.uc.reg_read(regs.UC_MIPS_REG_PC), STOP)
                self.assertEqual([x for _, x, _ in self.positions()], expected_x)

    def test_patch_eboot_strings_in_place(self) -> None:
        root = Path(__file__).resolve().parents[1]
        eboot_path = root / 'work' / 'eboot' / 'EBOOT_decrypted.bin'
        if not eboot_path.is_file():
            self.skipTest('local decrypted EBOOT not present')
        strings_path = root / 'glossary' / 'eboot_strings.json'
        patched, info = patch_bytes(eboot_path.read_bytes(), strings_path=strings_path)
        manifest = json.loads(strings_path.read_text(encoding='utf-8'))
        self.assertEqual(info['patched_strings'], manifest['count'])
        for entry in manifest['strings']:
            offset = int(entry['file_offset'], 16)
            cap = int(entry['slot_capacity'])
            encoded = entry['en'].encode('cp932')
            self.assertLessEqual(len(encoded), cap)
            expected = encoded + b'\x00' * (cap + 1 - len(encoded))
            self.assertEqual(patched[offset:offset + cap + 1], expected)


if __name__ == '__main__':
    unittest.main()
