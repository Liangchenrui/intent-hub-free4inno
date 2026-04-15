<template>
  <el-container class="page">
    <el-header class="header">
      <div class="left">
        <el-button text @click="back">返回</el-button>
        <span class="title">{{ tenantId }}</span>
      </div>
      <div class="actions">
        <ModeSwitcher />
        <el-button type="danger" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-main>
      <el-card>
        <el-table :data="codes" v-loading="loading" style="width: 100%">
          <el-table-column prop="code_id" label="Code ID" width="160" />
          <el-table-column prop="label" label="Label" />
          <el-table-column prop="status" label="Status" width="120" />
          <el-table-column prop="created_at" label="Created At" />
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button link type="primary" @click="rotateCode(row.code_id)">Rotate</el-button>
              <el-button link type="danger" @click="disableCodeById(row.code_id)">Disable</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  listTenants,
  rotateAccessCode,
  disableAccessCode,
  clearAdminSession,
  setActiveMode,
} from '../../api';
import ModeSwitcher from '../../components/ModeSwitcher.vue';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const codes = ref<any[]>([]);
const tenantId = computed(() => String(route.params.tenantId || ''));

const fetchDetail = async () => {
  loading.value = true;
  try {
    const response = await listTenants();
    const tenant = response.data.items.find((item) => item.tenant_id === tenantId.value);
    codes.value = tenant?.access_codes || [];
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载租户详情失败');
  } finally {
    loading.value = false;
  }
};

const rotateCode = async (codeId: string) => {
  try {
    const response = await rotateAccessCode(tenantId.value, codeId);
    ElMessage.success(`新 code: ${response.data.access_code.access_code}`);
    await fetchDetail();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'Rotate 失败');
  }
};

const disableCodeById = async (codeId: string) => {
  try {
    await disableAccessCode(tenantId.value, codeId);
    ElMessage.success('已禁用');
    await fetchDetail();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'Disable 失败');
  }
};

const back = () => router.push('/admin/tenants');

const logout = () => {
  clearAdminSession();
  setActiveMode('tenant');
  router.push('/login');
};

onMounted(() => {
  fetchDetail();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
}

.left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 20px;
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 12px;
}
</style>
