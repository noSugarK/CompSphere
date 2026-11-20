<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '../api';
import type {
  Award,
  AwardRecord,
  AwardRoster,
  ManagedEdition,
  ManagedEvent,
  ManagedGroup,
  ManagedOffering,
  Registration,
  RosterPublication,
} from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { useSession } from '../stores/session';
import { hasEditionPermission } from '../utils/permissions';
import { formatEventDateTime } from '../utils/format';

const { t } = useI18n();
const route = useRoute();
const session = useSession();
const editionId = Number(route.params.id);
// Element Plus 不接受 null 选项值：内部用 0 表示届次通用，仅 API 边界转 null。
const GENERAL = 0;
const edition = ref<ManagedEdition>();
const offerings = ref<ManagedOffering[]>([]);
const events = ref<ManagedEvent[]>([]);
const groups = ref<ManagedGroup[]>([]);
const awards = ref<Award[]>([]);
const rosters = ref<AwardRoster[]>([]);
const registrations = ref<Registration[]>([]);
const publication = ref<RosterPublication>();
const section = ref('awards');
const scope = ref<number>(GENERAL);
const loading = ref(true);
const loadError = ref<unknown>(null);
const saving = ref(false);
const feedback = ref('');
const blank = {
  offering_id: GENERAL,
  rank_level: 'first',
  name: '',
  quota: '',
  sort_order: '0',
};
const form = reactive({ ...blank });
const newEntry = reactive({
  registration_id: undefined as number | undefined,
  award_id: undefined as number | undefined,
});
const mode = ref<'open' | 'login' | 'none'>('open');
const fields = ref<string[]>([]);
const publishFields = ['team_code', 'org_name', 'member_names', 'event', 'group', 'award'] as const;

const scopeId = (value: number | null) => value ?? GENERAL;
const eventName = (id: number) => events.value.find((item) => item.id === id)?.name ?? `${id}`;
const groupName = (id: number) => groups.value.find((item) => item.id === id)?.name ?? `${id}`;

const grant = (permission: string) =>
  Boolean(
    edition.value &&
    hasEditionPermission(session.me, permission, editionId, edition.value.competition_id),
  );
const may = computed(() => grant('award:read'));
const mayConfigure = computed(() => grant('award:config') && edition.value?.status !== 'closed');
const mayManage = computed(
  () => grant('award:manage_roster') && edition.value?.status !== 'closed',
);
const mayPublish = computed(() => grant('roster:publish') && edition.value?.status !== 'closed');
const current = computed(() =>
  rosters.value.find((item) => scopeId(item.offering_id) === scope.value),
);
const mayDecide = computed(() => {
  const roster = current.value;
  if (!roster || roster.id === null || edition.value?.status === 'closed') return false;
  if (roster.status === 'editing') return grant('award:submit_roster');
  if (roster.status === 'under_approval') return grant('award:approve_roster');
  return grant('award:lock_roster');
});
const scopes = computed(() => [
  { id: GENERAL as number, label: t('rosterGeneral') },
  ...offerings.value
    .filter((item) => item.is_enabled)
    .map((item) => ({
      id: item.id,
      label: `${eventName(item.event_id)} · ${groupName(item.group_id)}`,
    })),
]);
const scopeLabel = computed(
  () => scopes.value.find((item) => item.id === scope.value)?.label ?? t('rosterGeneral'),
);
const scopeName = (offeringId: number | null) =>
  scopes.value.find((item) => item.id === scopeId(offeringId))?.label ??
  (offeringId === null ? t('awardScopeGeneral') : `${offeringId}`);
const awardsForScope = computed(() =>
  awards.value.filter((item) => scopeId(item.offering_id) === scope.value),
);
const awardedIds = computed(
  () => new Set((current.value?.records ?? []).map((item) => item.registration_id)),
);
const pickable = computed(() =>
  registrations.value.filter(
    (item) =>
      item.status === 'approved' &&
      item.approved_submission_no !== null &&
      item.approved_submission_no === item.current_submission_no &&
      (scope.value === GENERAL || item.offering_id === scope.value) &&
      !awardedIds.value.has(item.id),
  ),
);

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    edition.value = await api.managedEdition(editionId);
    const [state, offeringPage, eventPage, groupPage, awardPage, rosterRows] = await Promise.all([
      api.rosterPublication(editionId),
      api.editionOfferings(editionId, 1),
      api.editionEvents(editionId, 1, 100),
      api.editionGroups(editionId, 1, 100),
      api.listAwards(editionId),
      api.listRosters(editionId),
    ]);
    publication.value = state;
    mode.value = state.roster_publication;
    fields.value = state.roster_publish_fields;
    offerings.value = offeringPage.items;
    events.value = eventPage.items;
    groups.value = groupPage.items;
    awards.value = awardPage.items;
    rosters.value = rosterRows;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

async function loadCandidates() {
  if (registrations.value.length) return;
  try {
    const collected: Registration[] = [];
    // ponytail: cap candidate pages at 3 (300 rows); add a search picker if editions outgrow it.
    for (let page = 1; page <= 3; page += 1) {
      const result = await api.myRegistrations(editionId, page);
      collected.push(...result.items);
      if (collected.length >= result.total) break;
    }
    registrations.value = collected;
  } catch {
    registrations.value = [];
  }
}

async function createAward() {
  if (saving.value || !form.name.trim()) return;
  saving.value = true;
  try {
    await api.createAward(editionId, {
      offering_id: form.offering_id === GENERAL ? null : form.offering_id,
      rank_level: form.rank_level,
      name: form.name.trim(),
      quota: form.quota ? Number(form.quota) : null,
      sort_order: Number(form.sort_order) || 0,
    });
    awards.value = (await api.listAwards(editionId)).items;
    Object.assign(form, blank);
    feedback.value = t('eventAdded');
  } catch (error) {
    ElMessage.error(String(error instanceof Error ? error.message : error));
  } finally {
    saving.value = false;
  }
}

async function removeAward(item: Pick<Award, 'id' | 'name'>) {
  if (saving.value) return;
  try {
    await ElMessageBox.confirm(t('awardDeleteConfirm', { name: item.name }), t('awardDelete'), {
      type: 'warning',
    });
  } catch {
    return;
  }
  saving.value = true;
  try {
    await api.deleteAward(item.id);
    awards.value = (await api.listAwards(editionId)).items;
    rosters.value = await api.listRosters(editionId);
  } catch (error) {
    ElMessage.error(String(error instanceof Error ? error.message : error));
  } finally {
    saving.value = false;
  }
}

async function refresh() {
  rosters.value = await api.listRosters(editionId);
}

async function submitRecords(body: {
  add?: { registration_id: number; award_id: number }[];
  remove?: number[];
}) {
  if (saving.value || !current.value) return;
  saving.value = true;
  try {
    await api.changeRosterRecords(editionId, scope.value === GENERAL ? null : scope.value, {
      version: current.value.version,
      ...body,
    });
    await refresh();
    await loadCandidates();
    feedback.value = t('success');
  } catch (error) {
    ElMessage.error(String(error instanceof Error ? error.message : error));
    await refresh();
  } finally {
    saving.value = false;
  }
}

async function addEntry() {
  if (newEntry.registration_id && newEntry.award_id) {
    await submitRecords({
      add: [{ registration_id: newEntry.registration_id, award_id: newEntry.award_id }],
    });
    newEntry.registration_id = undefined;
    newEntry.award_id = undefined;
  }
}

async function decide(action: 'submit' | 'approve' | 'reject' | 'unlock') {
  const roster = current.value;
  if (!roster || roster.id === null || saving.value) return;
  let comment = '';
  if (action === 'reject' || action === 'unlock') {
    try {
      const prompt = await ElMessageBox.prompt(
        t(action === 'reject' ? 'rosterRejectPrompt' : 'rosterUnlockPrompt', {
          scope: scopeLabel.value,
        }),
        t(action === 'reject' ? 'rosterReject' : 'rosterUnlock'),
        {
          inputType: 'textarea',
          inputValidator: (value: string) => value.trim().length > 0 || t('required'),
        },
      );
      comment = prompt.value ?? '';
    } catch {
      return;
    }
  } else {
    try {
      await ElMessageBox.confirm(
        t(action === 'submit' ? 'rosterSubmitConfirm' : 'rosterApproveConfirm', {
          scope: scopeLabel.value,
        }),
        t(action === 'submit' ? 'rosterSubmit' : 'rosterApprove'),
        { type: 'warning' },
      );
    } catch {
      return;
    }
  }
  saving.value = true;
  try {
    const result = await api.decideRoster(
      editionId,
      scope.value === GENERAL ? null : scope.value,
      action,
      { version: roster.version, comment },
    );
    rosters.value = rosters.value.map((item) =>
      scopeId(item.offering_id) === scopeId(result.offering_id) ? result : item,
    );
    feedback.value = t('rosterDecisionDone', { status: t(result.status) });
  } catch (error) {
    ElMessage.error(String(error instanceof Error ? error.message : error));
    await refresh();
  } finally {
    saving.value = false;
  }
}

async function switchScope(value: number) {
  scope.value = value;
  feedback.value = '';
  await loadCandidates();
  await refresh();
}

async function savePublication() {
  if (saving.value) return;
  saving.value = true;
  try {
    publication.value = await api.setRosterPublication(editionId, {
      roster_publication: mode.value,
      roster_publish_fields: fields.value,
    });
    mode.value = publication.value.roster_publication;
    fields.value = publication.value.roster_publish_fields;
    feedback.value = t('success');
  } catch (error) {
    ElMessage.error(String(error instanceof Error ? error.message : error));
  } finally {
    saving.value = false;
  }
}

async function togglePublication(action: 'publish' | 'unpublish') {
  if (saving.value) return;
  try {
    await ElMessageBox.confirm(
      t(action === 'publish' ? 'publicationPublishConfirm' : 'publicationUnpublishConfirm'),
      t(action === 'publish' ? 'publicationPublish' : 'publicationUnpublish'),
      { type: 'warning' },
    );
  } catch {
    return;
  }
  saving.value = true;
  try {
    publication.value = await api.publishRoster(editionId, action);
    feedback.value = t('success');
  } catch (error) {
    ElMessage.error(String(error instanceof Error ? error.message : error));
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await load();
  if (edition.value) {
    scope.value = scopes.value[1]?.id ?? GENERAL;
    await loadCandidates();
  }
});
</script>

<template>
  <div class="page-heading">
    <div>
      <RouterLink :to="{ name: 'editionConfig', params: { id: editionId } }">{{
        t('editionConfiguration')
      }}</RouterLink>
      <h1 id="page-title" tabindex="-1">{{ edition?.name ?? t('awards') }}</h1>
      <p>{{ t('awardsHint') }}</p>
    </div>
  </div>
  <p v-if="loading" role="status">{{ t('loading') }}</p>
  <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
  <p v-else-if="!may" role="status">{{ t('noAccess') }}</p>
  <el-tabs v-else v-model="section" class="awards-sections">
    <el-tab-pane :label="t('awardsTab')" name="awards">
      <section class="content-panel">
        <h2>{{ t('awardsTab') }}</h2>
        <p v-if="!awards.length" class="muted">{{ t('none') }}</p>
        <el-table v-else :data="awards">
          <el-table-column :label="t('awardScope')"
            ><template #default="{ row }">{{
              scopeName((row as Award).offering_id)
            }}</template></el-table-column
          ><el-table-column prop="rank_level" :label="t('awardRank')"
            ><template #default="{ row }">{{
              t((row as Award).rank_level)
            }}</template></el-table-column
          ><el-table-column prop="name" :label="t('awardName')" /><el-table-column
            prop="quota"
            :label="t('awardQuota')"
          /><el-table-column prop="sort_order" :label="t('awardSort')" />
          <el-table-column v-if="mayConfigure" :label="t('status')"
            ><template #default="{ row }"
              ><el-button text :disabled="saving" @click="removeAward(row as Award)">{{
                t('awardDelete')
              }}</el-button></template
            ></el-table-column
          ></el-table
        >
        <el-form v-if="mayConfigure" class="award-form" @submit.prevent="createAward">
          <el-form-item :label="t('awardScope')"
            ><el-select v-model="form.offering_id" :disabled="saving"
              ><el-option
                v-for="item in scopes"
                :key="item.id"
                :value="item.id"
                :label="item.label" /></el-select></el-form-item
          ><el-form-item :label="t('awardRank')"
            ><el-select v-model="form.rank_level" :disabled="saving"
              ><el-option
                v-for="level in ['first', 'second', 'third', 'excellence', 'custom']"
                :key="level"
                :value="level"
                :label="t(level)" /></el-select></el-form-item
          ><el-form-item :label="t('awardName')"
            ><el-input v-model="form.name" maxlength="64" :disabled="saving" /></el-form-item
          ><el-form-item :label="t('awardQuota')"
            ><el-input
              v-model="form.quota"
              inputmode="numeric"
              :disabled="saving"
              class="quota-input" /></el-form-item
          ><el-form-item
            ><el-button type="primary" native-type="submit" :loading="saving">{{
              t('awardCreate')
            }}</el-button></el-form-item
          ></el-form
        >
      </section>
    </el-tab-pane>
    <el-tab-pane :label="t('rosterTab')" name="roster" lazy>
      <section class="content-panel">
        <div class="roster-head">
          <h2>{{ t('rosterTab') }}</h2>
          <el-select
            :model-value="scope"
            :disabled="saving"
            class="scope-select"
            @update:model-value="switchScope"
            ><el-option
              v-for="item in scopes"
              :key="String(item.id)"
              :value="item.id"
              :label="item.label"
          /></el-select>
          <StatusTag v-if="current" :status="current.status" />
          <span class="small muted">{{ t('rosterVersion') }} v{{ current?.version ?? 1 }}</span>
          <div class="actions">
            <el-button
              v-if="current?.status === 'editing' && mayDecide"
              type="primary"
              :loading="saving"
              @click="decide('submit')"
              >{{ t('rosterSubmit') }}</el-button><el-button
              v-if="current?.status === 'under_approval' && mayDecide"
              type="primary"
              :loading="saving"
              @click="decide('approve')"
              >{{ t('rosterApprove') }}</el-button
            ><el-button
              v-if="current?.status === 'under_approval' && mayDecide"
              :loading="saving"
              @click="decide('reject')"
              >{{ t('rosterReject') }}</el-button
            ><el-button
              v-if="current?.status === 'confirmed' && mayDecide"
              :loading="saving"
              @click="decide('unlock')"
              >{{ t('rosterUnlock') }}</el-button
            >
          </div>
        </div>
        <p role="status" v-if="feedback">{{ feedback }}</p>
        <p v-if="!current?.records.length" class="muted">{{ t('rosterEmpty') }}</p>
        <el-table v-else :data="current?.records">
          <el-table-column prop="batch_no" :label="t('reviewBatchNumber')" /><el-table-column
            prop="team_code"
            :label="t('teamCode')"
          /><el-table-column prop="org_name" :label="t('org')" /><el-table-column
            :label="t('members')"
            ><template #default="{ row }">{{
              (row as AwardRecord).member_names.join('、')
            }}</template></el-table-column
          ><el-table-column prop="award_name" :label="t('awardName')" />
          <el-table-column v-if="mayManage && current?.status === 'editing'" :label="t('status')"
            ><template #default="{ row }"
              ><el-button
                text
                :disabled="saving"
                @click="submitRecords({ remove: [(row as AwardRecord).registration_id] })"
                >{{ t('eventRemove') }}</el-button
              ></template
            ></el-table-column
          ></el-table
        >
        <div v-if="mayManage && current?.status === 'editing'" class="entry-row">
          <el-select
            v-model="newEntry.registration_id"
            :placeholder="t('rosterPickRegistration')"
            filterable
            :disabled="saving || !pickable.length"
            class="entry-select"
            ><el-option
              v-for="item in pickable"
              :key="item.id"
              :value="item.id"
              :label="`${item.batch_no}${item.team_id ? ` · ${item.enrollment_kind}` : ''}`" /></el-select
          ><el-select
            v-model="newEntry.award_id"
            :placeholder="t('rosterPickAward')"
            :disabled="saving || !awardsForScope.length"
            class="entry-select"
            ><el-option
              v-for="item in awardsForScope"
              :key="item.id"
              :value="item.id"
              :label="`${item.name} · ${t(item.rank_level)}`" /></el-select
          ><el-button type="primary" :disabled="saving" @click="addEntry">{{
            t('rosterAddEntry')
          }}</el-button>
        </div>
        <p
          v-if="mayManage && current?.status === 'editing' && !pickable.length"
          class="small muted"
        >
          {{ t('rosterNoApproved') }}
        </p>
      </section>
    </el-tab-pane>
    <el-tab-pane :label="t('rosterPublication')" name="publication" lazy>
      <section class="content-panel">
        <h2>{{ t('rosterPublication') }}</h2>
        <p role="status" v-if="feedback">{{ feedback }}</p>
        <p>
          {{ t('publicationState') }}：<StatusTag
            v-if="publication?.roster_published_at"
            status="approved"
          /><span v-else class="muted">{{ t('publicationNotPublished') }}</span>
          <template v-if="publication?.roster_published_at">
            ·
            {{
              t('publicationPublishedAt', {
                time: formatEventDateTime(publication.roster_published_at),
              })
            }}
          </template>
        </p>
        <el-form label-position="top" class="publication-form">
          <el-form-item :label="t('publicationMode')"
            ><el-radio-group v-model="mode" :disabled="saving || !mayPublish">
              <el-radio value="open">{{ t('publicationOpen') }}</el-radio>
              <el-radio value="login">{{ t('publicationLogin') }}</el-radio>
              <el-radio value="none">{{ t('publicationNone') }}</el-radio>
            </el-radio-group>
            <p class="small muted">{{ t('publicationModeHint') }}</p></el-form-item
          ><el-form-item :label="t('publicationFields')"
            ><el-checkbox-group v-model="fields" :disabled="saving || !mayPublish">
              <el-checkbox v-for="item in publishFields" :key="item" :value="item">{{
                t(item)
              }}</el-checkbox>
            </el-checkbox-group></el-form-item
          >
          <div class="actions">
            <el-button v-if="mayPublish" :loading="saving" @click="savePublication">{{
              t('save')
            }}</el-button>
            <el-button
              v-if="mayPublish && !publication?.roster_published_at"
              type="primary"
              :loading="saving"
              @click="togglePublication('publish')"
              >{{ t('publicationPublish') }}</el-button><el-button
              v-if="mayPublish && publication?.roster_published_at"
              :loading="saving"
              @click="togglePublication('unpublish')"
              >{{ t('publicationUnpublish') }}</el-button
            ><RouterLink
              class="primary-link"
              :to="{ name: 'publicRoster', params: { id: editionId } }"
              >{{ t('publicRoster') }}</RouterLink
            >
          </div>
        </el-form>
      </section>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped>
.awards-sections :deep(.el-tabs__item) {
  font-size: 13px;
}
.roster-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.roster-head h2 {
  margin-inline-end: auto;
}
.scope-select {
  max-inline-size: 220px;
}
.entry-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-block-start: 12px;
}
.entry-select {
  min-inline-size: 220px;
}
.award-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0 16px;
  margin-block-start: 16px;
}
.quota-input {
  max-inline-size: 96px;
}
.publication-form .actions {
  margin-block-start: 8px;
}
</style>
