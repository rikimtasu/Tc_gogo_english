# Twinkle Crusaders GoGo! (PSP) — English Translation Project Handoff

**Target Game**: *Twinkle Crusaders GoGo!* (*ティンクル☆くるせいだーす GoGo!*)  
**Platform**: Sony PlayStation Portable (PSP)  
**Product Code**: `ULJS-00316` (v1.01)  
**Git Repository**: [https://github.com/rikimtasu/Tc_gogo_english.git](https://github.com/rikimtasu/Tc_gogo_english.git) (Branch: `main`)  
**Last Updated**: 2026-11-21  

---

## 1. Executive Summary & Source Baseline

This project produces a complete English translation patch (xdelta3) for the PSP visual novel *Twinkle Crusaders GoGo!* (v1.01). Scope is currently restricted to Disc 1 (*GoGo!* main game); the *STARLIT BRAVE!!* bonus UMD is explicitly deferred.

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
5. **Word Wrapping Strategy**: Option (b) — Proportional word wrapping injected directly into the EBOOT MIPS text renderer. No pre-wrapping at extraction time.
6. **Font Choice**: `NewGoStyle-Ver1.000` (SIL Open Font License 1.1) to regenerate the PSP bitmap font sheets (`sulakyapi{8,12,18}`).

---

## 3. Reverse Engineering Findings & Formats

### 3.1 Container Hierarchy
```
ISO9660 (.iso)
 └── PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK (CRI CPK v7)
      ├── font/sulakyapi12/
      │    ├── abc.w_abc      (Glyph metrics & UCS-2 mapping)
      │    └── font12_*.tm2   (CRILAYLA compressed 4bpp indexed TIM2 sheets)
      └── pjadv/
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
- **Round-Trip Status**: Verified byte-identical repack for untouched script and full pointer-remapping verification for modified strings (`split_duplicates=7` test passed).

### 3.3 Font System (`font/sulakyapi12`)
- **Sheets**: `font12_0.tm2` through `font12_3.tm2` (512x512 4bpp indexed, 131,200 bytes uncompressed TIM2).
- **Sheet 3 Usable Area**: Rows `Y=401..512` are completely empty in the original Japanese atlas. ASCII characters `0x20..0x7E` are injected into this unused region, preserving 100% of existing Japanese Kanji.
- **Palette Indices**:
  - `14`: Transparent
  - `13`: 1px Black Outline
  - `15`: Solid White Fill (Ink)
- **Metrics File (`abc.w_abc`)**:
  - Header: 22 bytes (`magic=0x20040114`).
  - Lookup Table: `(max_ucs + 1) * 2` bytes (UCS-2 char code to glyph index).
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
  - Handles `\n` linebreaks (`0x0887D7A0` / `0x0887C400`).
  - Handles `\sNN` emote and formatting codes.
  - Redundant debug branches checking `0x08A05F94` can be repurposed, or code caves in `.text` (`0x08949940`) can hold word-wrap lookahead logic.

---

## 4. Phase Status Matrix

| Phase | Description | Status | Key Deliverable |
|---|---|---|---|
| **P0** | Environment Setup & Hashes | **Complete** | [`reports/source.md`](file:///d:/Documents/Twinkle_Crusaders_GoGo/reports/source.md) |
| **P1** | Extraction & Rebuild Toolchain | **Complete** | `tools/cpk/`, `tools/pjadv/`, `gt_input/` (931 scenes) |
| **P2** | EBOOT Word Wrap & Font Replacement | **In Progress** | `tools/font/build_font.py`, `tools/iso/patch_iso.py`, `tools/eboot/mips_asm.py` committed |
| **P3** | Text Translation & Editing | **Pending P2** | Target: `gt_output/` JSONs + human proofreading |
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
- **Rebuild**:
  ```powershell
  python tools/cpk/cpk.py pack <input_dir> <output.cpk>
  ```

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
  python tools/pjadv/scenario.py extract <unpacked_pjadv_dir> <gt_input_dir>
  ```
- **Rebuild scenario and text pools from translated JSONs**:
  ```powershell
  python tools/pjadv/scenario.py pack <unpacked_pjadv_dir> <gt_output_dir> <rebuilt_pjadv_dir>
  ```

### 4. `tools/font/build_font.py` (NewGoStyle Font Atlas & Metrics Generator)
- **Generate modified atlas & metrics**:
  ```powershell
  python tools/font/build_font.py --ttf NewGoStyle-Ver1.000/NewGoStyle-Regular.ttf --orig-font work/extracted_gameinit/font/sulakyapi12 --out work/font_build
  ```

### 5. `tools/iso/patch_iso.py` (ISO9660 Disc Patcher)
- **Patch file into ISO**:
  ```powershell
  python tools/iso/patch_iso.py --iso <target.iso> --path "PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK" --file <new_gameinit.cpk>
  ```

### 6. `tools/eboot/mips_asm.py` (MIPS32 Assembler)
- Lightweight assembler for compiling inline MIPS assembly snippets and generating binary patches for `EBOOT.BIN`.

---

## 6. Immediate Next Steps to Complete P2

1. **Generate Font Assets**:
   Run `tools/font/build_font.py` to create the updated `font12_3.tm2` and `abc.w_abc` with crisp NewGoStyle Latin glyphs.
2. **Build EBOOT Word Wrap Patcher (`tools/eboot/patch_eboot.py`)**:
   - Write hook in MIPS assembly using `tools/eboot/mips_asm.py`.
   - Intercept line calculation in typewriter loop (`0x0887D678` / `0x0887CAAC`).
   - Implement word-boundary lookahead: scan forward to space or newline, sum character widths from `abc.w_abc`, and trigger the newline handler (`0x0887D7A0`) if remaining line space is exceeded.
3. **Assemble Test Build**:
   - Translate opening prologue scene [`gt_input/0003_scene.json`](file:///d:/Documents/Twinkle_Crusaders_GoGo/gt_input/0003_scene.json) (`PROLOGUE1001_01`).
   - Pack with `tools/pjadv/scenario.py pack` into a rebuilt `GAMEINIT.CPK`.
   - Patch clean ISO copy with `tools/iso/patch_iso.py`.
4. **PPSSPP Emulator Validation**:
   - Launch in PPSSPP (`D:\Video_Game\Emulator\PSP\PPSSPP 1.20\ppsspp\PPSSPPWindows64.exe`).
   - Confirm:
     - NewGoStyle glyphs render sharply without clipping.
     - English text wraps naturally at word boundaries without cutting words in half.
     - No memory leaks or crashes during fast-forward / dialogue skip.

---

## 7. Safety Invariants & Rules

- **DO NOT commit proprietary binaries**: Keep `.iso`, `.bin`, `.cpk`, `.dat`, `.tm2` out of git. (Enforced by `.gitignore`).
- **Never modify clean source files directly**: Keep `Twinkle Crusaders GoGo! (Japan) (v1.01).iso` and `work/eboot/EBOOT_decrypted.bin` pristine and read-only.
- **Licensing**: Preserve the SIL Open Font License notice for `NewGoStyle` (`NewGoStyle-Ver1.000/OFL.txt`).
