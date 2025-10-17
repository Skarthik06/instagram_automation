# utils/config.py
import json
import os

# Path to a user-editable config.json in project root
ROOT = os.path.join(os.path.dirname(__file__), "..")
CONFIG_FILE = os.path.join(ROOT, "config.json")

DEFAULTS = {
    "quote": {
        "min_words": 35,
        "max_words": 50,
        "attempts": 6,
        "avoid_famous": True,
        "include_author": False
    },
    "overlay": {
        "font_path": "",  # if empty, fallback to system fonts / PIL default
        "font_size": 46,
        "max_width_pct": 0.85,
        "padding": 40,
        "line_spacing": 6,
        "text_color": "#ffffff",
        "box_opacity": 0.48,
        "box_padding": 20,
        "position": "center"  # "center", "bottom", or "top"
    },
    "hashtags": {
        "fixed": ["motivation", "dailyinspiration", "positivity", "mindset"],
        "max_dynamic": 6
    },
    # Optional: if you can serve files from a simple static host, set base URL here.
    # Example: "https://example.com/static/" so {base}{filename} must be valid url to the file.
    "hosted_image_base_url": ""
}

def load_config():
    cfg = DEFAULTS.copy()
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            # shallow merge for our simple structure
            for k, v in user.items():
                if isinstance(v, dict) and k in cfg:
                    cfg[k].update(v)
                else:
                    cfg[k] = v
    except Exception:
        # on any parse/read error, silently keep defaults
        pass
    return cfg

config = load_config()
