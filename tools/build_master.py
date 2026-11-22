"""Build and validate the merged P2+P3+P4 English ISO and xdelta3 v3.2.2 patch."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cpk.cpk import CpkArchive
from cpk.tim2 import decode_tm2, encode_tm2, unwrap_texture, wrap_texture
from eboot.patch_eboot import patch_bytes
from font.build_font import DEFAULT_TTF, build_fonts, font_license_files, font_specs, resolve_font_axes
from font.verify_font import verify_fonts
from iso.patch_iso import SECTOR_SIZE, find_iso_file_record, patch_iso
from pjadv.check_widths import DEFAULT_BUDGET_PX, DEFAULT_LINES, Metrics, wrap_lines
from pjadv.scenario import extract_from_bytes, pack_from_dir

ISO_SHA256 = "2025c8df4e642a65ae27da422eefb81c34f71028c425e848e5124d34a1669f7e"
GAMEINIT_SHA256 = "20387f20f9972667f9c2e28fd5d628832c6cdb20f3ac9be2550b06fc496f27b8"
DEFAULT_XDELTA = Path("work/tools/xdelta3-3.2.2/xdelta3-3.2.2-windows-x86_64/xdelta3.exe")


def _sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _verify_cpk_readback(orig: CpkArchive, rebuilt_path: Path, replacements: dict[str, bytes]) -> int:
    rebuilt = CpkArchive(str(rebuilt_path))
    if len(orig.entries()) != len(rebuilt.entries()):
        raise ValueError(f"CPK member count changed for {rebuilt_path.name}")
    for before, after in zip(orig.entries(), rebuilt.entries()):
        rel = f"{before['DirName']}/{before['FileName']}" if before["DirName"] else before["FileName"]
        if (before["DirName"], before["FileName"]) != (after["DirName"], after["FileName"]):
            raise ValueError(f"CPK member order changed: {rel}")
        expected = replacements[rel] if rel in replacements else orig.read_entry(before)
        if rebuilt.read_entry(after) != expected:
            raise ValueError(f"CPK readback mismatch: {rel}")
    return len(orig.entries())


def _collect_p4_replacements(
    manifest: list[dict],
    en_dir: Path,
    cpk_name: str,
    cpk: CpkArchive,
) -> dict[str, bytes]:
    rows = {f"{r['DirName']}/{r['FileName']}" if r["DirName"] else r["FileName"]: r for r in cpk.entries()}
    replacements: dict[str, bytes] = {}
    for item in manifest:
        if item["cpk"] != cpk_name:
            continue
        en_png = en_dir / item["png"]
        if not en_png.is_file():
            continue
        rel = item["rel"]
        row = rows[rel]
        orig_raw = cpk.read_entry(row)
        orig_tm2, kind, orig_prefix = unwrap_texture(orig_raw, row["FileName"])
        img = Image.open(en_png).convert("RGBA")
        new_tm2 = encode_tm2(img, orig_tm2)
        wrapped = wrap_texture(new_tm2, kind, orig_prefix)
        chk_tm2, _, _ = unwrap_texture(wrapped, row["FileName"])
        if decode_tm2(chk_tm2).size != (item["w"], item["h"]):
            raise ValueError(f"{rel}: TIM2 round-trip size mismatch")
        replacements[rel] = wrapped
    return replacements


def build_master(
    work: Path,
    iso: Path,
    gameinit_cpk: Path,
    battle_cpk: Path,
    graphic_cpk: Path,
    eboot: Path,
    eboot_strings: Path,
    trans: Path,
    p4_orig: Path,
    p4_en: Path,
    out: Path,
    fonts: Path | None,
    ttf: Path,
    xdelta_exe: Path,
    skip_xdelta: bool = False,
) -> dict:
    start = time.perf_counter()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {out}")

    if _sha256_file(iso) != ISO_SHA256:
        raise ValueError("Clean ISO identity mismatch; expected Japan v1.01")
    with iso.open("rb") as src_iso:
        _, gi_lba, gi_sz = find_iso_file_record(src_iso, "PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK")
        src_iso.seek(gi_lba * SECTOR_SIZE)
        if hashlib.sha256(src_iso.read(gi_sz)).hexdigest() != GAMEINIT_SHA256:
            raise ValueError("ISO GAMEINIT.CPK hash mismatch")
    if _sha256_file(gameinit_cpk) != GAMEINIT_SHA256:
        raise ValueError("work GAMEINIT.CPK does not match clean ISO")

    out.mkdir(parents=True)

    # 1. Patch EBOOT (P2 wrapping/backlog + P4 73 strings)
    patched_eboot, eboot_info = patch_bytes(eboot.read_bytes(), strings_path=eboot_strings)
    new_eboot = out / "EBOOT_patched.bin"
    new_eboot.write_bytes(patched_eboot)

    # 2. Fonts (P2 Barlow Semi Condensed Medium, tight dialogue)
    axes = resolve_font_axes(ttf, None)
    licenses = font_license_files(ttf)
    if fonts is None:
        fonts = out / "fonts"
        build_fonts(gameinit_cpk, ttf, fonts, tight_dialogue=True, font_axes=axes, antialias=True)
    font_results = verify_fonts(gameinit_cpk, fonts)

    # 3. Scenario width check + pack (P3 full gt_output)
    files_meta = json.loads((work / "metadata/scenario_slots.json").read_text(encoding="utf-8"))
    known_files = {item["file"] for item in files_meta}
    translated_files = {p.name for p in trans.glob("*.json")}
    if translated_files - known_files:
        raise ValueError(f"Unknown translation filenames: {sorted(translated_files - known_files)}")

    metrics = Metrics(fonts / "font" / "sulakyapi12" / "abc.w_abc")
    overflow = []
    for name in sorted(translated_files):
        for index, row in enumerate(json.loads((trans / name).read_text(encoding="utf-8"))):
            lines = wrap_lines(row.get("message", ""), metrics, DEFAULT_BUDGET_PX)
            if len(lines) > DEFAULT_LINES:
                overflow.append(f"{name}[{index}] ({len(lines)} lines)")

    packed_td, packed_sc, sc_stats = pack_from_dir(work, trans)
    if sc_stats["warnings"]:
        raise ValueError(f"Control-code validation failed: {sc_stats['warnings']}")

    checked = out / "reextracted"
    manifest_re = extract_from_bytes(packed_td, packed_sc, checked)
    changed_rows = 0
    for item in files_meta:
        name = item["file"]
        orig_rows = json.loads((work / "gt_input" / name).read_text(encoding="utf-8"))
        exp_path = trans / name if name in translated_files else work / "gt_input" / name
        exp_rows = json.loads(exp_path.read_text(encoding="utf-8"))
        act_rows = json.loads((checked / "gt_input" / name).read_text(encoding="utf-8"))
        if exp_rows != act_rows:
            raise ValueError(f"Re-extracted text differs: {name}")
        changed_rows += sum(a != b for a, b in zip(orig_rows, exp_rows))

    # 4. Merge P2 fonts + P3 scenario + P4 SystemZip into GAMEINIT.CPK
    p4_manifest = json.loads((p4_orig / "manifest.json").read_text(encoding="utf-8"))
    gi_arc = CpkArchive(str(gameinit_cpk))
    gi_replacements = {p.relative_to(fonts).as_posix(): p.read_bytes() for p in (fonts / "font").rglob("*") if p.is_file()}
    gi_replacements.update({"scenario/textdata.bin": packed_td, "scenario/scenario.bin": packed_sc})
    gi_p4 = _collect_p4_replacements(p4_manifest, p4_en, "GAMEINIT", gi_arc)
    gi_replacements.update(gi_p4)

    new_gi = out / "GAMEINIT.CPK"
    gi_arc.rebuild(str(new_gi), gi_replacements)
    gi_verified = _verify_cpk_readback(gi_arc, new_gi, gi_replacements)

    # 5. Pack P4 textures into BATTLE.CPK and GRAPHIC.CPK
    bt_arc = CpkArchive(str(battle_cpk))
    bt_replacements = _collect_p4_replacements(p4_manifest, p4_en, "BATTLE", bt_arc)
    new_bt = out / "BATTLE.CPK"
    bt_arc.rebuild(str(new_bt), bt_replacements)
    bt_verified = _verify_cpk_readback(bt_arc, new_bt, bt_replacements)

    gr_arc = CpkArchive(str(graphic_cpk))
    gr_replacements = _collect_p4_replacements(p4_manifest, p4_en, "GRAPHIC", gr_arc)
    new_gr = out / "GRAPHIC.CPK"
    gr_arc.rebuild(str(new_gr), gr_replacements)
    gr_verified = _verify_cpk_readback(gr_arc, new_gr, gr_replacements)

    # 6. Patch ISO
    new_iso = out / "Twinkle_Crusaders_GoGo_EN.iso"
    iso_replacements = {
        "PSP_GAME/SYSDIR/EBOOT.BIN": new_eboot,
        "PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK": new_gi,
        "PSP_GAME/USRDIR/DISK1/BATTLE.CPK": new_bt,
        "PSP_GAME/USRDIR/DISK1/GRAPHIC.CPK": new_gr,
    }
    patch_iso(iso, new_iso, iso_replacements)
    with new_iso.open("rb") as res_f:
        for iso_path, local_path in iso_replacements.items():
            _, lba, sz = find_iso_file_record(res_f, iso_path)
            res_f.seek(lba * SECTOR_SIZE)
            if res_f.read(sz) != local_path.read_bytes():
                raise ValueError(f"ISO readback mismatch: {iso_path}")

    for lic in licenses:
        shutil.copyfile(lic, out / lic.name)

    # 7. Generate xdelta3 patch
    xdelta_path = out / "Twinkle_Crusaders_GoGo_EN.xdelta"
    if not skip_xdelta:
        if not xdelta_exe.is_file():
            raise FileNotFoundError(f"xdelta3 binary not found: {xdelta_exe}")
        cmd = [str(xdelta_exe), "-e", "-9", "-f", "-s", str(iso), str(new_iso), str(xdelta_path)]
        subprocess.run(cmd, check=True)

    summary = {
        "iso": str(new_iso),
        "iso_bytes": new_iso.stat().st_size,
        "xdelta": str(xdelta_path) if not skip_xdelta else None,
        "xdelta_bytes": xdelta_path.stat().st_size if not skip_xdelta else None,
        "translated_files": len(translated_files),
        "changed_rows": changed_rows,
        "width_overflow_count": len(overflow),
        "width_overflow_sample": overflow[:10],
        "eboot_patched_strings": eboot_info["patched_strings"],
        "eboot_payload_bytes": eboot_info["payload_bytes"],
        "gameinit_p4_textures": len(gi_p4),
        "gameinit_members_verified": gi_verified,
        "battle_p4_textures": len(bt_replacements),
        "battle_members_verified": bt_verified,
        "graphic_p4_textures": len(gr_replacements),
        "graphic_members_verified": gr_verified,
        "fonts": font_results,
        "scenario": sc_stats,
        "reextracted_summary": manifest_re["summary"],
        "elapsed_seconds": round(time.perf_counter() - start, 2),
    }
    (out / "validation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, default=Path("."))
    ap.add_argument("--iso", type=Path, default=Path("Twinkle Crusaders GoGo! (Japan) (v1.01).iso"))
    ap.add_argument("--gameinit", type=Path, default=Path("work/iso_extract/GAMEINIT.CPK"))
    ap.add_argument("--battle", type=Path, default=Path("work/iso_extract/BATTLE.CPK"))
    ap.add_argument("--graphic", type=Path, default=Path("work/iso_extract/GRAPHIC.CPK"))
    ap.add_argument("--eboot", type=Path, default=Path("work/eboot/EBOOT_decrypted.bin"))
    ap.add_argument("--eboot-strings", type=Path, default=Path("glossary/eboot_strings.json"))
    ap.add_argument("--trans", type=Path, default=Path("gt_output"))
    ap.add_argument("--p4-orig", type=Path, default=Path("work/p4_textures_orig"))
    ap.add_argument("--p4-en", type=Path, default=Path("work/p4_textures_en"))
    ap.add_argument("--fonts", type=Path, default=None)
    ap.add_argument("--ttf", type=Path, default=DEFAULT_TTF)
    ap.add_argument("--xdelta", type=Path, default=DEFAULT_XDELTA)
    ap.add_argument("--skip-xdelta", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    res = build_master(
        work=args.work,
        iso=args.iso,
        gameinit_cpk=args.gameinit,
        battle_cpk=args.battle,
        graphic_cpk=args.graphic,
        eboot=args.eboot,
        eboot_strings=args.eboot_strings,
        trans=args.trans,
        p4_orig=args.p4_orig,
        p4_en=args.p4_en,
        out=args.out,
        fonts=args.fonts,
        ttf=args.ttf,
        xdelta_exe=args.xdelta,
        skip_xdelta=args.skip_xdelta,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
