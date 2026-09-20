"""Phase 2 API contract tests."""

from app.workers.jobs import RESEARCH_JOB
from tests.factories_phase2 import make_company


async def test_research_endpoint_queues_a_real_run(client, session, job_queue):
    company = await make_company(session)
    response = await client.post(f"/api/companies/{company.id}/research")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["company_id"] == company.id
    assert job_queue.jobs == [(RESEARCH_JOB, {"run_id": body["id"]})]


async def test_research_on_a_missing_company_is_a_clean_404(client):
    response = await client.post("/api/companies/9999/research")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_a_second_request_returns_the_run_already_in_flight(client, session, job_queue):
    """Clicking twice must not start two crawls of the same site."""
    company = await make_company(session)
    first = (await client.post(f"/api/companies/{company.id}/research")).json()
    second = (await client.post(f"/api/companies/{company.id}/research")).json()

    assert first["id"] == second["id"]
    assert len(job_queue.jobs) == 1


async def test_research_state_before_any_run(client, session):
    company = await make_company(session)
    body = (await client.get(f"/api/companies/{company.id}/research")).json()

    assert body["research_status"] == "not_started"
    assert body["latest_run"] is None
    assert body["runs"] == []
    assert body["brief"] is None
    assert body["counts"]["evidence"] == 0


async def test_research_history_is_returned_newest_first(client, session, job_queue):
    from app.models.enums import ResearchStatus
    from app.repositories.research import ResearchRunRepository

    company = await make_company(session)
    repo = ResearchRunRepository(session)
    for _ in range(3):
        run = await repo.create(company_id=company.id)
        run.status = ResearchStatus.COMPLETED
    await session.commit()

    body = (await client.get(f"/api/companies/{company.id}/research")).json()
    ids = [run["id"] for run in body["runs"]]
    assert ids == sorted(ids, reverse=True)
    assert body["counts"]["runs"] == 3


async def test_evidence_signals_and_opportunities_start_empty(client, session):
    company = await make_company(session)
    for path in ("evidence", "signals", "opportunities", "decision-makers", "contradictions"):
        response = await client.get(f"/api/companies/{company.id}/{path}")
        assert response.status_code == 200, path
        assert response.json() == [], path


async def test_brief_is_404_until_research_has_run(client, session):
    company = await make_company(session)
    assert (await client.get(f"/api/companies/{company.id}/brief")).status_code == 404


async def test_capabilities_are_seeded_on_first_read(client):
    response = await client.get("/api/ubm/capabilities")
    assert response.status_code == 200
    capabilities = response.json()
    assert len(capabilities) >= 10
    # Capabilities are keyed to signals, never to industries.
    for capability in capabilities:
        assert capability["signal_types"], capability["slug"]


async def test_signal_type_vocabulary_is_exposed(client):
    response = await client.get("/api/ubm/signal-types")
    assert response.status_code == 200
    values = {item["value"] for item in response.json()}
    assert "geographic_expansion" in values and "event_activity" in values


async def test_a_capability_can_be_created_and_edited(client):
    await client.get("/api/ubm/capabilities")  # seed

    created = await client.post(
        "/api/ubm/capabilities",
        json={
            "name": "Retail Media Networks",
            "description": "Designing in-store retail media placements.",
            "signal_types": ["geographic_expansion", "digital_activity"],
            "category": "Digital",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["slug"] == "retail-media-networks" and body["is_seed"] is False

    updated = await client.patch(
        f"/api/ubm/capabilities/{body['id']}", json={"active": False, "weight": 0.5}
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False and updated.json()["weight"] == 0.5


async def test_a_capability_cannot_reference_an_unknown_signal_type(client):
    response = await client.post(
        "/api/ubm/capabilities",
        json={
            "name": "Nonsense",
            "description": "Keyed to a signal that can never fire.",
            "signal_types": ["not_a_real_signal"],
        },
    )
    assert response.status_code == 422


async def test_duplicate_capability_slug_is_rejected(client):
    await client.get("/api/ubm/capabilities")
    payload = {
        "name": "Events",  # collides with the seeded slug
        "description": "Duplicate of an existing capability.",
        "signal_types": ["event_activity"],
    }
    assert (await client.post("/api/ubm/capabilities", json=payload)).status_code == 409


async def test_bulk_research_queues_each_company(client, session, job_queue):
    companies = [
        await make_company(session, canonical_domain=f"c{index}.test", name=f"Company {index}")
        for index in range(3)
    ]
    response = await client.post(
        "/api/companies/research/bulk",
        json={"company_ids": [company.id for company in companies]},
    )
    assert response.status_code == 202
    body = response.json()
    assert len(body["queued"]) == 3
    assert len(job_queue.jobs) == 3


async def test_bulk_research_reports_unknown_companies_instead_of_failing(client, session, job_queue):
    company = await make_company(session)
    response = await client.post(
        "/api/companies/research/bulk", json={"company_ids": [company.id, 98765]}
    )
    body = response.json()
    assert len(body["queued"]) == 1
    assert body["skipped"][0]["company_id"] == 98765
    assert "not found" in body["skipped"][0]["reason"].lower()


async def test_bulk_research_deduplicates_ids(client, session, job_queue):
    company = await make_company(session)
    response = await client.post(
        "/api/companies/research/bulk",
        json={"company_ids": [company.id, company.id, company.id]},
    )
    assert len(response.json()["queued"]) == 1
    assert len(job_queue.jobs) == 1


async def test_bulk_research_rejects_an_empty_selection(client):
    assert (
        await client.post("/api/companies/research/bulk", json={"company_ids": []})
    ).status_code == 422


async def test_research_runs_are_paginated(client, session):
    from app.repositories.research import ResearchRunRepository

    company = await make_company(session)
    repo = ResearchRunRepository(session)
    for _ in range(3):
        await repo.create(company_id=company.id)
    await session.commit()

    body = (await client.get("/api/research-runs", params={"page": 1, "page_size": 2})).json()
    assert len(body["items"]) == 2 and body["total"] == 3


async def test_missing_research_run_is_a_clean_404(client):
    response = await client.get("/api/research-runs/4242")
    assert response.status_code == 404 and response.json()["code"] == "not_found"


async def test_opportunity_status_can_be_set_by_a_human(client, session):
    from app.models import Opportunity, UbmCapability
    from app.services.fingerprints import opportunity_fingerprint

    company = await make_company(session)
    capability = UbmCapability(
        slug="x", name="X", description="d", signal_types=["event_activity"]
    )
    session.add(capability)
    await session.commit()

    opportunity = Opportunity(
        company_id=company.id,
        capability_id=capability.id,
        title="t",
        description="d",
        why_relevant="w",
        fingerprint=opportunity_fingerprint(company.id, capability.id),
    )
    session.add(opportunity)
    await session.commit()

    response = await client.patch(
        f"/api/opportunities/{opportunity.id}", json={"status": "dismissed"}
    )
    assert response.status_code == 200 and response.json()["status"] == "dismissed"


async def test_invalid_opportunity_status_is_rejected(client, session):
    response = await client.patch("/api/opportunities/1", json={"status": "hot_lead"})
    assert response.status_code == 422


async def test_phase_1_endpoints_still_work(client):
    """Phase 2 must not have broken the discovery API."""
    for path in ("/api/targets", "/api/companies", "/api/dashboard", "/api/status"):
        assert (await client.get(path)).status_code == 200, path
