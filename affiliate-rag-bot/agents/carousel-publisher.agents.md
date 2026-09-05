# Agent — Carousel Publisher (Instagram carousel posting)

**Role:** Publish a scored, curated collection as an **Instagram carousel** via the user's
selected IG account, then wire the comment→DM automation and refresh the storefront. This
is the agent that makes carousel posting *better and safer*.

**Code anchors (IG backend):** `instagram_automation/app/api.py` (`POST /api/sk/carousel`,
`ensure_affiliate_automation`), `app/services/instagram.py` (`publish`),
`app/engagement/api.py` (`_affiliate_dm_text`, post-specific rule), `app/api.py`
(`/api/sk/storefront/publish`). **Affiliate side:** `chains/compose.py` (caption),
`rag/posts.py` (`record`, labels). Legend: ✓ enforced · ⏳ pending.

---

## CP1 — Selection & ordering ✓
A carousel is **≤5 products** (Instagram carousel + our design cap), chosen as the top
products by Product Content Score ([[product-scorer]] SC7) for that category/collection.
Slide order = highest score first, so the strongest scroll-stopper is slide 1.

## CP2 — One category per carousel, uniquely labelled ✓
Each category → one carousel, posted one-by-one, recorded as `post_<N>#<category>`
(`rag/posts.py`). No ASIN repeats within a carousel (inherits [[dedup-guard]]).

## CP3 — Caption composition ✓
Caption = collection hook + per-product line (title · price · rating when present) + a
"link in bio 👆" pointer + FTC disclosure + hashtags. All numbers are real (inherits
[[content-strategist]] CG5). Captions are NOT clickable — the clickable link lives in the
DM and the storefront (CP6).

## CP4 — Secure multi-account posting ✓ (do NOT change)
Posting uses the rags-encrypted IG account chosen from the dropdown
(`rags.get_account(id, with_secret=True)` → `publish`). The token stays server-side, never
in the affiliate `.env`, never in the browser. One account, chosen per run.

## CP5 — Comment→DM automation attached per post ✓
On a successful publish, `ensure_affiliate_automation` registers the post and attaches a
**post-specific** rule: any comment → public reply ("Sent to your DM 📩") + DM with the
ACTUAL Amazon affiliate links for THAT post's products + lead capture. Post-specific rules
suppress the real-estate (JK) account-wide rules, so the two businesses never clash.

## CP5a — Per-account engagement isolation (JK ↔ SK never clash) ✓ enforced
Engagement is scoped by `social_account_id` end-to-end: rules, comments, DMs, activity, leads,
and the Posts view. `run_account_sync(account_id)` syncs ONLY that account's posts — real-estate
posts are filtered by their `account_id`, affiliate posts by `eng_posts.social_account_id`. So
switching the account dropdown loads exactly that account's automations/posts/comments/DMs, and
the affiliate account never touches real-estate media (and vice versa). Post-specific affiliate
rules still suppress account-wide rules (rules.evaluate). The Posts tab lists the account's
real-estate posts AND its affiliate posts (synthetic negative campaign_id for the latter).

## CP5d — Comment→DM sends PRODUCT CARDS (HaulPack-style) ✓ enforced
The auto-DM for an affiliate post is NOT plain text — it is an Instagram **generic-template**
carousel of product cards (`service.send_product_cards`): one card per product with its image,
name, price/discount, a **"Shop Now"** button (the Amazon affiliate link) and a **"See All
Products"** button (the public storefront / universal shop link). `_dispatch` detects an
affiliate post (`store.affiliate_products_for_media`) and sends cards; non-affiliate DMs fall
back to text. Messaging goes through the connected Page (`/{page-id}/messages`, Page token).
Each affiliate post gets ONE post-scoped rule (REPLY_TO_COMMENT + SEND_DM cards + MARK_LEAD),
created/refreshed by `ensure_affiliate_automation`.

## CP5e — DM card images are IG-fetchable (GitHub raw, not Amazon) ✓ enforced
Instagram's Messenger generic-template often CANNOT fetch Amazon CDN images
(`m.media-amazon.com`) → a card renders with "Couldn't load image" / no image. So the
comment→DM card image MUST be a re-hosted **GitHub-raw** URL, the SAME reliable host the
carousel slides use. `sk_carousel` re-hosts every product image (`_rehost_for_ig`, now 1:1
aligned so a failed slide never shifts the others) and **stamps the re-hosted URL back into
the products stored for the DM cards** (`_hi_res` maps a slide URL onto its product). The card
image therefore always equals its slide image. Never store/send an Amazon CDN URL on a card.
`app/backfill_card_images.py` repoints already-posted carousels to their existing GitHub-raw
copies (idempotent).

## CP5f — Hard per-post isolation: affiliate posts fire ONLY their own rule ✓ enforced
A comment/DM on an affiliate (Business-SK) post fires **only that post's own post-scoped
rule** — NEVER an account-wide rule (e.g. the Business-JK real-estate "site visit" auto-reply).
`process_event` detects an affiliate post via `store.affiliate_products_for_media` and filters
the loaded rules to `post_id == event.post_id` before `rules.evaluate`. This holds even if the
affiliate rule is disabled/missing, so JK and SK can NEVER clash on any account. Together with
account-scoped `load_engine_rules(account_id)` (CP5a), automations are strictly per-post and
per-account.

## CP5b — Comment→DM sending is endpoint-robust ✓ enforced
Sending a DM (public-reply and direct) tries `/{ig-business-id}/messages` first, then `/me/messages`
(`service._send_message`) — different tokens accept different targets; never assume `/me`. Reading
the DM inbox needs extended messaging permission; if unavailable the pull fails open (sending still
works). A comment triggers exactly one reply + one DM per (rule, comment) — idempotent, no repeats.

## CP5c — Near-real-time sync ✓ configurable
The engagement poller runs every `ENGAGEMENT_SYNC_INTERVAL` seconds (default **5s**, floor 5s) so
comment→DM is near-instant. Short intervals × many accounts can hit Instagram Graph rate limits —
raise the interval if rate-limit warnings appear.

## CP10 — Designed slides ("The Still Set") ✓ enforced
The carousel is NOT raw product photos — it is **designed editorial slides** rendered by
`app/services/sk_render.py` (Playwright → 1080×1350 @2×), using the Still Set identity:
the index-frame placard, per-category tint, Instrument Serif / Hanken Grotesk / Space Mono,
quiet price lockup. `plan_slides()` chooses the layout by product count (1→hero/deal/value,
2→duo, 3–4→grid, 5+→cover + per-product features + closer; ranking arc optional) — products
are never shrunk to fit; the STRUCTURE changes. `sk_carousel(design=true)` renders, pushes the
PNGs to GitHub raw (IG-fetchable) and posts those; it falls back to raw images if rendering is
unavailable so a post never fails over design. `/api/sk/render-preview` previews without posting.
Enforced truths (inherit [[product-scout]] S4, G3, G17):
  • **Product stays true to source** — the renderer only builds the ENVIRONMENT (stage, shadow,
    type). It never recolours/reshapes/relabels the product. Image prep = rembg isolation if
    installed, else a Pillow corner white-knockout (plain catalog bg only; interior whites kept).
  • **No fabrication** — MRP, discount % and rating render ONLY when present in the product data.
  • Prices use ₹ Indian grouping + tabular figures; discount derives truthfully from price vs MRP.
The caption/hashtags remain ONE structured LLM call (JSON) on the user's own model — no local LLM.

## CP6 — Storefront reflects ONLY posted products ✓ (Global G18)
The public storefront is built from `post_store.all_products`, which returns ONLY
`status='posted'` rows — generated-but-unposted, dry-run, and failed products NEVER appear on
the public link. After a real (non-dry) publish, the storefront is republished
(`/api/sk/storefront/publish`) so the newly-posted products appear on the public GitHub-Pages
link used in the IG bio. Every card carries the real affiliate tag. A post recorded with
`status='dry'` or `'failed'` is intentionally excluded from the catalog.

## CP6b — Ten unique products per post (Global G17)
A carousel targets up to 10 UNIQUE products (Instagram's carousel max). Uniqueness is
guaranteed by two-layer dedup + the embedding flywheel ([[dedup-guard]] R6–R8): no product
repeats within a carousel or across posts. When the fresh unique pool is smaller than 10,
publish fewer — never repeat or fabricate a slide to pad to 10.

## CP7 — Platform safety ✓
Respect Instagram publishing limits; post categories sequentially (not a tight loop). Dry
run posts nothing and simulates success (global rule G12). FTC disclosure is never stripped
(G3).

## CP8 — Truthful carousels
No fabricated price/discount/rating on any slide or in the caption (inherits
[[product-scout]] S4). A budget-titled carousel obeys the budget-claim guardrail
([[collection-builder]] CB2) — the summed real price must fit the claimed band.

## CP9 — Handoff / funnel position
Publisher is the **ATTENTION** stage of the funnel: Instagram → attention → storefront
(discovery) → product page (purchase intent) → Amazon (purchase) → commission. It hands off
to the engagement + storefront surfaces; it does not score or fabricate.
