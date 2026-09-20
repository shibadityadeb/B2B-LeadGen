"""Decision-maker validation and the LLM guard rails."""

import pytest

from app.models.enums import VerificationStatus
from app.providers.llm.base import LLMProvider, LLMStatus
from app.providers.llm.null_provider import NullLLMProvider
from app.providers.people.website_people import WebsitePeopleProvider
from app.services import llm_reasoning

TEAM_PAGE = """
Our Leadership
Priya Nair - Head of Marketing
Rahul Sharma, Co-Founder
Amit Verma | Business Development Head | amit@example.com
Chief Executive Officer: Sunita Rao
Read more
Privacy Policy
"""


@pytest.fixture
def provider():
    return WebsitePeopleProvider()


async def test_named_people_are_extracted_with_roles(provider):
    people = await provider.find_people(
        company_name="Acme", documents=[("https://acme.test/team", "Team", TEAM_PAGE)]
    )
    found = {(person.name, person.role_category) for person in people}
    assert ("Priya Nair", "marketing") in found
    assert ("Rahul Sharma", "founder") in found
    assert ("Sunita Rao", "executive") in found


async def test_only_emails_present_in_the_text_are_reported(provider):
    people = await provider.find_people(
        company_name="Acme", documents=[("https://acme.test/team", "Team", TEAM_PAGE)]
    )
    emails = {person.email for person in people if person.email}
    assert emails == {"amit@example.com"}
    # Nobody else gets an address invented from their name.
    priya = next(person for person in people if person.name == "Priya Nair")
    assert priya.email is None


async def test_a_role_without_a_name_is_not_given_one(provider):
    people = await provider.find_people(
        company_name="Acme",
        documents=[("https://acme.test/contact", "Contact", "For press, contact our Head of Marketing.")],
    )
    assert people
    assert people[0].name is None
    assert people[0].verification_status == VerificationStatus.ROLE_ONLY


async def test_page_furniture_is_not_mistaken_for_a_person(provider):
    people = await provider.find_people(
        company_name="Acme",
        documents=[("https://acme.test/x", "X", "Our Team\nRead More\nAbout Us\nPrivacy Policy")],
    )
    assert people == []


async def test_named_people_cite_a_source(provider):
    people = await provider.find_people(
        company_name="Acme", documents=[("https://acme.test/team", "Team", TEAM_PAGE)]
    )
    for person in people:
        if person.name:
            assert person.source_url and person.excerpt


async def test_empty_documents_produce_nobody(provider):
    assert await provider.find_people(company_name="Acme", documents=[]) == []
    assert await provider.find_people(company_name="Acme", documents=[("u", "t", "")]) == []


# --------------------------------------------------------------------------- #
# LLM guard rails
# --------------------------------------------------------------------------- #


class _Stub(LLMProvider):
    name = "stub"

    def __init__(self, payload):
        self.payload = payload

    @property
    def enabled(self) -> bool:
        return True

    async def complete_json(self, *, system, prompt, schema=None):
        return self.payload

    async def status(self):
        return LLMStatus(self.name, True)


SOURCE_TEXT = "Acme Retail opened two new showrooms in Bhopal this month. Footfall has grown."


async def test_the_null_provider_is_disabled_and_never_called():
    provider = NullLLMProvider()
    assert provider.enabled is False
    claims, uncertainties, stats = await llm_reasoning.extract_claims(
        provider, company_name="Acme", documents=[("home", SOURCE_TEXT)]
    )
    assert claims == [] and uncertainties == [] and stats["returned"] == 0


async def test_claims_not_present_in_the_source_are_discarded():
    provider = _Stub(
        {
            "claims": [
                {
                    "claim": "Acme opened showrooms.",
                    "excerpt": "Acme Retail opened two new showrooms in Bhopal this month",
                    "evidence_type": "new_store",
                    "certain": True,
                },
                {
                    "claim": "Acme raised 50 crore.",
                    "excerpt": "Acme raised 50 crore in a Series B round led by investors",
                    "evidence_type": "funding",
                    "certain": True,
                },
            ],
            "uncertainties": [],
        }
    )
    claims, _, stats = await llm_reasoning.extract_claims(
        provider, company_name="Acme", documents=[("home", SOURCE_TEXT)]
    )
    assert len(claims) == 1
    assert "showroom" in claims[0].claim.lower()
    assert stats["rejected_unverified"] == 1


async def test_unknown_evidence_types_are_rejected():
    provider = _Stub(
        {
            "claims": [
                {
                    "claim": "Something happened.",
                    "excerpt": "Acme Retail opened two new showrooms in Bhopal this month",
                    "evidence_type": "totally_made_up",
                    "certain": True,
                }
            ]
        }
    )
    claims, _, stats = await llm_reasoning.extract_claims(
        provider, company_name="Acme", documents=[("home", SOURCE_TEXT)]
    )
    assert claims == [] and stats["rejected_bad_type"] == 1


async def test_malformed_output_yields_nothing_rather_than_partial_trust():
    provider = _Stub({"claims": "not a list"})
    claims, uncertainties, _ = await llm_reasoning.extract_claims(
        provider, company_name="Acme", documents=[("home", SOURCE_TEXT)]
    )
    assert claims == [] and uncertainties == []


async def test_uncertain_claims_are_marked_possible_not_known():
    provider = _Stub(
        {
            "claims": [
                {
                    "claim": "Acme may open more showrooms.",
                    "excerpt": "Acme Retail opened two new showrooms in Bhopal this month",
                    "evidence_type": "new_store",
                    "certain": False,
                }
            ]
        }
    )
    claims, _, _ = await llm_reasoning.extract_claims(
        provider, company_name="Acme", documents=[("home", SOURCE_TEXT)]
    )
    assert claims[0].epistemic_status == "possible"


async def test_uncertainties_are_surfaced_not_dropped():
    provider = _Stub({"claims": [], "uncertainties": ["Headcount is not published."]})
    _, uncertainties, _ = await llm_reasoning.extract_claims(
        provider, company_name="Acme", documents=[("home", SOURCE_TEXT)]
    )
    assert uncertainties == ["Headcount is not published."]


def test_the_prompt_contains_the_retrieved_text():
    """The model must reason over evidence, not from memory."""
    prompt = llm_reasoning.build_prompt("Acme", [("home", SOURCE_TEXT)])
    assert SOURCE_TEXT in prompt
    assert "Acme" in prompt


async def test_people_are_found_in_long_prose_not_only_bullet_lists(provider):
    """Team information often sits inside a paragraph, not a bulleted list."""
    prose = (
        "Our leadership team drives the business. Priya Nair, Head of Marketing, leads "
        "brand strategy across all regions and has been with the company for six years."
    )
    people = await provider.find_people(
        company_name="Acme", documents=[("https://acme.test/about", "About", prose)]
    )
    assert any(person.name == "Priya Nair" for person in people)


async def test_a_title_written_before_the_name_is_recognised(provider):
    """Press writing puts the title first with no separator."""
    people = await provider.find_people(
        company_name="Acme",
        documents=[("https://acme.test/press", "Press", "Acme elevates COO Sudeep Nagar to cofounder.")],
    )
    assert any(person.name == "Sudeep Nagar" for person in people)


async def test_job_listing_fragments_are_not_read_as_names(provider):
    """'Marketing Manager Positions Available' must not become a person."""
    people = await provider.find_people(
        company_name="Acme",
        documents=[("https://acme.test/careers", "Careers", "Marketing Manager Positions Available across our stores.")],
    )
    assert all(person.name is None for person in people)
