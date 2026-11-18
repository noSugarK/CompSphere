<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { Edition, Registration } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
const route = useRoute(),
  { t } = useI18n();
const reviewing = computed(() => route.name === 'reviews');
const items = ref<Registration[]>([]),
  editions = ref<Edition[]>([]),
  editionId = ref<number>(),
  page = ref(1),
  total = ref(0),
  status = ref(''),
  loading = ref(true),
  error = ref<unknown>(null);
async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = reviewing.value
      ? await api.registrations(editionId.value, page.value, status.value)
      : editionId.value
        ? await api.myRegistrations(editionId.value, page.value)
        : null;
    items.value = data?.items || [];
    total.value = data?.total || 0;
  } catch (e) {
    error.value = e;
    items.value = [];
  } finally {
    loading.value = false;
  }
}
onMounted(async () => {
  try {
    editions.value = (await api.competitions()).items.flatMap((item) => item.editions);
    if (!reviewing.value) editionId.value = editions.value[0]?.id;
    await load();
  } catch (e) {
    error.value = e;
    loading.value = false;
  }
});
</script>
<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t(reviewing ? 'reviews' : 'registrations') }}</h1>
      <p v-if="reviewing">{{ t('desktopHint') }}</p>
    </div>
  </div>
  <div class="filter-bar">
    <el-form
      inline
      label-position="top"
      @submit.prevent="
        page = 1;
        load();
      "
      ><el-form-item :label="t('selectEdition')"
        ><el-select
          v-model="editionId"
          :clearable="reviewing"
          @change="
            page = 1;
            load();
          "
          ><el-option
            v-for="edition in editions"
            :key="edition.id"
            :value="edition.id"
            :label="edition.name" /></el-select></el-form-item
      ><el-form-item v-if="reviewing" :label="t('status')"
        ><el-select
          v-model="status"
          @change="
            page = 1;
            load();
          "
          ><el-option value="" :label="t('all')" /><el-option
            v-for="s in ['pending_review', 'approved', 'returned', 'rejected']"
            :key="s"
            :value="s"
            :label="t(s)" /></el-select></el-form-item
    ></el-form>
  </div>
  <ErrorNotice :error="error" @retry="load" /><el-skeleton
    v-if="loading"
    :rows="7"
    animated
  /><el-empty v-else-if="!error && !items.length" :description="t('none')" />
  <section v-else class="content-panel">
    <el-table :data="items"
      ><el-table-column
        prop="batch_no"
        :label="t('registrations')"
        min-width="170"
      /><el-table-column prop="team_id" :label="t('team')" /><el-table-column
        :label="t('status')"
        min-width="120"
        ><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column
      ><el-table-column :label="t('details')" min-width="110"
        ><template #default="{ row }"
          ><router-link :to="`/registrations/${row.id}`">{{ t('details') }}</router-link></template
        ></el-table-column
      ></el-table
    >
  </section>
  <el-pagination
    v-if="total > 20"
    v-model:current-page="page"
    :total="total"
    :page-size="20"
    layout="prev, pager, next"
    @current-change="load"
  />
</template>
