# P4 Non-Script Asset & EBOOT Audit (`reports/p4-asset-audit.md`)

Updated: 2026-11-21

## Overview

Before full P3 script translation, the project's non-script archives (`GAMEINIT.CPK`, `BATTLE.CPK`, `GRAPHIC.CPK`) and decrypted binary (`work/eboot/EBOOT_decrypted.bin`) were audited to:
1. Inventory all UI textures requiring P4 image localization.
2. Verify whether battle stage files (`BATTLE.CPK/Battle/*.bbn`) or title preload lists (`GRAPHIC.CPK/Grp_Title/*.txt`) contain player-visible text or act as internal script keys.
3. Export hardcoded Japanese strings from `EBOOT_decrypted.bin` into a structured translation manifest ([`glossary/eboot_strings.json`](../glossary/eboot_strings.json)).

## Summary Inventory

| Asset / Location | Inspected | Needs P4 Work | Status / Notes |
|---|---|---|---|
| `GAMEINIT.CPK/SystemZip` (`.zip` -> `TIM2`) | 83 | 15 | System menus, save/load, backlog, options |
| `BATTLE.CPK/EXName` (`.zip` -> `TIM2`) | 19 | 19 | EX-attack / boss nameplates |
| `BATTLE.CPK/res` (`.zip` -> `TIM2`) | 13 | 1–2 | `btl_res_title00.zip` (`○ 進む`), optional `btl_mvp_files01.zip` (`MACAROON` -> `MACARON`) |
| `BATTLE.CPK/res_title` (`.zip` -> `TIM2`) | 68 | 68 | Battle result stage/character title banners |
| `BATTLE.CPK/tutorial` (`.zip` -> `TIM2`) | 49 | 47 | All tutorial slides except `tu_nose.zip` and `tu_waku.zip` |
| `BATTLE.CPK/etc` (`.zip` -> `TIM2`) | 66 | 2 | `btl_btarget_name.zip`, `btl_total_vs_files01.zip` |
| `BATTLE.CPK` root `.tm2` | 247 (189 triaged, 58 BG/MVP skipped) | 24 | 6 HUD/command sheets + 18 `btl_nld_*_name*.tm2` banners |
| **Total UI Textures** | **545** | **176–177** | **176** JP/mixed UI textures + optional `btl_mvp_files01.zip` |
| `BATTLE.CPK/Battle/*.bbn` | 109 | 0 | Rolling-XOR encrypted engine tables (`0x0886f120`); links 414 scenario `label` keys |
| `GRAPHIC.CPK/Grp_Title/*.txt` | 920 | 0 | Preload asset lists (`0x0883c818`); links 841/841 (`766` visible) `scene_title` keys |
| `GRAPHIC.CPK/AdvGraphic` / `GAMEINIT.CPK/AdvZip` | 3,189 / 354 | — | Character sprites, event CGs, VFX, wipes (not individually triaged) |
| `work/eboot/EBOOT_decrypted.bin` | 5 verified ranges | 73 strings | Exported to [`glossary/eboot_strings.json`](../glossary/eboot_strings.json) |

---

## 1. CPK Layout & Texture Container Findings

- **`BATTLE.CPK` TOC-after-content layout:** Unlike `GAMEINIT.CPK` (`TocOffset < ContentOffset`), `BATTLE.CPK` places `ContentOffset` before `TocOffset`, with entry `FileOffset` values relative to `min(TocOffset, ContentOffset)`. [`tools/cpk/cpk.py`](../tools/cpk/cpk.py) now computes `self.file_base = min(self.toc_offset, self.content_offset)` for reading/extraction and guards `CpkArchive.rebuild()` with `NotImplementedError` when `self.toc_offset > self.content_offset` (P4 repacking support for `BATTLE.CPK` will need TOC-after-content or relocated layout handling).
- **Subfolder `.zip` UI textures (`GAMEINIT/SystemZip`, `BATTLE/*/`):** Wrapped with an 8-byte big-endian header followed by a zlib stream containing a `TIM2` image.
- **`BATTLE.CPK` root `.tm2` textures:** Of the 189 non-BG/non-MVP root textures, **186** are CRILAYLA-compressed with zeroed magic (`4`/`5` + `3` header bytes instead of `b"CRILAYLA"`, unpacking cleanly via [`tools/cpk/crilayla.py`](../tools/cpk/crilayla.py) `decompress(b"CRILAYLA" + raw[8:])`) and **3** are raw uncompressed `TIM2`.

---

## 2. UI Texture Triage (545 Textures)

### 2.1 `GAMEINIT.CPK/SystemZip` (15 / 83 need P4 edit)
The following 15 textures contain Japanese UI labels/prompts:
- `sys_hosi`, `sys_hosi2`
- `sys_log_base`
- `sys_o_files01`, `sys_o_files02`, `sys_o_files03`, `sys_o_files05`, `sys_o_files05_b`, `sys_o_files08`
- `sys_sl_files01`, `sys_sl_files04`, `sys_sl_lbase`, `sys_sl_sbase`
- `sys_sw`
- `sys_tm_files01`

### 2.2 `BATTLE.CPK` Subfolders (137–138 / 215 need P4 edit)
- **`BATTLE.CPK/EXName` (19 / 19):** All 19 textures require localization.
- **`BATTLE.CPK/res` (1–2 / 13):**
  - `btl_res_title00.zip` contains `○ 進む` (requires localization).
  - `btl_mvp_files01.zip` is in English (`EAU DE ROURKE`, `MACAROON`); include in P4 if spelling is unified to `Macaron`.
- **`BATTLE.CPK/res_title` (68 / 68):** All 68 textures require localization.
- **`BATTLE.CPK/tutorial` (47 / 49):** All textures require localization except `tu_nose.zip` and `tu_waku.zip`.
- **`BATTLE.CPK/etc` (2 / 66):** Only `btl_btarget_name.zip` and `btl_total_vs_files01.zip` require localization.

### 2.3 `BATTLE.CPK` Root `.tm2` (24 / 247 need P4 edit)
Skipped sets (`58`): `bt00_BG*` / `btl_BG*` (`28` battle backgrounds) and `btl_mvp_char*` (`30` MVP portraits).
Of the remaining `189` inspected root textures:

- **6 HUD / command / prompt sprite sheets:**
  - `btl_files01.tm2` (`352x504`)
  - `btl_files02.tm2` (`384x432`)
  - `btl_files03.tm2` (`256x200`)
  - `btl_filesE2_1.tm2` (`240x232`)
  - `btl_filesE2_2.tm2` (`160x160`)
  - `btl_filesE3.tm2` (`224x288`)
- **18 pre-fight / loading character title & EX-attack banners:**
  - `btl_nld_byl_name.tm2`, `btl_nld_llt_name.tm2`, `btl_nld_llt_name2.tm2`
  - `btl_nld_mac_name.tm2`, `btl_nld_mac_name2.tm2`, `btl_nld_mel_name.tm2`
  - `btl_nld_mis_name.tm2`, `btl_nld_mis_name2.tm2`, `btl_nld_nan2_name.tm2`
  - `btl_nld_nan_name.tm2`, `btl_nld_nan_name2.tm2`, `btl_nld_ode_name.tm2`
  - `btl_nld_ria_name.tm2`, `btl_nld_ria_name2.tm2`, `btl_nld_sar_name.tm2`
  - `btl_nld_sin2_name.tm2`, `btl_nld_sin_name.tm2`, `btl_nld_sin_name2.tm2`
- **165 clean / non-JP-text root `.tm2`:** `btl_Act_obj.tm2`, `btl_assist_files01.tm2` (`ASSIST`), `btl_black.tm2`, `btl_bonus_files01.tm2` (all-English bonus labels), `btl_cdown*.tm2` (`10` files: `GO!`, `1`–`3`, rings), `btl_filesE1.tm2`, `btl_filesE4.tm2`, `btl_nld_files02.tm2` (`NOW LOADING... PRESS ANY BUTTON`), `btl_nld_cardback.tm2`, `btl_nld_star.tm2`, `22` `btl_nld_*_card*.tm2` portrait cards, `110` `btl_sc08..19_*` cut-in sprites/VFX, `10` `btl_timeline*.tm2`, `2` `btl_unison_area*.tm2`, `btl_white.tm2`.
- **Existing English texture quirks (optional P4 cleanup):**
  - `btl_nld_*_name*.tm2` English sub-headers contain `MOTAL DUELIST -7th GENERAL-`, `LIVING LEXICON -7th GENERAL-` (Melilot), and `GOURMET FIGHTER -7th GENERAL-` (`オデローク`, vs `EAU DE ROURKE` in `btl_mvp_files01.zip`).
  - `btl_nld_*_card*.tm2` portrait cards use `MACAROON` and `MELLILOT`.

---

## 3. Scenario Engine Keys & P3 Guardrails

Two scenario entry categories in `gt_input/*.json` are **internal engine lookup keys**, not display text:

1. **`label` (`414` entries) -> `BATTLE.CPK/Battle/stage.bbn` (`[ステージN_*]`):**
   - EBOOT function `0x0886f120` decrypts `BATTLE.CPK/Battle/*.bbn` (`109` files) using the rolling XOR `dec[i] = raw[i] ^ ((0xC5 + i * 0x5C) & 0xFF)`.
   - None of the 109 decrypted `.bbn` files contain player-visible text; `stage.bbn` matches the scenario `label` lookup keys.
2. **`scene_title` (`841` raw / `766` visible `OP_SCENE` entries) -> `GRAPHIC.CPK/Grp_Title/%s.txt` (`920` files):**
   - EBOOT routine `0x0883c818` substitutes `?` -> `$` and loads `GRAPHIC.CPK/Grp_Title/%s.txt` asset lists (`841/841` raw matches confirmed).

To prevent accidental breakage during P3 translation, [`tools/pjadv/scenario.py`](../tools/pjadv/scenario.py) `pack_from_dir()` now rejects modified `label` or `scene_title` entries with `ValueError` unless explicitly opted in via `allow_label_edits=True` / `allow_scene_title_edits=True` (`--allow-label-edits` / `--allow-scene-title-edits`).

---

## 4. EBOOT Hardcoded Japanese Strings

[`tools/eboot/extract_strings.py`](../tools/eboot/extract_strings.py) extracts all **73** Japanese CP932 strings from `work/eboot/EBOOT_decrypted.bin` (`SHA-256: 96f2556cad518943ab0203f2ffe7d471b92e29fae4f8a7fab62a577355ca3de8`) into [`glossary/eboot_strings.json`](../glossary/eboot_strings.json), mapping PSP runtime virtual addresses via `vaddr = 0x08804000 + (file_offset - 0x54)`:

| Category | File Range | Count | Notes |
|---|---|---|---|
| `save_metadata` | `0x15c4a0..0x15c9a0` | 3 | Fixed PSP SFO buffers (`slot_capacity`: `127`, `127`, `1023`) |
| `date_time` | `0x15d3e8..0x15d454` | 19 | Calendar / weekday / time-of-day tokens (`年`, `月`, `日`, etc.) |
| `save_dialog` | `0x171178..0x171cf8` | 46 | Memory Stick / save / load / autosave / error dialogs (`%d`, `%s`, `%x` preserved) |
| `install_metadata` | `0x171d3c..0x171db0` | 3 | Data Install SFO metadata (`slot_capacity`: `35`, `19`, `59`) |
| `install_dialog` | `0x172124..0x172264` | 2 | Data Install OFF fallback messages (`UMDのみからロードを行います...`) |

**P4 patching note:** Except for `save_metadata`, these strings are tightly packed at 4-byte alignment in `.rodata` (`slot_capacity` is typically `0–3` bytes larger than `byte_len`), so longer English replacements will require pointer relocation into free binary space during P4 EBOOT patching.
