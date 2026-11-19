<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Bell } from '@element-plus/icons-vue';
import { api } from '../api';
import type { RegistrationNotice } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import { formatEventDateTime } from '../utils/format';

const { t } = useI18n();
const items = ref<RegistrationNotice[]>([]);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const loading = ref(true);
const loadError = ref<unknown>(null);
const readError = ref<unknown>(null);
const readingId = ref<number>();
const lastRead = ref<RegistrationNotice>();
const today = ref('');
const groups = computed(() => {
  const isToday = (notice: RegistrationNotice) =>
    formatEventDateTime(notice.created_at).startsWith(today.value);
  return [
    { key: 'today', items: items.value.filter(isToday) },
    { key: 'earlier', items: items.value.filter((item) => !isToday(item)) },
  ].filter((group) => group.items.length);
});

async function load() {
  loading.value = true;
  loadError.value = null;
  readError.value = null;
  try {
    const data = await api.notifications(page.value);
    today.value = formatEventDateTime(new Date().toISOString()).slice(0, 10);
    items.value = data.items;
    pageSize.value = data.page_size;
    total.value = data.total;
  } catch (error) {
    items.value = [];
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

async function markRead(item: RegistrationNotice) {
  if (item.read_at || readingId.value !== undefined) return;
  readingId.value = item.id;
  readError.value = null;
  lastRead.value = undefined;
  try {
    const updated = await api.readNotification(item.id);
    items.value = items.value.map((notice) => (notice.id === item.id ? updated : notice));
    lastRead.value = updated;
  } catch (error) {
    readError.value = error;
  } finally {
    readingId.value = undefined;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('notifications') }}</h1>
      <p>{{ t('inbox.hint') }}</p>
    </div>
  </div>
  <div v-if="loading || loadError || !items.length" class="content-panel">
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <p v-else class="muted">{{ t('inbox.empty') }}</p>
  </div>
  <ErrorNotice v-if="readError" :error="readError" />
  <template v-if="!loading && !loadError">
    <section v-for="group in groups" :key="group.key" class="content-panel inbox-group">
      <h2>{{ t(`inbox.${group.key}`) }}</h2>
      <ul class="inbox-list">
        <li v-for="item in group.items" :key="item.id" class="inbox-item">
          <span class="inbox-icon" aria-hidden="true"
            ><el-icon><Bell /></el-icon
          ></span>
          <div class="inbox-copy">
            <h3>{{ t(`inbox.${item.kind}`) }}</h3>
            <p class="small muted">
              {{ t('inbox.round', { id: item.registration_id, round: item.submission_no }) }}
            </p>
          </div>
          <div class="inbox-actions">
            <time :datetime="item.created_at" class="small muted">
              {{
                group.key === 'today'
                  ? formatEventDateTime(item.created_at).slice(11)
                  : formatEventDateTime(item.created_at)
              }}
            </time>
            <el-tag v-if="!item.read_at" type="primary" effect="plain">{{
              t('inbox.unread')
            }}</el-tag>
            <RouterLink
              :to="{ name: 'registration', params: { id: item.registration_id } }"
              :aria-label="t('inbox.viewRegistration', { id: item.registration_id })"
              >{{ t('inbox.view') }}</RouterLink
            >
            <el-button
              link
              :aria-disabled="Boolean(item.read_at) || readingId !== undefined"
              :aria-label="
                item.read_at
                  ? t('inbox.read')
                  : t('inbox.markReadFor', {
                      id: item.registration_id,
                      round: item.submission_no,
                      kind: t(`inbox.${item.kind}`),
                    })
              "
              @click="markRead(item)"
            >
              {{ t(item.read_at ? 'inbox.read' : 'inbox.markRead') }}
            </el-button>
          </div>
        </li>
      </ul>
    </section>
  </template>
  <p class="small muted inbox-confirmation" role="status">
    <template v-if="lastRead">{{
      t('inbox.readConfirmation', { id: lastRead.registration_id, round: lastRead.submission_no })
    }}</template>
  </p>
  <el-pagination
    v-if="total > pageSize"
    v-model:current-page="page"
    :page-size="pageSize"
    :total="total"
    :disabled="loading || readingId !== undefined"
    layout="prev, pager, next"
    :pager-count="5"
    @current-change="load"
  />
</template>

<style scoped>
.inbox-list {
  padding: 0;
  margin: 0;
  list-style: none;
}
.inbox-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px 16px;
  padding-block: 16px;
}
.inbox-item + .inbox-item {
  border-block-start: 1px solid var(--color-border);
}
.inbox-group h2 {
  margin-block-end: 4px;
  font-size: 1.125rem;
}
.inbox-icon {
  display: grid;
  place-items: center;
  inline-size: 36px;
  block-size: 36px;
  border-radius: 4px;
  color: var(--color-text);
  background: var(--color-soft);
}
.inbox-copy h3 {
  margin: 0 0 4px;
  font-size: 1rem;
}
.inbox-copy p {
  margin: 0;
}
.inbox-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0 12px;
}
.inbox-actions a,
.inbox-actions button {
  display: inline-flex;
  align-items: center;
  min-block-size: 44px;
}
.inbox-actions button[aria-disabled='true'] {
  color: var(--el-text-color-secondary);
  cursor: default;
}
.inbox-confirmation:empty {
  margin: 0;
}
@media (max-width: 767px) {
  .inbox-item {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .inbox-actions {
    grid-column: 2;
  }
}
</style>
