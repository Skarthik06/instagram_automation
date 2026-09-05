"""
main.py  —  CLI entry point for the RAG Affiliate Bot.

Consumes the shared pipeline (pipeline_runner.run_pipeline) and renders a live
Rich terminal dashboard showing each node as it runs.

For the web dashboard instead, run:
    venv\\Scripts\\python.exe -m uvicorn server:app   →  http://127.0.0.1:8000

Usage:
    python main.py                # live run
    python main.py --dry-run      # no actual posting
    python main.py --category fashion
"""
from __future__ import annotations
import asyncio
import sys
import time
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich import box

from config import cfg
from utils.logger import log
from pipeline_runner import run_pipeline, NODE_ORDER

console = Console()

DRY_RUN  = "--dry-run" in sys.argv
CATEGORY = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--category" and i + 1 < len(sys.argv)), None)


# ─── Live dashboard ───────────────────────────────────────────────────────────

NODE_LABELS = {
    "scrape_amazon":       "🕷  Scrape Amazon Best Sellers",
    "check_duplicates":    "🔁  Dedup Check  [PostgreSQL]",
    "search_trends":       "🔍  Tavily Trend Search",
    "rag_retrieve":        "🧠  RAG Retrieve  [pgvector]",
    "compose_pins":        "🤖  Rank + Write Pins  [1 LLM call]",
    "get_affiliate_links": "🔗  SiteStripe Affiliate Links",
    "post_pinterest":      "📌  Post to Pinterest",
    "store_results":       "💾  pgvector + PostgreSQL Write",
}

STATUS_ICONS  = {"pending": "○", "running": "◉", "done": "✔", "error": "✖", "skipped": "–"}
STATUS_STYLES = {"pending": "dim", "running": "bold cyan", "done": "bold green", "error": "bold red", "skipped": "dim yellow"}


def _build_dashboard(node_status: dict, stream_log: list[str], start_time: float) -> Panel:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("", width=3)
    table.add_column("Node", width=38)
    table.add_column("Status", width=10)

    for node in NODE_ORDER:
        status = node_status.get(node, "pending")
        icon   = STATUS_ICONS[status]
        style  = STATUS_STYLES[status]
        label  = NODE_LABELS.get(node, node)
        table.add_row(f"[{style}]{icon}[/]", f"[{style}]{label}[/]", f"[{style}]{status.upper()}[/]")

    recent   = stream_log[-4:] if stream_log else []
    log_text = "\n".join(f"  [dim]› {l}[/]" for l in recent) if recent else "  [dim]waiting...[/]"
    elapsed  = f"{time.time() - start_time:.0f}s"

    return Panel(
        f"{table}\n\n[dim]Recent:[/]\n{log_text}\n\n[dim]Elapsed: {elapsed}[/]",
        title=f"[bold cyan]🤖 Affiliate Bot  —  {datetime.now().strftime('%H:%M:%S')}[/]",
        border_style="cyan",
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    log.banner()

    try:
        cfg.validate()
    except ValueError as e:
        log.error(str(e))
        sys.exit(1)

    if DRY_RUN:
        log.warning("DRY RUN — Pinterest posts will be skipped")

    category = CATEGORY or cfg.amazon.category
    log.info(f"Category: [bold]{category}[/bold]  |  Products per run: {cfg.bot.products_per_run}")
    log.info(f"LLM: [bold]{cfg.openai_model}[/bold] (OpenAI)  |  RAG: PostgreSQL + pgvector")
    log.divider()
    console.print("[bold cyan]Running LangGraph pipeline with live streaming...[/]\n")

    node_status: dict[str, str] = {n: "pending" for n in NODE_ORDER}
    stream_log:  list[str]      = []
    start_time = time.time()

    with Live(_build_dashboard(node_status, stream_log, start_time), console=console, refresh_per_second=4) as live:
        async for ev in run_pipeline(category, cfg.bot.products_per_run, DRY_RUN):
            t = ev["type"]
            if t == "node":
                node_status[ev["node"]] = ev["status"]
            elif t == "log":
                prefix = "ERROR: " if ev.get("level") == "error" else ""
                stream_log.append(prefix + ev["message"])
            elif t == "error":
                stream_log.append(f"ERROR: {ev['message']}")
            live.update(_build_dashboard(node_status, stream_log, start_time))

    # ── Final summary ────────────────────────────────────────────────────
    log.divider()
    console.print("\n[bold]📊  RUN SUMMARY[/]")
    log.divider()
    console.print(f"[green]✔  Category:[/]   {category}")
    console.print(f"[green]✔  Elapsed:[/]    {time.time() - start_time:.0f}s")

    if stream_log:
        console.print("\n[bold]Pipeline log:[/]")
        for entry in stream_log:
            prefix = "[red]✖[/]" if entry.startswith("ERROR") else "[green]✔[/]"
            console.print(f"  {prefix}  {entry}")
    log.divider()


if __name__ == "__main__":
    asyncio.run(main())
