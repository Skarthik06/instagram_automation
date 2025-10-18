# utils/filters.py
from PIL import Image, ImageOps
import pytesseract
import requests
import hashlib
import cv2
import numpy as np

STOPWORDS = {"the","a","an","and","or","to","of","in","for","on","with","is","are","be","at","as","that","this","it"}

def _image_bytes_hash(image_bytes: bytes) -> str:
    """Compute SHA256 hash of image bytes"""
    return hashlib.sha256(image_bytes).hexdigest()


def download_image_bytes(url, timeout=6):
    """Download image as bytes with user-agent headers"""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; InstaBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def is_duplicate_image_url(image_url: str, seen_urls: set) -> bool:
    """Check if URL is already seen"""
    return image_url in seen_urls


def has_visible_text(image: Image.Image, min_chars=3) -> bool:
    """
    Detects if image contains visible text using OCR
    Returns True if text length exceeds min_chars
    """
    try:
        gray = image.convert("L")
        txt = pytesseract.image_to_string(gray).strip()
        # Count only alphanumeric characters
        return len([c for c in txt if c.isalnum()]) >= min_chars
    except Exception:
        return False


def has_watermark(image: Image.Image, edge_threshold=0.08, ocr_min_chars=3) -> bool:
    """
    Detects if an image likely contains watermark or visible text.
    Combines edge detection + OCR for better accuracy.
    
    Returns True if image contains text/watermark, else False.
    """
    try:
        # ----- Edge Detection -----
        gray = ImageOps.grayscale(image)
        img_np = np.array(gray)

        # Canny edge detection
        edges = cv2.Canny(img_np, 100, 200)
        edge_density = np.sum(edges > 0) / edges.size

        if edge_density > edge_threshold:
            # Too many edges → likely text overlay
            return True

        # ----- OCR Detection -----
        if has_visible_text(image, min_chars=ocr_min_chars):
            return True

        return False
    except Exception:
        # Fail-safe: if error occurs, assume watermark to avoid bad posts
        return True
