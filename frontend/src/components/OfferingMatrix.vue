<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessageBox } from 'element-plus';
import { api } from '../api';
import type { ManagedEdition, ManagedEvent, ManagedGroup, ManagedOffering } from '../api/schemas';
import { useSession } from '../stores/session';
import { formatEventDateTime } from '../utils/format';
import { hasEditionPermission } from '../utils/permissions';
import ErrorNotice from './ErrorNotice.vue';

const props = defineProps<{ edition: ManagedEdition }>();
const emit = defineEmits<{ changed: [] }>();
const { t } = useI18n();
const session = useSession();
const events = ref<ManagedEvent[]>([]);
const groups = ref<ManagedGroup[]>([]);
const offerings = ref<ManagedOffering[]>([]);
const loading = ref(false);
const busy = ref(false);
const loadError = ref<unknown>(null);
const actionError = ref<unknown>(null);
const feedback = ref('');
const editor = ref<{ item: ManagedOffering; event: ManagedEvent; group: ManagedGroup }>();
const editorOpen = ref(false);
const editError = ref<unknown>(null);
const dateFields = [
  ['enroll_start', 'editionEnrollStart'],
  ['enroll_end', 'editionEnrollEnd'],
] as const;
const rules = ref({ enroll_start: '', enroll_end: '', quota: '' });
const localInput = (value: string | null) =>
  value ? formatEventDateTime(value).replace(' ', 'T') : '';
const editable = computed(
  () =>
    props.edition.status !== 'closed' &&
    hasEditionPermission(
      session.me,
      'edition:update',
      props.edition.id,
      props.edition.competition_id,
    ),
);
const draftWritable = computed(() => editable.value && props.edition.status === 'draft');
const matrix = computed(() => {
  const byPair = new Map(
    offerings.value.map((item) => [`${item.event_id}:${item.group_id}`, item]),
  );
  return events.value.map((event) => ({
    event,
    cells: groups.value.map((group) => ({
      group,
      offering: byPair.get(`${event.id}:${group.id}`),
      prerequisitesEnabled: event.status === 'enabled' && group.status === 'enabled',
    })),
  }));
});

async function allPages<Item>(
  fetchPage: (page: number) => Promise<{ items: Item[]; total: number; page_size: number }>,
) {
  const first = await fetchPage(1);
  const result = [...first.items];
  const pages = Math.ceil(first.total / first.page_size);
  for (let index = 2; index <= pages; index += 1) {
    result.push(...(await fetchPage(index)).items);
  }
  return result;
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    [events.value, groups.value, offerings.value] = await Promise.all([
      allPages((page) => api.editionEvents(props.edition.id, page, 100)),
      allPages((page) => api.editionGroups(props.edition.id, page, 100)),
      allPages((page) => api.editionOfferings(props.edition.id, page)),
    ]);
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

type OfferingAction = 'add' | 'enable' | 'disable' | 'remove' | 'edit';
function actionText(action: OfferingAction, event: ManagedEvent, group: ManagedGroup) {
  return { action: t(`offerings.${action}`), event: event.name, group: group.name };
}

async function change(
  action: Exclude<OfferingAction, 'edit'>,
  event: ManagedEvent,
  group: ManagedGroup,
  item?: ManagedOffering,
) {
  if (busy.value || (action !== 'add' && !item)) return;
  const labels = actionText(action, event, group);
  if (action === 'disable' || action === 'remove') {
    try {
      await ElMessageBox.confirm(t('offerings.confirmation', labels), labels.action, {
        type: 'warning',
        cancelButtonText: t('cancel'),
        confirmButtonText: labels.action,
      });
    } catch {
      return;
    }
  }
  busy.value = true;
  actionError.value = null;
  feedback.value = '';
  try {
    if (action === 'add') {
      offerings.value.push(
        await api.createOffering(props.edition.id, { event_id: event.id, group_id: group.id }),
      );
    } else if (item) {
      if (action === 'remove') {
        await api.deleteOffering(item.id);
        offerings.value = offerings.value.filter((existing) => existing.id !== item.id);
      } else {
        const updated = await api.setOfferingState(item.id, action);
        offerings.value = offerings.value.map((existing) =>
          existing.id === updated.id ? updated : existing,
        );
      }
    }
    feedback.value = t('offerings.saved', labels);
    emit('changed');
  } catch (error) {
    actionError.value = error;
  } finally {
    busy.value = false;
  }
}

function edit(item: ManagedOffering, event: ManagedEvent, group: ManagedGroup) {
  editor.value = { item, event, group };
  rules.value = {
    enroll_start: localInput(item.enroll_start),
    enroll_end: localInput(item.enroll_end),
    quota: item.quota?.toString() ?? '',
  };
  editError.value = null;
  editorOpen.value = true;
}

async function saveRules() {
  if (!editor.value || busy.value) return;
  const { item, event, group } = editor.value;
  const quota = rules.value.quota === '' ? null : Number(rules.value.quota);
  const changes = {
    ...(rules.value.enroll_start !== localInput(item.enroll_start) && {
      enroll_start: rules.value.enroll_start || null,
    }),
    ...(rules.value.enroll_end !== localInput(item.enroll_end) && {
      enroll_end: rules.value.enroll_end || null,
    }),
    ...(quota !== item.quota && { quota }),
  };
  if (!Object.keys(changes).length) {
    editorOpen.value = false;
    return;
  }
  busy.value = true;
  editError.value = null;
  try {
    const updated = await api.updateOffering(item.id, { ...changes, time_zone: 'Asia/Shanghai' });
    offerings.value = offerings.value.map((existing) =>
      existing.id === updated.id ? updated : existing,
    );
    editorOpen.value = false;
    feedback.value = t('offerings.saved', actionText('edit', event, group));
    emit('changed');
  } catch (error) {
    editError.value = error;
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="content-panel" aria-labelledby="offering-title">
    <h2 id="offering-title">{{ t('offerings.title') }}</h2>
    <p class="muted">{{ t('offerings.hint') }}</p>
    <div role="status">
      <p v-if="feedback">{{ feedback }}</p>
    </div>
    <ErrorNotice v-if="actionError" :error="actionError" />
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <p v-else-if="!events.length || !groups.length" class="muted">
      {{ t('offerings.prerequisites') }}
    </p>
    <div v-else class="matrix-scroll" tabindex="0" role="region" aria-labelledby="offering-title">
      <table class="offering-matrix" :aria-label="t('offerings.title')">
        <thead>
          <tr>
            <th scope="col">{{ t('event') }}</th>
            <th v-for="group in groups" :key="group.id" scope="col">
              {{ group.name }}<span class="small muted">{{ group.code }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in matrix" :key="row.event.id">
            <th scope="row">
              {{ row.event.name }}<span class="small muted">{{ row.event.event_code }}</span>
            </th>
            <td v-for="cell in row.cells" :key="cell.group.id">
              <template v-if="cell.offering">
                <el-tag v-if="cell.offering.is_enabled" type="success" effect="light">{{
                  t('enabled')
                }}</el-tag>
                <span v-else class="small muted">{{
                  t(cell.offering.status === 'disabled' ? 'disabled' : 'offerings.blocked')
                }}</span>
                <p
                  v-if="cell.offering.enroll_start || cell.offering.enroll_end"
                  class="small muted"
                >
                  {{
                    t('offerings.registrationWindow', {
                      start: formatEventDateTime(
                        cell.offering.enroll_start ?? edition.enroll_start,
                      ),
                      end: formatEventDateTime(cell.offering.enroll_end ?? edition.enroll_end),
                    })
                  }}
                </p>
                <p v-if="cell.offering.quota !== null" class="small muted">
                  {{ t('offerings.quotaValue', { quota: cell.offering.quota }) }}
                </p>
                <div v-if="editable" class="matrix-actions">
                  <el-button
                    v-if="draftWritable"
                    link
                    type="primary"
                    :disabled="busy"
                    :aria-label="
                      t('offerings.actionName', actionText('edit', row.event, cell.group))
                    "
                    @click="edit(cell.offering, row.event, cell.group)"
                    >{{ t('offerings.edit') }}</el-button
                  >
                  <el-button
                    v-if="cell.offering.status === 'enabled'"
                    link
                    :disabled="busy"
                    :aria-label="
                      t('offerings.actionName', actionText('disable', row.event, cell.group))
                    "
                    @click="change('disable', row.event, cell.group, cell.offering)"
                    >{{ t('offerings.disable') }}</el-button
                  >
                  <el-button
                    v-else-if="cell.prerequisitesEnabled"
                    link
                    type="primary"
                    :disabled="busy"
                    :aria-label="
                      t('offerings.actionName', actionText('enable', row.event, cell.group))
                    "
                    @click="change('enable', row.event, cell.group, cell.offering)"
                    >{{ t('offerings.enable') }}</el-button
                  >
                  <el-button
                    v-if="draftWritable"
                    link
                    :disabled="busy"
                    :aria-label="
                      t('offerings.actionName', actionText('remove', row.event, cell.group))
                    "
                    @click="change('remove', row.event, cell.group, cell.offering)"
                    >{{ t('offerings.remove') }}</el-button
                  >
                </div>
              </template>
              <template v-else>
                <span class="small muted">{{ t('offerings.notConfigured') }}</span>
                <div v-if="draftWritable && cell.prerequisitesEnabled" class="matrix-actions">
                  <el-button
                    link
                    type="primary"
                    :disabled="busy"
                    :aria-label="
                      t('offerings.actionName', actionText('add', row.event, cell.group))
                    "
                    @click="change('add', row.event, cell.group)"
                    >{{ t('offerings.add') }}</el-button
                  >
                </div>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
  <el-dialog
    v-if="editor"
    v-model="editorOpen"
    :title="t('offerings.actionName', actionText('edit', editor.event, editor.group))"
    width="min(560px, calc(100% - 32px))"
    :show-close="!busy"
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
  >
    <p class="muted">{{ t('offerings.overrideHint') }}</p>
    <el-form label-position="top" @submit.prevent="saveRules">
      <ErrorNotice v-if="editError" :error="editError" />
      <el-form-item v-for="[field, label] in dateFields" :key="field" :label="t(label)">
        <el-input v-model="rules[field]" type="datetime-local" :disabled="busy" />
        <div class="small muted">
          {{ t('offerings.inherits', { date: formatEventDateTime(edition[field]) }) }}
        </div>
      </el-form-item>
      <el-form-item :label="t('offerings.quota')">
        <el-input
          v-model="rules.quota"
          type="number"
          min="0"
          max="2147483647"
          step="1"
          :disabled="busy"
        />
        <div class="small muted">{{ t('offerings.quotaHint') }}</div>
      </el-form-item>
      <el-button :disabled="busy" @click="editorOpen = false">{{ t('cancel') }}</el-button>
      <el-button type="primary" native-type="submit" :loading="busy">{{ t('save') }}</el-button>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.matrix-scroll {
  max-inline-size: 100%;
  overflow: auto;
}
.offering-matrix {
  border-collapse: separate;
  border-spacing: 0;
  inline-size: 100%;
}
.offering-matrix th,
.offering-matrix td {
  padding: 10px 12px;
  min-inline-size: 8rem;
  max-inline-size: 15rem;
  text-align: start;
  overflow-wrap: anywhere;
  border-block-end: 1px solid var(--color-border);
}
.offering-matrix th {
  background: var(--color-soft);
}
.offering-matrix tr > th:first-child {
  position: sticky;
  inset-inline-start: 0;
  z-index: 1;
}
.offering-matrix th span {
  display: block;
  font-weight: 400;
}
.matrix-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  margin-block-start: 8px;
}
.matrix-actions .el-button + .el-button {
  margin-inline-start: 0;
}
</style>
