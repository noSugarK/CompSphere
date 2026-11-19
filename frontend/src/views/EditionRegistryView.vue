<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { Plus } from '@element-plus/icons-vue';
import { api } from '../api';
import type { ManagedEdition, ManagedSeason } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
import { useSession } from '../stores/session';
import { formatEventDateTime } from '../utils/format';
import { mayCreateEdition, mayViewCompetitionRegistry } from '../utils/permissions';

const { t } = useI18n();
const route = useRoute();
const session = useSession();
const competitionId = Number(route.params.id);
const items = ref<ManagedEdition[]>([]);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const loading = ref(true);
const loadError = ref<unknown>(null);
const open = ref(false);
const saving = ref(false);
const loadingSeasons = ref(false);
const seasons = ref<ManagedSeason[]>([]);
const seasonError = ref<unknown>(null);
const saveError = ref<unknown>(null);
const timeError = ref(false);
const created = ref('');
const blank = {
  season_id: undefined as number | undefined,
  year: '',
  edition_no: '',
  name: '',
  venue: '',
  enroll_start: '',
  enroll_end: '',
  start_date: '',
  end_date: '',
};
const form = reactive({ ...blank });
const timeFields = [
  ['enroll_start', 'editionEnrollStart'],
  ['enroll_end', 'editionEnrollEnd'],
  ['start_date', 'editionEventStart'],
  ['end_date', 'editionEventEnd'],
] as const;

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    const result = await api.managedEditions(competitionId, page.value);
    items.value = result.items;
    pageSize.value = result.page_size;
    total.value = result.total;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

async function loadSeasons() {
  loadingSeasons.value = true;
  seasonError.value = null;
  seasons.value = [];
  try {
    const first = await api.eligibleEditionSeasons(competitionId);
    const pages = Math.ceil(first.total / first.page_size);
    const options = [...first.items];
    for (let index = 2; index <= pages; index += 1) {
      options.push(...(await api.eligibleEditionSeasons(competitionId, index)).items);
    }
    seasons.value = options;
    form.season_id = options.find((item) => item.is_default)?.id ?? options[0]?.id;
  } catch (error) {
    seasonError.value = error;
  } finally {
    loadingSeasons.value = false;
  }
}

function startDraft() {
  Object.assign(form, blank);
  saveError.value = null;
  timeError.value = false;
  created.value = '';
  open.value = true;
  void loadSeasons();
}

async function saveDraft() {
  if (saving.value || !form.season_id) return;
  timeError.value = !(
    form.enroll_start < form.enroll_end &&
    form.enroll_end <= form.start_date &&
    form.start_date < form.end_date
  );
  if (timeError.value) return;
  saving.value = true;
  saveError.value = null;
  try {
    const result = await api.createEdition(competitionId, {
      ...form,
      year: Number(form.year),
      edition_no: Number(form.edition_no),
      time_zone: 'Asia/Shanghai',
    });
    created.value = result.name;
    open.value = false;
    page.value = 1;
    await load();
  } catch (error) {
    saveError.value = error;
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-heading">
    <div>
      <RouterLink
        v-if="mayViewCompetitionRegistry(session.me)"
        :to="{ name: 'competitionRegistry' }"
        >{{ t('competitionRegistry') }}</RouterLink
      >
      <h1 id="page-title" tabindex="-1">{{ t('editionRegistry') }}</h1>
      <p>{{ t('editionRegistryHint', { id: competitionId }) }}</p>
    </div>
    <el-button
      v-if="!loading && !loadError && mayCreateEdition(session.me, competitionId)"
      type="primary"
      :icon="Plus"
      :disabled="saving"
      @click="startDraft"
      >{{ t('editionCreate') }}</el-button
    >
  </div>
  <div role="status">
    <p v-if="created">{{ t('competitionCreated', { name: created }) }}</p>
  </div>
  <div class="content-panel">
    <p v-if="loading">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="loadError" :error="loadError" @retry="load" />
    <p v-else-if="!items.length" class="muted">{{ t('none') }}</p>
    <ul v-else class="edition-list">
      <li v-for="item in items" :key="item.id" class="edition-row">
        <div>
          <h2>{{ item.name }}</h2>
          <p class="muted small">
            {{ t('editionIdentity', { year: item.year, number: item.edition_no }) }}
          </p>
        </div>
        <p class="small">
          {{ t('editionEventStart') }}
          <time :datetime="item.start_date">{{ formatEventDateTime(item.start_date) }}</time>
        </p>
        <StatusTag :status="item.status" />
      </li>
    </ul>
  </div>
  <el-pagination
    v-if="total > pageSize"
    :current-page="page"
    :page-size="pageSize"
    :total="total"
    :disabled="loading || saving"
    :pager-count="5"
    layout="prev, pager, next"
    @update:current-page="
      (value: number) => {
        page = value;
        load();
      }
    "
  />
  <el-dialog
    v-model="open"
    :title="t('editionCreate')"
    width="min(680px, calc(100% - 32px))"
    :show-close="!saving && !loadingSeasons"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving && !loadingSeasons"
  >
    <p v-if="loadingSeasons">{{ t('loading') }}</p>
    <ErrorNotice v-else-if="seasonError" :error="seasonError" @retry="loadSeasons" />
    <p v-else-if="!seasons.length" class="muted">{{ t('editionNoSeasons') }}</p>
    <el-form v-else label-position="top" @submit.prevent="saveDraft">
      <ErrorNotice v-if="saveError" :error="saveError" />
      <el-form-item :label="t('editionSeason')" required>
        <el-select v-model="form.season_id" :disabled="saving">
          <el-option
            v-for="season in seasons"
            :key="season.id"
            :label="season.name"
            :value="season.id"
          />
        </el-select>
      </el-form-item>
      <div class="edition-fields">
        <el-form-item :label="t('editionYear')" required
          ><el-input
            v-model="form.year"
            :disabled="saving"
            type="number"
            min="1"
            max="9999"
            required
        /></el-form-item>
        <el-form-item :label="t('editionNumber')" required
          ><el-input
            v-model="form.edition_no"
            :disabled="saving"
            type="number"
            min="1"
            max="9999"
            required
        /></el-form-item>
        <el-form-item :label="t('editionName')" required
          ><el-input v-model.trim="form.name" :disabled="saving" maxlength="128" required
        /></el-form-item>
        <el-form-item :label="t('editionVenue')" required
          ><el-input v-model.trim="form.venue" :disabled="saving" maxlength="255" required
        /></el-form-item>
      </div>
      <p id="edition-time-help" class="muted small">{{ t('editionTimeZone') }}</p>
      <div class="edition-fields">
        <el-form-item v-for="[field, label] in timeFields" :key="field" :label="t(label)" required>
          <el-input
            v-model="form[field]"
            :disabled="saving"
            type="datetime-local"
            aria-describedby="edition-time-help"
            required
            @input="timeError = false"
          />
        </el-form-item>
      </div>
      <el-alert
        v-if="timeError"
        :title="t('editionTimeOrder')"
        type="error"
        :closable="false"
        role="alert"
      />
      <div class="edition-actions">
        <el-button :disabled="saving" @click="open = false">{{ t('cancel') }}</el-button>
        <el-button type="primary" native-type="submit" :loading="saving">{{ t('save') }}</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.edition-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.edition-row {
  display: flex;
  gap: 8px 20px;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  padding-block: 12px;
  overflow-wrap: anywhere;
}
.edition-row + .edition-row {
  border-block-start: 1px solid var(--color-border);
}
.edition-row h2,
.edition-row p {
  margin: 0;
}
.edition-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}
.edition-actions {
  display: flex;
  justify-content: flex-end;
  margin-block-start: 12px;
}
@media (max-width: 560px) {
  .edition-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
