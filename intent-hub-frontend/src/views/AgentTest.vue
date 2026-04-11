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

      <el-card shadow="never" class="test-card">
        <div v-if="!hasFullReindex" class="warning-banner">
          <el-alert
            :title="$t('test.title')"
            type="warning"
            :closable="false"
            show-icon
          >
            <template #default>
              <span>{{ $t('test.warningMessage') }}</span>
              <el-button 
                type="primary" 
                size="small" 
                :loading="reindexing"
                @click="handleReindex"
                style="margin-left: 8px;"
              >
                {{ $t('test.sync') }}
              </el-button>
            </template>
          </el-alert>
        </div>
        <div class="input-section">
          <el-input 
            v-model="queryText" 
            :placeholder="$t('test.placeholder')" 
            size="large"
            clearable
            :disabled="!hasFullReindex"
            @keyup.enter="handleTest"
          >
            <template #prefix>
              <el-icon><ChatLineRound /></el-icon>
            </template>
            <template #append>
              <el-button 
                type="primary" 
                :loading="loading" 
                :disabled="!hasFullReindex"
                @click="handleTest"
              >
                {{ $t('test.test') }}
              </el-button>
            </template>
          </el-input>
        </div>

        <div v-if="results.length > 0" class="results-section">
          <div class="results-header">
            <h3>{{ $t('test.resultsTitle', { count: results.length }) }}</h3>
            <el-divider />
          </div>
          <div class="results-list">
            <el-card 
              v-for="(result, index) in results" 
              :key="`${result.id}-${result.route_key}`" 
              class="result-item" 
              :class="{ 'top-match': index === 0 }"
              shadow="hover"
            >
              <div class="result-info">
                <div class="name-box">
                  <el-tag v-if="index === 0" size="small" type="success" effect="dark" class="match-badge">{{ $t('test.bestMatch') }}</el-tag>
                  <div class="result-title">
                    <span class="result-name">{{ result.name }}</span>
                    <span class="result-route-key">{{ result.route_key }}</span>
                  </div>
                </div>
                <el-tag size="small" type="info" effect="plain">ID: {{ result.id }}</el-tag>
              </div>
              <div class="result-score">
                <div class="score-label">{{ $t('test.confidenceScore') }}</div>
                <div class="score-bar-container">
                  <el-progress 
                    :percentage="Math.min(Math.round((result.score || 0) * 100), 100)" 
                    :status="(result.score || 0) > 0.7 ? 'success' : ((result.score || 0) > 0.4 ? 'warning' : 'exception')"
                    :stroke-width="14"
                    :show-text="false"
                  />
                </div>
                <div class="score-number">{{ (result.score || 0).toFixed(4) }}</div>
              </div>
            </el-card>
          </div>
        </div>
        <div v-else-if="hasTested && !loading" class="empty-results">
          <el-empty :description="$t('test.noMatch')" :image-size="120" />
        </div>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ChatLineRound } from '@element-plus/icons-vue';
import { predict, reindex, type PredictResult } from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';

const { t } = useI18n();

const router = useRouter();
const queryText = ref('');
const results = ref<PredictResult[]>([]);
const loading = ref(false);
const hasTested = ref(false);
const activeTab = ref('test');
const reindexing = ref(false);

// 检查是否已完成全量同步
const hasFullReindex = computed(() => {
  return !!localStorage.getItem('last_full_reindex');
});

const handleLogout = () => {
  localStorage.removeItem('api_key');
  localStorage.removeItem('predict_auth_key');
  router.push('/login');
};

const handleTabChange = (tabName: any) => {
  if (tabName === 'list') {
    router.push('/');
  } else if (tabName === 'diagnostics') {
    router.push('/diagnostics');
  } else if (tabName === 'settings') {
    router.push('/settings');
  }
};

const handleReindex = async () => {
  try {
    await ElMessageBox.confirm(t('agent.reindexConfirm'), t('agent.reindexTitle'));
    reindexing.value = true;
    try {
      const response = await reindex(true);
      const { message, routes_count, total_points } = response.data;
      // 保存全量同步时间戳
      localStorage.setItem('last_full_reindex', Date.now().toString());
      ElMessage.success(`${message} (${t('nav.list')}: ${routes_count}, ${t('agent.utterances')}: ${total_points})`);
    } catch (error) {
      ElMessage.error(t('test.reindexError'));
    } finally {
      reindexing.value = false;
    }
  } catch (e) {
    // 用户取消
  }
};

const handleTest = async () => {
  if (!queryText.value.trim()) return ElMessage.warning(t('test.inputQueryWarning'));

  // 检查是否已完成全量同步
  const lastReindex = localStorage.getItem('last_full_reindex');
  if (!lastReindex) {
    ElMessage.warning(t('test.syncFirstWarning'));
    return;
  }

  loading.value = true;
  hasTested.value = true;
  try {
    const response = await predict(queryText.value);
    results.value = response.data;
  } catch (error) {
    ElMessage.error(t('test.predictError'));
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.layout-container {
  min-width: 160px;
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

.test-card {
  border: none;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
  padding: 16px;
}

.input-section {
  margin-bottom: 32px;
}

.results-section {
  margin-top: 24px;
}

.results-header h3 {
  margin: 0 0 12px 0;
  font-size: 18px;
  color: #303133;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  border-radius: 10px;
  border: 1px solid #ebeef5;
  transition: all 0.3s;
}

.top-match {
  border-left: 4px solid var(--el-color-success);
  background-color: #f0f9eb;
}

.result-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.name-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.result-name {
  font-weight: 700;
  color: #303133;
  font-size: 16px;
}

.result-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-route-key {
  font-size: 12px;
  color: #409eff;
  font-family: 'Courier New', Courier, monospace;
}

.match-badge {
  font-weight: normal;
}

.result-score {
  display: flex;
  align-items: center;
  gap: 16px;
}

.score-label {
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
}

.score-bar-container {
  flex: 1;
  min-width: 0; /* 防止溢出 */
}

.score-number {
  font-family: 'Courier New', Courier, monospace;
  font-weight: 600;
  color: #606266;
  min-width: 60px;
  text-align: right;
  font-size: 14px;
}

.empty-results {
  padding: 40px 0;
}

.warning-banner {
  margin-bottom: 20px;
}
</style>
