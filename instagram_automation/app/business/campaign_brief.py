"""Campaign Brief — the control contract that drives generation (Spec §10, §29, §41).

The LLM does NOT decide audience / angle / carousel type / CTA / claim policy — the
USER does, via the brief. The LLM then produces strategy, narrative, hooks, copy,
caption and hashtags *within* these constraints. This is what makes output
predictable and repeatable: same Property Knowledge + same Brief -> same campaign
shape, only the copy varies.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ---- allowed control vocabularies (mirrors the UI dropdowns, Spec §5-14) ----
GOALS = ["site_visit", "awareness", "brochure", "price_enquiry", "lead_generation",
         "whatsapp_enquiry", "phone_enquiry", "project_launch", "unit_availability",
         "property_discovery", "custom"]
AUDIENCES = ["first_time_home_buyer", "young_professionals", "families", "parents",
             "investors", "nri", "luxury_buyers", "budget_buyers", "rental_investors",
             "retirement_buyers", "commercial_buyers", "land_plot_buyers", "custom",
             "ai_recommended"]
ANGLES = ["location_first", "price_first", "family_first", "lifestyle_first",
          "amenities_first", "floor_plan_first", "connectivity_first", "space_first",
          "builder_trust", "investment_first", "project_first", "value_first",
          "balanced", "ai_recommended", "custom"]
CAROUSEL_TYPES = ["property_showcase", "property_launch", "location_guide",
                  "family_lifestyle", "amenities_showcase", "floor_plan_breakdown",
                  "price_value", "project_overview", "investment", "site_visit_campaign",
                  "builder_trust", "connectivity", "property_comparison", "educational",
                  "custom", "ai_recommended"]
TEMPLATES = ["premium", "luxury", "modern", "minimal", "corporate", "family", "bold",
             "editorial", "real_estate_classic", "custom", "ai_recommended"]
TONES = ["professional", "premium", "friendly", "family_focused", "conversational",
         "minimal", "trustworthy", "luxury", "local", "bold"]
DENSITIES = ["minimal", "balanced", "informative", "data_heavy"]
LANGUAGES = ["english", "kannada", "hindi", "english_kannada", "english_hindi", "custom"]
IMAGE_POLICIES = ["real_images_only", "real_images_plus_design", "creative_backgrounds",
                  "ai_recommended"]
CLAIM_POLICIES = ["strict", "standard", "custom"]
CTA_OBJECTIVES = ["call", "whatsapp", "dm", "brochure_download", "site_visit",
                  "price_enquiry", "enquiry_form", "website", "contact_agent", "custom"]
CONTACT_METHODS = ["phone", "whatsapp", "instagram_dm", "website", "multiple"]
GENERATION_MODES = ["standard", "controlled", "reproducible"]
ENRICHMENTS = ["source_document", "map_location", "nearby_schools", "nearby_hospitals",
               "nearby_malls", "metro_transport", "locality_info", "market_info"]

# Carousel-type -> ordered slide skeleton (Spec §22). Blueprint is trimmed/padded to
# the requested slide count; the LLM writes copy per slot, grounded in verified facts.
CAROUSEL_SKELETONS: Dict[str, List[str]] = {
    "property_showcase": ["hero", "property_overview", "location", "features", "amenity", "floorplan", "cta"],
    "location_guide": ["location", "connectivity", "schools", "hospitals", "shopping", "map", "property", "cta"],
    "family_lifestyle": ["hero", "bedrooms", "kids_facilities", "security", "parking", "amenity", "floorplan", "cta"],
    "floor_plan_breakdown": ["hero", "layout", "floorplan", "rooms", "dimensions", "amenity", "cta"],
    "site_visit_campaign": ["hero", "project", "why", "location", "features", "floorplan", "cta"],
    "amenities_showcase": ["hero", "amenity", "amenity", "security", "map", "cta"],
    "connectivity": ["location", "map", "metro", "malls", "hospitals", "property", "cta"],
    "price_value": ["hero", "value", "features", "amenity", "location", "cta"],
    "project_overview": ["hero", "project", "features", "amenity", "location", "floorplan", "cta"],
    "builder_trust": ["hero", "builder", "project", "features", "approvals", "cta"],
    "property_launch": ["hero", "project", "features", "amenity", "location", "floorplan", "cta"],
    "investment": ["hero", "value", "location", "connectivity", "builder", "cta"],
    "property_discovery": ["hero", "property_overview", "location", "features", "amenity", "floorplan", "cta"],
    "educational": ["hero", "point", "point", "point", "point", "cta"],
}


class CampaignBrief(BaseModel):
    goal: str = "site_visit"
    target_audience: str = "ai_recommended"
    content_angle: str = "ai_recommended"
    carousel_type: str = "ai_recommended"
    slide_count: int = Field(default=10, ge=4, le=10)
    language: str = "english"
    tone: str = "premium"
    content_density: str = "balanced"
    image_policy: str = "real_images_only"
    claim_policy: str = "strict"
    cta_objective: str = "site_visit"
    contact_method: str = "whatsapp"
    cta_keyword: str = ""
    cta_text: str = ""
    data_enrichment: List[str] = Field(default_factory=lambda: ["source_document", "map_location"])
    brand: str = ""
    template: str = "premium"
    generation_mode: str = "controlled"
    campaign_version: str = "brief-v1"

    def resolve_carousel_skeleton(self, angle: str) -> List[str]:
        ctype = self.carousel_type
        if ctype in ("ai_recommended", "custom", ""):
            # derive from angle when the user let the AI pick the type
            mapping = {
                "location_first": "location_guide", "connectivity_first": "connectivity",
                "family_first": "family_lifestyle", "floor_plan_first": "floor_plan_breakdown",
                "amenities_first": "amenities_showcase", "value_first": "price_value",
                "price_first": "price_value", "builder_trust": "builder_trust",
                "investment_first": "investment", "project_first": "project_overview",
            }
            ctype = mapping.get(angle, "property_showcase")
        return CAROUSEL_SKELETONS.get(ctype, CAROUSEL_SKELETONS["property_showcase"])


def options() -> Dict[str, Any]:
    """Everything the UI needs to render the control dropdowns."""
    return {
        "goal": GOALS, "target_audience": AUDIENCES, "content_angle": ANGLES,
        "carousel_type": CAROUSEL_TYPES, "template": TEMPLATES, "tone": TONES,
        "content_density": DENSITIES, "language": LANGUAGES, "image_policy": IMAGE_POLICIES,
        "claim_policy": CLAIM_POLICIES, "cta_objective": CTA_OBJECTIVES,
        "contact_method": CONTACT_METHODS, "generation_mode": GENERATION_MODES,
        "data_enrichment": ENRICHMENTS, "slide_count": list(range(4, 11)),
    }


_STRICT_BANNED = [
    "best investment", "guaranteed returns", "most affordable", "no. 1", "no.1",
    "number one", "guaranteed appreciation", "perfect location", "best in bangalore",
    "fastest-growing", "fastest growing", "world-class", "unbeatable", "once in a lifetime",
]


def constraints_text(brief: CampaignBrief) -> str:
    """Human-readable constraint block injected into the marketing LLM prompt."""
    lines = [
        f"- Campaign goal: {brief.goal}",
        f"- Target audience: {brief.target_audience} (write specifically for them)",
        f"- Content angle: {brief.content_angle} (prioritise this information)",
        f"- Carousel type: {brief.carousel_type}",
        f"- Tone: {brief.tone}; content density: {brief.content_density}",
        f"- Language: {brief.language}",
        f"- Image policy: {brief.image_policy} (never fabricate property visuals)",
        f"- CTA objective: {brief.cta_objective} via {brief.contact_method}"
        + (f"; keyword '{brief.cta_keyword}'" if brief.cta_keyword else "")
        + (f"; exact CTA text: '{brief.cta_text}'" if brief.cta_text else ""),
    ]
    if brief.claim_policy == "strict":
        lines.append(
            "- CLAIM POLICY = STRICT: every factual claim must be source-supported. "
            "Do NOT use superlative/hype claims such as: "
            + ", ".join(f'"{b}"' for b in _STRICT_BANNED[:8])
            + " unless a verified fact supports them. Persuasive language is fine; "
            "invented facts and unbacked superlatives are not."
        )
    return "\n".join(lines)


def violates_claim_policy(brief: CampaignBrief, text: str) -> List[str]:
    """Deterministic guard: flag banned hype in generated copy under STRICT policy."""
    if brief.claim_policy != "strict" or not text:
        return []
    low = text.lower()
    return [b for b in _STRICT_BANNED if b in low]
