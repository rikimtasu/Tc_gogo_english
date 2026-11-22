"""Audit localized atlas sizes, protected artwork, and known menu UV windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def check_ui(orig_dir: Path, en_dir: Path) -> dict:
    manifest = json.loads((orig_dir / "manifest.json").read_text(encoding="utf-8"))
    checked = {}
    errors = []
    for item in manifest:
        path = en_dir / item["png"]
        if not path.is_file():
            continue
        with Image.open(path) as image:
            if image.size != (item["w"], item["h"]):
                errors.append(f"{item['png']}: atlas dimensions changed")
                continue
            pixels = np.array(image.convert("RGBA"))
        checked[item["cpk"]] = checked.get(item["cpk"], 0) + 1
        with Image.open(orig_dir / item["png"]) as image:
            original = np.array(image.convert("RGBA"))
        filename = Path(item["png"]).name
        if filename == "sys_o_files01.zip.png":
            bottoms = []
            for x0, y0 in ((424, 1), (440, 1), (456, 49)):
                cell = pixels[y0:y0 + 16, x0:x0 + 16]
                ink = (cell[:, :, :3] > 180).all(axis=2) & (cell[:, :, 3] >= 200)
                rows = np.where(ink)[0]
                if rows.size:
                    bottoms.append(int(rows.max()))
            if len(bottoms) != 3 or len(set(bottoms)) != 1:
                errors.append(f"{item['png']}: decimal point and digits have different baselines")
        if filename == "btl_total_vs_files01.zip.png" and not np.array_equal(pixels[:226], original[:226]):
            errors.append(f"{item['png']}: score digits overwritten by badge labels")
        if filename == "hetr_pack01.zip.png":
            if not np.array_equal(pixels[62:66, 218:224], original[62:66, 218:224]):
                errors.append(f"{item['png']}: trophy speech bubble corner overwritten")
        if filename == "sys_o_files05.zip.png":
            for x0, x1 in ((77, 82), (192, 196)):
                expected = np.repeat(original[4:11, 15:16], x1 - x0, axis=1)
                if not np.array_equal(pixels[4:11, x0:x1], expected):
                    errors.append(f"{item['png']}: old lettering remains at x={x0}..{x1}")
            for x, y in ((12, 4), (13, 4), (350, 4), (354, 4), (356, 4)):
                if not np.array_equal(pixels[y, x], original[y, x]):
                    errors.append(f"{item['png']}: tab end cap overwritten at {(x, y)}")
        if filename == "sys_sousa_02.zip.png":
            for x0, x1, region0, region1 in ((8, 107, 0, 176), (205, 262, 176, 352), (377, 442, 352, 512)):
                if pixels[:13, region0:x0, 3].any() or pixels[:13, x1:region1, 3].any():
                    errors.append(f"{item['png']}: controls heading exceeds UV window {x0}..{x1}")
    return {"checked_textures": sum(checked.values()), "archives": checked, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orig", type=Path, default=Path("work/p4_textures_orig"))
    parser.add_argument("--en", type=Path, default=Path("work/p4_textures_en"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = check_ui(args.orig, args.en)
    text = json.dumps(result, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            output.write(text + "\n")
    print(text)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
