<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessageBox } from 'element-plus';
import { Plus } from '@element-plus/icons-vue';
import { api } from '../api';
import type { ManagedSeason } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { useSession } from '../stores/session';

const { t } = useI18n();
const session = useSession();
const items = ref<ManagedSeason[]>([]);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const loading = ref(true);
const busy = ref(false);
const open = ref(false);
const editOpen = ref(false);
const editing = ref<ManagedSeason>();
const editForm = reactive({ name: '', start_date: '', end_date: '' });
const updated = ref('');
const feedback = ref('');
const loadError = ref<unknown>(null);
const actionError = ref<unknown>(null);
const dateError = ref(false);
const endInput = ref<{ focus: () => void }>();
const form = reactive({ code: '', name: '', start_date: '', end_date: '' });

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    const data = await api.managedSeasons(page.value);
    items.value = data.items;
    pageSize.value = data.page_size;
    total.value = data.total;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function startDraft() {
  Object.assign(form, { code: '', name: '', start_date: '', end_date: '' });
  actionError.value = null;
  dateError.value = false;
  open.value = true;
}

async function apply(action: () => Promise<ManagedSeason>) {
  if (busy.value) return;
  busy.value = true;
  updated.value = '';
  actionError.value = null;
  try {
    const result = await action();
    updated.value = result.name;
    open.value = false;
    editOpen.value = false;
    await load();
  } catch (error) {
    actionError.value = error;
  } finally {
    busy.value = false;
  }
}

async function createDraft() {
  if (form.start_date > form.end_date) {
    dateError.value = true;
    endInput.value?.focus();
    return;
  }
  await apply(async () => {
    const result = await api.createSeason(form);
    page.value = 1;
    return result;
  });
}

async function setCurrent(item: ManagedSeason) {
  try {
    await ElMessageBox.confirm(
      t('seasonSwitchConfirm', { name: item.name }),
      t('seasonSetCurrent'),
      {
        confirmButtonText: t('seasonSetCurrent'),
        cancelButtonText: t('cancel'),
        type: 'warning',
      },
    );
  } catch {
    return;
  }
  await apply(() => api.setCurrentSeason(item.id));
}

function startEdit(item: ManagedSeason) {
  editing.value = item;
  Object.assign(editForm, {
    name: item.name,
    start_date: item.start_date,
    end_date: item.end_date,
  });
  actionError.value = null;
  dateError.value = false;
  editOpen.value = true;
}

async function saveEdit() {
  if (!editing.value || busy.value) return;
  if (editForm.start_date > editForm.end_date) {
    dateError.value = true;
    return;
  }
  const target = editing.value;
  await apply(async () => {
    const body: Record<string, string> = {};
    if (editForm.name !== target.name) body.name = editForm.name;
    if (editForm.start_date !== target.start_date) body.start_date = editForm.start_date;
    if (editForm.end_date !== target.end_date) body.end_date = editForm.end_date;
    return api.updateSeason(target.id, body);
  });
}

async function archive(item: ManagedSeason) {
  try {
    await ElMessageBox.confirm(t('seasonArchiveConfirm', { name: item.name }), t('seasonArchive'), {
      confirmButtonText: t('seasonArchive'),
      cancelButtonText: t('cancel'),
      type: 'warning',
    });
  } catch {
    return;
  }
  await apply(() => api.archiveSeason(item.id));
  updated.value = '';
  feedback.value = t('seasonArchived', { name: item.name });
}

onMounted(load);
</script>

<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('seasonManagement') }}</h1>
      <p>{{ t('seasonManagementHint') }}</p>
    </div>
    <el-button
      v-if="session.hasAny('season:create')"
      type="primary"
      :icon="Plus"
      :disabled="busy"
      @click="startDraft"
      >{{ t('seasonCreate') }}</el-button
    >
  </div>
  <div role="status">
    <p v-if="updated">{{ t('seasonSaved', { name: updated }) }}</p>
    <p v-if="feedback">{{ feedback }}</p>
  </div>
  <ErrorNotice v-if="!open && actionError" :error="actionError" />
  <div class="content-panel">
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <p v-else-if="!items.length" class="muted">{{ t('none') }}</p>
    <ul v-else class="season-list">
      <li v-for="item in items" :key="item.id" class="season-row">
        <div>
          <h2>{{ item.name }}</h2>
          <p class="small muted">{{ item.code }}</p>
          <p class="small muted">
            {{ t('seasonDateRange', { start: item.start_date, end: item.end_date }) }}
          </p>
        </div>
        <div class="season-actions">
          <StatusTag :status="item.status" />
          <el-tag v-if="item.is_default" type="primary">{{ t('seasonCurrentBadge') }}</el-tag>
          <el-button
            v-if="item.status === 'draft' && session.hasAny('season:activate')"
            :disabled="busy"
            @click="apply(() => api.activateSeason(item.id))"
            >{{ t('seasonActivate') }}</el-button
          >
          <el-button
            v-if="
              item.status === 'active' && !item.is_default && session.hasAny('season:set_current')
            "
            :disabled="busy"
            @click="setCurrent(item)"
            >{{ t('seasonSetCurrent') }}</el-button
          >
          <el-button
            v-if="item.status !== 'archived' && session.hasAny('season:update')"
            :disabled="busy"
            @click="startEdit(item)"
            >{{ t('seasonEdit') }}</el-button
          >
          <el-button
            v-if="item.status === 'active' && !item.is_default && session.hasAny('season:archive')"
            :disabled="busy"
            @click="archive(item)"
            >{{ t('seasonArchive') }}</el-button
          >
        </div>
      </li>
    </ul>
  </div>
  <el-pagination
    v-if="total > pageSize"
    :current-page="page"
    :page-size="pageSize"
    :total="total"
    :disabled="loading || busy"
    :pager-count="5"
    layout="prev, pager, next"
    @update:current-page="
      (value: number) => {
        page = value;
        load();
      }
    "
  />
  <el-dialog
    v-model="open"
    :title="t('seasonCreate')"
    width="min(560px, calc(100% - 32px))"
    :show-close="!busy"
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
  >
    <ErrorNotice v-if="actionError" :error="actionError" />
    <el-form label-position="top" @submit.prevent="createDraft">
      <el-form-item :label="t('seasonCode')" required>
        <el-input
          v-model.trim="form.code"
          :disabled="busy"
          :maxlength="32"
          pattern="[A-Z0-9][A-Z0-9\-]{0,31}"
          required
          aria-describedby="season-code-hint"
        />
        <span id="season-code-hint" class="small muted">{{ t('seasonCodeHint') }}</span>
      </el-form-item>
      <el-form-item :label="t('seasonName')" required>
        <el-input v-model.trim="form.name" :disabled="busy" :maxlength="64" required />
      </el-form-item>
      <el-form-item :label="t('seasonStart')" required>
        <el-input
          v-model="form.start_date"
          :disabled="busy"
          type="date"
          required
          @input="dateError = false"
        />
      </el-form-item>
      <el-form-item
        :label="t('seasonEnd')"
        required
        :error="dateError ? t('seasonDatesInvalid') : ''"
      >
        <el-input
          ref="endInput"
          v-model="form.end_date"
          :disabled="busy"
          type="date"
          required
          @input="dateError = false"
        />
      </el-form-item>
      <div class="season-actions">
        <el-button :disabled="busy" @click="open = false">{{ t('cancel') }}</el-button>
        <el-button type="primary" native-type="submit" :loading="busy">{{ t('save') }}</el-button>
      </div>
    </el-form>
  </el-dialog>
  <el-dialog
    v-model="editOpen"
    :title="t('seasonEdit')"
    width="min(560px, calc(100% - 32px))"
    :show-close="!busy"
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
  >
    <ErrorNotice v-if="actionError" :error="actionError" />
    <el-form label-position="top" @submit.prevent="saveEdit">
      <el-form-item :label="t('seasonCode')">
        <el-input :model-value="editing?.code ?? ''" disabled />
      </el-form-item>
      <el-form-item :label="t('seasonName')" required>
        <el-input v-model.trim="editForm.name" :disabled="busy" :maxlength="64" required />
      </el-form-item>
      <el-form-item :label="t('seasonStart')" required>
        <el-input
          v-model="editForm.start_date"
          :disabled="busy"
          type="date"
          required
          @input="dateError = false"
        />
      </el-form-item>
      <el-form-item
        :label="t('seasonEnd')"
        required
        :error="dateError ? t('seasonDatesInvalid') : ''"
      >
        <el-input
          v-model="editForm.end_date"
          :disabled="busy"
          type="date"
          required
          @input="dateError = false"
        />
      </el-form-item>
      <div class="season-actions">
        <el-button :disabled="busy" @click="editOpen = false">{{ t('cancel') }}</el-button>
        <el-button type="primary" native-type="submit" :loading="busy">{{ t('save') }}</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.season-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.season-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px 20px;
  flex-wrap: wrap;
  padding-block: 12px;
  overflow-wrap: anywhere;
}
.season-row + .season-row {
  border-block-start: 1px solid var(--color-border);
}
.season-row h2,
.season-row p {
  margin: 0;
}
.season-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}
.season-actions .el-button + .el-button {
  margin-inline-start: 0;
}
</style>
