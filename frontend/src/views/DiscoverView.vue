<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { z } from 'zod';
import { api } from '../api';
import { competitionSchema } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import { formatEventDateTime } from '../utils/format';
const { t } = useI18n();
const items = ref<z.infer<typeof competitionSchema>[]>([]);
const loading = ref(true),
  error = ref<unknown>(null),
  page = ref(1),
  total = ref(0);
async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = await api.competitions(page.value);
    items.value = data.items;
    total.value = data.total;
  } catch (e) {
    error.value = e;
    items.value = [];
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('discover') }}</h1>
      <p>{{ t('discoverHint') }}</p>
    </div>
  </div>
  <ErrorNotice :error="error" @retry="load" />
  <el-skeleton v-if="loading" :rows="6" animated />
  <el-empty v-else-if="!error && !items.length" :description="t('noCompetition')">
    <p>{{ t('noCompetitionHint') }}</p>
  </el-empty>
  <div v-else class="competition-grid">
    <article v-for="item in items" :key="item.id" class="competition-item">
      <div class="competition-art">
        <span>{{ item.public_code }}</span><strong>{{
          item.editions[0]?.name || item.name
        }}</strong>
      </div>
      <div class="competition-copy">
        <h2>{{ item.name }}</h2>
        <p>{{ item.summary }}</p>
        <ul class="edition-list">
          <li v-for="edition in item.editions" :key="edition.id">
            <div>
              <strong>{{ edition.name }}</strong>
              <p>{{ t('deadline') }} {{ formatEventDateTime(edition.enroll_end) }}</p>
            </div>
            <router-link :to="`/editions/${edition.id}`">{{ t('details') }}</router-link>
          </li>
        </ul>
      </div>
    </article>
  </div>
  <el-pagination
    v-if="total > 20"
    v-model:current-page="page"
    :total="total"
    :page-size="20"
    layout="prev, pager, next"
    @current-change="load"
  />
</template>
