<template>
  <el-card v-if="status" shadow="never" class="panel-card status-card">
    <div class="status-summary">
      <div class="phase-state">
        <span class="status-dot" :class="{ warning: sourceAttentionCount > 0 }" />
        <div>
          <span class="phase-label">上游数据差异</span>
          <strong>{{ sourceAttentionCount ? `${sourceAttentionCount} 个 Agent 需关注` : '本地内容与最近快照一致' }}</strong>
          <p>最近拉取：{{ formatTime(status.last_pull_at) }}</p>
        </div>
      </div>
      <div class="phase-divider" />
      <div class="phase-state">
        <span class="status-dot" :class="{ warning: !status.synced }" />
        <div>
          <span class="phase-label">向量数据同步</span>
          <strong>{{ status.synced ? '本地与向量数据一致' : `${status.pending_changes} 项待同步` }}</strong>
          <p>最近同步：{{ formatTime(status.last_vector_sync_at) }}</p>
        </div>
      </div>
      <div class="status-metrics">
        <div><span>本地 / 启用</span><strong>{{ status.agents_count }} / {{ status.active_agents_count }}</strong></div>
        <div><span>向量点数</span><strong>{{ status.points_count }} / {{ status.expected_points }}</strong></div>
        <div><span>Collection</span><strong class="collection-name">{{ status.collection }}</strong></div>
      </div>
    </div>
  </el-card>

  <el-card shadow="never" class="panel-card content-card">
    <div class="toolbar">
      <el-input v-model="query" clearable placeholder="搜索 Agent 名称或描述" />
      <div class="toolbar-actions">
        <el-button type="success" plain @click="openCreate">新建本地 Agent</el-button>
        <el-button :loading="pulling" @click="pull">从接口拉取 Agent</el-button>
        <el-button-group class="sync-actions">
          <el-button type="primary" :loading="syncing" @click="syncVectorsNow('incremental')">同步到向量数据库</el-button>
          <el-dropdown :disabled="syncing" @command="syncVectorsNow">
            <el-button type="primary" :disabled="syncing" aria-label="选择向量同步方式"><span class="dropdown-arrow">⌄</span></el-button>
            <template #dropdown><el-dropdown-menu><el-dropdown-item command="full">全量重建</el-dropdown-item></el-dropdown-menu></template>
          </el-dropdown>
        </el-button-group>
      </div>
    </div>

    <div class="diff-filters" aria-label="数据差异筛选">
      <button v-for="item in filterOptions" :key="item.value" type="button" :class="{ active: diffFilter === item.value }" @click="diffFilter = item.value">
        {{ item.label }} <span>{{ item.count }}</span>
      </button>
    </div>

    <el-table v-loading="loading" :data="filtered" row-key="id" header-cell-class-name="table-header-cell">
      <el-table-column prop="id" label="ID" width="80" align="center" />
      <el-table-column label="名称与描述" min-width="250"><template #default="{ row }"><div class="agent-info"><strong>{{ row.title }}</strong><span>{{ plainText(row.text) || '暂无描述' }}</span></div></template></el-table-column>
      <el-table-column label="来源" width="90" align="center"><template #default="{ row }"><el-tag :type="row.source_type === 'local' ? 'success' : 'info'" size="small">{{ row.source_type === 'local' ? '本地' : '上游' }}</el-tag></template></el-table-column>
      <el-table-column label="运行状态" width="100" align="center"><template #default="{ row }"><el-tag :type="row.lifecycle_status === 'active' ? 'success' : 'warning'" size="small">{{ row.lifecycle_status === 'active' ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column label="正 / 负语料" width="120" align="center"><template #default="{ row }">{{ row.utterances.length }} / {{ row.negative_samples.length }}</template></el-table-column>
      <el-table-column label="数据差异" min-width="170">
        <template #default="{ row }">
          <button class="comparison-button" type="button" @click="openDiff(row)">
            <el-tag :type="statusMeta(row.comparison.status).type" size="small" effect="light">{{ statusMeta(row.comparison.status).label }}</el-tag>
            <span v-if="row.comparison.diff_count">{{ row.comparison.diff_count }} 个字段</span>
            <span v-else-if="row.comparison.locked_equal_fields.length">{{ row.comparison.locked_equal_fields.length }} 个字段锁定</span>
            <span class="comparison-arrow">›</span>
          </button>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right" align="center"><template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link type="danger" @click="remove(row)">停用</el-button></template></el-table-column>
      <template #empty><el-empty description="当前筛选下暂无 Agent" /></template>
    </el-table>
  </el-card>

  <el-drawer v-model="diffVisible" :size="drawerSize" destroy-on-close class="diff-drawer">
    <template #header>
      <div v-if="diffAgent" class="drawer-heading">
        <span class="drawer-kicker">SOURCE COMPARISON · {{ diffAgent.id }}</span>
        <h2>{{ diffAgent.title }}</h2>
        <p>比较基准：最近一次成功拉取的上游快照 · {{ formatTime(diffDetail?.compared_at || status?.last_pull_at || null) }}</p>
      </div>
    </template>
    <div v-loading="diffLoading" class="diff-body">
      <el-alert v-if="diffDetail?.comparison.status === 'local_only'" title="这是仅本地 Agent，没有可对比的上游数据。" type="info" :closable="false" show-icon />
      <el-alert v-else-if="diffDetail?.comparison.status === 'upstream_missing'" title="该 Agent 已不在最近一次上游拉取结果中，下方展示的是最后一次上游快照。" type="warning" :closable="false" show-icon />
      <el-alert v-else-if="diffDetail?.comparison.status === 'snapshot_unknown'" title="旧数据尚未建立有效上游快照，请先执行一次拉取。" type="info" :closable="false" show-icon />

      <template v-if="diffDetail && Object.keys(diffDetail.fields).length">
        <section v-for="field in comparableFields" :key="field" class="field-diff" :class="{ changed: diffDetail.fields[field]?.changed }">
          <header>
            <div>
              <span class="field-name">{{ fieldLabels[field] }}</span>
              <el-tag v-if="diffDetail.fields[field]?.changed" size="small" type="warning">内容不同</el-tag>
              <el-tag v-else size="small" type="success">内容一致</el-tag>
              <el-tag v-if="diffDetail.fields[field]?.overridden" size="small" type="info" effect="plain">本地锁定</el-tag>
            </div>
            <el-button v-if="canRestore(field)" link type="primary" :loading="restoringField === field" @click="restoreField(field)">恢复此字段</el-button>
          </header>

          <div v-if="diffDetail.fields[field]?.kind === 'scalar'" class="scalar-grid">
            <div><span>本地当前值</span><p>{{ scalarField(field)?.local_value || '—' }}</p></div>
            <div><span>{{ diffDetail.comparison.status === 'upstream_missing' ? '最后一次上游快照' : '上游快照' }}</span><p>{{ scalarField(field)?.upstream_value || '—' }}</p></div>
          </div>

          <div v-else-if="diffDetail.fields[field]?.kind === 'corpus'" class="corpus-diff">
            <div class="corpus-stats">
              <span>本地 {{ corpusField(field)?.local_count }}</span>
              <span>上游 {{ corpusField(field)?.upstream_count }}</span>
              <span>双方共有 {{ corpusField(field)?.unchanged_count }}</span>
            </div>
            <div class="corpus-grid">
              <div class="corpus-column added"><h4>本地新增 · {{ corpusField(field)?.added.length }}</h4><ul v-if="corpusField(field)?.added.length"><li v-for="item in corpusField(field)?.added" :key="item">{{ item }}</li></ul><p v-else>无</p></div>
              <div class="corpus-column removed"><h4>仅上游存在 · {{ corpusField(field)?.removed.length }}</h4><ul v-if="corpusField(field)?.removed.length"><li v-for="item in corpusField(field)?.removed" :key="item">{{ item }}</li></ul><p v-else>无</p></div>
            </div>
          </div>
        </section>
      </template>
    </div>
  </el-drawer>

  <el-dialog v-model="visible" :title="creating ? '新建本地 Agent' : '编辑 Agent'" width="760px" destroy-on-close>
    <el-form label-position="top">
      <el-row :gutter="16">
        <el-col v-if="!creating" :span="8"><el-form-item label="ID"><el-input :model-value="form.id" disabled /></el-form-item></el-col>
        <el-col :span="creating ? 24 : 16"><el-form-item label="名称"><el-input v-model="form.title" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="描述"><el-input v-model="form.text" type="textarea" :rows="3" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item><template #label><div class="label-row"><span>正向语料</span><div><el-input-number v-model="positiveCount" :min="1" :max="20" size="small" /><el-button size="small" type="success" :loading="positiveGenerating" @click="recommend('positive')">AI 推荐</el-button></div></div></template><el-input v-model="positiveText" type="textarea" :rows="7" placeholder="每行一条语料" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="正向阈值"><el-input-number v-model="form.score_threshold" :min="0" :max="1" :step="0.01" :precision="2" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item><template #label><div class="label-row"><span>负向语料</span><div><el-input-number v-model="negativeCount" :min="1" :max="20" size="small" /><el-button size="small" type="warning" :loading="negativeGenerating" @click="recommend('negative')">AI 推荐</el-button></div></div></template><el-input v-model="negativeText" type="textarea" :rows="6" placeholder="每行一条语料" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="负向阈值"><el-input-number v-model="form.negative_threshold" :min="0" :max="1" :step="0.01" :precision="2" /></el-form-item></el-col>
        <el-col v-if="!creating" :span="12"><el-form-item label="状态"><el-switch v-model="active" active-text="启用" inactive-text="停用" /></el-form-item></el-col>
      </el-row>
    </el-form>
    <template #footer><el-button v-if="!creating && selected?.source_type === 'upstream' && selected.manual_overrides.length" @click="restore">全部恢复上游字段</el-button><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存到本地</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  createAgent, deleteAgent, getAgentDiff, getAgents, getSyncStatus, pullAgents, recommendCorpus,
  restoreAgentFields, syncVectors, updateAgent, type Agent, type AgentComparisonStatus,
  type AgentDiffDetail, type ComparableAgentField, type CorpusFieldDiff, type ScalarFieldDiff, type SyncStatus,
} from '../api';

type DiffFilter = 'all' | 'differences' | 'locked' | 'upstream_missing' | 'local_only';
const agents = ref<Agent[]>([]); const status = ref<SyncStatus>(); const query = ref(''); const diffFilter = ref<DiffFilter>('all');
const loading = ref(false); const pulling = ref(false); const syncing = ref(false); const saving = ref(false);
const visible = ref(false); const creating = ref(false); const selected = ref<Agent>();
const diffVisible = ref(false); const diffLoading = ref(false); const diffAgent = ref<Agent>(); const diffDetail = ref<AgentDiffDetail>(); const restoringField = ref<ComparableAgentField>();
const positiveText = ref(''); const negativeText = ref(''); const positiveCount = ref(5); const negativeCount = ref(5);
const positiveGenerating = ref(false); const negativeGenerating = ref(false); const active = ref(true); const viewportWidth = ref(window.innerWidth);
const form = reactive({ id: 0, title: '', text: '', score_threshold: 0.8, negative_threshold: 0.95 });
const comparableFields: ComparableAgentField[] = ['title', 'text', 'utterances', 'negative_samples'];
const fieldLabels: Record<ComparableAgentField, string> = { title: '名称', text: '描述', utterances: '正向语料', negative_samples: '负向语料' };
const statusMap: Record<AgentComparisonStatus, { label: string; type: 'success'|'warning'|'info'|'danger' }> = {
  same: { label: '一致', type: 'success' }, local_modified: { label: '本地有修改', type: 'warning' },
  locked_equal: { label: '值一致 · 本地锁定', type: 'info' }, upstream_missing: { label: '上游已移除', type: 'danger' },
  local_only: { label: '仅本地', type: 'info' }, snapshot_unknown: { label: '快照未知', type: 'info' },
};
const statusMeta = (value: AgentComparisonStatus) => statusMap[value] || statusMap.snapshot_unknown;
const lines = (value: string) => Array.from(new Set(value.split('\n').map(item => item.trim()).filter(Boolean)));
const isLocked = (agent: Agent) => agent.comparison.override_fields.some(field => comparableFields.includes(field as ComparableAgentField));
const matchesFilter = (agent: Agent) => diffFilter.value === 'all'
  || (diffFilter.value === 'differences' && agent.comparison.status === 'local_modified')
  || (diffFilter.value === 'locked' && isLocked(agent))
  || agent.comparison.status === diffFilter.value;
const filtered = computed(() => { const key = query.value.trim().toLowerCase(); return agents.value.filter(agent => matchesFilter(agent) && (!key || `${agent.title} ${agent.text}`.toLowerCase().includes(key))); });
const count = (predicate: (agent: Agent) => boolean) => agents.value.filter(predicate).length;
const filterOptions = computed(() => [
  { value: 'all' as const, label: '全部', count: agents.value.length },
  { value: 'differences' as const, label: '有差异', count: count(a => a.comparison.status === 'local_modified') },
  { value: 'locked' as const, label: '本地锁定', count: count(isLocked) },
  { value: 'upstream_missing' as const, label: '上游已移除', count: count(a => a.comparison.status === 'upstream_missing') },
  { value: 'local_only' as const, label: '仅本地', count: count(a => a.comparison.status === 'local_only') },
]);
const sourceAttentionCount = computed(() => count(a => ['local_modified', 'upstream_missing', 'snapshot_unknown'].includes(a.comparison.status)));
const drawerSize = computed(() => viewportWidth.value < 760 ? '100%' : '720px');
const plainText = (value: unknown) => new DOMParser().parseFromString(String(value || ''), 'text/html').body.textContent?.trim() || '';
const formatTime = (value: string | null) => value ? new Date(value).toLocaleString() : '尚未执行';
const errorDetail = (error: any, fallback: string) => error.response?.data?.error?.detail || fallback;
const load = async () => {
  loading.value = true;

  // Agent 列表与向量服务相互独立。Qdrant 或 Embedding 暂时不可用时，
  // 不能让同步状态请求的失败吞掉已经成功拉取的 Agent 数据。
  void getSyncStatus()
    .then(({ data }) => { status.value = data; })
    .catch((error: any) => { ElMessage.warning(errorDetail(error, '向量同步状态暂不可用')); });

  try {
    agents.value = (await getAgents()).data;
  } catch (error: any) {
    ElMessage.error(errorDetail(error, 'Agent 列表加载失败'));
  } finally {
    loading.value = false;
  }
};
const pull = async () => { pulling.value = true; try { const { data } = await pullAgents(); const message = `拉取完成：新增 ${data.created}，上游变化 ${data.upstream_changed ?? data.updated}，未变化 ${data.unchanged ?? 0}，上游移除 ${data.upstream_missing ?? data.disabled}`; data.warning ? ElMessage.warning(data.warning) : ElMessage.success(message); await load(); } catch (error: any) { ElMessage.error(errorDetail(error, '拉取失败')); } finally { pulling.value = false; } };
const syncVectorsNow = async (mode: 'incremental'|'full' = 'incremental') => { syncing.value = true; try { const { data } = await syncVectors(mode); ElMessage.success(`向量同步完成：更新 ${data.changed_agents}，删除 ${data.deleted_agents}`); await load(); } catch (error: any) { ElMessage.error(errorDetail(error, '向量同步失败')); } finally { syncing.value = false; } };
const openDiff = async (agent: Agent) => { diffAgent.value = agent; diffDetail.value = undefined; diffVisible.value = true; diffLoading.value = true; try { diffDetail.value = (await getAgentDiff(agent.id)).data; } catch (error: any) { ElMessage.error(errorDetail(error, '差异详情加载失败')); } finally { diffLoading.value = false; } };
const scalarField = (field: ComparableAgentField) => diffDetail.value?.fields[field] as ScalarFieldDiff | undefined;
const corpusField = (field: ComparableAgentField) => diffDetail.value?.fields[field] as CorpusFieldDiff | undefined;
const canRestore = (field: ComparableAgentField) => Boolean(diffAgent.value?.upstream_present && (diffDetail.value?.fields[field]?.changed || diffDetail.value?.fields[field]?.overridden));
const restoreField = async (field: ComparableAgentField) => { if (!diffAgent.value) return; restoringField.value = field; try { await restoreAgentFields(diffAgent.value.id, [field]); ElMessage.success(`${fieldLabels[field]}已恢复为最近上游值，向量数据需单独同步`); await load(); const refreshed = agents.value.find(agent => agent.id === diffAgent.value?.id); if (refreshed) await openDiff(refreshed); } catch (error: any) { ElMessage.error(errorDetail(error, '恢复失败')); } finally { restoringField.value = undefined; } };
const resetForm = (agent?: Agent) => { selected.value = agent; creating.value = !agent; form.id = agent?.id || 0; form.title = agent?.title || ''; form.text = agent?.text || ''; form.score_threshold = agent?.score_threshold ?? 0.8; form.negative_threshold = agent?.negative_threshold ?? 0.95; positiveText.value = agent?.utterances.join('\n') || ''; negativeText.value = agent?.negative_samples.join('\n') || ''; active.value = agent ? agent.lifecycle_status === 'active' : true; visible.value = true; };
const openCreate = () => resetForm(); const openEdit = (agent: Agent) => resetForm(agent);
const save = async () => { if (!form.title.trim()) return ElMessage.warning('请输入名称'); saving.value = true; const data = { title: form.title.trim(), text: form.text, utterances: lines(positiveText.value), negative_samples: lines(negativeText.value), score_threshold: form.score_threshold, negative_threshold: form.negative_threshold, lifecycle_status: active.value ? 'active' : 'inactive' } as any; try { creating.value ? await createAgent(data) : await updateAgent(form.id, data); ElMessage.success('已保存到本地，向量数据需单独同步'); visible.value = false; await load(); } catch (error: any) { ElMessage.error(errorDetail(error, '保存失败')); } finally { saving.value = false; } };
const recommend = async (polarity: 'positive'|'negative') => { if (creating.value) return ElMessage.warning('请先保存本地 Agent，再使用 AI 推荐'); const state = polarity === 'positive' ? positiveGenerating : negativeGenerating; state.value = true; try { const { data } = await recommendCorpus(form.id, { polarity, count: polarity === 'positive' ? positiveCount.value : negativeCount.value, title: form.title, text: form.text, utterances: lines(positiveText.value), negative_samples: lines(negativeText.value) }); const target = polarity === 'positive' ? positiveText : negativeText; target.value = [...lines(target.value), ...data.items].filter((v, i, a) => a.indexOf(v) === i).join('\n'); ElMessage.success(`已追加 ${data.items.length} 条建议`); } catch (error: any) { ElMessage.error(errorDetail(error, 'AI 推荐失败')); } finally { state.value = false; } };
const restore = async () => { if (!selected.value) return; try { await restoreAgentFields(selected.value.id, selected.value.manual_overrides); ElMessage.success('已恢复最近一次上游值'); visible.value = false; await load(); } catch (error: any) { ElMessage.error(errorDetail(error, '恢复失败')); } };
const remove = async (agent: Agent) => { try { await ElMessageBox.confirm(`停用 ${agent.title}？下次向量同步会清理其向量。`, '确认停用', { type: 'warning' }); await deleteAgent(agent.id); await load(); } catch (_) {} };
const updateViewport = () => { viewportWidth.value = window.innerWidth; };
onMounted(() => { window.addEventListener('resize', updateViewport); load(); });
onUnmounted(() => window.removeEventListener('resize', updateViewport));
</script>

<style scoped>
.toolbar-actions,.label-row,.label-row>div{display:flex;align-items:center;gap:10px}.sync-actions{display:inline-flex}.sync-actions :deep(> .el-button){border-top-right-radius:0;border-bottom-right-radius:0}.sync-actions :deep(.el-dropdown){display:inline-flex}.sync-actions :deep(.el-dropdown .el-button){margin-left:-1px;padding-right:10px;padding-left:10px;border-top-left-radius:0;border-bottom-left-radius:0}.dropdown-arrow{font-size:16px;line-height:1}.label-row{width:100%;justify-content:space-between}.status-card{margin-bottom:18px}.status-summary,.phase-state,.status-metrics{display:flex;align-items:center}.status-summary{gap:26px}.phase-state{gap:13px;min-width:220px}.phase-state>div{display:flex;flex-direction:column;gap:3px}.phase-state strong{font-size:14px}.phase-state p{margin:0;color:#909399;font-size:11px}.phase-label{color:#7a828e;font-size:11px;letter-spacing:.08em;text-transform:uppercase}.phase-divider{width:1px;height:48px;background:#ebeef5}.status-dot{width:9px;height:9px;flex:0 0 auto;border-radius:50%;background:#67c23a;box-shadow:0 0 0 5px #eaf7e5}.status-dot.warning{background:#e6a23c;box-shadow:0 0 0 5px #fdf3e4}.status-metrics{margin-left:auto}.status-metrics>div{min-width:105px;padding:2px 18px;border-left:1px solid #ebeef5}.status-metrics span,.status-metrics strong{display:block}.status-metrics span{margin-bottom:6px;color:#909399;font-size:11px}.collection-name{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:"JetBrains Mono","Cascadia Code",monospace;font-size:12px}.diff-filters{display:flex;gap:7px;margin:-4px 0 18px;padding-bottom:14px;border-bottom:1px solid #eef0f3;overflow-x:auto}.diff-filters button{padding:6px 10px;border:1px solid transparent;border-radius:7px;color:#606a78;background:transparent;cursor:pointer;white-space:nowrap}.diff-filters button span{margin-left:4px;color:#a1a8b2;font-family:"Cascadia Code",monospace;font-size:11px}.diff-filters button:hover{background:#f5f7fa}.diff-filters button.active{border-color:#c9dcfb;color:#246bd4;background:#edf5ff}.agent-info{display:flex;flex-direction:column;gap:5px;padding:7px 0}.agent-info span{max-width:420px;overflow:hidden;color:#909399;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.comparison-button{display:flex;align-items:center;gap:7px;width:100%;padding:4px 0;border:0;background:transparent;cursor:pointer;text-align:left}.comparison-button>span:not(.el-tag):not(.comparison-arrow){color:#909399;font-size:11px}.comparison-arrow{margin-left:auto;color:#aab2bd;font-size:20px;line-height:1}.drawer-heading{padding-right:30px}.drawer-kicker{color:#337ff2;font-family:"Cascadia Code",monospace;font-size:10px;letter-spacing:.12em}.drawer-heading h2{margin:7px 0 5px;color:#20242b;font-size:21px}.drawer-heading p{margin:0;color:#8a929e;font-size:12px}.diff-body{min-height:240px}.diff-body>.el-alert{margin-bottom:16px}.field-diff{margin-bottom:14px;border:1px solid #e8ebef;border-left:3px solid #cfd5dd;border-radius:9px;background:#fff;overflow:hidden}.field-diff.changed{border-left-color:#e6a23c}.field-diff>header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 15px;border-bottom:1px solid #edf0f3;background:#fafbfc}.field-diff>header>div{display:flex;align-items:center;gap:7px}.field-name{margin-right:3px;color:#252a32;font-weight:700}.scalar-grid,.corpus-grid{display:grid;grid-template-columns:1fr 1fr}.scalar-grid>div{min-height:90px;padding:14px 16px}.scalar-grid>div+div{border-left:1px solid #edf0f3}.scalar-grid span{color:#8a929e;font-size:11px}.scalar-grid p{margin:8px 0 0;color:#343b45;line-height:1.65;white-space:pre-wrap;word-break:break-word}.corpus-stats{display:flex;gap:18px;padding:10px 15px;color:#747e8b;background:#f8f9fb;font-size:11px}.corpus-column{padding:14px 15px}.corpus-column+.corpus-column{border-left:1px solid #edf0f3}.corpus-column h4{margin:0 0 10px;font-size:12px}.corpus-column.added h4{color:#2d8a5c}.corpus-column.removed h4{color:#c36d3d}.corpus-column ul{max-height:190px;margin:0;padding-left:18px;overflow:auto}.corpus-column li{margin:0 0 7px;color:#48515e;font-size:12px;line-height:1.5;word-break:break-word}.corpus-column p{margin:0;color:#b0b6bf;font-size:12px}.detail-form :deep(.el-input-number){width:100%}:deep(.diff-drawer .el-drawer__header){margin-bottom:0;padding-bottom:18px;border-bottom:1px solid #e9edf2}:deep(.diff-drawer .el-drawer__body){background:#f5f7f9}:deep(.table-header-cell){height:46px;color:#606874;background:#f8f9fb!important;font-weight:700}
@media(max-width:1180px){.status-summary{align-items:flex-start;flex-wrap:wrap}.status-metrics{width:100%;margin-left:0}.status-metrics>div:first-child{padding-left:0;border-left:0}}
@media(max-width:760px){.toolbar{align-items:stretch;flex-direction:column}.toolbar-actions{flex-wrap:wrap}.phase-divider{display:none}.phase-state{width:100%}.status-metrics{align-items:flex-start;flex-direction:column}.status-metrics>div{padding:4px 0;border:0}.scalar-grid,.corpus-grid{grid-template-columns:1fr}.scalar-grid>div+div,.corpus-column+.corpus-column{border-top:1px solid #edf0f3;border-left:0}}
</style>
