"""Seed definitions for UBM's capabilities.

These are *data*, loaded into ``ubm_capabilities`` on first run and editable
afterwards through the API. Nothing in the matching engine references a
capability by name, so editing a row — or adding a new capability — changes
behaviour with no code change.

Each capability declares which observable business signals make it plausibly
relevant. That is the entire matching rule: there is no industry anywhere in
this file.
"""

from __future__ import annotations

SEED_CAPABILITIES: list[dict] = [
    {
        "slug": "brand-experiences",
        "name": "Brand Experiences",
        "category": "Experiential",
        "description": (
            "Designing and running physical or hybrid brand experiences that let "
            "customers encounter a brand directly."
        ),
        "signal_types": [
            "geographic_expansion",
            "product_activity",
            "marketing_activity",
            "recognition",
        ],
        "keywords": ["experience", "flagship", "showroom", "launch", "customer"],
        "rationale_template": (
            "{company} shows {signal_summary}. Moments like these are when a brand "
            "is most visible to customers, so a designed brand experience could be "
            "relevant."
        ),
    },
    {
        "slug": "on-ground-activations",
        "name": "On-Ground Activations",
        "category": "Experiential",
        "description": (
            "Localised, customer-facing activations that build awareness and footfall "
            "in a specific place."
        ),
        "signal_types": ["geographic_expansion", "event_activity", "community_activity"],
        "keywords": ["store", "outlet", "city", "local", "footfall", "opening"],
        "rationale_template": (
            "{company} shows {signal_summary}. Entering or deepening a local market "
            "is typically when on-ground activation is considered."
        ),
    },
    {
        "slug": "events",
        "name": "Events",
        "category": "Events",
        "description": (
            "End-to-end planning and production of corporate, consumer and trade events."
        ),
        "signal_types": ["event_activity", "sponsorship_activity", "partnership_activity"],
        "keywords": ["event", "summit", "conference", "launch", "roadshow"],
        "rationale_template": (
            "{company} shows {signal_summary}. Companies already active around events "
            "often need production or management support."
        ),
    },
    {
        "slug": "expos-exhibitions",
        "name": "Expos & Exhibitions",
        "category": "Events",
        "description": (
            "Exhibition stall design, fabrication and on-site management for trade shows."
        ),
        "signal_types": ["event_activity", "product_activity"],
        "keywords": ["expo", "exhibition", "trade show", "booth", "stall", "pavilion"],
        "rationale_template": (
            "{company} shows {signal_summary}. Exhibiting companies need stall design "
            "and on-site execution."
        ),
    },
    {
        "slug": "digital-campaigns",
        "name": "Digital Campaigns",
        "category": "Digital",
        "description": (
            "Planning and running performance and brand campaigns across digital channels."
        ),
        "signal_types": [
            "marketing_activity",
            "digital_activity",
            "product_activity",
            "growth_investment",
        ],
        "keywords": ["campaign", "digital", "online", "social", "ecommerce", "d2c"],
        "rationale_template": (
            "{company} shows {signal_summary}. Visible market-facing activity usually "
            "runs alongside digital campaign work."
        ),
    },
    {
        "slug": "video-content",
        "name": "Video & Content",
        "category": "Content",
        "description": (
            "Video production and content programmes — brand films, product films and "
            "social-first content."
        ),
        "signal_types": [
            "product_activity",
            "marketing_activity",
            "digital_activity",
            "leadership_change",
        ],
        "keywords": ["video", "film", "content", "story", "campaign", "launch"],
        "rationale_template": (
            "{company} shows {signal_summary}. New offerings and campaigns generally "
            "require supporting video and content."
        ),
    },
    {
        "slug": "graphic-creative-production",
        "name": "Graphic & Creative Production",
        "category": "Content",
        "description": (
            "Design and production of creative assets across print, digital and "
            "environmental formats."
        ),
        "signal_types": ["marketing_activity", "product_activity", "event_activity"],
        "keywords": ["design", "creative", "collateral", "branding", "print"],
        "rationale_template": (
            "{company} shows {signal_summary}. Activity of this kind is normally "
            "supported by a volume of creative production."
        ),
    },
    {
        "slug": "community-rwa-activations",
        "name": "Community & RWA Activations",
        "category": "Experiential",
        "description": (
            "Neighbourhood, residential-community and RWA-level engagement programmes."
        ),
        "signal_types": ["community_activity", "geographic_expansion", "event_activity"],
        "keywords": ["community", "residential", "society", "rwa", "neighbourhood", "local"],
        "rationale_template": (
            "{company} shows {signal_summary}. Community-level engagement is a common "
            "way to build presence in a specific catchment."
        ),
    },
    {
        "slug": "growth-partnerships",
        "name": "Growth Partnerships",
        "category": "Growth",
        "description": (
            "Structuring co-marketing and growth partnerships between complementary brands."
        ),
        "signal_types": [
            "partnership_activity",
            "sponsorship_activity",
            "growth_investment",
            "recognition",
        ],
        "keywords": ["partnership", "collaboration", "alliance", "co-brand", "sponsor"],
        "rationale_template": (
            "{company} shows {signal_summary}. A company already forming partnerships "
            "may be open to structured growth partnerships."
        ),
    },
    {
        "slug": "customized-campaigns",
        "name": "Customized Brand Campaigns",
        "category": "Growth",
        "description": (
            "Bespoke campaigns built around a specific business moment rather than a "
            "standard format."
        ),
        "signal_types": [
            "marketing_hiring",
            "marketing_activity",
            "growth_investment",
            "leadership_change",
            "product_activity",
        ],
        "keywords": ["campaign", "brand", "marketing", "launch", "reposition"],
        "rationale_template": (
            "{company} shows {signal_summary}. Investment in marketing capacity often "
            "precedes larger campaign work."
        ),
    },
]
