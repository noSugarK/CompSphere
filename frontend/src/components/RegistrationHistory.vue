<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { Registration, RegistrationSubmission } from '../api/schemas';
import { formatEventDateTime } from '../utils/format';
import ErrorNotice from './ErrorNotice.vue';

const props = defineProps<{ record: Registration }>();
const { t } = useI18n();
const items = ref<RegistrationSubmission[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const error = ref<unknown>(null);
let lastRequest = 0;
const decisions = computed(() => {
  const byRound = new Map<number, Registration['approval_records']>();
  for (const decision of props.record.approval_records) {
    const list = byRound.get(decision.submission_no) ?? [];
    list.push(decision);
    byRound.set(decision.submission_no, list);
  }
  return byRound;
});

async function load() {
  const request = ++lastRequest;
  loading.value = true;
  error.value = null;
  try {
    const result = await api.registrationSubmissions(props.record.id, page.value);
    if (request !== lastRequest) return;
    items.value = result.items;
    total.value = result.total;
    pageSize.value = result.page_size;
  } catch (cause) {
    if (request === lastRequest) error.value = cause;
  } finally {
    if (request === lastRequest) loading.value = false;
  }
}

watch(() => [props.record.id, props.record.version, page.value], load, { immediate: true });
</script>

<template>
  <section class="content-panel" aria-labelledby="submission-history-title">
    <h2 id="submission-history-title">{{ t('reviewRecord') }}</h2>
    <p class="small muted">{{ t('submissionHistoryHint') }}</p>
    <p v-if="loading" role="status">{{ t('loading') }}</p>
    <template v-else-if="error">
      <ErrorNotice :error="error" />
      <el-button @click="load">{{ t('retry') }}</el-button>
    </template>
    <p v-else-if="!items.length" class="muted">{{ t('none') }}</p>
    <el-timeline v-else>
      <el-timeline-item
        v-for="round in items"
        :key="round.submission_no"
        :timestamp="formatEventDateTime(round.submitted_at)"
      >
        <h3 class="round-title">{{ t('reviewRound', { round: round.submission_no }) }}</h3>
        <p class="round-summary">{{ round.event_name }} · {{ round.group_name }}</p>
        <p v-if="round.selected_school_level" class="small muted">
          {{ t('submissionDeclaredLevel', { level: t(`groups.${round.selected_school_level}`) }) }}
        </p>
        <p v-if="round.cancelled_at" class="small muted">
          {{ t('submissionCancelledAt', { date: formatEventDateTime(round.cancelled_at) }) }}
        </p>
        <details v-if="round.members.length">
          <summary>{{ t('submissionFrozenMembers', { count: round.members.length }) }}</summary>
          <ul class="history-members">
            <li
              v-for="(member, index) in round.members"
              :key="member.user_id ?? `snapshot-${index}`"
            >
              <strong>{{ member.real_name }}</strong>
              <span class="small muted">{{
                t(member.role === 'captain' ? 'submissionCaptain' : 'submissionMember')
              }}</span>
              <span v-if="member.school_level" class="small muted">{{
                t(`groups.${member.school_level}`)
              }}</span>
              <span v-if="member.grade" class="small muted">{{ member.grade }}</span>
            </li>
          </ul>
        </details>
        <ul v-if="decisions.has(round.submission_no)" class="history-decisions">
          <li v-for="decision in decisions.get(round.submission_no)" :key="decision.id">
            <strong>{{
              t(decision.action === 'cancel_review' ? 'submissionCancelledAction' : decision.action)
            }}</strong>
            <time class="small muted" :datetime="decision.created_at">{{
              formatEventDateTime(decision.created_at)
            }}</time>
            <p v-if="decision.comment">{{ decision.comment }}</p>
          </li>
        </ul>
      </el-timeline-item>
    </el-timeline>
    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      :pager-count="5"
      layout="prev, pager, next"
    />
  </section>
</template>

<style scoped>
.round-title,
.round-summary {
  margin-block: 0 4px;
}
summary {
  cursor: pointer;
  padding-block: 6px;
}
.history-members,
.history-decisions {
  margin-block: 8px 0;
  padding-inline-start: 20px;
  overflow-wrap: anywhere;
}
.history-members span,
.history-decisions time {
  margin-inline-start: 8px;
}
.history-decisions p {
  margin-block: 4px 8px;
  white-space: pre-wrap;
}
</style>
