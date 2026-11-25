"""Check translated rows against the dialogue box's pixel width and 3-line budget.

The EBOOT word-wrap patch breaks lines at word boundaries against a per-line
pixel budget. A row whose greedy wrap needs more than three lines is clipped by
the message window, so this check flags it before an ISO build.

Usage:
    python tools/pjadv/check_widths.py --trans gt_output --fonts build/<build>/fonts
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpk import crilayla  # noqa: E402
from font.build_font import parse_w_abc  # noqa: E402

# The dialogue window holds three lines. The pixel budget comes from the
# engine: (slots >> 2) * half_cell, where the original slots allow 52 ASCII
# glyphs per line and half_cell is half the 14px Japanese cell (7px).
DEFAULT_BUDGET_PX = 52 * 7
DEFAULT_LINES = 3
CTRL_RE = re.compile(r"\\[sS]\d{2}")
RUBY_RE = re.compile(r"\\\{([^|]*)\|[^}]*\}")


class Metrics:
    def __init__(self, path: Path) -> None:
        _, self.lut, self.glyphs = parse_w_abc(crilayla.decompress(path.read_bytes()))

    def advance(self, ch: str) -> int:
        try:
            sjis = ch.encode("cp932")
        except UnicodeEncodeError:
            return 7
        if len(sjis) > 1:
            return 14
        code = sjis[0]
        if code >= len(self.lut) or self.lut[code] >= len(self.glyphs):
            return 7
        rec = self.glyphs[self.lut[code]]
        return (rec[4] + rec[5] + rec[6]) or 7


def visible(text: str) -> str:
    """Strip emote codes, resolve ruby to its rendered base text."""
    text = RUBY_RE.sub(r"\1", text)
    return CTRL_RE.sub("", text)


def wrap_lines(text: str, metrics: Metrics, budget: int) -> list[str]:
    """Greedy word wrap mirroring the EBOOT patch, per explicit \\n block."""
    lines: list[str] = []
    for block in text.split("\\n"):
        words = visible(block).split(" ")
        cur = ""
        for word in words:
            candidate = word if not cur else f"{cur} {word}"
            width = sum(metrics.advance(c) for c in candidate)
            if width <= budget or not cur:
                if width <= budget:
                    cur = candidate
                    continue
                # Word alone is too wide: character wrap it.
                if cur:
                    lines.append(cur)
                    cur = ""
                chunk = ""
                for ch in word:
                    if sum(metrics.advance(c) for c in chunk + ch) > budget and chunk:
                        lines.append(chunk)
                        chunk = ch
                    else:
                        chunk += ch
                cur = chunk
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trans", type=Path, default=Path("gt_output"))
    ap.add_argument("--fonts", type=Path, default=Path("build/master_v10/fonts"))
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET_PX)
    ap.add_argument("--lines", type=int, default=DEFAULT_LINES)
    ap.add_argument("--report-all", action="store_true", help="Print every row with its line count")
    args = ap.parse_args()

    metrics = Metrics(args.fonts / "font/sulakyapi12/abc.w_abc")
    failures = 0
    rows_checked = 0
    for path in sorted(args.trans.glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        for index, row in enumerate(rows):
            message = row.get("message", "")
            if not any(ch.isalpha() for ch in visible(message)):
                continue
            rows_checked += 1
            lines = wrap_lines(message, metrics, args.budget)
            width = max((sum(metrics.advance(c) for c in line) for line in lines), default=0)
            if len(lines) > args.lines or width > args.budget:
                failures += 1
                print(f"{path.name}[{index}] {len(lines)} lines, max {width}px "
                      f"(budget {args.budget}px x {args.lines})")
                print(f"    {visible(message)}")
            elif args.report_all:
                print(f"{path.name}[{index}] {len(lines)} lines, max {width}px")
    print(f"\nchecked {rows_checked} rows, {failures} overflow(s), budget {args.budget}px x {args.lines} lines")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
