# llm_quote_gen.py
import os
import random
import time
import re
from dotenv import load_dotenv

# Gemini client (google.generativeai)
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
    MODEL = genai.GenerativeModel("gemini-2.5-flash")
else:
    MODEL = None

# ----- Internal helper for LLM calls -----
def _call_model(prompt: str, max_retries: int = 3, sleep: float = 0.8) -> str:
    if MODEL is None:
        return ""
    for attempt in range(max_retries + 1):
        try:
            resp = MODEL.generate_content(prompt)
            text = (resp.text or "").strip()
            if not text and hasattr(resp, "candidates") and resp.candidates:
                text = " ".join([c.text for c in resp.candidates if getattr(c, "text", None)])
            return text.strip()
        except Exception:
            if attempt == max_retries:
                return ""
            time.sleep(sleep)

# ----- Quote generation ---ii---  -----
def _build_prompt(min_words=10, max_words=25, include_author=False):
    author_clause = " Optionally include a single short author name in parentheses at the end." if include_author else ""
    prompt = (
        f"Write an original, positive, uplifting motivational quote "
        f"between {min_words} and {max_words} words. "
        "Keep it concise, vivid, emotionally engaging, and easy to read. "
        "Avoid clichés, famous quotes, or repetitive phrasing. "
        "Do NOT include hashtags or emojis. Output only the quote"
        f"{author_clause}."
    )
    return prompt

def generate_unique_quote(existing_quotes: set, min_words: int = 10, max_words: int = 25,
                          max_attempts: int = 12, include_author: bool = False) -> str:
    attempts = 0
    while attempts < max_attempts:
        prompt = _build_prompt(min_words, max_words, include_author)
        text = _call_model(prompt)
        quote = " ".join(text.strip().strip('"').split()) if text else ""
        wc = len([w for w in re.split(r"\s+", quote) if w.strip()])
        if quote and (min_words <= wc <= max_words) and quote not in existing_quotes:
            return quote
        attempts += 1
    # fallback quote
    fallback = f"Keep moving forward, embrace small wins, and grow. ({random.randint(1000,9999)})"
    return fallback

# ----- Image prompt generation (Pinterest style) -----
def create_image_prompt(quote: str) -> str:
    """
    Generate a Pinterest-friendly background image prompt.
    """
    prompt = (
        f"Analyze this motivational quote: \"{quote}\". "
        "Describe a single, visually stunning, Pinterest-style background image (under 8 words) "
        "that represents the mood, emotion, and theme of the quote. "
        "Prefer natural scenes, soft gradients, abstract textures, or minimalistic aesthetics. "
        "Do not include text, logos, people, or quote overlays. Return only a concise keyword phrase."
    )
    text = _call_model(prompt)
    first_line = text.splitlines()[0].strip() if text else ""
    
    # fallback if LLM output is too short or empty
    if not first_line or len(first_line.split()) < 2:
        first_line = random.choice([
            "abstract pastel gradient background",
            "sunrise sky landscape nature",
            "minimalist marble texture aesthetic",
            "serene ocean waves blue tone",
            "soft light abstract background",
            "clean gradient sky landscape",
            "misty forest morning scene",
            "golden sunset over mountains"
        ])
    return first_line

# ----- Caption generation -----
def generate_caption(quote: str, max_words: int = 30) -> str:
    prompt = (
        f"Create a catchy, Instagram-ready caption for the motivational quote: \"{quote}\". "
        f"Make it concise, emotionally engaging, and up to {max_words} words. "
        "Include 1-2 relevant emojis naturally, but no hashtags. Add a subtle call-to-action if suitable."
    )
    text = _call_model(prompt)
    caption = " ".join(text.strip().split()) if text else ""
    if not caption:
        return f"{quote} ✨"
    return caption

# ----- Hashtag generation (LLM-assisted) -----
def generate_hashtags(quote: str, max_tags: int = 6) -> list:
    hashtags = []

    prompt = (
        f"Generate {max_tags} relevant Instagram hashtags for the quote: \"{quote}\". "
        "Focus on motivation, growth, mindset, inspiration, and positivity. "
        "Return hashtags only, separated by spaces, no numbers or emojis."
    )
    text = _call_model(prompt)
    if text:
        raw_tags = re.findall(r"#\w+", text)
        if raw_tags:
            hashtags = raw_tags[:max_tags]
        else:
            # fallback: split words and make hashtags
            for part in re.split(r"[,;\n ]", text):
                candidate = re.sub(r"[^\w]", "", part.strip())
                if candidate:
                    hashtags.append("#" + candidate.lower())
                if len(hashtags) >= max_tags:
                    break

    # fallback: extract from quote if LLM failed
    if len(hashtags) < 3:
        words = re.findall(r"[A-Za-z']+", quote.lower())
        STOPWORDS = {"the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "with", "is", "are", "be", "at", "as", "that", "this", "it"}
        freq = {}
        for w in words:
            if len(w) <= 3 or w in STOPWORDS:
                continue
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda t: (-t[1], -len(t[0]), t[0]))
        for w, _ in sorted_words:
            tag = "#" + re.sub(r"[^\w]", "", w)
            if tag not in hashtags:
                hashtags.append(tag)
            if len(hashtags) >= max_tags:
                break

    # ensure at least default hashtags
    defaults = ["#motivation", "#growth", "#mindset"]
    for d in defaults:
        if d not in hashtags:
            hashtags.append(d)
        if len(hashtags) >= max_tags:
            break

    # deduplicate and limit
    seen = set()
    final_tags = []
    for t in hashtags:
        t_low = t.lower()
        if t_low not in seen:
            seen.add(t_low)
            final_tags.append(t)
        if len(final_tags) >= max_tags:
            break

    return final_tags

# ----- Test harness -----
if __name__ == "__main__":
    ex = set()
    q = generate_unique_quote(ex, min_words=8, max_words=20)
    print("QUOTE:", q)
    print("PROMPT:", create_image_prompt(q))
    print("CAPTION:", generate_caption(q))
    print("HASHTAGS:", generate_hashtags(q, max_tags=6))
