<template>
  <el-container class="app-shell">
    <el-header class="app-header">
      <div class="header-content">
        <div class="brand">
          <img src="@/assets/logo.png" alt="Intent Hub" />
          <span class="brand-divider" />
          <span class="brand-caption">Agent 路由控制台</span>
        </div>
        <div class="header-actions"><span class="service-state"><i />服务控制台</span></div>
      </div>
    </el-header>

    <el-main class="main-wrapper">
      <el-tabs :model-value="route.path" class="nav-tabs" @tab-change="navigate">
        <el-tab-pane label="列表" name="/" />
        <el-tab-pane label="测试" name="/test" />
        <el-tab-pane label="诊断" name="/diagnostics" />
        <el-tab-pane label="设置" name="/settings" />
      </el-tabs>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const navigate = (path: string | number) => router.push(String(path));
</script>
