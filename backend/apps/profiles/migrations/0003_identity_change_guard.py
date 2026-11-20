from django.db import migrations

# 04 §guard_profile_identity：证件字段变更只能来自 INSERT、首次绑定或匹配
# 的已批准更正申请；绕开审批流程的写入在数据库层被拒绝。SQLite 无触发器
# 能力，本守卫仅在 PostgreSQL 生效；服务层已在每个写入路径重复校验。
SQL = """
CREATE FUNCTION guard_profile_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.identity_version := CASE WHEN NEW.document_hash IS NULL THEN 0 ELSE 1 END;
    NEW.identity_change_request_id := NULL;
    RETURN NEW;
  END IF;
  IF NEW.user_id <> OLD.user_id THEN
    RAISE EXCEPTION 'Profile owner is immutable' USING ERRCODE = '55000';
  END IF;
  IF ROW(NEW.document_type,NEW.document_country,NEW.document_hash,NEW.document_last4)
     IS NOT DISTINCT FROM ROW(OLD.document_type,OLD.document_country,OLD.document_hash,OLD.document_last4) THEN
    IF NEW.identity_version <> OLD.identity_version OR NEW.identity_change_request_id IS DISTINCT FROM OLD.identity_change_request_id THEN
      RAISE EXCEPTION 'Identity metadata requires an approved change' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
  END IF;
  IF OLD.document_hash IS NULL AND NEW.document_hash IS NOT NULL THEN
    NEW.identity_version := OLD.identity_version + 1;
    NEW.identity_change_request_id := NULL;
    RETURN NEW;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM identity_change_requests r WHERE r.id = NEW.identity_change_request_id
      AND r.user_id = OLD.user_id AND r.status = 'approved' AND r.base_identity_version = OLD.identity_version
      AND r.old_document_hash IS NOT DISTINCT FROM OLD.document_hash
      AND ROW(r.new_document_type,r.new_document_country,r.new_document_hash,r.new_document_last4,r.new_document_number_enc)
          IS NOT DISTINCT FROM ROW(NEW.document_type,NEW.document_country,NEW.document_hash,NEW.document_last4,NEW.document_number_enc)
  ) THEN
    RAISE EXCEPTION 'Identity change requires matching approved request' USING ERRCODE = '55000';
  END IF;
  NEW.identity_version := OLD.identity_version + 1;
  RETURN NEW;
END; $$;
CREATE TRIGGER profile_identity_guard BEFORE INSERT OR UPDATE ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION guard_profile_identity();
"""


def apply_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def remove_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS profile_identity_guard ON user_profiles"
        )
        schema_editor.execute("DROP FUNCTION IF EXISTS guard_profile_identity()")


class Migration(migrations.Migration):
    dependencies = [("profiles", "0002_identitychangerequest_and_more")]
    operations = [migrations.RunPython(apply_guard, remove_guard)]
