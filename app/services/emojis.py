"""Data-driven emoji selection.

No hardcoded emoji-character map. Emojis are resolved at runtime from the
`emoji` library (the same GitHub-style alias set used across the ecosystem),
so the available set is the full Unicode emoji catalogue rather than a frozen
list. A small *concept → alias* synonym layer bridges abstract words
("success", "growth") to a real alias the library knows ("trophy",
"chart_with_upwards_trend"); the alias is then rendered to its character by
the library, never stored literally here.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import List

import emoji as _emoji

# Concept word -> emoji *alias* (must exist in the emoji library).
_SYNONYMS = {
    "success": "trophy", "win": "trophy", "winner": "trophy", "achieve": "trophy",
    "dream": "sparkles", "shine": "sparkles", "magic": "sparkles", "wow": "sparkles",
    "hope": "sunrise", "morning": "sunrise", "new": "sunrise",
    "wish": "star2", "star": "star2", "stars": "star2",
    "love": "heart", "loving": "heart", "kind": "heart",
    "passion": "fire", "fire": "fire", "hot": "fire", "trending": "fire",
    "life": "seedling", "grow": "seedling", "growing": "seedling",
    "growth": "chart_with_upwards_trend", "progress": "chart_with_upwards_trend",
    "rise": "chart_with_upwards_trend", "profit": "chart_with_upwards_trend",
    "work": "briefcase", "business": "briefcase", "career": "briefcase",
    "money": "money_with_wings", "rich": "money_with_wings", "wealth": "money_with_wings",
    "strong": "muscle", "strength": "muscle", "discipline": "muscle",
    "power": "zap", "energy": "zap", "fast": "zap",
    "focus": "dart", "goal": "dart", "goals": "dart", "target": "dart", "aim": "dart",
    "grateful": "folded_hands", "gratitude": "folded_hands", "thanks": "folded_hands",
    "journey": "compass", "path": "compass", "direction": "compass",
    "travel": "airplane", "explore": "compass",
    "change": "arrows_counterclockwise", "transform": "arrows_counterclockwise",
    "start": "rocket", "begin": "rocket", "launch": "rocket", "boost": "rocket",
    "mind": "brain", "mindset": "brain", "think": "brain", "smart": "brain",
    "idea": "bulb", "ideas": "bulb", "learn": "books", "study": "books",
    "brave": "lion", "courage": "lion", "fearless": "lion", "bold": "lion",
    "calm": "ocean", "relax": "ocean", "patience": "ocean",
    "peace": "dove_of_peace", "quiet": "dove_of_peace",
    "sun": "sunny", "happy": "smile", "joy": "smile", "smile": "smile",
    "nature": "deciduous_tree", "tree": "deciduous_tree", "green": "deciduous_tree",
    "mountain": "mountain", "climb": "mountain", "summit": "mountain",
    "time": "hourglass_flowing_sand", "patience2": "hourglass_flowing_sand",
    # news niche
    "news": "newspaper", "report": "newspaper", "story": "newspaper",
    "breaking": "rotating_light", "alert": "rotating_light", "urgent": "rotating_light",
    "update": "satellite_antenna", "live": "satellite_antenna",
    "world": "globe_with_meridians", "global": "globe_with_meridians",
    "economy": "chart_with_upwards_trend", "market": "chart_with_upwards_trend",
    "tech": "computer", "technology": "computer", "ai": "robot_face",
    "robot": "robot_face", "science": "microscope", "research": "microscope",
    "health": "hospital", "medical": "hospital", "sport": "soccer",
    "sports": "soccer", "game": "video_game", "win2": "trophy",
    "vote": "ballot_box_with_ballot", "election": "ballot_box_with_ballot",
    "law": "scales", "court": "scales", "climate": "earth_africa",
}

_WORD_RE = re.compile(r"[a-zA-Z']+")


@lru_cache(maxsize=512)
def _resolve(alias: str) -> str:
    """Render an emoji alias to its character via the library, or '' if unknown."""
    rendered = _emoji.emojize(f":{alias}:", language="alias")
    return rendered if _emoji.purely_emoji(rendered) else ""


def pick_for_text(text: str, k: int = 2) -> str:
    """Return up to `k` emojis relevant to `text`, chosen automatically."""
    if not text:
        return ""
    seen: List[str] = []
    for word in _WORD_RE.findall(text.lower()):
        if len(word) < 3:
            continue
        alias = _SYNONYMS.get(word)
        char = _resolve(alias) if alias else _resolve(word)
        if char and char not in seen:
            seen.append(char)
        if len(seen) >= k:
            break
    return "".join(seen)


def strip_emojis(text: str) -> str:
    """Remove any emojis from text (used to keep overlaid quote text clean)."""
    return _emoji.replace_emoji(text, replace="").strip()
