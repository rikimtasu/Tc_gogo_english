"""Minimal MIPS32 little-endian assembler with label support for PSP EBOOT patching."""

from __future__ import annotations

import struct

REGS = {
    "zero": 0, "r0": 0,
    "at": 1, "r1": 1,
    "v0": 2, "v1": 3,
    "a0": 4, "a1": 5, "a2": 6, "a3": 7,
    "t0": 8, "t1": 9, "t2": 10, "t3": 11,
    "t4": 12, "t5": 13, "t6": 14, "t7": 15,
    "s0": 16, "s1": 17, "s2": 18, "s3": 19,
    "s4": 20, "s5": 21, "s6": 22, "s7": 23,
    "t8": 24, "t9": 25,
    "k0": 26, "k1": 27,
    "gp": 28, "sp": 29, "fp": 30, "s8": 30, "ra": 31,
}


def _r(name: str) -> int:
    s = name.strip().lstrip("$")
    if s not in REGS:
        raise ValueError(f"Unknown MIPS register: {name!r}")
    return REGS[s]


def _imm(val: str | int) -> int:
    if isinstance(val, int):
        return val
    return int(val.strip(), 0)


def _mem(expr: str) -> tuple[int, int]:
    expr = expr.strip()
    if "(" not in expr:
        return 0, _r(expr)
    off_s, rest = expr.split("(", 1)
    base_s = rest.rstrip(")").strip()
    off = int(off_s.strip(), 0) if off_s.strip() else 0
    return off, _r(base_s)


def _enc_r(rs: int, rt: int, rd: int, sa: int, fn: int) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | (sa << 6) | fn


def _enc_i(op: int, rs: int, rt: int, imm: int) -> int:
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def _enc_j(op: int, addr: int) -> int:
    return (op << 26) | ((addr >> 2) & 0x03FFFFFF)


class MipsAsm:
    """Two-pass MIPS32 little-endian assembler anchored at a fixed VA."""

    def __init__(self, base_va: int) -> None:
        self.base_va = base_va
        self.items: list[tuple[int, str, list[str]]] = []
        self.labels: dict[str, int] = {}
        self.cur_va = base_va

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"Duplicate label {name!r}")
        self.labels[name] = self.cur_va

    def emit(self, line: str) -> None:
        s = line.split("#", 1)[0].strip()
        if not s:
            return
        if s.endswith(":"):
            self.label(s[:-1].strip())
            return
        parts = s.split(None, 1)
        mnem = parts[0].lower()
        ops = [x.strip() for x in parts[1].split(",")] if len(parts) > 1 else []
        self.items.append((self.cur_va, mnem, ops))
        self.cur_va += 4

    def add_lines(self, text: str) -> None:
        for line in text.splitlines():
            self.emit(line)

    def _resolve(self, target: str) -> int:
        target = target.strip()
        if target in self.labels:
            return self.labels[target]
        return int(target, 0)

    def assemble(self) -> bytes:
        out = bytearray()
        for va, m, ops in self.items:
            w = self._encode(va, m, ops)
            out += struct.pack("<I", w)
        return bytes(out)

    def _encode(self, va: int, m: str, ops: list[str]) -> int:
        if m == "nop":
            return 0
        if m == ".word":
            return _imm(ops[0]) & 0xFFFFFFFF
        if m == "move":
            return _enc_r(_r(ops[1]), 0, _r(ops[0]), 0, 0x21)  # addu rd, rs, $zero
        if m == "li":
            val = _imm(ops[1])
            if -32768 <= val <= 32767:
                return _enc_i(9, 0, _r(ops[0]), val)
            if 0 <= val <= 0xFFFF:
                return _enc_i(13, 0, _r(ops[0]), val)
            raise ValueError(f"li constant {val:#x} doesn't fit 16-bit")
        if m == "lui":
            return _enc_i(15, 0, _r(ops[0]), _imm(ops[1]))
        if m in ("lwc1", "swc1"):
            off, base = _mem(ops[1])
            return _enc_i(49 if m == "lwc1" else 57, base, int(ops[0].lstrip("$f")), off)
        if m in ("mtc1", "mfc1"):
            return (17 << 26) | ((4 if m == "mtc1" else 0) << 21) | (_r(ops[0]) << 16) | (int(ops[1].lstrip("$f")) << 11)
        if m in ("cvt.s.w", "trunc.w.s"):
            fmt, fn = (20, 32) if m == "cvt.s.w" else (16, 13)
            return (17 << 26) | (fmt << 21) | (int(ops[1].lstrip("$f")) << 11) | (int(ops[0].lstrip("$f")) << 6) | fn
        if m == "mul.s":
            fd, fs, ft = (int(op.lstrip("$f")) for op in ops)
            return (17 << 26) | (16 << 21) | (ft << 16) | (fs << 11) | (fd << 6) | 2
        if m == "addiu":
            return _enc_i(9, _r(ops[1]), _r(ops[0]), _imm(ops[2]))
        if m == "andi":
            return _enc_i(12, _r(ops[1]), _r(ops[0]), _imm(ops[2]))
        if m == "ori":
            return _enc_i(13, _r(ops[1]), _r(ops[0]), _imm(ops[2]))
        if m == "xori":
            return _enc_i(14, _r(ops[1]), _r(ops[0]), _imm(ops[2]))
        if m == "slti":
            return _enc_i(10, _r(ops[1]), _r(ops[0]), _imm(ops[2]))
        if m == "sltiu":
            return _enc_i(11, _r(ops[1]), _r(ops[0]), _imm(ops[2]))
        if m in ("addu", "subu", "and", "or", "xor", "slt", "sltu"):
            fn = {"addu": 0x21, "subu": 0x23, "and": 0x24, "or": 0x25, "xor": 0x26, "slt": 0x2A, "sltu": 0x2B}[m]
            return _enc_r(_r(ops[1]), _r(ops[2]), _r(ops[0]), 0, fn)
        if m in ("sll", "srl", "sra"):
            fn = {"sll": 0x00, "srl": 0x02, "sra": 0x03}[m]
            return _enc_r(0, _r(ops[1]), _r(ops[0]), _imm(ops[2]), fn)
        if m == "mult":
            return _enc_r(_r(ops[0]), _r(ops[1]), 0, 0, 0x18)
        if m == "mflo":
            return _enc_r(0, 0, _r(ops[0]), 0, 0x12)
        if m == "mfhi":
            return _enc_r(0, 0, _r(ops[0]), 0, 0x10)
        if m == "div":
            if len(ops) == 2:
                return _enc_r(_r(ops[0]), _r(ops[1]), 0, 0, 0x1A)
            return _enc_r(_r(ops[1]), _r(ops[2]), 0, 0, 0x1A)
        if m in ("lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw"):
            op = {"lb": 32, "lh": 33, "lw": 35, "lbu": 36, "lhu": 37, "sb": 40, "sh": 41, "sw": 43}[m]
            off, base = _mem(ops[1])
            return _enc_i(op, base, _r(ops[0]), off)
        if m == "seh":
            return (0x1F << 26) | (_r(ops[1]) << 16) | (_r(ops[0]) << 11) | (0x18 << 6) | 0x20
        if m in ("beq", "bne", "beql", "bnel"):
            op = {"beq": 4, "bne": 5, "beql": 20, "bnel": 21}[m]
            tgt = self._resolve(ops[2])
            if (tgt - va - 4) % 4 or not -32768 <= (tgt - va - 4) // 4 <= 32767:
                raise ValueError(f"Branch target out of range or unaligned: {tgt:#x}")
            rel = (tgt - (va + 4)) >> 2
            return _enc_i(op, _r(ops[0]), _r(ops[1]), rel)
        if m in ("beqz", "bnez", "blez", "bgtz", "bltz", "bgez", "bgezl", "bltzl"):
            tgt = self._resolve(ops[1])
            if (tgt - va - 4) % 4 or not -32768 <= (tgt - va - 4) // 4 <= 32767:
                raise ValueError(f"Branch target out of range or unaligned: {tgt:#x}")
            rel = (tgt - (va + 4)) >> 2
            if m == "beqz":
                return _enc_i(4, _r(ops[0]), 0, rel)
            if m == "bnez":
                return _enc_i(5, _r(ops[0]), 0, rel)
            if m == "blez":
                return _enc_i(6, _r(ops[0]), 0, rel)
            if m == "bgtz":
                return _enc_i(7, _r(ops[0]), 0, rel)
            if m == "bltz":
                return _enc_i(1, _r(ops[0]), 0, rel)
            if m == "bgez":
                return _enc_i(1, _r(ops[0]), 1, rel)
            if m == "bltzl":
                return _enc_i(1, _r(ops[0]), 2, rel)
            if m == "bgezl":
                return _enc_i(1, _r(ops[0]), 3, rel)
        if m == "b":
            tgt = self._resolve(ops[0])
            if (tgt - va - 4) % 4 or not -32768 <= (tgt - va - 4) // 4 <= 32767:
                raise ValueError(f"Branch target out of range or unaligned: {tgt:#x}")
            rel = (tgt - (va + 4)) >> 2
            return _enc_i(4, 0, 0, rel)
        if m in ("j", "jal"):
            op = 2 if m == "j" else 3
            tgt = self._resolve(ops[0])
            if tgt % 4 or (tgt & 0xF0000000) != ((va + 4) & 0xF0000000):
                raise ValueError(f"Jump target out of region or unaligned: {tgt:#x}")
            return _enc_j(op, tgt)
        if m == "jr":
            return _enc_r(_r(ops[0]), 0, 0, 0, 0x08)
        if m == "jalr":
            if len(ops) == 1:
                return _enc_r(_r(ops[0]), 0, 31, 0, 0x09)
            return _enc_r(_r(ops[1]), 0, _r(ops[0]), 0, 0x09)
        raise ValueError(f"Unsupported instruction {m!r} {ops}")
