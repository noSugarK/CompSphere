import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from '../api';
import {
  ApiError,
  clearSessionToken,
  logoutSession,
  onSessionExpired,
  refreshSession,
  setSessionToken,
} from '../api/client';
import type { Me } from '../api/schemas';

export const useSession = defineStore('session', () => {
  const me = ref<Me | null>(null);
  const initialized = ref(false);
  const initializationError = ref(false);
  const authenticated = computed(() => me.value !== null);
  const hasAny = (permission: string) =>
    me.value?.grants.some((g) => g.permissions.includes(permission)) ?? false;
  // This only drives navigation. Backend scope checks remain authoritative.
  const hasPerm = (
    permission: string,
    scope?: { org_id?: number; edition_id?: number; competition_id?: number },
  ) =>
    me.value?.grants.some(
      (g) =>
        g.permissions.includes(permission) &&
        (g.scope_type === 'global' ||
          !scope ||
          (g.scope_type === 'org' && g.scope_id === scope.org_id) ||
          (g.scope_type === 'edition' && g.scope_id === scope.edition_id) ||
          (g.scope_type === 'competition' && g.scope_id === scope.competition_id)),
    ) ?? false;
  const clear = () => {
    me.value = null;
    window.dispatchEvent(new Event('session-cleared'));
  };
  onSessionExpired(clear);
  let initialization: Promise<void> | undefined;
  async function initialize() {
    if (initialized.value) return;
    initialization ||= (async () => {
      try {
        await refreshSession();
        me.value = await api.me();
      } catch (e) {
        if (!(e instanceof ApiError && e.code === 40101)) initializationError.value = true;
      } finally {
        initialized.value = true;
      }
    })();
    return initialization;
  }
  async function login(body: unknown) {
    clearSessionToken();
    clear();
    const result = await api.login(body);
    setSessionToken(result.access);
    try {
      me.value = await api.me();
      initializationError.value = false;
    } catch (e) {
      clearSessionToken();
      clear();
      throw e;
    }
  }
  async function logout() {
    await logoutSession();
  }
  async function reload() {
    me.value = await api.me();
  }
  return {
    me,
    initialized,
    initializationError,
    authenticated,
    hasAny,
    hasPerm,
    initialize,
    login,
    logout,
    reload,
  };
});
