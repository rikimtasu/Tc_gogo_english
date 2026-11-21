"""Patch files inside a PSP ISO9660 image (in-place if <= original sectors, else append & update LBA/PVD)."""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


SECTOR_SIZE = 2048


def _align_sector(n: int) -> int:
    return (n + SECTOR_SIZE - 1) // SECTOR_SIZE * SECTOR_SIZE


def find_iso_file_record(iso_bytes_or_file, target_path: str) -> tuple[int, int, int]:
    """Return (dir_record_file_offset, lba, size) for a path like 'PSP_GAME/SYSDIR/EBOOT.BIN'."""
    parts = [p.upper() for p in target_path.strip("/").split("/")]
    f = iso_bytes_or_file
    f.seek(16 * SECTOR_SIZE)
    pvd = f.read(SECTOR_SIZE)
    if pvd[0] != 1 or pvd[1:6] != b"CD001":
        raise ValueError("Invalid ISO9660 Primary Volume Descriptor")
    cur_lba = struct.unpack_from("<I", pvd, 156 + 2)[0]
    cur_sz = struct.unpack_from("<I", pvd, 156 + 10)[0]

    for depth, name in enumerate(parts):
        f.seek(cur_lba * SECTOR_SIZE)
        dir_data = f.read(cur_sz)
        pos = 0
        found = None
        while pos < len(dir_data):
            rec_len = dir_data[pos]
            if rec_len == 0:
                # Advance to next 2048-byte sector boundary inside directory extent
                next_sec = ((pos // SECTOR_SIZE) + 1) * SECTOR_SIZE
                pos = next_sec
                continue
            ext_lba = struct.unpack_from("<I", dir_data, pos + 2)[0]
            ext_sz = struct.unpack_from("<I", dir_data, pos + 10)[0]
            flags = dir_data[pos + 25]
            id_len = dir_data[pos + 32]
            ident = dir_data[pos + 33 : pos + 33 + id_len].decode("ascii", "replace")
            ident_clean = ident.split(";", 1)[0].upper()
            if ident_clean == name:
                is_dir = bool(flags & 2)
                if depth < len(parts) - 1 and not is_dir:
                    raise FileNotFoundError(f"{name} is not a directory in {target_path}")
                found = (cur_lba * SECTOR_SIZE + pos, ext_lba, ext_sz)
                cur_lba, cur_sz = ext_lba, ext_sz
                break
            pos += rec_len
        if found is None:
            raise FileNotFoundError(f"Path {target_path!r} not found (missing {name!r})")
    return found


def patch_iso(src_iso: Path, out_iso: Path, replacements: dict[str, Path]) -> None:
    """Copy src_iso to out_iso and replace specified ISO paths."""
    if src_iso.resolve() == out_iso.resolve():
        raise ValueError("Source ISO is read-only; output must be a separate file")
    if out_iso.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {out_iso}")
    if not replacements:
        raise ValueError("At least one replacement is required")
    # Validate every path before creating a potentially large output copy.
    with src_iso.open("rb") as source:
        for iso_path, local_file in replacements.items():
            find_iso_file_record(source, iso_path)
            if not local_file.is_file():
                raise FileNotFoundError(local_file)
    out_iso.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the path without overwriting another build.
    with out_iso.open("xb"):
        pass
    shutil.copyfile(src_iso, out_iso)

    with open(out_iso, "r+b") as f:
        f.seek(16 * SECTOR_SIZE)
        pvd = bytearray(f.read(SECTOR_SIZE))
        vol_sectors = struct.unpack_from("<I", pvd, 80)[0]

        for iso_path, local_file in replacements.items():
            data = local_file.read_bytes()
            rec_off, orig_lba, orig_sz = find_iso_file_record(f, iso_path)
            orig_cap = _align_sector(orig_sz)

            if len(data) <= orig_cap:
                new_lba = orig_lba
                f.seek(new_lba * SECTOR_SIZE)
                f.write(data)
                pad = orig_cap - len(data)
                if pad:
                    f.write(b"\x00" * pad)
                mode = "in-place"
            else:
                new_lba = vol_sectors
                padded = _align_sector(len(data))
                f.seek(new_lba * SECTOR_SIZE)
                f.write(data)
                pad = padded - len(data)
                if pad:
                    f.write(b"\x00" * pad)
                vol_sectors += padded // SECTOR_SIZE
                mode = f"appended@{new_lba}"

            # Patch directory record: LBA (LE+BE at +2,+6) and Size (LE+BE at +10,+14)
            f.seek(rec_off)
            rec = bytearray(f.read(34))
            struct.pack_into("<I", rec, 2, new_lba)
            struct.pack_into(">I", rec, 6, new_lba)
            struct.pack_into("<I", rec, 10, len(data))
            struct.pack_into(">I", rec, 14, len(data))
            f.seek(rec_off)
            f.write(rec)
            print(f"Patched {iso_path}: {orig_sz} -> {len(data)} bytes ({mode})")

        # Update PVD VolumeSpaceSize (LE at 80, BE at 84)
        struct.pack_into("<I", pvd, 80, vol_sectors)
        struct.pack_into(">I", pvd, 84, vol_sectors)
        f.seek(16 * SECTOR_SIZE)
        f.write(pvd)
        f.truncate(vol_sectors * SECTOR_SIZE)


def main() -> None:
    ap = argparse.ArgumentParser(description="Patch files inside a PSP ISO")
    ap.add_argument("--src", required=True, help="Source ISO (read-only)")
    ap.add_argument("--out", required=True, help="Output patched ISO")
    ap.add_argument(
        "--replace",
        action="append",
        required=True,
        help="ISO_PATH=LOCAL_PATH (e.g. PSP_GAME/SYSDIR/EBOOT.BIN=work/eboot/EBOOT_patched.bin)",
    )
    args = ap.parse_args()
    reps: dict[str, Path] = {}
    for item in args.replace:
        iso_p, loc_p = item.split("=", 1)
        reps[iso_p] = Path(loc_p)
    patch_iso(Path(args.src), Path(args.out), reps)


if __name__ == "__main__":
    main()
