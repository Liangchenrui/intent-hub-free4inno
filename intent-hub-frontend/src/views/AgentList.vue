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

      <el-card shadow="never" class="content-card">
        <div class="toolbar">
          <div class="search-box">
            <el-input
              v-model="searchQuery"
              :placeholder="$t('agent.searchPlaceholder')"
              class="search-input"
              clearable
              @input="handleSearch"
              @clear="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
          <div class="toolbar-actions">
            <el-button
              type="danger"
              plain
              @click="handleBatchDelete"
              :disabled="selectedRouteIds.length === 0"
              :loading="batchDeleting"
            >
              {{ $t('agent.batchDelete', { count: selectedRouteIds.length }) }}
            </el-button>
            <el-button 
              @click="handleReindex" 
              :loading="reindexing"
              type="warning"
              plain
              :icon="Refresh"
            >
              {{ $t('agent.reindex') }}
            </el-button>
            <el-button
              type="info"
              plain
              @click="handleExport"
            >
              {{ $t('agent.export') }}
            </el-button>
            <el-button
              type="info"
              plain
              @click="triggerImport"
              :loading="importing"
            >
              {{ $t('agent.import') }}
            </el-button>
            <el-button type="primary" :icon="Plus" @click="handleAdd">{{ $t('agent.add') }}</el-button>
          </div>
        </div>

        <input
          ref="importFileInput"
          type="file"
          accept="application/json,.json"
          style="display: none"
          @change="handleImportFileChange"
        />
        <input
          ref="skillFileInput"
          type="file"
          accept=".md,text/markdown,text/plain"
          style="display: none"
          @change="handleSkillFileChange"
        />

        <el-table 
          ref="agentTableRef"
          v-loading="loading"
          :data="paginatedAgents"
          style="width: 100%"
          class="custom-table"
          header-cell-class-name="table-header-cell"
          row-key="id"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="48" align="center" />
          <el-table-column prop="id" :label="$t('agent.id')" width="70" align="center" />
          <el-table-column :label="$t('agent.nameDesc')" min-width="200">
            <template #default="{ row }">
              <div class="agent-info">
                <div class="agent-name">{{ row.name }}</div>
                <div class="agent-route-key">{{ row.route_key }}</div>
                <div class="agent-description">{{ row.description || $t('agent.noDescription') }}</div>
                <el-tooltip v-if="row.sync?.error" :content="row.sync.error" placement="top">
                  <el-tag size="small" :type="syncTagType(row.sync?.status)" class="sync-tag">
                    {{ syncLabel(row.sync?.status) }}
                  </el-tag>
                </el-tooltip>
                <el-tag v-else size="small" :type="syncTagType(row.sync?.status)" class="sync-tag">
                  {{ syncLabel(row.sync?.status) }}
                </el-tag>
                <el-button
                  v-if="row.sync?.status === 'error' && row.sync?.task_id"
                  link
                  type="primary"
                  size="small"
                  @click="handleRetrySync(row)"
                >
                  {{ $t('agent.syncRetry') }}
                </el-button>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="score_threshold" :label="$t('agent.threshold')" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="light">{{ row.score_threshold }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="$t('agent.utterances')" min-width="520">
            <template #default="{ row }">
              <div class="utterances-container">
                <el-tag 
                  v-for="(text, index) in row.utterances.slice(0, 10)" 
                  :key="index" 
                  class="utterance-tag"
                  size="small"
                  effect="plain"
                  round
                >
                  {{ text }}
                </el-tag>
                <el-tooltip
                  v-if="row.utterances.length > 10"
                  placement="top"
                  effect="dark"
                >
                  <template #content>
                    <div class="tooltip-utterances">
                      <div v-for="(text, idx) in row.utterances" :key="idx" class="tooltip-item">
                        {{ text }}
                      </div>
                    </div>
                  </template>
                  <el-tag 
                    size="small" 
                    type="info" 
                    effect="light" 
                    round 
                    class="more-tag"
                  >
                    +{{ row.utterances.length - 10 }}
                  </el-tag>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="$t('agent.negativeSamples')" min-width="220">
            <template #default="{ row }">
              <div class="utterances-container">
                <el-tag 
                  v-for="(text, index) in (row.negative_samples || []).slice(0, 5)" 
                  :key="index" 
                  class="utterance-tag negative-tag"
                  size="small"
                  effect="plain"
                  round
                  type="warning"
                >
                  {{ text }}
                </el-tag>
                <el-tooltip
                  v-if="(row.negative_samples || []).length > 5"
                  placement="top"
                  effect="dark"
                >
                  <template #content>
                    <div class="tooltip-utterances">
                      <div v-for="(text, idx) in (row.negative_samples || [])" :key="idx" class="tooltip-item">
                        {{ text }}
                      </div>
                    </div>
                  </template>
                  <el-tag 
                    size="small" 
                    type="warning" 
                    effect="light" 
                    round 
                    class="more-tag"
                  >
                    +{{ (row.negative_samples || []).length - 5 }}
                  </el-tag>
                </el-tooltip>
                <span v-if="!row.negative_samples || row.negative_samples.length === 0" class="empty-text">
                  {{ $t('common.empty') }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="$t('agent.actions')" width="150" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="handleEdit(row)">{{ $t('common.edit') }}</el-button>
              <el-divider direction="vertical" />
              <el-button link type="danger" @click="handleDelete(row.id)">{{ $t('common.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-bar">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="totalAgents"
            :page-size="pageSize"
            :current-page="currentPage"
            @current-change="handlePageChange"
          />
        </div>
      </el-card>
    </el-main>

    <el-dialog
      v-model="showModal"
      :title="isEdit ? $t('agent.editTitle') : $t('agent.addTitle')"
      width="90%"
      style="max-width: 650px"
      destroy-on-close
      class="custom-dialog"
    >
        <el-form :model="editForm" label-position="top">
        <div class="skill-import-bar">
          <div class="skill-import-copy">
            <div class="skill-import-title">{{ $t('agent.skillImportTitle') }}</div>
            <div class="skill-import-desc">{{ $t('agent.skillImportDesc') }}</div>
          </div>
          <el-button
            type="primary"
            plain
            :loading="importingSkill"
            @click="triggerSkillImport"
          >
            {{ $t('agent.skillImportAction') }}
          </el-button>
        </div>
        <el-form-item :label="$t('agent.nameLabel')" required>
          <el-input v-model="editForm.name" :placeholder="$t('agent.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('agent.routeKeyLabel')" required>
          <el-input v-model="editForm.route_key" :placeholder="$t('agent.routeKeyPlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('agent.descLabel')">
          <el-input 
            v-model="editForm.description" 
            type="textarea" 
            :placeholder="$t('agent.descPlaceholder')" 
            :rows="3" 
          />
        </el-form-item>
        <el-form-item :label="$t('agent.thresholdLabel')">
          <div class="threshold-container">
            <el-slider 
              v-model="editForm.score_threshold" 
              :min="0" 
              :max="1" 
              :step="0.01"
              style="flex: 1; margin-right: 20px"
            />
            <el-input-number 
              v-model="editForm.score_threshold" 
              :precision="2" 
              :step="0.05" 
              :min="0" 
              :max="1"
              size="small"
            />
          </div>
        </el-form-item>
        <el-form-item>
          <template #label>
            <div class="label-row">
              <span>{{ $t('agent.utteranceLabel') }}</span>
              <div class="ai-gen-options">
                <span class="gen-label">{{ $t('agent.genCount') }}:</span>
                <el-input-number 
                  v-model="genCount" 
                  :min="1" 
                  :max="20" 
                  size="small"
                  controls-position="right"
                  class="gen-count-input"
                />
                <el-button 
                  type="success" 
                  size="small" 
                  :loading="generating"
                  @click="handleGenerateAI"
                  :icon="MagicStick"
                >
                  {{ $t('agent.aiGen') }}
                </el-button>
              </div>
            </div>
          </template>
          <el-input 
            v-model="utterancesText" 
            type="textarea" 
            :placeholder="$t('agent.utterancePlaceholder')" 
            :rows="10" 
          />
        </el-form-item>
        <el-form-item :label="$t('agent.negativeThresholdLabel')">
          <div class="threshold-container">
            <el-slider 
              v-model="editForm.negative_threshold" 
              :min="0.8" 
              :max="1" 
              :step="0.01"
              style="flex: 1; margin-right: 20px"
            />
            <el-input-number 
              v-model="editForm.negative_threshold" 
              :precision="2" 
              :step="0.05" 
              :min="0.8" 
              :max="1"
              size="small"
            />
          </div>
        </el-form-item>
        <el-form-item :label="$t('agent.negativeSamplesLabel')">
          <el-input 
            v-model="negativeSamplesText" 
            type="textarea" 
            :placeholder="$t('agent.negativeSamplesPlaceholder')" 
            :rows="6" 
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeModal">{{ $t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">
            {{ $t('common.save') }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { debounce } from 'lodash-es';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Plus, Refresh, MagicStick } from '@element-plus/icons-vue';
import {
  clearSession,
  getRoutes,
  searchRoutes,
  deleteRoute,
  updateRoute,
  createRoute,
  generateUtterances,
  reindex,
  importRoutes,
  importRouteFromSkill,
  retrySyncTask,
  type RouteConfig,
  type GenerateUtterancesRequest
} from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';

const { t } = useI18n();

const router = useRouter();
const agents = ref<RouteConfig[]>([]);
const loading = ref(false);
const saving = ref(false);
const generating = ref(false);
const reindexing = ref(false);
const importing = ref(false);
const importingSkill = ref(false);
const batchDeleting = ref(false);
const genCount = ref(5);
const searchQuery = ref('');
const activeTab = ref('list');
const importFileInput = ref<HTMLInputElement | null>(null);
const skillFileInput = ref<HTMLInputElement | null>(null);
const agentTableRef = ref<any>(null);
const selectedRouteIds = ref<number[]>([]);
const currentPage = ref(1);
const pageSize = 10;

const totalAgents = computed(() => agents.value.length);
const paginatedAgents = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return agents.value.slice(start, start + pageSize);
});

const syncTableSelection = async () => {
  await nextTick();
  const table = agentTableRef.value;
  if (!table) {
    return;
  }
  table.clearSelection();
  paginatedAgents.value.forEach((row) => {
    if (selectedRouteIds.value.includes(row.id)) {
      table.toggleRowSelection(row, true);
    }
  });
};

const fetchAgents = async (query: string = '', silent: boolean = false) => {
  if (!silent) loading.value = true;
  try {
    const response = query.trim() 
      ? await searchRoutes(query.trim())
      : await getRoutes();
    agents.value = response.data;
    const maxPage = Math.max(1, Math.ceil(agents.value.length / pageSize));
    if (currentPage.value > maxPage) {
      currentPage.value = maxPage;
    }
    selectedRouteIds.value = selectedRouteIds.value.filter((id) => agents.value.some((agent) => agent.id === id));
    await syncTableSelection();
  } catch (error) {
    if (!silent) ElMessage.error(t('agent.fetchError'));
  } finally {
    if (!silent) loading.value = false;
  }
};

// 防抖搜索处理
const handleSearch = debounce(() => {
  currentPage.value = 1;
  fetchAgents(searchQuery.value);
}, 300);

let syncPollTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  fetchAgents();
  syncPollTimer = setInterval(() => {
    if (agents.value.some(agent => ['pending', 'queued', 'syncing'].includes(agent.sync?.status || 'pending'))) {
      fetchAgents(searchQuery.value, true);
    }
  }, 2000);
});
onBeforeUnmount(() => syncPollTimer && clearInterval(syncPollTimer));

const syncLabel = (status?: string) => t(`agent.syncStatus.${status || 'pending'}`);
const syncTagType = (status?: string) => {
  if (status === 'synced') return 'success';
  if (status === 'error') return 'danger';
  if (status === 'stale') return 'warning';
  return 'info';
};

const handleRetrySync = async (route: RouteConfig) => {
  if (!route.sync?.task_id) return;
  try {
    await retrySyncTask(route.sync.task_id);
    ElMessage.success(t('agent.syncRetryQueued'));
    await fetchAgents(searchQuery.value, true);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('agent.syncRetryError'));
  }
};

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm(t('agent.logoutConfirm'), t('agent.logoutTitle'), { type: 'warning' });
    clearSession();
    router.push('/login');
  } catch (e) {}
};

const handleTabChange = (tabName: any) => {
  if (tabName === 'test') {
    router.push('/test');
  } else if (tabName === 'diagnostics') {
    router.push('/diagnostics');
  } else if (tabName === 'settings') {
    router.push('/settings');
  }
};

watch(paginatedAgents, () => {
  syncTableSelection();
});

const showModal = ref(false);
const isEdit = ref(false);
const originalRouteKey = ref('');
const editForm = ref<Partial<RouteConfig>>({
  id: 0,
  name: '',
  route_key: '',
  description: '',
  score_threshold: 0.75,
  negative_threshold: 0.95,
  utterances: [],
  negative_samples: []
});
const utterancesText = ref('');
const negativeSamplesText = ref('');

const openModal = (agent?: RouteConfig) => {
  if (agent) {
    isEdit.value = true;
    originalRouteKey.value = agent.route_key;
    editForm.value = { ...agent };
    utterancesText.value = agent.utterances.join('\n');
    negativeSamplesText.value = (agent.negative_samples || []).join('\n');
  } else {
    isEdit.value = false;
    originalRouteKey.value = '';
    editForm.value = { 
      id: 0, 
      name: '', 
      route_key: '',
      description: '', 
      score_threshold: 0.75, 
      negative_threshold: 0.95,
      utterances: [],
      negative_samples: []
    };
    utterancesText.value = '';
    negativeSamplesText.value = '';
  }
  showModal.value = true;
};

const closeModal = () => {
  showModal.value = false;
};

const handleAdd = () => openModal();
const handleEdit = (agent: RouteConfig) => openModal(agent);

const handleReindex = async () => {
  try {
    await ElMessageBox.confirm(t('agent.reindexConfirm'), t('agent.reindexTitle'));
    reindexing.value = true;
    const response = await reindex(true);
    const { message, routes_count, total_points } = response.data;
    ElMessage.success(`${message} (${t('nav.list')}: ${routes_count}, ${t('agent.utterances')}: ${total_points})`);
    fetchAgents();
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.response?.data?.error || e?.message || t('agent.reindexError');
    ElMessage.error(t('agent.reindexErrorDetail', { detail }));
    await fetchAgents(searchQuery.value, true);
  } finally { reindexing.value = false; }
};

const triggerImport = () => {
  if (importFileInput.value) {
    // reset，确保选择同一个文件也能触发 change
    importFileInput.value.value = '';
    importFileInput.value.click();
  }
};

const triggerSkillImport = () => {
  if (skillFileInput.value) {
    skillFileInput.value.value = '';
    skillFileInput.value.click();
  }
};

const handleExport = () => {
  try {
    const data = JSON.stringify(agents.value, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'routes_config.json';
    link.click();
    URL.revokeObjectURL(url);
    ElMessage.success(t('common.success'));
  } catch (error) {
    ElMessage.error(t('common.error'));
  }
};

const handleImportFileChange = async (evt: Event) => {
  const input = evt.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  importing.value = true;
  try {
    const text = await file.text();
    const parsed = JSON.parse(text);

    if (!Array.isArray(parsed)) {
      return ElMessage.error(t('agent.importInvalidFormat'));
    }

    // 轻量前端校验：必须包含 name + utterances
    for (const item of parsed) {
      if (!item || typeof item !== 'object') {
        return ElMessage.error(t('agent.importInvalidFormat'));
      }
      if (!('name' in item) || typeof item.name !== 'string' || !item.name.trim()) {
        return ElMessage.error(t('agent.importInvalidFormat'));
      }
      if (!('route_key' in item) || typeof item.route_key !== 'string' || !item.route_key.trim()) {
        return ElMessage.error(t('agent.importInvalidFormat'));
      }
      if (!('utterances' in item) || !Array.isArray(item.utterances) || item.utterances.length === 0) {
        return ElMessage.error(t('agent.importInvalidFormat'));
      }
    }

    const resp = await importRoutes({ routes: parsed, mode: 'merge' });
    ElMessage.success(
      t('agent.importSuccess', {
        created: resp.data.created,
        updated: resp.data.updated,
        total: resp.data.total
      })
    );
    fetchAgents();
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '';
    ElMessage.error(t('agent.importError', { detail }));
  } finally {
    importing.value = false;
  }
};

const handleSkillFileChange = async (evt: Event) => {
  const input = evt.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  importingSkill.value = true;
  try {
    const skillContent = await file.text();
    if (!skillContent.trim()) {
      return ElMessage.warning(t('agent.skillImportEmpty'));
    }

    const response = await importRouteFromSkill({ skill_content: skillContent });
    const draft = response.data;

    editForm.value.name = draft.name;
    editForm.value.route_key = draft.route_key;
    editForm.value.description = draft.description;
    utterancesText.value = draft.utterances.join('\n');

    ElMessage.success(t('agent.skillImportSuccess'));
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '';
    ElMessage.error(t('agent.skillImportError', { detail }));
  } finally {
    importingSkill.value = false;
  }
};

const handleGenerateAI = async () => {
  if (!editForm.value.name) return ElMessage.warning(t('agent.inputNameWarning'));
  if (!editForm.value.route_key?.trim()) return ElMessage.warning(t('agent.routeKeyRequired'));
  generating.value = true;
  try {
    const current = utterancesText.value.split('\n').filter(s => s.trim());
    const requestData: GenerateUtterancesRequest = {
      id: editForm.value.id || 0,
      name: editForm.value.name,
      route_key: editForm.value.route_key.trim(),
      count: genCount.value,
      utterances: current
    };
    
    if (editForm.value.description) {
      requestData.description = editForm.value.description;
    }
    
    const response = await generateUtterances(requestData);
    if (response.data.utterances && response.data.utterances.length > 0) {
      utterancesText.value = response.data.utterances.join('\n');
    }
    ElMessage.success(t('agent.aiGenSuccess'));
  } catch (e) { ElMessage.error(t('agent.aiGenError')); } finally { generating.value = false; }
};

const handleSave = async () => {
  if (!editForm.value.name) return ElMessage.warning(t('agent.nameRequired'));
  if (!editForm.value.route_key?.trim()) return ElMessage.warning(t('agent.routeKeyRequired'));
  saving.value = true;
  try {
    const trimmedRouteKey = editForm.value.route_key.trim();
    if (isEdit.value && originalRouteKey.value && originalRouteKey.value !== trimmedRouteKey) {
      await ElMessageBox.confirm(
        t('agent.routeKeyChangeWarning'),
        t('agent.routeKeyChangeTitle'),
        { type: 'warning' }
      );
    }

    const data = {
      ...editForm.value,
      route_key: trimmedRouteKey,
      utterances: utterancesText.value.split('\n').filter(s => s.trim()),
      negative_samples: negativeSamplesText.value.split('\n').filter(s => s.trim()),
      negative_threshold: editForm.value.negative_threshold || 0.95
    } as RouteConfig;
    isEdit.value ? await updateRoute(data.id, data) : await createRoute(data);
    ElMessage.success(t('agent.saveQueued'));
    closeModal();
    currentPage.value = 1;
    fetchAgents(searchQuery.value);
  } catch (e: any) {
    const detail = e?.response?.data?.detail;
    ElMessage.error(detail || t('agent.saveError'));
  } finally { saving.value = false; }
};

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm(t('agent.deleteConfirm'), t('agent.deleteTitle'), { type: 'error' });
    await deleteRoute(id);
    ElMessage.success(t('agent.deleteSuccess'));
    selectedRouteIds.value = selectedRouteIds.value.filter((item) => item !== id);
    fetchAgents(searchQuery.value);
  } catch (e) {}
};

const handleSelectionChange = (selection: RouteConfig[]) => {
  const pageIds = paginatedAgents.value.map((item) => item.id);
  const selectedOnPage = selection.map((item) => item.id);
  selectedRouteIds.value = [
    ...selectedRouteIds.value.filter((id) => !pageIds.includes(id)),
    ...selectedOnPage,
  ];
};

const handlePageChange = (page: number) => {
  currentPage.value = page;
};

const handleBatchDelete = async () => {
  if (selectedRouteIds.value.length === 0) {
    return;
  }

  try {
    const deleteCount = selectedRouteIds.value.length;
    await ElMessageBox.confirm(
      t('agent.batchDeleteConfirm', { count: deleteCount }),
      t('agent.batchDeleteTitle'),
      { type: 'error' }
    );
    batchDeleting.value = true;

    for (const id of [...selectedRouteIds.value]) {
      await deleteRoute(id);
    }

    selectedRouteIds.value = [];
    ElMessage.success(t('agent.batchDeleteSuccess', { count: deleteCount }));
    await fetchAgents(searchQuery.value);
  } catch (e: any) {
    if (e !== 'cancel') {
      const detail = e?.response?.data?.detail;
      ElMessage.error(detail || t('agent.batchDeleteError'));
    }
  } finally {
    batchDeleting.value = false;
  }
};
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

.content-card {
  border: none;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 40%;
}

.search-input {
  width: 100%;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.agent-name {
  font-weight: 600;
  color: #303133;
}

.agent-description {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.agent-route-key {
  font-size: 12px;
  color: #409eff;
  font-family: 'Courier New', Courier, monospace;
}

.utterances-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 0;
}

.utterance-tag {
  height: auto !important;
  padding: 4px 10px;
  white-space: normal;
  text-align: left;
  line-height: 1.5;
}

.more-tag {
  cursor: pointer;
}

.tooltip-utterances {
  max-width: 300px;
  max-height: 400px;
  overflow-y: auto;
  padding: 4px;
}

.tooltip-item {
  padding: 4px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
  line-height: 1.4;
}

.tooltip-item:last-child {
  border-bottom: none;
}

.negative-tag {
  border-color: #e6a23c;
}

.empty-text {
  color: #909399;
  font-size: 12px;
  font-style: italic;
}

.threshold-container {
  display: flex;
  align-items: center;
  background: #f8f9fb;
  padding: 8px 16px;
  border-radius: 8px;
}

.skill-import-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding: 14px 16px;
  background: #f8f9fb;
  border: 1px dashed #d7deea;
  border-radius: 12px;
}

.skill-import-copy {
  min-width: 0;
}

.skill-import-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.skill-import-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.ai-gen-options {
  display: flex;
  align-items: center;
  gap: 12px;
}

.gen-label {
  font-size: 12px;
  color: #606266;
}

.gen-count-input {
  width: 90px;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

:deep(.table-header-cell) {
  background-color: #f8f9fb !important;
  color: #606266;
  font-weight: 700;
}

:deep(.custom-dialog) {
  border-radius: 16px;
}

:deep(.el-dialog__header) {
  margin-right: 0;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 16px;
}
</style>
