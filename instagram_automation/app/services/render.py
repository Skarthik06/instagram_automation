"""Slide rendering for carousels.

Quotes  -> quote text overlaid on a scraped aesthetic background.
News    -> generated gradient infographic slides (heading + point + source).

All slides are rendered at 1080x1350 (4:5 portrait) so every slide in a
carousel shares one aspect ratio, as the Instagram Graph API requires.
"""
from __future__ import annotations

import os
import textwrap
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app import settings
from app.appconfig import load_config
from app.services.scraper import download_image_bytes


def _hex_rgb(value: str, fallback=(255, 255, 255)) -> tuple:
    try:
        h = value.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback

CANVAS_W, CANVAS_H = 1080, 1350
_FONTS_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"

# Gradient palettes (top, bottom) cycled across posts for variety.
_PALETTES: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = [
    ((24, 24, 51), (12, 12, 28)),       # indigo night
    ((38, 18, 56), (15, 10, 35)),       # plum
    ((10, 36, 48), (8, 18, 28)),        # teal deep
    ((48, 22, 22), (24, 10, 12)),       # ember
    ((18, 38, 28), (8, 20, 16)),        # forest
]
_ACCENTS = [
    (129, 140, 248),  # indigo
    (236, 72, 153),   # pink
    (45, 212, 191),   # teal
    (251, 146, 60),   # orange
    (74, 222, 128),   # green
]


# ===================== fonts =====================

def _font(size: int, *, bold: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont:
    if serif:
        names = ["georgiab.ttf", "georgia.ttf", "times.ttf"] if bold else ["georgia.ttf", "times.ttf"]
    else:
        names = ["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
    for name in names:
        for candidate in (_FONTS_DIR / name, Path(name)):
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """Greedy word-wrap using real glyph widths."""
    words = text.split()
    if not words:
        return [""]
    lines, line = [], words[0]
    for word in words[1:]:
        trial = f"{line} {word}"
        if draw.textlength(trial, font=font) <= max_w:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def _fit_font(
    draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int,
    start: int, *, bold: bool, serif: bool, line_gap: float = 1.25, min_size: int = 26,
) -> Tuple[ImageFont.FreeTypeFont, List[str]]:
    """Shrink the font until wrapped text fits within (max_w, max_h)."""
    size = start
    while size >= min_size:
        font = _font(size, bold=bold, serif=serif)
        lines = _wrap(draw, text, font, max_w)
        line_h = int(font.size * line_gap)
        if len(lines) * line_h <= max_h:
            return font, lines
        size -= 3
    font = _font(min_size, bold=bold, serif=serif)
    return font, _wrap(draw, text, font, max_w)


def _draw_centered_block(
    draw: ImageDraw.ImageDraw, lines: List[str], font: ImageFont.FreeTypeFont,
    cx: int, top: int, fill, *, line_gap: float = 1.25, shadow: bool = False,
) -> int:
    line_h = int(font.size * line_gap)
    y = top
    for line in lines:
        w = draw.textlength(line, font=font)
        x = cx - w / 2
        if shadow:
            for ox, oy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
                draw.text((x + ox, y + oy), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h
    return y


# ===================== backgrounds =====================

def _cover(img: Image.Image, w: int = CANVAS_W, h: int = CANVAS_H) -> Image.Image:
    """Resize+center-crop so the image fully covers the canvas."""
    img = img.convert("RGB")
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _gradient(palette_idx: int) -> Image.Image:
    top, bottom = _PALETTES[palette_idx % len(_PALETTES)]
    ramp = np.linspace(0, 1, CANVAS_H, dtype="float32")[:, None]
    col = (np.array(top) * (1 - ramp) + np.array(bottom) * ramp).astype("uint8")
    arr = np.repeat(col[:, None, :], CANVAS_W, axis=1)
    return Image.fromarray(arr, "RGB")


def _darken(img: Image.Image, amount: float = 0.45) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, int(255 * amount)))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


# ===================== slide renderers =====================

def _render_quote_slide(
    bg: Optional[Image.Image], slide: Dict[str, str], idx: int, total: int,
    handle: str, palette_idx: int, overlay: Dict,
) -> Image.Image:
    if bg is not None:
        base = _darken(_cover(bg), float(overlay.get("darkness", 0.42)))
    else:
        base = _gradient(palette_idx)
    draw = ImageDraw.Draw(base)
    accent = _ACCENTS[palette_idx % len(_ACCENTS)]
    text_color = _hex_rgb(overlay.get("text_color", "#ffffff"))

    margin = 110
    max_w = CANVAS_W - 2 * margin
    heading = (slide.get("heading") or "").upper()
    body = slide.get("body") or ""

    # Heading (small, accent, letter-spaced look via spaces)
    if heading:
        hfont = _font(34, bold=True)
        spaced = " ".join(heading)
        _draw_centered_block(draw, [spaced[:60]], hfont, CANVAS_W // 2, 150, accent, shadow=True)

    # Body quote (serif, large, fitted)
    bfont, lines = _fit_font(draw, body, max_w, 620, 78, bold=False, serif=True, line_gap=1.3)
    line_h = int(bfont.size * 1.3)
    block_h = len(lines) * line_h
    position = overlay.get("position", "center")
    if position == "top":
        top = 330
    elif position == "bottom":
        top = CANVAS_H - block_h - 300
    else:
        top = (CANVAS_H - block_h) // 2
    # decorative quote mark
    qfont = _font(150, bold=True, serif=True)
    draw.text((margin - 10, top - 150), "“", font=qfont, fill=(*accent, 255))
    _draw_centered_block(draw, lines, bfont, CANVAS_W // 2, top, text_color, line_gap=1.3, shadow=True)

    _draw_footer(draw, handle, idx, total, accent)
    return base


def _render_infographic_slide(
    slide: Dict[str, str], idx: int, total: int, handle: str, palette_idx: int,
    bg: Optional[Image.Image] = None,
) -> Image.Image:
    # Photo backdrop (heavily darkened for text legibility) or gradient fallback.
    base = _darken(_cover(bg), 0.66) if bg is not None else _gradient(palette_idx)
    draw = ImageDraw.Draw(base)
    accent = _ACCENTS[palette_idx % len(_ACCENTS)]
    margin = 100
    max_w = CANVAS_W - 2 * margin

    # accent bar top-left
    draw.rounded_rectangle([margin, 120, margin + 90, 132], radius=6, fill=accent)

    heading = (slide.get("heading") or "").upper()
    body = slide.get("body") or ""
    footnote = slide.get("footnote") or ""

    y = 175
    if heading:
        hfont = _font(46, bold=True)
        for line in _wrap(draw, heading, hfont, max_w):
            draw.text((margin, y), line, font=hfont, fill=accent)
            y += int(hfont.size * 1.2)
        y += 24

    bfont, lines = _fit_font(draw, body, max_w, CANVAS_H - y - 240, 64, bold=False, serif=False, line_gap=1.3)
    line_h = int(bfont.size * 1.3)
    for line in lines:
        draw.text((margin, y), line, font=bfont, fill=(245, 245, 250))
        y += line_h

    if footnote:
        ffont = _font(26, bold=False)
        draw.text((margin, CANVAS_H - 150), f"Source: {footnote}", font=ffont, fill=(170, 170, 185))

    _draw_footer(draw, handle, idx, total, accent)
    return base


def _draw_footer(draw: ImageDraw.ImageDraw, handle: str, idx: int, total: int, accent) -> None:
    hfont = _font(28, bold=True)
    draw.text((100, CANVAS_H - 95), f"@{handle}", font=hfont, fill=(210, 210, 220))
    # slide counter pill bottom-right
    label = f"{idx + 1}/{total}"
    pfont = _font(26, bold=True)
    tw = draw.textlength(label, font=pfont)
    x1, y1 = CANVAS_W - 100, CANVAS_H - 100
    x0, y0 = x1 - tw - 36, y1 - 12
    draw.rounded_rectangle([x0, y0, x1, y1 + 40], radius=20, fill=(*accent, 255))
    draw.text((x0 + 18, y0 + 12), label, font=pfont, fill=(15, 15, 25))


# ===================== public API =====================

def render_post_slides(
    *, post: Dict, niche: str, out_dir: Path, post_id: str,
    background_urls: Optional[List[str]] = None, handle: Optional[str] = None,
    palette_idx: int = 0,
) -> List[str]:
    """Render all slides for one post; return saved JPEG file paths in order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay = load_config()["overlay"]
    handle = handle or overlay.get("handle") or settings.DEFAULT_HANDLE
    slides = post.get("slides", [])
    bgs: List[Optional[Image.Image]] = []
    if background_urls:  # both niches use backgrounds now
        for url in background_urls:
            try:
                bgs.append(Image.open(BytesIO(download_image_bytes(url))).convert("RGB"))
            except Exception:
                bgs.append(None)

    paths: List[str] = []
    total = len(slides)
    for i, slide in enumerate(slides):
        bg = bgs[i % len(bgs)] if bgs else None
        if niche == "news":
            img = _render_infographic_slide(slide, i, total, handle, palette_idx, bg)
        else:
            img = _render_quote_slide(bg, slide, i, total, handle, palette_idx, overlay)
        path = out_dir / f"slide_{post_id}_{i + 1}.jpg"
        img.save(path, format="JPEG", quality=92)
        paths.append(str(path))
    return paths
