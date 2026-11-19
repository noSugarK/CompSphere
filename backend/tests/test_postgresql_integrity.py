from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.db import DatabaseError, connection, connections, transaction

from apps.accounts.models import User
from apps.competitions.models import Season
from apps.competitions.services import set_current_season
from apps.registrations.models import RegistrationSubmission
from apps.registrations.services import (
    bulk_review_registrations,
    create_registration,
    review_registration,
    submit_registration,
)
from core.exceptions import BusinessError


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_season_switches_keep_one_current(dataset):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row locking test")
    actor_id = dataset["accounts"]["platform"].id
    targets = [
        Season.objects.create(
            code=code,
            name=code,
            starts_on=date(2028, 1, 1),
            ends_on=date(2028, 12, 31),
            status="active",
        ).id
        for code in ("QA-ALPHA", "QA-BETA")
    ]
    barrier = Barrier(2)

    def run(season_id):
        try:
            actor = User.objects.get(pk=actor_id)
            barrier.wait(timeout=10)
            return set_current_season(actor, season_id).id
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(run, targets)) == targets
    assert Season.objects.get(is_default=True).id in targets
    assert Season.objects.filter(status="active").count() == 3


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


@pytest.mark.django_db(transaction=True)
def test_postgresql_bulk_and_single_review_serialize_same_round(dataset, draft_payload):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row locking test")
    author = dataset["accounts"]["student"]
    reviewer_id = dataset["accounts"]["reviewer"].id
    registration = create_registration(author, dataset["edition"], draft_payload)
    submit_registration(
        author, registration.id, registration.version, "concurrent-review-key"
    )
    barrier = Barrier(2)

    def run(bulk):
        try:
            reviewer = User.objects.get(pk=reviewer_id)
            action = {"action": "return", "comment": "Synthetic correction"}
            barrier.wait(timeout=10)
            if bulk:
                return bulk_review_registrations(
                    reviewer,
                    {
                        **action,
                        "items": [
                            {"registration_id": registration.id, "submission_no": 1}
                        ],
                    },
                )[0]["code"]
            review_registration(
                reviewer, registration.id, {**action, "submission_no": 1}
            )
            return 0
        except BusinessError as error:
            return error.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(run, [True, False])) == [0, 40902]
    assert registration.approval_records.count() == 1


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
