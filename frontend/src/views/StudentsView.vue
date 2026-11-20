<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessageBox } from 'element-plus';
import { api } from '../api';
import {
  type IdentityChange,
  type OrgMember,
  type Organization,
  type StudentAccount,
} from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { useSession } from '../stores/session';

const { t } = useI18n();
const session = useSession();
const orgs = ref<Organization[]>([]);
const orgId = ref<number>();
const members = ref<OrgMember[]>([]);
const changes = ref<IdentityChange[]>([]);
const section = ref('accounts');
const loading = ref(true);
const saving = ref(false);
const loadError = ref<unknown>(null);
const actionError = ref<unknown>(null);
const feedback = ref('');
const delivered = ref<{ name: string; username: string; password: string }>();
// el-dialog 只接受布尔可见性，凭据对象单独存放。
const credentialOpen = computed({
  get: () => delivered.value !== undefined,
  set: (open: boolean) => {
    if (!open) delivered.value = undefined;
  },
});
const blank = {
  real_name: '',
  document_type: 'id_card' as 'id_card' | 'passport',
  document_country: 'CN',
  document_number: '',
  student_no: '',
};
const form = reactive({ ...blank });
// 幂等键在一次表单提交的所有重试之间保持不变（06 §76）。
let provisionKey = '';
const mayProvision = computed(() => session.hasAny('user:provision'));
const mayReset = computed(() => session.hasAny('user:reset_student_password'));
const mayRequest = computed(() => session.hasAny('profile:request_identity_change'));
const mayReview = computed(() => session.hasAny('profile:review_identity_change'));
const selectableOrgs = computed(() => orgs.value.filter((item) => item.status === 'active'));
const students = computed(() => members.value);
const pendingForMe = computed(() =>
  changes.value.filter((item) =>
    mayReview.value ? item.status === 'submitted' : item.status !== 'approved',
  ),
);

async function loadOrgs() {
  loading.value = true;
  loadError.value = null;
  try {
    orgs.value = (await api.orgs()).items;
    orgId.value ??= selectableOrgs.value[0]?.id;
    await loadAll();
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

async function loadAll() {
  actionError.value = null;
  if (!orgId.value) {
    members.value = [];
    return;
  }
  try {
    const [rows, list] = await Promise.all([api.orgMembers(orgId.value), api.identityChanges()]);
    members.value = rows.items;
    changes.value = list;
  } catch (error) {
    actionError.value = error;
  }
}

async function switchOrg(value: number) {
  orgId.value = value;
  feedback.value = '';
  await loadAll();
}

function beginProvision() {
  if (!provisionKey) provisionKey = crypto.randomUUID();
}

async function submitProvision() {
  if (saving.value || !orgId.value || !form.real_name.trim() || !form.document_number.trim())
    return;
  beginProvision();
  saving.value = true;
  actionError.value = null;
  try {
    const created: StudentAccount = await api.provisionStudent(
      orgId.value,
      {
        real_name: form.real_name.trim(),
        document_type: form.document_type,
        document_country: form.document_country,
        document_number: form.document_number.trim().toUpperCase(),
        student_no: form.student_no.trim() || undefined,
      },
      provisionKey,
    );
    delivered.value = created.temporary_password
      ? {
          name: created.real_name,
          username: created.username,
          password: created.temporary_password,
        }
      : undefined;
    feedback.value = t('studentProvisioned', { name: created.real_name });
    Object.assign(form, blank);
    provisionKey = '';
    await loadAll();
  } catch (error) {
    actionError.value = error;
  } finally {
    saving.value = false;
  }
}

async function reset(member: OrgMember) {
  if (saving.value) return;
  const prompt = await ElMessageBox.prompt(t('studentResetPrompt'), t('studentReset'), {
    inputType: 'textarea',
    inputValidator: (value: string) => value.trim().length > 0 || t('required'),
  }).catch(() => undefined);
  const reason = (prompt?.value ?? '').trim();
  if (!reason) return;
  saving.value = true;
  actionError.value = null;
  try {
    const result = await api.resetStudentPassword(member.user_id, {
      primary_membership_id: member.id,
      affiliation_version: member.affiliation_version,
      reason: reason.trim(),
    });
    delivered.value = {
      name: member.real_name,
      username: result.username,
      password: result.temporary_password,
    };
    await loadAll();
  } catch (error) {
    actionError.value = error;
  } finally {
    saving.value = false;
  }
}

const changeDraft = reactive({
  user_id: undefined as number | undefined,
  document_type: 'id_card' as 'id_card' | 'passport',
  document_country: 'CN',
  document_number: '',
});

async function createChange() {
  if (saving.value || !changeDraft.user_id || !changeDraft.document_number.trim()) return;
  saving.value = true;
  actionError.value = null;
  try {
    await api.createIdentityChange({
      user_id: changeDraft.user_id,
      document_type: changeDraft.document_type,
      document_country: changeDraft.document_country,
      document_number: changeDraft.document_number.trim().toUpperCase(),
    });
    changeDraft.user_id = undefined;
    changeDraft.document_number = '';
    feedback.value = t('identityChangeDraftSaved');
    await loadAll();
  } catch (error) {
    actionError.value = error;
  } finally {
    saving.value = false;
  }
}

async function decide(item: IdentityChange, action: 'submit' | 'approve' | 'return' | 'reject') {
  if (saving.value) return;
  let comment = '';
  if (action === 'return' || action === 'reject') {
    try {
      const prompt = await ElMessageBox.prompt(
        t(action === 'return' ? 'identityReturnPrompt' : 'identityRejectPrompt'),
        t(action === 'return' ? 'identityReturn' : 'identityReject'),
        {
          inputType: 'textarea',
          inputValidator: (value: string) => value.trim().length > 0 || t('required'),
        },
      );
      comment = prompt.value ?? '';
    } catch {
      return;
    }
  } else if (action === 'approve') {
    try {
      await ElMessageBox.confirm(
        t('identityApproveConfirm', { last4: item.new_document_last4 }),
        t('identityApprove'),
        { type: 'warning' },
      );
    } catch {
      return;
    }
  }
  saving.value = true;
  actionError.value = null;
  try {
    if (action === 'submit') await api.submitIdentityChange(item.id);
    else
      await api.reviewIdentityChange(item.id, {
        action,
        comment,
        version: item.base_identity_version,
      });
    feedback.value = t('identityChangeUpdated');
    await loadAll();
  } catch (error) {
    actionError.value = error;
    await loadAll();
  } finally {
    saving.value = false;
  }
}

onMounted(loadOrgs);
</script>

<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('students') }}</h1>
      <p>{{ t('studentsHint') }}</p>
    </div>
  </div>
  <p v-if="loading" role="status">{{ t('loading') }}</p>
  <ErrorNotice v-else-if="loadError" :error="loadError" @retry="loadOrgs" />
  <p v-else-if="!selectableOrgs.length" role="status" class="muted">{{ t('none') }}</p>
  <template v-else>
    <div role="status">
      <p v-if="feedback">{{ feedback }}</p>
    </div>
    <ErrorNotice :error="actionError" @retry="loadAll" />
    <el-dialog
      v-model="credentialOpen"
      :title="t('studentCredentialTitle')"
      width="min(460px, calc(100% - 32px))"
    >
      <p>{{ t('studentCredentialOnce') }}</p>
      <dl class="credential">
        <div>
          <dt>{{ t('studentName') }}</dt>
          <dd>{{ delivered?.name }}</dd>
        </div>
        <div>
          <dt>{{ t('username') }}</dt>
          <dd class="mono">{{ delivered?.username }}</dd>
        </div>
        <div>
          <dt>{{ t('temporaryPassword') }}</dt>
          <dd class="mono">{{ delivered?.password }}</dd>
        </div>
      </dl>
      <template #footer
        ><el-button type="primary" @click="delivered = undefined">{{
          t('close')
        }}</el-button></template
      >
    </el-dialog>
    <el-tabs v-model="section">
      <el-tab-pane :label="t('students')" name="accounts">
        <section class="content-panel">
          <div class="roster-head">
            <h2>{{ t('org') }}</h2>
            <el-select
              :model-value="orgId"
              :disabled="saving"
              class="scope-select"
              @update:model-value="switchOrg"
              ><el-option
                v-for="item in selectableOrgs"
                :key="item.id"
                :value="item.id"
                :label="item.name"
            /></el-select>
          </div>
          <p v-if="!students.length" class="muted">{{ t('none') }}</p>
          <el-table v-else :data="students">
            <el-table-column prop="real_name" :label="t('studentName')" />
            <el-table-column prop="person_type" :label="t('personType')" />
            <el-table-column prop="grade" :label="t('grade')" />
            <el-table-column :label="t('status')">
              <template #default="{ row }">
                <StatusTag v-if="row.is_primary" status="active" />
                <span v-else class="muted small">{{ t('secondaryMembership') }}</span>
              </template>
            </el-table-column>
            <el-table-column v-if="mayReset" :label="t('actions')">
              <template #default="{ row }">
                <el-button
                  v-if="row.member_type === 'student'"
                  text
                  :disabled="saving"
                  @click="reset(row as OrgMember)"
                  >{{ t('studentReset') }}</el-button
                >
              </template>
            </el-table-column>
          </el-table>
          <el-form
            v-if="mayProvision"
            class="provision-form"
            label-position="top"
            @submit.prevent="submitProvision"
          >
            <h2>{{ t('studentProvision') }}</h2>
            <p class="small muted">{{ t('studentProvisionHint') }}</p>
            <div class="form-row">
              <el-form-item :label="t('studentName')" required
                ><el-input
                  v-model="form.real_name"
                  maxlength="64"
                  :disabled="saving"
                  @focus="beginProvision" /></el-form-item
              ><el-form-item :label="t('documentType')" required
                ><el-select
                  v-model="form.document_type"
                  :disabled="saving"
                  @update:model-value="
                    form.document_country = form.document_type === 'id_card' ? 'CN' : ''
                  "
                  ><el-option value="id_card" :label="t('idCard')" /><el-option
                    value="passport"
                    :label="t('passport')" /></el-select></el-form-item
              ><el-form-item :label="t('country')" required
                ><el-input
                  v-model="form.document_country"
                  maxlength="2"
                  :disabled="saving"
                  class="country-input" /></el-form-item
              ><el-form-item :label="t('documentNumber')" required
                ><el-input
                  v-model="form.document_number"
                  maxlength="32"
                  autocomplete="off"
                  :disabled="saving" /></el-form-item
              ><el-form-item :label="t('studentNo')"
                ><el-input v-model="form.student_no" maxlength="64" :disabled="saving"
              /></el-form-item>
            </div>
            <el-button type="primary" native-type="submit" :loading="saving">{{
              t('studentProvision')
            }}</el-button>
          </el-form>
        </section>
      </el-tab-pane>
      <el-tab-pane :label="t('identityChanges')" name="changes" lazy>
        <section class="content-panel">
          <h2>{{ t('identityChanges') }}</h2>
          <p class="small muted">{{ t('identityChangesHint') }}</p>
          <el-form
            v-if="mayRequest && orgId"
            class="provision-form"
            label-position="top"
            @submit.prevent="createChange"
          >
            <div class="form-row">
              <el-form-item :label="t('identityChangeStudent')" required
                ><el-select
                  v-model="changeDraft.user_id"
                  filterable
                  :disabled="saving"
                  :placeholder="t('rosterPickRegistration')"
                  ><el-option
                    v-for="item in students"
                    :key="item.user_id"
                    :value="item.user_id"
                    :label="item.real_name" /></el-select></el-form-item
              ><el-form-item :label="t('documentType')" required
                ><el-select
                  v-model="changeDraft.document_type"
                  :disabled="saving"
                  @update:model-value="
                    changeDraft.document_country =
                      changeDraft.document_type === 'id_card' ? 'CN' : ''
                  "
                  ><el-option value="id_card" :label="t('idCard')" /><el-option
                    value="passport"
                    :label="t('passport')" /></el-select></el-form-item
              ><el-form-item :label="t('country')" required
                ><el-input
                  v-model="changeDraft.document_country"
                  maxlength="2"
                  :disabled="saving"
                  class="country-input" /></el-form-item
              ><el-form-item :label="t('documentNumber')" required
                ><el-input
                  v-model="changeDraft.document_number"
                  maxlength="32"
                  autocomplete="off"
                  :disabled="saving"
              /></el-form-item>
            </div>
            <el-button type="primary" native-type="submit" :loading="saving">{{
              t('identityChangeCreate')
            }}</el-button>
          </el-form>
          <p v-if="!pendingForMe.length" class="muted">{{ t('none') }}</p>
          <el-table v-else :data="pendingForMe">
            <el-table-column :label="t('identityChangeStudent')"
              ><template #default="{ row }">{{
                students.find((item) => item.user_id === row.user_id)?.real_name ?? row.user_id
              }}</template></el-table-column
            ><el-table-column :label="t('documentType')"
              ><template #default="{ row }"
                >{{ t(row.new_document_type) }} · {{ row.new_document_country }} ·
                {{ row.new_document_last4 }}</template
              ></el-table-column
            ><el-table-column :label="t('status')"
              ><template #default="{ row }"
                ><StatusTag :status="row.status" /></template></el-table-column
            ><el-table-column :label="t('identityChangeBase')"
              ><template #default="{ row }"
                >v{{ row.base_identity_version
                }}{{ row.has_old_document ? ' · ' + t('identityChangeReplacement') : '' }}</template
              ></el-table-column
            ><el-table-column :label="t('actions')">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'draft' && mayRequest"
                  text
                  :disabled="saving"
                  @click="decide(row as IdentityChange, 'submit')"
                  >{{ t('identityChangeSubmit') }}</el-button><el-button
                  v-if="row.status === 'submitted' && mayReview"
                  type="primary"
                  text
                  :disabled="saving"
                  @click="decide(row as IdentityChange, 'approve')"
                  >{{ t('identityApprove') }}</el-button
                ><el-button
                  v-if="row.status === 'submitted' && mayReview"
                  text
                  :disabled="saving"
                  @click="decide(row as IdentityChange, 'return')"
                  >{{ t('identityReturn') }}</el-button
                ><el-button
                  v-if="row.status === 'submitted' && mayReview"
                  text
                  :disabled="saving"
                  @click="decide(row as IdentityChange, 'reject')"
                  >{{ t('identityReject') }}</el-button
                >
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>
    </el-tabs>
  </template>
</template>

<style scoped>
.roster-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.roster-head h2 {
  margin-inline-end: auto;
}
.scope-select {
  max-inline-size: 260px;
}
.provision-form {
  margin-block-start: 16px;
}
.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: 0 16px;
}
.country-input {
  max-inline-size: 96px;
}
.credential dd {
  margin: 0 0 8px;
}
</style>
