# Twinkle☆Crusaders GoGo! (PSP): English Translation Project Plan

**Target:** `Twinkle Crusaders GoGo! (Japan) (v1.01).iso`, 1.81 GB (this disc only; *STARLIT BRAVE!!* bonus UMD is out of scope for now). Developer: Lillian. Publisher: ASCII Media Works. Released 2010-09-30.
**Deliverable:** an xdelta patch that turns the Japanese ISO into a fully English ISO, playable on PPSSPP and on real PSP hardware running custom firmware.
**Existing work:** no public English patch exists for any version. A Traditional Chinese patch exists for the PC original ([r56208](https://vndb.org/r56208)).

## 1. Technical recon findings

| Area | Finding |
|---|---|
| Engine | **PJADV**, the same family as the PC original (`PJADV_SF0001` scenario bytecode, `PJADV_TF0001` text pool, `PJADV_FL0001` filename table). |
| Containers | CRI **CPK** v7, unencrypted `@UTF` tables. Story scripts live in `USRDIR/DISK1/GAMEINIT.CPK › scenario/`. |
| Script files | `textdata.bin`, `scenario.bin`, `filename.bin`, `GraphicARC.bin`, `AnmARC.bin`. Each `.bin` is a custom chunked container (`u32 offset + 24-byte name`), pointing at 8-byte headers (`u32 BE comp_size`, `u32 BE 0x7800`) + **zlib streams inflating to 30,720 bytes** each. |
| Text pool | 85,513 unique cp932 (Shift-JIS) strings separated by `\0\0`. 80 are `###` internal labels (do not translate). That leaves **~85,433 translatable strings (~1.91 million JP chars)**, including ~72,098 quoted lines. |
| Control codes | `\n` (line break) and `\sNN` / `\SNN` (icon/emote codes like `\s04`; 13 variants, ~1,800 uses). Speaker names are separate pool strings referenced by bytecode. |
| Decrypted EBOOT | Supplied locally (not committed to git): 1,527,040 bytes, static MIPS32 LE `ET_EXEC` ELF (`entry 0x089474e4`, `.text 0x08804000–0x08949994`, `.data 0x0894ac3c–0x08978630`). Contains internal asset names confirming `LOLOTTE`, `PAQY`, and `MACAROON`. |
| Font system | Three CRILAYLA-compressed bitmap font sets (`font/sulakyapi{8,12,18}/`): TIM2 (`.tm2`) 4bpp/16-color texture atlases + `abc.w_abc` width tables (`cnt` = 60,065 / 38,902 / 38,855 entries; line heights 19 / 12 / 26 px) + `JIS2UCS.BIN` (131,072-byte Shift-JIS → UCS-2 lookup). |
| Target font | **[NewGoStyle-Ver1.000](../NewGoStyle-Ver1.000)** (Regular, Medium, Bold, Heavy, Black `.ttf`), SIL Open Font License 1.1. Combines GenEi M Go v2.0 Japanese glyphs with **Console Square Beta** alphanumerics and adjusted metrics for high readability. |
| Other text sources | `BATTLE.CPK` (battle UI, `EXName`, `.bbn` battle voice/data), `GRAPHIC.CPK` and `SystemZip/*.zip` (menus, chapter cards, text-bearing images), `EBOOT` `.data`/`.rodata` (system menus), and `OP1/OP2.PMF`. |
| Install data risk | `PSP_GAME/INSDIR/DATA1–3.DAT` (~100 MB, PGD-encrypted). Must be tested early in P2 to confirm whether installed Memory Stick data overrides patched CPK files. |

## 2. Locked style & naming decisions

1. **Honorifics & order:** Keep original Japanese honorifics (`-san`, `-senpai`, `-sensei`, `-chan`, `-kun`, `-sama`, and Akane's `Kaichou-han`); use given-name-first order (*Synn Sakura*).
2. **Glossary spellings (informed by online consensus + in-game assets):**
   - **Synn Sakura** (`ＳＡＫＵＲＡＳＹＮＮ` in-script; VNDB/Fandom/TV Tropes consensus).
   - **Lolotte Rosenkreuz** (EBOOT confirms `LOLOTTE`; Wikipedia/Fandom/Twinkle Star Knights consensus prefers `Rosenkreuz` over VNDB's *Rozenkrutz*).
   - **Macaron** (merchandise & community consensus prefer `Macaron`, overriding internal `MACAROON` asset IDs / VNDB).
   - **Paqy** (confirmed by both official merchandise and EBOOT `BE_AS_PAQY`).
   - **Demon Lord** for general noun/title uses of 魔王; **Maou-sama** when addressed directly with the honorific (matching voice acting + fan consensus).
   - **Re-Crea** for リ・クリエ (matches online lore consensus).
   - Full cast & GalTransl dictionary are in [characters.md](../glossary/characters.md) and [gpt_dict_characters.txt](../glossary/gpt_dict_characters.txt).
3. **Translation pipeline:** GalTransl MTL first draft (using `gpt_dict_characters.txt` + style guide) followed by **full human editing and QA**.
4. **Scope:** This disc (`Twinkle Crusaders GoGo!` Japan v1.01) only for now.
5. **Word wrapping & font:** Implement proportional word-wrapping **directly in the EBOOT text renderer** (Option b), paired with bitmap font atlases (`sulakyapi{8,12,18}`) regenerated from **NewGoStyle-Ver1.000**.

## 3. Workstreams and phases

### P0: Setup (about 1 day)
- Record the SHA-256 of `Twinkle Crusaders GoGo! (Japan) (v1.01).iso` in `reports/source.md`.
- Maintain clean repo layout (`tools/`, `glossary/`, `style/`, `gt_output/`, `docs/`), keeping copyrighted binaries ignored in `.gitignore`.
- Keep the decrypted EBOOT locally under `work/eboot/` as the clean baseline for MIPS disassembly and binary patching.

### P1: Extraction & rebuild toolchain (Python, 1–2 weeks)
1. **CPK reader/writer:** list, unpack, and rebuild `GAMEINIT.CPK` (and `BATTLE.CPK` / `GRAPHIC.CPK`), preserving 2048-byte alignment, `@UTF` TOC, and ETOC. Reuse [cpk_toc.py](../tools/recon/cpk_toc.py).
2. **CRILAYLA & chunk container codecs:** lossless CRILAYLA compressor/decompressor (for `font/` and `ARC` bins) + 30,720-byte zlib chunk splitter/joiner for `textdata.bin` and `scenario.bin`.
3. **PJADV scenario parser:** decode `PJADV_SF0001` opcodes, locate all pointers into `textdata.bin` (dialogue, choices, speaker labels, scene titles), and export ordered GalTransl JSON per scene (`{"name","message"}`) with `metadata/` sidecars.
4. **Rebuilder:** encode translated strings, deduplicate/expand pool entries when identical JP strings need different English translations, patch all bytecode pointers, and re-chunk.
5. **Gate:** round-tripping the untouched JP script must produce byte-identical `textdata.bin` and `scenario.bin`.

### P2: EBOOT word wrap & NewGoStyle font PoC (2–3 weeks, critical technical milestone)
1. **Reverse-engineer the text renderer** in the decrypted EBOOT (via `rizin` / Ghidra): trace `JIS2UCS.BIN`, `abc.w_abc`, `font*.tm2` loading, glyph advance calculation, and line-break logic (`\n` and box-width overflow).
2. **Generate NewGoStyle PSP font assets:** rasterize **NewGoStyle-Medium** / **Regular** (and **Bold** if needed) into `sulakyapi8`, `sulakyapi12`, and `sulakyapi18` TIM2 atlases + `abc.w_abc` proportional width tables (plus `JIS2UCS.BIN` / ASCII mapping updates if needed), then CRILAYLA-compress them.
3. **Implement EBOOT word wrapping:** inject a MIPS32 code cave (or replace the character-break routine) to read proportional widths from `abc.w_abc`, scan ahead to the next space/hyphen/`\n`, break cleanly on word boundaries, and respect `\n` and `\sNN` emote codes.
4. **Verify INSDIR install data:** test patched ISO in PPSSPP with Data Install enabled and disabled to confirm whether `INSDIR/DATA1–3.DAT` overrides `GAMEINIT.CPK`, and disable/patch install logic if needed.
5. **Gate:** boot `PROLOGUE1001` in PPSSPP with long English test lines, `\sNN` codes, choices, and backlog—confirm crisp NewGoStyle rendering, accurate proportional spacing, and zero mid-word breaks.

### P3: Translation — GalTransl MTL + full human editing (the long phase)
- **Step 1 — Style guide & terms:** finish `style/style_guide.md` and `glossary/terms.md`.
- **Step 2 — GalTransl batch MTL pass:** run `gt_input/` (~85.4k strings, ~1.91M JP chars) through GalTransl using `glossary/gpt_dict_characters.txt` and `terms` dictionary.
- **Step 3 — Human editing & localization pass:** edit route-by-route into `gt_output/` (Prologue & common route → Heroine routes → Sub-heroine episodes & scene titles → Battle dialogue & tutorials).
- **Step 4 — Automated QA:** validate `\sNN` / `\n` codes, glossary consistency, no leftover Japanese, encoding validity, and line-count / page-overflow checks.

### P4: Non-script assets (in parallel with P3)
- **Graphics (`GRAPHIC.CPK`, `SystemZip/*.zip`, `BATTLE.CPK`):** extract TIM2/GIM images containing Japanese text, redraw in English, and reinsert.
- **EBOOT strings:** translate hardcoded system/save/error/menu text in the decrypted EBOOT.
- **Optional:** subtitle `OP1.PMF` / `OP2.PMF` and translate trophy/extras UI.

### P5: Build, QA & release
- **One-command build:** `gt_output/` + edited graphics + patched `EBOOT.BIN` + NewGoStyle font → CPK rebuild → ISO rebuild → `xdelta3` patch.
- **Playtesting:** full-route QA on PPSSPP and real PSP hardware (CFW).
- **Release package & licensing:** distribute the `.xdelta` patch + README + credits. Because NewGoStyle bitmap derivatives are bundled under **SIL OFL 1.1**, include `OFL.txt` and `THIRD_PARTY_NOTICES.txt` in the release archive (and do not use reserved font names `源暎`, `GenEi`, or `Source` as primary font names). **Never distribute the ISO.**

## 4. Key risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| EBOOT MIPS hook complexity (tight code space, multiple text renderers) | High | Analyze all `abc.w_abc` callers in decrypted EBOOT during P2; place hook in unused/BSS-extended region or spare segment space and test all 3 font sizes (`8/12/18`). |
| Modified text pool + NewGoStyle TIM2 atlases exceed `GAMEINIT.CPK` / UMD LBA layout | Medium | Rebuild CPK/ISO with proper TOC & LBA updates; verify on real PSP hardware as well as PPSSPP. |
| INSDIR `DATA1–3.DAT` PGD install overrides patched files | Medium | Test early in P2; patch EBOOT to ignore or disable Data Install if it reads `DATA1–3.DAT` over UMD CPKs. |
| MTL artifacts slipping into final script (~1.91M JP chars) | High (quality) | Route-by-route human editing milestones, strict GalTransl dictionaries, and automated QA scripts before each route sign-off. |
| `sulakyapi12` 4bpp TIM2 palette/swizzle or `w_abc` format quirks | Medium | Reverse-engineer exact `w_abc` entry layout from decrypted EBOOT before building the NewGoStyle atlas generator. |
