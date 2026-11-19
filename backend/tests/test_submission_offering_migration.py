import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.events.models import Offering
from apps.groups.models import Group
from apps.registrations.models import RegistrationSubmission
from apps.registrations.services import create_registration, submit_registration


@pytest.mark.django_db(transaction=True)
def test_backfill_uses_frozen_offering_instead_of_changed_working_copy(
    dataset, draft_payload
):
    edition = dataset["edition"]
    actor = dataset["accounts"]["student"]
    registration = create_registration(actor, edition, draft_payload)
    submit_registration(
        actor, registration.id, registration.version, "backfill-offering-test"
    )
    original = registration.submissions.get()
    group = Group.objects.create(edition=edition, code="QA", name="Working copy group")
    alternate = Offering.objects.create(
        edition=edition, event=dataset["offering"].event, group=group
    )
    registration.offering = alternate
    registration.save(update_fields=["offering"])

    before = [("registrations", "0002_postgresql_integrity")]
    after = [("registrations", "0003_submission_offering")]
    MigrationExecutor(connection).migrate(before)
    MigrationExecutor(connection).migrate(after)

    restored = RegistrationSubmission.objects.get(pk=original.pk)
    assert restored.offering_id == dataset["offering"].id
    assert restored.offering_id != registration.offering_id
    assert bytes(restored.snapshot_enc) == bytes(original.snapshot_enc)
