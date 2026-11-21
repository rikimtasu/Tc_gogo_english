"""Build and structurally validate a P2 test ISO without modifying clean inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cpk.cpk import CpkArchive
from eboot.patch_eboot import patch_bytes
from font.build_font import (build_fonts, font_specs, DEFAULT_TTF, resolve_font_axes,
                            font_license_files)
from font.verify_font import verify_fonts
from iso.patch_iso import patch_iso, find_iso_file_record, SECTOR_SIZE
from pjadv.scenario import pack_from_dir, extract_from_bytes


ISO_SHA256 = '2025c8df4e642a65ae27da422eefb81c34f71028c425e848e5124d34a1669f7e'
CPK_SHA256 = '20387f20f9972667f9c2e28fd5d628832c6cdb20f3ac9be2550b06fc496f27b8'


def build(work: Path, iso: Path, cpk: Path, eboot: Path, trans: Path,
          out: Path, fonts: Path | None, ttf: Path, dialogue_size: int | None = None,
          tight_dialogue: bool = False, dialogue_width_scale: float | None = None,
          font_axes: dict[str, float] | None = None, antialias: bool = True) -> dict:
    start = time.perf_counter()
    specs = font_specs(dialogue_size=dialogue_size, tight_dialogue=tight_dialogue,
                       dialogue_width_scale=dialogue_width_scale)
    axes = resolve_font_axes(ttf, font_axes)
    licenses = font_license_files(ttf)
    if fonts is not None and (dialogue_size is not None or tight_dialogue or dialogue_width_scale is not None or font_axes is not None or not antialias):
        raise ValueError('Font settings cannot be used with prebuilt --fonts; generate the requested settings first')
    if out.exists():
        raise FileExistsError(f'Choose a new build directory; refusing to overwrite {out}')
    # These hashes identify the exact source revision, not build status markers.
    with iso.open('rb') as source:
        sha = hashlib.sha256()
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
            sha.update(chunk)
        if sha.hexdigest() != ISO_SHA256:
            raise ValueError('Clean ISO identity mismatch; expected Japan v1.01')
        _, lba, size = find_iso_file_record(source, 'PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK')
        source.seek(lba * SECTOR_SIZE)
        source_cpk = source.read(size)
    if hashlib.sha256(source_cpk).hexdigest() != CPK_SHA256 or source_cpk != cpk.read_bytes():
        raise ValueError('CPK does not match the clean ISO')
    patched_eboot, eboot_info = patch_bytes(eboot.read_bytes())
    files_meta = json.loads((work / 'metadata/scenario_slots.json').read_text(encoding='utf-8'))
    known_files = {item['file'] for item in files_meta}
    translated_files = {p.name for p in trans.glob('*.json')}
    unknown = translated_files - known_files
    if unknown:
        raise ValueError(f'Unknown translation filenames: {sorted(unknown)}')
    if not translated_files:
        raise ValueError('No translated JSON files found')
    out.mkdir(parents=True)
    if fonts is None:
        fonts = out / 'fonts'
        build_fonts(cpk, ttf, fonts, dialogue_size=dialogue_size, tight_dialogue=tight_dialogue,
                    dialogue_width_scale=dialogue_width_scale, font_axes=axes, antialias=antialias)
    font_results = verify_fonts(cpk, fonts)
    packed_td, packed_sc, stats = pack_from_dir(work, trans)
    if stats['warnings']:
        raise ValueError(f"Control-code validation failed: {stats['warnings']}")

    # Re-extract the rebuilt scenario to verify ordered rows, names, and every
    # text reference, including scenes whose pointers moved but text did not.
    checked = out / 'reextracted'
    manifest = extract_from_bytes(packed_td, packed_sc, checked)
    expected_names = known_files
    actual_names = {p.name for p in (checked / 'gt_input').glob('*.json')}
    if expected_names != actual_names:
        raise ValueError('Re-extracted scene filenames differ')
    changed_rows = 0
    for item in files_meta:
        name = item['file']
        original = json.loads((work / 'gt_input' / name).read_text(encoding='utf-8'))
        expected_path = trans / name if name in translated_files else work / 'gt_input' / name
        expected = json.loads(expected_path.read_text(encoding='utf-8'))
        actual = json.loads((checked / 'gt_input' / name).read_text(encoding='utf-8'))
        if expected != actual:
            raise ValueError(f'Re-extracted text differs: {name}')
        changed_rows += sum(a != b for a, b in zip(original, expected))

    arc = CpkArchive(str(cpk))
    replacements = {p.relative_to(fonts).as_posix(): p.read_bytes()
                    for p in (fonts / 'font').rglob('*') if p.is_file()}
    replacements.update({'scenario/textdata.bin': packed_td, 'scenario/scenario.bin': packed_sc})
    paths = {f"{r['DirName']}/{r['FileName']}": r for r in arc.entries()}
    if replacements.keys() - paths.keys():
        raise ValueError('Replacement contains unknown CPK members')
    new_cpk = out / 'GAMEINIT.CPK'
    arc.rebuild(str(new_cpk), replacements)
    rebuilt = CpkArchive(str(new_cpk))
    if len(arc.entries()) != len(rebuilt.entries()):
        raise ValueError('CPK member count changed')
    for before, after in zip(arc.entries(), rebuilt.entries()):
        path = f"{before['DirName']}/{before['FileName']}"
        if (before['DirName'], before['FileName']) != (after['DirName'], after['FileName']):
            raise ValueError('CPK member order changed')
        expected = replacements[path] if path in replacements else arc.read_entry(before)
        if rebuilt.read_entry(after) != expected:
            raise ValueError(f'CPK readback mismatch: {path}')

    new_eboot = out / 'EBOOT_patched.bin'
    new_eboot.write_bytes(patched_eboot)
    new_iso = out / 'Twinkle_Crusaders_GoGo_P2.iso'
    iso_replacements = {'PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK': new_cpk,
                        'PSP_GAME/SYSDIR/EBOOT.BIN': new_eboot}
    patch_iso(iso, new_iso, iso_replacements)
    with new_iso.open('rb') as result:
        for path, local in iso_replacements.items():
            _, lba, size = find_iso_file_record(result, path)
            result.seek(lba * SECTOR_SIZE)
            if result.read(size) != local.read_bytes():
                raise ValueError(f'ISO readback mismatch: {path}')
    for license_path in licenses:
        shutil.copyfile(license_path, out / license_path.name)
    results = {'iso': str(new_iso), 'translated_files': sorted(translated_files),
               'changed_rows': changed_rows, 'scenario': stats,
               'reextracted_summary': manifest['summary'], 'cpk_members_verified': len(arc.entries()),
               'fonts': font_results, 'eboot_payload_bytes': eboot_info['payload_bytes'],
               'iso_bytes': new_iso.stat().st_size, 'elapsed_seconds': round(time.perf_counter() - start, 2),
               'runtime_validated': False, 'font_source': str(ttf), 'font_axes': axes,
               'font_antialias': antialias, 'font_presets': specs,
               'font_licenses': [str(path) for path in licenses]}
    if dialogue_size is not None:
        results['dialogue_size_px'] = dialogue_size
    if tight_dialogue:
        results['tight_dialogue'] = True
    (out / 'validation.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return results


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, default=Path('.'))
    ap.add_argument('--iso', type=Path, default=Path('Twinkle Crusaders GoGo! (Japan) (v1.01).iso'))
    ap.add_argument('--cpk', type=Path, default=Path('work/iso_extract/GAMEINIT.CPK'))
    ap.add_argument('--eboot', type=Path, default=Path('work/eboot/EBOOT_decrypted.bin'))
    ap.add_argument('--trans', type=Path, default=Path('gt_output'))
    ap.add_argument('--fonts', type=Path, help='Reuse a validated build containing font/; otherwise generate new assets')
    ap.add_argument('--ttf', type=Path, default=DEFAULT_TTF)
    ap.add_argument('--dialogue-size', type=int, help='Latin dialogue raster size, 10..16px (default: 14px)')
    ap.add_argument('--tight-dialogue', action='store_true', help='Tight Latin dialogue spacing, 90%% width and 2px spaces')
    ap.add_argument('--dialogue-width-scale', type=float, help='Override Latin dialogue width (0 < scale <= 1)')
    ap.add_argument('--font-weight', type=float, help='Variable weight (default: 500)')
    ap.add_argument('--font-roundness', type=float, help='Inrond roundness (default: 50)')
    ap.add_argument('--font-optical-size', type=float, help='Variable optical size (default: 14)')
    ap.add_argument('--no-antialias', action='store_true', help='Use legacy binary rasterization')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    axes = {tag: value for tag, value in (('wght', args.font_weight), ('ROND', args.font_roundness), ('opsz', args.font_optical_size)) if value is not None}
    print(json.dumps(build(args.work, args.iso, args.cpk, args.eboot, args.trans,
                           args.out, args.fonts, args.ttf, args.dialogue_size, args.tight_dialogue,
                           args.dialogue_width_scale, axes or None, not args.no_antialias), indent=2))
