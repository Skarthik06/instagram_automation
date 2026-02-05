# llm_quote_gen.py
import os
import random
import time
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

if GEMINI_KEY:
    if genai is None:
        raise RuntimeError("google.generativeai not installed or failed to import.")

    genai.configure(api_key=GEMINI_KEY)

    MODEL = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 120,
        },
    )
else:
    MODEL = None


# ===================== Internal LLM Call =====================

def _call_model(prompt: str, max_retries: int = 3, sleep: float = 0.8) -> str:
    if MODEL is None:
        return ""

    for attempt in range(max_retries):
        try:
            resp = MODEL.generate_content(prompt)

            text = (resp.text or "").strip()
            if text:
                return text

            # fallback to candidates if text is empty
            if hasattr(resp, "candidates") and resp.candidates:
                joined = " ".join(
                    c.text for c in resp.candidates if getattr(c, "text", None)
                ).strip()
                if joined:
                    return joined

        except Exception:
            pass

        time.sleep(sleep)

    return ""


# ===================== Quote Prompt =====================

def _build_prompt(min_words: int, max_words: int) -> str:
    return (
        "Write ONE original motivational sentence about growth, discipline, or progress. "
        f"The sentence must be between {min_words} and {max_words} words. "
        "Use natural human language. "
        "Do not include emojis, hashtags, quotes, or explanations. "
        "Output only the sentence."
    )


# ===================== Quote Generator (DB-Backed Uniqueness) =====================

def generate_unique_quote(
    existing_quotes: set,
    min_words: int = 8,
    max_words: int = 20,
    max_attempts: int = 12,
) -> str:

    # Merge DB quotes + runtime quotes
    db_quotes = set(get_all_quotes())
    used_quotes = set(existing_quotes) | db_quotes

    for _ in range(max_attempts):
        prompt = _build_prompt(min_words, max_words)
        text = _call_model(prompt)

        quote = " ".join(text.strip().strip('"').split()) if text else ""
        wc = len(quote.split())

        if not quote:
            continue

        if not (min_words <= wc <= max_words):
            continue

        if quote in used_quotes:
            continue

        # ✅ UNIQUE & VALID
        return quote

    # 🚨 TRUE fallback (only if Gemini fully fails)
    return "Progress grows when small actions are repeated consistently."

# ===================== Pinterest Image Prompt =====================

def create_image_prompt(quote: str) -> str:
    prompt = (
        f"Analyze this motivational quote: \"{quote}\". "
        "Describe ONE Pinterest-style background image in under 8 words. "
        "Use nature, gradients, abstract textures, or minimal aesthetics. "
        "No text, people, or logos."
    )

    text = _call_model(prompt)
    result = text.splitlines()[0].strip() if text else ""

    if not result or len(result.split()) < 2:
        return random.choice(
            [
                "abstract pastel gradient background",
                "sunrise sky landscape nature",
                "misty forest morning aesthetic",
                "serene ocean horizon minimal",
                "golden sunset over mountains",
                "soft light abstract texture",
            ]
        )

    return result


# ===================== Caption Generator =====================

def generate_caption(quote: str, max_words: int = 30) -> str:
    prompt = (
        f"Create a short Instagram caption for this quote: \"{quote}\". "
        f"Maximum {max_words} words. "
        "Emotionally engaging, include 1–2 emojis, no hashtags. "
        "Optional subtle call-to-action."
    )

    text = _call_model(prompt)
    caption = " ".join(text.strip().split()) if text else ""

    return caption if caption else f"{quote} ✨"


# ===================== Hashtag Generator =====================

def generate_hashtags(quote: str, max_tags: int = 6) -> list:
    prompt = (
        f"Generate {max_tags} Instagram hashtags for this quote: \"{quote}\". "
        "Focus on motivation, growth, mindset, inspiration. "
        "Lowercase, space separated, no emojis or numbers."
    )

    text = _call_model(prompt)
    tags = re.findall(r"#\w+", text.lower()) if text else []

    if tags:
        return tags[:max_tags]

    # fallback: extract keywords from quote
    words = re.findall(r"[a-zA-Z]+", quote.lower())
    STOPWORDS = {
        "the", "a", "an", "and", "or", "to", "of", "in", "for", "on",
        "with", "is", "are", "be", "at", "as", "that", "this", "it",
    }

    freq = {}
    for w in words:
        if len(w) <= 3 or w in STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1

    sorted_words = sorted(freq.items(), key=lambda t: (-t[1], -len(t[0])))
    hashtags = [f"#{w}" for w, _ in sorted_words[:max_tags]]

    defaults = ["#motivation", "#growth", "#mindset"]
    for d in defaults:
        if len(hashtags) < max_tags and d not in hashtags:
            hashtags.append(d)

    return hashtags[:max_tags]


# ===================== Test Harness =====================

if __name__ == "__main__":
    q = generate_unique_quote()
    print("\nQUOTE:\n", q)
    print("\nIMAGE PROMPT:\n", create_image_prompt(q))
    print("\nCAPTION:\n", generate_caption(q))
    print("\nHASHTAGS:\n", generate_hashtags(q))
