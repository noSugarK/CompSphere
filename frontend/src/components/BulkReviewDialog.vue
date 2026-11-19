<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import type { ButtonInstance, InputInstance } from 'element-plus';
import { api } from '../api';
import type { BulkReviewResult, ReviewAction, ReviewQueueItem } from '../api/schemas';
import ErrorNotice from './ErrorNotice.vue';

const props = defineProps<{ action: ReviewAction; rows: ReviewQueueItem[] }>();
const emit = defineEmits<{
  closed: [results: BulkReviewResult[] | undefined, uncertain: boolean];
}>();
const { t } = useI18n();
const open = ref(true);
const sending = ref(false);
const comment = ref('');
const commentError = ref(false);
const error = ref<unknown>(null);
const commentInput = ref<InputInstance>();
const cancelButton = ref<ButtonInstance>();
const required = computed(() => props.action !== 'approve');
const label = computed(() => t(props.action));
let results: BulkReviewResult[] | undefined;

async function confirm() {
  if (sending.value || error.value) return;
  if (required.value && !comment.value.trim()) {
    commentError.value = true;
    commentInput.value?.focus();
    return;
  }
  sending.value = true;
  try {
    results = await api.bulkReviewRegistrations({
      action: props.action,
      comment: comment.value.trim(),
      items: props.rows.map((row) => ({
        registration_id: row.id,
        submission_no: row.submission_no,
      })),
    });
    open.value = false;
  } catch (cause) {
    error.value = cause;
  } finally {
    sending.value = false;
  }
}

function focusCancel() {
  cancelButton.value?.ref?.focus();
}
</script>

<template>
  <el-dialog
    v-model="open"
    :title="t('bulkReviewTitle', { action: label, count: rows.length })"
    width="min(560px, calc(100% - 32px))"
    :show-close="!sending"
    :close-on-click-modal="false"
    :close-on-press-escape="!sending"
    @opened="focusCancel"
    @closed="emit('closed', results, Boolean(error))"
  >
    <el-form label-position="top" @submit.prevent="confirm">
      <p>{{ t(`bulkReviewEffect.${action}`) }}</p>
      <ul class="bulk-targets">
        <li v-for="row in rows" :key="row.id">
          {{ row.batch_no }} · {{ t('reviewRound', { round: row.submission_no }) }}
        </li>
      </ul>
      <el-form-item
        :label="t('comment')"
        :required="required"
        :error="commentError ? t('reviewCommentRequired') : ''"
      >
        <el-input
          ref="commentInput"
          v-model="comment"
          type="textarea"
          maxlength="2000"
          :disabled="sending || Boolean(error)"
          @input="commentError = false"
        />
      </el-form-item>
      <template v-if="error">
        <ErrorNotice :error="error" />
        <p role="status">{{ t('bulkReviewUncertain') }}</p>
      </template>
      <div class="actions">
        <el-button ref="cancelButton" :disabled="sending" @click="open = false">{{
          t(error ? 'bulkReviewRefresh' : 'cancel')
        }}</el-button>
        <el-button
          v-if="!error"
          :type="required ? 'danger' : 'primary'"
          native-type="submit"
          :loading="sending"
          >{{ t('bulkReviewConfirm', { action: label }) }}</el-button
        >
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.bulk-targets {
  max-block-size: 180px;
  overflow: auto;
  padding-inline-start: 24px;
  overflow-wrap: anywhere;
}
</style>
