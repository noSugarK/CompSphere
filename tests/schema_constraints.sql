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
INSERT INTO user_profiles(user_id,real_name,id_number_enc,id_number_hash,id_number_last4,is_deleted,deleted_at)
  VALUES (1,'Synthetic one',decode('00','hex'),'fixture-hash','0000',true,now());
SELECT expect_error($s$INSERT INTO user_profiles(user_id,real_name,id_number_enc,id_number_hash,id_number_last4)
  VALUES (2,'Synthetic two',decode('00','hex'),'fixture-hash','0000')$s$,'23505');
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
INSERT INTO teams(id,code,name,org_id,school_level) VALUES (1,'TEAM','Team',1,'HS'),(2,'TEAM-TWO','Team two',1,'HS');
INSERT INTO team_change_requests(id,team_id,org_id,team_code,request_kind,proposal_enc,status,submitted_by,reviewer_id,reviewed_at) VALUES
  (1,1,1,'TEAM','create',decode('00','hex'),'approved',1,2,now()),
  (2,2,1,'TEAM-TWO','create',decode('00','hex'),'approved',1,2,now());
UPDATE teams SET approved_revision_id=id;
SELECT expect_error($s$UPDATE teams SET approved_revision_id=2 WHERE id=1$s$,'23503');
SELECT expect_error($s$INSERT INTO team_change_requests(team_id,org_id,team_code,request_kind,proposal_enc,status,submitted_by,reviewer_id,reviewed_at)
  VALUES (1,1,'SELF','create',decode('00','hex'),'approved',1,1,now())$s$,'23514');
SELECT expect_error($s$INSERT INTO team_change_requests(team_id,org_id,team_code,request_kind,base_revision_id,proposal_enc,submitted_by)
  VALUES (2,1,'WRONG-BASE','update',1,decode('00','hex'),1)$s$,'23503');
INSERT INTO team_change_requests(id,team_id,org_id,team_code,request_kind,base_revision_id,proposal_enc,submitted_by)
  VALUES (3,1,1,'TEAM','update',1,decode('00','hex'),1);
SELECT expect_error($s$INSERT INTO team_change_requests(team_id,org_id,team_code,request_kind,base_revision_id,proposal_enc,submitted_by)
  VALUES (1,1,'DUP-PENDING','update',1,decode('00','hex'),1)$s$,'23505');
INSERT INTO competitions(id,public_code,name) VALUES (1,'TEST','Test');
INSERT INTO competition_editions(id,competition_id,edition_no,year,name) VALUES
  (1,1,1,2026,'Edition one'),(2,1,2,2026,'Edition two');
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
  (1,'REG-ONE',1,1,'team',1,NULL,1,'fixture','one@example.invalid','approved'),
  (2,'REG-TWO',2,2,'individual',NULL,2,2,'fixture','two@example.invalid','approved'),
  (3,'REG-THREE',1,1,'individual',NULL,2,2,'fixture','two@example.invalid','approved');
SELECT expect_error($s$INSERT INTO registrations(batch_no,edition_id,offering_id,enrollment_kind,individual_user_id,submitted_by,contact_phone,contact_email)
  VALUES ('CROSS',1,2,'individual',1,1,'fixture','one@example.invalid')$s$,'23503');
SELECT expect_error($s$INSERT INTO registrations(batch_no,edition_id,offering_id,enrollment_kind,team_id,submitted_by,contact_phone,contact_email,status)
  VALUES ('DUP',1,1,'team',1,1,'fixture','one@example.invalid','pending_review')$s$,'23505');
INSERT INTO registration_submissions(registration_id,submission_no,team_id,team_revision_id,snapshot_enc,submitted_by) VALUES
  (1,1,1,1,decode('00','hex'),1), (2,1,NULL,NULL,decode('00','hex'),2), (3,1,NULL,NULL,decode('00','hex'),2);
UPDATE registrations SET current_submission_no=1;
SELECT expect_error($s$UPDATE registrations SET current_submission_no=99 WHERE id=1$s$,'23503');
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
UPDATE registrations SET status='rejected',form_data='{"correction":"draft"}' WHERE id=3;
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
SELECT 'schema constraints PASS' AS result;
