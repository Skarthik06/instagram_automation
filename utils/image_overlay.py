# utils/image_overlay.py
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os
from utils.config import config


def _get_font(font_path, font_size):
    """Try to load custom font, fallback to PIL default."""
    try:
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, font_size)
    except Exception:
        pass
    try:
        return ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        return ImageFont.load_default()


def overlay_quote_on_image(image: Image.Image, quote: str, out_width: int = None) -> Image.Image:
    """
    Draws the quote text over the image using a semi-transparent background box.
    Returns a new Image object (RGB).
    """
    cfg = config.get("overlay", {})
    font_path = cfg.get("font_path", "")
    font_size = cfg.get("font_size", 46)
    max_width_pct = cfg.get("max_width_pct", 0.85)
    padding = cfg.get("padding", 40)
    box_opacity = cfg.get("box_opacity", 0.48)
    box_padding = cfg.get("box_padding", 20)
    line_spacing = cfg.get("line_spacing", 6)
    text_color = cfg.get("text_color", "#ffffff")
    position = cfg.get("position", "center")

    img = image.convert("RGB")
    w, h = img.size
    if out_width and out_width != w:
        new_h = int(h * (out_width / w))
        img = img.resize((out_width, new_h), Image.LANCZOS)
        w, h = img.size

    draw = ImageDraw.Draw(img)
    font = _get_font(font_path, font_size)

    # Compute text wrapping
    max_text_width = int(w * max_width_pct)
    avg_char_width = font.getbbox("x")[2] if hasattr(font, "getbbox") else font.getsize("x")[0]
    if avg_char_width <= 0:
        avg_char_width = font_size * 0.5
    approx_chars_per_line = max(20, int(max_text_width / avg_char_width))
    wrapped = textwrap.fill(quote, width=approx_chars_per_line)
    lines = wrapped.splitlines()

    # Measure text block
    line_heights = []
    max_line_w = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font) if hasattr(draw, "textbbox") else None
        if bbox:
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
        else:
            lw, lh = draw.textsize(line, font=font)
        line_heights.append(lh)
        max_line_w = max(max_line_w, lw)

    text_block_h = sum(line_heights) + (len(lines) - 1) * line_spacing
    text_block_w = max_line_w

    box_w = text_block_w + box_padding * 2
    box_h = text_block_h + box_padding * 2

    # Box position
    if position == "center":
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2
    elif position == "bottom":
        box_x = (w - box_w) // 2
        box_y = h - box_h - padding
    elif position == "top":
        box_x = (w - box_w) // 2
        box_y = padding
    else:
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2

    # Semi-transparent box
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ovdraw = ImageDraw.Draw(overlay)
    box_color = (0, 0, 0, int(255 * box_opacity))
    ovdraw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=16,
        fill=box_color,
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # Draw text
    draw = ImageDraw.Draw(img)
    text_x = box_x + box_padding
    text_y = box_y + box_padding
    for idx, line in enumerate(lines):
        draw.text((text_x, text_y), line, font=font, fill=text_color)
        text_y += line_heights[idx] + line_spacing

    return img


def save_image_with_quote(img: Image.Image, quote: str, out_path: str):
    """Convenience function to overlay quote and save image."""
    final_img = overlay_quote_on_image(img, quote)
    final_img.save(out_path, format="JPEG", quality=92)
    return out_path
