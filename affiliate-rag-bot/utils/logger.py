"""
utils/logger.py  —  Rich-powered terminal output.
"""
import sys

# Force UTF-8 on stdout/stderr. Under uvicorn on Windows the default console
# encoding is cp1252, which can't encode the emoji/✓ in our log lines and would
# raise UnicodeEncodeError mid-pipeline. Reconfigure before the Console is built.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.theme import Theme
from rich import print as rprint

_theme = Theme({
    "info":    "bold white",
    "success": "bold green",
    "warning": "bold yellow",
    "error":   "bold red",
    "step":    "bold cyan",
    "ai":      "bold magenta",
})

_console = Console(theme=_theme)


class _Logger:
    def info   (self, msg: str): _console.print(f"[info]ℹ  {msg}[/]")
    def success(self, msg: str): _console.print(f"[success]✔  {msg}[/]")
    def warning(self, msg: str): _console.print(f"[warning]⚠  {msg}[/]")
    def warn   (self, msg: str): self.warning(msg)
    def error  (self, msg: str): _console.print(f"[error]✖  {msg}[/]")
    def step   (self, msg: str): _console.print(f"[step]→  {msg}[/]")
    def ai     (self, msg: str): _console.print(f"[ai]✦  {msg}[/]")
    def divider(self          ): _console.print("[dim]" + "─" * 52 + "[/]")

    def banner(self):
        _console.print()
        _console.print("[bold cyan]╔══════════════════════════════════════════════════╗[/]")
        _console.print("[bold cyan]║[/][bold white]  🤖  Amazon → Pinterest RAG Affiliate Bot v3   [/][bold cyan]║[/]")
        _console.print("[bold cyan]║[/][dim]  LangGraph · LangChain · pgvector · gpt-5-nano    [/][bold cyan]║[/]")
        _console.print("[bold cyan]╚══════════════════════════════════════════════════╝[/]")
        _console.print()

    def product(self, p: dict, i: int):
        _console.print(f"\n[bold yellow]\\[Product {i+1}][/] [white]{p['title'][:60]}[/]")
        _console.print(f"  [dim]Price:[/] [green]{p.get('price','N/A')}[/]  [dim]ASIN:[/] [cyan]{p.get('asin','N/A')}[/]")

    def node(self, name: str):
        _console.rule(f"[bold cyan]NODE: {name}[/]")


log = _Logger()
