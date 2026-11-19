<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { Plus } from '@element-plus/icons-vue';
import { api } from '../api';
import type { EventTypeSummary, ManagedEdition, ManagedEvent } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import GroupConfiguration from '../components/GroupConfiguration.vue';
import OfferingMatrix from '../components/OfferingMatrix.vue';
import StatusTag from '../components/StatusTag.vue';
import { useSession } from '../stores/session';
import { hasEditionPermission, mayViewCompetitionRegistry } from '../utils/permissions';

const { t } = useI18n();
const session = useSession();
const editionId = Number(useRoute().params.id);
const edition = ref<ManagedEdition>();
const events = ref<ManagedEvent[]>([]);
const eventTypes = ref<EventTypeSummary[]>([]);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const loading = ref(true);
const loadingTypes = ref(false);
const saving = ref(false);
const open = ref(false);
const loadError = ref<unknown>(null);
const typeError = ref<unknown>(null);
const saveError = ref<unknown>(null);
const rangeError = ref(false);
const created = ref('');
const matrixRevision = ref(0);
const blank = {
  event_code: '',
  name: '',
  min_members: '1',
  max_members: '3',
  coach_required: true,
};
const form = reactive({ ...blank });
const mayCreate = computed(
  () =>
    edition.value?.status === 'draft' &&
    hasEditionPermission(session.me, 'event:create', editionId, edition.value.competition_id),
);

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    edition.value ??= await api.managedEdition(editionId);
    const result = await api.editionEvents(editionId, page.value);
    events.value = result.items;
    pageSize.value = result.page_size;
    total.value = result.total;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

async function loadTypes() {
  loadingTypes.value = true;
  typeError.value = null;
  eventTypes.value = [];
  try {
    const first = await api.editionEventTypes(editionId);
    const items = [...first.items];
    for (let index = 2; index <= Math.ceil(first.total / first.page_size); index += 1) {
      items.push(...(await api.editionEventTypes(editionId, index)).items);
    }
    eventTypes.value = items;
  } catch (error) {
    typeError.value = error;
  } finally {
    loadingTypes.value = false;
  }
}

function startDraft() {
  Object.assign(form, blank);
  rangeError.value = false;
  saveError.value = null;
  created.value = '';
  open.value = true;
  void loadTypes();
}

async function saveEvent() {
  if (saving.value) return;
  const min = Number(form.min_members);
  const max = Number(form.max_members);
  rangeError.value = min > max;
  if (rangeError.value) return;
  saving.value = true;
  saveError.value = null;
  try {
    const result = await api.createEditionEvent(editionId, {
      ...form,
      min_members: min,
      max_members: max,
    });
    created.value = result.name;
    matrixRevision.value += 1;
    open.value = false;
    await load();
  } catch (error) {
    saveError.value = error;
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-heading">
    <div>
      <RouterLink
        v-if="edition && mayViewCompetitionRegistry(session.me)"
        :to="{ name: 'editionRegistry', params: { id: edition.competition_id } }"
        >{{ t('editionRegistry') }}</RouterLink
      >
      <h1 id="page-title" tabindex="-1">{{ t('editionConfiguration') }}</h1>
      <p v-if="edition">{{ edition.name }} <StatusTag :status="edition.status" /></p>
    </div>
  </div>
  <div role="status">
    <p v-if="created">{{ t('eventAdded', { name: created }) }}</p>
  </div>
  <div class="content-panel">
    <div class="event-heading">
      <div>
        <h2>{{ t('eventSettings') }}</h2>
        <p v-if="edition && edition.status !== 'draft'" class="muted">
          {{ t('eventPublishedReadOnly') }}
        </p>
        <p v-else class="muted">{{ t('eventSettingsHint') }}</p>
      </div>
      <el-button
        v-if="mayCreate"
        :icon="Plus"
        type="primary"
        :disabled="saving"
        @click="startDraft"
        >{{ t('eventAdd') }}</el-button
      >
    </div>
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <p v-else-if="!events.length" class="muted">{{ t('none') }}</p>
    <ul v-else class="event-list">
      <li v-for="item in events" :key="item.id" class="event-row">
        <div>
          <h3>{{ item.name }}</h3>
          <p class="small muted">{{ item.event_code }}</p>
        </div>
        <div>
          <p>{{ t('eventMemberRange', { min: item.min_members, max: item.max_members }) }}</p>
          <p v-if="item.coach_required" class="small muted">{{ t('eventCoachRequired') }}</p>
        </div>
        <StatusTag :status="item.status" />
      </li>
    </ul>
    <el-pagination
      v-if="total > pageSize"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      :disabled="loading || saving"
      :pager-count="5"
      layout="prev, pager, next"
      @update:current-page="
        (value: number) => {
          page = value;
          load();
        }
      "
    />
  </div>
  <GroupConfiguration
    v-if="
      edition && hasEditionPermission(session.me, 'group:read', edition.id, edition.competition_id)
    "
    :edition="edition"
    @changed="matrixRevision += 1"
  />
  <OfferingMatrix
    v-if="
      edition && hasEditionPermission(session.me, 'group:read', edition.id, edition.competition_id)
    "
    :key="matrixRevision"
    :edition="edition"
  />
  <el-dialog
    v-model="open"
    :title="t('eventAdd')"
    width="min(560px, calc(100% - 32px))"
    :show-close="!saving && !loadingTypes"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving && !loadingTypes"
  >
    <p v-if="loadingTypes">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="typeError" :error="typeError" @retry="loadTypes" />
    <p v-else-if="!eventTypes.length" class="muted">{{ t('eventNoTypes') }}</p>
    <el-form v-else label-position="top" @submit.prevent="saveEvent">
      <ErrorNotice v-if="saveError" :error="saveError" />
      <el-form-item :label="t('eventType')" required>
        <el-select v-model="form.event_code" :disabled="saving">
          <el-option
            v-for="eventType in eventTypes"
            :key="eventType.code"
            :label="`${eventType.code} · ${eventType.name}`"
            :value="eventType.code"
          />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('eventName')" required>
        <el-input v-model.trim="form.name" :disabled="saving" maxlength="64" required />
      </el-form-item>
      <div class="event-fields">
        <el-form-item :label="t('eventMinMembers')" required>
          <el-input
            v-model="form.min_members"
            :disabled="saving"
            type="number"
            min="1"
            max="2147483647"
            required
            @input="rangeError = false"
          />
        </el-form-item>
        <el-form-item
          :label="t('eventMaxMembers')"
          required
          :error="rangeError ? t('eventRangeInvalid') : ''"
        >
          <el-input
            v-model="form.max_members"
            :disabled="saving"
            type="number"
            min="1"
            max="2147483647"
            required
            @input="rangeError = false"
          />
        </el-form-item>
      </div>
      <el-checkbox v-model="form.coach_required" :disabled="saving">{{
        t('eventCoachRequired')
      }}</el-checkbox>
      <div class="event-actions">
        <el-button :disabled="saving" @click="open = false">{{ t('cancel') }}</el-button>
        <el-button
          type="primary"
          native-type="submit"
          :disabled="!form.event_code"
          :loading="saving"
          >{{ t('save') }}</el-button
        >
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.event-heading,
.event-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.event-heading {
  margin-block-end: 16px;
}
.event-heading h2,
.event-heading p,
.event-row h3,
.event-row p {
  margin: 0;
}
.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.event-row {
  padding-block: 12px;
  border-block-start: 1px solid var(--color-border);
  overflow-wrap: anywhere;
}
.event-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.event-actions {
  display: flex;
  justify-content: flex-end;
  margin-block-start: 12px;
}
@media (max-width: 480px) {
  .event-fields {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }
}
</style>
