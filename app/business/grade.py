"""Benchmark grader (Spec §29/§30) — score a pipeline run vs the DREAMZ oracle.

Deterministic. The headline correctness check is the NOT_AVAILABLE price gate: the
run FAILS if it invents a price the brochure never stated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from app import settings

_ORACLE = settings.BASE_DIR / "business" / "benchmarks" / "dreamz_expected.json"


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def grade(result: Dict[str, Any], oracle_path: Path = _ORACLE) -> Dict[str, Any]:
    oracle = json.loads(Path(oracle_path).read_text(encoding="utf-8"))
    m = result["knowledge_model"]
    checks: List[Dict[str, Any]] = []

    def check(name: str, got: Any, want: Any, ok: bool) -> None:
        checks.append({"field": name, "got": got, "expected": want, "pass": bool(ok)})

    check("project_name", m["property"]["project_name"], oracle["property"]["project_name"],
          _norm(m["property"]["project_name"]) == _norm(oracle["property"]["project_name"]))
    check("builder", m["property"]["builder"], oracle["property"]["builder"],
          _norm(oracle["property"]["builder"]) in _norm(m["property"]["builder"]))
    check("total_units", m["project"]["total_units"], oracle["project"]["total_units"],
          str(m["project"]["total_units"]) == str(oracle["project"]["total_units"]))
    check("land_area", m["project"]["land_area"], oracle["project"]["land_area"],
          _norm("125") in _norm(m["project"]["land_area"]))
    got_area = (m["configuration"][0].get("area_sqft") if m.get("configuration") else None)
    check("area_sqft", got_area, 940, str(got_area) == "940")
    check("city", m["location"].get("city"), "Bengaluru",
          _norm("bengaluru") in _norm(m["location"].get("city")) or _norm("bangalore") in _norm(m["location"].get("city")))

    # CRITICAL: price must remain NOT_AVAILABLE (no hallucinated price).
    price_ok = m["pricing"]["price"] == "NOT_AVAILABLE"
    check("pricing.price==NOT_AVAILABLE (critical)", m["pricing"]["price"], "NOT_AVAILABLE", price_ok)

    check("connectivity>=5", len(m.get("connectivity", [])), ">=5", len(m.get("connectivity", [])) >= 5)
    check("amenities>=8", len(m.get("amenities", [])), ">=8", len(m.get("amenities", [])) >= 8)
    check("contacts==3", len(m.get("contacts", [])), 3, len(m.get("contacts", [])) == 3)
    got_types = {a["asset_type"] for a in m.get("media", [])}
    check("floor_plan_detected", sorted(got_types), "floor_plan", "floor_plan" in got_types)
    check("location_map_detected", sorted(got_types), "location_map", "location_map" in got_types)

    passed = sum(1 for c in checks if c["pass"])
    return {
        "score": f"{passed}/{len(checks)}",
        "accuracy": round(passed / len(checks), 3),
        "critical_price_ok": price_ok,
        "checks": checks,
    }
