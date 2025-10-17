# main.py
import asyncio
import random
import os
import io
from llm_quote_gen import generate_unique_quote, create_image_prompt
from playwright_scraper import scrape_pinterest_images
from ig_api_poster import post_to_instagram, build_caption
from utils.db import init_db, get_all_quotes, save_post
from utils.filters import download_image_bytes
from utils.image_overlay import save_image_with_quote  # use this instead of overlay manually
from PIL import Image
from utils.config import config

MAX_SCRAPE_ATTEMPTS = 3
IMAGES_PER_ATTEMPT = 6
LOCAL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "images")


async def run_automation():
    init_db()
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

    existing_quotes = get_all_quotes()

    # 1) Generate unique quote
    quote = generate_unique_quote(existing_quotes)
    print(f"\n✨ Generated Quote:\n{quote}\n")

    # 2) Create dynamic Pinterest prompt from quote
    prompt = create_image_prompt(quote)
    print(f"🔍 Dynamic Pinterest Prompt:\n{prompt}\n")

    # 3) Scrape Pinterest images (retry)
    images = []
    attempt = 0
    while attempt < MAX_SCRAPE_ATTEMPTS and not images:
        print(f"📸 Scrape attempt {attempt + 1} for prompt...")
        images = await scrape_pinterest_images(prompt, limit=IMAGES_PER_ATTEMPT, existing_urls=[])
        attempt += 1

    if not images:
        print("⚠️ No suitable images found after retries. Aborting.")
        return

    # 4) Choose an image
    chosen_url = random.choice(images)
    print(f"✅ Selected image URL:\n{chosen_url}\n")

    # 5) Download and open image
    try:
        img_bytes = download_image_bytes(chosen_url)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        print("❌ Failed to download or open image:", e)
        return

    # 6) Overlay quote and save locally
    try:
        safe_name = f"post_{abs(hash(quote)) % (10**8)}.jpg"
        out_path = os.path.join(LOCAL_OUTPUT_DIR, safe_name)
        save_image_with_quote(img, quote, out_path)  # overlay + save in one step
        print(f"💾 Saved overlaid image to: {out_path}")
    except Exception as e:
        print("❌ Overlay or save failed:", e)
        return

    # 7) Build caption
    caption = build_caption(quote)
    print("📝 Caption:\n", caption, "\n")

    # 8) Post to Instagram
    print("📤 Posting to Instagram...")
    ok = post_to_instagram(local_image_path=out_path, caption=caption)
    if ok:
        save_post(quote, chosen_url)
        print("💾 Saved post info to database.")
    else:
        print("❌ Posting failed; post not recorded.")

    print("\n🎉 Done.")


if __name__ == "__main__":
    asyncio.run(run_automation())
