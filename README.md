# Twinkle☆Crusaders GoGo! (PSP) — English Translation

Fan translation project for **Twinkle☆Crusaders GoGo!** (PSP, `ULJS-00316`, `v1.01`).

> **Note:** This repository contains translation tools, glossaries, style documentation, and open-licensed font assets only. No copyrighted game files, ISOs, or decrypted binaries are included.

## Project Decisions & Conventions
- **Scope:** *Twinkle☆Crusaders GoGo!* (main disc only; *STARLIT BRAVE!!* bonus UMD deferred).
- **Honorifics & Name Order:** Original Japanese honorifics retained (`-san`, `-senpai`, `-sensei`, `-chan`, `-kun`, `-sama`, `Kaichou-han`); given-name-first order (*Synn Sakura*).
- **Translation Pipeline:** A machine-translated first draft using the GalTransl translation tool and curated dictionaries, followed by full human editing and QA.
- **Technical Approach:** MIPS32 proportional wrapping in `EBOOT.BIN`, with tight **Inrond-1.0** Latin glyphs added to the bitmap atlases. Original Japanese glyphs are preserved.

## Repository Structure
- `docs/` — [Project plan](docs/translation_project_plan.md)
- `glossary/` — [Character glossary](glossary/characters.md), [GalTransl character dictionary](glossary/gpt_dict_characters.txt), and VNDB source JSON
- `tools/recon/` — Read-only container inspection utilities (e.g., `cpk_toc.py`)
- `Inrond-1.0/` — Active Latin font package, licensed under SIL Open Font License 1.1
- `NewGoStyle-Ver1.000/` — Historical font package retained for older trials; not used by current builds
- `reports/` — Source baselines, current progress, and build validation results
- `tests/` — CPU, font, and ISO safety tests
- `gt_input/` — Locally extracted Japanese JSONs (not tracked); `gt_output/` — English drafts with matching filenames

## P2 Rendering Trial

The opening prologue draft, font generator, and EBOOT wrapping proof of concept
can be built into a test ISO. Run these commands from the repository root:

```powershell
python -m pip install -r tools/requirements.txt
python -m unittest discover -s tests -v
python tools/build_p2.py --tight-dialogue --out build/p2_next_trial
```

These commands resume the prepared local workspace. The builder expects the clean Japan v1.01 ISO in the repository root,
`work/iso_extract/GAMEINIT.CPK`, `work/eboot/EBOOT_decrypted.bin`, and the
existing `original/`, `metadata/`, and `gt_input/` extraction directories.
Translated JSONs go in `gt_output/` with the matching input filenames. Edit
`message` and translate any existing `name` field according to the glossary;
preserve row order, name-field presence, and control codes. Omitted translation
files retain their original Japanese text.
Choose a new output directory for each build; clean inputs are not modified.

For a fresh clone, supply your own dump matching [the source baseline](reports/source.md).
Extract `GAMEINIT.CPK` from the ISO path `PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK`
with an ISO archive tool, and place a matching decrypted EBOOT at the path
above. EBOOT decryption is not implemented in this repository. Create a
separate extraction workspace, then point the builder at it:

```powershell
python tools/pjadv/scenario.py extract --cpk work/iso_extract/GAMEINIT.CPK --out work/pjadv_workspace
python tools/build_p2.py --work work/pjadv_workspace --trans gt_output --tight-dialogue --out build/p2_fresh_trial
```

The current local trial, which is not included in git, is
`build/p2_inrond_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`.
It uses Inrond at a 14px dialogue raster size, weight 500, roundness 50, and
optical size 14. `--tight-dialogue` selects 90% horizontal scale, minimal
letter spacing, and 2px word spaces. Four-times supersampling and grayscale
edge shades replace the earlier binary rendering. Japanese glyphs and their
used palette colors remain unchanged.

The default font is `Inrond-1.0/fonts/variable/Inrond[ROND,opsz,wght].ttf`;
that package must be present locally. Use `--dialogue-size`,
`--dialogue-width-scale`, `--font-weight`, `--font-roundness`, and
`--font-optical-size` to tune it. `--no-antialias` enables legacy binary
rendering if needed. The Inrond trial still needs a PPSSPP visual check.
The patch hooks the main
typewriter parser; ruby (pronunciation annotations above text), other layout callers, punctuation wrapping, and memory
use still need work. See [the P2 report](reports/p2-proof-of-concept.md) for
measured results, limitations, and the PPSSPP launch command.

Unicorn is required for CPU execution tests. Those tests are skipped if it is
missing, and local EBOOT tests are skipped if the decrypted dump is unavailable.

## Credits & Licenses
- **Inrond-1.0:** Copyright 2026 The Inrond Project Authors and Copyright (c) 2016 The Inter Project Authors, licensed under SIL Open Font License 1.1. See `Inrond-1.0/OFL.txt`. Current builds copy this notice into the output directory.
- **NewGoStyle-Ver1.000** (`ニューゴスタイル`): Copyright (c) 2026 isMe (based on GenEi M Go v2.0 and Console Square Beta), licensed under **SIL Open Font License 1.1**. See `NewGoStyle-Ver1.000/OFL.txt` and `NewGoStyle-Ver1.000/THIRD_PARTY_NOTICES.txt`.
