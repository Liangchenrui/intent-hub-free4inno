<template>
  <el-container class="page">
    <el-header class="header">
      <div class="left">
        <el-button text @click="back">返回</el-button>
        <span class="title">通用配置</span>
      </div>
      <div class="actions">
        <ModeSwitcher />
        <el-button type="danger" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-main>
      <el-card v-loading="loading">
        <el-form :model="settings" label-position="top">
          <el-divider content-position="left">Qdrant</el-divider>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="Qdrant URL">
                <el-input v-model="settings.QDRANT_URL" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Collection">
                <el-input v-model="settings.QDRANT_COLLECTION" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="Qdrant API Key">
            <el-input v-model="settings.QDRANT_API_KEY" type="password" show-password />
          </el-form-item>

          <el-divider content-position="left">Embedding</el-divider>
          <el-row :gutter="16">
            <el-col :span="16">
              <el-form-item label="Embedding Service URL">
                <el-input v-model="settings.EMBEDDING_SERVICE_URL" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="Device">
                <el-select v-model="settings.EMBEDDING_DEVICE" style="width: 100%">
                  <el-option label="cpu" value="cpu" />
                  <el-option label="cuda" value="cuda" />
                  <el-option label="mps" value="mps" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="Embedding Model">
            <el-input v-model="settings.EMBEDDING_MODEL_NAME" />
          </el-form-item>

          <el-divider content-position="left">LLM</el-divider>
          <el-form-item label="Provider">
            <el-select v-model="settings.LLM_PROVIDER" style="width: 100%">
              <el-option label="deepseek" value="deepseek" />
              <el-option label="openrouter" value="openrouter" />
              <el-option label="doubao" value="doubao" />
              <el-option label="qwen" value="qwen" />
              <el-option label="gemini" value="gemini" />
            </el-select>
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="LLM API Key">
                <el-input v-model="settings.LLM_API_KEY" type="password" show-password />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="LLM Model">
                <el-input v-model="settings.LLM_MODEL" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="LLM Base URL">
            <el-input v-model="settings.LLM_BASE_URL" />
          </el-form-item>

          <el-divider content-position="left">Auth</el-divider>
          <el-form-item label="AUTH_ENABLED">
            <el-switch v-model="settings.AUTH_ENABLED" />
          </el-form-item>
          <el-form-item label="API_KEYS">
            <el-input v-model="settings.API_KEYS" />
          </el-form-item>
          <el-form-item label="PREDICT_AUTH_KEY">
            <el-input v-model="settings.PREDICT_AUTH_KEY" type="password" show-password />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
            <el-button @click="fetchSettings">刷新</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  clearAdminSession,
  getSystemSettings,
  setActiveMode,
  type SystemSettings,
  updateSystemSettings,
} from '../../api';
import ModeSwitcher from '../../components/ModeSwitcher.vue';

const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const settings = ref<SystemSettings>({
  QDRANT_URL: '',
  QDRANT_COLLECTION: '',
  QDRANT_API_KEY: null,
  EMBEDDING_SERVICE_URL: '',
  EMBEDDING_MODEL_NAME: '',
  EMBEDDING_DEVICE: 'cpu',
  LLM_PROVIDER: 'deepseek',
  LLM_API_KEY: null,
  LLM_BASE_URL: null,
  LLM_MODEL: null,
  LLM_TEMPERATURE: 0.7,
  UTTERANCE_GENERATION_PROMPT: '',
  AGENT_REPAIR_PROMPT: '',
  SKILL_ROUTE_IMPORT_PROMPT: '',
  AUTH_ENABLED: true,
  API_KEYS: '',
  PREDICT_AUTH_KEY: null,
});

const fetchSettings = async () => {
  loading.value = true;
  try {
    const response = await getSystemSettings();
    settings.value = { ...settings.value, ...(response.data as any) };
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载配置失败');
  } finally {
    loading.value = false;
  }
};

const save = async () => {
  saving.value = true;
  try {
    await updateSystemSettings(settings.value);
    ElMessage.success('保存成功');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败');
  } finally {
    saving.value = false;
  }
};

const back = () => router.push('/admin/tenants');

const logout = () => {
  clearAdminSession();
  setActiveMode('tenant');
  router.push('/login');
};

onMounted(fetchSettings);
</script>

<style scoped>
.page { min-height: 100vh; }
.header { display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #ebeef5; }
.left { display:flex; align-items:center; gap:12px; }
.title { font-size:20px; font-weight:600; }
.actions { display:flex; gap:12px; }
</style>
