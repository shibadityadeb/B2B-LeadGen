"""The rule layer that maps sentences to evidence types.

Every pattern here describes a *business event* — something a company did —
never an industry. "opened a new store" is recognised identically for a
jeweller, a hospital or a logistics firm, and an industry the system has
never seen behaves exactly like one it has.

Patterns are data. Adding a new evidence type means adding a row, not a
branch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import EvidenceType


@dataclass(frozen=True)
class Pattern:
    evidence_type: EvidenceType
    #: Regex over a lowercased sentence.
    regex: re.Pattern[str]
    #: Human-readable claim template; ``{subject}`` is the company name.
    claim: str
    #: Explicit statements are KNOWN; hedged ones are downgraded at extraction.
    direct: bool = True


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Ordered: the first match wins, so more specific patterns come first.
PATTERNS: tuple[Pattern, ...] = (
    # --- physical footprint -------------------------------------------------
    Pattern(
        EvidenceType.NEW_STORE,
        _compile(r"\b(new|newly|latest)\s+(stores?|showrooms?|outlets?|branch(es)?|boutiques?|flagships?)\b"),
        "{subject} refers to a new store, showroom or outlet.",
    ),
    Pattern(
        EvidenceType.NEW_STORE,
        _compile(r"\b(open(ed|ing|s)?|launch(ed|ing|es)?|inaugurat(ed|ing|es)?)\b[^.]{0,60}\b(stores?|showrooms?|outlets?|branch(es)?|boutiques?|flagships?)\b"),
        "{subject} refers to opening a store, showroom or outlet.",
    ),
    Pattern(
        EvidenceType.NEW_LOCATION,
        _compile(r"\b(open(ed|ing|s)?|launch(ed|ing|es)?)\b[^.]{0,60}\b(offices?|facilit(y|ies)|centres?|centers?|warehouses?|plants?|factor(y|ies)|clinics?|studios?)\b"),
        "{subject} refers to opening a new facility or office.",
    ),
    Pattern(
        EvidenceType.GEOGRAPHIC_EXPANSION,
        _compile(r"\b(expand(ed|ing|s)?|expansion)\b[^.]{0,60}\b(to|into|across|in)\b"),
        "{subject} refers to geographic or operational expansion.",
    ),
    Pattern(
        EvidenceType.NEW_MARKET,
        _compile(r"\b(enter(ed|ing|s)?|entry into|foray into|debut(ed|s)? in)\b[^.]{0,50}\b(markets?|cit(y|ies)|regions?|states?|countr(y|ies))\b"),
        "{subject} refers to entering a new market.",
    ),
    # --- offerings ----------------------------------------------------------
    Pattern(
        EvidenceType.PRODUCT_LAUNCH,
        _compile(r"\b(launch(ed|ing|es)?|unveil(ed|ing|s)?|introduc(ed|ing|es)|debut(ed|s)?)\b[^.]{0,60}\b(products?|collections?|ranges?|lines?|models?|editions?)\b"),
        "{subject} refers to launching a product or collection.",
    ),
    Pattern(
        EvidenceType.SERVICE_LAUNCH,
        _compile(r"\b(launch(ed|ing|es)?|introduc(ed|ing|es)|roll(ed|ing)? out)\b[^.]{0,60}\b(services?|offerings?|platforms?|apps?|programmes?|programs?)\b"),
        "{subject} refers to launching a service or platform.",
    ),
    # --- people -------------------------------------------------------------
    Pattern(
        EvidenceType.MARKETING_HIRING,
        _compile(r"\b(hiring|we are hiring|now hiring|join our team|vacanc|recruit\w*|apply now|open position|job opening)\b[^.]{0,80}\b(market\w*|brand|communicat\w*|social media|content|digital|creative)\b"),
        "{subject} refers to hiring for marketing, brand or content roles.",
    ),
    Pattern(
        EvidenceType.MARKETING_HIRING,
        _compile(r"\b(market\w*|brand|communicat\w*|social media|content|digital|creative)\b[^.]{0,60}\b(manager|executive|lead|head|specialist|associate|intern)\b[^.]{0,60}\b(hiring|vacanc|apply|position|opening)\b"),
        "{subject} refers to an open marketing or brand role.",
    ),
    Pattern(
        EvidenceType.HIRING,
        _compile(r"\b(we are hiring|now hiring|join our team|current openings|job opening|vacanc\w+|apply now|careers at)\b"),
        "{subject} refers to active hiring.",
    ),
    Pattern(
        EvidenceType.LEADERSHIP_CHANGE,
        _compile(r"\b(appoint(ed|s|ment)?|join(ed|s) as|nam(ed|es)|promot(ed|es))\b[^.]{0,60}\b(ceo|cmo|chief|director|head of|president|managing director)\b"),
        "{subject} refers to a leadership appointment or change.",
    ),
    # --- relationships ------------------------------------------------------
    Pattern(
        EvidenceType.PARTNERSHIP,
        _compile(r"\b(partner(ed|ship|ing|s)?|collaborat(ed|ion|ing|es)?|tie-?up|joint venture|mou)\b[^.]{0,60}\b(with)\b"),
        "{subject} refers to a partnership or collaboration.",
    ),
    Pattern(
        EvidenceType.SPONSORSHIP,
        _compile(r"\b(sponsor(ed|ing|ship|s)?|title partner|presenting partner|official partner)\b"),
        "{subject} refers to a sponsorship.",
    ),
    Pattern(
        EvidenceType.ACQUISITION,
        _compile(
            r"\b(acquir(ed|es|ing)\s+(?:a\s+|the\s+)?[a-z]*\s*(compan|business|brand|firm|startup|stake|majority)"
            r"|acquisition of\b|acquired by\b|merger with\b|merged with\b|takeover of\b"
            r"|\bmerger and acquisition)\b"
        ),
        "{subject} refers to an acquisition or merger.",
    ),
    # --- money --------------------------------------------------------------
    Pattern(
        EvidenceType.FUNDING,
        _compile(r"\b(rais(ed|es|ing)|secur(ed|es)|clos(ed|es))\b[^.]{0,50}\b(funding|round|series [a-e]\b|investment|capital)\b"),
        "{subject} refers to raising funding or investment.",
    ),
    Pattern(
        EvidenceType.INVESTMENT,
        _compile(r"\b(invest(ed|ing|ment|s)?)\b[^.]{0,50}\b(crore|million|billion|lakh|inr|usd|rs\.?)\b"),
        "{subject} refers to a stated investment amount.",
    ),
    # --- market-facing activity --------------------------------------------
    Pattern(
        EvidenceType.EVENT_ORGANIZATION,
        _compile(r"\b(host(ed|ing|s)?|organis(ed|ing|es)|organiz(ed|ing|es)|present(ed|ing|s)?)\b[^.]{0,60}\b(events?|exhibitions?|expos?|shows?|fairs?|summits?|conferences?|roadshows?|meets?)\b"),
        "{subject} refers to hosting or organising an event.",
    ),
    Pattern(
        EvidenceType.EVENT_PARTICIPATION,
        _compile(r"\b(particip\w+|exhibit(ed|ing|s)?|showcas(ed|ing|es)|attend(ed|ing|s)?|booth|stall)\b[^.]{0,60}\b(events?|exhibitions?|expos?|shows?|fairs?|summits?|conferences?|trade shows?)\b"),
        "{subject} refers to participating in an event or exhibition.",
    ),
    Pattern(
        EvidenceType.CAMPAIGN,
        _compile(
            r"\b(campaign|advertis(e|ed|es|ing|ement)s?|tvc\b|billboards?|"
            r"out.of.home advertising|promotional (campaign|activity|offer)|"
            r"brand film|tv commercial)\b"
        ),
        "{subject} refers to an advertising or promotional campaign.",
    ),
    Pattern(
        EvidenceType.COMMUNITY_ACTIVITY,
        _compile(
            r"\b(community (initiative|programme|program|engagement|outreach|event)"
            r"|csr\b|outreach programme|outreach program|workshops? for|"
            r"donat(ed|ion|ing)\b|social impact|rwa\b)\b"
        ),
        "{subject} refers to community or outreach activity.",
    ),
    Pattern(
        EvidenceType.SEASONAL_ACTIVITY,
        _compile(r"\b(festive|festival|diwali|christmas|new year|ramadan|eid|holiday season|wedding season|seasonal)\b[^.]{0,60}\b(offer|collection|campaign|sale|launch|special)\b"),
        "{subject} refers to seasonal or festive activity.",
    ),
    Pattern(
        EvidenceType.AWARD,
        _compile(r"\b(award(ed|s)?|honou?red|recogni[sz]ed|winner|felicitat\w+|ranked)\b[^.]{0,50}\b(award|prize|recognition|rank|list)\b"),
        "{subject} refers to an award or public recognition.",
    ),
    Pattern(
        EvidenceType.CUSTOMER_GROWTH,
        _compile(r"\b(\d[\d,.]*\s*(k|m|lakh|crore|million|billion)?\+?\s*(customers|clients|users|members|subscribers|footfall))\b"),
        "{subject} states a customer or user figure.",
    ),
    Pattern(
        EvidenceType.DIGITAL_ACTIVITY,
        _compile(r"\b(new website|website relaunch|e-?commerce|online store|mobile app|shop online|d2c)\b"),
        "{subject} refers to digital or e-commerce activity.",
    ),
    Pattern(
        EvidenceType.CONTENT_ACTIVITY,
        _compile(r"\b(blog|video series|podcast|newsletter|case study|webinar|youtube channel)\b"),
        "{subject} refers to content publishing activity.",
    ),
    Pattern(
        EvidenceType.PRESS_ACTIVITY,
        _compile(r"\b(press release|media coverage|featured in|as seen in|in the news|press note)\b"),
        "{subject} refers to press or media activity.",
    ),
)

# Hedging words demote a claim from KNOWN to POSSIBLE: a plan is not an event.
HEDGES = _compile(
    r"\b(may|might|could|plans? to|planning to|expected to|aims? to|intends? to|"
    r"reportedly|rumou?red|likely|plan(s|ned)? for|plan(s|ned)? on|upcoming|soon)\b"
)

# Signal grouping: several evidence types roll up into one business signal.
SIGNAL_GROUPS: dict[str, tuple[str, tuple[EvidenceType, ...]]] = {
    "geographic_expansion": (
        "Geographic expansion",
        (
            EvidenceType.GEOGRAPHIC_EXPANSION,
            EvidenceType.NEW_LOCATION,
            EvidenceType.NEW_STORE,
            EvidenceType.NEW_MARKET,
        ),
    ),
    "product_activity": (
        "Product and service activity",
        (
            EvidenceType.PRODUCT_LAUNCH,
            EvidenceType.SERVICE_LAUNCH,
            EvidenceType.NEW_PRODUCT,
        ),
    ),
    "marketing_activity": (
        "Marketing and campaign activity",
        (
            EvidenceType.CAMPAIGN,
            EvidenceType.BRAND_ACTIVITY,
            EvidenceType.PRESS_ACTIVITY,
            EvidenceType.SEASONAL_ACTIVITY,
        ),
    ),
    "event_activity": (
        "Event activity",
        (EvidenceType.EVENT_ORGANIZATION, EvidenceType.EVENT_PARTICIPATION),
    ),
    "sponsorship_activity": (
        "Sponsorship activity",
        (EvidenceType.SPONSORSHIP,),
    ),
    "hiring_activity": (
        "Hiring activity",
        (EvidenceType.HIRING,),
    ),
    "marketing_hiring": (
        "Marketing team growth",
        (EvidenceType.MARKETING_HIRING,),
    ),
    "partnership_activity": (
        "Partnership activity",
        (EvidenceType.PARTNERSHIP, EvidenceType.ACQUISITION),
    ),
    "community_activity": (
        "Community and outreach activity",
        (EvidenceType.COMMUNITY_ACTIVITY,),
    ),
    "digital_activity": (
        "Digital and content activity",
        (EvidenceType.DIGITAL_ACTIVITY, EvidenceType.CONTENT_ACTIVITY),
    ),
    "growth_investment": (
        "Growth and investment",
        (
            EvidenceType.FUNDING,
            EvidenceType.INVESTMENT,
            EvidenceType.CUSTOMER_GROWTH,
        ),
    ),
    "leadership_change": (
        "Leadership change",
        (EvidenceType.LEADERSHIP_CHANGE,),
    ),
    "recognition": (
        "Awards and recognition",
        (EvidenceType.AWARD,),
    ),
}


def signal_type_for(evidence_type: str) -> str | None:
    for signal_type, (_, members) in SIGNAL_GROUPS.items():
        if evidence_type in {str(member) for member in members}:
            return signal_type
    return None
