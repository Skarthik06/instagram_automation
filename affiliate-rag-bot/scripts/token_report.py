"""
scripts/token_report.py  —  Measure the LLM optimisation.

Compares the OLD two-stage design (ranker + per-product content = 1 + N calls)
against the NEW single structured call (chains/compose.py), on the same
representative data, using tiktoken. Reports requests, input/output tokens,
the input:output ratio, and estimated gpt-4.1-nano cost.

Run:  venv\\Scripts\\python.exe scripts\\token_report.py
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── tiktoken encoder (gpt-4o family = o200k_base), with graceful fallback ──
try:
    import tiktoken
    try:
        ENC = tiktoken.get_encoding("o200k_base")
        ENC_NAME = "o200k_base"
    except Exception:
        ENC = tiktoken.get_encoding("cl100k_base")
        ENC_NAME = "cl100k_base (fallback)"
    def ntok(s: str) -> int:
        return len(ENC.encode(s))
except Exception:
    ENC_NAME = "approx (chars/4)"
    def ntok(s: str) -> int:
        return max(1, len(s) // 4)

MSG_OVERHEAD = 3   # ~chat formatting tokens per message
REQ_OVERHEAD = 3   # ~priming tokens per request

# gpt-4.1-nano pricing (USD / 1M tokens) — adjust if OpenAI changes it.
PRICE_IN, PRICE_OUT = 0.100, 0.400


# ─── Representative data (one realistic run) ──────────────────────────────────

N = 3  # products_per_run

PRODUCTS = [
    {"title": f"{brand} {desc}", "price": price, "category": "home"}
    for brand, desc, price in [
        ("Sttelli", "Borosilicate Glass Water Bottle 1 Litre Leak-Proof Fridge Bottle Pack of 3", "₹499"),
        ("Wakefit", "Orthopedic Memory Foam Mattress Single Bed Medium Firm 72x36x6 inch", "₹6,999"),
        ("Amazon Basics", "Stainless Steel Insulated Water Bottle 750ml Vacuum Flask Hot Cold", "₹749"),
        ("Cello", "Opalware Dazzle Dinner Set 18 Pieces White Lightweight Microwave Safe", "₹1,299"),
        ("Solimo", "12-Piece Nonstick Cookware Set Induction Bottom Gas Compatible PFOA Free", "₹2,499"),
        ("HOKIPO", "Self Adhesive Wall Hooks Heavy Duty Waterproof Set of 10 Transparent", "₹299"),
        ("Story@Home", "Microfibre Reversible Quilt Comforter Double Bed AC Blanket Floral", "₹899"),
        ("Pigeon", "Stovekraft Healthifry Digital Air Fryer 1200W 4.2L Timer Temp Control", "₹3,499"),
        ("Milton", "Thermosteel Flip Lid Flask 1000ml 24 Hours Hot Cold Stainless Steel", "₹1,049"),
        ("Urban Ladder", "Engineered Wood Wall Shelf Set of 2 Floating Shelves Honey Finish", "₹1,199"),
        ("Amazon Brand Umi", "Cotton 144 TC Bedsheet Double Bed with 2 Pillow Covers Geometric", "₹649"),
        ("Prestige", "Electric Kettle PKOSS 1.5 Litre Stainless Steel Auto Shut Off 1500W", "₹999"),
        ("BSB HOME", "Microfiber 3D Printed Double Bedsheet with 2 Pillow Covers King Size", "₹579"),
        ("Kuber Industries", "Plastic 3 Layer Multipurpose Storage Organiser Rack Drawer Beige", "₹1,399"),
        ("Borosil", "Glass Mixing Bowl with Lid Set of 3 Microwave Safe Oven Safe Clear", "₹1,150"),
    ]
]

TRENDS = ["cozy home decor", "small space organization", "aesthetic kitchen",
          "renter friendly", "minimalist home", "home essentials 2026",
          "budget home makeover", "storage hacks"]

RAG_EXAMPLES = [  # past similar pins (content RAG)
    {"pin_title": "7 Cozy Living Room Finds That Make Small Spaces Feel Huge",
     "pin_description": "Renter-friendly decor picks under budget that instantly warm up any apartment. Swipe for the full cozy setup checklist and shopping links.",
     "distance": 0.18},
    {"pin_title": "The Kitchen Organizer Everyone's Obsessed With Right Now",
     "pin_description": "This 3-layer storage rack cleared my entire countertop in minutes. Perfect for tiny kitchens that need more room without a renovation.",
     "distance": 0.27},
    {"pin_title": "Aesthetic Home Upgrades Under ₹1500 (You Need #3)",
     "pin_description": "Affordable finds that look way more expensive than they are. Bookmark these for your next budget-friendly home makeover weekend.",
     "distance": 0.31},
]

PRODUCT_IDEAS = ["insulated steel water bottle", "memory foam mattress",
                 "nonstick cookware set", "floating wall shelves",
                 "microfibre comforter", "multipurpose storage rack"]

# Realistic model outputs (what a good response looks like) ───────────────────
RANK_OUT = "[7, 4, 3]"
PIN_OUT = {
    "pin_title": "This ₹3500 Air Fryer Quietly Replaced 4 of My Kitchen Gadgets",
    "pin_description": "The Pigeon Healthifry crisps everything with barely any oil — fries, tikka, even reheats leftovers perfectly. A must-have for small-space cooking and budget home makeovers. #Ad | As an Amazon Associate I earn from qualifying purchases.",
    "hashtags": ["airfryer", "kitchenessentials", "healthycooking", "homeessentials", "smallkitchen"],
}
PIN_OUT_STR = json.dumps(PIN_OUT, ensure_ascii=False)
BATCH_OUT_STR = json.dumps({"pins": [dict(id=i, **PIN_OUT) for i in (7, 4, 3)]}, ensure_ascii=False)


# ─── OLD design prompts (verbatim from the pre-refactor ranker.py/content.py) ──

OLD_RANK_SYS = """You are an Amazon affiliate marketing strategist optimising for Pinterest revenue.

Commission rates (prioritise higher):
  Fashion/Apparel 9%  |  Furniture/Home 8%  |  Kitchen 7%  |  Beauty 6%  |  Electronics 2-5%

Pinterest success factors:
  1. Visually stunning — home décor, fashion, kitchen aesthetics
  2. Solves an obvious problem or has aspirational appeal
  3. ₹500–₹5000 price range (impulse-purchase sweet spot)
  4. Products similar to past successes (provided as RAG context)

Return ONLY a JSON array of product IDs (0-indexed integers), best first. Nothing else."""

OLD_RANK_HUMAN = """Select the best {count} products from this list.

PRODUCTS:
{products_json}

TRENDING KEYWORDS (use as signal for demand):
{trends}

RAG PRODUCT IDEAS — product types that have performed well before (bias toward similar):
{rag_ideas}

Return ONLY a JSON array like: [3, 0, 7, 1, 5]"""

OLD_CONTENT_SYS = """You are a world-class Pinterest SEO expert and affiliate marketer.

You create pins that go viral on Pinterest and drive high-converting affiliate sales.
Your content feels authentic, never spammy, and is fully FTC-compliant.

RULES:
1. pin_title must be under 100 characters and spark curiosity
2. pin_description must be 2-3 sentences, include keywords naturally, end with:
   "#Ad | As an Amazon Associate I earn from qualifying purchases."
3. hashtags: 5 tags, no # symbol, mix broad + niche
4. Study the RAG examples carefully — they show what style works
5. Weave in trending keywords naturally where they fit

Respond ONLY with valid JSON matching the schema. No markdown fences."""

OLD_CONTENT_HUMAN = """Product to promote:
- Title:    {product_title}
- Price:    {product_price}
- Category: {product_category}

Trending keywords to weave in (use 2-3 naturally):
{trend_keywords}

RAG context — past pins that performed well in this niche:
{rag_context}

Generate the Pinterest pin content now."""


def old_format_rag(examples):
    lines = []
    for i, ex in enumerate(examples[:3], 1):
        lines.append(f"Example {i} (similarity: {1 - ex['distance']:.0%}):")
        lines.append(f"  Title: {ex['pin_title']}")
        lines.append(f"  Desc:  {ex['pin_description'][:120]}...")
        lines.append("")
    return "\n".join(lines)


def measure_old():
    slim = [{"id": i, "title": p["title"], "price": p["price"], "category": p["category"]}
            for i, p in enumerate(PRODUCTS)]
    rank_human = OLD_RANK_HUMAN.format(
        count=N,
        products_json=json.dumps(slim, indent=2),
        trends=", ".join(TRENDS[:6]),
        rag_ideas="\n".join(f"  - {i}" for i in PRODUCT_IDEAS[:6]),
    )
    rank_in = ntok(OLD_RANK_SYS) + ntok(rank_human) + 2 * MSG_OVERHEAD + REQ_OVERHEAD
    rank_out = ntok(RANK_OUT)

    content_human = OLD_CONTENT_HUMAN.format(
        product_title=PRODUCTS[7]["title"], product_price=PRODUCTS[7]["price"],
        product_category="home",
        trend_keywords=", ".join(TRENDS[:8]),
        rag_context=old_format_rag(RAG_EXAMPLES),
    )
    one_content_in = ntok(OLD_CONTENT_SYS) + ntok(content_human) + 2 * MSG_OVERHEAD + REQ_OVERHEAD
    one_content_out = ntok(PIN_OUT_STR)

    return {
        "requests": 1 + N,
        "input": rank_in + N * one_content_in,
        "output": rank_out + N * one_content_out,
    }


def measure_new():
    from chains.compose import SYSTEM, HUMAN, _candidates_block, _winners_block, PinBatch
    human = HUMAN.format(
        count=N,
        candidates=_candidates_block(PRODUCTS),
        trends=", ".join(TRENDS[:6]),
        winners=_winners_block(RAG_EXAMPLES, PRODUCT_IDEAS),
    )
    base_in = ntok(SYSTEM) + ntok(human) + 2 * MSG_OVERHEAD + REQ_OVERHEAD

    # structured output adds the tool/function schema to the request
    schema_tokens = 0
    try:
        from langchain_core.utils.function_calling import convert_to_openai_tool
        schema_tokens = ntok(json.dumps(convert_to_openai_tool(PinBatch)))
    except Exception:
        schema_tokens = 120  # rough estimate

    return {
        "requests": 1,
        "input": base_in + schema_tokens,
        "output": ntok(BATCH_OUT_STR),
        "schema_tokens": schema_tokens,
    }


def cost(inp, out):
    return inp / 1_000_000 * PRICE_IN + out / 1_000_000 * PRICE_OUT


def bar(label, old, new):
    print(f"  {label:<22} {old:>10,}   →   {new:>10,}   ({pct(old, new)})")


def pct(old, new):
    if old == 0:
        return "—"
    d = (new - old) / old * 100
    return f"{d:+.0f}%"


def main():
    o, n = measure_old(), measure_new()
    o_tot, n_tot = o["input"] + o["output"], n["input"] + n["output"]
    o_cost, n_cost = cost(o["input"], o["output"]), cost(n["input"], n["output"])

    print("\n" + "=" * 66)
    print(f"  LLM OPTIMISATION — token report   (encoder: {ENC_NAME})")
    print(f"  Scenario: {len(PRODUCTS)} candidates → {N} pins per run")
    print("=" * 66)
    print(f"  {'metric':<22} {'OLD (1+N)':>10}       {'NEW (1 call)':>10}   change")
    print("-" * 66)
    bar("LLM requests", o["requests"], n["requests"])
    bar("Input tokens", o["input"], n["input"])
    bar("Output tokens", o["output"], n["output"])
    bar("Total tokens", o_tot, n_tot)
    print("-" * 66)
    print(f"  {'Input:output ratio':<22} {o['input']/max(o['output'],1):>9.1f}:1   →   {n['input']/max(n['output'],1):>9.1f}:1")
    print(f"  {'Est. cost / run (USD)':<22} ${o_cost:>9.5f}   →   ${n_cost:>9.5f}   ({pct(o_cost, n_cost)})")
    print("-" * 66)
    runs_day = 8
    print(f"  At {runs_day} runs/day: ${o_cost*runs_day*30:.2f}/mo  →  ${n_cost*runs_day*30:.2f}/mo")
    print(f"  (new request includes ~{n['schema_tokens']} tokens of structured-output schema)")
    print("=" * 66 + "\n")


if __name__ == "__main__":
    main()
