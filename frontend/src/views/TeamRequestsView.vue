<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus';
import { z } from 'zod';
import { api } from '../api';
import { orgMemberSchema, orgSchema, seasonSchema, type TeamRequest } from '../api/schemas';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
const { t } = useI18n(),
  session = useSession();
const items = ref<TeamRequest[]>([]),
  orgs = ref<z.infer<typeof orgSchema>[]>([]),
  members = ref<z.infer<typeof orgMemberSchema>[]>([]),
  season = ref<z.infer<typeof seasonSchema> | null>(null);
const loading = ref(true),
  saving = ref(false),
  error = ref<unknown>(null),
  showCreate = ref(false),
  form = ref<FormInstance>();
const fields = reactive({
  org_id: undefined as number | undefined,
  team_code: '',
  event_code: 'V5RC',
  name: '',
  coach_id: undefined as number | undefined,
  captain_id: undefined as number | undefined,
  member_ids: [] as number[],
});
async function load() {
  loading.value = true;
  error.value = null;
  try {
    items.value = (await api.teamRequests()).items;
    if (session.hasAny('team:create')) {
      orgs.value = (await api.orgs()).items;
      season.value = await api.season();
    }
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
}
watch(
  () => fields.org_id,
  async (id) => {
    members.value = [];
    fields.member_ids = [];
    fields.coach_id = undefined;
    fields.captain_id = undefined;
    if (id)
      try {
        members.value = (await api.orgMembers(id)).items;
      } catch (e) {
        error.value = e;
      }
  },
);
async function create() {
  if (!(await form.value?.validate().catch(() => false))) return;
  saving.value = true;
  error.value = null;
  try {
    const item = await api.createTeamRequest({
      request_kind: 'create',
      org_id: fields.org_id,
      team_code: fields.team_code,
      event_code: fields.event_code,
      registration_season_id: season.value?.id,
      proposal: {
        name: fields.name,
        coach_id: fields.coach_id ?? null,
        captain_id: fields.captain_id ?? null,
        members: fields.member_ids.map((user_id) => ({
          user_id,
          role: user_id === fields.captain_id ? 'captain' : 'member',
        })),
      },
    });
    items.value.unshift(item);
    showCreate.value = false;
    ElMessage.success(t('requestCreated'));
  } catch (e) {
    error.value = e;
  } finally {
    saving.value = false;
  }
}
async function submit(item: TeamRequest) {
  saving.value = true;
  error.value = null;
  try {
    await api.submitTeamRequest(item.id);
    await load();
  } catch (e) {
    error.value = e;
  } finally {
    saving.value = false;
  }
}
function canReview(item: TeamRequest) {
  return (
    item.status === 'submitted' &&
    item.submitted_by !== session.me?.user.id &&
    session.hasAny(item.request_kind === 'create' ? 'team:review_create' : 'team:review')
  );
}
async function review(item: TeamRequest, action: 'approve' | 'reject' | 'return') {
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
    await api.reviewTeamRequest(item.id, { action, comment: result.value || '' });
    await load();
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') error.value = e;
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('requests') }}</h1>
      <p>{{ t('emptyTeamsHint') }}</p>
    </div>
    <el-button
      v-if="session.hasAny('team:create')"
      type="primary"
      @click="showCreate = !showCreate"
      >{{ t('createTeam') }}</el-button
    >
  </div>
  <p class="mobile-note">{{ t('desktopHint') }}</p>
  <ErrorNotice :error="error" @retry="load" />
  <section v-if="showCreate" class="content-panel">
    <h2>{{ t('createTeam') }}</h2>
    <el-form
      ref="form"
      :model="fields"
      label-position="top"
      @submit.prevent="create"
      :scroll-to-error="true"
    >
      <div class="form-grid">
        <el-form-item
          prop="org_id"
          :label="t('org')"
          :rules="[{ required: true, message: t('required'), trigger: 'change' }]"
          ><el-select v-model="fields.org_id"
            ><el-option
              v-for="org in orgs"
              :key="org.id"
              :value="org.id"
              :label="org.name" /></el-select></el-form-item
        ><el-form-item
          prop="team_code"
          :label="t('teamCode')"
          :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
          ><el-input v-model="fields.team_code" name="team_code" :maxlength="32" /></el-form-item
        ><el-form-item
          prop="event_code"
          :label="t('event')"
          :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
          ><el-input v-model="fields.event_code" name="event_code" :maxlength="16" /></el-form-item
        ><el-form-item
          prop="name"
          :label="t('name')"
          :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
          ><el-input v-model="fields.name" name="name" :maxlength="128"
        /></el-form-item>
      </div>
      <el-form-item
        prop="member_ids"
        :label="t('members')"
        :rules="[
          { required: true, type: 'array', min: 1, message: t('required'), trigger: 'change' },
        ]"
        ><el-select v-model="fields.member_ids" multiple filterable
          ><el-option
            v-for="member in members.filter((m) => m.person_type === 'participant')"
            :key="member.user_id"
            :value="member.user_id"
            :label="member.real_name" /></el-select
      ></el-form-item>
      <div class="form-grid">
        <el-form-item :label="t('captain')"
          ><el-select v-model="fields.captain_id" clearable
            ><el-option
              v-for="member in members.filter((m) => fields.member_ids.includes(m.user_id))"
              :key="member.user_id"
              :value="member.user_id"
              :label="member.real_name" /></el-select></el-form-item
        ><el-form-item :label="t('coach')"
          ><el-select v-model="fields.coach_id" clearable
            ><el-option
              v-for="member in members.filter((m) => m.person_type === 'coach')"
              :key="member.user_id"
              :value="member.user_id"
              :label="member.real_name" /></el-select
        ></el-form-item>
      </div>
      <p>{{ t('season') }}: {{ season?.name || t('none') }}</p>
      <el-button type="primary" native-type="submit" :loading="saving" :disabled="!season">{{
        t('save')
      }}</el-button>
    </el-form>
  </section>
  <el-skeleton v-if="loading" :rows="6" animated /><el-empty
    v-else-if="!items.length && !error"
    :description="t('noPending')"
  />
  <article v-for="item in items" :key="item.id" class="content-panel">
    <div class="section-heading">
      <h2>{{ item.proposal.name }}</h2>
      <StatusTag :status="item.status" />
    </div>
    <p class="muted">{{ t('members') }}: {{ item.proposal.members.length }}</p>
    <p v-if="item.comment">{{ item.comment }}</p>
    <div class="actions">
      <el-button
        v-if="item.status === 'draft' && item.submitted_by === session.me?.user.id"
        type="primary"
        :loading="saving"
        @click="submit(item)"
        >{{ t('requestSubmit') }}</el-button><template v-if="canReview(item)"
        ><el-button type="primary" :loading="saving" @click="review(item, 'approve')">{{
          t('approve')
        }}</el-button
        ><el-button @click="review(item, 'return')">{{ t('return') }}</el-button
        ><el-button type="danger" plain @click="review(item, 'reject')">{{
          t('reject')
        }}</el-button></template
      >
    </div>
  </article>
</template>
