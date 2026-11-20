<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { api } from '../api';
import type { Dashboard } from '../api/schemas';
import ErrorNotice from '../components/ErrorNotice.vue';
import { useSession } from '../stores/session';

const { t } = useI18n();
const session = useSession();
const data = ref<Dashboard>();
const loading = ref(true);
const error = ref<unknown>(null);
const platform = computed(
  () => session.hasAny('stats:read_platform') && data.value?.users !== undefined,
);
const rate = computed(() =>
  data.value?.approval_rate == null ? '—' : `${Math.round(data.value.approval_rate * 100)}%`,
);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    data.value = await api.dashboard();
  } catch (e) {
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
      <h1 id="page-title" tabindex="-1">{{ t('dashboard') }}</h1>
      <p>{{ t('dashboardHint') }}</p>
    </div>
  </div>
  <p v-if="loading" role="status">{{ t('loading') }}</p>
  <ErrorNotice v-else-if="error" :error="error" @retry="load" />
  <template v-else-if="data">
    <section class="content-panel stat-grid">
      <dl>
        <div>
          <dt>{{ t('statRegistrations') }}</dt>
          <dd class="mono">{{ data.registrations }}</dd>
        </div>
        <div>
          <dt>{{ t('statApproved') }}</dt>
          <dd class="mono">{{ data.approved }}</dd>
        </div>
        <div>
          <dt>{{ t('statApprovalRate') }}</dt>
          <dd class="mono">{{ rate }}</dd>
        </div>
        <div>
          <dt>{{ t('statAwarded') }}</dt>
          <dd class="mono">{{ data.awarded }}</dd>
        </div>
        <template v-if="platform">
          <div>
            <dt>{{ t('statUsers') }}</dt>
            <dd class="mono">{{ data.users }}</dd>
          </div>
          <div>
            <dt>{{ t('statOrganizations') }}</dt>
            <dd class="mono">{{ data.organizations }}</dd>
          </div>
          <div>
            <dt>{{ t('statCompetitions') }}</dt>
            <dd class="mono">{{ data.competitions }}</dd>
          </div>
          <div>
            <dt>{{ t('statEditions') }}</dt>
            <dd class="mono">{{ data.editions }}</dd>
          </div>
        </template>
      </dl>
    </section>
    <section class="content-panel">
      <h2>{{ t('statByOffering') }}</h2>
      <p v-if="!data.by_offering.length" class="muted">{{ t('none') }}</p>
      <el-table v-else :data="data.by_offering">
        <el-table-column prop="event_name" :label="t('event')" />
        <el-table-column prop="group_name" :label="t('group')" />
        <el-table-column prop="submitted" :label="t('statRegistrations')" />
        <el-table-column prop="approved" :label="t('statApproved')" />
      </el-table>
    </section>
  </template>
</template>

<style scoped>
.stat-grid dl {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
  gap: 16px;
}
.stat-grid dt {
  font-size: 12px;
  color: var(--color-text-secondary, inherit);
}
.stat-grid dd {
  margin: 4px 0 0;
  font-size: 28px;
  font-weight: 600;
}
.mono {
  font-variant-numeric: tabular-nums;
}
</style>
