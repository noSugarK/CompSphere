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
