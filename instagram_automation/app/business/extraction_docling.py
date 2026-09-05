"""Optional Docling adapter (Agent 02, enhanced layout extraction).

Docling (MIT) gives superior reading order, table structure, and built-in OCR for
messy/scanned PDFs. It is HEAVY (pulls torch + models), so it is OFF by default and
enabled only via BUSINESS_USE_DOCLING=1 with the package installed
(`pip install -r requirements-docling.txt`).

Strategy: reuse the deterministic base extractor for image crops + provenance, then
overlay Docling's cleaner per-page text. Any API/availability issue falls back to
the base bundle — the pipeline never breaks.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

from app.business.extraction import ExtractionBundle, extract_pdf


def _docling_page_texts(path: Path) -> Dict[int, str]:
    """Return {page_no: text} from Docling, or {} if unavailable."""
    from docling.document_converter import DocumentConverter  # lazy, optional

    conv = DocumentConverter()
    result = conv.convert(str(path))
    doc = result.document
    pages: Dict[int, list] = defaultdict(list)
    for item in getattr(doc, "texts", []) or []:
        text = (getattr(item, "text", "") or "").strip()
        if not text:
            continue
        placed = False
        for prov in getattr(item, "prov", []) or []:
            pno = getattr(prov, "page_no", None)
            if pno is not None:
                pages[int(pno)].append(text)
                placed = True
        if not placed:
            pages[1].append(text)
    return {p: "\n".join(v) for p, v in pages.items()}


def overlay_docling(bundle: ExtractionBundle, path: str | Path) -> ExtractionBundle:
    """Overlay Docling's cleaner per-page text onto an existing base bundle (keeps the
    base's real image crops + provenance). Falls back to the base bundle on any error."""
    try:
        page_texts = _docling_page_texts(Path(path))
    except Exception as exc:  # noqa: BLE001
        print(f"[docling] unavailable, using base extractor: {exc}")
        return bundle
    improved = 0
    for pg in bundle.pages:
        dt = page_texts.get(pg.page)
        if dt and len(dt.strip()) > len(pg.text.strip()):
            pg.text = dt
            pg.method = "docling"
            improved += 1
    bundle.full_text = "\n\n".join(p.text for p in bundle.pages)
    bundle.trace["method"] = f"docling({improved}/{len(bundle.pages)} pages) + pdfium crops"
    bundle.trace["docling"] = True
    return bundle


def extract_pdf_docling(path: str | Path, *, out_dir: Path,
                        cdn_prefix: str) -> Optional[ExtractionBundle]:
    path = Path(path)
    bundle = extract_pdf(path, out_dir=out_dir, cdn_prefix=cdn_prefix)
    return overlay_docling(bundle, path)
