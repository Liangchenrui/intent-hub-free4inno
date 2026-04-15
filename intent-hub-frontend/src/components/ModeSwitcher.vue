<template>
  <el-radio-group v-model="currentMode" size="small" @change="handleChange">
    <el-radio-button label="tenant">{{ $t('mode.tenant') }}</el-radio-button>
    <el-radio-button label="admin">{{ $t('mode.admin') }}</el-radio-button>
  </el-radio-group>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { getActiveMode, setActiveMode } from '../api';

const router = useRouter();

const currentMode = computed({
  get: () => getActiveMode(),
  set: (val) => setActiveMode(val),
});

const handleChange = (nextMode: string) => {
  if (nextMode === 'admin') {
    if (!localStorage.getItem('admin_token')) {
      router.push('/login');
      return;
    }
    setActiveMode('admin');
    router.push('/admin/tenants');
    return;
  }

  if (!localStorage.getItem('tenant_access_code')) {
    router.push('/login');
    return;
  }
  setActiveMode('tenant');
  router.push('/');
};
</script>
