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
          <el-button @click="startNewUpload" :loading="uploading">选择本地目录并上传</el-button>
        </div>
        <el-alert
          title="Web 端扫描改为浏览器本地目录上传。选择目录后，页面只会读取其中的 SKILL.md 并上传到后端生成草稿。"
          type="info"
          :closable="false"
          show-icon
          class="hint"
        />
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="source_id" label="Source ID" width="160" />
          <el-table-column prop="source_label" label="Source" min-width="180" />
          <el-table-column prop="client_path_hint" label="本地目录提示" min-width="220">
            <template #default="{ row }">{{ row.client_path_hint || '-' }}</template>
          </el-table-column>
          <el-table-column prop="sync_mode" label="Mode" width="120" />
          <el-table-column prop="enabled" label="Enabled" width="100">
            <template #default="{ row }">{{ row.enabled ? 'Yes' : 'No' }}</template>
          </el-table-column>
          <el-table-column prop="last_scanned_at" label="Last Scanned" min-width="180">
            <template #default="{ row }">{{ row.last_scanned_at || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="startExistingUpload(row)" :disabled="uploading">
                重新上传目录
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>
  </el-container>

  <el-dialog v-model="showCreate" title="新增 Skill Source" width="520px">
    <el-form :model="createForm" label-position="top">
      <el-form-item label="Source 名称">
        <el-input v-model="createForm.source_label" placeholder="例如：team-skills" />
      </el-form-item>
      <el-form-item label="本地目录提示">
        <el-input v-model="createForm.client_path_hint" placeholder="例如：D:/skills 或 ./skills" />
      </el-form-item>
      <el-form-item label="Sync Mode">
        <el-select v-model="createForm.sync_mode" style="width: 100%">
          <el-option value="apply" label="apply" />
          <el-option value="scan" label="scan" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showCreate = false">取消</el-button>
      <el-button type="primary" @click="submitCreate" :loading="creating">创建</el-button>
    </template>
  </el-dialog>

  <input
    ref="directoryInput"
    type="file"
    webkitdirectory
    multiple
    class="hidden-directory-input"
    @change="handleDirectorySelected"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  listSkillSources,
  createSkillSource,
  scanSkillSources,
  clearTenantSession,
  setActiveMode,
  type SkillSourceRecord,
  type UploadedSkillPayload,
} from '../../api';
import ModeSwitcher from '../../components/ModeSwitcher.vue';
import LanguageSwitcher from '../../components/LanguageSwitcher.vue';

const router = useRouter();
const loading = ref(false);
const uploading = ref(false);
const creating = ref(false);
const showCreate = ref(false);
const items = ref<SkillSourceRecord[]>([]);
const directoryInput = ref<HTMLInputElement | null>(null);
const createForm = ref({
  source_label: '',
  client_path_hint: '',
  sync_mode: 'apply' as 'apply' | 'scan',
});
const uploadTarget = ref<{
  source_id?: string;
  source_label?: string;
  client_path_hint?: string;
  sync_mode?: 'apply' | 'scan';
} | null>(null);

const canCreate = computed(() => Boolean(createForm.value.source_label.trim()));

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
  createForm.value = { source_label: '', client_path_hint: '', sync_mode: 'apply' };
  showCreate.value = true;
};

const submitCreate = async () => {
  if (!canCreate.value) {
    ElMessage.warning('请先填写 Source 名称');
    return;
  }
  creating.value = true;
  try {
    await createSkillSource({
      source_label: createForm.value.source_label.trim(),
      client_path_hint: createForm.value.client_path_hint.trim() || undefined,
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

const openDirectoryPicker = () => {
  if (!directoryInput.value) {
    ElMessage.error('当前浏览器不支持目录选择');
    return;
  }
  directoryInput.value.value = '';
  directoryInput.value.click();
};

const startNewUpload = () => {
  uploadTarget.value = null;
  openDirectoryPicker();
};

const startExistingUpload = (source: SkillSourceRecord) => {
  uploadTarget.value = {
    source_id: source.source_id,
    source_label: source.source_label,
    client_path_hint: source.client_path_hint || undefined,
    sync_mode: source.sync_mode,
  };
  openDirectoryPicker();
};

const buildUploadedSkills = async (files: File[]): Promise<UploadedSkillPayload[]> => {
  const skillFiles = files.filter((file) => {
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    return relativePath.endsWith('/SKILL.md') || relativePath === 'SKILL.md';
  });
  return Promise.all(
    skillFiles.map(async (file) => {
      const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
      const normalizedPath = relativePath.replace(/\\/g, '/');
      const segments = normalizedPath.split('/').filter(Boolean);
      return {
        skill_name: segments.length >= 2 ? segments[segments.length - 2] : 'SKILL',
        relative_path: normalizedPath,
        content: await file.text(),
      };
    })
  );
};

const inferRootDirectory = (files: File[]) => {
  const firstPath = (files[0] as File & { webkitRelativePath?: string })?.webkitRelativePath || '';
  return firstPath.split('/')[0] || 'local-skills';
};

const handleDirectorySelected = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const fileList = Array.from(input.files || []);
  if (!fileList.length) {
    return;
  }

  uploading.value = true;
  try {
    const skills = await buildUploadedSkills(fileList);
    if (!skills.length) {
      ElMessage.warning('所选目录中未找到 SKILL.md');
      return;
    }

    const rootDirectory = inferRootDirectory(fileList);
    const sourceLabel = uploadTarget.value?.source_label || rootDirectory;
    const clientPathHint = uploadTarget.value?.client_path_hint || rootDirectory;
    const response = await scanSkillSources({
      source_id: uploadTarget.value?.source_id,
      source_label: sourceLabel,
      client_path_hint: clientPathHint,
      sync_mode: uploadTarget.value?.sync_mode || 'apply',
      skills,
    });
    const data = response.data || {};
    ElMessage.success(
      `上传完成 discovered=${data.discovered || 0}, updated=${data.updated || 0}, applied=${data.applied || 0}`
    );
    uploadTarget.value = null;
    await fetchSources();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '上传失败');
  } finally {
    uploading.value = false;
    input.value = '';
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

.hint {
  margin-bottom: 16px;
}

.hidden-directory-input {
  display: none;
}
</style>
