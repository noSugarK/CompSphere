<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
const props = defineProps<{ status: string }>();
const { t } = useI18n();
const type = computed(() =>
  ['approved', 'active'].includes(props.status)
    ? 'success'
    : ['rejected', 'revoked'].includes(props.status)
      ? 'danger'
      : ['submitted', 'pending_review', 'returned'].includes(props.status)
        ? 'warning'
        : 'info',
);
</script>
<template>
  <el-tag :type="type" effect="light">{{ t(status) }}</el-tag>
</template>
