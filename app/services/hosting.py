"""Public image hosting via GitHub raw.

Instagram's Graph API can only ingest images from a public URL. We host the
slide JPEGs by committing them to the configured PUBLIC repo and serving them
through raw.githubusercontent.com.

Important: only the explicit image paths are staged (`git add <path>`), never
the whole tree — so secrets in `.env` / `posts.db` are never swept into a push.
Pushing happens at PUBLISH time only; previews are served locally before that.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

from app import rags, settings


def _git_cfg():
    return (
        (rags.get_setting("github_username") or settings.GITHUB_USERNAME),
        (rags.get_setting("github_repo") or settings.GITHUB_REPO),
        (rags.get_setting("github_branch") or settings.GITHUB_BRANCH),
    )


def raw_url(local_path: str) -> str:
    user, repo, branch = _git_cfg()
    rel = Path(local_path).resolve().relative_to(settings.BASE_DIR).as_posix()
    return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{rel}"


def preview_url(local_path: str) -> str:
    """Local preview URL served by the backend static mount (no push needed)."""
    rel = Path(local_path).resolve().relative_to(settings.IMAGES_DIR).as_posix()
    return f"/cdn/{rel}"


def _run(args: List[str]) -> None:
    subprocess.run(args, cwd=str(settings.BASE_DIR), check=True, capture_output=True, text=True)


def _run_quiet(args: List[str]) -> bool:
    """Run a git command, swallowing failures. Returns True on success."""
    try:
        _run(args)
        return True
    except subprocess.CalledProcessError:
        return False


def _push_with_reconcile(branch: str) -> None:
    """Push to origin; if the remote moved ahead (another copy/session pushed),
    fetch + rebase our commit on top and retry once.

    Each publish stages uniquely-named slide files, so a rebase can't conflict.
    If it somehow does, we abort the rebase and surface the original error
    rather than leaving the repo mid-rebase.
    """
    if _run_quiet(["git", "push", "origin", branch]):
        return
    _run(["git", "fetch", "origin", branch])
    try:
        _run(["git", "rebase", f"origin/{branch}"])
    except subprocess.CalledProcessError:
        _run_quiet(["git", "rebase", "--abort"])
        raise
    _run(["git", "push", "origin", branch])


def sync() -> bool:
    """Best-effort pull of remote commits so multiple machines stay in step.

    Called before generation so a laptop that's been idle catches up on what
    the other one published, leaving the eventual publish-push with little or
    nothing to reconcile. Never fatal: if offline / no upstream / a rebase
    would conflict, it cleanly aborts and returns False so generation still
    proceeds. `--autostash` keeps any local tracked edits safe; untracked
    preview files are left untouched.
    """
    _, _, branch = _git_cfg()
    if not _run_quiet(["git", "fetch", "origin", branch]):
        return False
    try:
        _run(["git", "rebase", "--autostash", f"origin/{branch}"])
        return True
    except subprocess.CalledProcessError:
        _run_quiet(["git", "rebase", "--abort"])
        return False


def publish_images(paths: List[str], commit_msg: str = "Add carousel slides") -> List[str]:
    """Stage, commit and push the given image files; return their raw URLs."""
    if not paths:
        return []
    _, _, branch = _git_cfg()
    try:
        for p in paths:
            _run(["git", "add", p])
        _run(["git", "commit", "-m", commit_msg, "--allow-empty"])
        _push_with_reconcile(branch)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Git hosting push failed: {detail}") from exc
    return [raw_url(p) for p in paths]
