# Translation State (`reports/translation-state.md`)

Updated: 2026-11-21

## Current Phase
- **P0 (Setup & Source Baseline):** Complete (`reports/source.md`)
- **P1 (Extraction & Rebuild Toolchain):** Complete & verified
- **P2 (EBOOT Word Wrap & Inrond Font PoC):** User confirmed earlier boot/wrapping but rejected NewGoStyle. Tight Inrond fonts now replace all three Latin sets; the new trial is ready for visual testing. Broader runtime checks remain pending. See [P2 report](p2-proof-of-concept.md).
- **P3:** 6 scenes translated (34-row prologue `0003` + batch 1: the 526-row tutorial `0002` and opening "発足!! 流星生徒会" scenes `0001`/`0004`/`0005`/`0006`); glossaries rebuilt (`glossary/characters.md`, `glossary/terms.md`) and P3 key guardrails active in `tools/pjadv/scenario.py`. Batch-1 test build verified: `build/gt_batch1_test/` packs with 77 split pool duplicates, zero warnings, and readback re-extraction returns the English text. Scene titles (e.g. `発足!! 流星生徒会`) and battle stage labels (e.g. `チュートリアル１`) are intentionally left verbatim pending `GRAPHIC.CPK`/`stage.bbn` sync.
- **P4 (Non-Script & EBOOT Audit):** Completed asset/binary scan ([P4 asset audit](p4-asset-audit.md)): 545 UI textures triaged (**176–177** need localization), 73 EBOOT JP strings exported to [eboot_strings.json](../glossary/eboot_strings.json), and `Battle/*.bbn` + `Grp_Title/*.txt` verified as internal keys. P4 repacking/patching not yet implemented.

## Extraction Summary
| Item | Details |
|---|---|
| Engine & format | PJADV PSP (`PJADV_SF0001` scenario + `PJADV_TF0001` text pool) inside `GAMEINIT.CPK` (CRI CPK v7, zlib-chunked `.bin` containers) |
| Translation files | `gt_input/` (`931` JSON files, `97,274` ordered entries, `1,982,446` Japanese characters; `85,513` unique pool strings); place translations with matching filenames in `gt_output/` |
| Translation notes | Edit `message` and translate any existing `name` according to `glossary/characters.md`; preserve row order and name-field presence. Do not edit internal `label` (`stage.bbn`) or `scene_title` (`Grp_Title/%s.txt`) lookup keys (`tools/pjadv/scenario.py` enforces `allow_label_edits=False`, `allow_scene_title_edits=False` by default). Keep `\n` and `\sNN`/`\SNN` verbatim, original honorifics, and given-name-first order. Omitted translation files retain their original Japanese text. |
| Verification passed | Untouched JP round-trip (`textdata.bin`, `scenario.bin`, `GAMEINIT.CPK` all byte-identical); synthetic edits split seven shared pool strings into separate variants and passed pointer-remapping checks |
| Original P2 baseline verification | The original prologue build passed 31 tests, re-extracted 931 scenes and 97,274 matching entries, and read back all CPK/ISO replacements. Only 34 rows were translated; later font-only trials preserve those script payloads. |
| Historical smaller-font trial | `build/p2_font13_20261121/Twinkle_Crusaders_GoGo_P2.iso`: NewGoStyle 13px, unchanged 19px line height, about 12% less prologue width. 35 tests passed; two font members changed; EBOOT/scripts preserved. |
| Historical original font comparison | With proportional advances, `Hourly Rate` took 123px in the original font versus 94px at NewGoStyle 13px. The original had unmapped quotes/hyphens and was not selected; NewGoStyle was subsequently replaced by Inrond. |
| Historical tight-font trial | `build/p2_font13_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`: NewGoStyle at 75% width, tight spacing, 2px spaces. Prologue advances fell to 9,434px. 39 tests/readbacks passed; the user rejected its appearance. |
| Current Inrond trial | `build/p3_batch1_inrond/Twinkle_Crusaders_GoGo_P2.iso`: 14px dialogue, weight 500, roundness 50, optical size 14, 90% horizontal scale, tight spacing, and grayscale edges, now carrying the 908-row batch-1 translation. 53 tests and all 456 CPK readbacks passed; 11 CPK members changed (9 font assets + both scenario pools) plus the EBOOT. |
| Not yet verified | Inrond visual rendering and palette behavior in PPSSPP, full prologue/page-end/emote checks, PSP hardware loader compatibility, ruby/backlog/choices/centered text, Japanese punctuation wrapping, memory pressure, whether installed `INSDIR/DATA1–3.DAT` data overrides the patched disc files, and P4 runtime localization of battle/UI textures & EBOOT strings (audited in `reports/p4-asset-audit.md`) |
| Message-window budget | Three lines at 364px (`52 ASCII glyphs × 7px half-cell`). `tools/pjadv/check_widths.py` measures each translated row with the built `sulakyapi12` metrics and simulates the EBOOT's greedy word wrap; `tools/build_p2.py` now fails on any row that would need a fourth line. An earlier CPK-only ISO rendered the original wide font with no wrapping hook and clipped rows mid-word — the font and EBOOT must be patched together. |

## Recommended First Trial File
- `gt_input/0003_scene.json` (`PROLOGUE1001_01` — the opening prologue right after starting a new game).
- English draft: `gt_output/0003_scene.json` (34 entries, `\S10` preserved).
- Test ISO: `build/p2_inrond_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`. The user will run PPSSPP manually; earlier trials are preserved.
