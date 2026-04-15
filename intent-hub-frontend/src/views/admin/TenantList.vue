<template>
  <el-container class="page">
    <el-header class="header">
      <div class="title">Tenants</div>
      <div class="actions">
        <ModeSwitcher />
        <el-button @click="openGlobalSettings">通用配置</el-button>
        <el-button @click="openCreate">新建租户</el-button>
        <el-button type="danger" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-main>
      <el-card>
        <el-table :data="tenants" v-loading="loading" style="width: 100%">
          <el-table-column prop="tenant_id" label="Tenant ID" width="180" />
          <el-table-column prop="name" label="Name" />
          <el-table-column prop="qdrant_collection" label="Collection" />
          <el-table-column label="Codes" width="220">
            <template #default="{ row }">
              <span>{{ row.access_codes.length }}</span>
            </template>
          </el-table-column>
          <el-table-column label="Latest API Key" min-width="220">
            <template #default="{ row }">
              <el-text v-if="latestCodes[row.tenant_id]" type="primary">{{ latestCodes[row.tenant_id] }}</el-text>
              <el-text v-else type="info">-</el-text>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row.tenant_id)">详情</el-button>
              <el-button link type="success" @click="createCode(row.tenant_id)">新增 Code</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>
  </el-container>

  <el-dialog v-model="showCreate" title="新建租户" width="520px">
    <el-form :model="createForm" label-position="top">
      <el-form-item label="Tenant ID">
        <el-input v-model="createForm.tenant_id" />
      </el-form-item>
      <el-form-item label="Name">
        <el-input v-model="createForm.name" />
      </el-form-item>
      <el-form-item label="Collection (Optional)">
        <el-input v-model="createForm.qdrant_collection" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showCreate = false">取消</el-button>
      <el-button type="primary" @click="submitCreate" :loading="creating">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  listTenants,
  createTenant,
  createAccessCode,
  clearAdminSession,
  setActiveMode,
  type TenantRecord,
} from '../../api';
import ModeSwitcher from '../../components/ModeSwitcher.vue';
import { loadAdminAccessCodeCache, rememberLatestAccessCode } from '../../utils/adminAccessCodeCache';

const router = useRouter();
const loading = ref(false);
const creating = ref(false);
const showCreate = ref(false);
const tenants = ref<TenantRecord[]>([]);
const latestCodes = ref<Record<string, string>>({});
const createForm = ref({
  tenant_id: '',
  name: '',
  qdrant_collection: '',
});

const fetchTenants = async () => {
  loading.value = true;
  try {
    const response = await listTenants();
    tenants.value = response.data.items;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载租户失败');
  } finally {
    loading.value = false;
  }
};

const openCreate = () => {
  createForm.value = { tenant_id: '', name: '', qdrant_collection: '' };
  showCreate.value = true;
};

const submitCreate = async () => {
  creating.value = true;
  try {
    const response = await createTenant({
      tenant_id: createForm.value.tenant_id,
      name: createForm.value.name,
      qdrant_collection: createForm.value.qdrant_collection || undefined,
    });
    const cache = rememberLatestAccessCode({
      tenantId: response.data.tenant.tenant_id,
      codeId: response.data.access_code.code_id,
      accessCode: response.data.access_code.access_code,
    });
    latestCodes.value = { ...cache.byTenant };
    ElMessage.success(`创建成功，初始 access code: ${response.data.access_code.access_code}`);
    showCreate.value = false;
    await fetchTenants();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建失败');
  } finally {
    creating.value = false;
  }
};

const createCode = async (tenantId: string) => {
  try {
    const response = await createAccessCode(tenantId, 'default');
    const cache = rememberLatestAccessCode({
      tenantId,
      codeId: response.data.access_code.code_id,
      accessCode: response.data.access_code.access_code,
    });
    latestCodes.value = { ...cache.byTenant };
    ElMessage.success(`新 code: ${response.data.access_code.access_code}`);
    await fetchTenants();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建 code 失败');
  }
};

const openDetail = (tenantId: string) => {
  router.push(`/admin/tenants/${tenantId}`);
};

const openGlobalSettings = () => {
  router.push('/admin/settings');
};

const logout = () => {
  clearAdminSession();
  setActiveMode('tenant');
  router.push('/login');
};

onMounted(() => {
  latestCodes.value = loadAdminAccessCodeCache().byTenant;
  fetchTenants();
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

.title {
  font-size: 20px;
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 12px;
}
</style>
