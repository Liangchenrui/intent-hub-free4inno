<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="login-header"><img src="@/assets/logo.png" alt="Intent Hub" class="login-logo" /></div>
      </template>
      <el-form @submit.prevent="handleLogin" label-position="top">
        <el-form-item :label="$t('login.username')">
          <el-input v-model="username" :placeholder="$t('login.usernamePlaceholder')" clearable />
        </el-form-item>
        <el-form-item :label="$t('login.password')">
          <el-input v-model="password" type="password" :placeholder="$t('login.passwordPlaceholder')" show-password />
        </el-form-item>
        <el-alert v-if="error" class="error-msg" :title="error" type="error" :closable="false" show-icon />
        <el-button type="primary" native-type="submit" :loading="loading" class="login-btn" size="large">
          {{ loading ? $t('login.logging') : $t('login.login') }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import api, { clearSession } from '../api';

const { t } = useI18n();
const router = useRouter();
const username = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');

const handleLogin = async () => {
  loading.value = true;
  error.value = '';
  try {
    const response = await api.post('/auth/login', { username: username.value, password: password.value });
    const apiKey = response.data?.api_key;
    if (!apiKey) throw new Error(t('login.serverError'));
    clearSession();
    localStorage.setItem('api_key', apiKey);
    router.push('/');
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || t('login.loginFailed');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container { display: flex; justify-content: center; align-items: center; height: 100vh; background: var(--el-bg-color-page); }
.login-card { width: 100%; max-width: 400px; }
.login-header { display: flex; justify-content: center; }
.login-logo { max-width: 200px; height: auto; }
.login-btn { width: 100%; margin-top: 20px; }
.error-msg { margin-bottom: 20px; }
</style>
