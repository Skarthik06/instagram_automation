"""Deterministic rule engine — the heart of the engagement platform. NO AI.

A rule matches an inbound event (a comment or a DM) by keyword/text conditions and
emits actions (reply / send-DM / tag lead / log). Everything here is pure and
testable: same input -> same output, no network, no LLM.

Design (Spec sections 15-22, 39, 40, 47):
  - Trigger types: COMMENT_RECEIVED, DM_RECEIVED (optionally scoped to a post).
  - Conditions: contains / equals / starts_with / ends_with / contains_any /
    contains_all, case-insensitive by default, with light normalization.
  - Scopes: account-wide vs post-specific; post-specific wins (higher precedence).
  - Deterministic ordering by (scope, priority) so matching is stable.
  - Template variables ({{username}} etc.) filled only when data is available.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---- text normalization + matching ---------------------------------------

_WS = re.compile(r"\s+")


def normalize(text: str, *, strip_punct: bool = False) -> str:
    """Light, non-destructive normalization: collapse whitespace, trim. Optionally
    strip surrounding punctuation so 'CONTACT!!!' matches 'contact'."""
    s = _WS.sub(" ", (text or "")).strip()
    if strip_punct:
        s = re.sub(r"^[^\w]+|[^\w]+$", "", s)
    return s


# operator -> matcher(haystack, needles) ; all lower-cased upstream when case-insensitive
def _contains(h: str, ns: List[str]) -> bool:
    return any(n and n in h for n in ns)


def _equals(h: str, ns: List[str]) -> bool:
    return any(h == n for n in ns)


def _starts(h: str, ns: List[str]) -> bool:
    return any(n and h.startswith(n) for n in ns)


def _ends(h: str, ns: List[str]) -> bool:
    return any(n and h.endswith(n) for n in ns)


def _contains_any(h: str, ns: List[str]) -> bool:
    return any(n and n in h for n in ns)


def _contains_all(h: str, ns: List[str]) -> bool:
    return all(n in h for n in ns) if ns else False


_OPERATORS = {
    "contains": _contains, "equals": _equals, "starts_with": _starts,
    "ends_with": _ends, "contains_any": _contains_any, "contains_all": _contains_all,
}


@dataclass
class Condition:
    operator: str = "contains"            # one of _OPERATORS
    keywords: List[str] = field(default_factory=list)
    case_sensitive: bool = False
    strip_punct: bool = True              # so 'CONTACT!!!' matches 'contact'

    def matches(self, text: str) -> bool:
        # Catch-all: match ANY comment/DM regardless of text (no keywords needed).
        if self.operator in ("any", "any_message", "all_messages"):
            return True
        op = _OPERATORS.get(self.operator)
        if not op or not self.keywords:
            return False
        h = normalize(text, strip_punct=self.strip_punct)
        ns = [normalize(k, strip_punct=self.strip_punct) for k in self.keywords]
        if not self.case_sensitive:
            h = h.lower()
            ns = [n.lower() for n in ns]
        return op(h, ns)


@dataclass
class Action:
    type: str                              # REPLY_TO_COMMENT | SEND_DM | ADD_TAG | MARK_LEAD | LOG_EVENT
    message: str = ""                      # template text (for reply/DM)
    tag: str = ""                          # for ADD_TAG / MARK_LEAD
    ai: bool = False                       # rephrase `message` conversationally via LLM (grounded only)


@dataclass
class Rule:
    id: Any
    name: str
    trigger_type: str                      # COMMENT_RECEIVED | DM_RECEIVED
    conditions: List[Condition]
    actions: List[Action]
    enabled: bool = True
    post_id: Optional[str] = None          # None = account-wide; set = post-specific
    priority: int = 100                    # lower runs first within a scope
    match_mode: str = "all"                # 'all' conditions must match, or 'any'

    def matches_event(self, event: "InboundEvent") -> bool:
        if not self.enabled:
            return False
        # trigger_type may be a single value or 'BOTH' (comment AND dm).
        allowed = ({"COMMENT_RECEIVED", "DM_RECEIVED"} if self.trigger_type in ("BOTH", "ANY")
                   else {self.trigger_type})
        if event.trigger_type not in allowed:
            return False
        # post-specific rule only fires for its own post
        if self.post_id is not None and self.post_id != event.post_id:
            return False
        if not self.conditions:
            return False
        results = [c.matches(event.text) for c in self.conditions]
        return all(results) if self.match_mode == "all" else any(results)


@dataclass
class InboundEvent:
    trigger_type: str                      # COMMENT_RECEIVED | DM_RECEIVED
    text: str
    post_id: Optional[str] = None
    comment_id: Optional[str] = None
    conversation_id: Optional[str] = None
    username: Optional[str] = None
    user_id: Optional[str] = None
    external_event_id: Optional[str] = None


def evaluate(rules: List[Rule], event: InboundEvent) -> List[Rule]:
    """Return the matching rules in deterministic precedence order:
    post-specific before account-wide, then by ascending priority, then by id.
    A post-specific match SUPPRESSES account-wide rules for the same trigger so a
    tuned post reply overrides the generic one (Spec section 16)."""
    matched = [r for r in rules if r.matches_event(event)]
    matched.sort(key=lambda r: (0 if r.post_id is not None else 1, r.priority, str(r.id)))
    if any(r.post_id is not None for r in matched):
        matched = [r for r in matched if r.post_id is not None]
    return matched


# ---- template variables (deterministic; only filled when data exists) -----

_VAR = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_template(text: str, context: Dict[str, Any]) -> str:
    """Fill {{username}} etc. from context. Unknown/None variables render as empty
    (never the literal 'None'), so a missing field just drops cleanly."""
    def repl(m):
        v = context.get(m.group(1))
        return "" if v is None else str(v)
    return _VAR.sub(repl, text or "")


# ---- ResponseProvider interface (Spec section 39) — AI is optional --------

class ResponseProvider:
    """Strategy for producing the outgoing text of an action. The first two are
    deterministic and require no AI; AIResponseProvider is added later and must
    fall back to Fixed on failure."""
    def build(self, action: Action, event: InboundEvent, context: Dict[str, Any]) -> str:
        raise NotImplementedError


class FixedResponseProvider(ResponseProvider):
    def build(self, action, event, context):
        return action.message


class TemplateResponseProvider(ResponseProvider):
    def build(self, action, event, context):
        return render_template(action.message, context)


class AIResponseProvider(ResponseProvider):
    """Rephrases the grounded template conversationally using an injected LLM callable.
    It NEVER invents facts — the callable is prompted to use only the template text
    (already grounded on verified property data) plus the commenter's message. Falls
    back to the deterministic template on ANY failure, so an LLM outage never blocks a
    reply. AI only runs for actions that opt in (action.ai)."""
    def __init__(self, generate):
        self._generate = generate          # (grounded_text, inbound_text, username) -> str

    def build(self, action, event, context):
        grounded = render_template(action.message, context)
        if not getattr(action, "ai", False) or self._generate is None:
            return grounded
        try:
            out = (self._generate(grounded, event.text or "", context.get("username") or "") or "").strip()
            return out or grounded
        except Exception:
            return grounded


def default_provider(mode: str = "template", generate=None) -> ResponseProvider:
    if mode == "fixed":
        return FixedResponseProvider()
    if mode == "ai" or generate is not None:
        return AIResponseProvider(generate)
    return TemplateResponseProvider()
