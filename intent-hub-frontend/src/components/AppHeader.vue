<template>
  <el-header class="app-header">
    <div class="app-header__content">
      <img src="@/assets/logo.png" alt="Intent Hub" class="app-header__logo" />
      <div class="app-header__actions">
        <ServiceHealthIndicators />
        <div class="app-header__account">
          <LanguageSwitcher />
          <el-button type="danger" plain @click="$emit('logout')">{{ $t('common.logout') }}</el-button>
        </div>
      </div>
    </div>
  </el-header>
</template>

<script setup lang="ts">
import LanguageSwitcher from './LanguageSwitcher.vue';
import ServiceHealthIndicators from './ServiceHealthIndicators.vue';

defineEmits<{ logout: [] }>();
</script>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  height: 64px;
  padding: 0 40px;
  background: #fff;
  border-bottom: 1px solid #e6e8eb;
}
.app-header__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  width: 95%;
  max-width: 1400px;
  margin: 0 auto;
}
.app-header__logo { display: block; width: auto; height: 40px; }
.app-header__actions, .app-header__account { display: flex; align-items: center; gap: 16px; }
.app-header__account { padding-left: 16px; border-left: 1px solid #e6e8eb; }
@media (max-width: 720px) {
  .app-header { height: auto; min-height: 64px; padding: 12px 16px; }
  .app-header__content { display: grid; grid-template-columns: minmax(0, 1fr) auto; width: 100%; gap: 12px; }
  .app-header__logo { width: 100%; max-width: 160px; height: auto; }
  .app-header__actions { display: contents; }
  .app-header__actions > :deep(.service-health) { grid-column: 1 / -1; grid-row: 2; justify-content: flex-end; }
  .app-header__account { grid-column: 2; grid-row: 1; gap: 8px; padding-left: 0; border: none; }
  .app-header__account :deep(.language-switcher) { padding: 0 4px; }
}
</style>
