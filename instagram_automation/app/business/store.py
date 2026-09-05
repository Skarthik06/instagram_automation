"""Persistence for the Business platform — PostgreSQL + JSONB (Spec §22).

Stores properties (validated knowledge model + evidence), campaigns (marketing +
carousel + contract), and run traces/cost. Uses the same Postgres connection shim
as the rest of the app. Content-addressed by property_id so re-runs upsert rather
than duplicate; each campaign is versioned by insert (Spec §23 groundwork).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from psycopg.types.json import Jsonb

from app.db import connect

_NOW = "to_char(now(),'YYYY-MM-DD HH24:MI:SS')"


def init_business_db() -> None:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_properties (
                id          TEXT PRIMARY KEY,
                project_name TEXT,
                document    TEXT,
                model       JSONB,
                verdict     JSONB,
                updated_at  TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_campaigns (
                id          SERIAL PRIMARY KEY,
                property_id TEXT,
                goal        TEXT,
                angle       TEXT,
                status      TEXT DEFAULT 'REVIEW_REQUIRED',
                brief       JSONB,
                marketing   JSONB,
                carousel    JSONB,
                caption     JSONB,
                contract    JSONB,
                images      JSONB,
                created_at  TEXT DEFAULT ({_NOW})
            )""")
        # brief column added after initial release — safe idempotent migration.
        cur.execute("ALTER TABLE business_campaigns ADD COLUMN IF NOT EXISTS brief JSONB")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_property_versions (
                id          SERIAL PRIMARY KEY,
                property_id TEXT,
                version_no  INTEGER,
                model       JSONB,
                created_at  TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_brands (
                id            SERIAL PRIMARY KEY,
                name          TEXT NOT NULL,
                logo_ref      TEXT,
                logo_cdn      TEXT,
                primary_color   TEXT DEFAULT '#C79A3A',
                secondary_color TEXT DEFAULT '#0E2A3B',
                accent_color    TEXT DEFAULT '#E8C874',
                font          TEXT DEFAULT 'Poppins',
                style         TEXT DEFAULT 'premium',
                footer        TEXT DEFAULT '',
                created_at    TEXT DEFAULT ({_NOW})
            )""")
        cur.execute("ALTER TABLE business_properties ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_templates (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                config      JSONB,
                created_at  TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_leads (
                id           SERIAL PRIMARY KEY,
                property_id  TEXT,
                campaign_id  INTEGER,
                channel      TEXT,
                contact      TEXT,
                name         TEXT,
                message      TEXT,
                status       TEXT DEFAULT 'new',
                created_at   TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_schedules (
                campaign_id  INTEGER PRIMARY KEY,
                scheduled_at TEXT,
                account_id   INTEGER,
                created_at   TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_jobs (
                id          TEXT PRIMARY KEY,
                kind        TEXT,
                status      TEXT DEFAULT 'queued',
                result      JSONB,
                error       TEXT,
                created_at  TEXT DEFAULT ({_NOW}),
                updated_at  TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_analytics (
                id            SERIAL PRIMARY KEY,
                campaign_id   INTEGER,
                property_id   TEXT,
                media_id      TEXT,
                permalink     TEXT,
                account_label TEXT,
                metrics       JSONB,
                score         REAL,
                synced_at     TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS admin_audit (
                id             SERIAL PRIMARY KEY,
                action         TEXT NOT NULL,
                entity         TEXT,
                entity_id      TEXT,
                previous_value TEXT,
                new_value      TEXT,
                created_at     TEXT DEFAULT ({_NOW})
            )""")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS business_runs (
                id           SERIAL PRIMARY KEY,
                property_id  TEXT,
                document     TEXT,
                usage        JSONB,
                traces       JSONB,
                grade        JSONB,
                duration_ms  INTEGER,
                created_at   TEXT DEFAULT ({_NOW})
            )""")


def save_run(result: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert the property, insert a campaign + run. Returns the new ids."""
    model = result["knowledge_model"]
    pid = model["property"]["id"]
    verdict = result.get("verdict") or {}
    status = "AUTO_APPROVED" if verdict.get("status") == "PASS" else "REVIEW_REQUIRED"
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO business_properties (id, project_name, document, model, verdict, updated_at)
            VALUES (?, ?, ?, ?, ?, {_NOW})
            ON CONFLICT (id) DO UPDATE SET project_name=excluded.project_name,
                document=excluded.document, model=excluded.model,
                verdict=excluded.verdict, updated_at=excluded.updated_at
        """, (pid, model["property"]["project_name"], result.get("document"),
              Jsonb(model), Jsonb(verdict)))
        cur.execute("""
            INSERT INTO business_campaigns
                (property_id, goal, angle, status, marketing, carousel, caption, contract, images)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
        """, (pid, result["contract"].get("campaign_id", "").split("-")[-1],
              (result.get("marketing") or {}).get("angle"), status,
              Jsonb(result.get("marketing")), Jsonb(result.get("carousel")),
              Jsonb(result.get("caption")), Jsonb(result.get("contract")),
              Jsonb(result.get("render", {}).get("images", []))))
        campaign_id = int(cur.fetchone()["id"])
        cur.execute("""
            INSERT INTO business_runs (property_id, document, usage, traces, grade, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?) RETURNING id
        """, (pid, result.get("document"), Jsonb(result.get("usage")),
              Jsonb(result.get("traces")), Jsonb(result.get("grade")),
              result.get("duration_ms")))
        run_id = int(cur.fetchone()["id"])
    return {"property_id": pid, "campaign_id": campaign_id, "run_id": run_id, "status": status}


def save_property(model: Dict[str, Any], verdict: Dict[str, Any], document: str) -> str:
    """Upsert the extracted Property Knowledge (Stage A). Returns property_id."""
    pid = model["property"]["id"]
    with connect() as conn:
        cur = conn.cursor()
        # merge source_documents so re-uploads enrich rather than clobber (Spec §34)
        cur.execute("SELECT model FROM business_properties WHERE id = ?", (pid,))
        row = cur.fetchone()
        if row and row.get("model"):
            prev_docs = (row["model"] or {}).get("source_documents", [])
            docs = sorted(set(prev_docs) | set(model.get("source_documents", [])))
            model = {**model, "source_documents": docs}
        cur.execute(f"""
            INSERT INTO business_properties (id, project_name, document, model, verdict, updated_at)
            VALUES (?, ?, ?, ?, ?, {_NOW})
            ON CONFLICT (id) DO UPDATE SET project_name=excluded.project_name,
                document=excluded.document, model=excluded.model,
                verdict=excluded.verdict, updated_at=excluded.updated_at
        """, (pid, model["property"]["project_name"], document, Jsonb(model), Jsonb(verdict)))
    return pid


def get_property_model(pid: str) -> Optional[Dict[str, Any]]:
    """Load the saved Property Knowledge Model for reuse across campaigns (Stage B)."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT model FROM business_properties WHERE id = ?", (pid,))
        row = cur.fetchone()
        return row["model"] if row else None


# ---- Manual property CRUD + status (/api/v1 §8) ---------------------------

def create_property_manual(fields: Dict[str, Any]) -> str:
    import re as _re
    name = fields.get("project_name") or "Property"
    pid = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "property"
    model = {
        "property": {"id": pid, "project_name": name,
                     "property_type": fields.get("property_type", "NOT_AVAILABLE"),
                     "category": "NOT_AVAILABLE", "status": "new",
                     "builder": fields.get("builder", "NOT_AVAILABLE"),
                     "developer": "NOT_AVAILABLE"},
        "location": {"city": fields.get("city", "NOT_AVAILABLE"), "locality": "NOT_AVAILABLE",
                     "address": "NOT_AVAILABLE", "pincode": "NOT_AVAILABLE",
                     "landmark": "NOT_AVAILABLE", "latitude": None, "longitude": None},
        "configuration": [], "pricing": {"price": "NOT_AVAILABLE", "currency": "INR"},
        "project": {"land_area": "NOT_AVAILABLE", "total_units": None, "floors": None, "blocks": None},
        "amenities": [], "connectivity": [], "approvals": [], "features": [], "views": [],
        "floor_plans": [], "media": [], "contacts": [], "source_documents": [],
        "claims": [], "conflicts": [], "confidence": {},
    }
    save_property(model, {"status": "REVIEW_REQUIRED", "confidence": 0.0}, "manual")
    return pid


def update_property_fields(pid: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    model = get_property_model(pid)
    if not model:
        return None
    for k in ("project_name", "property_type", "category", "builder", "developer"):
        if k in fields and fields[k] is not None:
            model["property"][k] = fields[k]
    for k in ("city", "locality", "address", "pincode", "landmark"):
        if k in fields and fields[k] is not None:
            model["location"][k] = fields[k]
    save_property(model, {"status": "REVIEW_REQUIRED"}, model.get("source_documents", ["manual"])[0] if model.get("source_documents") else "manual")
    return model


def archive_property(pid: str) -> bool:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE business_properties SET status = 'archived' WHERE id = ?", (pid,))
        return cur.rowcount > 0


def set_fact_status(pid: str, field: str, status: str) -> Optional[Dict[str, Any]]:
    """Approve/reject an extracted fact by marking its claim (/api/v1 §9)."""
    model = get_property_model(pid)
    if not model:
        return None
    hit = None
    for c in model.get("claims", []):
        if c.get("field") == field:
            c["status"] = status
            hit = c
    if hit is not None:
        save_property(model, {"status": "REVIEW_REQUIRED"},
                      model.get("source_documents", ["manual"])[0] if model.get("source_documents") else "manual")
    return hit


# ---- Templates CRUD (/api/v1 §48) -----------------------------------------

def list_templates() -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_templates ORDER BY id")
        return [dict(r) for r in cur.fetchall()]


def create_template(name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO business_templates (name, config) VALUES (?, ?) RETURNING id",
                    (name, Jsonb(config)))
        tid = int(cur.fetchone()["id"])
        cur.execute("SELECT * FROM business_templates WHERE id = ?", (tid,))
        return dict(cur.fetchone())


def get_template(tid: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_templates WHERE id = ?", (tid,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_template(tid: int, name: Optional[str], config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    sets, params = [], []
    if name is not None:
        sets.append("name = ?"); params.append(name)
    if config is not None:
        sets.append("config = ?"); params.append(Jsonb(config))
    if sets:
        params.append(tid)
        with connect() as conn:
            conn.execute(f"UPDATE business_templates SET {', '.join(sets)} WHERE id = ?", params)
    return get_template(tid)


def delete_template(tid: int) -> bool:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM business_templates WHERE id = ?", (tid,))
        return cur.rowcount > 0


# ---- Campaign brief merge + scheduling (/api/v1 §19/§24-27/§51) -----------

def merge_campaign_brief(campaign_id: int, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    c = get_campaign(campaign_id)
    if not c:
        return None
    brief = dict(c.get("brief") or {})
    brief.update({k: v for k, v in patch.items() if v is not None})
    with connect() as conn:
        conn.execute("UPDATE business_campaigns SET brief = ? WHERE id = ?", (Jsonb(brief), campaign_id))
    return brief


def schedule_campaign(campaign_id: int, scheduled_at: str, account_id: Optional[int]) -> None:
    with connect() as conn:
        conn.execute("""INSERT INTO business_schedules (campaign_id, scheduled_at, account_id)
                        VALUES (?, ?, ?) ON CONFLICT (campaign_id) DO UPDATE SET
                        scheduled_at=excluded.scheduled_at, account_id=excluded.account_id""",
                     (campaign_id, scheduled_at, account_id))


def get_schedule(campaign_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_schedules WHERE campaign_id = ?", (campaign_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def unschedule_campaign(campaign_id: int) -> bool:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM business_schedules WHERE campaign_id = ?", (campaign_id,))
        return cur.rowcount > 0


def list_schedules() -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT s.campaign_id, s.scheduled_at, s.account_id, c.goal, c.angle,
                              c.property_id, c.status
                       FROM business_schedules s LEFT JOIN business_campaigns c ON c.id=s.campaign_id
                       ORDER BY s.scheduled_at""")
        return [dict(r) for r in cur.fetchall()]


# ---- Leads (/api/v1 §19 lead generation) ----------------------------------

def save_lead(fields: Dict[str, Any]) -> Dict[str, Any]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO business_leads (property_id, campaign_id, channel, contact, name, message, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
                    (fields.get("property_id"), fields.get("campaign_id"), fields.get("channel", "manual"),
                     fields.get("contact"), fields.get("name"), fields.get("message"),
                     fields.get("status", "new")))
        lid = int(cur.fetchone()["id"])
        cur.execute("SELECT * FROM business_leads WHERE id = ?", (lid,))
        return dict(cur.fetchone())


def list_leads(limit: int = 200) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_leads ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


def set_lead_status(lead_id: int, status: str) -> bool:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE business_leads SET status = ? WHERE id = ?", (status, lead_id))
        return cur.rowcount > 0


# ---- Async jobs (/api/v1 §13/§38) -----------------------------------------

def set_job_processing(jid: str) -> None:
    with connect() as conn:
        conn.execute(f"UPDATE business_jobs SET status='processing', updated_at={_NOW} WHERE id=?", (jid,))




def create_job(kind: str) -> str:
    import secrets
    jid = "JOB-" + secrets.token_hex(6)
    with connect() as conn:
        conn.execute("INSERT INTO business_jobs (id, kind, status) VALUES (?, ?, 'queued')", (jid, kind))
    return jid


def finish_job(jid: str, *, status: str, result: Any = None, error: str = None) -> None:
    with connect() as conn:
        conn.execute(f"UPDATE business_jobs SET status=?, result=?, error=?, updated_at={_NOW} WHERE id=?",
                     (status, Jsonb(result) if result is not None else None, error, jid))


def get_job(jid: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_jobs WHERE id = ?", (jid,))
        row = cur.fetchone()
        return dict(row) if row else None


# ---- Versioning (M5, Spec §35) --------------------------------------------

def _key_facts(model: Dict[str, Any]) -> Dict[str, Any]:
    """The factual fingerprint used to detect meaningful changes across versions."""
    cfg = (model.get("configuration") or [{}])[0]
    return {
        "project_name": model["property"].get("project_name"),
        "builder": model["property"].get("builder"),
        "property_type": model["property"].get("property_type"),
        "total_units": model["project"].get("total_units"),
        "land_area": model["project"].get("land_area"),
        "area_sqft": cfg.get("area_sqft"),
        "bhk": cfg.get("bhk"),
        "price": model["pricing"].get("price"),
        "city": model["location"].get("city"),
        "locality": model["location"].get("locality"),
        "amenities_count": len(model.get("amenities", [])),
        "connectivity_count": len(model.get("connectivity", [])),
        "contacts_count": len(model.get("contacts", [])),
        "approvals": ", ".join(sorted(model.get("approvals", []))),
    }


def list_versions(pid: str) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, version_no, created_at FROM business_property_versions "
                    "WHERE property_id = ? ORDER BY version_no", (pid,))
        return [dict(r) for r in cur.fetchall()]


def get_version(version_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_property_versions WHERE id = ?", (version_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _latest_version_model(pid: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT model FROM business_property_versions WHERE property_id = ? "
                    "ORDER BY version_no DESC LIMIT 1", (pid,))
        row = cur.fetchone()
        return row["model"] if row else None


def snapshot_version(pid: str, model: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Save a version snapshot only when the key facts changed (Spec §35). Returns
    {version_no, changed_fields, affected_campaigns} when a new version was created."""
    prev = _latest_version_model(pid)
    changed = diff_key_facts(prev, model) if prev else []
    if prev is not None and not changed:
        return None  # nothing meaningful changed -> no new version
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(version_no),0)+1 AS n FROM business_property_versions "
                    "WHERE property_id = ?", (pid,))
        vno = int(cur.fetchone()["n"])
        cur.execute("INSERT INTO business_property_versions (property_id, version_no, model) "
                    "VALUES (?, ?, ?)", (pid, vno, Jsonb(model)))
        cur.execute("SELECT COUNT(*) AS n FROM business_campaigns WHERE property_id = ?", (pid,))
        affected = int(cur.fetchone()["n"]) if changed else 0
    return {"version_no": vno, "changed_fields": changed, "affected_campaigns": affected}


def diff_key_facts(old: Optional[Dict[str, Any]], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not old:
        return []
    ko, kn = _key_facts(old), _key_facts(new)
    return [{"field": k, "old": ko.get(k), "new": kn.get(k)}
            for k in kn if str(ko.get(k)) != str(kn.get(k))]


def compare_versions(pid: str, from_id: int, to_id: int) -> Dict[str, Any]:
    a, b = get_version(from_id), get_version(to_id)
    if not a or not b:
        return {"error": "version not found"}
    changes = diff_key_facts(a["model"], b["model"])
    return {"from": a["version_no"], "to": b["version_no"], "changed_fields": changes,
            "affected_campaigns": len(list_campaigns_for(pid)) if changes else 0}


# ---- Analytics (M7, Spec §31/§37) -----------------------------------------

def save_analytics(campaign_id: int, property_id: str, media_id: str, permalink: str,
                   account_label: str, metrics: Dict[str, Any], score: float) -> int:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO business_analytics
                       (campaign_id, property_id, media_id, permalink, account_label, metrics, score)
                       VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
                    (campaign_id, property_id, media_id, permalink, account_label,
                     Jsonb(metrics), score))
        return int(cur.fetchone()["id"])


def get_analytics_for_property(property_id: str) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_analytics WHERE property_id = ? ORDER BY id DESC", (property_id,))
        return [dict(r) for r in cur.fetchall()]


def get_analytics_for_campaign(campaign_id: int) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_analytics WHERE campaign_id = ? ORDER BY id DESC",
                    (campaign_id,))
        return [dict(r) for r in cur.fetchall()]


def analytics_overview() -> Dict[str, Any]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT a.campaign_id, a.score, a.metrics, c.angle, c.goal
                       FROM business_analytics a LEFT JOIN business_campaigns c ON c.id=a.campaign_id
                       ORDER BY a.id DESC""")
        rows = [dict(r) for r in cur.fetchall()]
    # keep latest per campaign
    latest: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        latest.setdefault(r["campaign_id"], r)
    items = list(latest.values())
    return {"campaigns_tracked": len(items),
            "by_angle": _agg_by(items, "angle"),
            "top": sorted(items, key=lambda x: x.get("score") or 0, reverse=True)[:10]}


def _agg_by(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, float]] = {}
    for it in items:
        k = it.get(key) or "unknown"
        b = buckets.setdefault(k, {"count": 0, "score_sum": 0.0})
        b["count"] += 1
        b["score_sum"] += (it.get("score") or 0)
    return [{key: k, "count": int(v["count"]),
             "avg_score": round(v["score_sum"] / v["count"], 2) if v["count"] else 0}
            for k, v in buckets.items()]


# ---- Audit log (single-admin, Spec §14) -----------------------------------

def audit(action: str, entity: str = "", entity_id: str = "",
          previous_value: Any = None, new_value: Any = None) -> None:
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO admin_audit (action, entity, entity_id, previous_value, new_value) "
                "VALUES (?, ?, ?, ?, ?)",
                (action, entity, str(entity_id),
                 None if previous_value is None else str(previous_value),
                 None if new_value is None else str(new_value)))
    except Exception:  # noqa: BLE001 — audit must never break the main flow
        pass


def list_audit(limit: int = 100) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin_audit ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


def list_all_campaigns(limit: int = 500) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, property_id, goal, angle, status, created_at "
                    "FROM business_campaigns ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


def list_published_posts(limit: int = 200) -> List[Dict[str, Any]]:
    """Published campaigns ('Post #N') with the Instagram media id + permalink they
    published to — the anchor for pulling per-post comments & insights."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT id, property_id, goal, angle, contract, caption, images
                       FROM business_campaigns WHERE status = 'PUBLISHED'
                       ORDER BY id DESC LIMIT ?""", (limit,))
        out: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            d = dict(r)
            pub = (d.get("contract") or {}).get("published") or {}
            imgs = d.get("images") or {}
            cover = None
            if isinstance(imgs, dict):
                cover = (imgs.get("cover") or (imgs.get("slides") or [None])[0])
            elif isinstance(imgs, list) and imgs:
                cover = imgs[0]
            out.append({
                "campaign_id": d["id"], "label": f"Post #{d['id']}",
                "property_id": d.get("property_id"), "goal": d.get("goal"), "angle": d.get("angle"),
                "ig_media_id": pub.get("ig_media_id"), "permalink": pub.get("permalink"),
                "account_id": pub.get("account_id"), "account_label": pub.get("account_label"),
                "posts": pub.get("posts") or [], "cover": cover,
            })
        return out


def duplicate_campaign(campaign_id: int) -> Optional[int]:
    src = get_campaign(campaign_id)
    if not src:
        return None
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO business_campaigns
                       (property_id, goal, angle, status, brief, marketing, carousel, caption, contract, images)
                       VALUES (?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, ?) RETURNING id""",
                    (src["property_id"], src.get("goal"), src.get("angle"),
                     Jsonb(src.get("brief")), Jsonb(src.get("marketing")), Jsonb(src.get("carousel")),
                     Jsonb(src.get("caption")), Jsonb(src.get("contract")), Jsonb(src.get("images"))))
        return int(cur.fetchone()["id"])


def list_campaigns_for(pid: str) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, goal, angle, status FROM business_campaigns WHERE property_id = ?", (pid,))
        return [dict(r) for r in cur.fetchall()]


def save_campaign(pid: str, brief: Dict[str, Any], campaign: Dict[str, Any]) -> Dict[str, Any]:
    """Persist one generated campaign (Stage B) under an existing property."""
    status = "REVIEW_REQUIRED"
    if campaign.get("render", {}).get("rendered") and not campaign.get("claim_violations"):
        status = "AUTO_APPROVED"
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO business_campaigns
                (property_id, goal, angle, status, brief, marketing, carousel, caption, contract, images)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
        """, (pid, (brief or {}).get("goal"), (campaign.get("marketing") or {}).get("angle"),
              status, Jsonb(brief), Jsonb(campaign.get("marketing")), Jsonb(campaign.get("carousel")),
              Jsonb(campaign.get("caption")), Jsonb(campaign.get("contract")),
              Jsonb(campaign.get("render", {}).get("images", []))))
        campaign_id = int(cur.fetchone()["id"])
        cur.execute("""INSERT INTO business_runs (property_id, document, usage, traces, grade, duration_ms)
                       VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
                    (pid, None, Jsonb(campaign.get("usage")), Jsonb(campaign.get("traces")),
                     Jsonb(campaign.get("claim_violations")), campaign.get("duration_ms")))
        run_id = int(cur.fetchone()["id"])
    return {"property_id": pid, "campaign_id": campaign_id, "run_id": run_id, "status": status}


def list_properties(limit: int = 100) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.project_name, p.document, p.verdict, p.updated_at,
                   (SELECT COUNT(*) FROM business_campaigns c WHERE c.property_id=p.id) AS campaigns
            FROM business_properties p ORDER BY p.updated_at DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]


def get_property(pid: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_properties WHERE id = ?", (pid,))
        row = cur.fetchone()
        if not row:
            return None
        out = dict(row)
        cur.execute("""SELECT id, goal, angle, status, marketing, caption, images, created_at
                       FROM business_campaigns WHERE property_id = ? ORDER BY id DESC""", (pid,))
        out["campaigns"] = [dict(r) for r in cur.fetchall()]
        return out


def set_campaign_status(campaign_id: int, status: str) -> bool:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE business_campaigns SET status = ? WHERE id = ?", (status, campaign_id))
        return cur.rowcount > 0


# ===================== BRAND PRESETS (M4, Spec §13) =====================

_BRAND_COLS = ("name", "logo_ref", "logo_cdn", "primary_color", "secondary_color",
               "accent_color", "font", "style", "footer")


def list_brands() -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_brands ORDER BY id")
        return [dict(r) for r in cur.fetchall()]


def get_brand(brand_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_brands WHERE id = ?", (brand_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def create_brand(fields: Dict[str, Any]) -> Dict[str, Any]:
    cols = [c for c in _BRAND_COLS if c in fields]
    if "name" not in cols:
        cols = ["name"] + cols
        fields = {"name": fields.get("name", "Brand"), **fields}
    placeholders = ", ".join("?" for _ in cols)
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(f"INSERT INTO business_brands ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
                    [fields[c] for c in cols])
        bid = int(cur.fetchone()["id"])
    return get_brand(bid)


def update_brand(brand_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sets, params = [], []
    for c in _BRAND_COLS:
        if c in fields and fields[c] is not None:
            sets.append(f"{c} = ?")
            params.append(fields[c])
    if sets:
        params.append(brand_id)
        with connect() as conn:
            conn.execute(f"UPDATE business_brands SET {', '.join(sets)} WHERE id = ?", params)
    return get_brand(brand_id)


def delete_brand(brand_id: int) -> bool:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM business_brands WHERE id = ?", (brand_id,))
        return cur.rowcount > 0


def get_campaign(campaign_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_campaigns WHERE id = ?", (campaign_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_campaign(campaign_id: int, *, carousel: Any = None, caption: Any = None,
                    contract: Any = None, images: Any = None, marketing: Any = None) -> bool:
    """Persist edits to a campaign's slides/caption/contract (M2/M3 slide editing)."""
    sets, params = [], []
    for col, val in (("carousel", carousel), ("caption", caption), ("contract", contract),
                     ("images", images), ("marketing", marketing)):
        if val is not None:
            sets.append(f"{col} = ?")
            params.append(Jsonb(val))
    if not sets:
        return False
    params.append(campaign_id)
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE business_campaigns SET {', '.join(sets)} WHERE id = ?", params)
        return cur.rowcount > 0
