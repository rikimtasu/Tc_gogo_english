"""Generate PPSSPP CWCheat scene-jump codes for Twinkle Crusaders GoGo! (ULJS-00316).

Maps every gt_output/*.json scene (and optionally any individual dialogue row)
to its exact PJADV scenario.bin byte offset and emits ready-to-paste CWCheat
blocks targeting the live VM program counter at 0x0897BF08 (CWCheat 0x2017BF08).
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from pjadv.chunk_bin import unpack_chunked_bin  # noqa: E402
from pjadv.scenario import OP_SCENE, parse_textdata, walk_scenario  # noqa: E402

CWCHEAT_VM_PC = 0x2017BF08      # 0x0897BF08: live PJADV scenario.bin byte offset
CWCHEAT_VM_STATE = 0x2017BEFC   # 0x0897BEFC: VM wait state (0 = running)
DEFAULT_COMBO_MASK = 0x0030     # D-Pad Up (0x10) + Right (0x20) — unused in ADV mode
DEFAULT_COMBO_LABEL = "Up+Right"


def _load_title_map(glossary_path: Path) -> dict[str, str]:
    if not glossary_path.exists():
        return {}
    data = json.loads(glossary_path.read_text(encoding="utf-8"))
    return {entry["jp"]: entry["en"] for entry in data.get("titles", [])}


def _display_title(scene_raw: str, title_map: dict[str, str]) -> str:
    if scene_raw.startswith("###"):
        return scene_raw[3:]
    if "###" in scene_raw:
        vis, suffix = scene_raw.split("###", 1)
        en = title_map.get(vis, vis)
        return f"{en} [{suffix}]"
    vis = scene_raw.strip("\u3000 \t")
    if not vis:
        return "(system/untitled)"
    return title_map.get(scene_raw, title_map.get(vis, vis))


def _ascii_safe(text: str) -> str:
    """Keep PPSSPP CWCheat menu titles clean ASCII."""
    return text.encode("ascii", errors="replace").decode("ascii")


def load_scenes(work_dir: Path) -> list[dict[str, Any]]:
    meta_path = work_dir / "metadata" / "scenario_slots.json"
    sc_path = work_dir / "original" / "scenario.bin"
    td_path = work_dir / "original" / "textdata.bin"
    titles_path = work_dir / "glossary" / "scene_titles.json"

    files_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sc_raw, _ = unpack_chunked_bin(sc_path.read_bytes())
    td_raw, _ = unpack_chunked_bin(td_path.read_bytes())
    _, _, td_entries, off_to_idx = parse_textdata(td_raw)
    title_map = _load_title_map(titles_path)

    op_scenes: list[tuple[int, str]] = [
        (p, td_entries[off_to_idx[words[1]]][2])
        for p, w0, words in walk_scenario(sc_raw)
        if w0 == OP_SCENE
    ]
    op_offs = [p for p, _ in op_scenes]

    scenes: list[dict[str, Any]] = []
    for entry in files_meta:
        slots = entry["slots"]
        first_off = slots[0]["sc_off"]
        idx = bisect.bisect_right(op_offs, first_off) - 1
        if idx < 0:
            raise ValueError(f"Scene {entry['file']} precedes first OP_SCENE")
        op_off, op_raw = op_scenes[idx]
        if op_raw != entry["scene_raw"]:
            raise ValueError(
                f"OP_SCENE mismatch for {entry['file']}: "
                f"{op_raw!r} != {entry['scene_raw']!r}"
            )
        en_title = _display_title(entry["scene_raw"], title_map)
        scenes.append(
            {
                "file": entry["file"],
                "num": entry["file"].split("_", 1)[0],
                "op_off": op_off,
                "scene_raw": entry["scene_raw"],
                "en_title": en_title,
                "count": entry["count"],
                "slots": slots,
            }
        )
    return scenes


def format_cheat_block(
    label: str,
    target_off: int,
    *,
    combo_mask: int = DEFAULT_COMBO_MASK,
    instant: bool = False,
    comment: str | None = None,
) -> str:
    lines: list[str] = []
    if comment:
        lines.append(f"# {comment}")
    lines.append(f"_C0 {_ascii_safe(label)}")
    if instant:
        lines.append(f"_L 0xD0000001 0x1000{combo_mask:04X}")
        lines.append(f"_L 0x{CWCHEAT_VM_PC:08X} 0x{target_off:08X}")
        lines.append(f"_L 0x{CWCHEAT_VM_STATE:08X} 0x00000000")
    else:
        lines.append(f"_L 0xD0000000 0x1000{combo_mask:04X}")
        lines.append(f"_L 0x{CWCHEAT_VM_PC:08X} 0x{target_off:08X}")
    return "\n".join(lines)


def filter_scenes(scenes: list[dict[str, Any]], query: str | None) -> list[dict[str, Any]]:
    if not query:
        return scenes
    q = query.strip().lower()
    if q.isdigit() and len(q) <= 4:
        target_num = q.zfill(4)
        return [s for s in scenes if s["num"] == target_num]
    if q.startswith("0x"):
        target_hex = int(q, 16)
        return [s for s in scenes if s["op_off"] == target_hex]
    out = []
    for s in scenes:
        haystack = " ".join([s["file"], s["scene_raw"], s["en_title"]]).lower()
        if q in haystack:
            out.append(s)
    return out


def build_ini(
    scenes: list[dict[str, Any]],
    *,
    combo_mask: int = DEFAULT_COMBO_MASK,
    combo_label: str = DEFAULT_COMBO_LABEL,
    instant: bool = False,
    row_index: int | None = None,
    trans_dir: Path | None = None,
) -> str:
    how = (
        f"Tap {combo_label} to jump immediately"
        if instant
        else f"Hold {combo_label} at any dialogue, release, press Circle"
    )
    header = "\n".join(
        [
            "_S ULJS-00316",
            "_G Twinkle Crusaders GoGo!",
            f"# Generated by tools/pjadv/scene_jump_cheat.py ({len(scenes)} entries)",
            f"# Usage: Enable ONE cheat below. {how}.",
        ]
    )
    blocks: list[str] = []
    for s in scenes:
        if row_index is not None:
            if row_index < 0 or row_index >= s["count"]:
                raise SystemExit(
                    f"Row {row_index} out of range for {s['file']} (0..{s['count'] - 1})"
                )
            slot = s["slots"][row_index]
            target_off = slot["sc_off"]
            preview = ""
            if trans_dir is not None:
                jp_or_en = trans_dir / s["file"]
                if jp_or_en.exists():
                    rows = json.loads(jp_or_en.read_text(encoding="utf-8"))
                    msg = rows[row_index].get("message", "").replace("\n", " ")
                    preview = f" ({msg[:48]})"
            label = f"Jump {s['num']} row {row_index}: {s['en_title']}"
            comment = f"{s['file']}[{row_index}] ({slot['kind']}) @ 0x{target_off:08X}{preview}"
        else:
            target_off = s["op_off"]
            label = f"Jump {s['num']}: {s['en_title']}"
            comment = None
        blocks.append(
            format_cheat_block(
                label,
                target_off,
                combo_mask=combo_mask,
                instant=instant,
                comment=comment,
            )
        )
    return header + "\n\n" + "\n\n".join(blocks) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate PPSSPP CWCheat scene-jump codes from gt_output / scenario.bin."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Optional case-insensitive filter (scene number, filename, JP/EN title, or hex offset).",
    )
    parser.add_argument(
        "--work",
        type=Path,
        default=REPO_ROOT,
        help="Workspace root containing metadata/, original/, glossary/ (default: repo root).",
    )
    parser.add_argument(
        "--row",
        type=int,
        default=None,
        help="Jump directly to a specific row index (0-based) within the matched scene(s).",
    )
    parser.add_argument(
        "--instant",
        action="store_true",
        help="Also clear vm_state (0x2017BEFC = 0) so the jump fires without pressing Circle.",
    )
    parser.add_argument(
        "--combo",
        default=f"0x{DEFAULT_COMBO_MASK:04X}",
        help="PSP button bitmask hex for joker trigger (default: 0x0030 = Up+Right).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print a compact table of matching scenes instead of CWCheat blocks.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the generated ULJS00316.ini to this path instead of stdout.",
    )
    args = parser.parse_args()

    combo_mask = int(args.combo, 16)
    combo_label = (
        DEFAULT_COMBO_LABEL if combo_mask == DEFAULT_COMBO_MASK else f"0x{combo_mask:04X}"
    )

    scenes = load_scenes(args.work)
    matched = filter_scenes(scenes, args.query)
    if not matched:
        raise SystemExit(f"No scenes matched {args.query!r}")

    if args.list:
        for s in matched:
            print(
                f"{s['num']}  0x{s['op_off']:08X}  ({s['count']:4d} rows)  "
                f"{s['en_title']}  |  {s['file']}"
            )
        return

    ini_text = build_ini(
        matched,
        combo_mask=combo_mask,
        combo_label=combo_label,
        instant=args.instant,
        row_index=args.row,
        trans_dir=args.work / "gt_output",
    )

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(ini_text, encoding="utf-8", newline="\n")
        print(f"Wrote {len(matched)} cheat(s) to {args.out}")
    else:
        sys.stdout.write(ini_text)


if __name__ == "__main__":
    main()
