<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { Edition } from '../api/schemas';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
import { formatEventDateTime } from '../utils/format';
const route = useRoute(),
  session = useSession(),
  { t } = useI18n();
const edition = ref<Edition>(),
  loading = ref(true),
  error = ref<unknown>(null);
async function load() {
  loading.value = true;
  error.value = null;
  try {
    edition.value = await api.edition(Number(route.params.id));
  } catch (e) {
    error.value = e;
    edition.value = undefined;
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
<template>
  <router-link to="/" class="back-link">{{ t('back') }}</router-link>
  <ErrorNotice :error="error" @retry="load" /><el-skeleton v-if="loading" :rows="8" animated />
  <template v-if="edition"
    ><div class="event-heading">
      <h1 id="page-title" tabindex="-1">{{ edition.name }}</h1>
      <p>{{ t('venue') }} · {{ edition.venue }}</p>
      <p>{{ t('deadline') }} · {{ formatEventDateTime(edition.enroll_end) }}</p>
      <router-link
        v-if="session.hasAny('registration:create')"
        class="primary-link"
        :to="`/registrations/new/${edition.id}`"
        >{{ t('enroll') }}</router-link><router-link
        v-else-if="!session.authenticated"
        class="primary-link"
        :to="{ name: 'login', query: { next: `/registrations/new/${edition.id}` } }"
        >{{ t('login') }}</router-link
      >
    </div>
    <section class="content-panel">
      <h2>{{ t('group') }}</h2>
      <el-table :data="edition.offerings" table-layout="auto"
        ><el-table-column prop="event_name" :label="t('event')" /><el-table-column
          prop="group_name"
          :label="t('group')"
        /><el-table-column :label="t('members')"
          ><template #default="{ row }"
            >{{ row.min_members }}–{{ row.max_members }}</template
          ></el-table-column
        ><el-table-column :label="t('materials')" min-width="180"
          ><template #default="{ row }">{{
            row.required_materials.join('、') || t('noMaterials')
          }}</template></el-table-column
        ></el-table
      >
    </section>
  </template>
</template>
