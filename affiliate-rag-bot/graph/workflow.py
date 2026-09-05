"""
graph/workflow.py  —  LangGraph StateGraph (8 nodes).

START
  → scrape_amazon         Playwright: Amazon login + best sellers
  → check_duplicates      PostgreSQL: filter already-pinned ASINs
  → search_trends         Tavily: real-time trending keywords (optional)
  → rag_retrieve          pgvector: similar pins + product discovery
  → compose_pins          ONE structured LLM call: rank + write all pins
  → get_affiliate_links   Playwright: SiteStripe link generation
  → post_pinterest        Playwright: publish pins
  → store_results         pgvector + PostgreSQL: update memory
END

Conditional edges abort early when critical nodes produce nothing useful.
"""
from __future__ import annotations
from langgraph.graph import StateGraph, END

from graph.state import BotState
from graph.nodes import (
    scrape_amazon,
    check_duplicates,
    search_trends,
    rag_retrieve,
    compose_pins,          # NODE 5: single LLM call (rank + write)
    get_affiliate_links,
    post_pinterest,
    store_results,
)


# ─── Route conditions ─────────────────────────────────────────────────────────

def _has_raw(state: BotState) -> str:
    return "continue" if state.get("raw_products") else "abort"

def _has_fresh(state: BotState) -> str:
    """Abort if dedup removed all products."""
    return "continue" if state.get("fresh_products") else "abort"

def _has_content(state: BotState) -> str:
    return "continue" if state.get("generated_content") else "abort"


# ─── Build graph ──────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    builder = StateGraph(BotState)

    # ── Register all 8 nodes ─────────────────────────────────────────
    builder.add_node("scrape_amazon",       scrape_amazon)
    builder.add_node("check_duplicates",    check_duplicates)
    builder.add_node("search_trends",       search_trends)
    builder.add_node("rag_retrieve",        rag_retrieve)
    builder.add_node("compose_pins",        compose_pins)        # 1 LLM call: rank + write
    builder.add_node("get_affiliate_links", get_affiliate_links)
    builder.add_node("post_pinterest",      post_pinterest)
    builder.add_node("store_results",       store_results)

    builder.set_entry_point("scrape_amazon")

    # ── Edges ────────────────────────────────────────────────────────
    # Abort if Amazon scrape returns nothing
    builder.add_conditional_edges(
        "scrape_amazon",
        _has_raw,
        {"continue": "check_duplicates", "abort": END},
    )

    # Abort if ALL products are already pinned (nothing new to post)
    builder.add_conditional_edges(
        "check_duplicates",
        _has_fresh,
        {"continue": "search_trends", "abort": END},
    )

    # Trends → RAG → Compose (linear)
    builder.add_edge("search_trends", "rag_retrieve")
    builder.add_edge("rag_retrieve",  "compose_pins")

    # One structured LLM call ranks + writes; abort if it produced nothing.
    builder.add_conditional_edges(
        "compose_pins",
        _has_content,
        {"continue": "get_affiliate_links", "abort": END},
    )

    builder.add_edge("get_affiliate_links", "post_pinterest")
    builder.add_edge("post_pinterest",      "store_results")
    builder.add_edge("store_results",       END)

    return builder.compile()


# Compiled graph singleton
graph = build_graph()
