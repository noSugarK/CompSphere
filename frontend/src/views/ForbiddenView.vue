<script setup lang="ts">
import { useI18n } from 'vue-i18n';
const { t } = useI18n();
</script>
<template>
  <div class="page-heading">
    <h1 id="page-title" tabindex="-1">{{ t('forbiddenTitle') }}</h1>
  </div>
  <el-result icon="warning" :title="t('noAccess')" :sub-title="t('forbiddenHint')"
    ><template #extra
      ><router-link to="/" class="primary-link">{{ t('discover') }}</router-link></template
    ></el-result
  >
</template>
