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
GITHUB_REPO_DIR = os.path.dirname(__file__)
GITHUB_BRANCH = "main"
GIT_PUSH_RETRIES = 3
GIT_RETRY_DELAY = 5

def git_commit_and_push(local_path, commit_msg="Add Instagram post image"):
    """Add, commit, and push a file to GitHub"""
    for attempt in range(1, GIT_PUSH_RETRIES + 1):
        try:
            subprocess.run(["git", "add", local_path], cwd=GITHUB_REPO_DIR, check=True)
            subprocess.run(["git", "commit", "-m", commit_msg, "--allow-empty"], cwd=GITHUB_REPO_DIR, check=True)
            subprocess.run(["git", "push", "origin", GITHUB_BRANCH], cwd=GITHUB_REPO_DIR, check=True)
            print(f"✅ Uploaded {os.path.basename(local_path)} to GitHub.")
            time.sleep(10)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Git push attempt {attempt} failed:", e)
            if attempt < GIT_PUSH_RETRIES:
                time.sleep(GIT_RETRY_DELAY)
            else:
                print("❌ All Git push attempts failed.")
                return False

async def run_automation():
    """Main automation workflow"""
    init_db()
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    existing_quotes = get_all_quotes()

    # 1️⃣ Generate a unique, short, engaging quote
    quote = generate_unique_quote(existing_quotes, min_words=10, max_words=25)
    print(f"\n✨ Generated Quote:\n{quote}\n")

    # 2️⃣ Build Instagram caption (quote + emojis + hashtags)
    caption = build_caption(quote, use_llm_hashtags=True, max_hashtags=6)
    print(f"📝 Generated Caption with Hashtags:\n{caption}\n")

    # 3️⃣ Generate Pinterest-style image prompt
    prompt = create_image_prompt(quote)
    print(f"🔍 Dynamic Pinterest Prompt:\n{prompt}\n")

    # 4️⃣ Scrape Pinterest images
    images = []
    attempt = 0
    while attempt < MAX_SCRAPE_ATTEMPTS and not images:
        print(f"📸 Scrape attempt {attempt + 1} for prompt...")
        images = await scrape_pinterest_images(prompt, limit=IMAGES_PER_ATTEMPT, existing_urls=[])
        attempt += 1

    if not images:
        print("⚠️ No suitable images found. Aborting.")
        return

    # 5️⃣ Select a random image
    chosen_url = random.choice(images)
    print(f"✅ Selected image URL:\n{chosen_url}\n")

    # 6️⃣ Download and open image
    try:
        img_bytes = download_image_bytes(chosen_url)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        print("❌ Failed to download/open image:", e)
        return

    # 7️⃣ Overlay quote on image (auto-resizes for readability)
    safe_name = f"post_{abs(hash(quote)) % (10**8)}.jpg"
    out_path = os.path.join(LOCAL_OUTPUT_DIR, safe_name)
    try:
        save_image_with_quote(img, quote, out_path)
        print(f"💾 Saved overlaid image to: {out_path}")
    except Exception as e:
        print("❌ Overlay/save failed:", e)
        return

    # 8️⃣ Commit and push image to GitHub
    uploaded = git_commit_and_push(out_path)
    hosted_url = _save_local_and_get_hosted_url(out_path) if uploaded else None
    image_to_post = hosted_url or out_path

    # 9️⃣ Post to Instagram
    print("📤 Posting to Instagram...")
    ok = post_to_instagram(image_url=image_to_post, caption=caption, local_image_path=out_path)
    if ok:
        save_post(quote, chosen_url)
        print("💾 Saved post info to database.")
    else:
        print("❌ Posting failed; post not recorded.")

    print("\n🎉 Done.")

if __name__ == "__main__":
    asyncio.run(run_automation())
