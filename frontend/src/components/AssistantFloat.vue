<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { Close } from '@element-plus/icons-vue';
const { t } = useI18n();
const route = useRoute();
const open = ref(false);
const inspect = ref(false);
// Only route names are collected; raw query, form data and DOM never enter this context.
const context = computed(() => ({ page: typeof route.name === 'string' ? route.name : 'unknown' }));
function clear() {
  inspect.value = false;
}
window.addEventListener('session-cleared', clear);
onUnmounted(() => window.removeEventListener('session-cleared', clear));
</script>
<template>
  <aside v-if="open" id="assistant-panel" class="assistant-panel" :aria-label="t('assistant')">
    <header>
      <strong>{{ t('assistant') }}</strong><el-button text @click="clear">{{
        t('clear')
      }}</el-button
      ><el-button text :aria-label="t('close')" @click="open = false"
        ><el-icon><Close /></el-icon
      ></el-button>
    </header>
    <div class="assistant-body">
      <h2>{{ t('assistantUnavailable') }}</h2>
      <p>{{ t('assistantHint') }}</p>
      <el-button @click="inspect = !inspect">{{ t('assistantContext') }}</el-button>
      <pre v-if="inspect">{{ JSON.stringify(context, null, 2) }}</pre>
    </div>
  </aside>
  <el-button
    class="assistant-ball"
    circle
    :aria-label="t('assistant')"
    :aria-expanded="open"
    aria-controls="assistant-panel"
    @click="open = !open"
    >AI</el-button
  >
</template>
