# Twinkle Crusaders GoGo! (PSP) — English Translation Project Handoff

**Target Game**: *Twinkle Crusaders GoGo!* (*ティンクル☆くるせいだーす GoGo!*)  
**Platform**: Sony PlayStation Portable (PSP)  
**Product Code**: `ULJS-00316` (v1.01)  
**Git Repository**: [https://github.com/rikimtasu/Tc_gogo_english.git](https://github.com/rikimtasu/Tc_gogo_english.git) (Branch: `main`)  
**Last Updated**: 2026-11-22  

---

## 1. Executive Summary & Source Baseline

The intended deliverable is a complete English xdelta3 patch for the PSP visual novel *Twinkle Crusaders GoGo!* (v1.01). Currently, all 931 scenario scripts (`97,274` rows in `gt_output/`), a **Barlow Semi Condensed Medium** dialogue font pipeline, **`1.5x` EBOOT slot-expansion + save-load/backlog fixes + `0x0894552c` `™`-inserter fix**, all **73 EBOOT system strings** ([`glossary/eboot_strings.json`](file:///d:/Documents/Twinkle_Crusaders_GoGo/glossary/eboot_strings.json)), and **176 localized UI & Title Screen logo textures** across `GAMEINIT.CPK` (`14`), `BATTLE.CPK` (`145`), and `GRAPHIC.CPK` (`17`) have been merged into `build/master_v5/Twinkle_Crusaders_GoGo_EN.iso` and `build/master_v5/Twinkle_Crusaders_GoGo_EN.xdelta` (generated and round-trip verified with `xdelta3` v3.2.2), with `14/14` consolidated unit tests passing (`0.22s`). Scope is restricted to Disc 1 (*GoGo!* main game); the *STARLIT BRAVE!!* bonus UMD is deferred.

### Cryptographic Baseline Hashes
All patches and re-imports must strictly target and match the following clean baseline dumps (see `reports/source.md`):

| File | Size (bytes) | SHA-256 | Purpose / Status |
|---|---:|---|---|
| `Twinkle Crusaders GoGo! (Japan) (v1.01).iso` | 1,808,564,224 | `2025c8df4e642a65ae27da422eefb81c34f71028c425e848e5124d34a1669f7e` | Clean JP v1.01 source ISO (Read-only reference) |
| `work/eboot/EBOOT_decrypted.bin` | 1,527,040 | `96f2556cad518943ab0203f2ffe7d471b92e29fae4f8a7fab62a577355ca3de8` | Decrypted ELF32 MIPS32 LE executable (from `ULJS00316_EBOOT.BIN`) |
| `PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK` | 9,659,944 | `20387f20f9972667f9c2e28fd5d628832c6cdb20f3ac9be2550b06fc496f27b8` | Baseline scenario, font, and UI container |
| `PSP_GAME/PARAM.SFO` | 560 | `91af0700ac25313e2c0ca631403d9f908a62fcc20d5dcf08942e9ca13c6bf902` | Baseline PSP disc parameters (`DISC_ID: ULJS00316`) |

---

## 2. Project Policies & Locked Decisions

1. **Honorifics**: Keep original Japanese honorifics intact (`-san`, `-senpai`, `-sensei`, `-chan`, `-kun`, `-sama`, `Kaichou-han`).
2. **Name Order**: Given-name-first order across all dialogue, narration, and system text (e.g., *Synn Sakura*, *Lolotte Rosenkreuz*, *Nanaka Shisendo*).
3. **Character Glossary**: Locked in [`glossary/characters.md`](file:///d:/Documents/Twinkle_Crusaders_GoGo/glossary/characters.md) and [`glossary/gpt_dict_characters.txt`](file:///d:/Documents/Twinkle_Crusaders_GoGo/glossary/gpt_dict_characters.txt):
   - `Synn Sakura` (in-script: `ＳＡＫＵＲＡＳＹＮＮ`)
   - `Lolotte Rosenkreuz` (EBOOT asset string: `LOLOTTE`; German root `Rosenkreuz`)
   - `Macaron` (merchandise and community consensus over EBOOT `MACAROON`)
   - `Paqy` (EBOOT asset ID `BE_AS_PAQY` and merchandise over `Packy`)
   - `Demon Lord` for general noun/title; `Maou-sama` when used as direct address
   - `Re-Crea` for `リ・クリエ`
4. **Translation Workflow**: Machine translation (MTL) draft for initial throughput, followed by human editorial review, consistency passes, and in-game proofreading.
5. **Word Wrapping Strategy**: Proportional word wrapping injected directly into the EBOOT MIPS text renderer. No pre-wrapping at extraction time.
6. **Font Choice**: `BarlowSemiCondensed/BarlowSemiCondensed-Medium.ttf` (SIL Open Font License 1.1; license `BarlowSemiCondensed/OFL.txt`) replaces `Inrond-1.0` and NewGoStyle for all Latin glyphs in `sulakyapi{8,12,18}`. Original Japanese glyphs are preserved. `Inrond-1.0/` and NewGoStyle files/earlier builds remain only for historical comparison and variable-axis tests.
   The active dialogue preset is 14px raster size, `100%` horizontal scale (naturally semi-condensed), tight spacing (`c = -1`, 1px minimum gap between ink bounds), and `3px` word spaces. Capital `I` uses 4x supersampled rounded serifs; supersampled grayscale edges apply a `< 36` dust cutoff and `gamma = 0.72` boost across all 13 previously unused palette entries (`0..12`, with `247+ -> 15`) without changing Japanese glyph colors. Uniform font-wide `baseline_row` alignment (`8 / 11 / 19` for `sulakyapi8 / 12 / 18`) replaces the earlier `ink_lift = 4` clamp. Visible `H` is 10px versus 11px for original Japanese `本`; `"Hourly Rate"` advance is 64px. Runtime visual verification of the Barlow build in PPSSPP is pending.

---

## 3. Reverse Engineering Findings & Formats

### 3.1 Container Hierarchy
```
ISO9660 (.iso)
 └── PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK (CRI CPK v7)
      ├── font/sulakyapi12/
       │    ├── abc.w_abc      (Glyph metrics & Shift-JIS mapping)
      │    └── font12_*.tm2   (CRILAYLA compressed 4bpp indexed TIM2 sheets)
       └── scenario/
           ├── textdata.bin   (30,720-byte zlib chunk container -> PJADV_TF0001)
           ├── scenario.bin   (30,720-byte zlib chunk container -> PJADV_SF0001)
           └── filename.bin   (30,720-byte zlib chunk container -> file index)
```

### 3.2 PJADV Scenario Engine
- **Bytecode format**: `PJADV_SF0001`.
- **Text Pool format**: `PJADV_TF0001` (85,513 unique string entries).
- **Opcode Mapping**: 100% of text strings map across 5 opcodes:
  - `0x80000307`: Dialogue text (linked to speaker ID)
  - `0x80000406`: System / Narration text
  - `0x03000303`: Inline UI text
  - `0xF0010005`: Choice selections
  - `0x01000D02`: Dynamic string parameters
- **Extraction Corpus**: 931 scene JSON files extracted to `gt_input/` (97,274 ordered entries, 1,982,446 Japanese characters).
- **Round-Trip Status**: Verified byte-identical repack for untouched script and pointer remapping for modified strings. A synthetic edit test split seven shared pool strings into separate variants so different occurrences could receive different translations.

### 3.3 Font System (`font/sulakyapi12`)
- **Sheets**: `font12_0.tm2` through `font12_3.tm2` (512x512 4bpp indexed, 131,200 bytes uncompressed TIM2).
- **Sheet 3 Usable Area**: Rows `Y=401..512` are completely empty in the original Japanese atlas. ASCII characters `0x20..0x7E` are injected into this unused region, preserving 100% of existing Japanese Kanji.
- **Palette Indices**:
  - `14`: Transparent
  - `13`: 1px Black Outline (dynamically overwritten per draw by the EBOOT glyph renderer at `0x08881a44..0x08881a68` with sprite outline RGBA `+0x34..+0x37`)
  - `15`: Solid White Fill (Ink)
  - `0..12`: Unused in original sheets; populated with opaque grayscale edge shades (`18..237`) for antialiased Latin edges (left untouched by the EBOOT draw path)
- **Metrics File (`abc.w_abc`)**:
   - Header: 22 bytes (`version=5`, four floats, maximum lookup code).
   - Lookup Table: `(max_code + 1) * 2` bytes (Shift-JIS code to glyph index).
  - Glyph Count: 4 bytes.
  - Glyph Records (18 bytes each): `[x0, y0, x1, y1, a_bearing, b_width, c_bearing, 0, sheet_idx]`.

### 3.4 EBOOT Text Rendering Pipeline
- **ELF Type**: 32-bit MIPS32 Little-Endian, load address `0x08804000`.
- **Text Context Init**: `0x0887B340` (allocates `0x88` header + line buffers).
  - `+0x10`: Line width / character slots limit.
  - `+0x14`: Line count limit.
  - `+0x3C`: Base pointer to text buffer.
  - `+0x40`: Current slot cursor index.
  - `+0x70`: Glyph sprite pointer table.
- **Character Emission**:
  - `0x0887B97C`: 2-byte Shift-JIS / full-width emission.
  - `0x0887BFD4`: 1-byte ASCII emission.
- **Typewriter & Escape Sequence Parser**: `0x0887D678`.
   - Handles `\n` linebreaks through escape dispatch; callable newline helper: `0x0887C400`.
  - Handles `\sNN` emote and formatting codes.
   - `0x08949940` contains live code, not an empty cave. The PoC appends a second executable `PT_LOAD` at `0x08A76000`, after the original memory end `0x08A75B00`.
- **State Serializer / Deserializer**: `0x0887F2F8` (save) and `0x0887F5D8` (load) store fixed `0x1458`-byte records per text context, hardcoded for at most **`0xF8` (248)** byte slots (`0x64` header + `0xF8` text bytes + `0xF8 * 0x14` sprite records). The original `SLOT_FACTOR = 4` (`208 * 3 = 624` slots) overflowed this buffer by ~7.5 KB, corrupting `fade_obj->0x18` (`0x00000000`) and causing `Invalid Memory Access` at `0x6c` in `0x0887EB58` (`fade_flush`). Also, `0x0887F880` in `0x0887F5D8` mistakenly called `emit_wide` (`0x0887B97C`) instead of `emit_ascii` (`0x0887BFD4`) when restoring 1-byte ASCII.
- **Typewriter Fade List**: `0x0887E500` (`fade_add_main`, originally unchecked against capacity `0xc($a0)`), flushed by `0x0887EB58` (`fade_flush`) and freed by `0x0887E11C`.
- **Backlog Subsystem**: Capture at `0x0887F924` (hardcoded `0xF8` body cap at `0x0886D0C0`, `0x40` speaker cap at `0x0886D078`), allocator at `0x0887FB3C` (`~3x` body sprite capacity), and renderer at `0x0887FE40` (callers `0x0886DA6C`, `0x0886DA90`, `0x0886E44C`, `0x0886E470`), which originally advanced ASCII by fixed `half_cell` (`7px`) and wrapped mid-word. Flag `bl + 0x08 == 0xFFFF` (checked at `0x08880768`) puts body text on a new line below the speaker.

---

## 4. Phase Status Matrix

| Phase | Description | Status | Key Deliverable |
|---|---|---|---|
| **P0** | Environment Setup & Hashes | **Complete** | [`reports/source.md`](file:///d:/Documents/Twinkle_Crusaders_GoGo/reports/source.md) |
| **P1** | Extraction & Rebuild Toolchain | **Complete** | `tools/cpk/`, `tools/pjadv/`, `gt_input/` (931 scenes) |
| **P2** | EBOOT Word Wrap & Font Replacement | **Barlow + 1.5x slotfix + save-load/backlog EBOOT fixes built (`13/13` tests pass); PPSSPP re-check pending** | `tools/build_p2.py`, `tools/eboot/patch_eboot.py`, `BarlowSemiCondensed/`, `build/p3_batch1_backlogfix2/`; remaining checks in [P2 report](reports/p2-proof-of-concept.md) |
| **P3** | Text Translation & Editing | **Complete (931/931 scenes, 97,274 rows)** | Full script in `gt_output/` (`95,890` changed rows; `1,268` `label`/`scene_title` engine keys preserved; CP932 & ASCII `!`/`?` normalized; `195` 4-line rows flagged for editorial tightening) |
| **P4** | Graphic & UI Localization | **Complete (73 EBOOT strings + 176 UI/Logo textures)** | `glossary/eboot_strings.json` (`73/73`), CSM1 8bpp `tools/cpk/tim2.py`, 4x-supersampled `tools/p4/*` (`14` `GAMEINIT`, `145` `BATTLE`, `17` `GRAPHIC` including English Title Screen logos) |
| **P5** | Master Build & xdelta3 Release | **Built & round-trip verified (`build/master_v5/`)** | `tools/build_master.py`, `build/master_v5/Twinkle_Crusaders_GoGo_EN.iso` & `.xdelta` (`xdelta3` v3.2.2, `10,811,736` bytes, SHA-256 round-trip verified) |

---

## 5. Tooling Inventory & Usage

All tools are located in the [`tools/`](file:///d:/Documents/Twinkle_Crusaders_GoGo/tools/) directory:

### 1. `tools/cpk/cpk.py` (CRI CPK v7 Unpacker & Rebuilder)
- **Extract**:
  ```powershell
  python tools/cpk/cpk.py extract <input.cpk> <output_dir>
  ```
- **Verify an untouched rebuild**:
  ```powershell
   python tools/cpk/cpk.py verify-roundtrip <input.cpk> <new_output.cpk>
   ```
   Arbitrary member replacement uses `CpkArchive.rebuild(output_path, replacements)`; there is no directory-based `pack` CLI. `tools/build_p2.py` combines font and scenario replacements.

### 2. `tools/pjadv/chunk_bin.py` (Zlib Chunk Container Codec)
- **Unpack**:
  ```powershell
  python tools/pjadv/chunk_bin.py unpack <container.bin> <output_dir>
  ```
- **Pack**:
  ```powershell
  python tools/pjadv/chunk_bin.py pack <input_dir> <output.bin>
  ```

### 3. `tools/pjadv/scenario.py` (Scenario Disassembler & Rebuilder)
- **Extract all scenes to JSON**:
  ```powershell
   python tools/pjadv/scenario.py extract --cpk <input.cpk> --out <new_workspace>
   ```
   This creates `original/`, `metadata/`, and `gt_input/` under the new workspace. For a separate workspace, pass its path as `--work` to packing or `tools/build_p2.py`; the commands below use this project's already-prepared repository-root workspace.
- **Rebuild scenario and text pools from translated JSONs**:
  ```powershell
   python tools/pjadv/scenario.py pack --work . --trans gt_output --cpk work/iso_extract/GAMEINIT.CPK --out-cpk <new_output.cpk>
  ```

### 4. `tools/font/build_font.py` (Barlow Semi Condensed Font Atlas & Metrics Generator)
- **Generate modified atlas & metrics**:
  ```powershell
   python tools/font/build_font.py --cpk work/iso_extract/GAMEINIT.CPK --tight-dialogue --out work/font_next_trial
  ```
  Supports `--dialogue-size`, `--tight-dialogue`, `--dialogue-width-scale`, `--space-width`, variable axes (`--font-weight`, `--font-roundness`, `--font-optical-size`), and `--no-antialias`.

### 5. `tools/iso/patch_iso.py` (ISO9660 Disc Patcher)
- **Patch file into ISO**:
  ```powershell
   python tools/iso/patch_iso.py --src <clean.iso> --out <new_test.iso> --replace "PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK=<new_gameinit.cpk>"
  ```

### 6. `tools/eboot/mips_asm.py` (MIPS32 Assembler)
- Lightweight assembler for compiling inline MIPS assembly snippets and generating binary patches for `EBOOT.BIN`.

### 7. `tools/eboot/patch_eboot.py` (Version-Pinned Wrapping & String Patcher)
```powershell
python tools/eboot/patch_eboot.py --src work/eboot/EBOOT_decrypted.bin --out work/eboot/EBOOT_next_trial.bin --strings glossary/eboot_strings.json
```
Output must be a new file. `--strings` patches all 73 translated CP932 strings from `glossary/eboot_strings.json` in-place within their `slot_capacity` and patches `0x0894552c` (`move s6, t1` -> `move s6, zero`) in `0x089454ec` (`sceUtilityMsgDialog` wrapper) to disable hardcoded Japanese byte-offset `U+2122` (`™`) insertions.

### 8. `tools/p4/` & `tools/cpk/tim2.py` (P4 UI Texture & Title Logo Localization)
```powershell
python tools/p4/loc_battle_banners.py
python tools/p4/loc_battle_hud.py
python tools/p4/loc_systemzip.py
python tools/p4/loc_tutorial.py
python tools/p4/loc_graphic_menus.py
python tools/p4/loc_title_logo.py
python tools/p4/pack_textures.py
```
`tools/cpk/tim2.py` decodes/encodes 4bpp and 8bpp indexed RGBA32 `TIM2` textures (`.zip` zlib wrappers, raw `TIM2`, and zeroed-magic `CRILAYLA`), including PS2/PSP **CSM1 8bpp CLUT swizzling** (`_csm1_swizzle_palette` when `img_type == 5` and `(clut_type & 0x80) == 0`). `tools/cpk/cpk.py` supports TOC-after-content rebuilding (`BATTLE.CPK` and `GRAPHIC.CPK`, byte-identical `verify-roundtrip`). `tools/p4/render_helpers.py` provides 4x-supersampled Segoe UI Bold text rendering and parity-preserving vertical dither inpainting (`inpaint_vertical_dither`). Together, the P4 scripts localize **176** textures (`14` in `GAMEINIT.CPK/SystemZip`, `145` in `BATTLE.CPK`, and `17` in `GRAPHIC.CPK/AdvGraphic` including 1:1 template-matched English Title Screen logos `sys_ti_logo.zip`, `sys_ti_logo02.zip`, and `sys_ti_files02.zip`).

### 9. `tools/pjadv/check_widths.py` (Dialogue Box Budget Check)
```powershell
python tools/pjadv/check_widths.py --trans gt_output
```
Measures translated rows with the built `sulakyapi12` metrics (`a + b + c` signed bearings for ASCII, `14px` for 2-byte Shift-JIS) and simulates the EBOOT's greedy word wrap against the 364px-per-line, three-line message window. Any row needing a fourth line is clipped in game, so this must report zero overflows before a build. `tools/build_p2.py` runs the same check and fails on overflow.

### 10. `tools/build_p2.py` (P2 Test ISO Builder)
```powershell
python tools/build_p2.py --tight-dialogue --out build/p2_next_trial
python -m unittest discover -s tests -v
```
Choose a new output directory. The builder checks source identity, generates fonts, rebuilds and re-extracts the scripts, verifies every CPK member, and reads both replacements back from the separate ISO copy.

### 11. `tools/build_master.py` (P5 Merged Master ISO & xdelta3 v3.2.2 Builder)
```powershell
python tools/build_master.py --out build/master_next --fonts build/p3_batch1_backlogfix2/fonts
```
Merges P2 (Barlow font + EBOOT wrapping/backlog fixes), P3 (`gt_output/` 931 scenes, with full re-extraction verification), and P4 (`73` EBOOT strings + `176` localized UI/Logo textures across `GAMEINIT.CPK`, `BATTLE.CPK`, and `GRAPHIC.CPK`), patches all four files into the master ISO with readback verification, and generates `Twinkle_Crusaders_GoGo_EN.xdelta` using `xdelta3` v3.2.2.

---

## 6. Current Checkpoint and Next Steps

- **Latest Merged Master Build (`build/master_v5/`, 2026-11-22):**
  - **Merged ISO:** `build/master_v5/Twinkle_Crusaders_GoGo_EN.iso` (`1,820,000,256` bytes, SHA-256: `d45e7cc6ff080c4ddaa3f5879b1d490254973e57b225444fb2b26bae14efe138`)
  - **xdelta3 v3.2.2 Patch:** `build/master_v5/Twinkle_Crusaders_GoGo_EN.xdelta` (`10,811,736` bytes) — round-trip `-d` verified bit-for-bit against clean Japan v1.01 ISO (`XDELTA round-trip match: True`).
  - **P3 Script (`gt_output/`):** All `931 / 931` scene JSONs (`97,274` entries, `95,890` changed rows, `88,284` pool strings, `0` control-code warnings) packed and re-extraction verified. Restored `1,268` modified internal engine lookup keys (`label` and `scene_title` across `856` files), normalized `9` non-CP932 characters (`—` -> `--`, accented Latin letters across `746` files), and normalized fullwidth `！`/`？` -> ASCII `!`/`?` across `24,229` dialogue rows (`914` files). (`195` of `93,396` checked dialogue rows exceed the `364px x 3` line budget and are logged in `build/master_v5/validation.json` for editorial tightening.)
  - **P4 EBOOT & UI Textures:**
    - `EBOOT.BIN`: All `73 / 73` strings from `glossary/eboot_strings.json` patched in-place (`eboot_006_date_time` `日` -> `"  "` for clean Save/Load timestamp spacing), plus `0x0894552c` (`move s6, zero`) disabling stray `™` insertions in PSP system dialogs.
    - `GAMEINIT.CPK` (`14` P4 textures, `456/456` members verified): 4x-supersampled Segoe UI Bold `SystemZip` menus (`sys_o_files01..08` including uniform `BGM` and `16x16` digit grid `0..9/%/./s`, `sys_sl_files04`, `sys_sl_lbase`, `sys_sl_sbase`, `sys_sw`, `sys_tm_files01`, `sys_mn_files01`, `sys_k_files01`, `sys_k_files02`).
    - `BATTLE.CPK` (`145` P4 textures, `1,426/1,426` members verified): `68` `res_title` banners, `19` `EXName` plates, `18` `btl_nld_*_name*` banners, `4` `res`/`etc` sheets, `5` `btl_files*` HUD sheets, and `31` `tutorial` sheets.
    - `GRAPHIC.CPK` (`17` P4 textures, `4,109/4,109` members verified): 1:1 template-matched English Title Screen logos (`sys_ti_logo.zip`, `sys_ti_logo02.zip`, `sys_ti_files02.zip`), Title Screen menu (`sys_ti_files01.zip`), Data Install screens (`sys_media_base.zip`, `sys_media_files01..03.zip`, `sys_memory_files01.zip`), Gallery bottom bars (`sys_gc/gm/gs_base.zip`), Free Battle & Tutorial Select (`sys_hrbs_base1/2.zip`), Controls (`sys_sousa.zip`, `sys_sousa_02.zip`), and Trophy Gallery (`hetr_pack01.zip`).
  - **Unit Tests:** `python -m unittest discover -s tests` — **14/14 passing** (`0.220s`).
- **Earlier P2 Baseline ISO:** `build/p3_batch1_backlogfix2/Twinkle_Crusaders_GoGo_P2.iso` (`1,819,779,072` bytes) — **Barlow Semi Condensed Medium** (`14px`, `ws=1.00`, `space_w=3`, smooth gamma AA shades `2..12` + `15`, uniform `baseline_row=11`, 4x rounded serif `I`), **`1.5x` EBOOT slotfix + save-load/backlog fixes** (`6e3995e38115c3cc`, `1,912`-byte payload, `78 * 3 = 234 <= 248 = 0xF8`, plus `0xF8` serializer clamp), `abc.w_abc` record counts unchanged (`302 / 2956 / 177`), `456/456` CPK members verified, `914` changed rows across 6 scenes, `0` width overflows, `BarlowSemiCondensed/OFL.txt` included.
  - **Old-save load crash fix** (`_free_r` heap corruption at `0x08812970` when loading saves created under earlier `SLOT_FACTOR = 4` builds): added `fade_add_checked` capacity guard at `0x0887E500`, `guard_load_ctx` at `0x0887F774` (skips corrupted `> 0xF8` old-save text records), and fixed `0x0887F880` (`jal 0x0887b97c` -> `jal 0x0887bfd4`) so ASCII restores through `emit_ascii`.
  - **Backlog proportional spacing, word wrap & speaker capture clamp** (`0x0887FE40`, `0x0887F924`): refactored `advance` into shared `advance_by_font`, added `backlog_speaker_adv` (`0x0888052C`), `backlog_body_wrap` (`0x088809FC`), and `backlog_body_adv` (`0x08880B08`), preserved `0x20` in `ctx->text_buf` on `check_space` wraps so backlog does not join words across wrapped lines, and added `clamp_backlog_copy` (`0x0887FA74`/`0x0887FA88`/`0x0887FA94`) clamping `ctx->0x18` to caller `max_bytes` (`$a3`: `0x40` speaker / `0xF8` body) so `1.5x`-expanded speaker contexts cannot overflow the `0x58`-byte speaker backlog record into the adjacent `body_rec` header (which leaked `0x096Fxxxx` bytes as `X`/`x`/`o` inside speaker brackets).
  - Visual artifacts: `build/p3_batch1_barlow/barlow_preview.png` and 7-font comparison sheet `work/font_candidates/font_comparison_sheet.png` (made with `work/font_candidates/make_sheet.py`).
- **Superseded Builds (under `build/`):** `p3_batch1_backlogfix` (Barlow + backlog wrapping before the `0x0887F924` speaker capture clamp; body rendering confirmed clean in PPSSPP, speaker brackets showed leaked adjacent heap bytes), `p3_batch1_barlow` (Barlow + `1.5x` slotfix before save-load/backlog EBOOT fixes), `p3_batch1_slotfix` (Inrond Step 3 + `1.5x` slotfix), `p3_batch1_step3`, `p3_batch1_v4`, `p3_batch1_inrond` (all three used `SLOT_FACTOR = 4` which triggered the `0x6c` serializer heap overflow; note any saves written under `SLOT_FACTOR = 4` builds contain corrupted `> 0xF8` records on disk), `p3_batch1_v3` / `p3_batch1_legible` (appended glyph records / EBOOT y-lift), and earlier NewGoStyle/Inrond P2 trials.
- **Glyph Records & Leading:** ASCII edits reuse each code's existing `abc.w_abc` record (`302 / 2956 / 177`). Experimental per-line EBOOT y-lift remains **reverted**; vertical fit is enforced by `baseline_row = 11` and the `364px x 3-line` budget.

Next:
1. Boot `build/p3_batch1_backlogfix2/Twinkle_Crusaders_GoGo_P2.iso` in PPSSPP: confirm speaker brackets render cleanly (`[Misa]`, `[Nanaka]`, `[Ria]` with no trailing `o`/`X`/`x`), along with backlog proportional wrapping, loading an old save without crashing, saving/reloading a fresh save, and playing `PROLOGUE1001_01` + 発足!! 流星生徒会 scenes (`\S10`, page endings).
2. Check choices, centered text, ruby, and remaining direct-emission callers (`0x0887D210..0x0887D614`, `0x0884399C`, `0x08880BC4`, `0x08880CD0`).
3. Implement pixel-based Japanese punctuation handling (kinsoku checks still use the expanded byte-slot limit) and lookahead across arbitrary inline controls.
4. Check expanded `sulakyapi8`/`sulakyapi18` atlases and Data Install enabled/disabled behavior in disposable PPSSPP profiles without deleting user saves or installed data.

P2 remains in progress until runtime checks pass. This ISO is a proof of concept, not a release build.

---

## 7. Safety Invariants & Rules

- **DO NOT commit proprietary binaries**: Keep `.iso`, `.bin`, `.cpk`, `.dat`, `.tm2` out of git. (Enforced by `.gitignore`).
- **Never modify clean source files directly**: Keep `Twinkle Crusaders GoGo! (Japan) (v1.01).iso` and `work/eboot/EBOOT_decrypted.bin` pristine and read-only.
- **Licensing**: Include `BarlowSemiCondensed/OFL.txt` with current bitmap derivatives. Preserve `Inrond-1.0/OFL.txt` and NewGoStyle notices with any historical assets distributed separately.
