# utils/image_overlay.py
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageFilter
import textwrap
import os
from utils.config import config

INSTAGRAM_SQUARE = (1080, 1080)

def _get_font(font_path, font_size):
    # Prefer Times New Roman if available
    try:
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, font_size)
        # Try Times New Roman or similar serif
        for name in ["Times New Roman.ttf", "times.ttf", "Times.ttf"]:
            try:
                return ImageFont.truetype(name, font_size)
            except:
                continue
        # fallback
        return ImageFont.truetype("DejaVuSerif-Bold.ttf", font_size)
    except:
        return ImageFont.load_default()

def _resize_for_instagram(image):
    img = image.copy().convert("RGB")
    img.thumbnail(INSTAGRAM_SQUARE, Image.LANCZOS)
    new_img = Image.new("RGB", INSTAGRAM_SQUARE, (0, 0, 0))
    w, h = img.size
    new_img.paste(img, ((INSTAGRAM_SQUARE[0] - w)//2, (INSTAGRAM_SQUARE[1] - h)//2))
    return new_img

def _is_dark(image):
    stat = ImageStat.Stat(image)
    brightness = sum(stat.mean[:3]) / 3
    return brightness < 130

def _apply_soft_overlay(image, darkness=0.3):
    """Adds a subtle dark transparent layer to make text more readable."""
    overlay = Image.new("RGB", image.size, (0, 0, 0))
    return Image.blend(image, overlay, darkness)

def overlay_quote_on_image(image, quote):
    cfg = config.get("overlay", {})
    base_font_size = cfg.get("font_size", 52)
    padding = cfg.get("padding", 40)
    text_color = cfg.get("text_color", "#ffffff")

    # Step 1: resize & soften background
    img = _resize_for_instagram(image)
    img = _apply_soft_overlay(img, 0.25)
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # Step 2: dynamically adjust font size
    font = _get_font(cfg.get("font_path", ""), base_font_size)
    max_width = int(w * 0.8)
    max_height = int(h * 0.65)
    wrapped = textwrap.fill(quote, width=40)

    while True:
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if text_w <= max_width and text_h <= max_height:
            break
        base_font_size -= 2
        if base_font_size < 32:
            break
        font = _get_font(cfg.get("font_path", ""), base_font_size)
        wrapped = textwrap.fill(quote, width=int(40 * 52 / base_font_size))

    # Step 3: position text slightly above center (visually pleasing)
    text_x = (w - text_w) / 2
    text_y = (h - text_h) / 2.5  # slightly higher than center

    # Step 4: text shadow (for better visibility)
    shadow_offset = 3
    shadow_color = "black" if _is_dark(img) else "white"
    for dx in (-shadow_offset, shadow_offset):
        for dy in (-shadow_offset, shadow_offset):
            draw.multiline_text(
                (text_x + dx, text_y + dy),
                wrapped,
                font=font,
                fill=shadow_color,
                spacing=10,
                align="center",
            )

    # Step 5: main text
    text_color = "#ffffff" if _is_dark(img) else "#000000"
    draw.multiline_text(
        (text_x, text_y),
        wrapped,
        font=font,
        fill=text_color,
        spacing=10,
        align="center"
    )

    return img

def save_image_with_quote(img, quote, out_path):
    final_img = overlay_quote_on_image(img, quote)
    final_img.save(out_path, format="JPEG", quality=95)
    return out_path
