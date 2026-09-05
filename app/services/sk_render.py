"""Business-SK creative renderer — "The Still Set".

Turns product data + real product images into designed Instagram slides (1080×1350,
2× retina) using the exact visual identity from the creative-system playbook: the
"index frame", per-category tint, editorial serif + mono placard, quiet price lockup.

Design principles enforced here (see creative-system.html + carousel-publisher.agents.md):
  • The PRODUCT stays true to source — we never recolour/reshape/relabel it. Only the
    design ENVIRONMENT (stage, shadow, type) is created around it.
  • NO fabrication — a field (MRP, discount, rating) renders only when it is actually
    present in the product data. Missing → the element simply isn't drawn.
  • Multi-product LOGIC — the layout family is chosen by product count; products are
    never shrunk to fit, the structure changes instead (1→hero … 7+→carousel).

Stack (all free, self-hosted): Playwright/Chromium (render), Pillow (image prep),
Google Fonts CDN (Instrument Serif · Hanken Grotesk · Space Mono, all OFL) + the
system Noto fonts (Kannada/Devanagari) for the language module. rembg is used for
product isolation IF installed — otherwise the source image is staged as-is.
"""
from __future__ import annotations

import base64
import html
import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

W, H = 1080, 1350

# ── category tint system: one frame, many moods ───────────────────────────────
_TINTS = {
    "fashion": "#B04A32", "tech": "#3E5568", "home": "#5C6A4B",
    "beauty": "#A0566A", "deal": "#9A6A2E", "deals": "#9A6A2E",
    "default": "#B04A32",
}
# Latin display/UI/utility via Google Fonts; Indic via the container's Noto fonts.
_INDIC = "'Noto Sans Kannada','Noto Sans Devanagari','Noto Sans'"
_SERIF = f"'Instrument Serif',{_INDIC},Georgia,serif"
_SANS = f"'Hanken Grotesk',{_INDIC},-apple-system,'Segoe UI',sans-serif"
_MONO = "'Space Mono',ui-monospace,monospace"


def _tint(category: str) -> str:
    key = (category or "").strip().lower()
    for k, v in _TINTS.items():
        if k in key:
            return v
    return _TINTS["default"]


def _esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def _money(v: Any) -> str:
    """Render a price/MRP as a clean ₹ figure with Indian grouping. Passes through
    a value that already has a currency symbol; drops nothing, invents nothing."""
    if v is None or v == "":
        return ""
    s = str(v).strip()
    if not s:
        return ""
    if s[0] in "₹$€£":                       # already formatted upstream — keep as-is
        return s
    m = re.search(r"\d[\d,]*\.?\d*", s)
    if not m:
        return s
    num = m.group(0).replace(",", "")
    try:
        n = int(round(float(num)))
    except ValueError:
        return f"₹{s}"
    grp = _indian_group(n)
    return f"₹{grp}"


def _indian_group(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
    return f"{head},{tail}"


def _discount_pct(p: Dict[str, Any]) -> Optional[int]:
    """Real discount only: use the given pct, else derive from price vs MRP. None if
    we can't compute it truthfully."""
    d = p.get("discount_pct")
    if d not in (None, "", 0, "0"):
        try:
            return int(round(float(str(d).replace("%", ""))))
        except ValueError:
            pass
    price = _num(p.get("price"))
    mrp = _num(p.get("orig_price") or p.get("mrp"))
    if price and mrp and mrp > price:
        return int(round((mrp - price) / mrp * 100))
    return None


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    m = re.search(r"\d[\d,]*\.?\d*", str(v))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _name(p: Dict[str, Any]) -> str:
    return (p.get("product_title") or p.get("title") or p.get("name") or "Product").strip()


def _brand(p: Dict[str, Any]) -> str:
    b = (p.get("brand") or "").strip()
    if b:
        return b
    # first token of the title as a fallback brand cue (kept short, never fabricated)
    return _name(p).split()[0][:22]


# ── product image prep: stage the environment, keep the product true ──────────
_REMBG_SESSION = None


def _rembg_cut(img_bytes: bytes) -> Optional[bytes]:
    """Isolate the product (transparent PNG) IF rembg is installed. Returns None when
    unavailable so the caller stages the source image as-is. Never alters product pixels."""
    global _REMBG_SESSION
    try:
        from rembg import remove, new_session  # type: ignore
        if _REMBG_SESSION is None:
            _REMBG_SESSION = new_session("u2net")
        return remove(img_bytes, session=_REMBG_SESSION)
    except Exception:
        return None


def _knockout_white_bg(im):
    """Zero-dependency fallback background removal for the very common case of a product
    shot on a plain white studio background (most Amazon catalog images). Flood-fills the
    connected near-white region from the four corners → transparent, so the product sits on
    our tinted stage. Interior whites (a white logo, a white sole) are preserved because they
    aren't connected to a corner. If the corners aren't white (lifestyle/coloured bg), the
    image is returned untouched — never risk cutting into the product."""
    from PIL import Image, ImageDraw
    w, h = im.size
    rgb = im.convert("RGB")
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    if not all(min(rgb.getpixel(c)) > 232 for c in corners):
        return im                                   # not a white-bg catalog shot → leave alone
    sentinel = (255, 0, 255)
    for c in corners:
        try:
            ImageDraw.floodfill(rgb, c, sentinel, thresh=34)
        except Exception:
            return im
    try:
        import numpy as np
        arr = np.asarray(rgb)
        mask = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 255)
        alpha = np.asarray(im.split()[3]).copy()
        alpha[mask] = 0
        im.putalpha(Image.fromarray(alpha, "L"))
    except Exception:
        return im
    return im


def _prep_image(src: str, *, isolate: bool = True, box: int = 1000) -> Optional[str]:
    """Download/load a product image and return a data: URI ready for the stage.
    Steps: fetch → (optional rembg isolate) → fit into a square, padded, RGBA canvas
    (contain, never crop the product) → light sharpen. The product is untouched;
    only padding/transparency (the environment) is added for cross-source consistency."""
    from PIL import Image, ImageOps, ImageFilter
    raw: Optional[bytes] = None
    try:
        if src.startswith("http"):
            r = requests.get(src, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            raw = r.content
        else:
            p = Path(src)
            if p.exists():
                raw = p.read_bytes()
    except Exception:
        return None
    if not raw:
        return None
    isolated = False
    if isolate:
        cut = _rembg_cut(raw)
        if cut:
            raw = cut
            isolated = True
    try:
        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im).convert("RGBA")
        if not isolated:
            im = _knockout_white_bg(im)             # free fallback: drop a plain white catalog bg
        # Trim the product out of ANY uniform border (white / off-white / grey / solid colour),
        # not just a transparent one — this is what makes the product BIG on the stage instead
        # of sitting tiny inside its original margins. Uniform border only; never crops the product.
        bbox = _content_bbox(im)
        if bbox:
            im = im.crop(bbox)
        # Scale the product to FILL the stage (up OR down, aspect preserved) with only a hair of
        # padding, so it reads large and clear. Upscaled shots get a sharpen so they stay crisp.
        pad = int(box * 0.02)
        inner = box - 2 * pad
        scale = min(inner / max(1, im.width), inner / max(1, im.height))
        neww, newh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
        im = im.resize((neww, newh), Image.LANCZOS)
        if scale > 1.05:                            # we enlarged a small source → recover edges
            im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=115, threshold=2))
        canvas = Image.new("RGBA", (box, box), (0, 0, 0, 0))
        canvas.paste(im, ((box - im.width) // 2, (box - im.height) // 2), im)
        buf = io.BytesIO()
        canvas.save(buf, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def _content_bbox(im) -> Optional[Tuple[int, int, int, int]]:
    """Bounding box of the actual product. If the image already has transparency (rembg or the
    white-knockout), use the alpha bbox. Otherwise estimate the background colour from the four
    corners and return the box of everything that differs from it — trimming a uniform border of
    ANY colour. Returns None (keep full frame) when the image is edge-to-edge content."""
    try:
        import numpy as np
        w, h = im.size
        alpha = np.asarray(im.split()[3])
        if int(alpha.min()) < 245:                  # real transparency present → trust it
            return im.split()[3].getbbox()
        rgb = np.asarray(im.convert("RGB")).astype(np.int16)
        corners = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
        bg = np.median(corners, axis=0)
        # if corners disagree wildly it's a busy/lifestyle bg — don't risk trimming into product
        if np.abs(corners - bg).sum(axis=1).max() > 60:
            return None
        dist = np.abs(rgb - bg).sum(axis=2)
        mask = dist > 42
        ys, xs = np.where(mask)
        if xs.size == 0:
            return None
        m = max(4, int(min(w, h) * 0.01))
        x0, y0 = max(0, int(xs.min()) - m), max(0, int(ys.min()) - m)
        x1, y1 = min(w, int(xs.max()) + m), min(h, int(ys.max()) + m)
        # ignore a trim that barely does anything or one that ate almost everything (safety)
        if (x1 - x0) < w * 0.2 or (y1 - y0) < h * 0.2:
            return None
        return (x0, y0, x1, y1)
    except Exception:
        return im.getbbox()


# ── shared CSS (the identity) ─────────────────────────────────────────────────
def _base_css(tint: str) -> str:
    return f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px}}
body{{font-family:{_SANS};background:#EDE7DD;color:#221E18;overflow:hidden;-webkit-font-smoothing:antialiased}}
.slide{{width:{W}px;height:{H}px;position:relative;background:
   radial-gradient(140% 100% at 50% -6%, #FBF8F2 0%, #EFE9E1 46%, #E7DFD2 100%);padding:60px}}
.frame{{position:absolute;inset:34px;border:1.5px solid #CFC5B2;border-radius:6px;pointer-events:none}}
.corner{{position:absolute;width:26px;height:26px;border:1.5px solid {tint};opacity:.75}}
.c1{{top:34px;left:34px;border-right:none;border-bottom:none}}
.c2{{top:34px;right:34px;border-left:none;border-bottom:none}}
.c3{{bottom:34px;left:34px;border-right:none;border-top:none}}
.c4{{bottom:34px;right:34px;border-left:none;border-top:none}}
.placard{{position:relative;z-index:2;display:flex;justify-content:space-between;align-items:flex-start}}
.kick{{font-family:{_MONO};font-size:22px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:{tint}}}
.code{{font-family:{_MONO};font-size:19px;letter-spacing:.14em;color:#8B8171}}
.stage{{position:relative;border-radius:8px;overflow:hidden;background:
   radial-gradient(120% 92% at 50% 16%, {tint}1F 0%, {tint}0D 55%, #E4DBCC 100%);
   display:flex;align-items:center;justify-content:center}}
.stage img{{width:94%;height:94%;object-fit:contain;
   filter:drop-shadow(0 34px 40px {tint}59) drop-shadow(0 10px 14px rgba(34,30,24,.18))}}
.stage.big img{{width:97%;height:97%}}
.serif{{font-family:{_SERIF}}}
.pname{{font-family:{_SERIF};line-height:1.02;color:#221E18;letter-spacing:-.01em}}
.plock{{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}}
.price{{font-family:{_SANS};font-weight:800;font-variant-numeric:tabular-nums;color:#221E18}}
.mrp{{font-size:.5em;color:#8B8171;text-decoration:line-through;font-variant-numeric:tabular-nums;font-weight:600}}
.off{{font-family:{_MONO};font-weight:700;color:#fff;background:{tint};padding:6px 14px;border-radius:6px;letter-spacing:.03em}}
.rating{{font-family:{_MONO};font-size:24px;color:#5A5245;letter-spacing:.04em}}
.chip{{display:inline-flex;align-items:center;gap:14px;border:1.5px solid #CFC5B2;background:#F6F2EB;
   border-radius:100px;padding:12px 24px}}
.chips{{display:flex;flex-wrap:wrap;gap:12px}}
.factchip{{display:inline-flex;align-items:center;gap:9px;border:1.5px solid #CFC5B2;background:#F6F2EB;
   border-radius:100px;padding:10px 20px;font-family:{_MONO};font-size:22px;color:#5A5245;letter-spacing:.02em}}
.factchip b{{color:#221E18;font-weight:700}}
.save{{font-family:{_MONO};font-size:24px;font-weight:700;color:{tint};letter-spacing:.02em}}
.code{{display:none}}
.cta{{display:inline-flex;align-items:center;gap:12px;font-family:{_MONO};font-weight:700;letter-spacing:.16em;
   text-transform:uppercase;border:1.5px solid #221E18;border-radius:100px;padding:16px 30px;color:#221E18;font-size:22px}}
.cta.solid{{background:#221E18;color:#EDE7DD}}
.rank{{font-family:{_SERIF};color:{tint};line-height:.8}}
.foot{{position:absolute;left:60px;right:60px;bottom:56px;z-index:2;display:flex;justify-content:space-between;
   align-items:center;font-family:{_MONO};font-size:19px;letter-spacing:.14em;text-transform:uppercase;color:#8B8171}}
.progress{{position:absolute;left:34px;right:34px;bottom:34px;height:4px;background:#00000014;z-index:3;border-radius:2px;overflow:hidden}}
.progress i{{display:block;height:100%;background:{tint}}}
"""


def _page(tint: str, inner: str, *, idx: int = 1, total: int = 1,
          foot_left: str = "@business.sk", foot_right: str = "") -> str:
    # No edition code (top-right) and no slide counter (footer) — per brand: clean, uncluttered.
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Hanken+Grotesk:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>{_base_css(tint)}</style></head>
<body><div class="slide">
  <div class="frame"></div><span class="corner c1"></span><span class="corner c2"></span><span class="corner c3"></span><span class="corner c4"></span>
  {inner}
  <div class="foot"><span>{_esc(foot_left)}</span></div>
</div></body></html>"""


# ── individual templates ──────────────────────────────────────────────────────
def _clean_count(v: Any) -> str:
    """Tidy a count-ish field ('52', '50+', '1,240', '1K+', '500+ bought') → a compact token."""
    s = str(v or "").strip()
    m = re.search(r"[\d,]+\s*[KkMm]?\+?", s)
    return re.sub(r"\s+", "", m.group(0)) if m else ""


def _fmt_count(v: Any) -> str:
    """Human count with grouping, preserving +/K/M suffixes: 39800→'39,800', '1K+'→'1K+'."""
    s = _clean_count(v)
    m = re.match(r"^([\d,]+)([KkMm]?\+?)$", s)
    if not m:
        return s
    try:
        return _indian_group(int(m.group(1).replace(",", ""))) + m.group(2)
    except ValueError:
        return s


_GOOD_BADGES = {
    "amazon's choice": "Amazon's Choice", "amazons choice": "Amazon's Choice",
    "best seller": "Best Seller", "#1 best seller": "#1 Best Seller",
    "limited time deal": "Limited Time Deal",
}


def _badge_text(p: Dict[str, Any]) -> str:
    """Return a CLEAN, verified badge label or "". Guards against the truncated scrape
    ("Amazon's") and anything not on the known-good list — never show a partial badge."""
    raw = (p.get("badge") or "").strip()
    if not raw:
        return ""
    key = re.sub(r"\s+", " ", raw.replace("’", "'")).strip().lower()
    if key in _GOOD_BADGES:
        return _GOOD_BADGES[key]
    if key in ("amazon's", "amazons", "amazon"):     # the old truncated form → repair
        return "Amazon's Choice"
    for k, v in _GOOD_BADGES.items():
        if k in key:
            return v
    return ""                                         # unknown/partial → drop (no fabrication)


def _badge_pill(p: Dict[str, Any], tint: str) -> str:
    b = _badge_text(p)
    if not b:
        return ""
    return (f'<span style="display:inline-flex;align-items:center;gap:8px;font-family:{_MONO};'
            f'font-size:20px;font-weight:700;letter-spacing:.04em;color:#fff;background:{tint};'
            f'padding:9px 18px;border-radius:100px">✓ {_esc(b)}</span>')


def _rating_chip(p: Dict[str, Any]) -> str:
    rating = str(p.get("rating") or "").strip()
    if not rating:
        return ""
    reviews = _fmt_count(p.get("reviews") or p.get("ratings_count"))
    txt = f"★ {rating}" + (f" · <b>{reviews}</b> ratings" if reviews else "")
    return f'<span class="factchip">{txt}</span>'


def _demand_chip(p: Dict[str, Any]) -> str:
    """Show demand ONLY when it's a credible number — a bare '1'/'2' reads worse than nothing.
    Anything with a +, K or M suffix, or ≥ 50, qualifies as a real social-proof signal."""
    raw = _clean_count(p.get("bought_past_month"))
    if not raw:
        return ""
    credible = any(c in raw for c in "+KkMm")
    if not credible:
        try:
            credible = int(raw.replace(",", "")) >= 50
        except ValueError:
            credible = False
    if not credible:
        return ""
    return f'<span class="factchip"><b>{_fmt_count(raw)}</b> bought recently</span>'


def _savings_line(p: Dict[str, Any]) -> str:
    price = _num(p.get("price"))
    mrp = _num(p.get("orig_price") or p.get("mrp"))
    if price and mrp and mrp > price:
        return f'<div class="save">You save ₹{_indian_group(int(round(mrp - price)))}</div>'
    return ""


def _info_block(p: Dict[str, Any], tint: str = "#B04A32", *, name_size: int = 56,
                price_size: int = 62) -> str:
    """The rich, TRUTHFUL product overlay: a verified badge (Amazon's Choice / Best Seller),
    real trust chips (rating · reviews, demand), the serif name, the price lockup (₹ · struck
    MRP · % off) and the real savings. Every element is drawn only when its data exists."""
    chips = "".join(c for c in (_badge_pill(p, tint), _rating_chip(p), _demand_chip(p)) if c)
    chips_row = f'<div class="chips">{chips}</div>' if chips else ""
    save = _savings_line(p)
    return f"""{chips_row}
    {_lockup(p, name_size=name_size, price_size=price_size)}
    {save}"""


def _lockup(p: Dict[str, Any], *, name_size: int = 52, price_size: int = 58, show_mrp: bool = True) -> str:
    name = _esc(_name(p))[:60]
    price = _money(p.get("price"))
    mrp = _money(p.get("orig_price") or p.get("mrp")) if show_mrp else ""
    off = _discount_pct(p)
    pieces = []
    if price:
        pieces.append(f'<span class="price" style="font-size:{price_size}px">{price}</span>')
    if mrp and mrp != price:
        pieces.append(f'<span class="mrp">{mrp}</span>')
    if off:
        pieces.append(f'<span class="off" style="font-size:{max(20,int(price_size*0.36))}px">{off}% OFF</span>')
    lock = f'<div class="plock">{"".join(pieces)}</div>' if pieces else ""
    return f'<div class="pname" style="font-size:{name_size}px">{name}</div>{lock}'


def _cover_html(title: str, subtitle: str, tint: str, kick: str, imgs: List[str],
                idx: int, total: int) -> str:
    hero = next((u for u in imgs if u), "")
    hero_stage = (f'<div class="stage big" style="position:absolute;left:60px;right:60px;bottom:150px;'
                  f'height:720px;z-index:1"><img src="{hero}"></div>') if hero else ""
    inner = f"""
  <div class="placard"><span class="kick">{_esc(kick)}</span><span class="code">SK · THE EDIT</span></div>
  <div style="position:relative;z-index:2;margin-top:100px">
    <div class="serif" style="font-size:120px;line-height:.9;letter-spacing:-.02em;max-width:920px">{_esc(title)}</div>
    <div class="serif" style="font-size:50px;font-style:italic;color:{tint};margin-top:18px">{_esc(subtitle)}</div>
  </div>
  {hero_stage}
"""
    return _page(tint, inner, idx=idx, total=total)


def _hero_html(p: Dict[str, Any], img: str, tint: str, kick: str, code: str,
               idx: int, total: int) -> str:
    inner = f"""
  <div class="placard"><span class="kick">{_esc(kick)}</span><span class="code">{_esc(code)}</span></div>
  <div class="stage big" style="position:absolute;left:56px;right:56px;top:130px;height:800px;z-index:1">
    <img src="{img}">
  </div>
  <div style="position:absolute;left:60px;right:60px;bottom:140px;z-index:2;display:flex;flex-direction:column;align-items:flex-start;gap:18px">{_info_block(p, tint, name_size=60, price_size=64)}</div>
"""
    return _page(tint, inner, idx=idx, total=total)


def _deal_html(p: Dict[str, Any], img: str, tint: str, idx: int, total: int) -> str:
    off = _discount_pct(p)
    price = _money(p.get("price"))
    mrp = _money(p.get("orig_price") or p.get("mrp"))
    tag = f'<div class="off" style="font-size:34px;padding:10px 22px">↓ {off}% OFF</div>' if off else ""
    inner = f"""
  <div class="placard"><span class="kick">Price Drop</span></div>
  <div class="stage big" style="position:absolute;left:56px;right:56px;top:126px;height:660px;z-index:1"><img src="{img}"></div>
  <div style="position:absolute;left:60px;right:60px;bottom:140px;z-index:2;display:flex;flex-direction:column;align-items:flex-start;gap:18px">
    {f'<div class="chips">{_badge_pill(p, tint)}{_rating_chip(p)}{_demand_chip(p)}</div>' if (_badge_pill(p, tint) or _rating_chip(p) or _demand_chip(p)) else ''}
    <div class="pname" style="font-size:46px">{_esc(_name(p))[:52]}</div>
    <div class="plock"><span class="price" style="font-size:92px">{price}</span>{f'<span class="mrp" style="font-size:42px">{mrp}</span>' if mrp and mrp!=price else ''}</div>
    <div style="display:flex;align-items:center;gap:18px">{tag}{_savings_line(p)}</div>
  </div>
"""
    return _page(tint, inner, idx=idx, total=total)


def _value_html(p: Dict[str, Any], img: str, tint: str, idx: int, total: int) -> str:
    inner = f"""
  <div class="placard"><span class="kick">Best Value</span></div>
  <div class="stage big" style="position:absolute;left:56px;right:56px;top:130px;height:740px;z-index:1"><img src="{img}"></div>
  <div style="position:absolute;left:60px;right:60px;bottom:140px;z-index:2;display:flex;flex-direction:column;align-items:flex-start;gap:18px">
    {_info_block(p, tint, name_size=56, price_size=60)}
  </div>
"""
    return _page(tint, inner, idx=idx, total=total)


def _duo_html(ps: List[Dict[str, Any]], imgs: List[str], tint: str, idx: int, total: int) -> str:
    cols = ""
    for i, (p, u) in enumerate(zip(ps[:2], imgs[:2])):
        cols += f"""
      <div style="flex:1;display:flex;flex-direction:column;gap:22px">
        <div class="stage" style="flex:1"><img src="{u}"></div>
        <div>{_lockup(p, name_size=38, price_size=42)}</div>
      </div>"""
    inner = f"""
  <div class="placard"><span class="kick">Face-off / 02</span><span class="code">1 or 2?</span></div>
  <div style="position:absolute;left:60px;right:60px;top:150px;bottom:150px;z-index:2;display:flex;gap:26px">{cols}</div>
"""
    return _page(tint, inner, idx=idx, total=total)


def _rank_html(ps: List[Dict[str, Any]], imgs: List[str], tint: str, idx: int, total: int) -> str:
    rows = ""
    for i, (p, u) in enumerate(zip(ps[:5], imgs[:5]), 1):
        op = 1 - (i - 1) * 0.16
        price = _money(p.get("price"))
        off = _discount_pct(p)
        offtxt = f' <span class="off" style="font-size:20px;padding:3px 9px">{off}%</span>' if off else ""
        rows += f"""
      <div style="display:flex;align-items:center;gap:28px">
        <span class="rank" style="font-size:96px;opacity:{op:.2f}">{i:02d}</span>
        <div class="stage" style="width:150px;height:150px;flex:none"><img src="{u}"></div>
        <div style="flex:1">
          <div class="pname" style="font-size:38px">{_esc(_name(p))[:40]}</div>
          <div class="plock" style="margin-top:6px"><span class="price" style="font-size:38px">{price}</span>{offtxt}</div>
        </div>
      </div>"""
    inner = f"""
  <div class="placard"><span class="kick">Ranked / Top {min(5,len(ps))}</span><span class="code">SK · VERDICT</span></div>
  <div style="position:absolute;left:60px;right:60px;top:170px;bottom:150px;z-index:2;display:flex;flex-direction:column;justify-content:center;gap:30px">{rows}</div>
"""
    return _page(tint, inner, idx=idx, total=total)


def _grid_html(ps: List[Dict[str, Any]], imgs: List[str], tint: str, cols: int, kick: str,
               idx: int, total: int, theme_line: str = "") -> str:
    cells = ""
    for p, u in zip(ps, imgs):
        price = _money(p.get("price"))
        cells += f"""
      <div style="display:flex;flex-direction:column;gap:10px">
        <div class="stage" style="flex:1"><img src="{u}"></div>
        <div class="pname" style="font-size:27px">{_esc(_name(p))[:26]}</div>
        {f'<div class="price" style="font-size:30px">{price}</div>' if price else ''}
      </div>"""
    line = f'<div class="serif" style="position:absolute;left:60px;bottom:150px;z-index:2;font-size:44px">{_esc(theme_line)}</div>' if theme_line else ""
    inner = f"""
  <div class="placard"><span class="kick">{_esc(kick)}</span><span class="code">SK · THE EDIT</span></div>
  <div style="position:absolute;left:60px;right:60px;top:150px;bottom:{'230' if theme_line else '150'}px;z-index:2;
       display:grid;grid-template-columns:repeat({cols},1fr);gap:24px">{cells}</div>
  {line}
"""
    return _page(tint, inner, idx=idx, total=total)


def _lead_rail_html(ps: List[Dict[str, Any]], imgs: List[str], tint: str, idx: int, total: int) -> str:
    lead, lu = ps[0], imgs[0]
    rail = ""
    for p, u in zip(ps[1:5], imgs[1:5]):
        rail += f'<div class="stage"><img src="{u}"></div>'
    inner = f"""
  <div class="placard"><span class="kick">Top pick + {min(4,len(ps)-1)}</span><span class="code">SK · EDITOR</span></div>
  <div style="position:absolute;left:60px;right:60px;top:150px;bottom:150px;z-index:2;display:flex;gap:26px">
    <div style="flex:1.35;display:flex;flex-direction:column;gap:18px">
      <div class="stage" style="flex:1"><img src="{lu}"></div>
      <div>{_lockup(lead, name_size=40, price_size=44)}</div>
    </div>
    <div style="flex:1;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:18px">{rail}</div>
  </div>
"""
    return _page(tint, inner, idx=idx, total=total)


def _closer_html(tint: str, handle: str, idx: int, total: int) -> str:
    inner = f"""
  <div class="placard"><span class="kick">Shop the set</span><span class="code">SK · LINK</span></div>
  <div style="position:absolute;inset:150px 60px;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:44px;text-align:center">
    <div class="serif" style="font-size:100px;line-height:1.02">Everything here,<br>one link.</div>
    <span class="cta solid" style="font-size:26px">Link in bio →</span>
    <span class="rating" style="font-size:26px">{_esc(handle)} · new picks weekly</span>
  </div>
"""
    return _page(tint, inner, idx=idx, total=total)


# ── the planner: product count + arc → slide specs ────────────────────────────
def plan_slides(products: List[Dict[str, Any]], *, category: str = "", arc: str = "auto",
                handle: str = "@business.sk", theme: str = "") -> List[Dict[str, Any]]:
    """Decide the slide sequence from the products. Returns a list of specs the renderer
    consumes. Implements the multi-product logic: never shrink to fit — change structure,
    and split into a carousel with per-product slides once there are enough items."""
    n = len(products)
    tintk = category or "fashion"
    kick = (category or "The Edit").strip().title()
    specs: List[Dict[str, Any]] = []

    if n == 0:
        return specs
    if n == 1:
        p = products[0]
        tmpl = "deal" if (_discount_pct(p) or 0) >= 50 else ("value" if p.get("rating") else "hero")
        specs.append({"tmpl": tmpl, "products": [p], "kick": kick})
        return specs
    if n == 2:
        specs.append({"tmpl": "duo", "products": products[:2], "kick": kick})
        return specs
    if n == 3:
        specs.append({"tmpl": "grid3", "products": products[:3], "kick": kick, "theme_line": theme})
        return specs
    if n == 4:
        specs.append({"tmpl": "grid4", "products": products[:4], "kick": kick, "theme_line": theme})
        return specs

    # 5+ → a carousel that tells a story: cover → features → (rank/value) → closer
    title = theme or f"{kick}"
    specs.append({"tmpl": "cover", "products": products[:3], "kick": kick,
                  "title": _cover_title(theme, category, n), "subtitle": _cover_sub(products)})
    if arc == "ranking":
        specs.append({"tmpl": "rank", "products": products[:5], "kick": kick})
    for p in products[: min(n, 7)]:
        tmpl = "value" if p.get("rating") else "hero"
        specs.append({"tmpl": tmpl, "products": [p], "kick": kick})
    specs.append({"tmpl": "closer", "products": [], "kick": kick, "handle": handle})
    return specs[:10]                       # Instagram carousel hard cap


def _cover_title(theme: str, category: str, n: int) -> str:
    if theme:
        return theme
    cat = (category or "").strip().title()
    return f"The {cat}\nEdit" if cat else "This Week's\nEdit"


def _cover_sub(products: List[Dict[str, Any]]) -> str:
    n = len(products)
    prices = [p for p in (_num(x.get("price")) for x in products) if p]
    unit = "piece" if n == 1 else "pieces"
    if prices:
        hi = int(max(prices))
        return f"{n} {unit} · all under ₹{_indian_group(_round_up(hi))}"
    return f"{n} {unit} worth a look"


def _round_up(n: int) -> int:
    for step in (500, 1000, 2000, 5000, 10000):
        if n <= step:
            return step
    return ((n // 1000) + 1) * 1000


# ── render ────────────────────────────────────────────────────────────────────
def _render_htmls(htmls: List[str], out_dir: Path, cdn_prefix: str, slug: str) -> Dict[str, Any]:
    dest = out_dir / f"sk_{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    images_local: List[str] = []
    images_cdn: List[str] = []
    rendered, error = False, None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            page.set_default_timeout(20000)
            for i, doc in enumerate(htmls, 1):
                page.set_content(doc, wait_until="load")
                page.wait_for_timeout(450)          # let webfonts settle
                fname = f"slide_{i:02d}.png"
                fp = dest / fname
                page.screenshot(path=str(fp), clip={"x": 0, "y": 0, "width": W, "height": H})
                images_local.append(str(fp))
                images_cdn.append(f"{cdn_prefix}/sk_{slug}/{fname}")
            browser.close()
        rendered = True
    except Exception as exc:                        # noqa: BLE001
        error = str(exc)
    return {"rendered": rendered, "images": images_cdn, "local": images_local,
            "count": len(images_cdn), "dir": str(dest), "error": error}


def render_carousel(products: List[Dict[str, Any]], *, category: str = "", out_dir: Path,
                    cdn_prefix: str, slug: str, arc: str = "auto", handle: str = "@business.sk",
                    theme: str = "", isolate: bool = True) -> Dict[str, Any]:
    """Full pipeline: plan slides → prep each product image (staged, product-true) →
    render designed PNGs. Returns cdn urls + local paths + the plan (for auditing)."""
    tint = _tint(category)
    specs = plan_slides(products, category=category, arc=arc, handle=handle, theme=theme)
    if not specs:
        return {"rendered": False, "images": [], "local": [], "count": 0, "error": "no products"}

    # prep every unique product image once (data URIs), reused across slides
    img_cache: Dict[str, str] = {}

    def prep(p: Dict[str, Any]) -> str:
        src = (p.get("image_url") or p.get("image") or "").strip()
        if not src:
            return ""
        if src not in img_cache:
            img_cache[src] = _prep_image(src, isolate=isolate) or ""
        return img_cache[src]

    total = len(specs)
    htmls: List[str] = []
    for i, sp in enumerate(specs, 1):
        ps = sp["products"]
        imgs = [prep(p) for p in ps]
        code = f"SK—{slug[:4].upper()}"
        t = sp["tmpl"]
        if t == "cover":
            htmls.append(_cover_html(sp.get("title", ""), sp.get("subtitle", ""), tint, sp["kick"], imgs, i, total))
        elif t == "hero":
            htmls.append(_hero_html(ps[0], imgs[0], tint, sp["kick"], code, i, total))
        elif t == "deal":
            htmls.append(_deal_html(ps[0], imgs[0], tint, i, total))
        elif t == "value":
            htmls.append(_value_html(ps[0], imgs[0], tint, i, total))
        elif t == "duo":
            htmls.append(_duo_html(ps, imgs, tint, i, total))
        elif t == "rank":
            htmls.append(_rank_html(ps, imgs, tint, i, total))
        elif t == "grid3":
            htmls.append(_grid_html(ps, imgs, tint, 3, sp["kick"], i, total, sp.get("theme_line", "")))
        elif t == "grid4":
            htmls.append(_grid_html(ps, imgs, tint, 2, sp["kick"], i, total, sp.get("theme_line", "")))
        elif t == "lead_rail":
            htmls.append(_lead_rail_html(ps, imgs, tint, i, total))
        elif t == "closer":
            htmls.append(_closer_html(tint, sp.get("handle", handle), i, total))
        else:
            htmls.append(_hero_html(ps[0], imgs[0], tint, sp["kick"], code, i, total))

    result = _render_htmls(htmls, out_dir, cdn_prefix, slug)
    result["plan"] = [{"tmpl": s["tmpl"], "n": len(s["products"])} for s in specs]
    result["isolated"] = isolate and _REMBG_SESSION is not None
    return result
