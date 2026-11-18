<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { ApiError } from '../api/client';
import { errorMessage } from '../utils/errors';
defineProps<{ error: unknown }>();
defineEmits<{ retry: [] }>();
const { t } = useI18n();
</script>
<template>
  <div v-if="error" class="error-notice" role="alert">
    <el-alert :title="errorMessage(error)" type="error" :closable="false" show-icon />
    <p v-if="error instanceof ApiError && error.requestId" class="small muted">
      {{ t('requestId') }}: {{ error.requestId }}
    </p>
    <el-button v-if="$attrs.onRetry" class="retry-button" @click="$emit('retry')">{{
      t('retry')
    }}</el-button>
  </div>
</template>
