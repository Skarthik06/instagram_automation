"""Public image hosting via GitHub raw.

Instagram's Graph API can only ingest images from a public URL. We host the
slide JPEGs by committing them to the configured PUBLIC repo and serving them
through raw.githubusercontent.com.

Important: only the explicit image paths are staged (`git add <path>`), never
the whole tree — so secrets in `.env` / `posts.db` are never swept into a push.
Pushing happens at PUBLISH time only; previews are served locally before that.
"""
from __future__ import annotations

import base64
import subprocess
from pathlib import Path
from typing import List

import requests

from app import rags, settings


def _git_cfg():
    return (
        (rags.get_setting("github_username") or settings.GITHUB_USERNAME),
        (rags.get_setting("github_repo") or settings.GITHUB_REPO),
        (rags.get_setting("github_branch") or settings.GITHUB_BRANCH),
    )


def _github_token() -> str:
    """Token from the Settings panel (rags) takes precedence over .env."""
    return (rags.get_setting("github_token") or settings.GITHUB_TOKEN or "").strip()


def check_repo_access() -> dict:
    """Verify the configured token can reach the repo -> powers the "Repo connected"
    status in Settings. Never returns the token."""
    user, repo, branch = _git_cfg()
    full = f"{user}/{repo}"
    token = _github_token()
    if not token:
        return {"connected": False, "reason": "no_token", "repo": full, "branch": branch}
    try:
        r = requests.get(f"https://api.github.com/repos/{user}/{repo}",
                         headers={"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"}, timeout=15)
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "reason": str(exc)[:100], "repo": full, "branch": branch}
    if r.status_code == 200:
        body = r.json()
        perms = body.get("permissions") or {}
        return {"connected": True, "repo": full, "branch": branch,
                "private": body.get("private"), "can_push": perms.get("push", True)}
    reason = "bad_token" if r.status_code in (401, 403) else ("repo_not_found" if r.status_code == 404 else f"http_{r.status_code}")
    return {"connected": False, "reason": reason, "repo": full, "branch": branch}


def _upload_via_api(paths: List[str], commit_msg: str) -> List[str]:
    """Upload files with the GitHub Contents API (no local git repo needed — works
    inside the container). Requires a token with `contents:write` on the repo."""
    user, repo, branch = _git_cfg()
    token = _github_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    urls: List[str] = []
    for p in paths:
        rel = Path(p).resolve().relative_to(settings.BASE_DIR).as_posix()
        api = f"https://api.github.com/repos/{user}/{repo}/contents/{rel}"
        # A file that already exists needs its blob sha to be overwritten.
        sha = None
        try:
            g = requests.get(api, params={"ref": branch}, headers=headers, timeout=20)
            if g.status_code == 200:
                sha = g.json().get("sha")
        except Exception:  # noqa: BLE001
            pass
        body = {"message": commit_msg, "branch": branch,
                "content": base64.b64encode(Path(p).read_bytes()).decode("ascii")}
        if sha:
            body["sha"] = sha
        r = requests.put(api, json=body, headers=headers, timeout=45)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"GitHub upload failed ({r.status_code}) for {rel}: {r.text[:200]}")
        urls.append(raw_url(p))
    return urls


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


def _ensure_auth_remote() -> None:
    """If a GITHUB_TOKEN is configured, point origin at an authenticated HTTPS URL
    so `git push` works non-interactively (e.g. inside the backend container)."""
    token = settings.GITHUB_TOKEN
    if not token:
        return
    user, repo, _ = _git_cfg()
    url = f"https://{user}:{token}@github.com/{user}/{repo}.git"
    _run_quiet(["git", "remote", "set-url", "origin", url])


def publish_images(paths: List[str], commit_msg: str = "Add carousel slides") -> List[str]:
    """Publish image files to public hosting and return their raw URLs.

    Prefers the GitHub Contents API (works in-container with a token). Falls back
    to local `git` only when no token is configured (e.g. running on the host)."""
    if not paths:
        return []
    if _github_token():
        return _upload_via_api(paths, commit_msg)
    _, _, branch = _git_cfg()
    _ensure_auth_remote()
    try:
        for p in paths:
            _run(["git", "add", p])
        _run(["git", "commit", "-m", commit_msg, "--allow-empty"])
        _push_with_reconcile(branch)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Git hosting push failed: {detail}") from exc
    return [raw_url(p) for p in paths]
