# Translation State (`reports/translation-state.md`)

Updated: 2026-11-21

## Current Phase
- **P0 (Setup & Source Baseline):** Complete (`reports/source.md`)
- **P1 (Extraction & Rebuild Toolchain):** Complete & verified
- **Next Up — P2 (EBOOT Word Wrap & NewGoStyle Font PoC):** Ready to start

## Extraction Summary
| Item | Details |
|---|---|
| Engine & format | PJADV PSP (`PJADV_SF0001` scenario + `PJADV_TF0001` text pool) inside `GAMEINIT.CPK` (CRI CPK v7, zlib-chunked `.bin` containers) |
| Translation files | `gt_input/` (`931` JSON files, `97,274` ordered entries, `1,982,446` Japanese characters; `85,513` unique pool strings); place translations with matching filenames in `gt_output/` |
| Translation notes | Preserve `\n` line breaks and `\sNN`/`\SNN` emote codes verbatim; keep `"name"` fields aligned; keep original honorifics with given-name-first order per `glossary/characters.md` |
| Verification passed | Untouched JP round-trip (`textdata.bin`, `scenario.bin`, `GAMEINIT.CPK` all byte-identical); synthetic edit round-trip (`split_duplicates=7`) passed |
| Not yet verified | In-game text rendering, NewGoStyle font atlas replacement (`sulakyapi{8,12,18}`), EBOOT proportional word-wrap hook, `INSDIR/DATA1–3.DAT` override check, and battle/UI assets (`BATTLE.CPK`, `GRAPHIC.CPK`) |

## Recommended First Trial File
- `gt_input/0003_scene.json` (`PROLOGUE1001_01` — the opening prologue right after starting a new game).
