<template>
  <div class="service-health">
    <span
      v-for="service in services"
      :key="service.key"
      class="service-health__item"
      :class="`is-${service.state}`"
      :title="service.detail"
    >
      <i />{{ service.label }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { getServiceHealth } from '../api';

type HealthState = 'checking' | 'healthy' | 'unhealthy';
type ServiceKey = 'embedding' | 'qdrant';

interface HeaderService {
  key: ServiceKey;
  label: string;
  state: HealthState;
  detail: string;
}

const { t } = useI18n();
const services = ref<HeaderService[]>([
  { key: 'embedding', label: 'Embedding', state: 'checking', detail: t('health.checking') },
  { key: 'qdrant', label: 'Qdrant', state: 'checking', detail: t('health.checking') },
]);
let timer: number | undefined;

const refresh = async () => {
  try {
    const { data } = await getServiceHealth();
    services.value = services.value.map((service) => {
      const result = data.services[service.key];
      return {
        ...service,
        state: result.healthy ? 'healthy' : 'unhealthy',
        detail: result.healthy
          ? t('health.healthy', { latency: result.latency_ms })
          : t('health.unhealthy', { message: result.message }),
      };
    });
  } catch {
    services.value = services.value.map((service) => ({
      ...service,
      state: 'unhealthy',
      detail: t('health.unavailable'),
    }));
  }
};

onMounted(() => {
  refresh();
  timer = window.setInterval(refresh, 30_000);
});

onBeforeUnmount(() => {
  if (timer !== undefined) window.clearInterval(timer);
});
</script>

<style scoped>
.service-health { display: flex; align-items: center; gap: 12px; }
.service-health__item { display: inline-flex; align-items: center; gap: 6px; color: #606266; font-size: 12px; }
.service-health__item i { width: 8px; height: 8px; border-radius: 50%; background: #909399; }
.service-health__item.is-healthy i { background: #67c23a; box-shadow: 0 0 0 3px rgb(103 194 58 / 14%); }
.service-health__item.is-unhealthy i { background: #f56c6c; box-shadow: 0 0 0 3px rgb(245 108 108 / 14%); }
.service-health__item.is-checking i { background: #e6a23c; }
@media (max-width: 720px) { .service-health__item { font-size: 0; } }
</style>
