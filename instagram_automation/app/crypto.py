"""Symmetric encryption for secrets stored in the rags DB.

Instagram access tokens are encrypted with a local Fernet key kept in
`.ragskey` (git-ignored, never committed). This means `posts.db` on its own is
useless to anyone who copies it — the token cannot be read without the key file
that lives only on this machine.

Honest scope: this is encryption *at rest*. Someone with full read access to
this machine can read both the DB and the key, so it is defense-in-depth, not
protection against a fully compromised account. It does protect against the
realistic risks: a leaked/backed-up/accidentally-shared DB file.

Values written by us are prefixed `enc:`. Anything without that prefix is
treated as legacy plaintext and returned as-is (then re-encrypted on next save).
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from app.settings import BASE_DIR

_KEY_FILE = BASE_DIR / ".ragskey"
_PREFIX = "enc:"
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
        try:  # best-effort lock down on POSIX; on Windows ACLs default to the user
            os.chmod(_KEY_FILE, 0o600)
        except OSError:
            pass
    _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    token = _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt(stored: str | None) -> str:
    """Return the plaintext. Legacy unprefixed values pass through unchanged."""
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored  # legacy plaintext
    try:
        return _get_fernet().decrypt(stored[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""  # wrong/missing key — fail closed


def is_encrypted(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(_PREFIX)
