<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <img src="@/assets/logo.png" alt="Intent Hub" class="login-logo" />
        </div>
      </template>

      <el-tabs v-model="mode" stretch>
        <el-tab-pane :label="$t('mode.tenant')" name="tenant" />
        <el-tab-pane :label="$t('mode.admin')" name="admin" />
      </el-tabs>

      <el-form v-if="mode === 'tenant'" @submit.prevent="handleTenantLogin" label-position="top">
        <el-form-item :label="$t('login.accessCode')">
          <el-input v-model="tenantCode" :placeholder="$t('login.accessCodePlaceholder')" clearable />
        </el-form-item>
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          class="login-btn"
          size="large"
        >
          {{ loading ? $t('login.verifying') : $t('login.tenantLogin') }}
        </el-button>
      </el-form>

      <el-form v-else @submit.prevent="handleAdminLogin" label-position="top">
        <el-form-item :label="$t('login.username')">
          <el-input
            v-model="username"
            :placeholder="$t('login.usernamePlaceholder')"
            clearable
          />
        </el-form-item>
        <el-form-item :label="$t('login.password')">
          <el-input
            v-model="password"
            type="password"
            :placeholder="$t('login.passwordPlaceholder')"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          class="login-btn"
          size="large"
        >
          {{ loading ? $t('login.logging') : $t('login.adminLogin') }}
        </el-button>
      </el-form>

      <div v-if="error" class="error-msg">
        <el-alert :title="error" type="error" :closable="false" show-icon />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import api, { clearAdminSession, clearTenantSession, setActiveMode } from '../api';

const { t } = useI18n();
const router = useRouter();
const mode = ref<'tenant' | 'admin'>('tenant');
const tenantCode = ref('');
const username = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');

const handleTenantLogin = async () => {
  loading.value = true;
  error.value = '';
  try {
    await api.get('/v1/me', {
      headers: {
        Authorization: `Bearer ${tenantCode.value}`,
        'X-API-Key': tenantCode.value,
      },
    });
    clearTenantSession();
    localStorage.setItem('tenant_access_code', tenantCode.value);
    setActiveMode('tenant');
    router.push('/');
  } catch (err: any) {
    error.value = err?.response?.data?.detail || t('login.accessCodeInvalid');
  } finally {
    loading.value = false;
  }
};

const handleAdminLogin = async () => {
  loading.value = true;
  error.value = '';
  try {
    const response = await api.post('/auth/login', {
      username: username.value,
      password: password.value,
    });
    const apiKey = response.data?.api_key;
    if (!apiKey) {
      throw new Error(t('login.serverError'));
    }
    clearAdminSession();
    localStorage.setItem('admin_token', apiKey);
    setActiveMode('admin');
    router.push('/admin/tenants');
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || t('login.loginFailed');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: var(--el-bg-color-page);
}

.login-card {
  width: 100%;
  max-width: 420px;
}

.login-header {
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
}

.login-logo {
  max-width: 200px;
  height: auto;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
}

.error-msg {
  margin-top: 16px;
}
</style>
