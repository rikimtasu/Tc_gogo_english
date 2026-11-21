# Translation State (`reports/translation-state.md`)

Updated: 2026-11-21

## Current Phase
- **P0 (Setup & Source Baseline):** Complete (`reports/source.md`)
- **P1 (Extraction & Rebuild Toolchain):** Complete & verified
- **P2 (EBOOT Word Wrap & Inrond Font PoC):** User confirmed earlier boot/wrapping but rejected NewGoStyle. Tight Inrond fonts now replace all three Latin sets; the new trial is ready for visual testing. Broader runtime checks remain pending. See [P2 report](p2-proof-of-concept.md).
- **P3:** One 34-row opening prologue draft in `gt_output/0003_scene.json`; full translation and editorial review pending. Glossaries rebuilt (`glossary/characters.md`, `glossary/terms.md`) and P3 key guardrails active in `tools/pjadv/scenario.py`.
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
| Current Inrond trial | `build/p2_inrond_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`: 14px dialogue, weight 500, roundness 50, optical size 14, 90% horizontal scale, tight spacing, and grayscale edges. 45 tests and all 456 CPK readbacks passed. Six font members changed; EBOOT/scripts/Japanese glyphs and their used palette colors are unchanged. |
| Not yet verified | Inrond visual rendering and palette behavior in PPSSPP, full prologue/page-end/emote checks, PSP hardware loader compatibility, ruby/backlog/choices/centered text, Japanese punctuation wrapping, memory pressure, whether installed `INSDIR/DATA1–3.DAT` data overrides the patched disc files, and P4 runtime localization of battle/UI textures & EBOOT strings (audited in `reports/p4-asset-audit.md`) |

## Recommended First Trial File
- `gt_input/0003_scene.json` (`PROLOGUE1001_01` — the opening prologue right after starting a new game).
- English draft: `gt_output/0003_scene.json` (34 entries, `\S10` preserved).
- Test ISO: `build/p2_inrond_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`. The user will run PPSSPP manually; earlier trials are preserved.
