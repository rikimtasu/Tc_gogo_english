"""Pack localized P4 PNG textures back into GAMEINIT.CPK and BATTLE.CPK."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk.cpk import CpkArchive
from cpk.tim2 import decode_tm2, encode_tm2, unwrap_texture, wrap_texture


def build_p4_cpks(
    orig_dir: Path = Path("work/p4_textures_orig"),
    en_dir: Path = Path("work/p4_textures_en"),
    gameinit_src: Path = Path("work/iso_extract/GAMEINIT.CPK"),
    battle_src: Path = Path("work/iso_extract/BATTLE.CPK"),
    out_dir: Path = Path("work/p4_build"),
) -> dict[str, int]:
    manifest = json.loads((orig_dir / "manifest.json").read_text(encoding="utf-8"))
    gi = CpkArchive(str(gameinit_src))
    bt = CpkArchive(str(battle_src))

    gi_rows = {f"{r['DirName']}/{r['FileName']}" if r["DirName"] else r["FileName"]: r for r in gi.entries()}
    bt_rows = {f"{r['DirName']}/{r['FileName']}" if r["DirName"] else r["FileName"]: r for r in bt.entries()}

    gi_repl: dict[str, bytes] = {}
    bt_repl: dict[str, bytes] = {}

    for item in manifest:
        en_png = en_dir / item["png"]
        if not en_png.is_file():
            continue
        rel = item["rel"]
        cpk_name = item["cpk"]
        cpk = gi if cpk_name == "GAMEINIT" else bt
        row = gi_rows[rel] if cpk_name == "GAMEINIT" else bt_rows[rel]
        orig_raw = cpk.read_entry(row)
        orig_tm2, kind, orig_prefix = unwrap_texture(orig_raw, row["FileName"])

        img = Image.open(en_png).convert("RGBA")
        new_tm2 = encode_tm2(img, orig_tm2)
        wrapped = wrap_texture(new_tm2, kind, orig_prefix)

        # Round-trip sanity check
        chk_tm2, _, _ = unwrap_texture(wrapped, row["FileName"])
        chk_img = decode_tm2(chk_tm2)
        if chk_img.size != (item["w"], item["h"]):
            raise ValueError(f"{rel}: round-trip size mismatch {chk_img.size} != {(item['w'], item['h'])}")

        if cpk_name == "GAMEINIT":
            gi_repl[rel] = wrapped
        else:
            bt_repl[rel] = wrapped

    out_dir.mkdir(parents=True, exist_ok=True)
    gi_out = out_dir / "GAMEINIT.CPK"
    bt_out = out_dir / "BATTLE.CPK"
    gi.rebuild(str(gi_out), gi_repl)
    bt.rebuild(str(bt_out), bt_repl)

    return {"gameinit_replaced": len(gi_repl), "battle_replaced": len(bt_repl)}


if __name__ == "__main__":
    stats = build_p4_cpks()
    print("Built P4 CPKs:", stats)
