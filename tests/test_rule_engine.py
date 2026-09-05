"""Unit tests for the deterministic engagement rule engine (Spec section 47).

Pure — no Meta, no DB, no AI. Run: pytest tests/test_rule_engine.py
"""
from app.engagement.rules import (
    Action, Condition, InboundEvent, Rule, evaluate, normalize, render_template,
    FixedResponseProvider, TemplateResponseProvider,
)


def _comment(text, post_id=None, **kw):
    return InboundEvent(trigger_type="COMMENT_RECEIVED", text=text, post_id=post_id, **kw)


def _rule(keywords=("CONTACT",), *, id=1, post_id=None, enabled=True, op="contains",
          case_sensitive=False, priority=100, trigger="COMMENT_RECEIVED", actions=None):
    return Rule(id=id, name="r", trigger_type=trigger,
                conditions=[Condition(operator=op, keywords=list(keywords), case_sensitive=case_sensitive)],
                actions=actions or [Action(type="SEND_DM", message="hi")],
                enabled=enabled, post_id=post_id, priority=priority)


# ---- keyword matching (case-insensitive, punctuation-tolerant) -----------
def test_keyword_case_and_punctuation_variants():
    r = _rule(("CONTACT",))
    for t in ["CONTACT", "contact", "Contact", "CoNtAcT", "CONTACT!!!", "  contact  ", "please CONTACT me"]:
        assert r.matches_event(_comment(t)), t


def test_case_sensitive_rule_does_not_match_lowercase():
    r = _rule(("CONTACT",), case_sensitive=True)
    assert r.matches_event(_comment("CONTACT"))
    assert not r.matches_event(_comment("contact"))


def test_operators():
    assert _rule(("price",), op="equals").matches_event(_comment("PRICE"))
    assert not _rule(("price",), op="equals").matches_event(_comment("price now"))
    assert _rule(("buy",), op="starts_with").matches_event(_comment("BUY now"))
    assert _rule(("info",), op="ends_with").matches_event(_comment("more INFO"))
    assert _rule(("a", "b"), op="contains_any").matches_event(_comment("has b only"))
    assert _rule(("a", "b"), op="contains_all").matches_event(_comment("a and b"))
    assert not _rule(("a", "b"), op="contains_all").matches_event(_comment("only a"))


# ---- rule scoping: correct/wrong post, disabled ---------------------------
def test_post_specific_rule_only_fires_for_its_post():
    r = _rule(post_id="P128")
    assert r.matches_event(_comment("CONTACT", post_id="P128"))
    assert not r.matches_event(_comment("CONTACT", post_id="P999"))


def test_disabled_rule_never_matches():
    assert not _rule(enabled=False).matches_event(_comment("CONTACT"))


def test_trigger_type_must_match():
    dm_rule = _rule(trigger="DM_RECEIVED")
    assert not dm_rule.matches_event(_comment("CONTACT"))  # comment event, DM rule


# ---- precedence: post-specific overrides account-wide ---------------------
def test_post_specific_suppresses_account_wide():
    acct = _rule(id="acct", post_id=None)
    post = _rule(id="post", post_id="P1")
    got = evaluate([acct, post], _comment("CONTACT", post_id="P1"))
    assert [r.id for r in got] == ["post"]          # account-wide suppressed


def test_account_wide_used_when_no_post_specific():
    acct = _rule(id="acct", post_id=None)
    got = evaluate([acct], _comment("CONTACT", post_id="P1"))
    assert [r.id for r in got] == ["acct"]


def test_priority_ordering_within_scope():
    a = _rule(id="a", priority=200)
    b = _rule(id="b", priority=50)
    got = evaluate([a, b], _comment("CONTACT"))
    assert [r.id for r in got] == ["b", "a"]         # lower priority first


# ---- multiple keyword rules -----------------------------------------------
def test_multiple_keyword_rules_each_route_correctly():
    rules = [_rule(("CONTACT",), id="c"), _rule(("PRICE",), id="p"), _rule(("PDF",), id="d")]
    assert [r.id for r in evaluate(rules, _comment("send me the PRICE"))] == ["p"]
    assert [r.id for r in evaluate(rules, _comment("PDF please"))] == ["d"]
    assert evaluate(rules, _comment("hello")) == []


# ---- templates ------------------------------------------------------------
def test_template_fills_available_vars_and_drops_missing():
    ctx = {"username": "rahul", "post_title": "2 BHK", "phone": None}
    out = render_template("Hi {{username}}, thanks for {{post_title}}. {{phone}}{{missing}}", ctx)
    assert out == "Hi rahul, thanks for 2 BHK. "


def test_response_providers():
    a = Action(type="SEND_DM", message="Hi {{username}}!")
    ev = _comment("CONTACT", username="priya")
    assert FixedResponseProvider().build(a, ev, {"username": "priya"}) == "Hi {{username}}!"
    assert TemplateResponseProvider().build(a, ev, {"username": "priya"}) == "Hi priya!"


def test_normalize():
    assert normalize("  a   b ") == "a b"
    assert normalize("CONTACT!!!", strip_punct=True) == "CONTACT"
