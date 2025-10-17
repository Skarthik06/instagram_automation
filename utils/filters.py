from PIL import Image, ImageDraw, ImageFont, ImageOps
import pytesseract
import io
import requests
import os
import hashlib
from utils.config import config
import textwrap

def _image_bytes_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()

def has_visible_text(image: Image.Image, min_chars=3) -> bool:
    try:
        gray = image.convert("L")
        txt = pytesseract.image_to_string(gray).strip()
        return len([c for c in txt if c.isalnum()]) >= min_chars
    except Exception:
        return False

def has_watermark(image: Image.Image) -> bool:
    return has_visible_text(image)

def is_duplicate_image_url(image_url: str, seen_urls: set) -> bool:
    return image_url in seen_urls

def download_image_bytes(url, timeout=6):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; InstaBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.content
