<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus';
import { api } from '../api';
import type { Edition, Registration, Team } from '../api/schemas';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { formatEventDateTime } from '../utils/format';
import { isOfferingOpen } from '../utils/offerings';

const { t } = useI18n(),
  route = useRoute(),
  router = useRouter(),
  session = useSession();
const edition = ref<Edition>(),
  record = ref<Registration>(),
  teams = ref<Team[]>([]);
const form = ref<FormInstance>(),
  loading = ref(true),
  saving = ref(false),
  error = ref<unknown>(null);
const fields = reactive({
  offering_id: undefined as number | undefined,
  enrollment_kind: 'team' as 'team' | 'individual',
  team_id: undefined as number | undefined,
  coach_user_id: undefined as number | undefined,
  selected_school_level: null as string | null,
  name: '',
  phone: '',
  email: '',
  project_title: '',
  document_usage: false,
});
const offering = computed(() => edition.value?.offerings.find((o) => o.id === fields.offering_id));
const selectableOfferings = computed(
  () =>
    edition.value?.offerings.filter(
      (item) => item.id === record.value?.offering_id || isOfferingOpen(item),
    ) ?? [],
);
const coachChoices = computed(() => {
  const choices = new Map<number, string>();
  for (const team of teams.value) {
    if (team.coach_id !== null) choices.set(team.coach_id, `${team.team_code} · ${t('coach')}`);
  }
  return Array.from(choices, ([id, label]) => ({ id, label }));
});
const editable = computed(() => !record.value || record.value.can_edit);
const canReview = computed(
  () =>
    record.value &&
    session.hasAny('approval:review_single') &&
    record.value.submitted_by !== session.me?.user.id &&
    !record.value.members.some((m) => m.user_id === session.me?.user.id) &&
    (record.value.status === 'pending_review' ||
      (record.value.status === 'approved' && session.hasAny('approval:reject_approved'))),
);
function assign(value: Registration) {
  record.value = value;
  Object.assign(fields, {
    offering_id: value.offering_id,
    enrollment_kind: value.enrollment_kind,
    team_id: value.team_id ?? undefined,
    coach_user_id: value.coach_user_id ?? undefined,
    selected_school_level: value.selected_school_level,
    name: value.contact?.name || '',
    phone: value.contact?.phone || '',
    email: value.contact?.email || '',
    project_title: value.form_data?.project_title || '',
    document_usage: value.consents?.document_usage || false,
  });
}
async function load() {
  loading.value = true;
  error.value = null;
  try {
    if (route.params.id) {
      const value = await api.registration(Number(route.params.id));
      assign(value);
      edition.value = await api.edition(value.edition_id);
    } else {
      edition.value = await api.edition(Number(route.params.editionId));
      fields.offering_id = selectableOfferings.value[0]?.id;
      selectOffering();
    }
    if (session.hasAny('registration:create')) teams.value = (await api.teams()).items;
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
}
function selectOffering() {
  fields.selected_school_level = offering.value?.school_level ?? null;
  if (offering.value?.enrollment_type === 'individual') {
    fields.enrollment_kind = 'individual';
    fields.team_id = undefined;
  } else fields.enrollment_kind = 'team';
}
function selectTeam() {
  fields.coach_user_id =
    teams.value.find((team) => team.id === fields.team_id)?.coach_id ?? undefined;
}
function body() {
  return {
    offering_id: fields.offering_id,
    enrollment_kind: fields.enrollment_kind,
    ...(fields.enrollment_kind === 'team' ? { team_id: fields.team_id } : {}),
    coach_user_id: fields.coach_user_id ?? null,
    selected_school_level: fields.selected_school_level,
    contact: { name: fields.name, phone: fields.phone, email: fields.email || null },
    form_data: { project_title: fields.project_title },
    consents: { document_usage: fields.document_usage },
  };
}
async function save() {
  if (!(await form.value?.validate().catch(() => false)) || !edition.value) return false;
  saving.value = true;
  error.value = null;
  try {
    const result = record.value
      ? await api.saveRegistration(record.value.id, record.value.version, body())
      : await api.createRegistration(edition.value.id, body());
    assign(result);
    ElMessage.success(t('success'));
    if (!route.params.id) await router.replace(`/registrations/${result.id}`);
    return true;
  } catch (e) {
    error.value = e;
    return false;
  } finally {
    saving.value = false;
  }
}
async function submit() {
  if (!record.value || !(await form.value?.validate().catch(() => false))) return;
  try {
    await ElMessageBox.confirm(t('submitConfirm'), t('submit'), {
      confirmButtonText: t('submit'),
      cancelButtonText: t('cancel'),
    });
    if (!(await save()) || !record.value) return;
    saving.value = true;
    const action = ['returned', 'rejected'].includes(record.value.status) ? 'resubmit' : 'submit';
    assign(
      await api.registrationAction(
        record.value.id,
        action,
        record.value.version,
        crypto.randomUUID(),
      ),
    );
    ElMessage.success(t('success'));
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') error.value = e;
  } finally {
    saving.value = false;
  }
}
async function cancelReview() {
  if (!record.value) return;
  try {
    await ElMessageBox.confirm(t('cancelConfirm'), t('cancelledit'), {
      confirmButtonText: t('cancelledit'),
      cancelButtonText: t('cancel'),
    });
    saving.value = true;
    assign(await api.registrationAction(record.value.id, 'cancel-review', record.value.version));
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') error.value = e;
  } finally {
    saving.value = false;
  }
}
async function review(action: 'approve' | 'reject' | 'return') {
  if (!record.value?.current_submission_no) return;
  try {
    const result = await ElMessageBox.prompt(t('reviewConfirm'), t(action), {
      inputType: 'textarea',
      inputPlaceholder: t('comment'),
      inputValidator: (value: string) => action === 'approve' || !!value?.trim() || t('required'),
      confirmButtonText: t(action),
      cancelButtonText: t('cancel'),
    });
    saving.value = true;
    error.value = null;
    assign(
      await api.reviewRegistration(record.value.id, {
        action,
        comment: result.value || '',
        submission_no: record.value.current_submission_no,
      }),
    );
    ElMessage.success(t('success'));
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') error.value = e;
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>
<template>
  <router-link
    :to="
      session.hasAny('approval:review_single') && !session.hasAny('registration:read_own')
        ? '/reviews'
        : '/registrations'
    "
    class="back-link"
    >{{ t('back') }}</router-link
  >
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ edition?.name || t('registrations') }}</h1>
      <p v-if="record">{{ record.batch_no }}</p>
    </div>
    <StatusTag v-if="record" :status="record.status" />
  </div>
  <ErrorNotice :error="error" @retry="load" /><el-skeleton v-if="loading" :rows="9" animated />
  <template v-else-if="edition">
    <el-alert v-if="!editable" :title="t('frozen')" type="info" :closable="false" show-icon />
    <p v-if="!record && !selectableOfferings.length" class="content-panel">
      {{ t('offerings.noCurrentWindow') }}
    </p>
    <section v-else class="content-panel">
      <el-form
        ref="form"
        :model="fields"
        label-position="top"
        @submit.prevent="save"
        :disabled="!editable"
        :scroll-to-error="true"
      >
        <h2>{{ t('group') }}</h2>
        <div class="form-grid">
          <el-form-item
            prop="offering_id"
            :label="t('group')"
            :rules="[{ required: true, message: t('required'), trigger: 'change' }]"
            ><el-select v-model="fields.offering_id" @change="selectOffering"
              ><el-option
                v-for="option in selectableOfferings"
                :key="option.id"
                :value="option.id"
                :label="`${option.event_name} · ${option.group_name}`" /></el-select></el-form-item
          ><el-form-item :label="t('schoolLevel')"
            ><el-input :model-value="fields.selected_school_level || '—'" readonly
          /></el-form-item>
        </div>
        <el-form-item v-if="offering?.enrollment_type === 'both'" :label="t('enrollmentType')"
          ><el-radio-group v-model="fields.enrollment_kind"
            ><el-radio value="team">{{ t('team') }}</el-radio
            ><el-radio value="individual">{{ t('individualEnrollment') }}</el-radio></el-radio-group
          ></el-form-item
        >
        <div class="form-grid">
          <el-form-item
            v-if="fields.enrollment_kind === 'team'"
            prop="team_id"
            :label="t('team')"
            :rules="[{ required: true, message: t('required'), trigger: 'change' }]"
            ><el-select v-model="fields.team_id" @change="selectTeam"
              ><el-option
                v-for="team in teams"
                :key="team.id"
                :value="team.id"
                :label="`${team.team_code} · ${team.name}`" /></el-select></el-form-item
          ><el-form-item :label="t('coach')"
            ><el-select v-model="fields.coach_user_id" clearable
              ><el-option
                v-for="coach in coachChoices"
                :key="coach.id"
                :value="coach.id"
                :label="coach.label"
              />
              <el-option
                v-if="
                  fields.coach_user_id &&
                  !coachChoices.some((coach) => coach.id === fields.coach_user_id)
                "
                :value="fields.coach_user_id"
                :label="t('currentCoach')"
              /> </el-select
          ></el-form-item>
        </div>
        <h2>{{ t('contact') }}</h2>
        <div class="form-grid">
          <el-form-item
            prop="name"
            :label="t('contact')"
            :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
            ><el-input
              v-model="fields.name"
              name="contact_name"
              autocomplete="name"
              :maxlength="64" /></el-form-item
          ><el-form-item
            prop="phone"
            :label="t('phone')"
            :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
            ><el-input
              v-model="fields.phone"
              name="contact_phone"
              type="tel"
              autocomplete="tel"
              :maxlength="20" /></el-form-item
          ><el-form-item
            prop="email"
            :label="t('email')"
            :rules="[{ type: 'email', message: t('fieldError'), trigger: 'blur' }]"
            ><el-input
              v-model="fields.email"
              name="contact_email"
              type="email"
              autocomplete="email"
              :maxlength="255" /></el-form-item
          ><el-form-item :label="t('project')"
            ><el-input v-model="fields.project_title" name="project_title" :maxlength="200"
          /></el-form-item>
        </div>
        <el-form-item prop="document_usage"
          ><el-checkbox v-model="fields.document_usage">{{
            t('consent')
          }}</el-checkbox></el-form-item
        >
        <div v-if="editable" class="actions">
          <el-button type="primary" native-type="submit" :loading="saving">{{
            t('save')
          }}</el-button><el-button v-if="record" :loading="saving" @click="submit">{{
            t('submit')
          }}</el-button>
        </div>
      </el-form>
    </section>
    <section v-if="record?.members.length" class="content-panel">
      <h2>{{ t('members') }}</h2>
      <el-table :data="record.members"
        ><el-table-column prop="real_name" :label="t('name')" /><el-table-column
          prop="school_level"
          :label="t('schoolLevel')" /><el-table-column prop="grade" :label="t('grade')"
      /></el-table>
    </section>
    <section class="content-panel">
      <h2>{{ t('materials') }}</h2>
      <p>{{ offering?.required_materials.join('、') || t('noMaterials') }}</p>
      <el-alert
        v-if="offering?.required_materials.length"
        :title="t('filePending')"
        type="warning"
        :closable="false"
      />
      <p v-if="!record" class="small muted">{{ t('saveFirst') }}</p>
    </section>
    <div class="actions">
      <el-button
        v-if="
          record?.status === 'pending_review' &&
          record.submitted_by === session.me?.user.id &&
          session.hasAny('registration:cancel_review')
        "
        :loading="saving"
        @click="cancelReview"
        >{{ t('cancelledit') }}</el-button><template v-if="canReview"
        ><el-button
          v-if="record?.status === 'pending_review'"
          type="primary"
          :loading="saving"
          @click="review('approve')"
          >{{ t('approve') }}</el-button
        ><el-button v-if="record?.status === 'pending_review'" @click="review('return')">{{
          t('return')
        }}</el-button
        ><el-button type="danger" plain @click="review('reject')">{{
          t('reject')
        }}</el-button></template
      >
    </div>
    <section v-if="record?.approval_records.length" class="content-panel">
      <h2>{{ t('reviewRecord') }}</h2>
      <el-timeline
        ><el-timeline-item
          v-for="item in record.approval_records"
          :key="item.id"
          :timestamp="formatEventDateTime(item.created_at)"
          ><strong>{{ t(item.action) }}</strong>
          <p>{{ item.comment }}</p></el-timeline-item
        ></el-timeline
      >
    </section>
  </template>
</template>
