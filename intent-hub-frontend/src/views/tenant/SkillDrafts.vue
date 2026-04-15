<template>
  <el-container class="page">
    <el-header class="header">
      <div class="left">
        <el-button text @click="back">返回路由列表</el-button>
        <span class="title">Skill Drafts</span>
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
          <el-button @click="fetchDrafts" :loading="loading">刷新</el-button>
        </div>
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="skill_path" label="Skill Path" min-width="280" />
          <el-table-column prop="status" label="Status" width="120" />
          <el-table-column prop="draft_file" label="Draft File" min-width="280" />
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                  @click="applyDraft(row.draft_file)"
                  :disabled="row.status !== 'pending'"
                >
                Apply
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  listSkillDrafts,
  applySkillDraft,
  clearTenantSession,
  setActiveMode,
  type SkillDraftRecord,
} from '../../api';
import ModeSwitcher from '../../components/ModeSwitcher.vue';
import LanguageSwitcher from '../../components/LanguageSwitcher.vue';

const router = useRouter();
const loading = ref(false);
const items = ref<SkillDraftRecord[]>([]);

const fetchDrafts = async () => {
  loading.value = true;
  try {
    const response = await listSkillDrafts();
    items.value = response.data.items;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载失败');
  } finally {
    loading.value = false;
  }
};

const applyDraft = async (draftFile: string) => {
  try {
    const response = await applySkillDraft(draftFile);
    const data = response.data || {};
    ElMessage.success(`导入完成 created=${data.created || 0}, updated=${data.updated || 0}`);
    await fetchDrafts();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败');
  }
};

const back = () => router.push('/');

const logout = () => {
  clearTenantSession();
  setActiveMode('tenant');
  router.push('/login');
};

onMounted(() => {
  fetchDrafts();
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
}
</style>
