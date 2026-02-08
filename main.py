# main.py
import asyncio
import os
import io
import subprocess
import time
from llm_quote_gen import generate_post_bundle
from playwright_scraper import scrape_pinterest_images
from ig_api_poster import post_to_instagram, build_caption
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
GITHUB_USERNAME = "skarthik06"
GITHUB_REPO = "instagram_automation"
GITHUB_BRANCH = "main"

# ============ Git Helper Functions ============

def git_commit_and_push_files(paths, commit_msg="Add Instagram preview images"):
    if not paths:
        return False
    try:
        for p in paths:
            subprocess.run(["git", "add", p], cwd=GITHUB_REPO_DIR, check=True)
        subprocess.run(["git", "commit", "-m", commit_msg, "--allow-empty"], cwd=GITHUB_REPO_DIR, check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", GITHUB_BRANCH], cwd=GITHUB_REPO_DIR, check=False)
        subprocess.run(["git", "push", "origin", GITHUB_BRANCH], cwd=GITHUB_REPO_DIR, check=True)
        print(f"✅ Committed & pushed {len(paths)} preview(s)")
        time.sleep(5)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Git push failed:", e)
        return False


def _save_local_and_get_hosted_url(local_path: str) -> str:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    rel_path = os.path.relpath(local_path, repo_root).replace("\\", "/")
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}/{rel_path}"


# ============ API FLOW ============

async def api_generate_previews():
    init_db()
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    os.makedirs(PREVIEWS_DIR, exist_ok=True)

    # ✅ ONE Gemini call
    post = generate_post_bundle(min_words=6, max_words=20)

    quote = post["quote"]
    caption = f'{post["caption"]}\n\n{post["hashtags"]}'
    image_prompt = post["image_prompt"]

    print(f"\n✨ Quote:\n{quote}")
    print(f"\n📝 Caption:\n{caption}")
    print(f"\n🎨 Image Prompt:\n{image_prompt}\n")

    search_prompt = f"{image_prompt} aesthetic background high quality"
    images = []

    for attempt in range(MAX_SCRAPE_ATTEMPTS):
        print(f"📸 Scrape attempt {attempt + 1}")
        images = await scrape_pinterest_images(search_prompt, limit=IMAGES_PER_ATTEMPT, existing_urls=[])
        if images:
            break

    if not images:
        raise Exception("No images found")

    preview_paths = []

    for i, img_data in enumerate(images[:3], start=1):
        try:
            img_bytes = download_image_bytes(img_data["url"])
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            name = f"post_preview_{abs(hash(img_data['url'])) % 10**8}_{i}.jpg"
            path = os.path.join(PREVIEWS_DIR, name)
            save_image_with_quote(img, quote, path)
            preview_paths.append(path)
            print(f"💾 Saved preview {i}")
        except Exception as e:
            print("❌ Preview error:", e)

    if not preview_paths:
        raise Exception("No previews created")

    if not git_commit_and_push_files(preview_paths):
        raise Exception("Git upload failed")

    preview_urls = [_save_local_and_get_hosted_url(p) for p in preview_paths]

    return {
        "quote": quote,
        "caption": caption,
        "preview_urls": preview_urls,
        "preview_paths": preview_paths,
    }


def api_post_selected_preview(selected_index, preview_paths, preview_urls, caption, quote):
    url = preview_urls[selected_index]
    local = preview_paths[selected_index]

    ok = post_to_instagram(image_url=url, caption=caption, local_image_path=local)
    if ok:
        save_post(quote, url)
        return {"status": "success"}
    raise Exception("Instagram post failed")


# ============ CLI ENTRY ============

if __name__ == "__main__":
    asyncio.run(api_generate_previews())
