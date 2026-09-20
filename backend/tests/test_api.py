"""API contract tests."""

from app.workers.jobs import CRAWL_JOB, DISCOVERY_JOB

TARGET = {
    "name": "Jewellery — Indore",
    "industry": "Jewellery",
    "location": "Indore",
    "country": "India",
    "company_size": "51-200",
    "keywords": ["jewellery showroom", "jewellery brands"],
}


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200


async def test_create_and_read_a_target(client):
    created = await client.post("/api/targets", json=TARGET)
    assert created.status_code == 201
    body = created.json()
    assert body["industry"] == "Jewellery"
    assert body["keywords"] == ["jewellery showroom", "jewellery brands"]

    fetched = await client.get(f"/api/targets/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == TARGET["name"]


async def test_target_validation_rejects_bad_input(client):
    response = await client.post("/api/targets", json={"name": "x", "industry": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_invalid_company_size_is_rejected(client):
    response = await client.post("/api/targets", json={**TARGET, "company_size": "huge"})
    assert response.status_code == 422


async def test_any_company_size_is_stored_as_unset(client):
    response = await client.post("/api/targets", json={**TARGET, "company_size": "any"})
    assert response.status_code == 201
    assert response.json()["company_size"] is None


async def test_keywords_are_deduplicated_and_trimmed(client):
    response = await client.post(
        "/api/targets", json={**TARGET, "keywords": ["  gold  ", "gold", "GOLD", ""]}
    )
    assert response.json()["keywords"] == ["gold"]


async def test_target_list_reports_counts(client):
    await client.post("/api/targets", json=TARGET)
    response = await client.get("/api/targets")
    assert response.status_code == 200
    item = response.json()[0]
    assert item["companies_count"] == 0
    assert item["last_run_status"] is None


async def test_query_preview_saves_nothing(client):
    response = await client.post("/api/targets/preview", json=TARGET)
    assert response.status_code == 200
    queries = response.json()["queries"]
    assert queries and all("Jewellery" in query or "jewellery" in query for query in queries)
    assert (await client.get("/api/targets")).json() == []


async def test_missing_target_returns_a_clean_404(client):
    response = await client.get("/api/targets/999")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "not_found" and body["message"]


async def test_delete_target(client):
    target_id = (await client.post("/api/targets", json=TARGET)).json()["id"]
    assert (await client.delete(f"/api/targets/{target_id}")).status_code == 204
    assert (await client.get(f"/api/targets/{target_id}")).status_code == 404


async def test_discovery_enqueues_a_real_queued_run(client, job_queue):
    target_id = (await client.post("/api/targets", json=TARGET)).json()["id"]

    response = await client.post(f"/api/targets/{target_id}/discover")
    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "queued"
    assert run["target_id"] == target_id
    assert job_queue.jobs == [(DISCOVERY_JOB, {"run_id": run["id"]})]


async def test_run_detail_exposes_queries_and_results(client):
    target_id = (await client.post("/api/targets", json=TARGET)).json()["id"]
    run_id = (await client.post(f"/api/targets/{target_id}/discover")).json()["id"]

    response = await client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["target_name"] == TARGET["name"]
    assert body["queries"] == [] and body["results"] == []


async def test_runs_are_paginated(client):
    target_id = (await client.post("/api/targets", json=TARGET)).json()["id"]
    for _ in range(3):
        await client.post(f"/api/targets/{target_id}/discover")

    response = await client.get("/api/runs", params={"page": 1, "page_size": 2})
    body = response.json()
    assert len(body["items"]) == 2 and body["total"] == 3 and body["page_size"] == 2


async def test_companies_list_is_paginated_and_empty_by_default(client):
    response = await client.get("/api/companies")
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_company_page_size_is_capped(client):
    assert (await client.get("/api/companies", params={"page_size": 5000})).status_code == 422


async def test_missing_company_returns_404(client):
    assert (await client.get("/api/companies/12345")).status_code == 404
    assert (await client.post("/api/companies/12345/crawl")).status_code == 404


async def test_crawl_enqueues_a_job_for_an_existing_company(client, session, job_queue):
    from app.models import Company

    company = Company(name="Example", canonical_domain="example.com", website_url="https://example.com")
    session.add(company)
    await session.commit()
    await session.refresh(company)

    response = await client.post(f"/api/companies/{company.id}/crawl")
    assert response.status_code == 202
    assert response.json()["status"] == "researching"
    assert job_queue.jobs == [(CRAWL_JOB, {"company_id": company.id})]


async def test_dashboard_reports_zeroes_on_an_empty_database(client):
    response = await client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["targets_count"] == 0
    assert body["companies_count"] == 0
    assert body["recent_runs"] == [] and body["recent_companies"] == []


async def test_dashboard_counts_are_real(client):
    await client.post("/api/targets", json=TARGET)
    body = (await client.get("/api/dashboard")).json()
    assert body["targets_count"] == 1


async def test_company_filters_endpoint(client):
    response = await client.get("/api/companies/filters")
    assert response.status_code == 200
    assert response.json() == {"industries": [], "locations": [], "statuses": []}


async def test_status_endpoint_exposes_no_secrets(client):
    response = await client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert {component["name"] for component in body["components"]} >= {
        "Database", "Search Provider", "Crawler", "Local LLM"
    }
    serialized = response.text.lower()
    for secret in ("password", "secret", "postgresql+asyncpg"):
        assert secret not in serialized
