"""Extract hardcoded Japanese CP932 strings from decrypted PSP EBOOT.BIN.

Scans the verified Japanese string regions in `work/eboot/EBOOT_decrypted.bin`
and exports structured translation entries (`glossary/eboot_strings.json`) with
file offsets, PSP virtual addresses (`0x08804000 + (file_offset - 0x54)`),
CP932 byte lengths, and in-place slot capacities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

PSP_LOAD_ADDR = 0x08804000
ELF_TEXT_OFFSET = 0x54
DEFAULT_EBOOT = Path("work/eboot/EBOOT_decrypted.bin")
DEFAULT_OUT = Path("glossary/eboot_strings.json")

JP_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]")

# Verified (category, start_file_offset, end_file_offset) blocks in EBOOT_decrypted.bin
EBOOT_BLOCKS: tuple[tuple[str, int, int], ...] = (
    ("save_metadata", 0x15C4A0, 0x15C9A0),
    ("date_time", 0x15D3E8, 0x15D454),
    ("save_dialog", 0x171178, 0x171CF8),
    ("install_metadata", 0x171D3C, 0x171DB0),
    ("install_dialog", 0x172124, 0x172264),
)


def file_offset_to_vaddr(file_offset: int) -> int:
    """Convert an EBOOT_decrypted.bin file offset to its PSP runtime vaddr."""
    return PSP_LOAD_ADDR + (file_offset - ELF_TEXT_OFFSET)


def _scan_block(
    eboot_bytes: bytes,
    category: str,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    limit = min(end, len(eboot_bytes))
    results: list[dict[str, Any]] = []
    pos = start

    while pos < limit:
        if eboot_bytes[pos] == 0:
            pos += 1
            continue

        nul = eboot_bytes.find(b"\x00", pos, limit)
        if nul == -1:
            nul = limit

        raw = eboot_bytes[pos:nul]
        next_pos = nul
        while next_pos < limit and eboot_bytes[next_pos] == 0:
            next_pos += 1

        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            pos = next_pos
            continue

        if JP_RE.search(text):
            # Max CP932 payload bytes before the required NUL terminator in contiguous padding.
            slot_capacity = max(len(raw), (next_pos - pos) - 1)
            results.append(
                {
                    "category": category,
                    "file_offset": f"0x{pos:06x}",
                    "vaddr": f"0x{file_offset_to_vaddr(pos):08x}",
                    "byte_len": len(raw),
                    "slot_capacity": slot_capacity,
                    "jp": text,
                    "en": "",
                }
            )

        pos = next_pos

    return results


def extract_eboot_strings(eboot_bytes: bytes) -> dict[str, Any]:
    """Extract all verified Japanese CP932 strings from decrypted EBOOT bytes."""
    entries: list[dict[str, Any]] = []
    for category, start, end in EBOOT_BLOCKS:
        entries.extend(_scan_block(eboot_bytes, category, start, end))

    for idx, entry in enumerate(entries, start=1):
        entry["id"] = f"eboot_{idx:03d}_{entry['category']}"
        # Keep consistent key ordering with id first.
        ordered = {
            "id": entry["id"],
            "category": entry["category"],
            "file_offset": entry["file_offset"],
            "vaddr": entry["vaddr"],
            "byte_len": entry["byte_len"],
            "slot_capacity": entry["slot_capacity"],
            "jp": entry["jp"],
            "en": entry["en"],
        }
        entries[idx - 1] = ordered

    return {
        "source_sha256": hashlib.sha256(eboot_bytes).hexdigest(),
        "count": len(entries),
        "strings": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract Japanese CP932 strings from decrypted PSP EBOOT.BIN."
    )
    parser.add_argument(
        "--eboot",
        type=Path,
        default=DEFAULT_EBOOT,
        help=f"Path to decrypted EBOOT.BIN (default: {DEFAULT_EBOOT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSON path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args(argv)

    eboot_bytes = args.eboot.read_bytes()
    payload = extract_eboot_strings(eboot_bytes)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    counts: dict[str, int] = {}
    for item in payload["strings"]:
        cat = item["category"]
        counts[cat] = counts.get(cat, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    print(f"Extracted {payload['count']} strings to {args.out} ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
