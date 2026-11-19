<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { ReviewQueueItem, ReviewQueueOption } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { formatEventDateTime } from '../utils/format';
import {
  readReviewQueueQuery,
  reviewDimensions,
  writeReviewQueueQuery,
  type ReviewDimension,
} from '../utils/reviewQueue';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const current = readReviewQueueQuery(route.query);
const filters = reactive({ ...current });
const labels = { edition: 'selectEdition', event: 'event', group: 'group', org: 'org' } as const;
const statuses = [
  'pending_review',
  'approved',
  'returned',
  'rejected',
  'withdrawn',
  'draft',
  'all',
] as const;
const options = reactive<Record<ReviewDimension, ReviewQueueOption[]>>({
  edition: [],
  event: [],
  group: [],
  org: [],
});
const items = ref<ReviewQueueItem[]>([]);
const total = ref(0);
const pageSize = ref(20);
const loading = ref(true);
const loadingOptions = ref(false);
const error = ref<unknown>(null);
const optionsError = ref<unknown>(null);
let optionRequest = 0;

async function loadQueue() {
  loading.value = true;
  error.value = null;
  try {
    const result = await api.registrations({
      ...current,
      status: current.status === 'all' ? undefined : current.status,
    });
    items.value = result.items;
    total.value = result.total;
    pageSize.value = result.page_size;
  } catch (cause) {
    error.value = cause;
  } finally {
    loading.value = false;
  }
}

async function fetchOptions(dimension: ReviewDimension, edition?: number) {
  const first = await api.reviewQueueOptions({ dimension, edition, page_size: 100 });
  const result = [...first.items];
  for (let page = 2; page <= Math.ceil(first.total / first.page_size); page += 1) {
    result.push(
      ...(await api.reviewQueueOptions({ dimension, edition, page_size: 100, page })).items,
    );
  }
  return result;
}

async function loadOptions() {
  const request = ++optionRequest;
  loadingOptions.value = true;
  optionsError.value = null;
  try {
    const result = await Promise.all(
      reviewDimensions.map((dimension) =>
        fetchOptions(dimension, dimension === 'edition' ? undefined : filters.edition),
      ),
    );
    if (request === optionRequest) {
      reviewDimensions.forEach((dimension, index) => {
        options[dimension] = result[index] ?? [];
      });
    }
  } catch (cause) {
    if (request === optionRequest) optionsError.value = cause;
  } finally {
    if (request === optionRequest) loadingOptions.value = false;
  }
}

watch(
  () => filters.edition,
  () => {
    filters.event = filters.group = filters.org = undefined;
    void loadOptions();
  },
);

function applyFilters() {
  void router.replace({ name: 'reviews', query: writeReviewQueueQuery({ ...filters, page: 1 }) });
}

function changePage(page: number) {
  void router.replace({ name: 'reviews', query: writeReviewQueueQuery({ ...current, page }) });
}

function resetFilters() {
  Object.assign(filters, readReviewQueueQuery({}));
  void router.replace({ name: 'reviews' });
}

onMounted(() => {
  void loadQueue();
  void loadOptions();
});
</script>

<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('reviews') }}</h1>
      <p>{{ t('reviewQueueHint') }}</p>
    </div>
  </div>
  <section class="content-panel" :aria-label="t('reviewFilters')">
    <el-form label-position="top" @submit.prevent="applyFilters">
      <div class="review-filters">
        <el-form-item :label="t('reviewSearch')">
          <el-input v-model="filters.q" clearable maxlength="80" />
        </el-form-item>
        <el-form-item :label="t('status')">
          <el-select v-model="filters.status">
            <el-option
              v-for="status in statuses"
              :key="status"
              :value="status"
              :label="t(status)"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-for="dimension in reviewDimensions"
          :key="dimension"
          :label="t(labels[dimension])"
        >
          <el-select
            v-model="filters[dimension]"
            clearable
            filterable
            :loading="loadingOptions"
            :empty-values="[null, undefined, '']"
            :value-on-clear="() => undefined"
          >
            <el-option
              v-for="option in options[dimension]"
              :key="option.id"
              :value="option.id"
              :label="option.name"
            />
          </el-select>
        </el-form-item>
      </div>
      <el-button type="primary" native-type="submit">{{ t('reviewApplyFilters') }}</el-button>
      <el-button @click="resetFilters">{{ t('reviewResetFilters') }}</el-button>
    </el-form>
    <ErrorNotice :error="optionsError" />
    <el-button v-if="optionsError" class="retry-button" @click="loadOptions">{{
      t('retry')
    }}</el-button>
  </section>
  <ErrorNotice :error="error" />
  <el-button v-if="error" class="retry-button" @click="loadQueue">{{ t('retry') }}</el-button>
  <p v-if="loading" role="status">{{ t('loading') }}</p>
  <section v-else-if="!error" class="content-panel">
    <h2 id="review-results-title">{{ t('reviewResultCount', { count: total }) }}</h2>
    <p v-if="!items.length" class="muted">{{ t('reviewNoResults') }}</p>
    <div
      v-else
      class="queue-scroll"
      tabindex="0"
      role="region"
      aria-labelledby="review-results-title"
    >
      <table class="queue-table">
        <thead>
          <tr>
            <th scope="col">{{ t('registrations') }}</th>
            <th scope="col">{{ t('selectEdition') }}</th>
            <th scope="col">{{ t('org') }}</th>
            <th scope="col">{{ t('status') }}</th>
            <th scope="col">{{ t('reviewSubmittedAt') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <th scope="row">
              <RouterLink
                :to="{
                  path: `/registrations/${item.id}`,
                  query: { ...writeReviewQueueQuery(current), origin: 'reviews' },
                }"
                >{{ item.batch_no }}</RouterLink
              >
              <span class="small muted">{{ item.team_code ?? t('individualEnrollment') }}</span>
            </th>
            <td>
              {{ item.edition_name
              }}<span class="small muted">{{ item.event_name }} · {{ item.group_name }}</span>
            </td>
            <td>{{ item.org_name }}</td>
            <td>
              <StatusTag :status="item.status" /><span class="small muted">{{
                t('reviewRound', { round: item.submission_no })
              }}</span>
            </td>
            <td>
              <time :datetime="item.submitted_at">{{
                formatEventDateTime(item.submitted_at)
              }}</time>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <el-pagination
      v-if="total > pageSize"
      :current-page="current.page"
      :page-size="pageSize"
      :total="total"
      :pager-count="5"
      layout="prev, pager, next"
      @current-change="changePage"
    />
  </section>
</template>

<style scoped>
.review-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: 0 16px;
}
.content-panel + .content-panel {
  margin-block-start: 16px;
}
.queue-scroll {
  max-inline-size: 100%;
  max-block-size: min(520px, 75vh);
  overflow: auto;
}
.queue-table {
  min-inline-size: 42rem;
  inline-size: 100%;
  border-collapse: separate;
  border-spacing: 0;
}
.queue-table thead th {
  position: sticky;
  inset-block-start: 0;
  z-index: 2;
  background: var(--color-soft);
}
.queue-table thead th:first-child {
  inset-inline-start: 0;
  z-index: 3;
}
.queue-table tbody th {
  position: sticky;
  inset-inline-start: 0;
  z-index: 1;
  background: var(--color-surface);
}
.queue-table :is(th, td) {
  padding: 10px 12px;
  text-align: start;
  overflow-wrap: anywhere;
  border-block-end: 1px solid var(--color-border);
}
.queue-table .small {
  display: block;
  font-weight: 400;
}
.queue-table time {
  white-space: nowrap;
}
</style>
