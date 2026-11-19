<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { Edition, Registration } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
const { t } = useI18n();
const items = ref<Registration[]>([]),
  editions = ref<Edition[]>([]),
  editionId = ref<number>(),
  page = ref(1),
  total = ref(0),
  loading = ref(true),
  error = ref<unknown>(null);
async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = editionId.value ? await api.myRegistrations(editionId.value, page.value) : null;
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
    editionId.value = editions.value[0]?.id;
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
      <h1 id="page-title" tabindex="-1">{{ t('registrations') }}</h1>
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
          @change="
            page = 1;
            load();
          "
          ><el-option
            v-for="edition in editions"
            :key="edition.id"
            :value="edition.id"
            :label="edition.name" /></el-select></el-form-item
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
