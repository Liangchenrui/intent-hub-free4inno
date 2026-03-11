<template>
  <el-config-provider :locale="elementLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';

const elementLocale = ref(localStorage.getItem('locale') === 'en' ? en : zhCn);

const handleLocaleChange = (event: CustomEvent) => {
  elementLocale.value = event.detail.locale;
};

onMounted(() => {
  window.addEventListener('locale-change', handleLocaleChange as EventListener);
});

onUnmounted(() => {
  window.removeEventListener('locale-change', handleLocaleChange as EventListener);
});
</script>
