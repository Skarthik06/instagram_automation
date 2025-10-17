# ig_api_poster.py
import requests
import os
from dotenv import load_dotenv
import json
from utils.config import config

load_dotenv()

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
INSTAGRAM_ID = os.getenv("INSTAGRAM_BUSINESS_ID")

GRAPH_VERSION = "v21.0"

# Simple mapping for emoji suggestions by keyword
_EMOJI_MAP = {
    "success": "🏆",
    "dream": "✨",
    "hope": "🌅",
    "love": "❤️",
    "life": "🌱",
    "growth": "🌿",
    "work": "💼",
    "strength": "💪",
    "focus": "🎯",
    "gratitude": "🙏",
    "journey": "🛤️",
    "change": "🔁",
    "start": "🚀",
    "mindset": "🧠",
}

STOPWORDS = {
    "the","a","an","and","or","to","of","in","for","on","with","is","are","be","at","as","that","this","it"
}

def _extract_keywords(text, max_keywords=6):
    # very lightweight keyword extraction: word frequency after lowercasing and removing stopwords/punctuation
    import re
    words = re.findall(r"[A-Za-z']+", text.lower())
    freq = {}
    for w in words:
        if len(w) <= 3 or w in STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    # sort by frequency then alphabetically
    items = sorted(freq.items(), key=lambda t: (-t[1], t[0]))
    return [w for w, _ in items][:max_keywords]

def _keywords_to_hashtags(keywords):
    hashtags = []
    for k in keywords:
        clean = "".join(ch for ch in k if ch.isalnum())
        if not clean:
            continue
        hashtags.append("#" + clean)
    return hashtags

def _emoji_for_text(text, max_emojis=3):
    # pick emojis whose keys are present in the text
    shots = []
    low = text.lower()
    for k, e in _EMOJI_MAP.items():
        if k in low:
            shots.append(e)
        if len(shots) >= max_emojis:
            break
    return "".join(shots)

def build_caption(quote):
    # quote first, then emojis, then hashtags separated nicely
    hashtags_cfg = config.get("hashtags", {})
    fixed = hashtags_cfg.get("fixed", [])
    max_dynamic = hashtags_cfg.get("max_dynamic", 6)

    keywords = _extract_keywords(quote, max_keywords=max_dynamic)
    dyn_tags = _keywords_to_hashtags(keywords)
    fixed_tags = ["#" + t for t in fixed if not t.startswith("#")]
    emojis = _emoji_for_text(quote)

    # nice formatting: quote in quotes, then a newline, then emojis, then hashtags in a block
    caption_lines = []
    caption_lines.append(f"“{quote}”")
    if emojis:
        caption_lines.append(emojis)
    tags = dyn_tags + fixed_tags
    if tags:
        # place hashtags on new line to avoid cutting caption preview
        caption_lines.append(" ".join(tags))
    return "\n\n".join(caption_lines)

def _save_local_and_get_hosted_url(local_path):
    """
    If configured, map local filename to hosted URL. The project cannot upload files
    for you; this helper constructs a public URL if you already serve static files.
    """
    base = config.get("hosted_image_base_url", "").strip()
    if not base:
        return None
    # Ensure trailing slash
    if not base.endswith("/"):
        base = base + "/"
    filename = os.path.basename(local_path)
    return base + filename

def post_to_instagram(image_url=None, caption="", local_image_path=None, timeout=12):
    """
    Use either image_url or local_image_path.
    If local_image_path is provided, it will use file upload if no hosted_image_base_url is configured.
    """
    if not ACCESS_TOKEN or not INSTAGRAM_ID:
        print("❌ IG_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ID not set in environment.")
        return False

    if local_image_path:
        hosted = _save_local_and_get_hosted_url(local_image_path)
        if hosted:
            image_url = hosted
        else:
            # Use file upload directly
            try:
                with open(local_image_path, "rb") as f:
                    files = {"file": f}
                    create_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{INSTAGRAM_ID}/media"
                    payload = {"caption": caption, "access_token": ACCESS_TOKEN}
                    r = requests.post(create_url, data=payload, files=files, timeout=timeout)
                    r.raise_for_status()
                    data = r.json()
                    media_id = data.get("id")
                    if not media_id:
                        print("❌ No media id returned:", data)
                        return False
                    # Publish
                    publish_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{INSTAGRAM_ID}/media_publish"
                    publish_payload = {"creation_id": media_id, "access_token": ACCESS_TOKEN}
                    pub = requests.post(publish_url, data=publish_payload, timeout=timeout)
                    pub.raise_for_status()
                    print("✅ Successfully published post.")
                    return True
            except Exception as e:
                print("❌ Error posting local image:", e)
                return False

    if not image_url:
        print("❌ No image_url provided.")
        return False

    # If image_url is provided, fallback to normal URL posting
    create_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{INSTAGRAM_ID}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN
    }
    try:
        r = requests.post(create_url, data=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("❌ Create media error:", e)
        return False

    media_id = data.get("id")
    if not media_id:
        print("❌ No media id returned:", data)
        return False

    publish_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{INSTAGRAM_ID}/media_publish"
    publish_payload = {"creation_id": media_id, "access_token": ACCESS_TOKEN}
    try:
        pub = requests.post(publish_url, data=publish_payload, timeout=timeout)
        pub.raise_for_status()
        print("✅ Successfully published post.")
        return True
    except Exception as e:
        print("❌ Publish error:", e)
        return False

