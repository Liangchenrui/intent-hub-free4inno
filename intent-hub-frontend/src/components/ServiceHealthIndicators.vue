<template>
  <div class="service-health" role="group" :aria-label="t('health.label')">
    <el-tooltip v-for="service in services" :key="service.key" :content="service.detail" placement="bottom" :show-after="200">
      <span class="service-health__item" :class="`is-${service.state}`" tabindex="0" :aria-label="`${service.label}: ${service.detail}`">
        <i class="service-health__dot" aria-hidden="true" />
        <span class="service-health__name">{{ service.label }}</span>
        <span class="service-health__state">{{ t(`health.${service.state}Label`) }}</span>
      </span>
    </el-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useServiceHealth } from '../composables/useServiceHealth';

const { t } = useI18n();
const { health, unavailable } = useServiceHealth();
const services = computed(() => (['embedding', 'qdrant'] as const).map((key) => {
  const result = health.value?.services[key];
  const state = unavailable.value ? 'unknown' : !result ? 'checking' : result.healthy ? 'healthy' : 'unhealthy';
  const detail = state === 'unknown' ? t('health.unavailable')
    : !result ? t('health.checking')
    : result.healthy ? t('health.healthy', { latency: result.latency_ms })
    : t('health.unhealthy', { message: result.message });
  return { key, label: key === 'embedding' ? 'Embedding' : 'Qdrant', state, detail };
}));
</script>

<style scoped>
.service-health { display: flex; align-items: center; gap: 8px; }
.service-health__item {
  --status-color: #64748b;
  --status-background: #f8fafc;
  --status-border: #e2e8f0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-sizing: border-box;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--status-border);
  border-radius: 8px;
  background: var(--status-background);
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  cursor: default;
}
.service-health__item:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 3px; }
.service-health__name { color: #334155; font-weight: 600; }
.service-health__state { min-width: 3em; text-align: center; color: var(--status-color); }
.service-health__dot { flex: 0 0 6px; height: 6px; border-radius: 50%; background: var(--status-color); }
.is-healthy { --status-color: #18794e; --status-background: #f2faf5; --status-border: #d5eadd; }
.is-unhealthy { --status-color: #b42318; --status-background: #fff5f4; --status-border: #f5d5d1; }
.is-checking { --status-color: #946200; --status-background: #fffbef; --status-border: #efe3bc; }
@media (max-width: 720px) {
  .service-health__item { gap: 6px; padding: 0 8px; }
  .service-health__state { display: none; }
}
</style>
