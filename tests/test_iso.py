import struct
import tempfile
import unittest
from pathlib import Path

from tools.iso.patch_iso import find_iso_file_record, patch_iso, SECTOR_SIZE


def record(lba, size, name, flags=0):
    length = 33 + len(name)
    length += length % 2
    out = bytearray(length)
    out[0] = length
    struct.pack_into('<I', out, 2, lba)
    struct.pack_into('>I', out, 6, lba)
    struct.pack_into('<I', out, 10, size)
    struct.pack_into('>I', out, 14, size)
    out[25] = flags
    out[32] = len(name)
    out[33:33 + len(name)] = name
    return out


class IsoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.src, self.out, self.file = root / 'src.iso', root / 'out.iso', root / 'file.bin'
        iso = bytearray(32 * SECTOR_SIZE)
        pvd = 16 * SECTOR_SIZE
        iso[pvd:pvd + 7] = b'\x01CD001\x01'
        struct.pack_into('<I', iso, pvd + 80, 32)
        struct.pack_into('>I', iso, pvd + 84, 32)
        iso[pvd + 156:pvd + 190] = record(20, 2048, b'\0', 2)
        r = record(25, 2048, b'FILE.BIN;1')
        iso[20 * SECTOR_SIZE:20 * SECTOR_SIZE + len(r)] = r
        iso[25 * SECTOR_SIZE:26 * SECTOR_SIZE] = b'J' * SECTOR_SIZE
        self.src.write_bytes(iso)

    def test_iso_patch_and_safety_guards(self):
        for size in (4, 4097):
            out = self.out.with_name(f'out_{size}.iso')
            before = self.src.read_bytes()
            self.file.write_bytes(b'E' * size)
            patch_iso(self.src, out, {'FILE.BIN': self.file})
            with out.open('rb') as f:
                off, lba, actual_size = find_iso_file_record(f, 'FILE.BIN')
                self.assertEqual(actual_size, size)
                self.assertEqual(lba, 25 if size == 4 else 32)
                f.seek(lba * SECTOR_SIZE)
                self.assertEqual(f.read(size), b'E' * size)
                f.seek(off + 6)
                self.assertEqual(struct.unpack('>I', f.read(4))[0], lba)
            self.assertEqual(before, self.src.read_bytes())

        with self.assertRaises(ValueError):
            patch_iso(self.src, self.src, {'FILE.BIN': self.file})

        self.out.write_bytes(b'user work')
        with self.assertRaises(FileExistsError):
            patch_iso(self.src, self.out, {'FILE.BIN': self.file})
        self.assertEqual(self.out.read_bytes(), b'user work')

        missing_out = self.out.with_name('missing.iso')
        with self.assertRaises(FileNotFoundError):
            patch_iso(self.src, missing_out, {'MISSING.BIN': self.file})
        self.assertFalse(missing_out.exists())

    def test_iso_reuses_interior_zero_gap_without_growing_volume(self):
        # Build a 128-sector ISO with an interior 64-sector zero gap between A.BIN (LBA 32) and B.BIN (LBA 100)
        root = self.src.parent
        src = root / 'gap_src.iso'
        out = root / 'gap_out.iso'
        iso = bytearray(128 * SECTOR_SIZE)
        pvd = 16 * SECTOR_SIZE
        iso[pvd:pvd + 7] = b'\x01CD001\x01'
        struct.pack_into('<I', iso, pvd + 80, 128)
        struct.pack_into('>I', iso, pvd + 84, 128)
        iso[pvd + 156:pvd + 190] = record(20, 2048, b'\0', 2)
        ra = record(32, 2048, b'A.BIN;1')
        rb = record(100, 2048, b'B.BIN;1')
        iso[20 * SECTOR_SIZE:20 * SECTOR_SIZE + len(ra)] = ra
        iso[20 * SECTOR_SIZE + len(ra):20 * SECTOR_SIZE + len(ra) + len(rb)] = rb
        iso[32 * SECTOR_SIZE:33 * SECTOR_SIZE] = b'A' * SECTOR_SIZE
        iso[100 * SECTOR_SIZE:101 * SECTOR_SIZE] = b'B' * SECTOR_SIZE
        src.write_bytes(iso)

        big = root / 'big_a.bin'
        payload = b'X' * (10 * SECTOR_SIZE)
        big.write_bytes(payload)
        patch_iso(src, out, {'A.BIN': big})
        self.assertEqual(out.stat().st_size, 128 * SECTOR_SIZE)
        with out.open('rb') as f:
            _, lba, sz = find_iso_file_record(f, 'A.BIN')
            self.assertEqual(sz, len(payload))
            self.assertEqual(lba, 48)  # 16-sector-aligned inside interior gap 33..100
            f.seek(lba * SECTOR_SIZE)
            self.assertEqual(f.read(sz), payload)
