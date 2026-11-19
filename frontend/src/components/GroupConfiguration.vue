<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessageBox } from 'element-plus';
import { Plus } from '@element-plus/icons-vue';
import { api } from '../api';
import type { ManagedEdition, ManagedGroup } from '../api/schemas';
import { useSession } from '../stores/session';
import { hasEditionPermission } from '../utils/permissions';
import ErrorNotice from './ErrorNotice.vue';
import StatusTag from './StatusTag.vue';

const props = defineProps<{ edition: ManagedEdition }>();
const { t } = useI18n();
const session = useSession();
const hasGrant = (permission: string) =>
  hasEditionPermission(session.me, permission, props.edition.id, props.edition.competition_id);
const levels = ['ES', 'MS', 'HS', 'U'] as const;
const entryTypes = ['individual', 'team', 'both'] as const;
const items = ref<ManagedGroup[]>([]);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const loading = ref(false);
const busy = ref(false);
const open = ref(false);
const editingId = ref<number>();
const loadError = ref<unknown>(null);
const actionError = ref<unknown>(null);
const feedback = ref('');
const form = reactive({
  code: '',
  name: '',
  school_level: '',
  enrollment_type: 'team',
  grades: '',
});

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    const data = await api.editionGroups(props.edition.id, page.value);
    items.value = data.items;
    pageSize.value = data.page_size;
    total.value = data.total;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function openDraft(item?: ManagedGroup) {
  editingId.value = item?.id;
  Object.assign(form, {
    code: item?.code ?? '',
    name: item?.name ?? '',
    school_level: item?.school_level ?? '',
    enrollment_type: item?.enrollment_type ?? 'team',
    grades: item?.grade_limits.join('\n') ?? '',
  });
  actionError.value = null;
  feedback.value = '';
  open.value = true;
}

async function apply(action: () => Promise<unknown>, message: string, resetPage = false) {
  if (busy.value) return;
  busy.value = true;
  actionError.value = null;
  feedback.value = '';
  try {
    await action();
    open.value = false;
    feedback.value = message;
    if (resetPage) page.value = 1;
    await load();
  } catch (error) {
    actionError.value = error;
  } finally {
    busy.value = false;
  }
}

function save() {
  const body = {
    code: form.code,
    name: form.name,
    school_level: form.school_level || null,
    enrollment_type: form.enrollment_type,
    grade_limits: form.grades
      .split(/\r?\n/)
      .map((grade) => grade.trim())
      .filter(Boolean),
  };
  const id = editingId.value;
  return apply(
    () => (id ? api.updateGroup(id, body) : api.createGroup(props.edition.id, body)),
    t('groups.saved', { name: form.name.trim() }),
  );
}

async function change(item: ManagedGroup, action: 'enable' | 'disable' | 'remove') {
  if (action !== 'enable') {
    try {
      await ElMessageBox.confirm(
        t(action === 'remove' ? 'groups.confirmDelete' : 'groups.confirmDisable', {
          name: item.name,
        }),
        t(`groups.${action}`),
        {
          type: 'warning',
          cancelButtonText: t('cancel'),
          confirmButtonText: t(`groups.${action}`),
        },
      );
    } catch {
      return;
    }
  }
  await apply(
    () => (action === 'remove' ? api.deleteGroup(item.id) : api.setGroupState(item.id, action)),
    t(action === 'remove' ? 'groups.removed' : 'groups.saved', { name: item.name }),
    action === 'remove',
  );
}

onMounted(load);
</script>

<template>
  <section class="content-panel" aria-labelledby="group-panel-title">
    <div class="group-header">
      <div>
        <h2 id="group-panel-title">{{ t('groups.title') }}</h2>
        <p class="muted">{{ t('groups.hint') }}</p>
      </div>
      <el-button
        v-if="edition.status === 'draft' && hasGrant('group:create')"
        type="primary"
        :icon="Plus"
        :disabled="busy"
        @click="openDraft()"
        >{{ t('groups.add') }}</el-button
      >
    </div>
    <div role="status">
      <p v-if="feedback">{{ feedback }}</p>
    </div>
    <ErrorNotice v-if="actionError && !open" :error="actionError" />
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <p v-else-if="!items.length" class="muted">{{ t('none') }}</p>
    <ul v-else class="group-list">
      <li v-for="item in items" :key="item.id" class="group-row">
        <div>
          <h3>{{ item.name }}</h3>
          <p class="small muted">
            {{ item.code }} · {{ t(`groups.${item.school_level ?? 'noLevel'}`) }} ·
            {{ t(`groups.${item.enrollment_type}`) }}
          </p>
          <p v-if="item.grade_limits.length" class="small muted">
            {{ item.grade_limits.join(' / ') }}
          </p>
        </div>
        <div class="group-actions">
          <StatusTag :status="item.status" />
          <template v-if="edition.status === 'draft' && hasGrant('group:update')">
            <el-button link type="primary" :disabled="busy" @click="openDraft(item)">{{
              t('groups.edit')
            }}</el-button>
            <el-button link :disabled="busy" @click="change(item, 'remove')">{{
              t('groups.remove')
            }}</el-button>
          </template>
          <el-button
            v-if="edition.status !== 'closed' && hasGrant('group:enable_disable')"
            link
            :disabled="busy"
            @click="change(item, item.status === 'enabled' ? 'disable' : 'enable')"
            >{{ t(item.status === 'enabled' ? 'groups.disable' : 'groups.enable') }}</el-button
          >
        </div>
      </li>
    </ul>
    <el-pagination
      v-if="total > pageSize"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      :disabled="loading || busy"
      layout="prev, pager, next"
      :pager-count="5"
      @update:current-page="
        (value: number) => {
          page = value;
          load();
        }
      "
    />
  </section>
  <el-dialog
    v-model="open"
    :title="t(editingId ? 'groups.edit' : 'groups.add')"
    width="min(560px, calc(100% - 32px))"
    :show-close="!busy"
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
  >
    <ErrorNotice v-if="actionError" :error="actionError" />
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item :label="t('groups.code')" required
        ><el-input
          v-model.trim="form.code"
          maxlength="8"
          pattern="[A-Z0-9][A-Z0-9\-]{0,7}"
          required
          :disabled="busy"
      /></el-form-item>
      <el-form-item :label="t('groups.name')" required
        ><el-input v-model.trim="form.name" maxlength="64" required :disabled="busy"
      /></el-form-item>
      <el-form-item :label="t('schoolLevel')"
        ><el-select v-model="form.school_level" :disabled="busy"
          ><el-option :label="t('groups.noLevel')" value="" /><el-option
            v-for="level in levels"
            :key="level"
            :label="t(`groups.${level}`)"
            :value="level" /></el-select
      ></el-form-item>
      <el-form-item :label="t('groups.type')" required
        ><el-select v-model="form.enrollment_type" :disabled="busy"
          ><el-option
            v-for="kind in entryTypes"
            :key="kind"
            :label="t(`groups.${kind}`)"
            :value="kind" /></el-select
      ></el-form-item>
      <el-form-item :label="t('groups.grades')">
        <el-input
          v-model="form.grades"
          type="textarea"
          :rows="2"
          maxlength="1056"
          aria-describedby="division-grade-hint"
          :disabled="busy"
        />
        <p id="division-grade-hint" class="small muted">{{ t('groups.gradeHint') }}</p>
      </el-form-item>
      <div class="group-actions">
        <el-button :disabled="busy" @click="open = false">{{ t('cancel') }}</el-button>
        <el-button type="primary" native-type="submit" :loading="busy">{{ t('save') }}</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.group-header,
.group-row,
.group-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}
.group-header,
.group-row {
  justify-content: space-between;
}
.group-actions {
  justify-content: flex-end;
}
.group-header {
  margin-block-end: 12px;
}
.group-header h2,
.group-header p,
.group-row h3,
.group-row p {
  margin: 0;
}
.group-list {
  padding: 0;
  margin: 0;
  list-style: none;
}
.group-row {
  border-block-start: 1px solid var(--color-border);
  padding-block: 12px;
  overflow-wrap: anywhere;
}
.group-actions .el-button + .el-button {
  margin-inline-start: 0;
}
</style>
