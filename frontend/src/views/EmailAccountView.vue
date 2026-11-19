<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import type { FormInstance } from 'element-plus';
import { api } from '../api';
import { ApiError } from '../api/client';
import { emailSchema, verificationCodeSchema } from '../api/authSchemas';
import ErrorNotice from '../components/ErrorNotice.vue';

const route = useRoute();
const { t } = useI18n();
const registering = computed(() => route.name === 'register');
const purpose = computed(() => (registering.value ? 'register' : 'reset_password'));
const form = ref<FormInstance>();
const fields = reactive({ email: '', real_name: '', verification_code: '', password: '' });
const sending = ref(false),
  submitting = ref(false),
  complete = ref(false);
const error = ref<unknown>(null),
  accepted = ref(false);
const serverErrors = reactive({ email: '', real_name: '', verification_code: '', password: '' });
const now = ref(Date.now());
const cooldowns = reactive(new Map<string, number>());
const emailKey = computed(() => `${purpose.value}:${fields.email.trim().toLowerCase()}`);
const remaining = computed(() =>
  Math.max(0, Math.ceil(((cooldowns.get(emailKey.value) || 0) - now.value) / 1000)),
);
let timer: number | undefined;
let active = true;
onMounted(() => {
  timer = window.setInterval(() => {
    now.value = Date.now();
  }, 1000);
});
onUnmounted(() => {
  active = false;
  window.clearInterval(timer);
});
watch(
  () => fields.email,
  () => {
    accepted.value = false;
  },
);

const requiredRule = () => ({ required: true, message: t('required'), trigger: 'blur' });
function focusInvalidField() {
  const input: unknown = form.value?.$el.querySelector('.is-error input');
  if (input instanceof HTMLElement) input.focus();
}
function clearField(name: keyof typeof serverErrors) {
  serverErrors[name] = '';
  form.value?.clearValidate(name);
}
function showServerError(value: unknown) {
  error.value = value;
  if (!(value instanceof ApiError)) return;
  if (value.code === 40102) serverErrors.verification_code = t('verificationInvalid');
  for (const name of Object.keys(value.fields)) {
    if (name === 'password' || name === 'new_password') serverErrors.password = t('passwordPolicy');
    if (name === 'verification_code') serverErrors.verification_code = t('verificationInvalid');
    if (name === 'email') serverErrors.email = t('emailInvalid');
    if (name === 'real_name') serverErrors.real_name = t('nameInvalid');
  }
  void nextTick(focusInvalidField);
}
async function sendCode() {
  if (sending.value || remaining.value || submitting.value) return;
  error.value = null;
  accepted.value = false;
  try {
    await form.value?.validateField('email');
  } catch {
    focusInvalidField();
    return;
  }
  const target = emailSchema.safeParse(fields.email);
  if (!target.success) {
    serverErrors.email = t('emailInvalid');
    focusInvalidField();
    return;
  }
  const key = emailKey.value;
  sending.value = true;
  try {
    await api.sendVerificationCode({ email: target.data, purpose: purpose.value });
    if (!active) return;
    accepted.value = key === emailKey.value;
    // This cooldown reflects the documented 60-second resend interval after actual acceptance.
    now.value = Date.now();
    cooldowns.set(key, now.value + 60_000);
  } catch (e) {
    if (!active) return;
    showServerError(e);
    if (e instanceof ApiError && e.code === 42901 && e.retryAfterSeconds !== undefined) {
      now.value = Date.now();
      cooldowns.set(key, now.value + e.retryAfterSeconds * 1000);
    }
  } finally {
    if (active) sending.value = false;
  }
}
async function submit() {
  if (submitting.value || sending.value) return;
  error.value = null;
  if (!(await form.value?.validate().catch(() => false))) {
    focusInvalidField();
    return;
  }
  submitting.value = true;
  try {
    if (registering.value)
      await api.register({
        email: fields.email,
        password: fields.password,
        verification_code: fields.verification_code,
        real_name: fields.real_name,
      });
    else
      await api.resetPassword({
        email: fields.email,
        new_password: fields.password,
        verification_code: fields.verification_code,
      });
    if (!active) return;
    fields.password = '';
    fields.verification_code = '';
    complete.value = true;
  } catch (e) {
    if (active) showServerError(e);
  } finally {
    if (active) submitting.value = false;
  }
}
</script>

<template>
  <div class="login-layout">
    <div class="login-statement">
      <h1 id="page-title" tabindex="-1">{{ t(registering ? 'register' : 'forgotPassword') }}</h1>
      <p>{{ t(registering ? 'registerHint' : 'resetHint') }}</p>
      <span>COMPSPHERE</span>
    </div>
    <section class="login-form content-panel">
      <el-result
        v-if="complete"
        icon="success"
        :title="t(registering ? 'registered' : 'passwordReset')"
        :sub-title="t('signInExplicitly')"
        ><template #extra
          ><router-link to="/login" class="primary-link">{{ t('login') }}</router-link></template
        ></el-result
      >
      <template v-else>
        <ErrorNotice :error="error" />
        <p v-if="accepted" class="verification-notice" role="status">
          {{ t('verificationAccepted') }}
        </p>
        <el-form
          ref="form"
          :model="fields"
          label-position="top"
          :action="registering ? '/api/v1/auth/register' : '/api/v1/auth/password/reset'"
          method="post"
          :scroll-to-error="true"
          @submit.prevent="submit"
        >
          <el-form-item
            prop="email"
            :label="t('email')"
            :error="serverErrors.email"
            :rules="[
              requiredRule(),
              { type: 'email', message: t('emailInvalid'), trigger: 'blur' },
            ]"
          >
            <el-input
              id="account-email"
              v-model="fields.email"
              name="email"
              type="email"
              autocomplete="email"
              inputmode="email"
              autocapitalize="none"
              :spellcheck="false"
              :maxlength="255"
              required
              @input="clearField('email')"
            />
          </el-form-item>
          <el-form-item
            v-if="registering"
            prop="real_name"
            :label="t('realName')"
            :error="serverErrors.real_name"
            :rules="[
              requiredRule(),
              {
                validator: (_rule, value, callback) =>
                  value.trim() ? callback() : callback(new Error(t('required'))),
                trigger: 'blur',
              },
            ]"
          >
            <el-input
              id="account-real-name"
              v-model="fields.real_name"
              name="real_name"
              autocomplete="name"
              :maxlength="64"
              required
              @input="clearField('real_name')"
            />
          </el-form-item>
          <el-form-item
            prop="verification_code"
            :label="t('verificationCode')"
            :error="serverErrors.verification_code"
            :rules="[
              requiredRule(),
              {
                validator: (_rule, value, callback) =>
                  verificationCodeSchema.safeParse(value).success
                    ? callback()
                    : callback(new Error(t('verificationFormat'))),
                trigger: 'blur',
              },
            ]"
          >
            <div class="verification-field">
              <el-input
                id="account-verification-code"
                v-model="fields.verification_code"
                name="verification_code"
                autocomplete="one-time-code"
                inputmode="numeric"
                pattern="[0-9]{6}"
                :minlength="6"
                :maxlength="6"
                required
                @input="clearField('verification_code')"
              /><el-button
                native-type="button"
                :loading="sending"
                :disabled="remaining > 0 || submitting"
                @click="sendCode"
                >{{
                  remaining ? t('retryInSeconds', { seconds: remaining }) : t('sendVerification')
                }}</el-button
              >
            </div>
          </el-form-item>
          <p id="account-password-hint" class="small muted">{{ t('passwordMin') }}</p>
          <el-form-item
            prop="password"
            :label="t(registering ? 'password' : 'newPassword')"
            :error="serverErrors.password"
            :rules="[
              requiredRule(),
              { min: 12, max: 256, message: t('passwordMin'), trigger: 'blur' },
            ]"
          >
            <el-input
              id="account-new-password"
              v-model="fields.password"
              name="password"
              type="password"
              autocomplete="new-password"
              :minlength="12"
              :maxlength="256"
              required
              show-password
              aria-describedby="account-password-hint"
              @input="clearField('password')"
            />
          </el-form-item>
          <el-button type="primary" native-type="submit" :loading="submitting" class="full-width">{{
            t(registering ? 'register' : 'resetPassword')
          }}</el-button>
        </el-form>
        <nav class="auth-links" :aria-label="t('accountHelp')">
          <router-link to="/login">{{ t('login') }}</router-link><router-link
            :to="registering ? '/password-reset' : '/register'"
            >{{ t(registering ? 'forgotPassword' : 'register') }}</router-link
          >
        </nav>
      </template>
    </section>
  </div>
</template>
