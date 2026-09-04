<template>
  <el-container class="app-shell">
    <el-header class="app-header">
      <div class="header-content">
        <div class="brand">
          <img src="@/assets/logo.png" alt="Intent Hub" />
          <span class="brand-divider" />
          <span class="brand-caption">Agent 路由控制台</span>
        </div>
        <div class="header-actions">
          <span
            v-for="service in services"
            :key="service.key"
            class="service-state"
            :class="service.state"
            :title="service.detail"
          ><i /><span>{{ service.label }}</span></span>
        </div>
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
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getServiceHealth } from './api';

type HealthState = 'checking' | 'healthy' | 'unhealthy';

interface HeaderService {
  key: 'embedding' | 'qdrant';
  label: string;
  state: HealthState;
  detail: string;
}

const route = useRoute();
const router = useRouter();
const services = ref<HeaderService[]>([
  { key: 'embedding', label: 'Embedding', state: 'checking', detail: '正在检查服务状态' },
  { key: 'qdrant', label: 'Qdrant', state: 'checking', detail: '正在检查服务状态' },
]);
let healthTimer: number | undefined;

const navigate = (path: string | number) => router.push(String(path));

const refreshHealth = async () => {
  try {
    const { data } = await getServiceHealth();
    services.value = services.value.map((service) => {
      const result = data.services[service.key];
      return {
        ...service,
        state: result.healthy ? 'healthy' : 'unhealthy',
        detail: result.healthy
          ? `服务正常 · ${result.latency_ms} ms`
          : `服务异常 · ${result.message}`,
      };
    });
  } catch {
    services.value = services.value.map((service) => ({
      ...service,
      state: 'unhealthy',
      detail: '无法获取服务状态',
    }));
  }
};

onMounted(() => {
  refreshHealth();
  healthTimer = window.setInterval(refreshHealth, 30_000);
});

onBeforeUnmount(() => {
  if (healthTimer !== undefined) window.clearInterval(healthTimer);
});
</script>
