"""Phase 3 API contract, including the Gmail and campaign endpoints."""

import pytest

from app.models.enums import OutreachStatus
from tests.factories_phase3 import seeded_opportunity


async def _outreach(client, session, **kwargs):
    company, opportunity, evidence, person = await seeded_opportunity(session, **kwargs)
    response = await client.post(
        f"/api/opportunities/{opportunity.id}/outreach", json={"tone": "professional"}
    )
    assert response.status_code == 201, response.text
    return response.json(), opportunity, person


async def test_create_outreach_from_an_opportunity(client, session):
    body, opportunity, person = await _outreach(client, session)
    assert body["status"] == OutreachStatus.REVIEW
    assert body["opportunity_id"] == opportunity.id
    assert body["subject"] and body["body"]
    assert body["gmail_draft_id"] is None and body["sent_at"] is None


async def test_create_outreach_for_a_missing_opportunity_is_404(client):
    response = await client.post("/api/opportunities/9999/outreach", json={})
    assert response.status_code == 404


async def test_invalid_tone_is_rejected(client, session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    response = await client.post(
        f"/api/opportunities/{opportunity.id}/outreach", json={"tone": "shouty"}
    )
    assert response.status_code == 422


async def test_outreach_detail_exposes_claims_with_their_evidence(client, session):
    body, *_ = await _outreach(client, session)
    detail = (await client.get(f"/api/outreach/{body['id']}")).json()

    active = [version for version in detail["versions"] if version["is_active"]][0]
    bound = [claim for claim in active["claims"] if claim["requires_evidence"]]
    assert bound
    for claim in bound:
        assert claim["evidence"], claim["text"]
        for reference in claim["evidence"]:
            # The reviewer must be able to check the source.
            assert reference["excerpt"] and reference["evidence_id"]


async def test_outreach_list_is_paginated_and_searchable(client, session):
    await _outreach(client, session)
    page = (await client.get("/api/outreach", params={"page_size": 10})).json()
    assert page["total"] >= 1

    hit = (await client.get("/api/outreach", params={"search": "acme"})).json()
    assert hit["total"] >= 1
    miss = (await client.get("/api/outreach", params={"search": "nothingmatches"})).json()
    assert miss["total"] == 0


async def test_editing_marks_the_outreach_as_user_edited(client, session):
    body, *_ = await _outreach(client, session)
    response = await client.patch(
        f"/api/outreach/{body['id']}", json={"body": "My own wording for this message."}
    )
    assert response.status_code == 200
    assert response.json()["user_edited"] is True


async def test_an_invalid_recipient_address_is_rejected_on_edit(client, session):
    body, *_ = await _outreach(client, session)
    response = await client.patch(
        f"/api/outreach/{body['id']}", json={"to_email": "not-an-email"}
    )
    assert response.status_code == 422


async def test_regeneration_creates_a_comparable_version(client, session):
    body, *_ = await _outreach(client, session)
    await client.post(f"/api/outreach/{body['id']}/regenerate", json={"tone": "direct"})

    detail = (await client.get(f"/api/outreach/{body['id']}")).json()
    assert len(detail["versions"]) == 2
    assert sum(1 for version in detail["versions"] if version["is_active"]) == 1


async def test_a_version_can_be_reactivated(client, session):
    body, *_ = await _outreach(client, session)
    original_body = body["body"]
    await client.post(f"/api/outreach/{body['id']}/regenerate", json={"tone": "direct"})

    detail = (await client.get(f"/api/outreach/{body['id']}")).json()
    first = next(v for v in detail["versions"] if v["version_number"] == 1)
    response = await client.post(
        f"/api/outreach/{body['id']}/versions/activate", json={"version_id": first["id"]}
    )
    assert response.status_code == 200
    assert response.json()["body"] == original_body


async def test_approve_then_reject_flow(client, session):
    body, *_ = await _outreach(client, session, email="priya@example.com")
    approved = await client.post(f"/api/outreach/{body['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == OutreachStatus.APPROVED

    rejected = await client.post(
        f"/api/outreach/{body['id']}/reject", json={"reason": "Wrong angle"}
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == OutreachStatus.REJECTED


async def test_gmail_draft_without_a_connected_mailbox_reports_clearly(client, session):
    body, *_ = await _outreach(client, session, email="priya@example.com")
    await client.post(f"/api/outreach/{body['id']}/approve")

    response = await client.post(
        f"/api/outreach/{body['id']}/gmail-draft", json={"force_new": False}
    )
    # No mailbox is connected in tests: the message must say so, not 500.
    assert response.status_code == 502
    assert "connect" in response.json()["message"].lower()


async def test_gmail_draft_before_approval_is_a_conflict(client, session):
    body, *_ = await _outreach(client, session, email="priya@example.com")
    response = await client.post(
        f"/api/outreach/{body['id']}/gmail-draft", json={"force_new": False}
    )
    assert response.status_code == 409
    assert "approved" in response.json()["message"].lower()


async def test_mark_sent_requires_approval(client, session):
    body, *_ = await _outreach(client, session)
    response = await client.post(f"/api/outreach/{body['id']}/mark-sent", json={})
    assert response.status_code == 409


async def test_outcome_recording_and_invalid_status(client, session):
    body, *_ = await _outreach(client, session, email="priya@example.com")
    await client.post(f"/api/outreach/{body['id']}/approve")
    await client.post(f"/api/outreach/{body['id']}/mark-sent", json={})

    ok = await client.patch(
        f"/api/outreach/{body['id']}/outcome",
        json={"status": "replied", "notes": "Asked for a call"},
    )
    assert ok.status_code == 200 and ok.json()["outcome_status"] == "replied"

    bad = await client.patch(
        f"/api/outreach/{body['id']}/outcome", json={"status": "very_interested"}
    )
    assert bad.status_code == 422


async def test_follow_up_draft_endpoint(client, session):
    body, *_ = await _outreach(client, session, email="priya@example.com")
    await client.post(f"/api/outreach/{body['id']}/approve")
    await client.post(f"/api/outreach/{body['id']}/mark-sent", json={})

    response = await client.post(f"/api/outreach/{body['id']}/follow-up-draft")
    assert response.status_code == 201
    follow_up = response.json()
    assert follow_up["parent_outreach_id"] == body["id"]
    assert follow_up["status"] == OutreachStatus.REVIEW


async def test_sender_profile_is_created_and_editable(client):
    profile = (await client.get("/api/sender-profile")).json()
    assert profile["company"] == "Upshot Brand Media"
    # No real person's details are shipped.
    assert profile["email"] is None

    updated = await client.patch(
        "/api/sender-profile",
        json={"name": "A Reviewer", "email": "reviewer@example.com", "role": "Director"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "A Reviewer"


async def test_sender_profile_rejects_a_bad_email(client):
    await client.get("/api/sender-profile")
    response = await client.patch("/api/sender-profile", json={"email": "nope"})
    assert response.status_code == 422


async def test_gmail_status_reports_when_oauth_is_not_configured(client):
    response = await client.get("/api/gmail/status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["configured"] is False
    assert "GOOGLE_CLIENT_ID" in (body["detail"] or "")
    # Credentials must never appear in an API response.
    assert "access_token" not in response.text
    assert "refresh_token" not in response.text


async def test_gmail_authorize_fails_cleanly_without_credentials(client):
    response = await client.get("/api/gmail/authorize")
    assert response.status_code == 500
    assert "GOOGLE_CLIENT_ID" in response.json()["message"]


async def test_campaign_creation_and_listing(client, session):
    created = await client.post(
        "/api/campaigns",
        json={
            "name": "Indore Growth Outreach",
            "description": "Jewellery and retail in Indore",
            "follow_up_intervals": [3, 7, 14],
        },
    )
    assert created.status_code == 201
    campaign = created.json()
    assert campaign["status"] == "active"

    listing = (await client.get("/api/campaigns")).json()
    assert any(item["id"] == campaign["id"] for item in listing)


async def test_campaign_rejects_unordered_follow_up_intervals(client):
    response = await client.post(
        "/api/campaigns", json={"name": "Bad Campaign", "follow_up_intervals": [7, 3]}
    )
    assert response.status_code == 422


async def test_preparing_a_campaign_creates_review_drafts_only(client, session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    campaign = (
        await client.post("/api/campaigns", json={"name": "Prepare Test"})
    ).json()

    response = await client.post(
        f"/api/campaigns/{campaign['id']}/prepare",
        json={"opportunity_ids": [opportunity.id]},
    )
    assert response.status_code == 201
    created = response.json()["created"]
    assert len(created) == 1
    # Nothing is approved, nothing is drafted in Gmail, nothing is sent.
    assert created[0]["status"] == OutreachStatus.REVIEW
    assert created[0]["gmail_draft_id"] is None
    assert created[0]["sent_at"] is None


async def test_preparing_reports_unknown_opportunities(client, session):
    campaign = (await client.post("/api/campaigns", json={"name": "Skip Test"})).json()
    response = await client.post(
        f"/api/campaigns/{campaign['id']}/prepare", json={"opportunity_ids": [4242]}
    )
    body = response.json()
    assert body["created"] == []
    assert body["skipped"][0]["opportunity_id"] == 4242


async def test_analytics_returns_real_counts_and_hides_small_sample_rates(client, session):
    await _outreach(client, session)
    body = (await client.get("/api/outreach-analytics")).json()

    assert body["outreach_total"] >= 1
    assert body["awaiting_review"] >= 1
    # With one message a percentage would be meaningless.
    assert body["approval_rate"] is None
    assert body["reply_rate"] is None


async def test_phase_1_and_2_endpoints_still_work(client):
    for path in (
        "/api/targets",
        "/api/companies",
        "/api/dashboard",
        "/api/status",
        "/api/ubm/capabilities",
        "/api/research-runs",
    ):
        assert (await client.get(path)).status_code == 200, path
