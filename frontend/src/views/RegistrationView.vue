<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus';
import { api } from '../api';
import type { Edition, Registration, Team } from '../api/schemas';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
import RegistrationHistory from '../components/RegistrationHistory.vue';
import StatusTag from '../components/StatusTag.vue';
import { readReviewQueueQuery, writeReviewQueueQuery } from '../utils/reviewQueue';

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
const available = ref<Edition['offerings']>([]);
const loadingOfferings = ref(false);
const offeringsError = ref<unknown>(null);
let offeringsRequest = 0;
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
const needsTeam = computed(() => fields.enrollment_kind === 'team' && !fields.team_id);
const selectableOfferings = computed(() => {
  const options = available.value.filter((item) =>
    ['both', fields.enrollment_kind].includes(item.enrollment_type),
  );
  const saved = edition.value?.offerings.find((item) => item.id === record.value?.offering_id);
  return saved && !options.some((item) => item.id === saved.id) ? [saved, ...options] : options;
});
const offering = computed(() =>
  selectableOfferings.value.find((item) => item.id === fields.offering_id),
);
const coachChoices = computed(() => {
  const choices = new Map<number, string>();
  for (const team of teams.value) {
    if (team.coach_id !== null) choices.set(team.coach_id, `${team.team_code} · ${t('coach')}`);
  }
  return Array.from(choices, ([id, label]) => ({ id, label }));
});
const editable = computed(() => !record.value || record.value.can_edit);
const backTarget = computed(() => {
  if (!session.hasAny('approval:review_single')) return '/registrations';
  if (route.query.origin === 'reviews') {
    return { name: 'reviews', query: writeReviewQueueQuery(readReviewQueueQuery(route.query)) };
  }
  return session.hasAny('registration:read_own') ? '/registrations' : '/reviews';
});
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
    }
    if (session.hasAny('registration:create')) teams.value = (await api.teams()).items;
    await loadOfferings();
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
}
function selectOffering() {
  fields.selected_school_level = offering.value?.school_level ?? null;
  form.value?.clearValidate('offering_id');
}

async function loadOfferings() {
  const sequence = ++offeringsRequest;
  offeringsError.value = null;
  loadingOfferings.value = false;
  available.value = [];
  if (
    !edition.value ||
    !editable.value ||
    needsTeam.value ||
    !session.hasAny('registration:create')
  )
    return;
  loadingOfferings.value = true;
  try {
    const options = await api.availableOfferings(edition.value.id, fields.team_id);
    if (sequence === offeringsRequest) available.value = options;
  } catch (error) {
    if (sequence === offeringsRequest) offeringsError.value = error;
  } finally {
    if (sequence === offeringsRequest) loadingOfferings.value = false;
  }
}

function selectTeam() {
  fields.coach_user_id =
    teams.value.find((team) => team.id === fields.team_id)?.coach_id ?? undefined;
  fields.offering_id = undefined;
  selectOffering();
  void loadOfferings();
}

function selectEnrollmentKind() {
  fields.team_id = undefined;
  selectTeam();
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
  if (
    saving.value ||
    loadingOfferings.value ||
    !(await form.value?.validate().catch(() => false)) ||
    !edition.value
  )
    return false;
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
    await loadOfferings();
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') error.value = e;
  } finally {
    saving.value = false;
  }
}
async function review(action: 'approve' | 'reject' | 'return') {
  const target = record.value;
  if (!target?.current_submission_no || saving.value || !canReview.value) return;
  saving.value = true;
  error.value = null;
  try {
    const message =
      target.status === 'approved' ? 'reviewRejectApprovedConfirm' : 'reviewRoundConfirm';
    const result = await ElMessageBox.prompt(
      t(message, {
        batch: target.batch_no,
        round: target.current_submission_no,
        action: t(action),
      }),
      t(action),
      {
        inputType: 'textarea',
        inputPlaceholder: t('comment'),
        inputValidator: (value: string) => {
          if (action !== 'approve' && !value?.trim()) return t('reviewCommentRequired');
          return (value?.trim().length ?? 0) <= 2000 || t('reviewCommentTooLong');
        },
        confirmButtonText: t(action),
        cancelButtonText: t('cancel'),
      },
    );
    assign(
      await api.reviewRegistration(target.id, {
        action,
        comment: result.value || '',
        submission_no: target.current_submission_no,
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
  <router-link :to="backTarget" class="back-link">{{ t('back') }}</router-link>
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
    <section class="content-panel">
      <el-form
        ref="form"
        :model="fields"
        label-position="top"
        @submit.prevent="save"
        :disabled="!editable"
        :scroll-to-error="true"
      >
        <h2>{{ t('group') }}</h2>
        <el-form-item :label="t('enrollmentType')">
          <el-radio-group
            v-model="fields.enrollment_kind"
            :disabled="!!record"
            @change="selectEnrollmentKind"
          >
            <el-radio value="team">{{ t('team') }}</el-radio>
            <el-radio value="individual">{{ t('individualEnrollment') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item
          v-if="fields.enrollment_kind === 'team'"
          prop="team_id"
          :label="t('team')"
          :rules="[{ required: true, message: t('required'), trigger: 'change' }]"
        >
          <el-select v-model="fields.team_id" :disabled="!!record" @change="selectTeam">
            <el-option
              v-for="team in teams"
              :key="team.id"
              :value="team.id"
              :label="`${team.team_code} · ${team.name}`"
            />
            <el-option
              v-if="record?.team_id && !teams.some((team) => team.id === record?.team_id)"
              :value="record.team_id"
              :label="t('registrationCurrentTeam')"
            />
          </el-select>
        </el-form-item>
        <ErrorNotice :error="offeringsError" />
        <el-button v-if="offeringsError" class="retry-button" @click="loadOfferings">{{
          t('retry')
        }}</el-button>
        <div class="form-grid">
          <el-form-item
            prop="offering_id"
            :label="t('group')"
            :rules="[{ required: true, message: t('required'), trigger: 'change' }]"
            ><el-select
              v-model="fields.offering_id"
              :loading="loadingOfferings"
              :validate-event="false"
              :disabled="needsTeam || loadingOfferings"
              aria-describedby="registration-offering-hint"
              @change="selectOffering"
              ><el-option
                v-for="option in selectableOfferings"
                :key="option.id"
                :value="option.id"
                :label="`${option.event_name} · ${option.group_name}`"
            /></el-select>
            <div id="registration-offering-hint" class="small muted" role="status">
              <template v-if="needsTeam">{{ t('registrationChooseTeamFirst') }}</template>
              <template v-else-if="loadingOfferings">{{ t('loading') }}</template>
              <template v-else-if="!selectableOfferings.length && !offeringsError">{{
                t('offerings.noCurrentWindow')
              }}</template>
            </div> </el-form-item
          ><el-form-item :label="t('schoolLevel')"
            ><el-input :model-value="fields.selected_school_level || '—'" readonly
          /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item :label="t('coach')"
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
        ><el-button
          v-if="record?.status === 'pending_review'"
          :disabled="saving"
          @click="review('return')"
          >{{ t('return') }}</el-button
        ><el-button type="danger" plain :disabled="saving" @click="review('reject')">{{
          t('reject')
        }}</el-button></template
      >
    </div>
  </template>
  <RegistrationHistory v-if="record?.current_submission_no" :record="record" />
</template>
