from django.db import migrations

# Composite references and immutable history require PostgreSQL. SQLite runs only
# portable service tests; it is not a substitute for these production constraints.
SQL = r"""
ALTER TABLE competition_events ADD CONSTRAINT event_id_edition_unique UNIQUE (id, edition_id);
ALTER TABLE competition_groups ADD CONSTRAINT group_id_edition_unique UNIQUE (id, edition_id);
ALTER TABLE competition_offerings ADD CONSTRAINT offering_id_edition_unique UNIQUE (id, edition_id);
ALTER TABLE competition_offerings ADD CONSTRAINT offering_event_same_edition FOREIGN KEY(event_id,edition_id) REFERENCES competition_events(id,edition_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE competition_offerings ADD CONSTRAINT offering_group_same_edition FOREIGN KEY(group_id,edition_id) REFERENCES competition_groups(id,edition_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registrations ADD CONSTRAINT registration_offering_same_edition FOREIGN KEY(offering_id,edition_id) REFERENCES competition_offerings(id,edition_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE team_numbers ADD CONSTRAINT team_number_same_org_unique UNIQUE (id,org_id);
ALTER TABLE teams ADD CONSTRAINT team_number_same_org FOREIGN KEY(team_number_id,org_id) REFERENCES team_numbers(id,org_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE teams ADD CONSTRAINT team_id_org_event_unique UNIQUE(id,org_id,event_code);
ALTER TABLE teams ADD CONSTRAINT team_id_event_unique UNIQUE(id,event_code);
ALTER TABLE team_change_requests ADD CONSTRAINT request_id_team_unique UNIQUE(id,team_id);
ALTER TABLE team_change_requests ADD CONSTRAINT request_team_same_org_event FOREIGN KEY(team_id,org_id,event_code) REFERENCES teams(id,org_id,event_code) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE team_change_requests ADD CONSTRAINT request_base_same_team FOREIGN KEY(base_revision_id,team_id) REFERENCES team_change_requests(id,team_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE teams ADD CONSTRAINT approved_revision_same_team FOREIGN KEY(approved_revision_id,id) REFERENCES team_change_requests(id,team_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE team_change_requests ADD CONSTRAINT request_kind_fields CHECK ((request_kind='create' AND registration_season_id IS NOT NULL AND base_revision_id IS NULL) OR (request_kind='update' AND team_id IS NOT NULL AND base_revision_id IS NOT NULL));
ALTER TABLE team_change_requests ADD CONSTRAINT request_reviewed_metadata CHECK (status NOT IN ('approved','returned','rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL));
ALTER TABLE registrations ADD CONSTRAINT reg_id_team_unique UNIQUE(id,team_id);
ALTER TABLE registration_submissions ADD CONSTRAINT submission_team_matches_registration FOREIGN KEY(registration_id,team_id) REFERENCES registrations(id,team_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registration_submissions ADD CONSTRAINT submission_revision_same_team FOREIGN KEY(team_revision_id,team_id) REFERENCES team_change_requests(id,team_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registration_submissions ADD CONSTRAINT submission_team_revision_presence CHECK ((team_id IS NULL)=(team_revision_id IS NULL));
ALTER TABLE registrations ADD CONSTRAINT current_submission_reference FOREIGN KEY(id,current_submission_no) REFERENCES registration_submissions(registration_id,submission_no) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registrations ADD CONSTRAINT approved_submission_reference FOREIGN KEY(id,approved_submission_no) REFERENCES registration_submissions(registration_id,submission_no) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registrations ADD CONSTRAINT approved_submission_matches_current CHECK (status<>'approved' OR (approved_submission_no IS NOT NULL AND current_submission_no IS NOT NULL AND approved_submission_no=current_submission_no));
ALTER TABLE registration_members ADD CONSTRAINT member_submission_reference FOREIGN KEY(registration_id,submission_no) REFERENCES registration_submissions(registration_id,submission_no) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE approval_records ADD CONSTRAINT approval_submission_reference FOREIGN KEY(registration_id,submission_no) REFERENCES registration_submissions(registration_id,submission_no) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE season_student_team_bindings ADD CONSTRAINT binding_original_team_event FOREIGN KEY(original_team_id,event_code) REFERENCES teams(id,event_code) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE season_student_team_bindings ADD CONSTRAINT binding_current_team_event FOREIGN KEY(current_team_id,event_code) REFERENCES teams(id,event_code) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE season_student_team_bindings ADD CONSTRAINT binding_source_submission FOREIGN KEY(source_registration_id,source_submission_no) REFERENCES registration_submissions(registration_id,submission_no) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE users ADD CONSTRAINT org_created_user_metadata CHECK (account_source<>'org' OR (created_by_id IS NOT NULL AND created_by_org_id IS NOT NULL));
ALTER TABLE user_profiles ADD CONSTRAINT identity_fields_complete CHECK ((document_type IS NULL AND document_country IS NULL AND document_number_enc IS NULL AND document_hash IS NULL AND document_last4 IS NULL) OR (document_type IN ('id_card','passport') AND document_country ~ '^[A-Z]{2}$' AND document_number_enc IS NOT NULL AND document_hash IS NOT NULL AND document_last4 IS NOT NULL AND (document_type<>'id_card' OR document_country='CN')));
CREATE FUNCTION reject_immutable_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND TG_TABLE_NAME='registration_submissions' AND OLD.cancelled_at IS NULL AND NEW.cancelled_at IS NOT NULL AND (to_jsonb(OLD)-'cancelled_at')=(to_jsonb(NEW)-'cancelled_at') THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'Immutable business history cannot be modified' USING ERRCODE='55000';
END; $$;
CREATE TRIGGER immutable_submission BEFORE UPDATE OR DELETE ON registration_submissions FOR EACH ROW EXECUTE FUNCTION reject_immutable_history();
CREATE TRIGGER immutable_registration_member BEFORE UPDATE OR DELETE ON registration_members FOR EACH ROW EXECUTE FUNCTION reject_immutable_history();
CREATE TRIGGER immutable_approval_record BEFORE UPDATE OR DELETE ON approval_records FOR EACH ROW EXECUTE FUNCTION reject_immutable_history();
"""


def apply_postgresql_constraints(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def remove_postgresql_constraints(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP FUNCTION IF EXISTS reject_immutable_history() CASCADE"
        )
        for table, names in {
            "competition_events": ["event_id_edition_unique"],
            "competition_groups": ["group_id_edition_unique"],
            "competition_offerings": [
                "offering_id_edition_unique",
                "offering_event_same_edition",
                "offering_group_same_edition",
            ],
            "team_numbers": ["team_number_same_org_unique"],
            "teams": [
                "team_number_same_org",
                "team_id_org_event_unique",
                "team_id_event_unique",
                "approved_revision_same_team",
            ],
            "team_change_requests": [
                "request_id_team_unique",
                "request_team_same_org_event",
                "request_base_same_team",
                "request_kind_fields",
                "request_reviewed_metadata",
            ],
            "registrations": [
                "registration_offering_same_edition",
                "reg_id_team_unique",
                "current_submission_reference",
                "approved_submission_reference",
                "approved_submission_matches_current",
            ],
            "registration_submissions": [
                "submission_team_matches_registration",
                "submission_revision_same_team",
                "submission_team_revision_presence",
            ],
            "registration_members": ["member_submission_reference"],
            "approval_records": ["approval_submission_reference"],
            "season_student_team_bindings": [
                "binding_original_team_event",
                "binding_current_team_event",
                "binding_source_submission",
            ],
            "users": ["org_created_user_metadata"],
            "user_profiles": ["identity_fields_complete"],
        }.items():
            for name in names:
                schema_editor.execute(
                    f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name} CASCADE"
                )


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0001_initial"),
        ("accounts", "0002_initial"),
        ("profiles", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(
            apply_postgresql_constraints, remove_postgresql_constraints
        )
    ]
