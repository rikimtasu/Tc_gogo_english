# Changelog

## 1.0, updated 17 November 2026

Rounder stroke ends. Same version, same file names, same metrics: replace the files and nothing else changes.

- **Every stroke end is now one full circle.** The flat ends are gone (the hook of f, the ear of g, the tail of t, the foot of a, the upper end of the italic s), and so are the shoulders where a cap met a curved stroke (c, e, s, 3, 5).
- **Round ends pass the baseline and the x-height slightly, the way an o does.** A rounded stem no longer looks shorter than the round letters next to it.
- **Wide ends are one arc** (the tops of M, N and A, the bottom of V), and outer corners are a little rounder.
- **Nothing moves.** Advance widths, kerning and shaping are still identical to Inter at every roundness, and ROND 0 is still Inter.
- **Files are 7 to 9% larger.** The full roman is 899 KB as woff2 (was 843), its Latin subset 257 KB (was 236).

If you load Inrond from jsDelivr at `@v1.0`, the CDN may serve the earlier files for a while.
