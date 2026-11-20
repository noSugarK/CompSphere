<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import { ApiError } from '../api/client';
import type { Edition, PublicRoster, PublicRosterEntry } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';

const { t } = useI18n();
const route = useRoute();
const editionId = Number(route.params.id);
const data = ref<PublicRoster>();
const offerings = ref<Edition['offerings']>([]);
const loading = ref(true);
const error = ref<unknown>(null);
const gated = ref(false);
const eventId = ref<number>();
const groupId = ref<number>();

// 02 §4.7：列 = 服务端常量 ∩ 届次白名单；被裁字段整列消失，顺序随 publish_fields。
const shows = (key: string) => data.value?.publish_fields.includes(key) ?? false;
const eventOptions = computed(() => {
  const map = new Map<number, string>();
  for (const item of offerings.value) map.set(item.event_id, item.event_name);
  return map;
});
const groupOptions = computed(() => {
  const map = new Map<number, string>();
  for (const item of offerings.value)
    if (eventId.value === undefined || item.event_id === eventId.value)
      map.set(item.group_id, item.group_name);
  return map;
});

async function load() {
  loading.value = true;
  error.value = null;
  gated.value = false;
  try {
    data.value = await api.publicRoster(editionId, {
      event: eventId.value,
      group: groupId.value,
    });
  } catch (e) {
    if (e instanceof ApiError && e.code === 40101) {
      gated.value = true;
      data.value = undefined;
    } else {
      error.value = e;
    }
  } finally {
    loading.value = false;
  }
}
async function pick(event?: number, group?: number) {
  eventId.value = event;
  groupId.value = group;
  await load();
}
onMounted(async () => {
  await load();
  try {
    offerings.value = (await api.edition(editionId)).offerings;
  } catch {
    offerings.value = [];
  }
});
</script>

<template>
  <div class="page-heading">
    <div>
      <RouterLink to="/">{{ t('discover') }}</RouterLink>
      <h1 id="page-title" tabindex="-1">{{ data?.edition_name ?? t('publicRoster') }}</h1>
      <p>{{ t('publicRosterHint') }}</p>
    </div>
  </div>
  <p v-if="loading" role="status">{{ t('loading') }}</p>
  <ErrorNotice v-else-if="error" :error="error" @retry="load" />
  <section v-else-if="gated" class="content-panel">
    <p>{{ t('publicRosterLogin') }}</p>
    <RouterLink class="primary-link" :to="{ name: 'login', query: { next: route.fullPath } }">{{
      t('login')
    }}</RouterLink>
  </section>
  <section v-else-if="data" class="content-panel">
    <div v-if="eventOptions.size" class="roster-filters">
      <el-select
        :model-value="eventId"
        clearable
        :placeholder="t('publicRosterAllEvents')"
        class="roster-filter"
        @update:model-value="pick($event as number | undefined, undefined)"
        ><el-option
          v-for="[id, name] in eventOptions"
          :key="id"
          :value="id"
          :label="name" /></el-select
      ><el-select
        v-if="groupOptions.size"
        :model-value="groupId"
        clearable
        :placeholder="t('publicRosterAllGroups')"
        class="roster-filter"
        @update:model-value="pick(eventId, $event as number | undefined)"
        ><el-option v-for="[id, name] in groupOptions" :key="id" :value="id" :label="name"
      /></el-select>
    </div>
    <p v-if="!data.entries.length" class="muted">{{ t('publicRosterEmpty') }}</p>
    <el-table v-else :data="data.entries" table-layout="auto">
      <el-table-column v-if="shows('team_code')" prop="team_code" :label="t('teamCode')" />
      <el-table-column v-if="shows('org_name')" prop="org_name" :label="t('org')" />
      <el-table-column v-if="shows('event')" prop="event" :label="t('event')" />
      <el-table-column v-if="shows('group')" prop="group" :label="t('group')" />
      <el-table-column v-if="shows('member_names')" :label="t('members')" min-width="200">
        <template #default="{ row }: { row: PublicRosterEntry }">
          {{ (row.member_names ?? []).join('、') }}
        </template>
      </el-table-column>
      <el-table-column v-if="shows('award')" prop="award" :label="t('awardName')" />
    </el-table>
  </section>
</template>

<style scoped>
.roster-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-block-end: 16px;
}
.roster-filter {
  min-inline-size: 180px;
}
</style>
