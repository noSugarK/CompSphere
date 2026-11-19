<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessageBox } from 'element-plus';
import { Plus } from '@element-plus/icons-vue';
import { api } from '../api';
import type { EventTypeSummary, ManagedEdition, ManagedEvent } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import GroupConfiguration from '../components/GroupConfiguration.vue';
import OfferingMatrix from '../components/OfferingMatrix.vue';
import EditionPublicationPanel from '../components/EditionPublicationPanel.vue';
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
const editingId = ref<number>();
const loadError = ref<unknown>(null);
const typeError = ref<unknown>(null);
const saveError = ref<unknown>(null);
const rangeError = ref(false);
const feedback = ref('');
const matrixRevision = ref(0);
const publicationRevision = ref(0);
const blank = {
  event_code: '',
  name: '',
  min_members: '1',
  max_members: '3',
  coach_required: true,
};
const form = reactive({ ...blank });
const hasEventGrant = (permission: string) =>
  Boolean(
    edition.value &&
    hasEditionPermission(session.me, permission, editionId, edition.value.competition_id),
  );
const mayCreate = computed(
  () => edition.value?.status === 'draft' && hasEventGrant('event:create'),
);
const mayEdit = computed(() => edition.value?.status === 'draft' && hasEventGrant('event:update'));
const mayToggle = computed(
  () => edition.value?.status !== 'closed' && hasEventGrant('event:enable_disable'),
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

function startDraft(item?: ManagedEvent) {
  editingId.value = item?.id;
  Object.assign(
    form,
    item
      ? {
          event_code: item.event_code,
          name: item.name,
          min_members: String(item.min_members),
          max_members: String(item.max_members),
          coach_required: item.coach_required,
        }
      : blank,
  );
  rangeError.value = false;
  saveError.value = null;
  feedback.value = '';
  open.value = true;
  if (!item) void loadTypes();
}

async function saveEvent() {
  if (saving.value) return;
  const min = Number(form.min_members);
  const max = Number(form.max_members);
  rangeError.value = min > max;
  if (rangeError.value) return;
  const body = {
    name: form.name,
    min_members: min,
    max_members: max,
    coach_required: form.coach_required,
  };
  const id = editingId.value;
  await applyEventChange(async () => {
    const result = id
      ? await api.updateEditionEvent(id, body)
      : await api.createEditionEvent(editionId, { ...body, event_code: form.event_code });
    configurationChanged();
    open.value = false;
    return t(id ? 'eventSaved' : 'eventAdded', { name: result.name });
  });
}

async function applyEventChange(action: () => Promise<string>) {
  if (saving.value) return;
  saving.value = true;
  saveError.value = null;
  feedback.value = '';
  try {
    feedback.value = await action();
    await load();
  } catch (error) {
    saveError.value = error;
  } finally {
    saving.value = false;
  }
}

async function changeEvent(item: ManagedEvent, action: 'enable' | 'disable' | 'remove') {
  if (saving.value) return;
  if (action !== 'enable') {
    try {
      const label = t(action === 'remove' ? 'eventRemove' : 'eventDisable');
      await ElMessageBox.confirm(
        t(action === 'remove' ? 'eventRemoveConfirm' : 'eventDisableConfirm', { name: item.name }),
        label,
        {
          type: 'warning',
          cancelButtonText: t('cancel'),
          confirmButtonText: label,
        },
      );
    } catch {
      return;
    }
  }
  await applyEventChange(async () => {
    if (action === 'remove') {
      await api.deleteEditionEvent(item.id);
      page.value = 1;
    } else {
      await api.setEditionEventState(item.id, action);
    }
    configurationChanged();
    return t(action === 'remove' ? 'eventRemoved' : 'eventSaved', { name: item.name });
  });
}

function configurationChanged() {
  matrixRevision.value += 1;
  publicationRevision.value += 1;
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
    <p v-if="feedback">{{ feedback }}</p>
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
        @click="startDraft()"
        >{{ t('eventAdd') }}</el-button
      >
    </div>
    <ErrorNotice v-if="saveError && !open" :error="saveError" />
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
        <div class="event-actions">
          <StatusTag :status="item.status" />
          <template v-if="mayEdit">
            <el-button link type="primary" :disabled="saving" @click="startDraft(item)">{{
              t('eventEdit')
            }}</el-button>
            <el-button link :disabled="saving" @click="changeEvent(item, 'remove')">{{
              t('eventRemove')
            }}</el-button>
          </template>
          <el-button
            v-if="mayToggle"
            link
            :disabled="saving"
            @click="changeEvent(item, item.status === 'enabled' ? 'disable' : 'enable')"
            >{{ t(item.status === 'enabled' ? 'eventDisable' : 'eventEnable') }}</el-button
          >
        </div>
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
    @changed="configurationChanged"
  />
  <OfferingMatrix
    v-if="
      edition && hasEditionPermission(session.me, 'group:read', edition.id, edition.competition_id)
    "
    :key="matrixRevision"
    :edition="edition"
    @changed="publicationRevision += 1"
  />
  <EditionPublicationPanel
    v-if="edition"
    :edition="edition"
    :revision="publicationRevision"
    @published="edition = $event"
  />
  <el-dialog
    v-model="open"
    :title="t(editingId ? 'eventEdit' : 'eventAdd')"
    width="min(560px, calc(100% - 32px))"
    :show-close="!saving && !loadingTypes"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving && !loadingTypes"
  >
    <p v-if="!editingId && loadingTypes">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="!editingId && typeError" :error="typeError" @retry="loadTypes" />
    <p v-else-if="!editingId && !eventTypes.length" class="muted">{{ t('eventNoTypes') }}</p>
    <el-form v-else label-position="top" @submit.prevent="saveEvent">
      <ErrorNotice v-if="saveError" :error="saveError" />
      <el-form-item :label="t('eventType')" required>
        <el-input v-if="editingId" :model-value="form.event_code" readonly />
        <el-select v-else v-model="form.event_code" :disabled="saving">
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
