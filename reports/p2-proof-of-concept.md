# P2 prologue test build

Date: 2026-11-21

The user confirmed earlier PPSSPP boot/wrapping but rejected the NewGoStyle
appearance and requested Inrond-1.0 with tight spacing. Inrond is now the active
Latin font source. The latest trial is
`build/p2_inrond_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`.
It has not been checked in PPSSPP. No emulator was launched by the agent.

## Tight Inrond trial

Source: `Inrond-1.0/fonts/variable/Inrond[ROND,opsz,wght].ttf`.

All three Latin sets now use Inrond: 10px for `sulakyapi8`, 14px for dialogue
in `sulakyapi12`, and 21px for `sulakyapi18`. Variable axes are optical size
14, weight 500, and roundness 50. Axis order is read from the font, not inferred
from the filename.

Dialogue keeps one-pixel minimum gaps between ink bounds and 2px word spaces,
with a minimum 3px advance for thin letters. Horizontal scale is 90% rather
than the rejected 75% pixel compression. Glyphs are rasterized at four times
native resolution, condensed before downsampling, and quantized to grayscale
edge shades. The black outline remains one pixel thick.

The original sheets use only palette indices 13, 14, and 15. Indices 0–12
provide grayscale shades for the new glyphs; the palette entries used by
Japanese glyphs are unchanged. Original Japanese mappings, glyph rectangles,
pixel indices, and used palette colors were checked against the clean CPK.
The line geometry and wrapping EBOOT are unchanged.

| Check | Result |
|---|---|
| Font source | Inrond-1.0; no NewGoStyle Latin glyphs are used in this build |
| Prologue advances | 10,816px, versus 14,900px for regular NewGoStyle 13px and 9,434px for the rejected compressed trial |
| `Hourly Rate` advance | 68px |
| Visible height | New Latin `H`: 10px; preserved original Japanese `本`: 11px |
| Changed CPK members | Atlas and metrics for each of the three font sets: six members total |
| Readback | All 456 CPK members, ISO CPK replacement, and unchanged EBOOT checked; scenario payloads unchanged |
| Tests | 45 passed, including axis ranges/order, unused-palette protection, glyph completeness, and open counters in `O`, `o`, `0`, `8`, `B`, and `R` |
| License | Inrond's OFL notice, including the Inrond and Inter copyright statements, copied into the build directory |
| Runtime | New font appearance and grayscale palette handling remain unverified in PPSSPP |

The new trial is less compact than the rejected compressed font. It keeps
tight spacing but gives the letter shapes more room; it still uses about
27% less prologue width than the regular NewGoStyle 13px trial.

Results: `build/p2_inrond_tight_20261121/validation.json`.
Atlas-pixel preview: `build/p2_inrond_tight_20261121/font_preview.png`.
The tuning candidates are retained locally in `work/inrond_tuning/`.

Build from the prepared repository-root workspace into a new directory:

```powershell
python tools/build_p2.py --tight-dialogue --out build/p2_inrond_next_trial
```

The defaults reproduce the selected Inrond settings. Tune with
`--dialogue-size`, `--dialogue-width-scale`, `--font-weight`,
`--font-roundness`, or `--font-optical-size`. `--no-antialias` provides a
binary-raster fallback if the game's palette handling requires it. The tools
locate `OFL.txt` in the package ancestors because the TTF is nested under
`fonts/variable/`.

The NewGoStyle package and its earlier ISOs are preserved only as history.
The following sections describe those earlier builds, not the active preset.

## Historical tight NewGoStyle 13px trial

Reference ISO: `build/p2_font13_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`.

The glyphs retain their 13px raster height but are condensed to 75% ink width.
Column buckets take the maximum ink value so single-pixel strokes are not
discarded during shrinking. The outline is applied afterward and stays one
pixel thick.

Letter advances leave one pixel between ink bounds, with a minimum advance of
3px for the thinnest glyphs to accommodate the existing EBOOT byte-slot budget.
Outline columns may overlap; white letter strokes remain separated. This uses
signed C bearings down to -1, which the existing wrapping code already supports.
Spaces advance 2px. The text area, letter height, line spacing, and EBOOT are
unchanged. Japanese glyphs and the other font sizes are unchanged.

| Check | Result |
|---|---|
| Prologue advance total | 9,434px versus 14,900px in the regular-width 13px trial: 36.68% less width |
| `Hourly Rate` advance | 59px versus 94px in the regular-width 13px trial |
| Changed CPK members | Only `font/sulakyapi12/abc.w_abc` and `font/sulakyapi12/font12_3.tm2` |
| Readback | All 456 CPK members, ISO CPK replacement, and unchanged ISO EBOOT checked |
| Tests | 39 passed; includes stroke retention, height preservation, and minimum ink separation |
| Runtime | The user rejected this font's appearance and requested Inrond instead |

Results are in `build/p2_font13_tight_20261121/validation.json`.
The atlas-pixel comparison is
`build/p2_font13_tight_20261121/tight_font_comparison.png`.
The earlier build is preserved for comparison. Current build defaults use
Inrond; use the recipe above for new trials.

## Historical regular NewGoStyle 13px trial

Regular-width reference ISO: `build/p2_font13_20261121/Twinkle_Crusaders_GoGo_P2.iso`.

Latin dialogue glyphs were reduced from 15px to 13px. The 19px cell height,
line spacing, visible text area, and wrapping code are unchanged. Spaces were
reduced from 4px to 3px, and glyphs are centered within the existing line cells.

Only `font/sulakyapi12/abc.w_abc` and `font/sulakyapi12/font12_3.tm2` changed
in the CPK. The script payloads, working EBOOT, other font sizes, and non-ASCII
glyphs were preserved. All 456 CPK members and the ISO CPK/EBOOT readbacks
were checked. The font validator passed, and 35 tests passed.

Across all 34 prologue rows, excluding the emote escape, advances total
14,900px versus 16,982px in the 15px trial: 12.26% less horizontal space.
That suggests roughly 14% more text per line for similar prose; actual wrapping
also depends on word lengths. A subsequent in-game screenshot showed this
font rendering and wrapping; full page/emote checks are still pending.
Detailed results are in `build/p2_font13_20261121/validation.json`.

### Original font comparison

The user requested a size close to the Japanese original, with the original
font preferred if it fits more text. The stock font was compared using the
same proportional advance metrics that the wrapping patch reads.

| Font | Visible ink height of `H` | Advance of `Hourly Rate` |
|---|---|---|
| Original `sulakyapi12` Latin | 9px | 123px |
| NewGoStyle, 15px raster size | 12px | 108px |
| NewGoStyle, 13px raster size | 10px | 94px |

The original Japanese `本` has 11px of visible ink. The 13px raster setting
therefore gives a Latin capital height close to the Japanese glyph height;
raster size is not the same as visible ink height.

For a comparison restricted to prologue characters mapped by the original
font, advances total 20,401px with the original font and 14,739px with the
13px font. The original uses more space, so the condition for reverting to it
was not met. Its Latin glyphs are narrow but have substantial spacing, and
17 printable ASCII characters lack mappings, including the double quotes
and hyphens used in this draft. The 13px NewGoStyle font remains the trial
choice; the other font sizes and Japanese glyphs are unchanged.

The diagnostic atlas-pixel comparison and measurements are in
`build/p2_font13_20261121/original_font_comparison.png` and
`build/p2_font13_20261121/original_font_comparison.json`.

This trial used the earlier NewGoStyle settings. Current generation defaults
are Inrond; the reference ISO remains available for comparison.

## Original 15px build results

| Check | Result |
|---|---|
| Source version | Clean Japan v1.01 ISO, extracted CPK, and decrypted EBOOT matched [the recorded source identities](source.md) |
| Translation | `gt_output/0003_scene.json`: 34 English draft rows; editorial review pending |
| Script readback | All 931 scene JSONs and 97,274 ordered entries matched the expected original or translated rows after re-extraction |
| Pool and controls | 85,514 pool strings; one shared original string was split to preserve its untranslated occurrences; zero control-code warnings |
| CPK readback | All 456 members matched their expected payloads, including unchanged members |
| Fonts | 95 printable ASCII glyphs per size; original glyph rectangles and non-ASCII mappings preserved; TIM2 and metrics serialization checked |
| EBOOT | 1,076-byte payload in a second executable `PT_LOAD` at `0x08A76000`; original segment bounds preserved |
| ISO | `PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK` and `PSP_GAME/SYSDIR/EBOOT.BIN` read back correctly; output size 1,819,772,928 bytes |
| Build time | 37.58 seconds on this machine |
| Tests | 31 passed with `python -m unittest discover -s tests -v` |

Detailed build results are in `build/p2_prologue_20261121/validation.json`.
The build directory includes the font license and third-party notices.
Do not distribute the ISO or decrypted EBOOT.

## Renderer implementation

`tools/eboot/patch_eboot.py` checks the clean EBOOT's identity and expected
instructions before patching. It appends an executable segment after the
original memory range instead of replacing live code or BSS.

The main typewriter parser's ASCII calls scan ahead at spaces, hyphens, and
emote boundaries. Widths come from the loaded font's `abc.w_abc` records,
including signed A/B/C bearings. The patch uses the engine's newline helper
when a word will not fit. Words wider than the whole box fall back to
character wrapping. Explicit breaks and formatting remain with the original
parser.

Both ASCII and full-width emission position glyphs using the accumulated
advance of the current line. Japanese characters and emotes retain the
nominal full-cell advance. Byte slots store text and sprite references; the
pixel budget limits the visible line width. Byte-slot capacity is multiplied by four through
the original allocation arithmetic; the pixel budget stays unchanged. The
patch recomputes advance from the original line buffer rather than storing
extra mutable state.

CPU tests execute the generated payload and the real patched parser,
emitters, newline handler, positioning function, and context initializer.
The local parser tests substitute memory-copy and sprite allocation/release
services; they do not test GPU rendering or the PSP loader.

## Font correction

The old assets in `work/font_build/` were preserved. Validation found that
the large-font backtick had no ink because its negative bearing placed it
outside the canvas. `tools/font/build_font.py` now renders onto a larger
canvas and fits the complete ink and outline into each cell. Tall glyphs in
the smallest font are compressed vertically when necessary.

The corrected assets are in `build/p2_prologue_20261121/fonts/font/`:

| Font | Atlas dimensions | ASCII advance range |
|---|---|---|
| `sulakyapi8` | 256×256 | 3–11 px |
| `sulakyapi12` | Four 512×512 sheets; ASCII on sheet 3 | 4–16 px |
| `sulakyapi18` | 512×256 | 5–22 px |

## Corrections to earlier notes

- Script members are under `scenario/` in `GAMEINIT.CPK`, not `pjadv/`.
- `abc.w_abc` has version 5 and a Shift-JIS-indexed lookup table, not a
  UCS-2-indexed table. The runtime byte-swaps two-byte Shift-JIS before lookup.
- `0x08949940` contains live instructions and cannot be used as an empty cave.
- `0x0887D7A0` is part of escape dispatch. The callable newline helper is
  `0x0887C400`.
- The documented command examples have been corrected in `HANDOFF.md`.

## Remaining runtime checks and limitations

P2 remains in progress. This build is a rendering trial, not a release patch.

1. Earlier PPSSPP boot and wrapping were confirmed by the user. Check the
   Inrond font and grayscale shades visually. PSP hardware loader compatibility
   has not been checked.
2. Start a new game and play `PROLOGUE1001_01`, verify all 34 lines, and check glyph spacing,
   wrapping, page endings, and the `\S10` emote. Do not count a returned
   parser status as evidence that all text appeared on screen.
3. Check backlog, choices, centered text, ruby, and other direct-emission
   callers. Word wrapping only hooks the main parser; other layout routines
   still use byte slots and may be affected by the expanded capacity.
4. Implement pixel-based Japanese punctuation handling before release. The original
   kinsoku checks (rules against closing punctuation at the start of a line) still use the expanded slot limit instead of the pixel
   limit, so closing punctuation may wrap incorrectly in this trial.
5. Test words containing inline controls. Lookahead stops at escape sequences;
   it does not yet measure an entire word across arbitrary formatting codes.
6. Measure memory use during skipping and fast-forward. Per-context line
   buffers have four times as many slots. The global sprite pool is unchanged.
7. Check the expanded `sulakyapi8`/`sulakyapi18` atlases in the renderer. The
   screens that use these font sizes have not yet been mapped.
8. Test Data Install with separate disposable PPSSPP Memory Stick directories.
   One should contain no installed game data; install data from the clean
   Japanese disc in the other, then test the patched disc there. This checks
   whether installed files override the patched CPK without deleting existing
   user saves or installed data. Back up saves before changing profiles.

To launch the existing local build in PowerShell (substitute your emulator
and repository paths if they differ):

```powershell
& 'D:\Video_Game\Emulator\PSP\PPSSPP 1.20\ppsspp\PPSSPPWindows64.exe' 'D:\Documents\Twinkle_Crusaders_GoGo\build\p2_inrond_tight_20261121\Twinkle_Crusaders_GoGo_P2.iso'
```

To rebuild after editing, run from the repository root and choose a new output directory:

```powershell
python tools/build_p2.py --tight-dialogue --out build/p2_next_trial
```

The builder rejects existing output directories, checks source identity,
generates or validates fonts, rebuilds and re-extracts scripts, verifies CPK
members, and patches a separate ISO copy. It does not launch the emulator.

## Legibility and leading corrections (2026-11-21)

In-game dialogue exposed two rendering problems that the atlas tests could not see.

**Thin strokes were painted as gray antialias edges.** The rasterizer promoted
ink to white only at coverage >= 247/255, so a one-pixel stem (capital `I`,
apostrophe, quotes) survived the downscale as a gray shade and read as missing
or as a pipe. The core is now white at coverage >= 128/255 and grays are used
only on the outer edge, so every printable ASCII glyph (0x21..0x7E) contains
white ink. ASCII `I` additionally gets one-pixel serifs so it cannot be mistaken
for `|`.

**The third line touched the window's bottom edge.** The payload now tightens
the leading from the positioning hook already used for the x correction:
`y -= 4 * line + 2`, and the original y is kept when that would go negative so
non-dialogue windows cannot be pushed offscreen. The lift is controlled by
`LINE_LIFT` and `BLOCK_LIFT` in `tools/eboot/patch_eboot.py`; the parser tests
now assert the lifted coordinates.

**Glyph count must stay at the original size.** Appending a record per ASCII
code (2956 -> 3034) crashed the game with the same null-style signature as the
leading experiment, so the engine keeps a fixed-size glyph structure. ASCII now
updates the record its code already references; only codes that had no record at
all (like `"`) still append, which is what the shipping Inrond trial already did
(2956 records).

**Ink is raised 4px inside the 19px cell (`ink_lift`).** The engine's line pitch
is fixed at roughly 17.5px, so the third message line otherwise sits on the
window's bottom border. Lifting the ink is a pixel-placement change only; it
cannot corrupt engine state. Ink tops stay at row 1 or lower, so the 1px outline
still fits inside the cell.

**ASCII glyphs must go into fresh records, not reused slots.** The builder used
to write each ASCII glyph into the record its code already referenced
(`glyphs[lut[code]] = new_rec`). In game, punctuation mapped to those low
records (`!` #2, `'` #4, `,` #7) rendered blank, while codes that had no record
and were appended (`"` #2939) rendered correctly. The low records are the
half-width ASCII slots the game rebuilds at boot, which discarded the edits.
Every ASCII code now gets a newly appended record and a repointed LUT entry;
the original records are left untouched, so Japanese and half-width lookups are
unchanged. `sulakyapi12` grows from 2956 to 3034 records.

**Leading lift was attempted and reverted.** Lifting each line by
`4 px * line + 2 px` from the position hook made the game crash
(`Invalid Memory Access`, read at `0x6c`) in PPSSPP. The reverted payload is
byte-identical to the build that boots, so the vertical fit is handled by the
364px x 3-line translation budget instead.

**Backlog is a separate renderer.** The backlog corrupts after translation
(each row drawn twice, characters shifted by one glyph code: `W` renders as
`V`, `I` as `H`, plus mid-word gaps). Neither emitter's address appears anywhere
as a materialized immediate, so both are reached through one common dispatch
entry; the backlog therefore does not use these emitters at all. It must be
reverse-engineered and patched separately: it needs the same pixel wrapping and
the same slot-geometry assumptions as the message window.
