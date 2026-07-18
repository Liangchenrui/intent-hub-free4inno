<template>
  <div class="page-intro">
    <div>
      <h1>Agent 管理</h1>
      <p>查看上游 Agent 快照、语料与向量同步状态</p>
    </div>
  </div>

  <el-card v-if="status" shadow="never" class="panel-card status-card">
    <div class="status-summary">
      <div class="status-copy">
        <span class="status-dot" :class="{ warning: !status.synced }" />
        <div>
          <strong>{{ status.synced ? '向量数据已同步' : '向量数据需要同步' }}</strong>
          <p>{{ status.synced ? '当前 Agent 快照与向量数据库一致' : '当前快照与向量数据库存在差异' }}</p>
        </div>
      </div>
      <div class="status-metrics">
        <div><span>Agent 快照</span><strong>{{ status.agents_count }}</strong></div>
        <div><span>Collection</span><strong class="collection-name">{{ status.collection }}</strong></div>
        <div><span>向量点数</span><strong>{{ status.points_count }} / {{ status.expected_points }}</strong></div>
      </div>
    </div>
  </el-card>

  <el-card shadow="never" class="panel-card content-card">
    <div class="toolbar">
      <el-input v-model="query" clearable placeholder="搜索 Agent 名称或描述">
        <template #prefix><span class="search-mark">⌕</span></template>
      </el-input>
      <el-button type="primary" :loading="syncing" @click="sync">同步 Agent</el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="filtered"
      class="agent-table"
      header-cell-class-name="table-header-cell"
      row-key="id"
    >
      <el-table-column prop="id" label="ID" width="86" align="center" />
      <el-table-column label="名称与描述" min-width="260">
        <template #default="{ row }">
          <div class="agent-info">
            <strong>{{ row.title }}</strong>
            <span>{{ plainText(row.text) || '暂无描述' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="正向阈值" width="110" align="center">
        <template #default="{ row }"><el-tag size="small" effect="light">{{ row.score_threshold }}</el-tag></template>
      </el-table-column>
      <el-table-column label="负向阈值" width="110" align="center">
        <template #default="{ row }"><el-tag size="small" type="warning" effect="light">{{ row.negative_threshold }}</el-tag></template>
      </el-table-column>
      <el-table-column label="正向语料" min-width="260">
        <template #default="{ row }">
          <div class="corpus-list">
            <el-tag v-for="text in row.utterances.slice(0, 3)" :key="text" size="small" effect="plain" round>{{ text }}</el-tag>
            <el-tag v-if="row.utterances.length > 3" size="small" type="info" effect="light" round>+{{ row.utterances.length - 3 }}</el-tag>
            <span v-if="!row.utterances.length" class="empty-text">暂无语料</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="负向语料" min-width="220">
        <template #default="{ row }">
          <div class="corpus-list">
            <el-tag v-for="text in row.negative_samples.slice(0, 2)" :key="text" size="small" type="warning" effect="plain" round>{{ text }}</el-tag>
            <el-tag v-if="row.negative_samples.length > 2" size="small" type="info" effect="light" round>+{{ row.negative_samples.length - 2 }}</el-tag>
            <span v-if="!row.negative_samples.length" class="empty-text">暂无语料</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" align="center" fixed="right">
        <template #default="{ row }"><el-button link type="primary" @click="show(row)">查看详情</el-button></template>
      </el-table-column>
      <template #empty><el-empty description="暂无 Agent 数据" /></template>
    </el-table>
  </el-card>

  <el-dialog v-model="detailsVisible" title="Agent 详情" width="720px" class="agent-dialog">
    <el-form v-if="selected" label-position="top" class="detail-form">
      <el-row :gutter="16">
        <el-col :xs="24" :sm="12">
          <el-form-item label="ID"><el-input :model-value="selected.id" disabled /></el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12">
          <el-form-item label="名称"><el-input :model-value="selected.title" disabled /></el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="描述"><el-input :model-value="plainText(selected.text)" type="textarea" :rows="4" disabled /></el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="正向语料"><el-input :model-value="selected.utterances.join('\n')" type="textarea" :rows="5" disabled /></el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12">
          <el-form-item label="正向阈值">
            <el-input-number v-model="thresholds.score_threshold" :min="0" :max="1" :step="0.01" :precision="2" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="负向语料"><el-input :model-value="selected.negative_samples.join('\n')" type="textarea" :rows="5" disabled /></el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12">
          <el-form-item label="负向阈值">
            <el-input-number v-model="thresholds.negative_threshold" :min="0" :max="1" :step="0.01" :precision="2" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button @click="detailsVisible = false">取消</el-button>
      <el-button type="primary" :loading="savingThresholds" @click="saveThresholds">保存阈值</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { getAgents, getSyncStatus, syncAgents, updateAgentThresholds, type Agent, type SyncStatus } from '../api';

const agents = ref<Agent[]>([]);
const query = ref('');
const loading = ref(false);
const syncing = ref(false);
const detailsVisible = ref(false);
const selected = ref<Agent>();
const status = ref<SyncStatus>();
const savingThresholds = ref(false);
const thresholds = ref({ score_threshold: 0.8, negative_threshold: 0.95 });
const plainText = (value: unknown) => {
  if (value == null) return '';
  return new DOMParser().parseFromString(String(value), 'text/html').body.textContent?.trim() || '';
};
const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  return keyword
    ? agents.value.filter((agent) => `${agent.title} ${agent.text}`.toLowerCase().includes(keyword))
    : agents.value;
});

const load = async () => {
  loading.value = true;
  try { agents.value = (await getAgents()).data; }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '获取 Agent 失败'); }
  finally { loading.value = false; }
};
const loadStatus = async () => {
  try { status.value = (await getSyncStatus()).data; }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '获取同步状态失败'); }
};
const sync = async () => {
  syncing.value = true;
  try {
    const { data } = await syncAgents();
    await Promise.all([load(), loadStatus()]);
    data.warning
      ? ElMessage.warning(data.warning)
      : ElMessage.success(`同步完成：${data.agents_count} 个 Agent`);
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '同步失败');
    await Promise.all([load(), loadStatus()]);
  } finally { syncing.value = false; }
};
const show = (agent: Agent) => {
  selected.value = agent;
  thresholds.value = {
    score_threshold: agent.score_threshold,
    negative_threshold: agent.negative_threshold,
  };
  detailsVisible.value = true;
};
const saveThresholds = async () => {
  if (!selected.value) return;
  savingThresholds.value = true;
  try {
    selected.value = (await updateAgentThresholds(
      selected.value.id,
      thresholds.value.score_threshold,
      thresholds.value.negative_threshold,
    )).data;
    await Promise.all([load(), loadStatus()]);
    ElMessage.success('阈值已保存并同步到向量数据库');
    detailsVisible.value = false;
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '阈值保存失败');
  } finally { savingThresholds.value = false; }
};
onMounted(() => Promise.all([load(), loadStatus()]));
</script>

<style scoped>
.status-card { margin-bottom: 18px; }
.status-card :deep(.el-card__body) { padding: 18px 22px; }
.status-summary, .status-copy, .status-metrics { display: flex; align-items: center; }
.status-summary { justify-content: space-between; gap: 28px; }
.status-copy { gap: 14px; min-width: 230px; }
.status-copy strong { display: block; margin-bottom: 4px; font-size: 15px; }
.status-copy p { margin: 0; color: #909399; font-size: 12px; }
.status-dot { width: 10px; height: 10px; flex: 0 0 auto; border-radius: 50%; background: #67c23a; box-shadow: 0 0 0 5px #eaf7e5; }
.status-dot.warning { background: #e6a23c; box-shadow: 0 0 0 5px #fdf3e4; }
.status-metrics { flex: 1; justify-content: flex-end; }
.status-metrics > div { min-width: 130px; padding: 2px 26px; border-left: 1px solid #ebeef5; }
.status-metrics span, .status-metrics strong { display: block; }
.status-metrics span { margin-bottom: 6px; color: #909399; font-size: 12px; }
.status-metrics strong { color: #303133; font-size: 17px; }
.status-metrics .collection-name { max-width: 220px; overflow: hidden; font-family: Consolas, monospace; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.content-card :deep(.el-card__body) { padding: 22px 24px; }
.search-mark { color: #909399; font-size: 20px; line-height: 1; transform: rotate(-20deg); }
.agent-info { display: flex; flex-direction: column; gap: 5px; padding: 7px 0; }
.agent-info strong { color: #303133; font-size: 14px; }
.agent-info span { max-width: 440px; overflow: hidden; color: #909399; font-size: 12px; line-height: 1.5; text-overflow: ellipsis; white-space: nowrap; }
.corpus-list { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 0; }
.corpus-list :deep(.el-tag) { max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
.empty-text { color: #b1b3b8; font-size: 12px; font-style: italic; }
:deep(.table-header-cell) { height: 48px; color: #606266; background: #f8f9fb !important; font-weight: 700; }
:deep(.agent-table .el-table__row:hover > td) { background: #f7faff !important; }
:deep(.agent-dialog) { max-width: calc(100vw - 32px); border-radius: 14px; }
:deep(.agent-dialog .el-dialog__header) { padding-bottom: 16px; border-bottom: 1px solid #f0f0f0; }
:deep(.agent-dialog .el-dialog__footer) { padding-top: 16px; border-top: 1px solid #f0f0f0; }
.detail-form :deep(.el-input-number) { width: 100%; }

@media (max-width: 900px) {
  .status-summary { align-items: flex-start; flex-direction: column; }
  .status-metrics { width: 100%; justify-content: flex-start; }
  .status-metrics > div:first-child { padding-left: 0; border-left: 0; }
}

@media (max-width: 600px) {
  .status-metrics { align-items: stretch; flex-direction: column; gap: 12px; }
  .status-metrics > div { padding: 0; border-left: 0; }
  .content-card :deep(.el-card__body) { padding: 16px; }
}
</style>
