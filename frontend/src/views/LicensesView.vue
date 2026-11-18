<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessageBox } from 'element-plus';
import { z } from 'zod';
import { api } from '../api';
import { seasonRegistrationSchema, seasonSchema, type Team } from '../api/schemas';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
const { t } = useI18n(),
  session = useSession();
const items = ref<z.infer<typeof seasonRegistrationSchema>[]>([]),
  teams = ref<Team[]>([]),
  season = ref<z.infer<typeof seasonSchema> | null>(null),
  teamId = ref<number>(),
  loading = ref(true),
  saving = ref(false),
  error = ref<unknown>(null);
async function load() {
  loading.value = true;
  error.value = null;
  try {
    items.value = (await api.seasonRegistrations()).items;
    if (session.hasAny('team:request_season_registration')) {
      teams.value = (await api.teams()).items;
      season.value = await api.season();
    }
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
}
async function create() {
  if (!teamId.value || !season.value) return;
  try {
    await ElMessageBox.confirm(t('licenseConfirm'), t('applyLicense'), {
      confirmButtonText: t('submit'),
      cancelButtonText: t('cancel'),
    });
    saving.value = true;
    const item = await api.createSeasonRegistration({
      team_id: teamId.value,
      season_id: season.value.id,
    });
    await api.submitSeasonRegistration(item.id);
    await load();
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') error.value = e;
  } finally {
    saving.value = false;
  }
}
async function review(item: unknown, action: 'approve' | 'reject') {
  try {
    const record = seasonRegistrationSchema.parse(item);
    const result = await ElMessageBox.prompt(t('reviewConfirm'), t(action), {
      inputType: 'textarea',
      inputPlaceholder: t('comment'),
      inputValidator: (v: string) => !!v?.trim() || t('required'),
      confirmButtonText: t(action),
      cancelButtonText: t('cancel'),
    });
    saving.value = true;
    await api.reviewSeasonRegistration(record.id, action, result.value);
    await load();
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') error.value = e;
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <h1 id="page-title" tabindex="-1">{{ t('licenses') }}</h1>
  </div>
  <ErrorNotice :error="error" @retry="load" />
  <section v-if="session.hasAny('team:request_season_registration')" class="content-panel">
    <h2>{{ t('applyLicense') }}</h2>
    <p>{{ season?.name || t('none') }}</p>
    <el-form label-position="top" @submit.prevent="create"
      ><el-form-item :label="t('team')"
        ><el-select v-model="teamId"
          ><el-option
            v-for="team in teams"
            :key="team.id"
            :value="team.id"
            :label="`${team.team_code} · ${team.name}`" /></el-select></el-form-item
      ><el-button
        type="primary"
        native-type="submit"
        :loading="saving"
        :disabled="!teamId || !season"
        >{{ t('applyLicense') }}</el-button
      ></el-form
    >
  </section>
  <el-skeleton v-if="loading" :rows="6" animated /><el-empty
    v-else-if="!error && !items.length"
    :description="t('none')"
  />
  <section v-else class="content-panel">
    <el-table :data="items"
      ><el-table-column prop="team_id" :label="t('team')" /><el-table-column
        prop="season_id"
        :label="t('season')"
      /><el-table-column :label="t('status')"
        ><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column
      ><el-table-column :label="t('reviews')" min-width="180"
        ><template #default="{ row }"
          ><template
            v-if="
              row.status === 'submitted' &&
              row.submitted_by !== session.me?.user.id &&
              session.hasAny('team:review_season_registration')
            "
            ><el-button type="primary" :loading="saving" @click="review(row, 'approve')">{{
              t('approve')
            }}</el-button
            ><el-button @click="review(row, 'reject')">{{ t('reject') }}</el-button></template
          ></template
        ></el-table-column
      ></el-table
    >
  </section>
</template>
