# Inrond

**Inter, with a roundness axis.** One variable font that goes from Inter to fully round, at every weight, in roman and italic, without moving a single line break.

![Inrond roundness axis](documentation/inrond-roundness.gif)

Inrond is built on [Inter 4.1](https://rsms.me/inter/) by Rasmus Andersson and keeps all of it: 2,937 glyphs, 2,852 characters including Cyrillic and Greek, 39 OpenType features, the optical size axis, the drawn italic, and Inter's metrics and kerning. At `ROND 0` it renders the same as Inter. Turn the axis up and every stroke end and outer corner rounds, up to `ROND 100`.

Rounded takes on Inter already exist (Open Runde, Intern), but each is a separate family frozen at one setting, without italics. A roundness axis already exists too, in Google Sans Flex, but on a different design with Latin only. Inrond is the combination that was missing:

- **Drop-in for Inter.** Advance widths and kerning are identical to Inter at every roundness, so switching, theming or animating never reflows text.
- **Any roundness, not one.** Pick a value, animate it, or bind it to the radius token your buttons and cards use.
- **All of Inter.** Cyrillic, Greek, Vietnamese, 39 features, optical sizes and a real italic, all rounded by the same rule.
- **Pay only for what you use.** If you want one roundness, ship a frozen build at about 1.6 times the size of Inter instead of the full axis.

![Roundness steps](documentation/inrond-ramp.png)

## Use

### From a CDN

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/Hairline-UI/inrond@v1.0/fonts/webfonts/inrond.css">
<!-- frozen builds: inrond-round.css (ROND 100, family "Inrond Round"), inrond-soft.css (ROND 50, family "Inrond Soft") -->
```

The stylesheet uses unicode-range subsets, so a Latin page downloads only the Latin file.

### Self-hosted

Download the [latest release](https://github.com/Hairline-UI/inrond/releases/latest) and copy `fonts/webfonts/` into your site.

```css
@font-face {
  font-family: "Inrond";
  src: url("Inrond[ROND,opsz,wght].woff2") format("woff2");
  font-weight: 100 900;
  font-display: swap;
}
@font-face {
  font-family: "Inrond";
  src: url("Inrond-Italic[ROND,opsz,wght].woff2") format("woff2");
  font-weight: 100 900;
  font-style: italic;
  font-display: swap;
}

body {
  font-family: "Inrond", sans-serif;
  font-variation-settings: "ROND" 60;   /* 0 sharp, 100 round */
}
```

One token for components and type:

```css
:root {
  --round: 60;                              /* 0 to 100 */
  --radius: calc(var(--round) * 0.22px);    /* 13.2px */
}
body            { font-variation-settings: "ROND" var(--round); }
.button, .card  { border-radius: var(--radius); }
```

It animates like weight does, and text never reflows, because advance widths and kerning are identical at every roundness:

```css
a       { font-variation-settings: "ROND" 0; transition: font-variation-settings .25s; }
a:hover { font-variation-settings: "ROND" 100; }
```

`fonts/webfonts/inrond.css` loads unicode-range subsets (Latin, Latin Extended, Vietnamese, Cyrillic, Greek) so a page only downloads what it uses.

### One roundness only

A site that uses a single roundness does not need the axis on the wire. Two frozen builds ship ready to use, each still variable in weight and optical size:

```html
<link rel="stylesheet" href="fonts/webfonts/inrond-round.css">   <!-- ROND 100, family "Inrond Round" -->
<link rel="stylesheet" href="fonts/webfonts/inrond-soft.css">    <!-- ROND 50,  family "Inrond Soft"  -->
```

For any other value, freeze your own:

```bash
python scripts/pin.py 60
```

That writes `fonts/custom/Inrond60[opsz,wght].woff2`, the italic, the subsets and a css file.

Open `specimen/index.html` through a local server to try everything interactively.

## Files

| Folder | Contents |
| --- | --- |
| `fonts/variable/` | `Inrond[ROND,opsz,wght].ttf` and `Inrond-Italic[ROND,opsz,wght].ttf` (everything), plus the frozen `InrondRound[opsz,wght].ttf` and `InrondSoft[opsz,wght].ttf` with their italics |
| `fonts/webfonts/` | All six as woff2, unicode-range subsets of each, `inrond.css`, `inrond-round.css`, `inrond-soft.css` |
| `fonts/static/` | Inrond Soft (ROND 50) and Inrond Round (ROND 100), nine weights, roman and italic, for apps without variable font support |
| `site/` | The landing page (Next.js, static export), set in the real webfonts |
| `qa/` | Verification and FontBakery reports |

| Axis | Tag | Range | Default |
| --- | --- | --- | --- |
| Roundness | `ROND` | 0 to 100 | 0 |
| Weight | `wght` | 100 to 900 | 400 |
| Optical size | `opsz` | 14 to 32 | 14 |

## How it compares

Read from the released font files with fontTools on 14 November 2026 (`tools/bench.py`).

| | Inrond 1.0 | Inter 4.1 | Intern 1.0 | Goeist 0.0.2 | Open Runde 1.0.1 | Google Sans Flex |
| --- | --- | --- | --- | --- | --- | --- |
| Roundness | Axis, 0 to 100 | None | Fixed | Fixed | Fixed | Axis, 0 to 100 |
| Glyphs | 2,937 | 2,937 | 1,087 | 975 | 2,549 | 686 |
| Unicode characters | 2,852 | 2,852 | 541 | 728 | 2,512 | 541 |
| Cyrillic / Greek | 249 / 105 | 249 / 105 | 0 / 0 | 134 / 5 | 256 / 121 | 0 / 1 |
| Italic | Drawn | Drawn | No | Yes | No | Slant axis |
| Weight | 100 to 900 axis | 100 to 900 axis | 100 to 900 axis | 100 to 900 axis | 4 static | 1 to 1000 axis |
| Optical size | 14 to 32 axis | 14 to 32 axis | 14 to 32 axis | No | No | 1 to 144 axis |
| OpenType features | 39 | 39 | 33 | 26 | 6 | 20 |
| Full roman, woff2 | 899 KB | 344 KB | 170 KB | 87 KB | 151 KB per weight | 1,418 KB |

### What it costs

The price of the axis is file size. Same subsetter settings for every row, woff2, roman:

| Build | Latin subset | Full font |
| --- | --- | --- |
| Inter 4.1 | 103 KB | 344 KB |
| Inrond, roundness axis live | 257 KB | 899 KB |
| Inrond Soft, frozen at ROND 50 | 163 KB | 563 KB |
| Inrond Round, frozen at ROND 100 | 159 KB | 540 KB |

So a page set in Latin downloads 154 KB more than with Inter if it wants the live axis, and about 60 KB more if it freezes one roundness. Rounding roughly doubles the number of outline points, which is why even a frozen build is larger than Inter.

Google Sans Flex stores its roundness axis more compactly: cut down to weight and roundness only, its Latin subset is 70 KB against 155 KB for Inrond with the same two axes. Inrond's case is not size; it is Inter compatibility, coverage and the italic.

## How it is made

Inrond is generated, not redrawn. `scripts/roundlib.py` reads every master of the source and rounds it by one rule, the path a round pen would leave:

- A stroke end gets the circle that touches its two sides and its cut, so it becomes a true round cap. The cap passes the cut slightly, by no more than Inter's own o passes the baseline, so a rounded stem does not look shorter than a round letter.
- An outer corner gets a radius of about half the local stroke width.
- Joins, crotches and counters stay crisp.

The sharp and the round outline of each glyph share one point structure. In the sharp outline every fillet collapses onto its corner; in the round one the same points open into an arc. That is what makes the axis possible. Three things keep it clean between the masters:

1. Where a cap lands on a curve, the join sits where the circle touches the stroke, at the same share between its two handles in every master, so it stays smooth at every weight and roundness in between.
2. Exact outlines at half roundness and at a mid weight are stored as sparse corrections, because a cap's end travels along a curved stroke and plain interpolation would cut that path short.
3. Parts that join other parts (ogonek, cedilla, Cyrillic tails) keep the joining end sharp, and letters that are joined in only a few accented forms get those forms rounded as outlines of their own.

Layout tables, metrics, kerning and anchors are copied from the source untouched.

## Verification

`tests/verify.py` rasterises every glyph with FreeType at 1024 px per em and compares Inrond with Inter at seven weight and optical size locations. Full reports are in `qa/`.

| Check | Roman | Italic |
| --- | --- | --- |
| Glyphs compared | 2,915 | 2,879 |
| 1. Sharp: largest difference to Inter at ROND 0 | 0 px | 0 px |
| 2. Inside: glyphs with ink more than 8 units beyond the overshoot of a round end (Inter's own o overshoot, 20 to 24 units) | 0 | 0 |
| 3. Monotone: glyphs where 10 units of ink or more come back, inside Inter's outline, as roundness grows | 0 | 0 |
| 4. Kinks: glyphs that gain a direction break of 8 degrees or more at ROND 100 | 13 (limit 58) | 18 (limit 57) |
| 5. Metrics: advance widths that differ from Inter | 0 | 0 |
| 6. Shaping: HarfBuzz runs that differ from Inter | 0 of 504 | 0 of 504 |

Both fonts pass every check. Units are font units of a 2048 em, so 8 units is 0.4% of the type size. Deviations under the limits are counted and listed in the reports: round stroke ends pass Inter's outline by up to 24 units, and the fonts gain small direction breaks of 3 to 8 degrees where a growing cap meets a curved stroke.

Two frozen builds were compared with the main fonts at the same roundness at four locations: no glyph of Inrond Round differs by 4 units or more, and 2 of the 2,901 glyphs of Inrond Soft Italic do.

FontBakery, universal profile (`qa/fontbakery-*.md`):

| | FAIL | WARN | PASS |
| --- | --- | --- | --- |
| Inrond roman | 3 | 6 | 98 |
| Inter 4.1 roman | 6 | 4 | 96 |
| Inrond italic | 4 | 6 | 98 |
| Inter 4.1 italic | 7 | 5 | 95 |
| Intern 1.0 | 2 | 4 | 99 |
| Goeist 0.0.2 | 0 | 7 | 99 |

Inrond's three failures are Inter's own and are left alone on purpose: Windows ascent and descent stay equal to Inter's so line height matches, and the other two concern Inter's character set. The italic's fourth is FontBakery noting that it was checked without its roman. Inrond fixes the three that were fixable without changing the design (name length, Mac name records, smart dropout control). Its extra warnings are the file size and, in the roman, FontBakery's interpolation check. Intern and Goeist score better here mainly because they carry a third of the glyphs.

## Known limits

- **File size.** The full roman is about two and a half times Inter (899 KB against 344 KB as woff2). Use the subsets on the web, and a frozen build if you need one roundness.
- **Generated, not hand-drawn.** One rule rounds all 2,937 glyphs. It is consistent and measurable, but nobody has tuned individual letters by eye the way a type designer would.
- **Small direction breaks.** Where a cap meets a curved stroke, the join can show a break of a few degrees. They are largest at weights between the drawn ones (around 700 to 850) and can be seen there at large sizes.
- **Three italic glyphs are rounded less.** The small capital G (ɢ), its hooked form (ʛ) and the cruzeiro sign (₢) get 75% of the normal rounding in the italic, because at Black weight the full amount turned a short arm into a spike.
- **Only tested on Inter.** The generator is written for any TrueType variable font, but Inter is the only one it has been run and verified on.
- **Hinting.** Like Inter's variable fonts, Inrond is unhinted.
- **Name.** The name has not had a formal trademark search. It is set in one place (`scripts/naming.py`).

## Build

```bash
pip install -r requirements.txt
```

```bash
python scripts/release.py
```

```bash
python tests/verify.py sources/InterVariable.ttf "fonts/variable/Inrond[ROND,opsz,wght].ttf"
```

The landing page builds from the same webfonts:

```bash
cd site && npm install && npm run dev
```

A full release takes about ten minutes. `scripts/build.py` adds the axis to one font, `scripts/release.py` produces every shipped file, `scripts/pin.py` freezes a roundness, and `scripts/naming.py` holds the family name and credits.

## License and credits

Inrond is licensed under the [SIL Open Font License 1.1](OFL.txt). It is a derivative of Inter, Copyright 2016 The Inter Project Authors, designed by Rasmus Andersson. Inrond is not affiliated with or endorsed by the Inter project. "Inter" is a trademark of rsms.

The idea of rounded takes on popular UI typefaces owes a debt to Open Runde, Intern and Goeist.
