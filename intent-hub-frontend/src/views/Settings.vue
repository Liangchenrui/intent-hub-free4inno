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
          <el-divider :content-position="'left'">{{ $t('settings.qdrantTitle') }}</el-divider>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('settings.qdrantUrl')">
                <el-input v-model="settings.QDRANT_URL" :placeholder="$t('settings.qdrantUrlPlaceholder')" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('settings.collection')">
                <el-input v-model="settings.QDRANT_COLLECTION" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item :label="$t('settings.qdrantApiKey')">
            <el-input v-model="settings.QDRANT_API_KEY" type="password" show-password :placeholder="$t('settings.qdrantApiKeyPlaceholder')" />
          </el-form-item>

          <el-divider :content-position="'left'">{{ $t('settings.embeddingTitle') }}</el-divider>
          <el-form-item :label="$t('settings.embeddingServiceUrl')">
            <el-input 
              v-model="settings.EMBEDDING_SERVICE_URL" 
              :placeholder="$t('settings.embeddingServiceUrlPlaceholder')" 
            />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ $t('settings.embeddingServiceUrlHint') }}
            </div>
          </el-form-item>
          <el-row :gutter="20">
            <el-col :span="16">
              <el-form-item :label="$t('settings.modelName')">
                <el-input 
                  v-model="settings.EMBEDDING_MODEL_NAME" 
                  :placeholder="$t('settings.modelNamePlaceholder')" 
                />
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.modelNameHint') }}
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('settings.embeddingDevice')">
                <el-select v-model="settings.EMBEDDING_DEVICE" style="width: 100%">
                  <el-option label="CPU" value="cpu" />
                  <el-option label="CUDA" value="cuda" />
                  <el-option label="MPS" value="mps" />
                </el-select>
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.embeddingDeviceHint') }}
                </div>
              </el-form-item>
            </el-col>
          </el-row>

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

          <el-divider :content-position="'left'">{{ $t('settings.policyTitle') }}</el-divider>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item :label="$t('settings.authEnabled')">
                <el-switch v-model="settings.AUTH_ENABLED" />
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.authEnabledHint') }}
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="16">
              <el-form-item v-if="settings.AUTH_ENABLED" :label="$t('settings.apiKeys')">
                <el-input 
                  v-model="settings.API_KEYS" 
                  :placeholder="$t('settings.apiKeysPlaceholder')" 
                />
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  {{ $t('settings.apiKeysHint') }}
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('settings.username')">
                <el-input 
                  v-model="settings.DEFAULT_USERNAME" 
                  :placeholder="$t('settings.usernamePlaceholder')" 
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('settings.password')">
                <el-input 
                  v-model="settings.DEFAULT_PASSWORD" 
                  type="password" 
                  show-password 
                  :placeholder="$t('settings.passwordPlaceholder')" 
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item :label="$t('settings.predictAuthKey')">
            <el-input 
              v-model="settings.PREDICT_AUTH_KEY" 
              type="password" 
              show-password 
              :placeholder="$t('settings.predictAuthKeyPlaceholder')" 
            />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ $t('settings.predictAuthKeyHint') }}
            </div>
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
import { getSettings, updateSettings, type Settings } from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';

const { t } = useI18n();

const router = useRouter();
const activeTab = ref('settings');
const loading = ref(false);
const saving = ref(false);

const settings = ref<Settings>({
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
  SKILL_ROUTE_IMPORT_PROMPT: '',
  AGENT_REPAIR_PROMPT: '',
  AUTH_ENABLED: true,
  API_KEYS: '',
  PREDICT_AUTH_KEY: null,
  DEFAULT_USERNAME: 'admin',
  DEFAULT_PASSWORD: '',
  BATCH_SIZE: 32,
  DEFAULT_ROUTE_ID: 0,
  DEFAULT_ROUTE_NAME: 'none',
  REGION_THRESHOLD_SIGNIFICANT: 0.85,
  INSTANCE_THRESHOLD_AMBIGUOUS: 0.92
});

const fetchSettings = async (showResetMessage = false) => {
  loading.value = true;
  try {
    const response = await getSettings();
    const data = response.data as any;
    settings.value = {
      QDRANT_URL: data.QDRANT_URL ?? '',
      QDRANT_COLLECTION: data.QDRANT_COLLECTION ?? '',
      QDRANT_API_KEY: data.QDRANT_API_KEY ?? null,
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
      AUTH_ENABLED: data.AUTH_ENABLED ?? true,
      API_KEYS: data.API_KEYS ?? '',
      PREDICT_AUTH_KEY: data.PREDICT_AUTH_KEY ?? null,
      DEFAULT_USERNAME: data.DEFAULT_USERNAME ?? 'admin',
      DEFAULT_PASSWORD: data.DEFAULT_PASSWORD ?? '',
      BATCH_SIZE: data.BATCH_SIZE ?? 32,
      DEFAULT_ROUTE_ID: data.DEFAULT_ROUTE_ID ?? 0,
      DEFAULT_ROUTE_NAME: data.DEFAULT_ROUTE_NAME ?? 'none',
      REGION_THRESHOLD_SIGNIFICANT: data.REGION_THRESHOLD_SIGNIFICANT ?? 0.85,
      INSTANCE_THRESHOLD_AMBIGUOUS: data.INSTANCE_THRESHOLD_AMBIGUOUS ?? 0.92
    };
    // 将 Predict Key 保存到本地存储，供测试页面使用
    if (data.PREDICT_AUTH_KEY) {
      localStorage.setItem('predict_auth_key', data.PREDICT_AUTH_KEY);
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

const prepareSettingsForSubmit = (data: Settings): Partial<Settings> => {
  const result: any = { ...data };
  const nullableFields: (keyof Settings)[] = [
    'QDRANT_API_KEY',
    'LLM_API_KEY',
    'LLM_BASE_URL',
    'LLM_MODEL',
    'PREDICT_AUTH_KEY'
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
      const data = response.data.settings as any;
      settings.value = {
        QDRANT_URL: data.QDRANT_URL ?? '',
        QDRANT_COLLECTION: data.QDRANT_COLLECTION ?? '',
        QDRANT_API_KEY: data.QDRANT_API_KEY ?? null,
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
        AUTH_ENABLED: data.AUTH_ENABLED ?? true,
        API_KEYS: data.API_KEYS ?? '',
        PREDICT_AUTH_KEY: data.PREDICT_AUTH_KEY ?? null,
        DEFAULT_USERNAME: data.DEFAULT_USERNAME ?? 'admin',
        DEFAULT_PASSWORD: data.DEFAULT_PASSWORD ?? '',
        BATCH_SIZE: data.BATCH_SIZE ?? 32,
        DEFAULT_ROUTE_ID: data.DEFAULT_ROUTE_ID ?? 0,
        DEFAULT_ROUTE_NAME: data.DEFAULT_ROUTE_NAME ?? 'none',
        REGION_THRESHOLD_SIGNIFICANT: data.REGION_THRESHOLD_SIGNIFICANT ?? 0.85,
        INSTANCE_THRESHOLD_AMBIGUOUS: data.INSTANCE_THRESHOLD_AMBIGUOUS ?? 0.92
      };
      // 将 Predict Key 保存到本地存储，供测试页面使用
      if (data.PREDICT_AUTH_KEY) {
        localStorage.setItem('predict_auth_key', data.PREDICT_AUTH_KEY);
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
});
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  background-color: #f5f7fa;
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

:deep(.el-divider__text) {
  font-weight: bold;
  color: var(--el-color-primary);
}
</style>
