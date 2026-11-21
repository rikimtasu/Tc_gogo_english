"""Validate rebuilt font metrics, Japanese preservation, and TIM2 round trips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .build_font import (FONT_SPECS, CpkArchive, crilayla, parse_w_abc,
                             build_w_abc, decode_tim2_4bpp, encode_tim2_4bpp, antialias_clut)
except ImportError:
    from build_font import (FONT_SPECS, CpkArchive, crilayla, parse_w_abc,
                            build_w_abc, decode_tim2_4bpp, encode_tim2_4bpp, antialias_clut)


def verify_fonts(cpk_path: Path, font_root: Path) -> dict:
    arc = CpkArchive(str(cpk_path))
    rows = {f"{r['DirName']}/{r['FileName']}": r for r in arc.entries()}
    results = {}
    for name, spec in FONT_SPECS.items():
        rel = f'font/{name}'
        original = crilayla.decompress(arc.read_entry(rows[f'{rel}/abc.w_abc']))
        rebuilt = crilayla.decompress((font_root / rel / 'abc.w_abc').read_bytes())
        oh, ol, og = parse_w_abc(original)
        nh, nl, ng = parse_w_abc(rebuilt)
        if oh != nh or original != build_w_abc(oh, ol, og) or rebuilt != build_w_abc(nh, nl, ng):
            raise ValueError(f'{name}: metrics header/serialization mismatch')
        for code in range(127, len(ol)):
            if og[ol[code]] != ng[nl[code]]:
                raise ValueError(f'{name}: non-ASCII mapping changed at {code:#x}')
        original_sheets, new_sheets = [], []
        antialiased_sheets = 0
        aa_sheet_indices = set()
        for sheet in spec['sheets']:
            src = crilayla.decompress(arc.read_entry(rows[f'{rel}/{sheet}']))
            dst = crilayla.decompress((font_root / rel / sheet).read_bytes())
            op, ow, ohh, ohdr, oc = decode_tim2_4bpp(src)
            np, nw, nhh, nhdr, nc = decode_tim2_4bpp(dst)
            if src != encode_tim2_4bpp(op, ow, ohh, ohdr, oc) or dst != encode_tim2_4bpp(np, nw, nhh, nhdr, nc):
                raise ValueError(f'{name}/{sheet}: TIM2 round-trip mismatch')
            if oc != nc:
                if nc != antialias_clut(oc, set(op)):
                    raise ValueError(f'{name}/{sheet}: palette used by original glyphs changed')
                antialiased_sheets += 1
                aa_sheet_indices.add(len(new_sheets))
            original_sheets.append((op, ow, ohh))
            new_sheets.append((np, nw, nhh))
        # Old glyph rectangles remain intact even when the atlas expands.
        for record in og:
            x0, y0, x1, y1, _, _, _, _, sheet = record
            op, ow, ohh = original_sheets[sheet]
            np, nw, nhh = new_sheets[sheet]
            if not (0 <= x0 <= x1 <= ow <= nw and 0 <= y0 <= y1 <= ohh <= nhh):
                raise ValueError(f'{name}: invalid original glyph bounds')
            for y in range(y0, y1):
                if op[y * ow + x0:y * ow + x1] != np[y * nw + x0:y * nw + x1]:
                    raise ValueError(f'{name}: original glyph pixels changed')
        advances = []
        for code in range(32, 127):
            if not nl[code] or nl[code] >= len(ng):
                raise ValueError(f'{name}: missing printable ASCII {code:#x}')
            x0, y0, x1, y1, a, b, c, _, sheet = ng[nl[code]]
            px, w, h = new_sheets[sheet]
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h and a + b + c > 0):
                raise ValueError(f'{name}: invalid ASCII glyph {code:#x}')
            indices = {px[y * w + x] for y in range(y0, y1) for x in range(x0, x1)}
            allowed = set(range(16)) if sheet in aa_sheet_indices else {13, 14, 15}
            if not indices <= allowed or (code != 32 and 15 not in indices):
                raise ValueError(f'{name}: invalid palette or missing ink at {code:#x}')
            advances.append(a + b + c)
        results[name] = {'ascii_glyphs': 95, 'original_glyphs_preserved': len(og),
                         'advance_min': min(advances), 'advance_max': max(advances),
                         'sheets': [[w, h] for _, w, h in new_sheets],
                         'antialiased_sheets': antialiased_sheets}
    return results


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cpk', type=Path, required=True)
    ap.add_argument('--fonts', type=Path, required=True, help='Build output containing font/')
    args = ap.parse_args()
    print(json.dumps(verify_fonts(args.cpk, args.fonts), indent=2))
