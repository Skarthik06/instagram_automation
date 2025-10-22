# main.py
import asyncio
import random
import os
import io
import subprocess
import time
from llm_quote_gen import generate_unique_quote, create_image_prompt
from playwright_scraper import scrape_pinterest_images
from ig_api_poster import post_to_instagram, _save_local_and_get_hosted_url, build_caption
from utils.db import init_db, get_all_quotes, save_post
from utils.filters import download_image_bytes
from utils.image_overlay import save_image_with_quote
from PIL import Image

# Config
MAX_SCRAPE_ATTEMPTS = 3
IMAGES_PER_ATTEMPT = 6
LOCAL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "images")
PREVIEWS_DIR = os.path.join(LOCAL_OUTPUT_DIR, "previews")
GITHUB_REPO_DIR = os.path.dirname(__file__)
GITHUB_BRANCH = "main"
GIT_PUSH_RETRIES = 3
GIT_RETRY_DELAY = 5


def git_commit_and_push_files(paths, commit_msg="Add Instagram preview images"):
    """Add, commit, and push a list of paths to GitHub in one commit."""
    if not paths:
        return False
    try:
        # ensure relative paths for git add (workdir = repo root)
        for p in paths:
            subprocess.run(["git", "add", p], cwd=GITHUB_REPO_DIR, check=True)
        subprocess.run(["git", "commit", "-m", commit_msg, "--allow-empty"], cwd=GITHUB_REPO_DIR, check=True)
        subprocess.run(["git", "push", "origin", GITHUB_BRANCH], cwd=GITHUB_REPO_DIR, check=True)
        print(f"✅ Committed & pushed {len(paths)} file(s) to GitHub.")
        # small delay so GitHub raw URLs become available
        time.sleep(5)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Git push failed:", e)
        return False


def git_delete_and_push_files(paths):
    """Delete given paths from git and push removal."""
    if not paths:
        return False
    try:
        for p in paths:
            # only run git rm if file exists in repo (ignore local-only)
            subprocess.run(["git", "rm", "-f", p], cwd=GITHUB_REPO_DIR, check=True)
        subprocess.run(["git", "commit", "-m", f"Remove preview images"], cwd=GITHUB_REPO_DIR, check=True)
        subprocess.run(["git", "push", "origin", GITHUB_BRANCH], cwd=GITHUB_REPO_DIR, check=True)
        print("🗑️ Removed preview files from GitHub.")
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Failed to delete files from GitHub:", e)
        return False


def _save_local_and_get_hosted_url(local_path: str) -> str:
    """
    Convenience wrapper to build the raw.githubusercontent URL for a file path
    relative to the repo root. Matches the same behaviour as ig_api_poster._save_local_and_get_hosted_url.
    """
    GITHUB_USERNAME = "skarthik06"
    GITHUB_REPO = "instagram_automation"
    GITHUB_BRANCH = "main"
    repo_root = os.path.dirname(os.path.abspath(__file__))
    rel_path = os.path.relpath(local_path, repo_root).replace("\\", "/")
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}/{rel_path}"
    return raw_url


async def run_automation():
    init_db()
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    os.makedirs(PREVIEWS_DIR, exist_ok=True)
    existing_quotes = get_all_quotes()

    # 1 Generate unique quote
    quote = generate_unique_quote(existing_quotes, min_words=10, max_words=25)
    print(f"\n✨ Generated Quote:\n{quote}\n")

    # 2 Build caption (helpers: emojis+hashtags)
    caption = build_caption(quote, use_llm_hashtags=True, max_hashtags=6)
    print(f"📝 Generated Caption with Hashtags:\n{caption}\n")

    # 3️⃣ Create Pinterest prompt (refined search)
    image_prompt = create_image_prompt(quote)
    search_prompt = f"{image_prompt} aesthetic background, high quality, Instagram-worthy"
    print(f"🔍 Refined Pinterest Search Prompt:\n{search_prompt}\n")

    # 4️⃣ Scrape & rank images using the refined prompt
    images = []
    attempt = 0
    while attempt < MAX_SCRAPE_ATTEMPTS and not images:
        print(f"📸 Scrape attempt {attempt + 1} for: {search_prompt}")
        images = await scrape_pinterest_images(search_prompt, limit=IMAGES_PER_ATTEMPT, existing_urls=[])
        attempt += 1

    if not images:
        print("⚠️ No suitable images found. Aborting.")
        return

    # Take top-3 (or fewer if not available)
    top_n = min(3, len(images))
    top_candidates = images[:top_n]
    print(f"✅ Found {len(images)} candidates, preparing top {top_n} previews...\n")

    # 5 Create preview images (overlay quote) and save locally
    preview_local_paths = []
    for idx, cand in enumerate(top_candidates, start=1):
        src = cand["url"]
        try:
            img_bytes = download_image_bytes(src)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            print("❌ Failed to download candidate:", e)
            continue

        preview_name = f"post_preview_{abs(hash(src)) % (10**8)}_{idx}.jpg"
        preview_path = os.path.join(PREVIEWS_DIR, preview_name)
        try:
            save_image_with_quote(img, quote, preview_path)
            preview_local_paths.append(preview_path)
            print(f"💾 Saved preview {idx} locally: {preview_path}")
        except Exception as e:
            print("❌ Failed to overlay/save preview:", e)

    if not preview_local_paths:
        print("⚠️ No previews created. Aborting.")
        return

    # 6 Commit and push preview files to GitHub so they are viewable
    pushed = git_commit_and_push_files(preview_local_paths, commit_msg="Add preview images for manual approval")
    if not pushed:
        print("⚠️ Could not upload previews to GitHub. Aborting preview step.")
        # optionally continue but safer to abort
        return

    # 7 Build preview URLs (raw.githubusercontent)
    preview_urls = [_save_local_and_get_hosted_url(p) for p in preview_local_paths]

    # Display preview URLs and caption
    print("\n🖼️ PREVIEWS (view in browser):")
    for i, u in enumerate(preview_urls, start=1):
        print(f"{i}. {u}")
    print("\n📝 Caption:\n")
    print(caption)
    print("\nChoose: enter 1/2/3 to POST that preview, or 's' to SKIP/REJECT (deletes previews).")

    # 8 Wait for user input
    choice = input("Your choice (1/2/3/s): ").strip().lower()
    if choice not in [str(i) for i in range(1, len(preview_urls)+1)] + ["s"]:
        print("Invalid choice. Aborting and cleaning up previews.")
        # delete previews locally + remote
        git_delete_and_push_files(preview_local_paths)
        for p in preview_local_paths:
            if os.path.exists(p):
                os.remove(p)
        return

    if choice == "s":
        print("🚫 You rejected the previews. Removing preview files from GitHub and locally.")
        # delete previews from git & local
        git_delete_and_push_files(preview_local_paths)
        for p in preview_local_paths:
            if os.path.exists(p):
                os.remove(p)
        return

    # user selected a preview index
    sel_idx = int(choice) - 1
    selected_local = preview_local_paths[sel_idx]
    selected_url = preview_urls[sel_idx]
    print(f"✅ You selected preview #{choice}: {selected_url}")

    # delete the other preview files from git + local cleanup
    other_paths = [p for i, p in enumerate(preview_local_paths) if i != sel_idx]
    if other_paths:
        git_delete_and_push_files(other_paths)
        for p in other_paths:
            if os.path.exists(p):
                os.remove(p)

    # 9 Post the selected preview to Instagram (hosted raw URL)
    print("📤 Posting selected image to Instagram...")
    ok = post_to_instagram(image_url=selected_url, caption=caption, local_image_path=selected_local)
    if ok:
        save_post(quote, selected_url)
        print("💾 Saved post info to database.")
        # keep the selected preview in repo as final record (already uploaded)
    else:
        print("❌ Posting failed; post not recorded.")

    # done
    print("\n🎉 Done.")


if __name__ == "__main__":
    asyncio.run(run_automation())
