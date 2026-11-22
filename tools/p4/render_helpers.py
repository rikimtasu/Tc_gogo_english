"""Shared high-DPI (4x supersampled) PIL rendering helpers for P4 UI texture localization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_WIN_UI_FONT = Path(r"C:\Windows\Fonts\segoeuib.ttf")
_FALLBACK_FONT = Path("BarlowSemiCondensed/BarlowSemiCondensed-Medium.ttf")
DEFAULT_FONT = _WIN_UI_FONT if _WIN_UI_FONT.is_file() else _FALLBACK_FONT


def load_font(size: int, font_path: Path = DEFAULT_FONT) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path), size)


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: int,
    start_size: int,
    min_size: int = 8,
    font_path: Path = DEFAULT_FONT,
) -> ImageFont.FreeTypeFont:
    """Find the largest font size <= start_size that fits within max_w."""
    for sz in range(start_size, min_size - 1, -1):
        font = load_font(sz, font_path)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_w:
            return font
    return load_font(min_size, font_path)


def draw_outlined_text(
    img: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_fill: tuple[int, int, int, int] = (24, 120, 232, 255),
    stroke_width: float = 1.25,
    anchor: str = "lt",
    supersample: int = 4,
) -> None:
    """Draw crisp, uniform 4x-supersampled outlined text onto an RGBA image."""
    if not text:
        return
    font_path = getattr(font, "path", str(DEFAULT_FONT))
    base_size = getattr(font, "size", 12)
    ss = max(1, int(supersample))
    hi_font = ImageFont.truetype(str(font_path), max(1, int(round(base_size * ss))))
    hi_sw = max(0, int(round(stroke_width * ss)))

    # Measure in hi-res to render into a tight bounding box (fast even for large images)
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bx0, by0, bx1, by1 = dummy.textbbox((0, 0), text, font=hi_font, stroke_width=hi_sw, anchor=anchor)
    pad = hi_sw + ss * 2
    # Align top-left to an exact multiple of ss so downsampling preserves subpixel placement
    ox = ((bx0 - pad) // ss) * ss
    oy = ((by0 - pad) // ss) * ss
    w_hi = max(ss, (((bx1 + pad - ox) + ss - 1) // ss) * ss)
    h_hi = max(ss, (((by1 + pad - oy) + ss - 1) // ss) * ss)

    hi_canvas = Image.new("RGBA", (w_hi, h_hi), (0, 0, 0, 0))
    hi_draw = ImageDraw.Draw(hi_canvas)
    hi_draw.text(
        (-ox, -oy),
        text,
        font=hi_font,
        fill=fill,
        stroke_width=hi_sw,
        stroke_fill=stroke_fill if hi_sw > 0 else None,
        anchor=anchor,
    )
    lo_patch = hi_canvas.resize((w_hi // ss, h_hi // ss), Image.Resampling.LANCZOS) if ss > 1 else hi_canvas
    dst_x = xy[0] + (ox // ss)
    dst_y = xy[1] + (oy // ss)
    img.alpha_composite(lo_patch, (dst_x, dst_y))


def draw_gradient_outlined_text(
    img: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    top_color: tuple[int, int, int],
    bot_color: tuple[int, int, int],
    stroke_fill: tuple[int, int, int, int] = (24, 120, 232, 255),
    stroke_width: float = 1.75,
    anchor: str = "lm",
    supersample: int = 4,
) -> None:
    """Draw 4x-supersampled text with a smooth vertical RGB gradient fill and solid outline."""
    if not text:
        return
    font_path = getattr(font, "path", str(DEFAULT_FONT))
    base_size = getattr(font, "size", 12)
    ss = max(1, int(supersample))
    hi_font = ImageFont.truetype(str(font_path), max(1, int(round(base_size * ss))))
    hi_sw = max(0, int(round(stroke_width * ss)))

    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bx0, by0, bx1, by1 = dummy.textbbox((0, 0), text, font=hi_font, stroke_width=hi_sw, anchor=anchor)
    pad = hi_sw + ss * 2
    ox = ((bx0 - pad) // ss) * ss
    oy = ((by0 - pad) // ss) * ss
    w_hi = max(ss, (((bx1 + pad - ox) + ss - 1) // ss) * ss)
    h_hi = max(ss, (((by1 + pad - oy) + ss - 1) // ss) * ss)

    hi_canvas = Image.new("RGBA", (w_hi, h_hi), (0, 0, 0, 0))
    hi_draw = ImageDraw.Draw(hi_canvas)
    if hi_sw > 0:
        hi_draw.text(
            (-ox, -oy),
            text,
            font=hi_font,
            fill=stroke_fill,
            stroke_width=hi_sw,
            stroke_fill=stroke_fill,
            anchor=anchor,
        )

    fill_mask = Image.new("RGBA", (w_hi, h_hi), (0, 0, 0, 0))
    ImageDraw.Draw(fill_mask).text((-ox, -oy), text, font=hi_font, fill=(255, 255, 255, 255), anchor=anchor)
    arr = np.array(fill_mask)
    alpha = arr[:, :, 3]
    ys = np.where(alpha > 0)[0]
    if ys.size > 0:
        y0, y1 = int(ys.min()), int(ys.max())
        span = max(1, y1 - y0)
        grad = np.zeros_like(arr)
        for y in range(y0, y1 + 1):
            t = (y - y0) / span
            grad[y, :, 0] = int(top_color[0] * (1 - t) + bot_color[0] * t)
            grad[y, :, 1] = int(top_color[1] * (1 - t) + bot_color[1] * t)
            grad[y, :, 2] = int(top_color[2] * (1 - t) + bot_color[2] * t)
        grad[:, :, 3] = alpha
        hi_canvas.alpha_composite(Image.fromarray(grad, mode="RGBA"))

    lo_patch = hi_canvas.resize((w_hi // ss, h_hi // ss), Image.Resampling.LANCZOS) if ss > 1 else hi_canvas
    dst_x = xy[0] + (ox // ss)
    dst_y = xy[1] + (oy // ss)
    img.alpha_composite(lo_patch, (dst_x, dst_y))


def draw_text_in_box(
    img: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
    start_size: int,
    fill: tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_fill: tuple[int, int, int, int] = (24, 120, 232, 255),
    stroke_width: float = 1.25,
    min_size: int = 7,
    align: str = "center",
    font_path: Path = DEFAULT_FONT,
    baseline: int | None = None,
) -> None:
    """Fit the actual outlined raster into a sprite's half-open UV box.

    Measure after supersampling, including the outline, descenders and filter
    fringe. Never silently crop letters or spill into adjacent atlas cells.
    """
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= img.width and 0 <= y0 < y1 <= img.height):
        raise ValueError(f"Invalid text box: {box} for {img.size}")
    if align not in ("center", "left", "right"):
        raise ValueError(f"Invalid text alignment: {align}")
    if baseline is not None and not y0 <= baseline < y1:
        raise ValueError(f"Baseline {baseline} outside text box: {box}")
    if not text:
        return
    for size in range(start_size, min_size - 1, -1):
        font = load_font(size, font_path)
        # A generous scratch margin keeps measuring independent of the UV box.
        padding = int(stroke_width + 8)
        width = int(font.getlength(text)) + padding * 2 + size * 2
        patch = Image.new("RGBA", (width, size * 3 + padding * 2))
        scratch_baseline = padding + size * 2
        draw_outlined_text(patch, (padding, scratch_baseline), text, font, fill,
                           stroke_fill, stroke_width, anchor="ls")
        pixels = np.array(patch)
        # Remove nearly invisible Lanczos dust, not the visible antialiased edge.
        pixels[pixels[:, :, 3] < 8] = 0
        patch = Image.fromarray(pixels)
        bounds = patch.getbbox()
        if bounds is None:
            return
        patch = patch.crop(bounds)
        if patch.width > x1 - x0 or patch.height > y1 - y0:
            continue
        if align == "left":
            x = x0
        elif align == "right":
            x = x1 - patch.width
        else:
            x = x0 + (x1 - x0 - patch.width) // 2
        y = y0 + (y1 - y0 - patch.height) // 2 if baseline is None else baseline - (scratch_baseline - bounds[1])
        if y < y0 or y + patch.height > y1:
            continue
        img.alpha_composite(patch, (x, y))
        return
    raise ValueError(f"Text does not fit {box} at {min_size}px: {text!r}")


def clear_box(img: Image.Image, box: tuple[int, int, int, int], fill: tuple[int, int, int, int] = (0, 0, 0, 0)) -> None:
    """Clear a rectangular region [x0, y0, x1, y1) with a solid color (default transparent)."""
    d = ImageDraw.Draw(img)
    d.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], fill=fill)


def fill_vertical_gradient_from_col(
    img: Image.Image,
    box: tuple[int, int, int, int],
    sample_x: int,
) -> None:
    """Fill [x0, y0, x1, y1) by replicating the per-row vertical gradient column at sample_x."""
    x0, y0, x1, y1 = box
    arr = np.array(img)
    col = arr[y0:y1, sample_x : sample_x + 1, :]
    arr[y0:y1, x0:x1, :] = col
    img.paste(Image.fromarray(arr[y0:y1, x0:x1, :], mode="RGBA"), (x0, y0))


def inpaint_vertical_dither(
    img: Image.Image,
    box: tuple[int, int, int, int],
) -> None:
    """Inpaint [x0, y0, x1, y1) by interpolating vertically per-column while preserving 2-row dither parity."""
    x0, y0, x1, y1 = box
    arr = np.array(img)
    h_img = arr.shape[0]
    span = max(1, y1 - y0)
    for y in range(y0, y1):
        p = y & 1
        # Nearest row above y0 with same parity p
        ya = y0 - 1 if ((y0 - 1) & 1) == p else y0 - 2
        ya = max(0, ya)
        # Nearest row at/below y1 with same parity p
        yb = y1 if (y1 & 1) == p else min(h_img - 1, y1 + 1)
        yb = min(h_img - 1, yb)
        t = (y - y0) / span
        top_row = arr[ya, x0:x1, :].astype(np.float32)
        bot_row = arr[yb, x0:x1, :].astype(np.float32)
        arr[y, x0:x1, :] = np.clip(top_row * (1.0 - t) + bot_row * t, 0, 255).astype(np.uint8)
    img.paste(Image.fromarray(arr[y0:y1, x0:x1, :], mode="RGBA"), (x0, y0))
