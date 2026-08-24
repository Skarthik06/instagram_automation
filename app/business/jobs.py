"""Real async job execution (/api/v1 §13/§38).

A small thread pool runs long tasks (extraction, campaign generation) off the
request thread. The endpoint returns a job_id immediately (status=queued); the
worker moves it queued -> processing -> completed/failed, pollable via
GET /api/v1/jobs/{id}. Sufficient for a single-admin app (no external broker).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

from app.business import pipeline, store

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="biz-job")


def submit_extract(document_path: str) -> str:
    jid = store.create_job("extraction")
    _pool.submit(_run_extract, jid, document_path)
    return jid


def _run_extract(jid: str, document_path: str) -> None:
    try:
        store.set_job_processing(jid)
        result = pipeline.extract_property(document_path)
        pid = store.save_property(result["knowledge_model"], result.get("verdict") or {}, result["document"])
        store.snapshot_version(pid, result["knowledge_model"])
        store.audit("DOCUMENT_EXTRACTED", "property", pid, new_value=Path(document_path).name)
        store.finish_job(jid, status="completed", result={"property_id": pid, "verdict": result.get("verdict")})
    except Exception as exc:  # noqa: BLE001
        store.finish_job(jid, status="failed", error=str(exc))


def submit_generate(property_id: str, brief_dict: Dict[str, Any], render: bool = True) -> str:
    jid = store.create_job("campaign_generate")
    _pool.submit(_run_generate, jid, property_id, brief_dict, render)
    return jid


def _run_generate(jid: str, property_id: str, brief_dict: Dict[str, Any], render: bool) -> None:
    try:
        store.set_job_processing(jid)
        from app.business.api import _resolve_brand
        from app.business.campaign_brief import CampaignBrief
        model = store.get_property_model(property_id)
        if not model:
            store.finish_job(jid, status="failed", error="Property not found")
            return
        brief = CampaignBrief(**{k: v for k, v in brief_dict.items()
                                 if k in getattr(CampaignBrief, "model_fields", {})})
        brand = _resolve_brand(brief_dict)
        result = pipeline.generate_campaign(model, brief, render=render, brand=brand)
        persisted = store.save_campaign(property_id, brief.model_dump(), result)
        store.audit("CAMPAIGN_GENERATED", "campaign", persisted["campaign_id"])
        store.finish_job(jid, status="completed", result=persisted)
    except Exception as exc:  # noqa: BLE001
        store.finish_job(jid, status="failed", error=str(exc))
