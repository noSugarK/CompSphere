<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import type { FormInstance } from 'element-plus';
import { api } from '../api';
import { setSessionToken } from '../api/client';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
const { t } = useI18n(),
  session = useSession(),
  router = useRouter();
const fields = reactive({ old_password: '', new_password: '' }),
  form = ref<FormInstance>(),
  loading = ref(false),
  error = ref<unknown>(null);
async function submit() {
  if (!(await form.value?.validate().catch(() => false))) return;
  loading.value = true;
  error.value = null;
  try {
    const result = await api.changePassword(fields);
    setSessionToken(result.access);
    fields.old_password = '';
    fields.new_password = '';
    await session.reload();
    await router.push('/');
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <h1 id="page-title" tabindex="-1">{{ t('changePassword') }}</h1>
      <p>{{ t('mustChange') }}</p>
    </div>
  </div>
  <section class="content-panel narrow-panel">
    <ErrorNotice :error="error" /><el-form
      ref="form"
      :model="fields"
      label-position="top"
      action="/api/v1/auth/password/change"
      method="post"
      @submit.prevent="submit"
      :scroll-to-error="true"
      ><el-form-item
        prop="old_password"
        :label="t('oldPassword')"
        :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
        ><el-input
          v-model="fields.old_password"
          name="old_password"
          type="password"
          autocomplete="current-password"
          show-password
      /></el-form-item>
      <p id="password-hint" class="small muted">{{ t('passwordMin') }}</p>
      <el-form-item
        prop="new_password"
        :label="t('newPassword')"
        :rules="[
          { required: true, message: t('required'), trigger: 'blur' },
          { min: 12, message: t('passwordMin'), trigger: 'blur' },
        ]"
        ><el-input
          v-model="fields.new_password"
          name="new_password"
          type="password"
          autocomplete="new-password"
          aria-describedby="password-hint"
          show-password
          :maxlength="256" /></el-form-item
      ><el-button type="primary" native-type="submit" :loading="loading">{{
        t('changePassword')
      }}</el-button></el-form
    >
  </section>
</template>
