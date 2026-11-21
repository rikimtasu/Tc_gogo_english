# Source Baseline (`reports/source.md`)

Recorded during Phase **P0** (2026-11-21). All patches must target this exact dump.

## Disc & Core Binaries

| File | Size (bytes) | SHA-256 | Notes |
|---|---:|---|---|
| `Twinkle Crusaders GoGo! (Japan) (v1.01).iso` | 1,808,564,224 | `2025c8df4e642a65ae27da422eefb81c34f71028c425e848e5124d34a1669f7e` | Source UMD ISO (read-only) |
| `ULJS00316_EBOOT.BIN` (`work/eboot/EBOOT_decrypted.bin`) | 1,527,040 | `96f2556cad518943ab0203f2ffe7d471b92e29fae4f8a7fab62a577355ca3de8` | Decrypted ELF32 MIPS32 LE executable supplied by project lead |
| `PSP_GAME/USRDIR/DISK1/GAMEINIT.CPK` | 9,659,944 | `20387f20f9972667f9c2e28fd5d628832c6cdb20f3ac9be2550b06fc496f27b8` | Main scenario, font, and system UI CPK |
| `PSP_GAME/PARAM.SFO` | 560 | `91af0700ac25313e2c0ca631403d9f908a62fcc20d5dcf08942e9ca13c6bf902` | Disc metadata |

## `PARAM.SFO` Metadata

- **DISC_ID:** `ULJS00316`
- **TITLE:** `ティンクル☆くるせいだーす GoGo!`
- **DISC_VERSION:** `1.01`
- **APP_VER:** `01.00`
- **PSP_SYSTEM_VER:** `6.31`
- **CATEGORY:** `UG` (`BOOTABLE = 1`, `REGION = 32768`)
