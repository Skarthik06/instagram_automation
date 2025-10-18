# utils/config.py
import json
import os
from collections.abc import Mapping

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
        "font_path": "",
        "font_size": 46,
        "max_width_pct": 0.85,
        "padding": 40,
        "line_spacing": 6,
        "text_color": "#ffffff",
        "box_opacity": 0.48,
        "box_padding": 20,
        "position": "center"
    },
    "hashtags": {
        "fixed": ["motivation", "dailyinspiration", "positivity", "mindset"],
        "max_dynamic": 6
    },
    "hosted_image_base_url": "https://skarthik06.github.io/instagram_automation/images/"
}

def deep_merge(default: dict, override: dict) -> dict:
    """
    Recursively merge two dictionaries. Values from `override` take priority.
    """
    merged = default.copy()
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, Mapping):
            merged[k] = deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged

def load_config():
    cfg = DEFAULTS.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            cfg = deep_merge(cfg, user_cfg)
        except Exception as e:
            print(f"⚠️ Failed to load config.json: {e}. Using defaults.")
    return cfg

config = load_config()
