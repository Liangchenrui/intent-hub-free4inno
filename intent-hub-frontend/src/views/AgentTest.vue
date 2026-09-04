<template>
  <el-container class="layout-container">
    <el-header class="header-wrapper">
      <div class="header-content">
        <div class="brand">
          <img src="@/assets/logo.png" alt="Intent Hub" class="logo-img" />
        </div>
        <div class="user-info">
          <ServiceHealthIndicators />
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
              :class="{ 'top-match': index === 0 && !isNoneRoute(result), 'none-match': isNoneRoute(result) }"
              shadow="hover"
            >
              <div class="result-info">
                <div class="name-box">
                  <el-tag v-if="index === 0 && !isNoneRoute(result)" size="small" type="success" effect="dark" class="match-badge">{{ $t('test.bestMatch') }}</el-tag>
                  <el-tag v-else-if="isNoneRoute(result)" size="small" type="info" effect="plain" class="match-badge">{{ $t('test.noRouteBadge') }}</el-tag>
                  <div class="result-title">
                    <span class="result-name">{{ isNoneRoute(result) ? $t('test.noRouteTitle') : result.name }}</span>
                    <span v-if="isNoneRoute(result)" class="result-route-key none-route-copy">{{ $t('test.noRouteDescription') }}</span>
                    <span v-else class="result-route-key">{{ result.route_key }}</span>
                  </div>
                </div>
                <el-tag v-if="!isNoneRoute(result)" size="small" type="info" effect="plain">ID: {{ result.id }}</el-tag>
              </div>
              <div class="result-score">
                <div class="score-label">{{ $t('test.confidenceScore') }}</div>
                <div class="score-bar-container">
                  <el-progress 
                    :percentage="Math.min(Math.round((result.score || 0) * 100), 100)" 
                    :status="isNoneRoute(result) ? 'warning' : ((result.score || 0) > 0.7 ? 'success' : ((result.score || 0) > 0.4 ? 'warning' : 'exception'))"
                    :stroke-width="14"
                    :show-text="false"
                  />
                </div>
                <div class="score-number">{{ result.score == null ? '--' : result.score.toFixed(4) }}</div>
              </div>
              <div v-if="!isNoneRoute(result)" class="feedback-actions">
                <el-button
                  circle
                  class="feedback-button positive-button"
                  :class="{ 'is-active': getFeedbackState(result.id) === 'positive', 'is-pending': isFeedbackPending(result.id) }"
                  :disabled="isFeedbackPending(result.id)"
                  @click="handleFeedback(result, 'positive')"
                >
                  <span class="thumb-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none">
                      <path
                        d="M7 21V9"
                        stroke="currentColor"
                        stroke-width="1.9"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                      <path
                        d="M14.7 4.2 11.9 9H19a2 2 0 0 1 1.94 2.5l-1.4 5A2 2 0 0 1 17.62 18H7V9.8a2 2 0 0 1 .58-1.4l4.83-4.95a1.15 1.15 0 0 1 1.93 1.11Z"
                        stroke="currentColor"
                        stroke-width="1.9"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </span>
                </el-button>
                <el-button
                  circle
                  class="feedback-button negative-button"
                  :class="{ 'is-active': getFeedbackState(result.id) === 'negative', 'is-pending': isFeedbackPending(result.id) }"
                  :disabled="isFeedbackPending(result.id)"
                  @click="handleFeedback(result, 'negative')"
                >
                  <span class="thumb-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none">
                      <path
                        d="M17 3v12"
                        stroke="currentColor"
                        stroke-width="1.9"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                      <path
                        d="M9.3 19.8 12.1 15H5a2 2 0 0 1-1.94-2.5l1.4-5A2 2 0 0 1 6.38 6H17v8.2a2 2 0 0 1-.58 1.4l-4.83 4.95a1.15 1.15 0 0 1-1.93-1.11Z"
                        stroke="currentColor"
                        stroke-width="1.9"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </span>
                </el-button>
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
import { ref, computed, onBeforeUnmount, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ChatLineRound } from '@element-plus/icons-vue';
import {
  clearSession,
  getRoutes,
  getSyncTasks,
  deleteNegativeRouteFeedback,
  deletePositiveRouteFeedback,
  predict,
  reindex,
  submitNegativeRouteFeedback,
  submitPositiveRouteFeedback,
  type PredictResult,
  type RouteConfig,
  type SyncTask,
} from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';
import ServiceHealthIndicators from '../components/ServiceHealthIndicators.vue';

const { t } = useI18n();

const router = useRouter();
const queryText = ref('');
const results = ref<PredictResult[]>([]);
const loading = ref(false);
const hasTested = ref(false);
const activeTab = ref('test');
const reindexing = ref(false);
const reindexTaskId = ref<string>();
const feedbackState = ref<Record<number, 'positive' | 'negative' | undefined>>({});
const feedbackPending = ref<Record<number, boolean | undefined>>({});

const routes = ref<RouteConfig[]>([]);
const routesLoaded = ref(false);

const refreshRouteSyncState = async () => {
  try {
    routes.value = (await getRoutes()).data;
    routesLoaded.value = true;
  } catch (_) {
    routesLoaded.value = false;
  }
};

let syncPollTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  refreshRouteSyncState();
  refreshReindexTask();
  syncPollTimer = setInterval(() => {
    if (!hasFullReindex.value) refreshRouteSyncState();
    if (reindexing.value || reindexTaskId.value) refreshReindexTask();
  }, 2000);
});
onBeforeUnmount(() => syncPollTimer && clearInterval(syncPollTimer));

const refreshReindexTask = async () => {
  try {
    const tasks = (await getSyncTasks()).data;
    let task: SyncTask | undefined;
    if (reindexTaskId.value) {
      task = tasks.find(item => item.id === reindexTaskId.value);
    } else {
      task = [...tasks].reverse().find(item =>
        item.kind === 'incremental_reindex' && ['queued', 'running'].includes(item.status)
      );
      if (task) reindexTaskId.value = task.id;
    }
    if (!task) return;
    if (['queued', 'running'].includes(task.status)) {
      reindexing.value = true;
      return;
    }

    reindexing.value = false;
    reindexTaskId.value = undefined;
    await refreshRouteSyncState();
    if (task.status === 'succeeded') {
      const result = task.result || {};
      ElMessage.success(t('agent.reindexSuccessDetail', {
        created: result.new_routes || 0,
        updated: result.updated_routes || 0,
        deleted: result.deleted_routes || 0,
        skipped: result.skipped_routes || 0,
      }));
    } else if (task.status === 'error') {
      ElMessage.error(t('test.reindexErrorDetail', { detail: task.error || t('test.reindexError') }));
    }
  } catch (_) {
    // Route readiness polling remains available if task polling is temporarily unavailable.
  }
};

// Backend route versions are the source of truth for index readiness.
const hasFullReindex = computed(() => {
  return routesLoaded.value && routes.value.every(route => route.sync?.status === 'synced');
});

const handleLogout = () => {
  clearSession();
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
      const response = await reindex();
      reindexTaskId.value = response.data.id;
      ElMessage.success(t('agent.reindexQueued'));
      refreshReindexTask();
    } catch (error: any) {
      reindexing.value = false;
      const detail = error?.response?.data?.detail || error?.response?.data?.error || error?.message || t('test.reindexError');
      ElMessage.error(t('test.reindexErrorDetail', { detail }));
      await refreshRouteSyncState();
    }
  } catch (e) {
    // 用户取消
  }
};

const handleTest = async () => {
  if (!queryText.value.trim()) return ElMessage.warning(t('test.inputQueryWarning'));

  if (!hasFullReindex.value) {
    ElMessage.warning(t('test.syncFirstWarning'));
    return;
  }

  loading.value = true;
  hasTested.value = true;
  try {
    const response = await predict(queryText.value);
    results.value = response.data;
    feedbackState.value = {};
    feedbackPending.value = {};
  } catch (error) {
    ElMessage.error(t('test.predictError'));
  } finally {
    loading.value = false;
  }
};

const isNoneRoute = (result: PredictResult) => result.route_key === 'none';
const getFeedbackState = (routeId: number) => feedbackState.value[routeId];
const isFeedbackPending = (routeId: number) => Boolean(feedbackPending.value[routeId]);

const handleFeedback = async (result: PredictResult, feedbackType: 'positive' | 'negative') => {
  const text = queryText.value.trim();
  if (!text) {
    ElMessage.warning(t('test.inputQueryWarning'));
    return;
  }

  const previousState = feedbackState.value[result.id];
  const nextState = previousState === feedbackType ? undefined : feedbackType;
  feedbackState.value = {
    ...feedbackState.value,
    [result.id]: nextState,
  };
  feedbackPending.value = {
    ...feedbackPending.value,
    [result.id]: true,
  };
  try {
    if (previousState === feedbackType) {
      if (feedbackType === 'positive') {
        await deletePositiveRouteFeedback(result.id, text);
      } else {
        await deleteNegativeRouteFeedback(result.id, text);
      }
    } else if (feedbackType === 'positive') {
      await submitPositiveRouteFeedback(result.id, text);
    } else {
      await submitNegativeRouteFeedback(result.id, text);
    }
    ElMessage({
      type: 'success',
      message: t('test.feedbackSyncHint'),
    });
  } catch (error) {
    feedbackState.value = {
      ...feedbackState.value,
      [result.id]: previousState,
    };
    ElMessage.error(t('test.feedbackError'));
  } finally {
    feedbackPending.value = {
      ...feedbackPending.value,
      [result.id]: false,
    };
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

.none-match {
  border-left: 4px solid var(--el-color-warning);
  background-color: #fff8eb;
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

.feedback-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.feedback-button {
  width: 40px;
  height: 40px;
  border-width: 1px;
  transition: all 0.2s ease;
}

.thumb-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
}

.thumb-icon svg {
  width: 22px;
  height: 22px;
}

.feedback-button.is-pending {
  opacity: 0.7;
}

.positive-button {
  border-color: #d0d5dd;
  color: #475467;
  background: #ffffff;
}

.positive-button.is-active {
  border-color: #1f2937;
  color: #ffffff;
  background: #1f2937;
}

.negative-button {
  border-color: #d0d5dd;
  color: #475467;
  background: #ffffff;
}

.negative-button.is-active {
  border-color: #1f2937;
  color: #ffffff;
  background: #1f2937;
}

.feedback-button:not(.is-active):hover {
  border-color: #98a2b3;
  color: #111827;
  background: #f8fafc;
}

.none-route-copy {
  color: #909399;
  white-space: normal;
}

.empty-results {
  padding: 40px 0;
}

.warning-banner {
  margin-bottom: 20px;
}
</style>
