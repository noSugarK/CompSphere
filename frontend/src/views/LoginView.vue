<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import type { FormInstance } from 'element-plus';
import { loginSchema } from '../api/schemas';
import { useSession } from '../stores/session';
import ErrorNotice from '../components/ErrorNotice.vue';
const session = useSession(),
  route = useRoute(),
  router = useRouter(),
  { t } = useI18n();
const form = ref<FormInstance>();
const fields = reactive({
  login_type: 'email' as 'email' | 'document',
  email: '',
  password: '',
  document_type: 'id_card',
  document_country: 'CN',
  document_number: '',
});
const loading = ref(false),
  error = ref<unknown>(null);
async function submit() {
  if (!(await form.value?.validate().catch(() => false))) return;
  loading.value = true;
  error.value = null;
  try {
    const body = loginSchema.parse(
      fields.login_type === 'email'
        ? { login_type: 'email', email: fields.email, password: fields.password }
        : {
            login_type: 'document',
            document_type: fields.document_type,
            document_country: fields.document_country,
            document_number: fields.document_number,
            password: fields.password,
          },
    );
    await session.login(body);
    fields.password = '';
    fields.document_number = '';
    const next =
      typeof route.query.next === 'string' &&
      route.query.next.startsWith('/') &&
      !route.query.next.startsWith('//')
        ? route.query.next
        : '/';
    await router.push(session.me?.user.must_change_password ? '/password' : next);
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
}
</script>
<template>
  <div class="login-layout">
    <div class="login-statement">
      <h1 id="page-title" tabindex="-1">{{ t('login') }}</h1>
      <p>{{ t('loginHint') }}</p>
      <span>COMPSPHERE</span>
    </div>
    <div class="login-form content-panel">
      <ErrorNotice :error="error" />
      <el-form
        ref="form"
        :model="fields"
        label-position="top"
        action="/api/v1/auth/login"
        method="post"
        @submit.prevent="submit"
        :scroll-to-error="true"
      >
        <el-form-item
          ><el-radio-group v-model="fields.login_type" :aria-label="t('login')"
            ><el-radio-button value="email">{{ t('emailLogin') }}</el-radio-button
            ><el-radio-button value="document">{{
              t('documentLogin')
            }}</el-radio-button></el-radio-group
          ></el-form-item
        >
        <el-form-item
          v-if="fields.login_type === 'email'"
          prop="email"
          :label="t('email')"
          :rules="[
            { required: true, message: t('required'), trigger: 'blur' },
            { type: 'email', message: t('fieldError'), trigger: 'blur' },
          ]"
          ><el-input
            v-model="fields.email"
            id="login-email"
            name="email"
            type="email"
            autocomplete="username"
            :maxlength="255"
            autocapitalize="none"
            :spellcheck="false"
        /></el-form-item>
        <template v-else
          ><el-form-item :label="t('documentType')"
            ><el-select v-model="fields.document_type"
              ><el-option value="id_card" :label="t('idCard')" /><el-option
                value="passport"
                :label="t('passport')" /></el-select></el-form-item
          ><el-form-item
            prop="document_country"
            :label="t('country')"
            :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
            ><el-input
              v-model="fields.document_country"
              name="document_country"
              :maxlength="2" /></el-form-item
          ><el-form-item
            prop="document_number"
            :label="t('documentNumber')"
            :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
            ><el-input
              v-model="fields.document_number"
              name="document_number"
              :maxlength="32"
              autocomplete="off" /></el-form-item
        ></template>
        <el-form-item
          prop="password"
          :label="t('password')"
          :rules="[{ required: true, message: t('required'), trigger: 'blur' }]"
          ><el-input
            v-model="fields.password"
            id="login-password"
            name="password"
            type="password"
            autocomplete="current-password"
            show-password
            :maxlength="256"
        /></el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" class="full-width">{{
          t('login')
        }}</el-button>
      </el-form>
      <nav class="auth-links" :aria-label="t('accountHelp')">
        <router-link to="/register">{{ t('register') }}</router-link>
        <router-link to="/password-reset">{{ t('forgotPassword') }}</router-link>
      </nav>
    </div>
  </div>
</template>
