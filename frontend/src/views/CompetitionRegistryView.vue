<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Plus } from '@element-plus/icons-vue';
import { ElMessageBox } from 'element-plus';
import { api } from '../api';
import type { ManagedCompetition } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { useSession } from '../stores/session';
import { hasCompetitionPermission, mayCreateCompetition } from '../utils/permissions';

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
const form = reactive({ name: '', summary: '' });

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
    <p v-if="publishedName">{{ t('publication.competitionDone', { name: publishedName }) }}</p>
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
