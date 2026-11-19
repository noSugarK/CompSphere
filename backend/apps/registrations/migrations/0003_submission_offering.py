from itertools import batched

import django.db.models.deletion
from django.db import migrations, models

from core.crypto import decrypt


def copy_frozen_offering(apps, schema_editor):
    alias = schema_editor.connection.alias
    submission_model = apps.get_model("registrations", "RegistrationSubmission")
    offering_model = apps.get_model("events", "Offering")
    is_postgresql = schema_editor.connection.vendor == "postgresql"
    if is_postgresql:
        schema_editor.execute(
            "ALTER TABLE registration_submissions DISABLE TRIGGER immutable_submission"
        )
    submissions = submission_model.objects.using(alias).select_related("registration")
    submissions = submissions.only("snapshot_enc", "registration__edition_id").order_by(
        "id"
    )
    for batch in batched(submissions.iterator(chunk_size=500), 500):
        for submission in batch:
            offering_id = decrypt(submission.snapshot_enc)["offering_id"]
            if type(offering_id) is not int:
                raise ValueError("Invalid offering reference in a frozen submission")
            submission.offering_id = offering_id
        edition_by_offering = dict(
            offering_model.objects.using(alias)
            .filter(pk__in={submission.offering_id for submission in batch})
            .values_list("id", "edition_id")
        )
        if any(
            edition_by_offering.get(submission.offering_id)
            != submission.registration.edition_id
            for submission in batch
        ):
            raise ValueError("Frozen submission references an invalid edition offering")
        submission_model.objects.using(alias).bulk_update(batch, ["offering"])
    if is_postgresql:
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        schema_editor.execute(
            "ALTER TABLE registration_submissions ENABLE TRIGGER immutable_submission"
        )


class Migration(migrations.Migration):
    dependencies = [("registrations", "0002_postgresql_integrity")]
    operations = [
        migrations.AddField(
            model_name="registrationsubmission",
            name="offering",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="events.offering",
            ),
        ),
        migrations.RunPython(copy_frozen_offering, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="registrationsubmission",
            name="offering",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="events.offering"
            ),
        ),
    ]
