<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { Team } from '../api/schemas';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
import StatusTag from '../components/StatusTag.vue';
const session = useSession(),
  { t } = useI18n();
const teams = ref<Team[]>([]),
  loading = ref(true),
  error = ref<unknown>(null),
  page = ref(1),
  total = ref(0);
async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = await api.teams(page.value);
    teams.value = data.items;
    total.value = data.total;
  } catch (e) {
    teams.value = [];
    error.value = e;
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('teams') }}</h1>
      <p>{{ t('emptyTeamsHint') }}</p>
    </div>
    <router-link v-if="session.hasAny('team:create')" to="/team-requests" class="primary-link">{{
      t('createTeam')
    }}</router-link>
  </div>
  <ErrorNotice :error="error" @retry="load" /><el-skeleton
    v-if="loading"
    :rows="7"
    animated
  /><el-empty v-else-if="!error && !teams.length" :description="t('emptyTeams')" />
  <article v-for="team in teams" :key="team.id" class="content-panel team-panel">
    <header>
      <div>
        <span class="team-number">{{ team.team_code }}</span>
        <h2>{{ team.name }}</h2>
      </div>
      <StatusTag :status="team.status" />
    </header>
    <p class="muted">{{ team.event_code }}</p>
    <el-table v-if="team.members" :data="team.members"
      ><el-table-column prop="real_name" :label="t('name')" /><el-table-column
        prop="school_level"
        :label="t('schoolLevel')" /><el-table-column prop="grade" :label="t('group')"
    /></el-table>
    <div class="license-row">
      <span>{{ t('licenses') }}</span><StatusTag
        v-for="license in team.season_registrations"
        :key="license.id"
        :status="license.status"
      />
    </div>
  </article>
  <el-pagination
    v-if="total > 20"
    v-model:current-page="page"
    :total="total"
    :page-size="20"
    layout="prev, pager, next"
    @current-change="load"
  />
</template>
