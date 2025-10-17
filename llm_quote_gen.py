# llm_quote_gen.py
import google.generativeai as genai
from dotenv import load_dotenv
import os
import random
import time
from utils.config import config

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in .env")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

def _call_model(prompt, max_retries=2, sleep=0.6):
    for attempt in range(max_retries + 1):
        try:
            resp = model.generate_content(prompt)
            text = resp.text.strip()
            return text
        except Exception as e:
            if attempt == max_retries:
                raise
            time.sleep(sleep)
    raise RuntimeError("unreachable")

def _build_prompt(min_words, max_words, avoid_famous=True, include_author=False):
    avoid_clause = "Avoid famous, well-known, or attributed quotes." if avoid_famous else ""
    author_clause = " Optionally include an author name at the end in parentheses." if include_author else ""
    prompt = (
        f"Write an original, uplifting motivational quote between {min_words} and {max_words} words. "
        f"Keep the tone positive, actionable and vivid. {avoid_clause}{author_clause} "
        "Do NOT include hashtags or emojis. Output only the quote (and optional author in parentheses)."
    )
    return prompt

def generate_unique_quote(existing_quotes, max_attempts=None):
    """Generate a motivational quote (configurable length) not in existing_quotes."""
    qcfg = config.get("quote", {})
    min_words = qcfg.get("min_words", 35)
    max_words = qcfg.get("max_words", 50)
    avoid_famous = qcfg.get("avoid_famous", True)
    include_author = qcfg.get("include_author", False)
    attempts = max_attempts or qcfg.get("attempts", 6)

    base_prompt = _build_prompt(min_words, max_words, avoid_famous, include_author)

    for i in range(attempts):
        text = _call_model(base_prompt)
        quote = text.strip().strip('"').replace("\n", " ").strip()
        # basic normalization and collapse spaces
        quote = " ".join(quote.split())
        # simple word count check
        wc = len([w for w in quote.split() if w.strip()])
        if quote and (min_words <= wc <= max_words) and quote not in existing_quotes:
            return quote
        # If model didn't match, try again but allow slightly out-of-range quotes eventually
        if quote and quote not in existing_quotes and i >= attempts - 2:
            return quote
    # deterministic fallback
    return f"Keep moving with purpose, nurture tiny wins every day and watch your life transform. ({random.randint(1000,9999)})"

def create_image_prompt(quote, concise=True):
    """
    Create a Pinterest-style search prompt from the quote.
    """
    prompt = (
        f"Based on the motivational quote: \"{quote}\", craft 1 concise Pinterest search query for "
        "a high-quality background image (no text, no watermark, no logos). Mention mood, lighting and subject "
        "(example: 'golden sunrise over misty mountains, warm light, soft bokeh'). Keep it search-friendly and short."
    )
    text = _call_model(prompt)
    first_line = text.splitlines()[0].strip() if text else ""
    if len(first_line) < 8:
        first_line = f"{quote} inspirational background no text no watermark"
    if concise:
        first_line = first_line[:120]
    return first_line
