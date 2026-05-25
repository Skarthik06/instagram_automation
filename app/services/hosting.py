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


def publish_images(paths: List[str], commit_msg: str = "Add carousel slides") -> List[str]:
    """Stage, commit and push the given image files; return their raw URLs."""
    if not paths:
        return []
    _, _, branch = _git_cfg()
    try:
        for p in paths:
            _run(["git", "add", p])
        _run(["git", "commit", "-m", commit_msg, "--allow-empty"])
        _run(["git", "push", "origin", branch])
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Git hosting push failed: {detail}") from exc
    return [raw_url(p) for p in paths]
