<template>
  <el-container class="layout-container">
    <el-header class="header-wrapper">
      <div class="header-content">
        <div class="brand">
          <img src="@/assets/logo.png" alt="Intent Hub" class="logo-img" />
        </div>
        <div class="user-info">
          <LanguageSwitcher />
          <el-button type="danger" @click="handleLogout">{{ $t('common.logout') }}</el-button>
        </div>
      </div>
    </el-header>

    <el-main class="main-wrapper">
      <div class="page-header">
        <el-tabs v-model="activeTab" class="nav-tabs" @tab-change="handleTabChange">
          <el-tab-pane :label="$t('nav.list')" name="list"></el-tab-pane>
          <el-tab-pane :label="$t('nav.test')" name="test"></el-tab-pane>
          <el-tab-pane :label="$t('nav.diagnostics')" name="diagnostics"></el-tab-pane>
          <el-tab-pane :label="$t('nav.settings')" name="settings"></el-tab-pane>
        </el-tabs>
      </div>

      <el-card shadow="never" class="settings-card" v-loading="loading">
        <el-form :model="settings" label-position="top" class="settings-form">
          <el-divider content-position="left">Infrastructure</el-divider>
          <el-form-item label="Qdrant URL">
            <el-input v-model="settings.QDRANT_URL" placeholder="http://app.qdrant.free4inno.com" />
          </el-form-item>
          <el-form-item :label="$t('settings.qdrantCollection')">
            <el-select
              v-model="settings.QDRANT_COLLECTION"
              filterable
              allow-create
              default-first-option
              :loading="collectionsLoading"
              :placeholder="$t('settings.qdrantCollectionPlaceholder')"
              style="width: 100%"
            >
              <el-option
                v-for="collection in qdrantCollections"
                :key="collection"
                :label="collection"
                :value="collection"
              />
            </el-select>
            <div class="field-hint">{{ $t('settings.qdrantCollectionHint') }}</div>
            <el-button
              class="collection-import-button"
              type="primary"
              plain
              :loading="importingRoutes"
              :disabled="!settings.QDRANT_COLLECTION"
              @click="handleImportCollection"
            >
              {{ $t('settings.importCollectionRoutes') }}
            </el-button>
          </el-form-item>
          <el-form-item label="Embedding Service URL">
            <el-input v-model="settings.EMBEDDING_SERVICE_URL" placeholder="http://embedding.free4inno.com" />
          </el-form-item>
          <el-form-item label="Route API Key">
            <el-input v-model="settings.PREDICT_AUTH_KEY" type="password" show-password />
          </el-form-item>

          <el-divider :content-position="'left'">{{ $t('settings.llmTitle') }}</el-divider>
          <el-form-item :label="$t('settings.llmProvider')">
            <el-select v-model="settings.LLM_PROVIDER" style="width: 100%">
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="OpenRouter" value="openrouter" />
              <el-option label="豆包 (Doubao)" value="doubao" />
              <el-option label="通义千问 (Qwen)" value="qwen" />
              <el-option label="Gemini" value="gemini" />
            </el-select>
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ $t('settings.providerHint') }}
            </div>
          </el-form-item>
          <el-row :gutter="20">
            <el-col :span="16">
              <el-form-item :label="$t('settings.apiKey')">
                <el-input 
                  v-model="settings.LLM_API_KEY" 
                  type="password" 
                  show-password 
                  :placeholder="getApiKeyPlaceholder()"
                />
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.apiKeyHint') }}
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('settings.model')">
                <el-input 
                  v-model="settings.LLM_MODEL" 
                  :placeholder="getModelPlaceholder()"
                />
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.modelHint') }}
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item v-if="settings.LLM_PROVIDER !== 'gemini'" :label="$t('settings.baseUrl')">
            <el-input 
              v-model="settings.LLM_BASE_URL" 
              :placeholder="getBaseUrlPlaceholder()"
            />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ $t('settings.baseUrlHint') }}
            </div>
          </el-form-item>
          <el-form-item :label="$t('settings.temperature')">
            <el-slider v-model="settings.LLM_TEMPERATURE" :min="0" :max="2" :step="0.1" show-input />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ $t('settings.temperatureHint') }}
            </div>
          </el-form-item>
          <el-form-item :label="$t('settings.prompt')">
            <el-input v-model="settings.UTTERANCE_GENERATION_PROMPT" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item :label="$t('settings.skillImportPrompt')">
            <el-input v-model="settings.SKILL_ROUTE_IMPORT_PROMPT" type="textarea" :rows="6" />
          </el-form-item>
          <el-form-item :label="$t('settings.repairPrompt')">
            <el-input v-model="settings.AGENT_REPAIR_PROMPT" type="textarea" :rows="4" />
          </el-form-item>

          <el-divider :content-position="'left'">{{ $t('settings.diagnosticTitle') }}</el-divider>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('settings.regionThreshold')">
                <el-slider 
                  v-model="settings.REGION_THRESHOLD_SIGNIFICANT" 
                  :min="0" 
                  :max="1" 
                  :step="0.01" 
                  show-input 
                  :format-tooltip="(val: number) => (val * 100).toFixed(1) + '%'"
                />
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.regionThresholdHint') }}
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('settings.instanceThreshold')">
                <el-slider 
                  v-model="settings.INSTANCE_THRESHOLD_AMBIGUOUS" 
                  :min="0" 
                  :max="1" 
                  :step="0.01" 
                  show-input 
                  :format-tooltip="(val: number) => (val * 100).toFixed(1) + '%'"
                />
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.instanceThresholdHint') }}
                </div>
              </el-form-item>
            </el-col>
          </el-row>

          <div class="form-actions">
            <el-button type="primary" :loading="saving" @click="handleSave">{{ $t('settings.save') }}</el-button>
            <el-button @click="fetchSettings(true)">{{ $t('settings.reset') }}</el-button>
          </div>
        </el-form>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  getQdrantCollections,
  getSettings,
  importRoutesFromQdrant,
  updateSettings,
  type SystemSettings,
} from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';

const { t } = useI18n();

const router = useRouter();
const activeTab = ref('settings');
const loading = ref(false);
const saving = ref(false);
const collectionsLoading = ref(false);
const qdrantCollections = ref<string[]>([]);
const importingRoutes = ref(false);

const settings = ref<SystemSettings>({
  QDRANT_URL: 'http://app.qdrant.free4inno.com',
  PREDICT_AUTH_KEY: null,
  EMBEDDING_SERVICE_URL: 'http://embedding.free4inno.com',
  EMBEDDING_MODEL_NAME: '',
  EMBEDDING_DEVICE: 'cpu',
  LLM_PROVIDER: 'deepseek',
  LLM_API_KEY: null,
  LLM_BASE_URL: null,
  LLM_MODEL: null,
  LLM_TEMPERATURE: 0.7,
  UTTERANCE_GENERATION_PROMPT: '',
  SKILL_ROUTE_IMPORT_PROMPT: '',
  AGENT_REPAIR_PROMPT: '',
  BATCH_SIZE: 32,
  DEFAULT_ROUTE_ID: 0,
  DEFAULT_ROUTE_NAME: 'none',
  REGION_THRESHOLD_SIGNIFICANT: 0.85,
  INSTANCE_THRESHOLD_AMBIGUOUS: 0.92
});

const normalizeSettings = (data: any): SystemSettings => ({
  QDRANT_URL: data.QDRANT_URL ?? '',
  QDRANT_COLLECTION: data.QDRANT_COLLECTION ?? '',
  QDRANT_API_KEY: data.QDRANT_API_KEY ?? null,
  PREDICT_AUTH_KEY: data.PREDICT_AUTH_KEY ?? null,
  EMBEDDING_SERVICE_URL: data.EMBEDDING_SERVICE_URL ?? '',
  EMBEDDING_MODEL_NAME: data.EMBEDDING_MODEL_NAME ?? '',
  EMBEDDING_DEVICE: data.EMBEDDING_DEVICE ?? 'cpu',
  LLM_PROVIDER: data.LLM_PROVIDER ?? 'deepseek',
  LLM_API_KEY: data.LLM_API_KEY ?? null,
  LLM_BASE_URL: data.LLM_BASE_URL ?? null,
  LLM_MODEL: data.LLM_MODEL ?? null,
  LLM_TEMPERATURE: data.LLM_TEMPERATURE ?? 0.7,
  UTTERANCE_GENERATION_PROMPT: data.UTTERANCE_GENERATION_PROMPT ?? '',
  SKILL_ROUTE_IMPORT_PROMPT: data.SKILL_ROUTE_IMPORT_PROMPT ?? '',
  AGENT_REPAIR_PROMPT: data.AGENT_REPAIR_PROMPT ?? '',
  BATCH_SIZE: data.BATCH_SIZE ?? 32,
  DEFAULT_ROUTE_ID: data.DEFAULT_ROUTE_ID ?? 0,
  DEFAULT_ROUTE_NAME: data.DEFAULT_ROUTE_NAME ?? 'none',
  REGION_THRESHOLD_SIGNIFICANT: data.REGION_THRESHOLD_SIGNIFICANT ?? 0.85,
  INSTANCE_THRESHOLD_AMBIGUOUS: data.INSTANCE_THRESHOLD_AMBIGUOUS ?? 0.92
});

const fetchSettings = async (showResetMessage = false) => {
  loading.value = true;
  try {
    const response = await getSettings();
    settings.value = normalizeSettings(response.data as any);
    if (settings.value.PREDICT_AUTH_KEY) {
      localStorage.setItem('predict_auth_key', settings.value.PREDICT_AUTH_KEY);
    } else {
      localStorage.removeItem('predict_auth_key');
    }
    if (showResetMessage) {
      ElMessage.success(t('settings.resetSuccess'));
    }
  } catch (error) {
    ElMessage.error(t('settings.fetchError'));
  } finally {
    loading.value = false;
  }
};

const fetchQdrantCollections = async () => {
  collectionsLoading.value = true;
  try {
    const response = await getQdrantCollections();
    qdrantCollections.value = response.data.items;
  } catch (error) {
    qdrantCollections.value = [];
  } finally {
    collectionsLoading.value = false;
  }
};

const handleImportCollection = async () => {
  const collection = settings.value.QDRANT_COLLECTION?.trim();
  if (!collection) return;
  try {
    await ElMessageBox.confirm(
      t('settings.importCollectionConfirm', { collection }),
      t('settings.importCollectionTitle'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    );
    importingRoutes.value = true;
    await updateSettings(prepareSettingsForSubmit(settings.value));
    const response = await importRoutesFromQdrant(collection);
    ElMessage.success(response.data.message);
    router.push('/');
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || t('settings.importCollectionError'));
    }
  } finally {
    importingRoutes.value = false;
  }
};

const prepareSettingsForSubmit = (data: SystemSettings): Partial<SystemSettings> => {
  const result: any = { ...data };
  const nullableFields: (keyof SystemSettings)[] = [
    'LLM_API_KEY',
    'LLM_BASE_URL',
    'LLM_MODEL'
  ];
  nullableFields.forEach(field => {
    if (result[field] === '') {
      result[field] = null;
    }
  });
  return result;
};

const handleSave = async () => {
  try {
    await ElMessageBox.confirm(t('settings.saveConfirm'), t('settings.saveConfirmTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    });
    saving.value = true;
    const payload = prepareSettingsForSubmit(settings.value);
    const response = await updateSettings(payload);
    ElMessage.success(response.data.message || t('settings.saveSuccess'));
    // 更新时只更新所有已知字段
    if (response.data.settings) {
      settings.value = normalizeSettings(response.data.settings as any);
      if (settings.value.PREDICT_AUTH_KEY) {
        localStorage.setItem('predict_auth_key', settings.value.PREDICT_AUTH_KEY);
      } else {
        localStorage.removeItem('predict_auth_key');
      }
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || t('settings.saveError'));
    }
  } finally {
    saving.value = false;
  }
};

const handleLogout = () => {
  localStorage.removeItem('api_key');
  localStorage.removeItem('predict_auth_key');
  router.push('/login');
};

const handleTabChange = (tabName: any) => {
  if (tabName === 'list') {
    router.push('/');
  } else if (tabName === 'test') {
    router.push('/test');
  } else if (tabName === 'diagnostics') {
    router.push('/diagnostics');
  }
};

const getApiKeyPlaceholder = () => {
  const placeholders: Record<string, string> = {
    deepseek: 'DeepSeek API Key',
    openrouter: 'OpenRouter API Key',
    doubao: '豆包 API Key',
    qwen: '通义千问 API Key',
    gemini: 'Gemini API Key'
  };
  return placeholders[settings.value.LLM_PROVIDER] || 'API Key';
};

const getModelPlaceholder = () => {
  const placeholders: Record<string, string> = {
    deepseek: 'deepseek-chat',
    openrouter: 'openai/gpt-4',
    doubao: 'ep-20241208123456-xxxxx',
    qwen: 'qwen-turbo',
    gemini: 'gemini-pro'
  };
  return placeholders[settings.value.LLM_PROVIDER] || '模型名称';
};

const getBaseUrlPlaceholder = () => {
  const placeholders: Record<string, string> = {
    deepseek: 'https://api.deepseek.com',
    openrouter: 'https://openrouter.ai/api/v1',
    doubao: 'https://ark.cn-beijing.volces.com/api/v3',
    qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    gemini: ''
  };
  return placeholders[settings.value.LLM_PROVIDER] || 'API Base URL';
};

onMounted(() => {
  fetchSettings();
  fetchQdrantCollections();
});
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  background-color: #f5f7fa;
}

.field-hint {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}

.collection-import-button {
  margin-top: 10px;
}

.header-wrapper {
  background-color: #fff;
  border-bottom: 1px solid #e6e8eb;
  padding: 0 40px;
  height: 64px !important;
  display: flex;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  width: 95%;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-img {
  height: 40px;
  width: auto;
}

.main-wrapper {
  width: 95%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 0;
}

.page-header {
  margin-bottom: 24px;
}

.nav-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.nav-tabs :deep(.el-tabs__item) {
  min-width: 120px;
  padding: 0 5%;
  justify-content: center;
  font-size: 15px;
}

.settings-card {
  border: none;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
  padding: 20px;
}

.settings-form {
  max-width: 1000px;
  margin: 0 auto;
}

.form-actions {
  margin-top: 40px;
  display: flex;
  justify-content: center;
  gap: 20px;
}

.skill-actions {
  display: flex;
  gap: 12px;
}

:deep(.el-divider__text) {
  font-weight: bold;
  color: var(--el-color-primary);
}
</style>
