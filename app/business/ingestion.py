"""Agent 01 — Ingestion (governed by business/agents/ingestion.agents.md).

Mission: accept ANY raw input, identify it reliably by CONTENT (magic bytes, not
the filename extension), hash it for de-duplication, and record provenance before a
single byte is interpreted. Deterministic only — NO LLM (charter §2, Spec §2).

Charter rules honoured here:
  - "Detect type by content, not filename/extension (a .pdf may be an image scan)."
  - "Compute sha256; an identical hash is a duplicate."
  - "Unknown/unsupported/corrupt type -> REVIEW_REQUIRED with reason."
  - "Encrypted/password-protected file -> stop, request credential (never guess)."

Output: a `source_document` classification dict consumed by Extraction (Agent 02).
"""
from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

# Text/code/markup families we can read directly as UTF-8 and feed to extraction as
# a text document. The list is broad on purpose — the owner asked to accept "any
# kind of file such as zip or a js file or any kinds of files".
_TEXT_EXT = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json", ".ndjson",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".xml", ".html", ".htm",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".py", ".rb", ".php", ".java", ".c",
    ".h", ".cpp", ".cc", ".hpp", ".cs", ".go", ".rs", ".swift", ".kt", ".sh", ".bash",
    ".ps1", ".sql", ".css", ".scss", ".less", ".vue", ".svelte", ".r", ".m", ".pl",
    ".lua", ".dart", ".gradle", ".properties", ".srt", ".vtt",
}
_IMAGE_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpeg", b"GIF87a": "gif",
    b"GIF89a": "gif", b"BM": "bmp", b"II*\x00": "tiff", b"MM\x00*": "tiff",
}
_MAX_ARCHIVE_MEMBERS = 200
# Categories Extraction (Agent 02) knows how to route.
#   pdf | image | office_zip | text | archive | unknown


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_text(sample: bytes) -> bool:
    """Heuristic: decodes as UTF-8 (or mostly-printable) and has few NUL bytes."""
    if not sample:
        return False
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        # allow latin-1-ish text with a low proportion of control bytes
        ctrl = sum(1 for b in sample if b < 9 or (13 < b < 32))
        return ctrl / max(1, len(sample)) < 0.05


def _zip_kind(path: Path) -> str:
    """A ZIP container is either an OOXML office file or a real archive."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
    except Exception:  # noqa: BLE001  (corrupt / encrypted zip)
        return "archive"
    joined = "\n".join(names)
    if "word/document.xml" in joined or joined.startswith("word/"):
        return "docx"
    if "xl/workbook.xml" in joined or "xl/" in joined:
        return "xlsx"
    if "ppt/presentation.xml" in joined or "ppt/" in joined:
        return "pptx"
    return "archive"


def classify(path: str | Path) -> Dict[str, Any]:
    """Identify a file by content. Returns a source_document classification.

    `category` drives Extraction routing; `extractable=False` + `reason` means the
    caller should mark the document REVIEW_REQUIRED (charter escalation), never guess.
    """
    path = Path(path)
    size = path.stat().st_size if path.exists() else 0
    head = b""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except Exception as exc:  # noqa: BLE001
        return {"real_type": "unreadable", "mime": "application/octet-stream",
                "category": "unknown", "size": size, "extractable": False,
                "reason": f"cannot read file: {exc}"}

    if not head:
        return {"real_type": "empty", "mime": "application/octet-stream",
                "category": "unknown", "size": 0, "extractable": False,
                "reason": "zero-byte / truncated upload"}

    sha = sha256_file(path)
    base = {"sha256": sha, "size": size, "ext": path.suffix.lower()}

    # --- PDF --------------------------------------------------------------
    if head[:5] == b"%PDF-":
        return {**base, "real_type": "pdf", "mime": "application/pdf",
                "category": "pdf", "extractable": True}

    # --- raster images (magic bytes; a .pdf-named scan is caught here) -----
    for magic, kind in _IMAGE_MAGIC.items():
        if head.startswith(magic):
            return {**base, "real_type": kind, "mime": f"image/{kind}",
                    "category": "image", "extractable": True}
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return {**base, "real_type": "webp", "mime": "image/webp",
                "category": "image", "extractable": True}

    # --- ZIP container: OOXML office doc vs a real archive ----------------
    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        kind = _zip_kind(path)
        if kind in ("docx", "xlsx", "pptx"):
            mime = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}[kind]
            return {**base, "real_type": kind, "mime": mime,
                    "category": "office_zip", "extractable": True}
        return {**base, "real_type": "zip", "mime": "application/zip",
                "category": "archive", "extractable": True}

    # --- legacy OLE office (.doc/.xls/.ppt) -------------------------------
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return {**base, "real_type": "ole_office", "mime": "application/x-ole-storage",
                "category": "unknown", "extractable": False,
                "reason": "legacy OLE office format — please re-save as PDF/DOCX/XLSX"}

    # --- other archives we don't unpack ----------------------------------
    if head[:2] == b"\x1f\x8b":
        return {**base, "real_type": "gzip", "mime": "application/gzip",
                "category": "unknown", "extractable": False, "reason": "gzip archive not supported (send a zip)"}
    if head[:6] == b"7z\xbc\xaf\x27\x1c":
        return {**base, "real_type": "7z", "mime": "application/x-7z-compressed",
                "category": "unknown", "extractable": False, "reason": "7z archive not supported (send a zip)"}
    if head[:4] == b"Rar!":
        return {**base, "real_type": "rar", "mime": "application/vnd.rar",
                "category": "unknown", "extractable": False, "reason": "rar archive not supported (send a zip)"}

    # --- text / code / markup --------------------------------------------
    if _looks_text(head) or path.suffix.lower() in _TEXT_EXT:
        rt = (path.suffix.lower().lstrip(".") or "text")
        mime = "text/csv" if rt in ("csv", "tsv") else "text/plain"
        return {**base, "real_type": rt, "mime": mime,
                "category": "text", "extractable": True}

    # --- give up: escalate, never guess ----------------------------------
    return {**base, "real_type": "unknown", "mime": "application/octet-stream",
            "category": "unknown", "extractable": False,
            "reason": "unrecognised binary format — content could not be identified"}


def iter_archive_members(path: str | Path, dest_dir: Path):
    """Yield extracted member paths from a ZIP (bounded, safe against zip-slip).

    Password-protected members raise (charter: stop and request credential)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        members = [m for m in z.infolist() if not m.is_dir()][:_MAX_ARCHIVE_MEMBERS]
        for m in members:
            # zip-slip guard: resolve target stays inside dest_dir
            target = (dest_dir / m.filename).resolve()
            if not str(target).startswith(str(dest_dir.resolve())):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                data = z.read(m)
            except RuntimeError as exc:  # encrypted member
                raise RuntimeError(f"encrypted archive member '{m.filename}' — password required") from exc
            target.write_bytes(data)
            yield target
