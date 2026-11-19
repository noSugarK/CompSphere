<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import zh from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';
import { Bell, Moon, Sunny, Monitor } from '@element-plus/icons-vue';
import { api } from './api';
import { ApiError } from './api/client';
import { useSession } from './stores/session';
import ErrorNotice from './components/ErrorNotice.vue';
import AssistantFloat from './components/AssistantFloat.vue';
import { mayRenderPrivate, mayViewCompetitionRegistry } from './utils/permissions';

const session = useSession();
const route = useRoute();
const router = useRouter();
const { t, locale } = useI18n();
const theme = ref<'light' | 'dark' | 'system'>('system');
const preferenceError = ref<unknown>(null);
const sessionGeneration = ref(0);
function clearPrivateView() {
  if (route.meta.auth) {
    sessionGeneration.value += 1;
    void router.replace({ name: 'login' });
  }
}
window.addEventListener('session-cleared', clearPrivateView);
onUnmounted(() => window.removeEventListener('session-cleared', clearPrivateView));
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
const applyTheme = () =>
  document.documentElement.classList.toggle(
    'dark',
    theme.value === 'dark' || (theme.value === 'system' && systemTheme.matches),
  );
systemTheme.addEventListener('change', applyTheme);
onUnmounted(() => systemTheme.removeEventListener('change', applyTheme));
watch(theme, applyTheme, { immediate: true });
watch(
  () => session.me,
  (me) => {
    if (me) {
      locale.value = me.locale;
      theme.value = me.theme;
    }
  },
);
watch(
  locale,
  (value) => {
    document.documentElement.lang = value;
    document.title = `${t(typeof route.meta.title === 'string' ? route.meta.title : 'app')} · ${t('app')}`;
  },
  { immediate: true },
);
const isManager = computed(() =>
  ['approval:review_single', 'team:create', 'team:review_create', 'team:review'].some(
    session.hasAny,
  ),
);
const inAdmin = computed(
  () =>
    ['competitionRegistry', 'seasonManagement'].includes(String(route.name)) ||
    (isManager.value && ['requests', 'licenses', 'reviews'].includes(String(route.name))),
);
const links = computed(() =>
  [
    { name: 'discover', path: '/', visible: true },
    {
      name: 'competitionRegistry',
      path: '/competition-registry',
      visible: mayViewCompetitionRegistry(session.me),
    },
    {
      name: 'seasonManagement',
      path: '/season-management',
      visible: session.hasAny('season:read'),
    },
    {
      name: 'registrations',
      path: '/registrations',
      visible: session.hasAny('registration:read_own'),
    },
    {
      name: 'teams',
      path: '/teams',
      visible: ['team:read', 'team:leave_own'].some(session.hasAny),
    },
    {
      name: 'requests',
      path: '/team-requests',
      visible: ['team:create', 'team:review_create', 'team:review'].some(session.hasAny),
    },
    {
      name: 'licenses',
      path: '/season-licenses',
      visible: ['team:request_season_registration', 'team:review_season_registration'].some(
        session.hasAny,
      ),
    },
    { name: 'reviews', path: '/reviews', visible: session.hasAny('approval:review_single') },
  ].filter((link) => link.visible),
);
async function preferences(change: 'locale' | 'theme') {
  const nextLocale =
    change === 'locale' ? (locale.value === 'zh-CN' ? 'en-US' : 'zh-CN') : locale.value;
  const options = ['light', 'dark', 'system'] as const;
  const nextTheme =
    change === 'theme'
      ? (options[(options.indexOf(theme.value) + 1) % 3] ?? 'system')
      : theme.value;
  locale.value = nextLocale;
  theme.value = nextTheme;
  preferenceError.value = null;
  if (session.authenticated)
    try {
      await api.preferences({ locale: nextLocale, theme: nextTheme });
    } catch (e) {
      preferenceError.value = e;
    }
}
async function logout() {
  try {
    await session.logout();
  } catch (e) {
    preferenceError.value = e;
  } finally {
    await router.replace('/');
  }
}
</script>
<template>
  <el-config-provider :locale="locale === 'zh-CN' ? zh : en">
    <a class="skip-link" href="#page-title">{{ t('skip') }}</a>
    <div class="app-shell" :class="{ 'has-sidebar': inAdmin }">
      <header class="app-header">
        <router-link to="/" class="brand"
          ><span class="brand-mark" aria-hidden="true">C</span
          ><span>{{ t('app') }}<small>COMPSPHERE</small></span></router-link
        >
        <nav class="top-nav" :aria-label="t('ownership')">
          <router-link v-for="link in links" :key="link.name" :to="link.path">{{
            t(link.name)
          }}</router-link>
        </nav>
        <div class="header-actions">
          <el-button text @click="preferences('locale')">{{
            locale === 'zh-CN' ? 'EN' : '中文'
          }}</el-button>
          <el-button text :aria-label="t(theme)" @click="preferences('theme')"
            ><el-icon
              ><Moon v-if="theme === 'dark'" /><Sunny v-else-if="theme === 'light'" /><Monitor
                v-else /></el-icon
          ></el-button>
          <template v-if="session.authenticated">
            <router-link
              :to="{ name: 'notifications' }"
              class="header-inbox"
              :aria-label="t('notifications')"
              :title="t('notifications')"
            >
              <el-icon aria-hidden="true"><Bell /></el-icon>
            </router-link>
            <span class="account-name">{{
              session.me?.profile?.real_name || session.me?.user.username
            }}</span><el-button text @click="logout">{{ t('logout') }}</el-button></template
          >
          <router-link v-else to="/login" class="login-link">{{ t('login') }}</router-link>
        </div>
      </header>
      <aside v-if="inAdmin" class="admin-sidebar">
        <p>{{ t('work') }}</p>
        <nav :aria-label="t('manage')">
          <router-link v-for="link in links" :key="link.name" :to="link.path">{{
            t(link.name)
          }}</router-link>
        </nav>
        <span class="sidebar-foot">COMPSPHERE</span>
      </aside>
      <main class="main-content">
        <ErrorNotice v-if="preferenceError" :error="preferenceError" />
        <ErrorNotice v-if="session.initializationError" :error="new ApiError(50301)" />
        <router-view v-slot="{ Component }"
          ><component
            v-if="mayRenderPrivate(route.meta.auth, session.authenticated)"
            :is="Component"
            :key="`${route.fullPath}:${sessionGeneration}`"
        /></router-view>
      </main>
      <footer class="app-footer">
        COMPSPHERE <span>{{ t('recordsHint') }}</span>
      </footer>
    </div>
    <AssistantFloat />
  </el-config-provider>
</template>
