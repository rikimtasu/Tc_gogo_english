# Twinkle☆Crusaders GoGo! (PSP) — English Translation

Fan translation project for **Twinkle☆Crusaders GoGo!** (PSP, `ULJS-00316`, `v1.01`).

> **Note:** This repository contains translation tools, glossaries, style documentation, and open-licensed font assets only. No copyrighted game files, ISOs, or decrypted binaries are included.

## Project Decisions & Conventions
- **Scope:** *Twinkle☆Crusaders GoGo!* (main disc only; *STARLIT BRAVE!!* bonus UMD deferred).
- **Honorifics & Name Order:** Original Japanese honorifics retained (`-san`, `-senpai`, `-sensei`, `-chan`, `-kun`, `-sama`, `Kaichou-han`); given-name-first order (*Synn Sakura*).
- **Translation Pipeline:** GalTransl MTL first draft using curated dictionaries followed by full human editing and QA.
- **Technical Approach:** MIPS32 proportional word-wrapping patch in `EBOOT.BIN` paired with bitmap font atlases generated from **NewGoStyle-Ver1.000**.

## Repository Structure
- `docs/` — [Project plan](docs/translation_project_plan.md)
- `glossary/` — [Character glossary](glossary/characters.md), [GalTransl character dictionary](glossary/gpt_dict_characters.txt), and VNDB source JSON
- `tools/recon/` — Read-only container inspection utilities (e.g., `cpk_toc.py`)
- `NewGoStyle-Ver1.000/` — Hybrid Japanese/alphanumeric font by isMe (SIL Open Font License 1.1)

## Credits & Licenses
- **NewGoStyle-Ver1.000** (`ニューゴスタイル`): Copyright (c) 2026 isMe (based on GenEi M Go v2.0 and Console Square Beta), licensed under **SIL Open Font License 1.1**. See `NewGoStyle-Ver1.000/OFL.txt` and `NewGoStyle-Ver1.000/THIRD_PARTY_NOTICES.txt`.
