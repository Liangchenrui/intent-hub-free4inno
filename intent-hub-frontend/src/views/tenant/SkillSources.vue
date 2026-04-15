<template>
  <el-container class="page">
    <el-header class="header">
      <div class="left">
        <el-button text @click="back">返回路由列表</el-button>
        <span class="title">Skill Sources</span>
      </div>
      <div class="actions">
        <ModeSwitcher />
        <LanguageSwitcher />
        <el-button type="danger" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-main>
      <el-card>
        <div class="toolbar">
          <el-button type="primary" @click="openCreate">新增 Source</el-button>
          <el-button @click="scanAll" :loading="scanning">扫描全部</el-button>
        </div>
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="source_id" label="Source ID" width="160" />
          <el-table-column prop="path" label="Path" />
          <el-table-column prop="sync_mode" label="Mode" width="120" />
          <el-table-column prop="enabled" label="Enabled" width="120">
            <template #default="{ row }">{{ row.enabled ? 'Yes' : 'No' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>
  </el-container>

  <el-dialog v-model="showCreate" title="新增 Skill Source" width="520px">
    <el-form :model="createForm" label-position="top">
      <el-form-item label="Path">
        <el-input v-model="createForm.path" />
      </el-form-item>
      <el-form-item label="Sync Mode">
        <el-select v-model="createForm.sync_mode" style="width: 100%">
          <el-option value="draft" label="draft" />
          <el-option value="apply" label="apply" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showCreate = false">取消</el-button>
      <el-button type="primary" @click="submitCreate" :loading="creating">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  listSkillSources,
  createSkillSource,
  scanSkillSources,
  clearTenantSession,
  setActiveMode,
  type SkillSourceRecord,
} from '../../api';
import ModeSwitcher from '../../components/ModeSwitcher.vue';
import LanguageSwitcher from '../../components/LanguageSwitcher.vue';

const router = useRouter();
const loading = ref(false);
const scanning = ref(false);
const creating = ref(false);
const showCreate = ref(false);
const items = ref<SkillSourceRecord[]>([]);
const createForm = ref({
  path: '',
  sync_mode: 'draft' as 'draft' | 'apply',
});

const fetchSources = async () => {
  loading.value = true;
  try {
    const response = await listSkillSources();
    items.value = response.data.items;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载失败');
  } finally {
    loading.value = false;
  }
};

const openCreate = () => {
  createForm.value = { path: '', sync_mode: 'draft' };
  showCreate.value = true;
};

const submitCreate = async () => {
  creating.value = true;
  try {
    await createSkillSource({
      path: createForm.value.path,
      sync_mode: createForm.value.sync_mode,
      enabled: true,
    });
    ElMessage.success('创建成功');
    showCreate.value = false;
    await fetchSources();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建失败');
  } finally {
    creating.value = false;
  }
};

const scanAll = async () => {
  scanning.value = true;
  try {
    const response = await scanSkillSources();
    const data = response.data || {};
    ElMessage.success(
      `扫描完成 discovered=${data.discovered || 0}, updated=${data.updated || 0}, applied=${data.applied || 0}`
    );
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '扫描失败');
  } finally {
    scanning.value = false;
  }
};

const back = () => router.push('/');

const logout = () => {
  clearTenantSession();
  setActiveMode('tenant');
  router.push('/login');
};

onMounted(() => {
  fetchSources();
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

.toolbar {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
}
</style>
