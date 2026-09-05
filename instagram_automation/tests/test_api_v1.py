"""Integration tests for the /api/v1 surface (Spec §70).

Runs against the LIVE backend (default http://localhost:8000). Exercises the
single-admin auth gate, the standard response envelope, and the core end-to-end
campaign flow. Run:  pytest tests/test_api_v1.py -v
Override host with BASE_URL env if needed.
"""
import os
import time

import pytest
import requests

BASE = os.getenv("BASE_URL", "http://localhost:8000")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin")
PROPERTY_ID = os.getenv("TEST_PROPERTY", "landmark-dreamz")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE}/api/v1/admin/login",
                      json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["access_token"]
    return body["access_token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _env(body):
    """Assert the standard envelope and return data."""
    assert set(("success", "data", "error", "meta")).issubset(body.keys())
    assert body["meta"].get("request_id")
    return body


def test_health_gate_requires_auth():
    r = requests.get(f"{BASE}/api/v1/dashboard/summary", timeout=15)
    assert r.status_code == 401


def test_bad_login_rejected():
    r = requests.post(f"{BASE}/api/v1/admin/login", json={"username": "admin", "password": "nope"}, timeout=15)
    assert r.status_code == 401


def test_dashboard_envelope(auth):
    r = requests.get(f"{BASE}/api/v1/dashboard/summary", headers=auth, timeout=30)
    assert r.status_code == 200
    d = _env(r.json())
    assert d["success"] is True
    assert "properties" in d["data"]


def test_error_envelope(auth):
    r = requests.get(f"{BASE}/api/v1/properties/does-not-exist", headers=auth, timeout=15)
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_properties_and_workspace(auth):
    r = requests.get(f"{BASE}/api/v1/properties", headers=auth, timeout=30)
    data = _env(r.json())["data"]
    assert isinstance(data, list)
    r = requests.get(f"{BASE}/api/v1/properties/{PROPERTY_ID}/workspace", headers=auth, timeout=30)
    assert r.status_code == 200
    ws = _env(r.json())["data"]
    assert ws["knowledge"]["property"]["project_name"]


def test_facts_have_evidence(auth):
    r = requests.get(f"{BASE}/api/v1/properties/{PROPERTY_ID}/facts", headers=auth, timeout=30)
    facts = _env(r.json())["data"]
    assert len(facts) >= 1
    assert all("source" in f for f in facts)


def test_price_never_invented(auth):
    r = requests.get(f"{BASE}/api/v1/properties/{PROPERTY_ID}/knowledge", headers=auth, timeout=30)
    m = _env(r.json())["data"]
    # DREAMZ states no price -> must remain NOT_AVAILABLE
    assert m["pricing"]["price"] == "NOT_AVAILABLE"


def test_generate_flow(auth):
    gen = requests.post(f"{BASE}/api/v1/campaigns/generate", headers=auth, timeout=180,
                        json={"property_id": PROPERTY_ID, "render": False,
                              "brief": {"goal": "site_visit", "target_audience": "families",
                                        "content_angle": "location_first", "slide_count": 5,
                                        "claim_policy": "strict"}})
    assert gen.status_code == 200, gen.text
    cid = _env(gen.json())["data"]["campaign_id"]

    ap = requests.post(f"{BASE}/api/v1/campaigns/{cid}/approve", headers=auth, timeout=30)
    assert ap.status_code == 200

    val = requests.post(f"{BASE}/api/v1/campaigns/{cid}/validate", headers=auth, timeout=30)
    assert _env(val.json())["data"]["status"] == "PASS"

    prev = requests.get(f"{BASE}/api/v1/campaigns/{cid}/preview", headers=auth, timeout=30)
    pdata = _env(prev.json())["data"]
    assert len(pdata["slides"]) == 5


def test_async_job(auth):
    r = requests.post(f"{BASE}/api/v1/campaigns/generate-async", headers=auth, timeout=30,
                      json={"property_id": PROPERTY_ID, "render": False,
                            "brief": {"goal": "awareness", "content_angle": "value_first", "slide_count": 5}})
    jid = _env(r.json())["data"]["job_id"]
    assert jid.startswith("JOB-")
    status = None
    for _ in range(40):
        jr = requests.get(f"{BASE}/api/v1/jobs/{jid}", headers=auth, timeout=15)
        status = _env(jr.json())["data"]["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(2)
    assert status == "completed"


def test_templates_and_integrations(auth):
    t = requests.get(f"{BASE}/api/v1/templates", headers=auth, timeout=15)
    assert "vocabulary" in _env(t.json())["data"]
    ig = requests.get(f"{BASE}/api/v1/integrations/instagram/health", headers=auth, timeout=15)
    assert "connected" in _env(ig.json())["data"]


def test_openapi_lists_v1(auth):
    r = requests.get(f"{BASE}/openapi.json", headers=auth, timeout=15)
    paths = r.json()["paths"]
    v1 = [p for p in paths if p.startswith("/api/v1")]
    assert len(v1) >= 50
