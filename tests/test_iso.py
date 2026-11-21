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

    def test_replacement_and_growth(self):
        for size in (4, 4097):
            with self.subTest(size=size):
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

    def test_source_cannot_be_output(self):
        with self.assertRaises(ValueError):
            patch_iso(self.src, self.src, {'FILE.BIN': self.file})

    def test_existing_output_cannot_be_overwritten(self):
        self.out.write_bytes(b'user work')
        with self.assertRaises(FileExistsError):
            patch_iso(self.src, self.out, {'FILE.BIN': self.file})
        self.assertEqual(self.out.read_bytes(), b'user work')

    def test_invalid_replacement_creates_no_output(self):
        with self.assertRaises(FileNotFoundError):
            patch_iso(self.src, self.out, {'MISSING.BIN': self.file})
        self.assertFalse(self.out.exists())
