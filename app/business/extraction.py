"""Extraction stage (Agent 02) — deterministic document understanding.

Digital-PDF path for the MVP (DREAMZ is a digital PDF): pdfplumber for
layout-aware text + word boxes + image regions, pypdfium2 for page rasterization
and real-image crops. No LLM here (Spec §2). Every text span keeps page provenance;
every image region is cropped from the real page so downstream slides use REAL
property images (Spec §15). Ligature/glyph corruption is normalized.

Designed to generalize: scanned/Office inputs plug in as additional loaders behind
the same `ExtractionBundle` contract.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

try:  # OCR optional at import; degrades gracefully
    import pytesseract
except Exception:  # noqa: BLE001
    pytesseract = None

try:
    import cv2
    import numpy as np
except Exception:  # noqa: BLE001
    cv2 = None
    np = None

# Private-use + unicode ligature glyphs seen in real brochures (DREAMZ uses these).
_LIGATURES = {
    "": "fi", "": "fl", "": "ff", "": "ffi", "": "ffl",
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
}
_RENDER_SCALE = 6.0            # ~432 DPI page raster — high-res crops when native fails
_MIN_DIGITAL_CHARS = 40        # below this a page is treated as scanned -> OCR
_OCR_MIN_CONF = 45             # drop OCR words below this confidence
_USE_DOCLING = os.getenv("BUSINESS_USE_DOCLING", "0").strip() not in ("0", "false", "")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def normalize_glyphs(text: str) -> str:
    for bad, good in _LIGATURES.items():
        text = text.replace(bad, good)
    # de-hyphenate line-break splits: "afford-\nable" -> "affordable"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return text


def ocr_available() -> bool:
    return pytesseract is not None


def _variants_for_ocr(pil: Image.Image) -> List[Image.Image]:
    """Return candidate preprocessings: plain grayscale (best on clean renders) and,
    if opencv is present, a denoised adaptive-threshold (best on messy photos)."""
    variants = [pil.convert("L")]
    if cv2 is not None and np is not None:
        arr = cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2GRAY)
        arr = cv2.fastNlMeansDenoising(arr, h=10)
        arr = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 15)
        variants.append(Image.fromarray(arr))
    return variants


def _ocr_one(proc: Image.Image, scale: float) -> Tuple[str, List[Dict[str, Any]], float]:
    """OCR a single preprocessed image -> (text, words, score). score = high-conf char count."""
    try:
        data = pytesseract.image_to_data(proc, output_type=pytesseract.Output.DICT)
    except Exception:  # noqa: BLE001
        return "", [], 0.0
    words: List[Dict[str, Any]] = []
    lines: Dict[Tuple[int, int, int], List[str]] = {}
    score = 0.0
    for i in range(len(data.get("text", []))):
        txt = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not txt or conf < _OCR_MIN_CONF:
            continue
        score += len(txt) * (conf / 100.0)
        x, y = data["left"][i] / scale, data["top"][i] / scale
        w, h = data["width"][i] / scale, data["height"][i] / scale
        words.append({"text": normalize_glyphs(txt),
                      "bbox": [round(x, 1), round(y, 1), round(x + w, 1), round(y + h, 1)],
                      "conf": round(conf, 1)})
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(txt)
    text = "\n".join(" ".join(w) for w in lines.values())
    return normalize_glyphs(text), words, score


def _ocr_image(pil: Image.Image, *, scale: float = 1.0,
               page_num: int = 1) -> Tuple[str, List[Dict[str, Any]]]:
    """OCR a PIL image trying multiple preprocessings, keeping the best-scoring one."""
    if pytesseract is None:
        return "", []
    best_text, best_words, best_score = "", [], -1.0
    for proc in _variants_for_ocr(pil):
        text, words, score = _ocr_one(proc, scale)
        if score > best_score:
            best_text, best_words, best_score = text, words, score
    return best_text, best_words


@dataclass
class ImageRegion:
    page: int
    bbox: List[float]          # [x0, top, x1, bottom] in PDF points
    width: int
    height: int
    storage_ref: str           # path under images/ (served via /cdn)
    cdn_url: str


@dataclass
class PageExtract:
    page: int
    width: float
    height: float
    text: str
    words: List[Dict[str, Any]]
    images: List[ImageRegion]
    method: str = "digital_text"


@dataclass
class ExtractionBundle:
    document: str
    sha256: str
    page_count: int
    pages: List[PageExtract]
    full_text: str = ""
    trace: Dict[str, Any] = field(default_factory=dict)

    def page_tagged_text(self) -> str:
        """Compact, page-labelled text for grounding the entity LLM (Spec §28)."""
        out = []
        for p in self.pages:
            out.append(f"[PAGE {p.page}]\n{p.text.strip()}")
        return "\n\n".join(out)

    def find_span(self, text: str, page: int | None = None) -> bool:
        """Deterministic evidence check: does this span exist in the source?"""
        needle = _norm(text)
        if not needle:
            return False
        if page is not None:
            for p in self.pages:
                if p.page == page and needle in _norm(p.text):
                    return True
            # fall through to global check (LLM may cite the wrong page number)
        return any(needle in _norm(p.text) for p in self.pages)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _native_images(rpage, page_height: float) -> List[Dict[str, Any]]:
    """Extract embedded image objects at their NATIVE resolution (not the page raster).

    Returns [{bbox:(x0,top,x1,bottom in points), pil}]. Best-effort: any pypdfium API
    difference degrades to an empty list so the page-crop path still runs."""
    out: List[Dict[str, Any]] = []
    try:
        import pypdfium2.raw as pdfium_c
        for obj in rpage.get_objects():
            try:
                if obj.type != pdfium_c.FPDF_PAGEOBJ_IMAGE:
                    continue
                pil = obj.get_bitmap(render=False).to_pil().convert("RGB")
                left, bottom, right, top = obj.get_pos()   # points, bottom-left origin
                out.append({"bbox": (left, page_height - top, right, page_height - bottom),
                            "pil": pil})
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return []
    return out


def _match_native(region_bbox, natives: List[Dict[str, Any]]):
    """Find the native image whose position best overlaps a pdfplumber image region."""
    rx0, rtop, rx1, rbot = region_bbox
    ra = max(1.0, (rx1 - rx0) * (rbot - rtop))
    best, best_ov = None, 0.0
    for n in natives:
        nx0, ntop, nx1, nbot = n["bbox"]
        ix0, iy0 = max(rx0, nx0), max(rtop, ntop)
        ix1, iy1 = min(rx1, nx1), min(rbot, nbot)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        ov = (ix1 - ix0) * (iy1 - iy0) / ra
        if ov > best_ov:
            best, best_ov = n, ov
    return best if best_ov >= 0.5 else None


def extract_pdf(path: str | Path, *, out_dir: Path, cdn_prefix: str) -> ExtractionBundle:
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    doc_slug = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    img_dir = out_dir / doc_slug
    img_dir.mkdir(parents=True, exist_ok=True)

    pages: List[PageExtract] = []
    pdf_render = pdfium.PdfDocument(raw)
    try:
        with pdfplumber.open(path) as pdf:
            for idx, pg in enumerate(pdf.pages):
                pnum = idx + 1
                text = normalize_glyphs(pg.extract_text() or "")
                words = [
                    {"text": normalize_glyphs(w.get("text", "")),
                     "bbox": [round(w["x0"], 1), round(w["top"], 1),
                              round(w["x1"], 1), round(w["bottom"], 1)]}
                    for w in pg.extract_words()
                ]
                # Rasterize the page once, then crop each embedded image region.
                rpage = pdf_render[idx]
                bitmap = rpage.render(scale=_RENDER_SCALE)
                pil = bitmap.to_pil().convert("RGB")
                natives = _native_images(rpage, float(pg.height))

                # Scanned / image-only page -> OCR the rasterized page (Spec §7).
                method = "digital_text"
                if len(text.strip()) < _MIN_DIGITAL_CHARS and ocr_available():
                    ocr_text, ocr_words = _ocr_image(pil, scale=_RENDER_SCALE, page_num=pnum)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text, words, method = ocr_text, ocr_words, "ocr"

                regions: List[ImageRegion] = []
                seen = set()
                # For a scanned page the whole page IS the visual — save it as an asset.
                if method == "ocr":
                    name = f"p{pnum:02d}_page.png"
                    pil.save(img_dir / name)
                    regions.append(ImageRegion(
                        page=pnum, bbox=[0, 0, round(pg.width, 1), round(pg.height, 1)],
                        width=round(pg.width), height=round(pg.height),
                        storage_ref=str(img_dir / name),
                        cdn_url=f"{cdn_prefix}/{doc_slug}/{name}",
                    ))
                for k, im in enumerate(pg.images):
                    x0, top = float(im["x0"]), float(im["top"])
                    x1, bottom = float(im["x1"]), float(im["bottom"])
                    w_px, h_px = round(x1 - x0), round(bottom - top)
                    if w_px < 40 or h_px < 40:  # skip tiny decorations
                        continue
                    key = (round(x0), round(top), w_px, h_px)
                    if key in seen:
                        continue
                    seen.add(key)
                    crop = pil.crop((int(x0 * _RENDER_SCALE), int(top * _RENDER_SCALE),
                                     int(x1 * _RENDER_SCALE), int(bottom * _RENDER_SCALE)))
                    # Prefer the NATIVE embedded image when it's higher-resolution than
                    # the page-raster crop (avoids upscaled/blurry small images).
                    native = _match_native((x0, top, x1, bottom), natives)
                    if native and (native["pil"].width * native["pil"].height
                                   > crop.width * crop.height):
                        crop = native["pil"]
                    name = f"p{pnum:02d}_img{k:02d}.png"
                    crop.save(img_dir / name)
                    regions.append(ImageRegion(
                        page=pnum, bbox=[round(x0, 1), round(top, 1), round(x1, 1), round(bottom, 1)],
                        width=crop.width, height=crop.height,   # actual saved pixels
                        storage_ref=str(img_dir / name),
                        cdn_url=f"{cdn_prefix}/{doc_slug}/{name}",
                    ))
                pages.append(PageExtract(
                    page=pnum, width=round(pg.width, 1), height=round(pg.height, 1),
                    text=text, words=words, images=regions, method=method,
                ))
    finally:
        pdf_render.close()

    full = "\n\n".join(p.text for p in pages)
    ocr_pages = sum(1 for p in pages if p.method == "ocr")
    bundle = ExtractionBundle(
        document=path.name, sha256=sha, page_count=len(pages), pages=pages, full_text=full,
    )
    bundle.trace = {
        "agent": "02-extraction", "document": path.name, "pages": len(pages),
        "images": sum(len(p.images) for p in pages),
        "chars": sum(len(p.text) for p in pages),
        "method": f"digital+ocr({ocr_pages}/{len(pages)} pages OCR'd)" if ocr_pages else "digital_text+pdfium",
        "ocr_pages": ocr_pages,
    }
    return bundle


def extract_image(path: str | Path, *, out_dir: Path, cdn_prefix: str) -> ExtractionBundle:
    """OCR a standalone image (screenshot, WhatsApp share, photo of a page)."""
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    doc_slug = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    img_dir = out_dir / doc_slug
    img_dir.mkdir(parents=True, exist_ok=True)

    pil = Image.open(path).convert("RGB")
    text, words = _ocr_image(pil, scale=1.0, page_num=1) if ocr_available() else ("", [])
    name = "p01_page.png"
    pil.save(img_dir / name)
    region = ImageRegion(page=1, bbox=[0, 0, pil.width, pil.height],
                         width=pil.width, height=pil.height,
                         storage_ref=str(img_dir / name),
                         cdn_url=f"{cdn_prefix}/{doc_slug}/{name}")
    page = PageExtract(page=1, width=pil.width, height=pil.height,
                       text=text, words=words, images=[region],
                       method="ocr" if text else "image_only")
    bundle = ExtractionBundle(document=path.name, sha256=sha, page_count=1,
                              pages=[page], full_text=text)
    bundle.trace = {"agent": "02-extraction", "document": path.name, "pages": 1,
                    "images": 1, "chars": len(text), "method": "image_ocr",
                    "ocr_pages": 1 if text else 0}
    return bundle


def _office_text(path: Path) -> str:
    """Best-effort text from an OOXML office file. Uses Docling when available,
    else a light unzip + XML-text-node strip (deterministic, no deps)."""
    if _USE_DOCLING:
        try:
            from docling.document_converter import DocumentConverter
            md = DocumentConverter().convert(str(path)).document.export_to_markdown()
            if md and md.strip():
                return normalize_glyphs(md)
        except Exception:  # noqa: BLE001
            pass
    # Fallback: pull visible text from the document part(s) of the zip.
    import zipfile
    texts: List[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            wanted = [n for n in z.namelist()
                      if n.endswith(".xml") and ("document" in n or "sheet" in n
                      or "slide" in n or "sharedStrings" in n)]
            for n in wanted:
                raw = z.read(n).decode("utf-8", "ignore")
                # text lives in <...>text</...>; strip tags, keep node text
                txt = re.sub(r"<[^>]+>", " ", raw)
                txt = re.sub(r"\s+", " ", txt).strip()
                if txt:
                    texts.append(txt)
    except Exception:  # noqa: BLE001
        pass
    return normalize_glyphs("\n".join(texts))


def extract_text_like(path: str | Path, *, out_dir: Path, cdn_prefix: str,
                      category: str = "text") -> ExtractionBundle:
    """Build a text-only bundle from a text/code/markup file or an office document.

    A JS/JSON/CSV/TXT/DOCX/XLSX becomes source text the Entity agent can reason over;
    it carries no real property images (those only come from PDFs/images)."""
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if category == "office_zip":
        text = _office_text(path)
        method = "office_text"
    else:
        text = ""
        for enc in ("utf-8", "latin-1"):
            try:
                text = raw.decode(enc); break
            except UnicodeDecodeError:
                continue
        text = normalize_glyphs(text)
        method = "plain_text"
    page = PageExtract(page=1, width=0, height=0, text=text, words=[], images=[], method=method)
    bundle = ExtractionBundle(document=path.name, sha256=sha, page_count=1,
                              pages=[page], full_text=text)
    bundle.trace = {"agent": "02-extraction", "document": path.name, "pages": 1,
                    "images": 0, "chars": len(text), "method": method}
    return bundle


def _merge_bundles(document: str, sha: str, parts: List[ExtractionBundle]) -> ExtractionBundle:
    """Combine per-member bundles from an archive into one, renumbering pages."""
    pages: List[PageExtract] = []
    texts: List[str] = []
    total_images = 0
    n = 0
    for b in parts:
        for p in b.pages:
            n += 1
            total_images += len(p.images)
            pages.append(PageExtract(page=n, width=p.width, height=p.height, text=p.text,
                                     words=p.words, images=p.images, method=p.method))
        if b.full_text:
            texts.append(f"[FILE {b.document}]\n{b.full_text}")
    merged = ExtractionBundle(document=document, sha256=sha, page_count=len(pages),
                              pages=pages, full_text="\n\n".join(texts))
    merged.trace = {"agent": "02-extraction", "document": document, "pages": len(pages),
                    "images": total_images, "chars": len(merged.full_text),
                    "method": "archive", "members": len(parts)}
    return merged


def extract_archive(path: str | Path, *, out_dir: Path, cdn_prefix: str) -> ExtractionBundle:
    """Unpack a ZIP and extract every supported member, merging into one bundle."""
    from app.business import ingestion
    path = Path(path)
    sha = ingestion.sha256_file(path)
    work = out_dir / f"_zip_{sha[:12]}"
    parts: List[ExtractionBundle] = []
    for member in ingestion.iter_archive_members(path, work):
        info = ingestion.classify(member)
        if not info.get("extractable") or info["category"] == "archive":
            continue  # skip nested archives + unknowns (charter: don't guess)
        try:
            parts.append(extract_document(member, out_dir=out_dir, cdn_prefix=cdn_prefix))
        except Exception as exc:  # noqa: BLE001
            print(f"[extraction] archive member '{member.name}' skipped: {exc}")
    if not parts:
        raise ValueError("archive contained no extractable documents")
    return _merge_bundles(path.name, sha, parts)


def extract_document(path: str | Path, *, out_dir: Path, cdn_prefix: str) -> ExtractionBundle:
    """Type-aware router driven by Agent-01 Ingestion's CONTENT-based classification
    (not the filename extension). Handles PDF, images, office docs, text/code files,
    and ZIP archives. Unknown/unsupported content raises -> REVIEW_REQUIRED upstream.

    Optionally uses Docling as the primary layout extractor when enabled
    (BUSINESS_USE_DOCLING=1) and installed; always falls back to the built-in
    deterministic path so the pipeline never breaks."""
    from app.business import ingestion
    path = Path(path)
    info = ingestion.classify(path)
    category = info["category"]

    if not info.get("extractable"):
        raise ValueError(f"unsupported/unreadable file ({info.get('real_type')}): "
                         f"{info.get('reason', 'cannot extract')}")
    if category == "image":
        return extract_image(path, out_dir=out_dir, cdn_prefix=cdn_prefix)
    if category == "archive":
        return extract_archive(path, out_dir=out_dir, cdn_prefix=cdn_prefix)
    if category in ("text", "office_zip"):
        return extract_text_like(path, out_dir=out_dir, cdn_prefix=cdn_prefix, category=category)

    # category == "pdf": fast deterministic base pass first.
    bundle = extract_pdf(path, out_dir=out_dir, cdn_prefix=cdn_prefix)

    # Escalate to Docling ONLY when the fast path struggled (scanned / low text) —
    # keeps digital PDFs on the fast, high-accuracy path (Spec §24 cost/quality).
    needs_docling = (bundle.trace.get("ocr_pages", 0) > 0
                     or bundle.trace.get("chars", 0) < 120 * max(1, bundle.page_count))
    if _USE_DOCLING and needs_docling:
        try:
            from app.business.extraction_docling import overlay_docling
            bundle = overlay_docling(bundle, path)
        except Exception as exc:  # noqa: BLE001
            print(f"[extraction] Docling overlay failed, keeping base: {exc}")
    return bundle
