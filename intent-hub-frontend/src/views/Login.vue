<template>
  <div class="login-page">
    <div class="login-backdrop" aria-hidden="true"><span /><span /></div>
    <el-card shadow="never" class="login-card">
      <div class="login-brand">
        <img src="@/assets/logo.png" alt="Intent Hub" />
        <p>Agent 路由控制台</p>
      </div>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名"><el-input v-model="username" size="large" autocomplete="username" placeholder="请输入用户名" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="password" size="large" type="password" autocomplete="current-password" placeholder="请输入密码" show-password /></el-form-item>
        <el-button class="full" size="large" type="primary" native-type="submit" :loading="loading">登录控制台</el-button>
      </el-form>
      <div class="login-foot"><i />Intent Hub 服务连接正常</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { login } from '../api';

const router = useRouter();
const username = ref('');
const password = ref('');
const loading = ref(false);

const submit = async () => {
  loading.value = true;
  try {
    const response = await login(username.value, password.value);
    localStorage.setItem('api_key', response.data.api_key);
    router.push('/');
  } catch (error: any) {
    ElMessage.error(error.response?.data?.error || '登录失败');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-page { position: relative; width: 100%; min-height: 100vh; display: grid; place-items: center; overflow: hidden; background: #f5f7fa; }
.login-backdrop { position: absolute; inset: 0; pointer-events: none; }
.login-backdrop::before { content: ""; position: absolute; inset: 0; background-image: linear-gradient(#e8edf5 1px, transparent 1px), linear-gradient(90deg, #e8edf5 1px, transparent 1px); background-size: 40px 40px; opacity: .45; mask-image: linear-gradient(to bottom, #000, transparent 82%); }
.login-backdrop span { position: absolute; width: 280px; height: 280px; border: 70px solid rgba(51, 127, 242, .07); border-radius: 50%; }
.login-backdrop span:first-child { top: -150px; left: -110px; }
.login-backdrop span:last-child { right: -100px; bottom: -160px; }
.login-card { z-index: 1; width: min(420px, calc(100vw - 40px)); border: 0; border-radius: 14px; box-shadow: 0 18px 50px rgba(31, 55, 86, .12); }
.login-card :deep(.el-card__body) { padding: 34px 38px 26px; }
.login-brand { margin-bottom: 30px; text-align: center; }
.login-brand img { width: 190px; height: auto; }
.login-brand p { margin: 10px 0 0; color: #909399; font-size: 13px; letter-spacing: .08em; }
.login-foot { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 22px; color: #a8abb2; font-size: 11px; }
.login-foot i { width: 6px; height: 6px; border-radius: 50%; background: #67c23a; }
@media (max-width: 480px) { .login-card :deep(.el-card__body) { padding: 28px 24px 22px; } }
</style>
