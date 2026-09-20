from app.services.query_generation import generate_queries


def _queries(**kwargs) -> list[str]:
    return [item.query for item in generate_queries(**kwargs)]


def test_queries_are_built_from_the_target_values():
    queries = _queries(industry="Jewellery", location="Indore", max_queries=6)
    assert queries
    assert all("Jewellery" in query and "Indore" in query for query in queries)


def test_an_unknown_industry_behaves_like_any_other():
    """No per-industry branching: the shape of the output must not depend on
    which industry was supplied."""
    known = generate_queries(industry="Jewellery", location="Indore", max_queries=6)
    unknown = generate_queries(industry="Hydroponic Equipment", location="Indore", max_queries=6)
    assert [item.template for item in known] == [item.template for item in unknown]


def test_keywords_are_included_and_deduplicated():
    queries = _queries(
        industry="Jewellery",
        location="Indore",
        keywords=["jewellery showroom", "jewellery showroom", "JEWELLERY SHOWROOM"],
        max_queries=12,
    )
    assert sum("jewellery showroom" in query.lower() for query in queries) >= 1
    assert len(queries) == len(set(query.lower() for query in queries))


def test_a_keyword_equal_to_the_industry_is_not_repeated():
    queries = _queries(industry="Jewellery", location="Indore", keywords=["jewellery"], max_queries=12)
    assert len(queries) == len(set(query.lower() for query in queries))


def test_max_queries_is_respected():
    queries = _queries(
        industry="Jewellery", location="Indore", keywords=["a", "b", "c", "d"], max_queries=5
    )
    assert len(queries) == 5


def test_every_keyword_appears_even_under_a_tight_limit():
    """Breadth-first ordering: a small budget must not starve later keywords."""
    queries = _queries(
        industry="Jewellery", location="Indore", keywords=["alpha", "beta"], max_queries=4
    )
    joined = " ".join(queries).lower()
    assert "alpha" in joined and "beta" in joined


def test_location_is_optional():
    queries = _queries(industry="Logistics", max_queries=4)
    assert queries and all("Logistics" in query for query in queries)


def test_search_context_widens_only_the_primary_query():
    queries = _queries(
        industry="Jewellery", location="Indore", search_context="retail chain", max_queries=8
    )
    assert sum("retail chain" in query for query in queries) == 1


def test_empty_target_produces_no_queries():
    assert _queries(industry="", keywords=[]) == []


def test_generation_is_deterministic():
    kwargs = {"industry": "BFSI", "location": "Ahmedabad", "keywords": ["nbfc"], "max_queries": 8}
    assert _queries(**kwargs) == _queries(**kwargs)
