# utils/image_overlay.py
from PIL import Image, ImageDraw, ImageFont, ImageStat
import textwrap
import os
from utils.config import config

def _get_font(font_path, font_size):
    """Try to use Times New Roman, else fall back safely."""
    try:
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, font_size)
        for name in ["Times New Roman.ttf", "times.ttf", "Times.ttf"]:
            try:
                return ImageFont.truetype(name, font_size)
            except Exception:
                continue
        return ImageFont.truetype("DejaVuSerif-Bold.ttf", font_size)
    except Exception:
        return ImageFont.load_default()


def _resize_for_instagram(image):
    # Deprecated: preserve original aspect ratio by default. Keep for backward compatibility.
    img = image.copy().convert("RGB")
    return img


def _is_dark(image):
    stat = ImageStat.Stat(image)
    brightness = sum(stat.mean[:3]) / 3
    return brightness < 130


def _apply_soft_overlay(image, darkness=0.3):
    """Adds a subtle dark transparent layer to make text more readable."""
    overlay = Image.new("RGBA", image.size, (0, 0, 0, int(255 * darkness)))
    base = image.convert("RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")


def _pad_to_square(img, size=1080, color=(0, 0, 0)):
    """Pad the image to a perfect square canvas (1080x1080) with optional background color."""
    iw, ih = img.size
    if iw == ih:
        return img
    new_img = Image.new("RGB", (size, size), color)
    ratio = min(size / iw, size / ih)
    new_w = int(iw * ratio)
    new_h = int(ih * ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    offset = ((size - new_w) // 2, (size - new_h) // 2)
    new_img.paste(resized, offset)
    return new_img


def overlay_quote_on_image(image, quote, handle="sparkle06.exe", max_width=1080):
    """
    Overlay a quote on the image while preserving aspect ratio.
    - If image is wider than `max_width`, downscale preserving aspect ratio.
    - Add a subtle dark panel behind text for readability.
    - Draw a multi-offset soft shadow for the text.
    - Add Instagram handle at bottom-right.
    """
    cfg = config.get("overlay", {})

    # Convert and optionally downscale
    img = image.copy().convert("RGBA")
    iw, ih = img.size
    if iw > max_width:
        new_h = int((max_width / iw) * ih)
        img = img.resize((max_width, new_h), Image.LANCZOS)
    # apply a very subtle background darkening to improve contrast but keep image visible
    cfg_darkness = cfg.get("darkness", None)
    try:
        darkness_val = float(cfg_darkness) if cfg_darkness is not None else 0.06
    except Exception:
        darkness_val = 0.06
    base = _apply_soft_overlay(img, darkness=darkness_val)
    base = base.convert("RGBA")
    w, h = base.size

    # Prepare text layer
    txt_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    # Font sizing: start from a fraction of image width and shrink until it fits
    base_font_size = int(w * 0.06)
    font_path = cfg.get("font_path", "")
    font = _get_font(font_path, base_font_size)

    # We will attempt to wrap text so it fits within 90% width and up to 60% height
    max_text_w = int(w * 0.9)
    max_text_h = int(h * 0.62)

    # Helper to compute text size in a Pillow-version-safe way
    def _text_size(txt, fnt):
        try:
            return fnt.getsize(txt)
        except Exception:
            try:
                bbox = draw.textbbox((0, 0), txt, font=fnt)
                return (bbox[2] - bbox[0], bbox[3] - bbox[1])
            except Exception:
                try:
                    mask = fnt.getmask(txt)
                    bb = mask.getbbox()
                    if bb:
                        return (bb[2], bb[3])
                except Exception:
                    pass
        return (int(len(txt) * (fnt.size if hasattr(fnt, 'size') else 10) * 0.5),
                (fnt.size if hasattr(fnt, 'size') else 14))

    # Wrap by estimating characters per line using average char width
    def wrap_for_font(fnt):
        avg_w = _text_size("a", fnt)[0]
        if avg_w <= 0:
            avg_w = max(1, int(w * 0.02))
        chars = max(20, int(max_text_w / max(1, avg_w)))
        return textwrap.fill(quote, width=chars)

    wrapped = wrap_for_font(font)
    while True:
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= max_text_w and text_h <= max_text_h:
            break
        base_font_size = int(base_font_size * 0.9)
        if base_font_size < 18:
            break
        font = _get_font(font_path, base_font_size)
        wrapped = wrap_for_font(font)

    padding = int(w * 0.05)
    text_x = int((w - text_w) / 2)
    pos = cfg.get("position", "center")
    if pos == "top":
        text_y = int(h * 0.12)
    elif pos == "bottom":
        text_y = int(h - text_h - padding - int(h * 0.04))
    else:
        text_y = int((h - text_h) / 2)

    rect_x0 = text_x - padding // 2
    rect_y0 = text_y - padding // 2
    rect_x1 = text_x + text_w + padding // 2
    rect_y1 = text_y + text_h + padding // 2
    panel_op = cfg.get("box_opacity", 0.06)
    try:
        panel_op = float(panel_op)
    except Exception:
        panel_op = 0.06
    panel_op = max(0.0, min(1.0, panel_op))
    panel_alpha = max(0, min(255, int(255 * panel_op)))
    panel_color = (0, 0, 0, panel_alpha)

    panel_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel_layer)
    try:
        panel_draw.rounded_rectangle([rect_x0, rect_y0, rect_x1, rect_y1], radius=12, fill=panel_color)
    except Exception:
        panel_draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=panel_color)

    txt_layer = Image.alpha_composite(txt_layer, panel_layer)
    draw = ImageDraw.Draw(txt_layer)

    shadow_color = (0, 0, 0, 220)
    text_color = (255, 255, 255, 255)
    offsets = [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 0)]
    y = text_y
    lines = wrapped.split("\n")
    line_h = _text_size("Ay", font)[1]
    for line in lines:
        for ox, oy in offsets:
            fill = shadow_color if (ox, oy) != (0, 0) else text_color
            draw.text((text_x + ox, y + oy), line, font=font, fill=fill)
        y += line_h + 6

    handle_font = _get_font(font_path, max(14, int(w * 0.028)))
    handle_txt = f"@{handle}"
    hw, hh = _text_size(handle_txt, handle_font)
    hx = w - hw - padding
    hy = h - hh - padding
    for ox, oy in offsets:
        fill = shadow_color if (ox, oy) != (0, 0) else (255, 255, 255, 230)
        draw.text((hx + ox, hy + oy), handle_txt, font=handle_font, fill=fill)

    out = Image.alpha_composite(base.convert("RGBA"), txt_layer).convert("RGB")

    # ✅ Fix: pad to 1080x1080 so Instagram doesn’t crop it
    out = _pad_to_square(out, size=1080)

    return out


def save_image_with_quote(img, quote, out_path, handle="sparkle06.exe"):
    final_img = overlay_quote_on_image(img, quote, handle=handle)
    final_img.save(out_path, format="JPEG", quality=95)
    return out_path
