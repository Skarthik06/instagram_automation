"""Deterministic grammar/capitalization polish for on-slide + caption text.

The LLM often returns lowercase, casual copy ("schools nearby", "family first living").
This makes it read professionally WITHOUT destroying real acronyms (BHK, RERA, BBMP)
or numbers. Pure, no AI.
"""
from __future__ import annotations

import re

# Acronyms / brand casings to preserve or force, checked case-insensitively.
_FORCE = {
    "bhk": "BHK", "rera": "RERA", "bbmp": "BBMP", "cctv": "CCTV", "emi": "EMI",
    "nri": "NRI", "kva": "KVA", "sqft": "sq ft", "2bhk": "2 BHK", "3bhk": "3 BHK",
    "id": "ID", "faq": "FAQ", "dm": "DM", "cta": "CTA", "pdf": "PDF",
}
_SENTENCE_SPLIT = re.compile(r"([.!?]\s+)")


def _cap_first_alpha(s: str) -> str:
    for i, ch in enumerate(s):
        if ch.isalpha():
            return s[:i] + ch.upper() + s[i + 1:]
        if ch.isdigit():
            return s
    return s


def _fix_words(s: str) -> str:
    def repl(m):
        w = m.group(0)
        low = w.lower()
        if low in _FORCE:
            return _FORCE[low]
        if low == "i":
            return "I"
        return w
    return re.sub(r"[A-Za-z][A-Za-z]*", repl, s)


def polish(text: str) -> str:
    """Sentence-case a short line (headline/subheadline/fact), fixing acronyms + 'i'."""
    if not text:
        return text
    t = re.sub(r"\s+", " ", text).strip()
    parts = _SENTENCE_SPLIT.split(t)          # keep the separators
    out = "".join(_cap_first_alpha(p) if i % 2 == 0 else p for i, p in enumerate(parts))
    return _fix_words(out)


def polish_caption(text: str) -> str:
    """Polish a multi-line caption: capitalize each line + each sentence, fix acronyms.
    Blank lines and emoji lines are preserved."""
    if not text:
        return text
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join(polish(ln) if ln.strip() else ln for ln in lines)


# Unicode "bold" (mathematical sans-serif bold) for the caption hook — Instagram
# captions are plain text, so this is the only way to emphasize a line.
_BOLD_UPPER = {c: chr(0x1D5D4 + i) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
_BOLD_LOWER = {c: chr(0x1D5EE + i) for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
_BOLD_DIGIT = {c: chr(0x1D7EC + i) for i, c in enumerate("0123456789")}


def bold(text: str) -> str:
    """Convert ASCII letters/digits to Unicode bold (for a caption hook line)."""
    m = {**_BOLD_UPPER, **_BOLD_LOWER, **_BOLD_DIGIT}
    return "".join(m.get(ch, ch) for ch in (text or ""))
