# Meta / Instagram Integration — Publisher (M6) + Analytics (M7)

Two **different** mechanisms are involved. Don't confuse them:

| | Meta **MCP** (Devtools/Ads) | Instagram **Graph API** |
|---|---|---|
| What | A tool an **AI client** (Claude Code/Desktop) uses to help you *build/debug* | The REST API your **app calls at runtime** |
| Used by | Me / your AI agent, at dev time | `app/services/instagram.py`, `app/business/analytics.py` |
| Publishes carousels? | ❌ No (Devtools MCP is a dev-assistant; publishing/insights MCP tools are "forthcoming") | ✅ Yes (already implemented) |
| Returns post insights? | ❌ No | ✅ Yes (`/{media_id}/insights`) |

**So the runtime publisher + analytics run on the Graph API** (below, §2). The **MCP is an optional dev accelerator** (§1).

Sources: [Meta MCP](https://developers.facebook.com/documentation/mcp) ·
[Devtools MCP](https://developers.facebook.com/documentation/mcp/devtools-mcp) ·
[Ads MCP blog](https://developers.facebook.com/blog/post/2026/07/16/meta-ads-mcp-server/)

---

## 1. Meta MCP — connect it to *your* AI client (dev-time helper)

The MCP is consumed by an MCP-capable client, **not** embedded in this app's backend.
It helps discover Graph endpoints/permissions, troubleshoot errors, manage webhooks,
and check app compliance while building the integration.

**Add to Claude Code** (HTTP transport + browser OAuth):

```bash
# Devtools MCP — copy the exact server URL from the "connect" panel on
# https://developers.facebook.com/documentation/mcp/devtools-mcp
claude mcp add --transport http meta-devtools <DEVTOOLS_MCP_URL>

# Ads MCP (paid ads only — NOT organic posting), confirmed URL:
claude mcp add --transport http meta-ads https://mcp.facebook.com/ads
```

Then run the command, pick the server, and complete **Meta OAuth in the browser**;
grant the **minimum scopes** (read over manage where possible). Verify with the
client's tool list (`list_tools`).

> Security (from Meta's docs): agents act with whatever scopes you grant — grant the
> minimum, separate dev/prod apps, audit periodically, watch for prompt injection.

This app never stores your MCP OAuth; that lives in your client.

---

## 2. Instagram Graph API — the runtime publisher + analytics (what actually posts)

### Prerequisites (one-time)
1. **Instagram Business or Creator account**, linked to a **Facebook Page**.
2. A **Meta app** (developer.facebook.com) with these products/permissions:
   - `instagram_basic`
   - `instagram_content_publish`  → **publishing (M6)**
   - `instagram_manage_insights`  → **analytics (M7)**
   - `pages_show_list`, `pages_read_engagement`
3. A **long-lived access token** for the account, and the numeric **IG Business Account ID**.
   (Use Graph API Explorer / your token tool; exchange the short-lived token for a
   long-lived one — ~60 days — and refresh before expiry. The Devtools MCP can walk
   you through the exact endpoints + permission requirements.)

### Where credentials go
Add the account in the app's **Settings** panel (stored encrypted in the rags store,
never in the frontend): label, **IG Business ID**, **access token**. The publisher
reads them per-account. Multiple accounts are supported.

### Publishing (M6) — already wired
`POST /api/business/campaigns/{id}/publish` → `{account_id, dry_run}`
- Only **AUTO_APPROVED** campaigns can post.
- Slides are pushed to public GitHub-raw (`hosting.publish_images`) so the Graph API
  can fetch them, then posted as a **carousel** via `app/services/instagram.py`
  (`/{ig_id}/media` children → `CAROUSEL` container → `/media_publish`).
- `dry_run: true` returns the exact public URLs + caption **without** pushing/posting.
- Publishing is **irreversible + outward-facing** — invoke it deliberately.

> **GitHub-raw hosting note:** the backend container needs the git repo + push
> credentials to publish images. Set the repo/branch in Settings, and provide a
> git credential (e.g. a `GITHUB_TOKEN` remote or mounted `.git` + creds) in the
> backend container, or run the publish step where git is authenticated.

### Analytics (M7) — already wired
`POST /api/business/campaigns/{id}/analytics/sync` → `{account_id}` pulls
`/{media_id}/insights` (reach, saved, likes, comments, shares, total_interactions,
views), scores engagement, and stores it.
- `GET /api/business/analytics/campaigns/{id}` — per-campaign history
- `GET /api/business/analytics/overview` — top campaigns + averages **by angle**
  (which angle drives the best engagement — analytics-first, no RL, per Spec §37).
- Requires a **real published media id** (populated at publish time).

---

## 3. Recommended flow
```
Approve campaign → POST /publish {account_id, dry_run:true}  (verify URLs+caption)
                 → POST /publish {account_id}                (real post — your action)
                 → later: POST /analytics/sync {account_id}  (pull insights)
                 → GET /analytics/overview                   (compare angles → improve)
```
