# Twinkle Crusaders GoGo! (PSP) — English Translation Project Handoff

**Target Game**: *Twinkle Crusaders GoGo!* (*ティンクル☆くるせいだーす GoGo!*)  
**Platform**: Sony PlayStation Portable (PSP)  
**Product Code**: `ULJS-00316` (v1.01)  
**Git Repository**: [https://github.com/rikimtasu/Tc_gogo_english.git](https://github.com/rikimtasu/Tc_gogo_english.git) (Branch: `main`)  
**Last Updated**: 2026-11-21  

---

## 1. Executive Summary & Source Baseline

The intended deliverable is a complete English xdelta3 patch for the PSP visual novel *Twinkle Crusaders GoGo!* (v1.01). Currently, a 34-row prologue draft and a P2 rendering trial are built; runtime validation is pending. Scope is restricted to Disc 1 (*GoGo!* main game); the *STARLIT BRAVE!!* bonus UMD is deferred.

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
6. **Font Choice**: `Inrond-1.0` (SIL Open Font License 1.1) replaces NewGoStyle for all Latin glyphs in `sulakyapi{8,12,18}`. Original Japanese glyphs are preserved. NewGoStyle files and earlier builds remain only for historical comparison.
   The active dialogue preset is 14px, weight 500, roundness 50, optical size 14. `--tight-dialogue` uses 90% horizontal scale, one-pixel minimum gaps between ink bounds, and 2px spaces. Supersampled grayscale edges use previously unused palette entries without changing Japanese glyph colors. The new `H` has 10px of visible ink versus 11px for original Japanese `本`. Runtime readability testing is pending.

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
  - `13`: 1px Black Outline
  - `15`: Solid White Fill (Ink)
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

---

## 4. Phase Status Matrix

| Phase | Description | Status | Key Deliverable |
|---|---|---|---|
| **P0** | Environment Setup & Hashes | **Complete** | [`reports/source.md`](file:///d:/Documents/Twinkle_Crusaders_GoGo/reports/source.md) |
| **P1** | Extraction & Rebuild Toolchain | **Complete** | `tools/cpk/`, `tools/pjadv/`, `gt_input/` (931 scenes) |
| **P2** | EBOOT Word Wrap & Font Replacement | **Boot/wrapping confirmed; tight Inrond trial ready** | `tools/build_p2.py`, `tools/eboot/patch_eboot.py`, verified fonts, and prologue test ISO; remaining runtime checks in [P2 report](reports/p2-proof-of-concept.md) |
| **P3** | Text Translation & Editing | **Full pass pending P2** | 34-row opening draft in `gt_output/0003_scene.json`; editorial review pending |
| **P4** | Graphic & UI Localization | **Deferred** | Textures in `GRAPHIC.CPK` and `BATTLE.CPK` |
| **P5** | Master Build & xdelta3 Release | **Deferred** | Verified patch against clean v1.01 ISO |

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

### 4. `tools/font/build_font.py` (Inrond Font Atlas & Metrics Generator)
- **Generate modified atlas & metrics**:
  ```powershell
   python tools/font/build_font.py --cpk work/iso_extract/GAMEINIT.CPK --tight-dialogue --out work/font_next_trial
  ```

### 5. `tools/iso/patch_iso.py` (ISO9660 Disc Patcher)
- **Patch file into ISO**:
  ```powershell
   python tools/iso/patch_iso.py --src <clean.iso> --out <new_test.iso> --replace "PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK=<new_gameinit.cpk>"
  ```

### 6. `tools/eboot/mips_asm.py` (MIPS32 Assembler)
- Lightweight assembler for compiling inline MIPS assembly snippets and generating binary patches for `EBOOT.BIN`.

### 7. `tools/eboot/patch_eboot.py` (Version-Pinned Wrapping PoC)
```powershell
python tools/eboot/patch_eboot.py --src work/eboot/EBOOT_decrypted.bin --out work/eboot/EBOOT_next_trial.bin
```
Output must be a new file. GPU rendering and PSP loader compatibility remain unverified.

### 8. `tools/build_p2.py` (Validated Test ISO Builder)
```powershell
python tools/build_p2.py --tight-dialogue --out build/p2_next_trial
python -m unittest discover -s tests -v
```
Choose a new output directory. The builder checks source identity, generates fonts, rebuilds and re-extracts the scripts, verifies every CPK member, and reads both replacements back from the separate ISO copy.

---

## 6. Current Checkpoint and Next Steps

- **Test ISO:** `build/p2_inrond_tight_20261121/Twinkle_Crusaders_GoGo_P2.iso`. Earlier NewGoStyle trials are preserved under `build/`.
- **Script baseline validation:** The original prologue build re-extracted 931 scenes and 97,274 ordered entries matching the expected rows. All 456 CPK members and both ISO replacements passed readback checks. Only the intended 34 rows changed, with one split pool duplicate and zero control-code warnings. Later font-only trials preserve these script payloads.
- **Fonts:** Latest assets in `build/p2_inrond_tight_20261121/fonts/font/`. All three Latin sets now use Inrond. Dialogue uses 14px raster size, 90% horizontal scale, tight spacing, and grayscale edge shades; line height remains 19px. Prologue advances total 10,816px, about 27% less than the regular-width NewGoStyle 13px trial. Six font members changed; EBOOT, scripts, Japanese glyphs, and their used palette colors were preserved. The output includes Inrond's OFL notice.
- **Runtime:** The user confirmed boot/wrapping in earlier trials but rejected the NewGoStyle appearance. The Inrond trial has not been tested in PPSSPP. 45 tests pass, including variable-axis validation, open letter counters, and protection of original palette colors. All 456 CPK members and ISO CPK/EBOOT readbacks were checked. See [P2 report](reports/p2-proof-of-concept.md) for the launch command and remaining checklist.

Next:
1. Boot the test ISO in PPSSPP, start a new game, and play the opening `PROLOGUE1001_01`. Verify all 34 lines, spacing, word wrapping, page endings, and `\S10`.
2. Check backlog, choices, centered text, ruby, and direct-emission callers. Word wrapping currently hooks only the main typewriter parser.
3. Implement pixel-based Japanese punctuation handling. Existing kinsoku checks (rules that prevent closing punctuation from starting a line) still use the expanded byte-slot limit. Lookahead across arbitrary inline controls also needs work.
4. Measure memory during skipping/fast-forward; line-slot storage was expanded fourfold, while the global sprite pool remains unchanged.
5. Check the expanded small/large atlases and Data Install enabled/disabled behavior. Do not delete user saves or installed data.

P2 remains in progress until runtime checks pass. This ISO is a proof of concept, not a release build.

---

## 7. Safety Invariants & Rules

- **DO NOT commit proprietary binaries**: Keep `.iso`, `.bin`, `.cpk`, `.dat`, `.tm2` out of git. (Enforced by `.gitignore`).
- **Never modify clean source files directly**: Keep `Twinkle Crusaders GoGo! (Japan) (v1.01).iso` and `work/eboot/EBOOT_decrypted.bin` pristine and read-only.
- **Licensing**: Include `Inrond-1.0/OFL.txt` with current bitmap derivatives. Preserve NewGoStyle's notices with any historical assets distributed separately.
