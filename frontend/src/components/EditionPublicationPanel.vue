<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessageBox } from 'element-plus';
import { api } from '../api';
import type { EditionPublicationChecks, ManagedEdition } from '../api/schemas';
import { useSession } from '../stores/session';
import { hasEditionPermission } from '../utils/permissions';
import ErrorNotice from './ErrorNotice.vue';

const props = defineProps<{ edition: ManagedEdition; revision: number }>();
const emit = defineEmits<{ published: [edition: ManagedEdition] }>();
const { t } = useI18n();
const session = useSession();
const checks = ref<EditionPublicationChecks>();
const loading = ref(false);
const publishing = ref(false);
const published = ref(false);
const loadError = ref<unknown>(null);
const publishError = ref<unknown>(null);
const checklist = [
  'active_season',
  'title_and_venue',
  'ordered_schedule',
  'open_offering',
  'supported_rules',
] as const satisfies readonly (keyof EditionPublicationChecks)[];
const ready = computed(
  () => !loading.value && checks.value && checklist.every((key) => checks.value?.[key]),
);
const canPublish = computed(
  () =>
    props.edition.status === 'draft' &&
    hasEditionPermission(
      session.me,
      'edition:publish',
      props.edition.id,
      props.edition.competition_id,
    ),
);
let requestSequence = 0;

async function load() {
  const current = ++requestSequence;
  loading.value = true;
  loadError.value = null;
  checks.value = undefined;
  try {
    const result = await api.editionPublicationChecks(props.edition.id);
    if (current === requestSequence) checks.value = result;
  } catch (error) {
    if (current === requestSequence) loadError.value = error;
  } finally {
    if (current === requestSequence) loading.value = false;
  }
}

async function publish() {
  if (!ready.value || publishing.value) return;
  publishing.value = true;
  try {
    try {
      await ElMessageBox.confirm(
        t('publication.editionConfirm', { name: props.edition.name }),
        t('publication.editionAction'),
        {
          type: 'warning',
          cancelButtonText: t('cancel'),
          confirmButtonText: t('publication.editionAction'),
        },
      );
    } catch {
      return;
    }
    publishError.value = null;
    const edition = await api.publishEdition(props.edition.id);
    published.value = true;
    emit('published', edition);
  } catch (error) {
    publishError.value = error;
    await load();
  } finally {
    publishing.value = false;
  }
}

watch(
  () => props.revision,
  () => {
    if (props.edition.status === 'draft') void load();
  },
  { immediate: true },
);
</script>

<template>
  <section
    v-if="edition.status === 'draft' || published"
    class="content-panel"
    aria-labelledby="edition-publication-title"
  >
    <div class="publication-header">
      <div>
        <h2 id="edition-publication-title">{{ t('publication.title') }}</h2>
        <p class="muted">{{ t('publication.hint') }}</p>
      </div>
      <el-button
        v-if="canPublish"
        type="primary"
        :disabled="!ready"
        :loading="publishing"
        @click="publish"
        >{{ t('publication.editionAction') }}</el-button
      >
    </div>
    <div role="status">
      <p v-if="published">{{ t('publication.editionDone') }}</p>
    </div>
    <ErrorNotice v-if="publishError" :error="publishError" />
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <ul v-else-if="checks && !published" class="publication-list">
      <li v-for="key in checklist" :key="key">
        <span>{{ t(`publication.${key}`) }}</span>
        <el-tag :type="checks[key] ? 'success' : 'warning'" effect="light">{{
          t(checks[key] ? 'publication.ready' : 'publication.missing')
        }}</el-tag>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.publication-header,
.publication-list li {
  display: flex;
  gap: 8px 16px;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
}
.publication-header h2,
.publication-header p {
  margin: 0;
}
.publication-list {
  padding: 0;
  list-style: none;
  margin-block-end: 0;
}
.publication-list li {
  padding-block: 10px;
  border-block-start: 1px solid var(--color-border);
}
</style>
