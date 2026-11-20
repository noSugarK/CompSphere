<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { AuditLogEntry } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import { formatEventDateTime } from '../utils/format';

const { t } = useI18n();
const items = ref<AuditLogEntry[]>([]);
const total = ref(0);
const page = ref(1);
const loading = ref(true);
const error = ref<unknown>(null);
const filters = reactive({ resource: '', date_from: '', date_to: '' });

async function load(target = page.value) {
  loading.value = true;
  error.value = null;
  page.value = target;
  try {
    const data = await api.auditLogs(
      {
        resource: filters.resource || undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
      },
      target,
    );
    items.value = data.items;
    total.value = data.total;
  } catch (e) {
    error.value = e;
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}
onMounted(() => load(1));
</script>

<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('auditLogs') }}</h1>
      <p>{{ t('auditHint') }}</p>
    </div>
  </div>
  <ErrorNotice :error="error" @retry="load(1)" />
  <section class="content-panel">
    <el-form class="audit-filters" @submit.prevent="load(1)">
      <el-form-item :label="t('auditResource')"
        ><el-input
          v-model="filters.resource"
          maxlength="32"
          clearable
          :placeholder="t('auditAllResources')"
      /></el-form-item>
      <el-form-item :label="t('auditDateFrom')"
        ><el-input
          v-model="filters.date_from"
          placeholder="YYYY-MM-DD"
          maxlength="10" /></el-form-item
      ><el-form-item :label="t('auditDateTo')"
        ><el-input
          v-model="filters.date_to"
          placeholder="YYYY-MM-DD"
          maxlength="10" /></el-form-item
      ><el-form-item
        ><el-button type="primary" native-type="submit" :disabled="loading">{{
          t('reviewApplyFilters')
        }}</el-button></el-form-item
      >
    </el-form>
    <p v-if="loading" role="status">{{ t('loading') }}</p>
    <p v-else-if="!items.length" class="muted">{{ t('reviewNoResults') }}</p>
    <el-table v-else :data="items">
      <el-table-column prop="action" :label="t('auditAction')" min-width="180" />
      <el-table-column prop="resource" :label="t('auditResource')" />
      <el-table-column prop="resource_id" :label="t('auditResourceId')" />
      <el-table-column :label="t('auditActor')"
        ><template #default="{ row }">{{ row.actor_id ?? '—' }}</template></el-table-column
      ><el-table-column :label="t('auditAt')" min-width="150"
        ><template #default="{ row }">
          <time :datetime="row.created_at">{{ formatEventDateTime(row.created_at) }}</time>
        </template></el-table-column
      ></el-table
    >
    <el-pagination
      v-if="total > 20"
      layout="prev, pager, next"
      :total="total"
      :current-page="page"
      :page-size="20"
      @current-change="load"
    />
  </section>
</template>

<style scoped>
.audit-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0 16px;
}
</style>
