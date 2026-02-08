# llm_quote_gen.py
import os
import time
import random
import re
from dotenv import load_dotenv
from utils.db import get_all_quotes

# ===================== Gemini Setup =====================

try:
    import google.generativeai as genai
except Exception:
    genai = None

load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY and genai:
    genai.configure(api_key=GEMINI_KEY)

    # ✅ FIXED: correct & supported model name
    MODEL = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        generation_config={
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 300,
        },
    )
else:
    MODEL = None


# ===================== Internal Gemini Call =====================

def _call_model(prompt: str, retries: int = 3, sleep: float = 1.2) -> str:
    if MODEL is None:
        return ""

    for attempt in range(1, retries + 1):
        try:
            resp = MODEL.generate_content(prompt)
            text = (resp.text or "").strip()
            if text:
                return text
        except Exception as e:
            print(f"⚠️ Gemini error (attempt {attempt}): {e}")
            time.sleep(sleep)

    return ""


# ===================== ONE-CALL POST GENERATOR =====================

def generate_post_bundle(
    min_words: int = 6,
    max_words: int = 20,
    max_attempts: int = 3,
):
    """
    ONE Gemini call → quote + caption + hashtags + image prompt
    """

    used_quotes = set(get_all_quotes())

    prompt = (
        "Generate content for ONE Instagram motivational post.\n\n"
        "Rules:\n"
        f"- Quote must be {min_words} to {max_words} words\n"
        "- Quote must be original and not famous\n"
        "- Quote must NOT contain emojis or hashtags\n"
        "- Caption may include 1–2 emojis\n"
        "- Hashtags must be lowercase and space-separated\n"
        "- Image prompt must be under 8 words\n\n"
        "Return EXACTLY in this format:\n"
        "QUOTE: <text>\n"
        "CAPTION: <text>\n"
        "HASHTAGS: <hashtags>\n"
        "IMAGE: <image description>\n"
    )

    for _ in range(max_attempts):
        raw = _call_model(prompt)
        if not raw:
            continue

        data = {}
        for line in raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip().upper()] = v.strip()

        quote = data.get("QUOTE", "")
        caption = data.get("CAPTION", "")
        hashtags = data.get("HASHTAGS", "")
        image_prompt = data.get("IMAGE", "")

        # ---- Validation ----
        if not quote:
            continue
        if quote in used_quotes:
            continue
        if not (min_words <= len(quote.split()) <= max_words):
            continue

        if not caption:
            caption = f"{quote} ✨"

        if not hashtags:
            hashtags = "#motivation #growth #mindset"

        if not image_prompt or len(image_prompt.split()) < 2:
            image_prompt = "abstract aesthetic background"

        return {
            "quote": quote,
            "caption": caption,
            "hashtags": hashtags,
            "image_prompt": image_prompt,
        }

    # 🚨 Absolute fallback (NO Gemini dependency)
    return {
        "quote": "Small consistent actions create powerful long term change",
        "caption": "Small steps today build strong results tomorrow ✨",
        "hashtags": "#motivation #growth #consistency #mindset",
        "image_prompt": "soft gradient abstract background",
    }


# ===================== Compatibility Helpers =====================
# (So your existing main.py does not break)

def generate_unique_quote(existing_quotes=None, min_words=6, max_words=20):
    bundle = generate_post_bundle(min_words, max_words)
    return bundle["quote"]


def create_image_prompt(quote: str):
    bundle = generate_post_bundle()
    return bundle["image_prompt"]


def generate_caption(quote: str, max_words: int = 30):
    bundle = generate_post_bundle()
    return bundle["caption"]


def generate_hashtags(quote: str, max_tags: int = 6):
    bundle = generate_post_bundle()
    tags = bundle["hashtags"].split()
    return tags[:max_tags]


# ===================== Test Harness =====================

if __name__ == "__main__":
    post = generate_post_bundle()
    print("\nQUOTE:\n", post["quote"])
    print("\nCAPTION:\n", post["caption"])
    print("\nHASHTAGS:\n", post["hashtags"])
    print("\nIMAGE PROMPT:\n", post["image_prompt"])
