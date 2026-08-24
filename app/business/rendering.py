"""Rendering stage (Agent 09) — deterministic HTML/CSS -> Playwright slides.

Renders each planned slide to an exact 1080x1350 Instagram image with a
template-driven design system. REAL cropped property images only (Spec §15).
Brand-aware (colors/logo/font from a Brand Preset) and language-aware (Latin +
Kannada + Devanagari via bundled Noto fonts, chosen per-glyph by the browser).
Fully deterministic; degrades to rendered=False if the browser is unavailable.
"""
from __future__ import annotations

import base64
import html
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

W, H = 1080, 1350

# Default brand (used when a campaign has no Brand Preset selected).
_DEFAULT = {
    "ink": "#0E2A3B", "ink2": "#14384d", "paper": "#F6F4EE",
    "accent": "#C79A3A", "accent2": "#E8C874", "text_light": "#FFFFFF",
    "muted": "#AFC2CE", "font": "Archivo",
}
# Indic + Latin fallback chain — the browser picks the right font per glyph, so
# Kannada/Hindi text renders correctly even in an otherwise-Latin design.
_INDIC = "'Noto Sans Kannada', 'Noto Sans Devanagari', 'Noto Sans'"


def _data_uri(path: str | None) -> str | None:
    if not path or not Path(path).exists():
        return None
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b = Path(path).read_bytes()
    return f"data:{mime};base64," + base64.b64encode(b).decode("ascii")


def _esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def _resolve_theme(brand: Optional[Dict[str, Any]]) -> Dict[str, str]:
    t = dict(_DEFAULT)
    if brand:
        if brand.get("secondary_color"):
            t["ink"] = brand["secondary_color"]
            t["ink2"] = brand["secondary_color"]
        if brand.get("primary_color"):
            t["accent"] = brand["primary_color"]
        if brand.get("accent_color"):
            t["accent2"] = brand["accent_color"]
        if brand.get("font"):
            t["font"] = brand["font"]
    return t


def _fonts(theme: Dict[str, str]) -> Tuple[str, str]:
    disp = f"'{theme['font']}', 'Archivo', {_INDIC}, sans-serif"
    body = f"'Newsreader', {_INDIC}, Georgia, serif"
    return disp, body


_FACT_LABELS = {
    "property_type": "Type", "area_sqft": "Area", "bhk": "Configuration",
    "total_units": "Units", "land_area": "Land area", "price": "Price",
    "amenities": "Amenities", "views": "Views", "builder": "Builder",
    "location": "Location", "category": "Segment", "rooms": "Rooms",
    "approvals": "Approvals", "connectivity": "Connectivity", "contacts": "Contact",
    "possession": "Possession", "rera": "RERA", "distance": "Distance",
}


def _clean_facts(facts: List[Any]) -> List[str]:
    """Make on-slide bullets professional: format hotspot dicts as 'Name — Distance',
    drop missing-data tokens, humanise snake_case field names, tidy 'key: value'. No noise."""
    out: List[str] = []
    for f in facts:
        # Structured hotspot objects ({'name','distance'}) -> "Name — Distance"
        if isinstance(f, dict):
            name = str(f.get("name") or f.get("place") or f.get("label") or "").strip()
            dist = str(f.get("distance") or f.get("dist") or f.get("value") or "").strip()
            if name and dist:
                s = f"{name} — {dist}"
            elif name or dist:
                s = name or dist
            else:
                s = ", ".join(str(v) for v in f.values() if v)
        else:
            s = str(f).strip().strip("•-·").strip()
        if not s or "NOT_AVAILABLE" in s.upper() or "NOT AVAILABLE" in s.upper():
            continue  # never surface a missing-data placeholder to a viewer
        if ":" in s:
            key, _, val = s.partition(":")
            key, val = key.strip(), val.strip()
            label = _FACT_LABELS.get(key.lower().replace(" ", "_"))
            if label is None:
                label = key.replace("_", " ").strip()
                label = label[:1].upper() + label[1:]
            s = f"{label}: {val}" if val else label
        elif "_" in s:
            s = s.replace("_", " ")
        out.append(s)
    return out


def _slide_html(slide: Dict[str, Any], model: Dict[str, Any], idx: int, total: int,
                th: Dict[str, str], disp: str, body: str, logo_uri: Optional[str]) -> str:
    img = _data_uri(slide.get("image_source"))
    _hl = slide.get("headline", "") or ""
    headline = _esc(_hl[:1].upper() + _hl[1:])       # professional: capitalised headline
    sub = _esc(slide.get("subheadline", ""))
    template = slide.get("template", "fact")
    facts = _clean_facts(slide.get("facts", []) or [])
    badges = slide.get("badges", []) or []
    cta = _esc(slide.get("cta", "")) if template == "cta" else ""
    # per-slide overrides (from the Slide Editor) win over the property model
    project = _esc(slide.get("brandname") or model["property"]["project_name"])
    locality = _esc(slide.get("locality") or model["location"].get("locality", "")
                    or model["location"].get("city", ""))
    is_context = bool(slide.get("image_is_context_bg")) or template == "map"
    attribution = _esc(slide.get("image_attribution", ""))

    # On the CTA slide the contacts render in their own block — don't repeat them as facts.
    _facts = [] if (template == "cta" and model.get("contacts")) else facts
    fact_rows = "".join(f'<div class="fact"><span class="dot"></span>{_esc(f)}</div>' for f in _facts[:5])
    badge_row = "".join(f'<span class="badge">{_esc(b)}</span>' for b in badges[:4])

    if img:
        scrim_cls = "scrim-map" if template == "map" else ("scrim-strong" if is_context or facts or cta else "scrim")
        # Plans/maps must show in full (no crop) so labels/rooms/pins stay intact —
        # they use object-fit:contain; photos use cover with a subject-protecting bias.
        plan_types = {"floor_plan", "site_plan", "cluster_plan", "location_map", "context_map"}
        contain = slide.get("image_asset_type") in plan_types or template == "map" or slide.get("image_small")
        media_cls = "media plan" if contain else "media"
        media = f'<div class="{media_cls}"><img src="{img}" alt=""/><div class="{scrim_cls}"></div></div>'
    else:
        media = ('<div class="media gradient"><div class="mono">'
                 f'{_esc(model["property"].get("property_type","").upper())}</div><div class="scrim-strong"></div></div>')

    context_tag = ('<div class="ctxtag">AREA MAP · © OpenStreetMap</div>' if template == "map"
                   else ('<div class="ctxtag">AREA CONTEXT</div>' if slide.get("image_is_context_bg") else ''))
    attribution_html = (f'<div class="attrib">{attribution}</div>' if attribution and template != "map" else '')
    logo_html = f'<img class="logo" src="{logo_uri}" alt=""/>' if logo_uri else ''
    contacts = slide.get("contacts") or model.get("contacts", [])   # per-slide override
    contact_html = ""
    if template == "cta" and contacts:
        rows = "".join(f'<div class="c">{_esc(c.get("name"))} · {_esc(c.get("phone"))}</div>' for c in contacts[:3])
        contact_html = f'<div class="contacts">{rows}</div>'
    pct = round(idx / max(1, total) * 100)          # progress bar fill

    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;800;900&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400;1,6..72,500&family=Poppins:wght@500;600;800&family=Montserrat:wght@600;800&display=swap" rel="stylesheet">
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px}}
  body{{font-family:{body};background:{th['ink']};color:{th['text_light']};overflow:hidden}}
  .slide{{width:{W}px;height:{H}px;position:relative}}
  .media{{width:100%;height:100%;position:relative;overflow:hidden;background:{th['ink2']}}}
  .media img{{width:100%;height:100%;object-fit:cover;object-position:center 40%}}
  .media.plan img{{object-fit:contain;object-position:center 42%;background:{th['ink2']}}}
  .media.gradient{{display:flex;align-items:center;justify-content:center;background:radial-gradient(120% 90% at 20% 0%, {th['ink2']}, {th['ink']})}}
  .media .mono{{font-family:{disp};letter-spacing:.4em;color:{th['muted']};font-size:34px}}
  .scrim,.scrim-strong,.scrim-map{{position:absolute;inset:0}}
  .scrim{{background:linear-gradient(180deg,rgba(9,22,31,.10) 0%,rgba(9,22,31,.55) 62%,rgba(9,22,31,.90) 100%)}}
  .scrim-strong{{background:linear-gradient(180deg,rgba(9,22,31,.40) 0%,rgba(9,22,31,.60) 46%,rgba(9,22,31,.93) 100%)}}
  .scrim-map{{background:linear-gradient(180deg,rgba(9,22,31,.62) 0%,rgba(9,22,31,.14) 30%,rgba(9,22,31,.60) 70%,rgba(9,22,31,.94) 100%)}}
  /* ── chrome: refined, understated ─────────────────────────── */
  .topbar{{position:absolute;top:52px;left:64px;right:64px;display:flex;justify-content:space-between;align-items:flex-start;gap:16px;z-index:3}}
  .brandwrap{{display:flex;align-items:center;gap:14px}}
  .logo{{height:50px;width:auto;border-radius:8px;background:rgba(255,255,255,.92);padding:5px}}
  .brandname{{font-family:'Newsreader',Georgia,serif;font-weight:500;letter-spacing:.005em;font-size:34px;color:#fff;text-shadow:0 2px 18px rgba(0,0,0,.55)}}
  .locality{{font-family:{disp};font-size:16px;color:#EAF0F4;letter-spacing:.20em;text-transform:uppercase;font-weight:600;text-align:right;max-width:46%;padding-bottom:6px;border-bottom:2px solid {th['accent']};text-shadow:0 2px 14px rgba(0,0,0,.5)}}
  .ctxtag{{position:absolute;top:118px;right:64px;z-index:3;font-family:{disp};font-size:14px;letter-spacing:.24em;text-transform:uppercase;color:#DCE6EC;opacity:.85}}
  .attrib{{position:absolute;bottom:120px;right:64px;z-index:3;font-family:{disp};font-size:15px;color:{th['muted']};opacity:.8;letter-spacing:.02em}}
  /* ── content: elegant editorial ───────────────────────────── */
  .panel{{position:absolute;left:0;right:0;bottom:0;padding:64px 64px 150px;z-index:3}}
  .kicker{{font-family:{disp};font-size:18px;font-weight:600;letter-spacing:.34em;text-transform:uppercase;color:{th['accent2']};margin-bottom:22px;display:flex;align-items:center;gap:16px}}
  .kicker::before{{content:"";width:44px;height:1.5px;background:{th['accent']};display:inline-block}}
  h1{{font-family:'Newsreader',Georgia,serif;font-weight:500;font-size:80px;line-height:1.05;letter-spacing:-.015em;text-wrap:balance;text-shadow:0 2px 26px rgba(0,0,0,.4)}}
  .sub{{font-family:'Newsreader',Georgia,serif;font-style:italic;font-weight:400;font-size:35px;line-height:1.4;color:#E9EFF3;margin-top:24px;max-width:920px}}
  .facts{{margin-top:38px;display:flex;flex-direction:column;gap:18px}}
  .fact{{display:flex;align-items:baseline;gap:20px;font-family:{disp};font-weight:400;font-size:30px;color:#EDF2F5;line-height:1.25}}
  .dot{{width:22px;height:1.5px;border-radius:0;background:{th['accent']};flex:none;position:relative;top:-9px}}
  .badges{{position:absolute;top:124px;left:64px;display:flex;gap:12px;flex-wrap:wrap;z-index:3}}
  .badge{{font-family:{disp};font-weight:600;font-size:18px;letter-spacing:.14em;text-transform:uppercase;background:rgba(12,20,28,.34);color:#F1F5F8;border:1px solid rgba(255,255,255,.30);padding:8px 18px;border-radius:999px}}
  .cta{{font-family:{disp};font-weight:700;font-size:38px;letter-spacing:.01em;background:{th['accent']};color:{th['ink']};display:inline-block;padding:22px 44px;border-radius:6px;margin-top:10px}}
  .contacts{{margin-top:32px;display:flex;flex-direction:column;gap:10px;font-family:{disp};font-size:29px;color:{th['accent2']}}}
  /* ── footer + progress ────────────────────────────────────── */
  .foot{{position:absolute;bottom:56px;left:64px;right:64px;display:flex;justify-content:space-between;align-items:center;z-index:3;font-family:{disp};font-size:20px;color:{th['muted']};letter-spacing:.14em;text-transform:uppercase}}
  .pageno{{font-family:'Newsreader',Georgia,serif;font-weight:500;font-size:26px;letter-spacing:.05em;color:#E9EFF3}}
  .pageno b{{color:{th['accent2']};font-weight:600}}
  .progress{{position:absolute;bottom:0;left:0;width:100%;height:5px;background:rgba(255,255,255,.14);z-index:4}}
  .progress i{{display:block;height:100%;background:{th['accent']};width:{pct}%}}
  .rail{{position:absolute;top:0;left:0;width:6px;height:100%;background:{th['accent']};z-index:4;opacity:.9}}
</style></head>
<body><div class="slide">
  {media}
  <div class="rail"></div>
  <div class="topbar"><div class="brandwrap">{logo_html}<div class="brandname">{project}</div></div>{f'<div class="locality">{locality}</div>' if locality else ''}</div>
  {context_tag}
  {f'<div class="badges">{badge_row}</div>' if badge_row else ''}
  {attribution_html}
  <div class="panel">
    <div class="kicker">{_esc(slide.get('template','').replace('_', ' ').upper())}</div>
    <h1>{headline}</h1>
    {f'<div class="sub">{sub}</div>' if sub else ''}
    {f'<div class="facts">{fact_rows}</div>' if fact_rows else ''}
    {f'<div class="cta">{cta}</div>' if cta else ''}
    {contact_html}
  </div>
  <div class="foot"><span class="pageno"><b>{idx:02d}</b> / {total:02d}</span><span>{_esc(slide.get("footer")) if slide.get("footer") else (_esc(model["property"]["builder"]) if model["property"]["builder"]!="NOT_AVAILABLE" else project)}</span></div>
  <div class="progress"><i></i></div>
</div></body></html>"""


def render_one_slide(campaign: Dict[str, Any], model: Dict[str, Any], index: int, *,
                     out_dir: Path, cdn_prefix: str, brand: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Render ONLY slide `index` (fast — used by the Slide Editor's Apply). Returns its
    cache-busted cdn_url, or None on failure."""
    slides = campaign["carousel"].get("slides", [])
    if index < 0 or index >= len(slides):
        return None
    th = _resolve_theme(brand)
    disp, body = _fonts(th)
    logo_uri = _data_uri(brand.get("logo_ref")) if brand else None
    slug = re.sub(r"[^a-z0-9]+", "-", model["property"]["id"].lower()).strip("-")
    dest = out_dir / f"campaign_{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    total = len(slides)
    fname = f"slide_{index + 1:02d}.png"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            page.set_default_timeout(15000)
            page.set_content(_slide_html(slides[index], model, index + 1, total, th, disp, body, logo_uri), wait_until="load")
            page.wait_for_timeout(400)
            page.screenshot(path=str(dest / fname), clip={"x": 0, "y": 0, "width": W, "height": H})
            browser.close()
    except Exception:  # noqa: BLE001
        return None
    return f"{cdn_prefix}/campaign_{slug}/{fname}"


def render_carousel(campaign: Dict[str, Any], model: Dict[str, Any], *, out_dir: Path,
                    cdn_prefix: str, brand: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    slides = campaign["carousel"].get("slides", [])
    th = _resolve_theme(brand)
    disp, body = _fonts(th)
    logo_uri = _data_uri(brand.get("logo_ref")) if brand else None
    slug = re.sub(r"[^a-z0-9]+", "-", model["property"]["id"].lower()).strip("-")
    dest = out_dir / f"campaign_{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    total = len(slides)
    images: List[str] = []
    rendered, error = False, None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            # device_scale_factor=2 -> renders at 2160x2700 (retina): crisp text +
            # full use of the high-res source crops. Instagram accepts and downscales.
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            page.set_default_timeout(15000)
            for i, sl in enumerate(slides, 1):
                page.set_content(_slide_html(sl, model, i, total, th, disp, body, logo_uri), wait_until="load")
                page.wait_for_timeout(400)
                fname = f"slide_{i:02d}.png"
                page.screenshot(path=str(dest / fname), clip={"x": 0, "y": 0, "width": W, "height": H})
                images.append(f"{cdn_prefix}/campaign_{slug}/{fname}")
            browser.close()
        rendered = True
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    return {"rendered": rendered, "images": images, "count": len(images),
            "dir": str(dest), "error": error,
            "_trace": {"agent": "09-rendering", "rendered": rendered, "slides": total,
                       "brand": (brand or {}).get("name"), "font": th["font"]}}
