import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.development import create_development_data
from apps.accounts.services import issue_tokens


@pytest.fixture(autouse=True)
def clear_rate_limits():
    cache.clear()


@pytest.fixture
def dataset(db):
    return create_development_data("Synthetic-flow-test-2026!")


@pytest.fixture
def actor_client():
    def make(user):
        client = APIClient()
        tokens, _ = issue_tokens(user)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
        return client

    return make


@pytest.fixture
def draft_payload(dataset):
    return {
        "offering_id": dataset["offering"].id,
        "enrollment_kind": "team",
        "team_id": dataset["team"].id,
        "coach_user_id": dataset["accounts"]["coach"].id,
        "selected_school_level": "HS",
        "contact": {"name": "Synthetic contact", "phone": "00000000000", "email": None},
        "form_data": {"project_title": "Synthetic project"},
        "consents": {"document_usage": True},
        "submit": False,
    }


@pytest.fixture
def approved_registration(actor_client, dataset, draft_payload):
    """One team registration pushed through submit -> approve by the normal flow."""
    student = actor_client(dataset["accounts"]["student"])
    created = student.post(
        f"/api/v1/editions/{dataset['edition'].id}/registrations",
        {**draft_payload, "submit": False},
        format="json",
    ).data["data"]
    student.post(
        f"/api/v1/registrations/{created['id']}/submit",
        {"version": created["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="seed-submit",
    )
    organizer = actor_client(dataset["accounts"]["organizer"])
    approved = organizer.post(
        f"/api/v1/registrations/{created['id']}/approval",
        {"action": "approve", "comment": "", "submission_no": 1},
        format="json",
    )
    assert approved.status_code == 200, approved.data
    return created["id"]
