<template>
  <el-container class="app-shell">
    <el-header v-if="!route.meta.public" class="app-header">
      <div class="header-content">
        <div class="brand">
          <img src="@/assets/logo.png" alt="Intent Hub" />
          <span class="brand-divider" />
          <span class="brand-caption">Agent 路由控制台</span>
        </div>
        <div class="header-actions">
          <span class="service-state"><i />服务控制台</span>
          <el-button type="danger" plain @click="logout">退出登录</el-button>
        </div>
      </div>
    </el-header>

    <el-main v-if="!route.meta.public" class="main-wrapper">
      <el-tabs :model-value="route.path" class="nav-tabs" @tab-change="navigate">
        <el-tab-pane label="列表" name="/" />
        <el-tab-pane label="测试" name="/test" />
        <el-tab-pane label="诊断" name="/diagnostics" />
        <el-tab-pane label="设置" name="/settings" />
      </el-tabs>
      <router-view />
    </el-main>
    <router-view v-else />
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const navigate = (path: string | number) => router.push(String(path));
const logout = () => {
  localStorage.removeItem('api_key');
  router.push('/login');
};
</script>
