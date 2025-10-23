# utils/image_overlay.py
from PIL import Image, ImageDraw, ImageFont, ImageStat
import textwrap
import os
from utils.config import config

INSTAGRAM_SQUARE = (1080, 1080)
FOOTER_TEXT = "@sparkle06.exe"

def _get_font(font_path=None, font_size=52):
    """Load a readable font; fall back gracefully."""
    preferred_fonts = [
        "Poppins-SemiBold.ttf",
        "Montserrat-SemiBold.ttf",
        "Arial.ttf",
        "DejaVuSans-Bold.ttf"
    ]
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, font_size)
        except Exception:
            pass
    for name in preferred_fonts:
        try:
            return ImageFont.truetype(name, font_size)
        except Exception:
            continue
    return ImageFont.load_default()


def _resize_for_instagram(image):
    """Resize/pad to 1080x1080 using black borders to preserve composition."""
    img = image.copy().convert("RGB")
    img.thumbnail(INSTAGRAM_SQUARE, Image.LANCZOS)
    new_img = Image.new("RGB", INSTAGRAM_SQUARE, (0, 0, 0))
    w, h = img.size
    new_img.paste(img, ((INSTAGRAM_SQUARE[0] - w)//2, (INSTAGRAM_SQUARE[1] - h)//2))
    return new_img


def overlay_quote_on_image(image, quote):
    cfg = config.get("overlay", {})
    img = _resize_for_instagram(image).convert("RGB")
    w, h = img.size

    # Apply consistent soft dark overlay for contrast
    dark_layer = Image.new("RGB", img.size, (0, 0, 0))
    img = Image.blend(img, dark_layer, 0.35)
    draw = ImageDraw.Draw(img)

    # Base font size depending on quote length (slightly larger overall)
    word_count = len(quote.split())
    if word_count < 10:
        font_size = 120
    elif word_count < 20:
        font_size = 100
    elif word_count < 35:
        font_size = 80
    else:
        font_size = 65

    font = _get_font(cfg.get("font_path", ""), font_size)
    spacing = int(font_size * 0.42)

    # Wrap text dynamically (allow wider layout for better fit)
    max_chars = 38
    wrapped = textwrap.fill(quote, width=max_chars)

    # Measure the wrapped text
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Adjust font if text overflows or is too small
    while (text_w > w * 0.9 or text_h > h * 0.55) and font_size > 42:
        font_size -= 4
        font = _get_font(cfg.get("font_path", ""), font_size)
        spacing = int(font_size * 0.42)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    while text_h < h * 0.25 and font_size < 160:
        font_size += 4
        font = _get_font(cfg.get("font_path", ""), font_size)
        spacing = int(font_size * 0.42)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Center text slightly above middle
    x = (w - text_w) / 2
    y = (h - text_h) / 2.15

    # Draw the main quote
    draw.multiline_text(
        (x, y),
        wrapped,
        font=font,
        fill="#FFFFFF",
        spacing=spacing,
        align="center"
    )

    # Footer text (@sparkle06.exe)
    FOOTER_TEXT = "@sparkle06.exe"
    footer_font = _get_font(cfg.get("font_path", ""), 38)
    fw, fh = draw.textbbox((0, 0), FOOTER_TEXT, font=footer_font)[2:]
    fx, fy = (w - fw) / 2, h - fh - 40
    draw.text((fx, fy), FOOTER_TEXT, font=footer_font, fill="#CFCFCF", align="center")

    return img

def save_image_with_quote(img, quote, out_path):
    final_img = overlay_quote_on_image(img, quote)
    final_img.save(out_path, format="JPEG", qualisty=95)
    return out_path
  #hiii
  