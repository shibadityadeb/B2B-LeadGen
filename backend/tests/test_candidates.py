from app.services.candidates import (
    REJECT_DOCUMENT,
    REJECT_EXCLUDED_DOMAIN,
    REJECT_INVALID_URL,
    extract_candidates,
)
from tests.factories import result


def test_urls_from_one_site_produce_a_single_company():
    extraction = extract_candidates([
        result("https://www.example.com/about", "Example Jewellers | About"),
        result("https://example.com/products", "Example Jewellers - Products"),
        result("https://example.com/", "Example Jewellers"),
    ])
    assert len(extraction.candidates) == 1
    candidate = extraction.candidates[0]
    assert candidate.domain == "example.com"
    # All three URLs are kept as evidence, not discarded.
    assert len(candidate.evidence) == 3


def test_distinct_domains_stay_distinct():
    extraction = extract_candidates([
        result("https://alpha.com", "Alpha Jewellers"),
        result("https://beta.com", "Beta Jewellers"),
    ])
    assert {candidate.domain for candidate in extraction.candidates} == {"alpha.com", "beta.com"}


def test_similar_names_on_different_domains_are_never_merged():
    extraction = extract_candidates([
        result("https://acmejewellers.com", "Acme Jewellers"),
        result("https://acme-jewellers.in", "Acme Jewellers"),
    ])
    assert len(extraction.candidates) == 2


def test_directories_and_social_results_are_rejected():
    extraction = extract_candidates([
        result("https://www.justdial.com/Indore/Jewellery", "Jewellery in Indore"),
        result("https://www.linkedin.com/company/acme", "Acme"),
        result("https://example.com", "Acme"),
    ])
    assert [candidate.domain for candidate in extraction.candidates] == ["example.com"]
    reasons = [d.rejection_reason for d in extraction.decisions if not d.accepted]
    assert reasons == [REJECT_EXCLUDED_DOMAIN, REJECT_EXCLUDED_DOMAIN]


def test_documents_and_broken_urls_are_rejected():
    extraction = extract_candidates([
        result("https://example.com/catalogue.pdf", "Catalogue"),
        result("not-a-url", "Broken"),
    ])
    assert extraction.candidates == []
    reasons = {d.rejection_reason for d in extraction.decisions}
    assert reasons == {REJECT_DOCUMENT, REJECT_INVALID_URL}


def test_every_result_gets_exactly_one_decision():
    items = [
        result("https://example.com", "Example"),
        result("https://justdial.com/x", "Directory"),
        result("bad url", None),
    ]
    extraction = extract_candidates(items)
    assert len(extraction.decisions) == len(items)
    assert [d.result_index for d in extraction.decisions] == [0, 1, 2]
    assert extraction.rejected_count == 2


def test_website_url_is_the_site_root_not_the_deep_link():
    extraction = extract_candidates([result("https://www.example.com/about/team", "Example")])
    assert extraction.candidates[0].website_url == "https://www.example.com"


def test_name_comes_from_the_first_result_for_that_domain():
    extraction = extract_candidates([
        result("https://example.com/about", "Example Jewellers | About Us"),
        result("https://example.com/contact", "Contact"),
    ])
    assert extraction.candidates[0].name == "Example Jewellers"


def test_empty_input_is_handled():
    extraction = extract_candidates([])
    assert extraction.candidates == [] and extraction.decisions == []
