from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import DatabaseError, connection, connections, transaction

from apps.accounts.models import User
from apps.registrations.models import RegistrationSubmission
from apps.registrations.services import create_registration, submit_registration
from core.exceptions import BusinessError


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_submission_is_serialized(dataset, draft_payload):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row locking test")
    actor = dataset["accounts"]["student"]
    registration = create_registration(actor, dataset["edition"], draft_payload)
    barrier = Barrier(2)

    def run(index):
        try:
            user = User.objects.get(pk=actor.id)
            barrier.wait(timeout=10)
            try:
                return submit_registration(
                    user, registration.id, 1, f"parallel-submit-{index}"
                ).status
            except BusinessError as exc:
                return exc.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, [1, 2]))
    assert sorted(map(str, results)) == ["40906", "pending_review"]
    assert RegistrationSubmission.objects.filter(registration=registration).count() == 1


@pytest.mark.django_db
def test_postgresql_immutable_submission_is_enforced(dataset, draft_payload):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL trigger test")
    actor = dataset["accounts"]["student"]
    registration = create_registration(actor, dataset["edition"], draft_payload)
    submit_registration(actor, registration.id, 1, "immutable-test-key")
    with pytest.raises(DatabaseError), transaction.atomic():
        RegistrationSubmission.objects.filter(registration=registration).update(
            selected_school_level="MS"
        )
