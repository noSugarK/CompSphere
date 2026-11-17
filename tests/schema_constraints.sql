-- Synthetic values only; these bytes are fixtures, not usable encrypted identities.
CREATE FUNCTION expect_error(statement TEXT, expected_state TEXT) RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE statement;
  EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE = expected_state THEN RETURN; END IF;
    RAISE;
  END;
  RAISE EXCEPTION 'Expected SQLSTATE %, but statement succeeded: %', expected_state, statement;
END;
$$;

-- Keep generated IDs separate from explicit fixture IDs.
DO $$
DECLARE sequence_name TEXT;
BEGIN
  FOR sequence_name IN SELECT sequencename FROM pg_sequences WHERE schemaname=current_schema()
  LOOP
    PERFORM setval(format('%I.%I',current_schema(),sequence_name)::regclass,1000);
  END LOOP;
END;
$$;

INSERT INTO users(id,username,email,password_hash) VALUES
  (1,'member-one','one@example.invalid','fixture'),
  (2,'member-two','two@example.invalid','fixture');
UPDATE users SET locale='en-US', theme='dark' WHERE id=1;
SELECT expect_error($s$UPDATE users SET locale='fr-FR' WHERE id=1$s$,'23514');
SELECT expect_error($s$UPDATE users SET theme='custom' WHERE id=1$s$,'23514');
INSERT INTO roles(id,code,name) VALUES (1,'participant','Participant');
INSERT INTO user_roles(user_id,role_id,scope_type) VALUES (1,1,'global');
SELECT expect_error($s$INSERT INTO user_roles(user_id,role_id,scope_type) VALUES (1,1,'global')$s$,'23505');
SELECT expect_error($s$INSERT INTO user_roles(user_id,role_id,scope_type,scope_id) VALUES (1,1,'unknown',1)$s$,'23514');
INSERT INTO user_profiles(user_id,real_name,document_type,document_country,document_number_enc,document_hash,document_last4,is_deleted,deleted_at)
  VALUES (1,'Synthetic one','id_card','CN',decode('00','hex'),'fixture-hash','0000',true,now());
SELECT expect_error($s$INSERT INTO user_profiles(user_id,real_name,document_type,document_country,document_number_enc,document_hash,document_last4)
  VALUES (2,'Synthetic two','id_card','CN',decode('00','hex'),'fixture-hash','0000')$s$,'23505');
-- Nonparticipants may omit identity; telephone numbers may be shared.
INSERT INTO user_profiles(user_id,real_name,person_type) VALUES (2,'Synthetic staff','staff');
UPDATE users SET phone='shared-contact';

INSERT INTO organizations(id,code,name,org_type,path,depth) VALUES (1,'TEST','Test','school','0001',1);
INSERT INTO org_creation_requests(id,proposal_enc,status,submitted_by,reviewer_id,reviewed_at,result_org_id)
  VALUES (1,decode('00','hex'),'approved',1,2,now(),1);
SELECT expect_error($s$INSERT INTO org_creation_requests(proposal_enc,status,submitted_by,reviewer_id)
  VALUES (decode('00','hex'),'submitted',1,1)$s$,'23514');
SELECT expect_error($s$INSERT INTO org_creation_requests(proposal_enc,status,submitted_by,reviewer_id,reviewed_at)
  VALUES (decode('00','hex'),'approved',1,2,now())$s$,'23514');
INSERT INTO event_types(code,name) VALUES ('E','Event'),('F','Other event'),('G','Third event');
INSERT INTO team_numbers(id,code,org_id) VALUES (1,'TEAM',1),(2,'TEAM-TWO',1);
INSERT INTO teams(id,team_number_id,event_code,name,org_id) VALUES (1,1,'E','Team',1),(2,2,'E','Team two',1),(3,1,'F','Team',1);
INSERT INTO seasons(id,code,name,starts_on,ends_on,status,is_default) VALUES (1,'2026-2027','2026-2027 Season','2026-09-01','2027-08-31','active',true),(2,'2025-2026','2025-2026 Season','2025-09-01','2026-08-31','archived',false);
INSERT INTO team_change_requests(id,team_id,org_id,team_code,event_code,request_kind,registration_season_id,proposal_enc,status,submitted_by,reviewer_id,reviewed_at) VALUES
  (1,1,1,'TEAM','E','create',1,decode('00','hex'),'approved',1,2,now()),
  (2,2,1,'TEAM-TWO','E','create',1,decode('00','hex'),'approved',1,2,now());
UPDATE teams SET approved_revision_id=id WHERE id IN (1,2);
SELECT expect_error($s$UPDATE teams SET approved_revision_id=2 WHERE id=1$s$,'23503');
SELECT expect_error($s$INSERT INTO team_change_requests(team_id,org_id,team_code,event_code,request_kind,registration_season_id,proposal_enc,status,submitted_by,reviewer_id,reviewed_at)
  VALUES (1,1,'SELF','E','create',1,decode('00','hex'),'approved',1,1,now())$s$,'23514');
SELECT expect_error($s$INSERT INTO team_change_requests(team_id,org_id,team_code,event_code,request_kind,base_revision_id,proposal_enc,submitted_by)
  VALUES (2,1,'WRONG-BASE','E','update',1,decode('00','hex'),1)$s$,'23503');
INSERT INTO team_change_requests(id,team_id,org_id,team_code,event_code,request_kind,base_revision_id,proposal_enc,submitted_by)
  VALUES (3,1,1,'TEAM','E','update',1,decode('00','hex'),1);
SELECT expect_error($s$INSERT INTO team_change_requests(team_id,org_id,team_code,event_code,request_kind,base_revision_id,proposal_enc,submitted_by)
  VALUES (1,1,'DUP-PENDING','E','update',1,decode('00','hex'),1)$s$,'23505');
INSERT INTO competitions(id,public_code,name) VALUES (1,'TEST','Test');
INSERT INTO competition_editions(id,season_id,competition_id,edition_no,year,name) VALUES
  (1,1,1,1,2026,'Edition one'),(2,1,1,2,2026,'Edition two');
SELECT expect_error($s$UPDATE competition_editions SET team_entry_mode='unknown' WHERE id=1$s$,'23514');
SELECT expect_error($s$UPDATE competition_editions SET team_access_version=0 WHERE id=1$s$,'23514');
INSERT INTO edition_team_allowlist(edition_id,team_id,source,created_by) VALUES (1,1,'import',1),(2,1,'manual',1);
SELECT expect_error($s$INSERT INTO edition_team_allowlist(edition_id,team_id,source,created_by) VALUES (1,1,'manual',1)$s$,'23505');
SELECT expect_error($s$INSERT INTO edition_team_allowlist(edition_id,team_id,source,created_by) VALUES (1,999,'manual',1)$s$,'23503');
SELECT expect_error($s$UPDATE edition_team_allowlist SET status='unknown' WHERE edition_id=1 AND team_id=1$s$,'23514');
INSERT INTO competition_events(id,edition_id,code,name) VALUES (1,1,'E','Event'),(2,2,'E','Event');
INSERT INTO competition_groups(id,edition_id,code,name) VALUES (1,1,'HS','Group'),(2,2,'HS','Group');
INSERT INTO competition_offerings(id,edition_id,event_id,group_id) VALUES (1,1,1,1),(2,2,2,2);
SELECT expect_error($s$INSERT INTO competition_offerings(edition_id,event_id,group_id) VALUES (1,2,1)$s$,'23503');
SELECT expect_error($s$INSERT INTO competition_offerings(edition_id,event_id,group_id) VALUES (1,1,2)$s$,'23503');
INSERT INTO registrations(id,batch_no,edition_id,offering_id,enrollment_kind,team_id,individual_user_id,submitted_by,contact_phone,contact_email,status) VALUES
  (1,'REG-ONE',1,1,'team',1,NULL,1,'fixture','one@example.invalid','pending_review'),
  (2,'REG-TWO',2,2,'individual',NULL,2,2,'fixture','two@example.invalid','pending_review'),
  (3,'REG-THREE',1,1,'individual',NULL,2,2,'fixture','two@example.invalid','pending_review');
SELECT expect_error($s$INSERT INTO registrations(batch_no,edition_id,offering_id,enrollment_kind,individual_user_id,submitted_by,contact_phone,contact_email)
  VALUES ('CROSS',1,2,'individual',1,1,'fixture','one@example.invalid')$s$,'23503');
SELECT expect_error($s$INSERT INTO registrations(batch_no,edition_id,offering_id,enrollment_kind,team_id,submitted_by,contact_phone,contact_email,status)
  VALUES ('DUP',1,1,'team',1,1,'fixture','one@example.invalid','pending_review')$s$,'23505');
INSERT INTO registration_submissions(registration_id,submission_no,team_id,team_revision_id,snapshot_enc,submitted_by) VALUES
  (1,1,1,1,decode('00','hex'),1), (2,1,NULL,NULL,decode('00','hex'),2), (3,1,NULL,NULL,decode('00','hex'),2);
UPDATE registrations SET current_submission_no=1,approved_submission_no=1,status='approved';
SELECT expect_error($s$UPDATE registrations SET current_submission_no=99 WHERE id=1$s$,'23514');
SELECT expect_error($s$INSERT INTO registration_submissions(registration_id,submission_no,team_id,team_revision_id,snapshot_enc,submitted_by)
  VALUES (1,2,1,2,decode('00','hex'),1)$s$,'23503');
INSERT INTO registration_members(id,registration_id,user_id,snapshot_enc,public_info,role) VALUES
  (1,1,1,decode('00','hex'),'{}','captain'),(2,1,2,decode('00','hex'),'{}','member'),
  (3,2,2,decode('00','hex'),'{}','member'),(4,3,2,decode('00','hex'),'{}','member');
SELECT expect_error($s$INSERT INTO registration_members(registration_id,user_id,snapshot_enc,public_info)
  VALUES (1,1,decode('00','hex'),'{}')$s$,'23505');
INSERT INTO awards(id,edition_id,offering_id,rank_level,name) VALUES (1,1,1,'first','First'),(2,2,2,'first','First');
INSERT INTO award_rosters(id,edition_id,offering_id) VALUES (1,1,1),(2,2,2);
SELECT expect_error($s$INSERT INTO awards(edition_id,offering_id,rank_level,name) VALUES (1,2,'first','Cross')$s$,'23503');
SELECT expect_error($s$INSERT INTO award_rosters(edition_id,offering_id) VALUES (1,2)$s$,'23503');
INSERT INTO award_records(id,edition_id,roster_id,award_id,registration_id,recipient_kind,batch_no)
  VALUES (1,1,1,1,1,'team','REG-ONE');
SELECT expect_error($s$INSERT INTO award_records(edition_id,roster_id,award_id,registration_id,recipient_kind,batch_no)
  VALUES (1,1,2,3,'individual','REG-THREE')$s$,'23503');
SELECT expect_error($s$INSERT INTO award_records(edition_id,roster_id,award_id,registration_id,recipient_kind,batch_no)
  VALUES (1,2,1,3,'individual','REG-THREE')$s$,'23503');
SELECT expect_error($s$INSERT INTO award_records(edition_id,roster_id,award_id,registration_id,recipient_kind,batch_no)
  VALUES (1,1,1,2,'individual','REG-TWO')$s$,'23503');

-- Two teammates receive distinct certificates from the same team award.
INSERT INTO certificates(id,serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token,status) VALUES
  (1,'CS-T-00001','CS-T',1,1,1,1,1,'Synthetic one','token-one','issued'),
  (2,'CS-T-00002','CS-T',2,1,1,1,2,'Synthetic two','token-two','issued');
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token)
  VALUES ('CS-T-00003','CS-T',3,1,1,1,1,'Duplicate','token-dup')$s$,'23505');
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token)
  VALUES ('CS-T-00004','CS-T',4,1,1,1,3,'Cross member','token-cross')$s$,'23503');
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token)
  VALUES ('CS-T-00005','CS-T',5,1,1,3,4,'Wrong registration','token-wrong')$s$,'23503');
UPDATE certificates SET status='revoked' WHERE id IN (1,2);
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token)
  VALUES ('CS-T-00007','CS-T',7,1,2,1,2,'Wrong edition','token-edition')$s$,'23503');
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token,reissue_of)
  VALUES ('CS-T-00006','CS-T',6,1,1,1,2,'Wrong recipient','token-reissue-cross',1)$s$,'23503');
INSERT INTO certificates(id,serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token,reissue_of)
  VALUES (10,'CS-T-00010','CS-T',10,1,1,1,1,'Synthetic one','token-reissue',1);
UPDATE certificates SET status='failed' WHERE id=10;
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,display_name,qr_token)
  VALUES ('CS-T-00011','CS-T',11,1,1,1,1,'Duplicate retry','token-retry')$s$,'23505');
UPDATE certificates SET status='queued' WHERE id=10;
-- A new round reuses the registration number and preserves prior members.
UPDATE registrations SET status='rejected',approved_submission_no=NULL,form_data='{"correction":"draft"}' WHERE id=3;
INSERT INTO registration_submissions(registration_id,submission_no,snapshot_enc,submitted_by)
  VALUES (3,2,decode('01','hex'),2);
INSERT INTO registration_members(registration_id,submission_no,user_id,snapshot_enc,public_info)
  VALUES (3,2,2,decode('01','hex'),'{}');
UPDATE registrations SET current_submission_no=2,status='pending_review' WHERE id=3;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM registration_submissions WHERE registration_id=3 AND submission_no=1 AND snapshot_enc=decode('00','hex'))
     OR (SELECT count(*) FROM registration_members WHERE registration_id=3 AND user_id=2) <> 2 THEN
    RAISE EXCEPTION 'Resubmission lost prior snapshot or membership';
  END IF;
END;
$$;
SELECT expect_error($s$INSERT INTO registration_members(registration_id,submission_no,user_id,snapshot_enc,public_info)
  VALUES (3,99,2,decode('00','hex'),'{}')$s$,'23503');
SELECT expect_error($s$INSERT INTO registration_submissions(registration_id,submission_no,snapshot_enc,submitted_by)
  VALUES (3,2,decode('02','hex'),2)$s$,'23505');

-- Current identity changes cannot bypass approval; approved change releases old binding.
SELECT expect_error($s$UPDATE user_profiles SET document_hash='unapproved-change' WHERE user_id=1$s$,'55000');
SELECT expect_error($s$INSERT INTO identity_change_requests(user_id,base_identity_version,old_document_hash,new_document_type,new_document_country,new_document_number_enc,new_document_hash,new_document_last4,status,submitted_by,reviewer_id,reviewed_at)
  VALUES (1,1,'fixture-hash','passport','GB',decode('01','hex'),'new-passport','0001','approved',1,1,now())$s$,'23514');
INSERT INTO identity_change_requests(id,user_id,base_identity_version,old_document_hash,new_document_type,new_document_country,new_document_number_enc,new_document_hash,new_document_last4,status,submitted_by)
  VALUES (1,1,1,'fixture-hash','passport','GB',decode('01','hex'),'new-passport','0001','submitted',1);
SELECT expect_error($s$UPDATE user_profiles SET document_type='passport',document_country='GB',document_number_enc=decode('01','hex'),document_hash='new-passport',document_last4='0001',identity_change_request_id=1 WHERE user_id=1$s$,'55000');
UPDATE identity_change_requests SET status='approved',reviewer_id=2,reviewed_at=now() WHERE id=1;
UPDATE user_profiles SET document_type='passport',document_country='GB',document_number_enc=decode('01','hex'),document_hash='new-passport',document_last4='0001',identity_change_request_id=1 WHERE user_id=1;
INSERT INTO users(id,username,password_hash) VALUES (3,'released-number-owner','fixture'),(4,'another-no-email','fixture');
INSERT INTO user_profiles(user_id,real_name,document_type,document_country,document_number_enc,document_hash,document_last4)
  VALUES (3,'New owner','id_card','CN',decode('00','hex'),'fixture-hash','0000');
SELECT expect_error($s$UPDATE user_profiles SET document_hash='another-unapproved' WHERE user_id=1$s$,'55000');
SELECT expect_error($s$INSERT INTO user_profiles(user_id,real_name,document_type,document_country,document_number_enc,document_hash,document_last4)
  VALUES (4,'Invalid issuer','id_card','US',decode('00','hex'),'invalid-issuer','0000')$s$,'23514');
INSERT INTO users(username,password_hash,account_source,created_by,created_by_org_id,must_change_password)
  VALUES ('provisioned-student','fixture','org',1,1,true);
SELECT expect_error($s$INSERT INTO users(username,password_hash,account_source) VALUES ('missing-provisioner','fixture','org')$s$,'23514');

-- A team number belongs to one organization; number + event identifies the team.
INSERT INTO organizations(id,code,name,org_type,path,depth) VALUES (2,'OTHER','Other','enterprise','0002',1);
SELECT expect_error($s$INSERT INTO team_numbers(code,org_id) VALUES ('TEAM',2)$s$,'23505');
SELECT expect_error($s$INSERT INTO teams(team_number_id,event_code,name,org_id) VALUES (1,'G','Wrong owner',2)$s$,'23503');
SELECT expect_error($s$INSERT INTO teams(team_number_id,event_code,name,org_id) VALUES (1,'E','Duplicate identity',1)$s$,'23505');

-- A second submission cannot issue a certificate against the first-round award.
INSERT INTO registration_submissions(registration_id,submission_no,team_id,team_revision_id,selected_school_level,snapshot_enc,submitted_by)
  VALUES (1,2,1,1,'HS',decode('02','hex'),1);
INSERT INTO registration_members(id,registration_id,submission_no,user_id,snapshot_enc,public_info)
  VALUES (20001,1,2,1,decode('02','hex'),'{}');
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,submission_no,display_name,qr_token)
  VALUES ('ROUND-1','ROUND',1,1,1,1,20001,1,'Wrong member round','round-token-1')$s$,'23503');
SELECT expect_error($s$INSERT INTO certificates(serial_no,serial_prefix,serial_no_seq,award_record_id,edition_id,registration_id,recipient_member_id,submission_no,display_name,qr_token)
  VALUES ('ROUND-2','ROUND',2,1,1,1,20001,2,'Wrong award round','round-token-2')$s$,'23503');

-- Unreviewed cancellation retains the old submission; the next round captures new mode.
UPDATE registration_submissions SET cancelled_at=now() WHERE registration_id=3 AND submission_no=2;
UPDATE registrations SET status='draft' WHERE id=3;
UPDATE competition_editions SET approval_mode='two_stage' WHERE id=1;
INSERT INTO registration_submissions(registration_id,submission_no,approval_mode,selected_school_level,snapshot_enc,submitted_by)
  VALUES (3,3,'two_stage','HS',decode('03','hex'),2);
UPDATE registrations SET current_submission_no=3,status='submitted' WHERE id=3;
SELECT expect_error($s$UPDATE registrations SET status='approved',approved_submission_no=2 WHERE id=3$s$,'23514');
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM registration_submissions WHERE registration_id=3 AND submission_no=2 AND approval_mode='single' AND cancelled_at IS NOT NULL)
     OR NOT EXISTS (SELECT 1 FROM registration_submissions WHERE registration_id=3 AND submission_no=3 AND approval_mode='two_stage') THEN
    RAISE EXCEPTION 'Cancellation or frozen approval mode lost';
  END IF;
END;
$$;
INSERT INTO async_outbox(topic,business_key,payload) VALUES ('certificate.generate','certificate:10:v1','{"certificate_id":10,"roster_version":1}');
SELECT expect_error($s$INSERT INTO async_outbox(topic,business_key,payload) VALUES ('certificate.generate','certificate:10:v1','{}')$s$,'23505');
SELECT expect_error($s$UPDATE async_outbox SET status='unknown'$s$,'23514');

-- Identity metadata and stale approvals cannot bypass a fresh review.
SELECT expect_error($s$UPDATE user_profiles SET identity_version=99 WHERE user_id=1$s$,'55000');
SELECT expect_error($s$UPDATE user_profiles SET document_type='id_card',document_country='CN',document_hash='fixture-hash',document_last4='0000',document_number_enc=decode('00','hex'),identity_change_request_id=1 WHERE user_id=1$s$,'55000');
SELECT expect_error($s$INSERT INTO identity_change_requests(user_id,base_identity_version,old_document_hash,new_document_type,new_document_country,new_document_number_enc,new_document_hash,new_document_last4,status,submitted_by,reviewer_id,reviewed_at)
  VALUES (1,2,'new-passport','passport','GB',decode('02','hex'),'another-passport','0002','approved',2,1,now())$s$,'23514');
SELECT expect_error($s$UPDATE registrations SET status='approved',approved_submission_no=NULL WHERE id=3$s$,'23514');

-- One student has one current team globally, including across event types.
INSERT INTO team_members(team_id,user_id,joined_at) VALUES (1,3,'2026-01-01T00:00:00Z');
SELECT expect_error($s$INSERT INTO team_members(team_id,user_id,joined_at) VALUES (2,3,'2026-01-02T00:00:00Z')$s$,'23505');
SELECT expect_error($s$INSERT INTO team_members(team_id,user_id,joined_at) VALUES (3,3,'2026-01-02T00:00:00Z')$s$,'23505');
SELECT expect_error($s$UPDATE team_members SET left_at='2025-12-31T00:00:00Z' WHERE user_id=3$s$,'23514');
UPDATE team_members SET left_at='2026-01-03T00:00:00Z' WHERE team_id=1 AND user_id=3;
INSERT INTO team_members(team_id,user_id,joined_at) VALUES (2,3,'2026-01-04T00:00:00Z');
SELECT expect_error($s$UPDATE team_members SET left_at=NULL WHERE team_id=1 AND user_id=3$s$,'23505');
DO $$
BEGIN
  IF (SELECT count(*) FROM team_members WHERE user_id=3) <> 2
     OR (SELECT count(*) FROM team_members WHERE user_id=3 AND left_at IS NULL) <> 1 THEN
    RAISE EXCEPTION 'Team transfer lost historical membership';
  END IF;
END;
$$;

-- Leaving current membership preserves competition binding; direct switches are blocked.
INSERT INTO registration_members(registration_id,submission_no,user_id,snapshot_enc,public_info) VALUES (1,1,3,decode('00','hex'),'{}');
INSERT INTO season_student_team_bindings(season_id,event_code,user_id,original_team_id,current_team_id,source_registration_id,source_submission_no)
  VALUES (1,'E',3,1,1,1,1);
SELECT expect_error($s$INSERT INTO season_student_team_bindings(season_id,event_code,user_id,original_team_id,current_team_id,source_registration_id,source_submission_no) VALUES (1,'E',3,1,1,1,1)$s$,'23505');
SELECT expect_error($s$UPDATE season_student_team_bindings SET current_team_id=2 WHERE user_id=3$s$,'55000');
SELECT expect_error($s$UPDATE season_student_team_bindings SET binding_version=99 WHERE user_id=3$s$,'55000');
UPDATE team_members SET left_at='2026-01-05T00:00:00Z' WHERE user_id=3 AND left_at IS NULL;
DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM season_student_team_bindings WHERE user_id=3 AND current_team_id=1) THEN RAISE EXCEPTION 'Leaving cleared competition binding'; END IF;
END; $$;
INSERT INTO team_members(team_id,user_id,joined_at) VALUES (1,3,'2026-01-06T00:00:00Z'); -- Rejoining original team is legal.
SELECT expect_error($s$INSERT INTO team_transfer_requests(season_id,event_code,user_id,from_team_id,to_team_id,base_binding_version,reason,submitted_by) VALUES (1,'E',3,1,3,1,'Test reason',3)$s$,'23503');
SELECT expect_error($s$INSERT INTO team_transfer_requests(season_id,event_code,user_id,from_team_id,to_team_id,base_binding_version,reason,submitted_by,status,reviewer_id,reviewed_at) VALUES (1,'E',3,1,2,1,'Test reason',3,'approved',3,now())$s$,'23514');
INSERT INTO team_transfer_requests(id,season_id,event_code,user_id,from_team_id,to_team_id,base_binding_version,reason,submitted_by)
  VALUES (1,1,'E',3,1,2,1,'Reviewed transfer',3);
SELECT expect_error($s$UPDATE season_student_team_bindings SET current_team_id=2,last_transfer_request_id=1 WHERE user_id=3$s$,'55000');
UPDATE team_transfer_requests SET status='approved',reviewer_id=2,reviewed_at=now() WHERE id=1;
UPDATE season_student_team_bindings SET current_team_id=2,last_transfer_request_id=1 WHERE user_id=3;
UPDATE team_members SET left_at='2026-01-07T00:00:00Z' WHERE user_id=3 AND left_at IS NULL;
INSERT INTO team_members(team_id,user_id,joined_at) VALUES (2,3,'2026-01-08T00:00:00Z');
DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM season_student_team_bindings WHERE user_id=3 AND current_team_id=2 AND original_team_id=1 AND binding_version=2) THEN RAISE EXCEPTION 'Approved transfer lost binding origin'; END IF;
END; $$;
SELECT expect_error($s$UPDATE season_student_team_bindings SET current_team_id=1 WHERE user_id=3$s$,'55000');

SELECT expect_error($s$DELETE FROM season_student_team_bindings WHERE user_id=3$s$,'55000');

-- Season boundaries and cross-competition participation share one binding.
SELECT expect_error($s$INSERT INTO seasons(code,name,starts_on,ends_on) VALUES ('INVALID','Invalid','2027-08-31','2026-09-01')$s$,'23514');
SELECT expect_error($s$INSERT INTO seasons(code,name,starts_on,ends_on,status,is_default) VALUES ('OTHER','Other','2026-07-01','2027-06-30','active',true)$s$,'23505');
SELECT expect_error($s$UPDATE competition_editions SET season_id=999 WHERE id=1$s$,'23503');
SELECT expect_error($s$INSERT INTO season_student_team_bindings(season_id,event_code,user_id,original_team_id,current_team_id,source_registration_id,source_submission_no) VALUES (2,'E',3,1,1,1,1)$s$,'23514');
INSERT INTO competitions(id,public_code,name) VALUES (2,'SECOND','Second competition');
INSERT INTO competition_editions(id,season_id,competition_id,edition_no,year,name) VALUES (3,1,2,1,2027,'Another competition in same season');
INSERT INTO competition_events(id,edition_id,code,name) VALUES (3,3,'E','Event');
INSERT INTO competition_groups(id,edition_id,code,name) VALUES (3,3,'HS','Group');
INSERT INTO competition_offerings(id,edition_id,event_id,group_id) VALUES (3,3,3,3);
INSERT INTO registrations(id,batch_no,edition_id,offering_id,enrollment_kind,team_id,submitted_by,contact_phone,status) VALUES (4,'CROSS-COMPETITION',3,3,'team',2,2,'fixture','pending_review');
INSERT INTO registration_submissions(registration_id,submission_no,team_id,team_revision_id,snapshot_enc,submitted_by) VALUES (4,1,2,2,decode('00','hex'),2);
INSERT INTO registration_members(registration_id,submission_no,user_id,snapshot_enc,public_info) VALUES (4,1,3,decode('00','hex'),'{}');
UPDATE registrations SET status='approved',current_submission_no=1,approved_submission_no=1 WHERE id=4;
SELECT expect_error($s$INSERT INTO season_student_team_bindings(season_id,event_code,user_id,original_team_id,current_team_id,source_registration_id,source_submission_no) VALUES (1,'E',3,2,2,4,1)$s$,'23505');

-- Organization transfer preserves the account and old membership; only one current primary.
INSERT INTO organization_members(id,org_id,user_id,member_role,is_primary,joined_at) VALUES (1,1,3,'student',true,'2026-01-01');
UPDATE users SET affiliation_version=1 WHERE id=3;
SELECT expect_error($s$INSERT INTO organization_members(org_id,user_id,is_primary) VALUES (2,3,true)$s$,'23505');
SELECT expect_error($s$INSERT INTO org_transfer_requests(user_id,from_org_id,to_org_id,source_membership_id,base_affiliation_version,submitted_by,reason,status) VALUES (3,1,2,1,1,3,'School transfer','awaiting_source')$s$,'23514');
SELECT expect_error($s$INSERT INTO org_transfer_requests(user_id,from_org_id,to_org_id,source_membership_id,base_affiliation_version,submitted_by,authorization_ref,consented_at,reason,status,source_reviewer_id,source_reviewed_at) VALUES (3,1,2,1,1,3,'fixture-consent',now(),'School transfer','awaiting_target',3,now())$s$,'23514');
INSERT INTO org_transfer_requests(id,user_id,from_org_id,to_org_id,source_membership_id,base_affiliation_version,submitted_by,authorization_ref,consented_at,reason,status) VALUES (1,3,1,2,1,1,3,'fixture-consent',now(),'School transfer','awaiting_source');
SELECT expect_error($s$INSERT INTO org_transfer_requests(user_id,from_org_id,to_org_id,source_membership_id,base_affiliation_version,submitted_by,reason) VALUES (3,1,2,1,1,3,'Duplicate request')$s$,'23505');
SELECT expect_error($s$UPDATE org_transfer_requests SET status='awaiting_target' WHERE id=1$s$,'23514');
UPDATE org_transfer_requests SET status='awaiting_target',source_reviewer_id=1,source_reviewed_at=now() WHERE id=1;
SELECT expect_error($s$UPDATE org_transfer_requests SET status='completed',completed_at=now() WHERE id=1$s$,'23514');
SELECT expect_error($s$UPDATE org_transfer_requests SET status='completed',completed_at=now(),target_reviewer_id=1,target_reviewed_at=now() WHERE id=1$s$,'23514');
DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM organization_members WHERE user_id=3 AND org_id=1 AND is_primary AND left_at IS NULL) THEN RAISE EXCEPTION 'Source approval prematurely changed affiliation'; END IF;
END; $$;
UPDATE team_members SET left_at='2026-02-01' WHERE user_id=3 AND left_at IS NULL;
UPDATE organization_members SET left_at='2026-11-17' WHERE id=1;
INSERT INTO organization_members(id,org_id,user_id,member_role,is_primary,joined_at) VALUES (2,2,3,'student',true,'2026-11-17');
UPDATE users SET affiliation_version=affiliation_version+1,token_version=token_version+1 WHERE id=3;
UPDATE org_transfer_requests SET status='completed',target_reviewer_id=2,target_reviewed_at=now(),completed_at=now() WHERE id=1;
DO $$ BEGIN
  IF (SELECT count(*) FROM organization_members WHERE user_id=3) <> 2 OR NOT EXISTS(SELECT 1 FROM organization_members WHERE user_id=3 AND org_id=2 AND is_primary AND left_at IS NULL) OR (SELECT affiliation_version FROM users WHERE id=3) <> 2 THEN RAISE EXCEPTION 'Organization transfer lost account or membership history'; END IF;
END; $$;

SELECT expect_error($s$INSERT INTO team_change_requests(org_id,team_code,event_code,request_kind,proposal_enc,submitted_by) VALUES (1,'NO-SEASON','E','create',decode('00','hex'),1)$s$,'23514');
-- Seasonal team licenses never carry into a different season.
INSERT INTO team_season_registrations(id,team_id,season_id,proposal_enc,submitted_by,status) VALUES (1,1,1,decode('00','hex'),1,'submitted');
SELECT expect_error($s$INSERT INTO team_season_registrations(team_id,season_id,proposal_enc,submitted_by) VALUES (1,1,decode('00','hex'),1)$s$,'23505');
SELECT expect_error($s$UPDATE team_season_registrations SET status='approved' WHERE id=1$s$,'23514');
SELECT expect_error($s$UPDATE team_season_registrations SET status='approved',reviewer_id=1,reviewed_at=now(),comment='Self' WHERE id=1$s$,'23514');
UPDATE team_season_registrations SET status='rejected',reviewer_id=2,reviewed_at=now(),comment='Correct materials' WHERE id=1;
INSERT INTO team_season_registrations(id,team_id,season_id,resubmission_of,proposal_enc,submitted_by,status,reviewer_id,reviewed_at,comment) VALUES (2,1,1,1,decode('00','hex'),1,'approved',2,now(),'Verified');
SELECT expect_error($s$INSERT INTO team_season_registrations(team_id,season_id,proposal_enc,submitted_by) VALUES (1,1,decode('00','hex'),1)$s$,'23505');
SELECT expect_error($s$UPDATE team_season_registrations SET status='revoked' WHERE id=2$s$,'23514');
SELECT expect_error($s$INSERT INTO team_season_registrations(team_id,season_id,proposal_enc,submitted_by) VALUES (1,9999,decode('00','hex'),1)$s$,'23503');
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM team_season_registrations WHERE team_id=1 AND season_id=2 AND status='approved') THEN RAISE EXCEPTION 'License leaked into another season'; END IF;
  IF NOT EXISTS(SELECT 1 FROM team_season_registrations WHERE id=1 AND status='rejected') THEN RAISE EXCEPTION 'Resubmission overwrote history'; END IF;
END; $$;
UPDATE team_season_registrations SET status='revoked',revoked_by=2,revoked_at=now(),revoke_reason='Withdraw eligibility' WHERE id=2;
INSERT INTO team_season_registrations(team_id,season_id,proposal_enc,submitted_by) VALUES (1,1,decode('00','hex'),1);
SELECT 'schema constraints PASS' AS result;
