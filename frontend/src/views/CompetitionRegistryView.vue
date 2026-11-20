<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Plus } from '@element-plus/icons-vue';
import { ElMessageBox } from 'element-plus';
import { api } from '../api';
import type { ManagedCompetition, ManagedCompetitionDetail } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { useSession } from '../stores/session';
import {
  hasCompetitionPermission,
  mayCreateCompetition,
  mayUnarchiveCompetition,
} from '../utils/permissions';

const { t } = useI18n();
const session = useSession();
const items = ref<ManagedCompetition[]>([]);
const page = ref(1);
const size = ref(20);
const total = ref(0);
const loading = ref(true);
const loadError = ref<unknown>(null);
const open = ref(false);
const saving = ref(false);
const saveError = ref<unknown>(null);
const nameError = ref(false);
const nameInput = ref<{ focus: () => void }>();
const created = ref('');
const publishedName = ref('');
const publishingId = ref<number>();
const publishError = ref<unknown>(null);
const editOpen = ref(false);
const editingId = ref<number>();
const editLoading = ref(false);
const editSaving = ref(false);
const editError = ref<unknown>(null);
const editForm = reactive({ name: '', summary: '', category: '', level: '' });
const archivedName = ref('');
const restoredName = ref('');
const editSavedName = ref('');
const archiveBusy = ref<number>();
const form = reactive({ name: '', summary: '' });
const categoryOptions = [
  ['subject', 'categorySubject'],
  ['technology', 'categoryTechnology'],
  ['entrepreneurship', 'categoryEntrepreneurship'],
  ['sports', 'categorySports'],
  ['arts', 'categoryArts'],
  ['other', 'categoryOther'],
] as const;
const levelOptions = [
  ['school', 'levelSchool'],
  ['province', 'levelProvince'],
  ['national', 'levelNational'],
  ['international', 'levelInternational'],
] as const;

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    const result = await api.managedCompetitions(page.value);
    items.value = result.items;
    size.value = result.page_size;
    total.value = result.total;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function startDraft() {
  form.name = '';
  form.summary = '';
  saveError.value = null;
  nameError.value = false;
  created.value = '';
  publishedName.value = '';
  open.value = true;
}

async function saveDraft() {
  if (saving.value) return;
  if (!form.name.trim()) {
    nameError.value = true;
    nameInput.value?.focus();
    return;
  }
  saving.value = true;
  saveError.value = null;
  try {
    const result = await api.createCompetition(form);
    created.value = result.name;
    open.value = false;
    page.value = 1;
    await load();
  } catch (error) {
    saveError.value = error;
  } finally {
    saving.value = false;
  }
}

async function publish(item: ManagedCompetition) {
  if (publishingId.value) return;
  publishingId.value = item.id;
  try {
    try {
      await ElMessageBox.confirm(
        t('publication.competitionConfirm', { name: item.name }),
        t('publication.competitionAction'),
        {
          type: 'warning',
          cancelButtonText: t('cancel'),
          confirmButtonText: t('publication.competitionAction'),
        },
      );
    } catch {
      return;
    }
    publishError.value = null;
    publishedName.value = '';
    const updated = await api.publishCompetition(item.id);
    items.value = items.value.map((current) => (current.id === updated.id ? updated : current));
    created.value = '';
    publishedName.value = updated.name;
  } catch (error) {
    publishError.value = error;
  } finally {
    publishingId.value = undefined;
  }
}

function mergeDetail(detail: ManagedCompetitionDetail) {
  items.value = items.value.map((item) =>
    item.id === detail.id
      ? {
          id: detail.id,
          public_code: detail.public_code,
          name: detail.name,
          summary: detail.summary,
          status: detail.status,
        }
      : item,
  );
}

async function startEdit(item: ManagedCompetition) {
  if (editingId.value) return;
  editingId.value = item.id;
  editOpen.value = true;
  editLoading.value = true;
  editError.value = null;
  editSavedName.value = '';
  Object.assign(editForm, { name: item.name, summary: item.summary, category: '', level: '' });
  try {
    const detail = await api.competitionDetail(item.id);
    Object.assign(editForm, {
      name: detail.name,
      summary: detail.summary,
      category: detail.category ?? '',
      level: detail.level ?? '',
    });
  } catch (error) {
    editError.value = error;
  } finally {
    editLoading.value = false;
    editingId.value = undefined;
  }
}

async function saveEdit() {
  if (editSaving.value || editingId.value === undefined || editLoading.value) return;
  if (!editForm.name.trim()) return;
  editSaving.value = true;
  editError.value = null;
  try {
    const detail = await api.updateCompetition(editingId.value, {
      name: editForm.name.trim(),
      summary: editForm.summary.trim(),
      category: (editForm.category || null) as ManagedCompetitionDetail['category'],
      level: (editForm.level || null) as ManagedCompetitionDetail['level'],
    });
    mergeDetail(detail);
    editOpen.value = false;
    created.value = '';
    publishedName.value = '';
    archivedName.value = '';
    restoredName.value = '';
    editSavedName.value = detail.name;
  } catch (error) {
    editError.value = error;
  } finally {
    editSaving.value = false;
  }
}

async function archive(item: ManagedCompetition) {
  if (archiveBusy.value) return;
  try {
    await ElMessageBox.confirm(
      t('competitionArchiveConfirm', { name: item.name }),
      t('competitionArchive'),
      {
        confirmButtonText: t('competitionArchive'),
        cancelButtonText: t('cancel'),
        type: 'warning',
      },
    );
  } catch {
    return;
  }
  archiveBusy.value = item.id;
  publishError.value = null;
  try {
    const detail = await api.archiveCompetition(item.id);
    mergeDetail(detail);
    archivedName.value = detail.name;
    created.value = '';
    publishedName.value = '';
    restoredName.value = '';
    editSavedName.value = '';
  } catch (error) {
    publishError.value = error;
  } finally {
    archiveBusy.value = undefined;
  }
}

async function unarchive(item: ManagedCompetition) {
  if (archiveBusy.value) return;
  let reason: string;
  try {
    const answer = await ElMessageBox.prompt(
      t('competitionUnarchivePrompt', { name: item.name }),
      t('competitionUnarchive'),
      {
        confirmButtonText: t('competitionUnarchive'),
        cancelButtonText: t('cancel'),
        inputValidator: (value) =>
          value && value.trim() ? true : t('competitionUnarchiveRequired'),
      },
    );
    reason = String(answer.value ?? '').trim();
  } catch {
    return;
  }
  if (!reason) return;
  archiveBusy.value = item.id;
  publishError.value = null;
  try {
    const detail = await api.unarchiveCompetition(item.id, reason);
    mergeDetail(detail);
    restoredName.value = detail.name;
    created.value = '';
    publishedName.value = '';
    archivedName.value = '';
    editSavedName.value = '';
  } catch (error) {
    publishError.value = error;
  } finally {
    archiveBusy.value = undefined;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('competitionRegistry') }}</h1>
      <p>{{ t('competitionRegistryHint') }}</p>
    </div>
    <el-button
      v-if="mayCreateCompetition(session.me)"
      type="primary"
      :icon="Plus"
      @click="startDraft"
      >{{ t('createCompetition') }}</el-button
    >
  </div>
  <div role="status" class="registry-feedback">
    <p v-if="created">{{ t('competitionCreated', { name: created }) }}</p>
    <p v-if="editSavedName">{{ t('competitionUpdated', { name: editSavedName }) }}</p>
    <p v-if="publishedName">{{ t('publication.competitionDone', { name: publishedName }) }}</p>
    <p v-if="archivedName">{{ t('competitionArchived', { name: archivedName }) }}</p>
    <p v-if="restoredName">{{ t('competitionUnarchived', { name: restoredName }) }}</p>
  </div>
  <div class="content-panel">
    <ErrorNotice v-if="publishError" :error="publishError" />
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <p v-else-if="!items.length" class="muted">{{ t('competitionEmpty') }}</p>
    <table v-else class="registry-table" aria-labelledby="page-title">
      <thead>
        <tr>
          <th scope="col">{{ t('competitionName') }}</th>
          <th scope="col">{{ t('status') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <th scope="row">
            <RouterLink :to="{ name: 'editionRegistry', params: { id: item.id } }">{{
              item.name
            }}</RouterLink>
            <span class="small muted">{{ item.public_code }}</span>
          </th>
          <td>
            <div class="registry-state">
              <StatusTag :status="item.status" />
              <el-button
                v-if="
                  item.status === 'draft' &&
                  hasCompetitionPermission(session.me, 'competition:publish', item.id)
                "
                link
                type="primary"
                :loading="publishingId === item.id"
                :disabled="Boolean(publishingId)"
                :aria-label="t('publication.competitionLabel', { name: item.name })"
                @click="publish(item)"
                >{{ t('publication.competitionAction') }}</el-button
              >
              <el-button
                v-if="
                  item.status !== 'archived' &&
                  hasCompetitionPermission(session.me, 'competition:update', item.id)
                "
                link
                type="primary"
                :disabled="Boolean(archiveBusy)"
                :aria-label="t('competitionEdit')"
                @click="startEdit(item)"
                >{{ t('competitionEdit') }}</el-button
              >
              <el-button
                v-if="
                  item.status === 'published' &&
                  hasCompetitionPermission(session.me, 'competition:archive', item.id)
                "
                link
                type="danger"
                :loading="archiveBusy === item.id"
                :disabled="Boolean(publishingId || archiveBusy)"
                :aria-label="t('competitionArchive')"
                @click="archive(item)"
                >{{ t('competitionArchive') }}</el-button
              >
              <el-button
                v-if="
                  item.status === 'archived' &&
                  mayUnarchiveCompetition(session.me) &&
                  hasCompetitionPermission(session.me, 'competition:archive', item.id)
                "
                link
                type="primary"
                :loading="archiveBusy === item.id"
                :disabled="Boolean(archiveBusy)"
                :aria-label="t('competitionUnarchive')"
                @click="unarchive(item)"
                >{{ t('competitionUnarchive') }}</el-button
              >
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <el-pagination
    v-if="total > size"
    :current-page="page"
    :page-size="size"
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
  <el-dialog
    v-model="open"
    :title="t('createCompetition')"
    width="min(560px, calc(100% - 32px))"
    :show-close="!saving"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    @opened="nameInput?.focus()"
  >
    <ErrorNotice v-if="saveError" :error="saveError" />
    <el-form label-position="top" @submit.prevent="saveDraft">
      <el-form-item
        :label="t('competitionName')"
        required
        :error="nameError ? t('competitionNameRequired') : ''"
      >
        <el-input
          ref="nameInput"
          v-model="form.name"
          :maxlength="128"
          :disabled="saving"
          required
          @input="nameError = false"
        />
      </el-form-item>
      <el-form-item :label="t('competitionSummary')">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="3"
          :maxlength="2000"
          :disabled="saving"
        />
      </el-form-item>
      <div class="registry-actions">
        <el-button :disabled="saving" @click="open = false">{{ t('cancel') }}</el-button>
        <el-button type="primary" native-type="submit" :loading="saving">{{ t('save') }}</el-button>
      </div>
    </el-form>
  </el-dialog>
  <el-dialog
    v-model="editOpen"
    :title="t('competitionEdit')"
    width="min(560px, calc(100% - 32px))"
    :show-close="!editSaving"
    :close-on-click-modal="false"
    :close-on-press-escape="!editSaving"
  >
    <p v-if="editLoading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="editError" :error="editError" />
    <el-form v-else label-position="top" @submit.prevent="saveEdit">
      <el-form-item
        :label="t('competitionName')"
        required
        :error="!editForm.name.trim() ? t('competitionNameRequired') : ''"
      >
        <el-input v-model="editForm.name" :maxlength="128" :disabled="editSaving" required />
      </el-form-item>
      <el-form-item :label="t('competitionSummary')">
        <el-input
          v-model="editForm.summary"
          type="textarea"
          :rows="3"
          :maxlength="2000"
          :disabled="editSaving"
        />
      </el-form-item>
      <el-form-item :label="t('competitionCategory')">
        <el-select v-model="editForm.category" :disabled="editSaving" clearable>
          <el-option :value="''" :label="t('categoryUnset')" />
          <el-option
            v-for="[value, label] in categoryOptions"
            :key="value"
            :value="value"
            :label="t(label)"
          />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('competitionLevel')">
        <el-select v-model="editForm.level" :disabled="editSaving" clearable>
          <el-option :value="''" :label="t('categoryUnset')" />
          <el-option
            v-for="[value, label] in levelOptions"
            :key="value"
            :value="value"
            :label="t(label)"
          />
        </el-select>
      </el-form-item>
      <div class="registry-actions">
        <el-button :disabled="editSaving" @click="editOpen = false">{{ t('cancel') }}</el-button>
        <el-button
          type="primary"
          native-type="submit"
          :loading="editSaving"
          :disabled="editLoading"
          >{{ t('save') }}</el-button
        >
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.registry-state {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.registry-table {
  inline-size: 100%;
  border-collapse: collapse;
  overflow-wrap: anywhere;
}
.registry-table th,
.registry-table td {
  padding: 12px;
  text-align: start;
}
.registry-table thead th {
  color: var(--color-muted);
  background: var(--color-soft);
}
.registry-table tbody tr + tr {
  border-block-start: 1px solid var(--color-border);
}
.registry-table th span {
  display: block;
  font-weight: 400;
}
.registry-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
