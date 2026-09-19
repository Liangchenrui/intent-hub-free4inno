<template>
  <el-container class="layout-container">
    <el-header class="header-wrapper">
      <div class="header-content">
        <div class="brand"><img src="@/assets/logo.png" alt="Intent Hub" class="logo-img" /></div>
        <div class="user-info">
          <ServiceHealthIndicators />
          <LanguageSwitcher />
          <el-button type="danger" @click="logout">{{ t('common.logout') }}</el-button>
        </div>
      </div>
    </el-header>
    <el-main class="main-wrapper">
      <div class="page-header">
        <el-tabs model-value="logs" class="nav-tabs" @tab-change="navigate">
          <el-tab-pane v-for="item in navigation" :key="item.name" :name="item.name" :label="t(`nav.${item.name}`)" />
        </el-tabs>
      </div>
      <el-card shadow="never" class="content-card">
        <div class="retention-note"><el-tag type="info" effect="plain">{{ tx('最近 30 天', 'Last 30 days') }}</el-tag></div>
        <el-tabs v-model="kind" @tab-change="changeKind">
          <el-tab-pane name="runtime" :label="tx('运行日志', 'Runtime logs')" />
          <el-tab-pane name="routing" :label="tx('路由记录', 'Routing records')" />
        </el-tabs>
        <el-radio-group v-if="kind === 'runtime'" v-model="category" class="category-filter" @change="search">
          <el-radio-button value="">{{ tx('全部类型', 'All categories') }}</el-radio-button>
          <el-radio-button v-for="value in categories" :key="value" :value="value">{{ categoryLabel(value) }}</el-radio-button>
        </el-radio-group>
        <el-form class="filters" label-position="top" @submit.prevent="search">
          <el-form-item :label="tx('时间范围', 'Time range')" class="time-filter">
            <el-date-picker v-model="range" type="datetimerange" :start-placeholder="tx('开始时间', 'Start time')" :end-placeholder="tx('结束时间', 'End time')" />
          </el-form-item>
          <el-form-item label="Request ID"><el-input v-model="requestId" clearable :placeholder="tx('精确匹配', 'Exact match')" /></el-form-item>
          <el-form-item :label="kind === 'runtime' ? tx('消息关键词', 'Message keyword') : tx('输入关键词', 'Input keyword')">
            <el-input v-model="keyword" clearable :placeholder="tx('包含文本', 'Contains text')" />
          </el-form-item>
          <el-form-item v-if="kind === 'runtime'" :label="tx('级别', 'Level')" class="level-filter">
            <el-select v-model="level" clearable :placeholder="tx('全部', 'All')"><el-option v-for="value in levels" :key="value" :label="value" :value="value" /></el-select>
          </el-form-item>
          <div class="filter-actions"><el-button type="primary" native-type="submit" :loading="loading">{{ tx('查询', 'Search') }}</el-button><el-button @click="reset">{{ tx('重置', 'Reset') }}</el-button></div>
        </el-form>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="error" />
        <el-table v-loading="loading" :data="items" :empty-text="error ? tx('查询失败，请重试', 'Query failed. Please retry.') : tx('没有符合条件的记录', 'No matching records')" stripe>
          <el-table-column :label="tx('时间', 'Time')" width="185"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
          <el-table-column :label="tx('类型', 'Category')" width="100"><template #default="{ row }"><el-tag effect="plain">{{ categoryLabel(row.category) }}</el-tag></template></el-table-column>
          <el-table-column :label="tx('状态', 'Status')" width="110"><template #default="{ row }"><el-tag :type="row.level === 'ERROR' || row.level === 'CRITICAL' || row.status === 'failed' ? 'danger' : row.level === 'WARNING' ? 'warning' : 'info'">{{ row.level || (row.status === 'failed' ? tx('失败', 'Failed') : tx('成功', 'Succeeded')) }}</el-tag></template></el-table-column>
          <el-table-column :label="kind === 'runtime' ? tx('消息', 'Message') : tx('输入摘要', 'Input preview')" min-width="250"><template #default="{ row }"><span class="preview">{{ preview(row.message ?? row.input_text ?? '') }}</span></template></el-table-column>
          <el-table-column v-if="kind === 'routing'" :label="tx('路由结果', 'Route result')" min-width="150"><template #default="{ row }">{{ resultSummary(row) }}</template></el-table-column>
          <el-table-column v-if="kind === 'routing'" :label="tx('兜底状态', 'Fallback')" min-width="130"><template #default="{ row }">{{ fallbackSummary(row) }}</template></el-table-column>
          <el-table-column v-else :label="tx('来源', 'Source')" min-width="140" show-overflow-tooltip><template #default="{ row }">{{ row.module || row.path || '—' }}</template></el-table-column>
          <el-table-column :label="tx('耗时', 'Duration')" width="100"><template #default="{ row }">{{ row.elapsed_ms == null ? '—' : `${row.elapsed_ms} ms` }}</template></el-table-column>
          <el-table-column label="Request ID" width="160"><template #default="{ row }"><code>{{ row.request_id ? row.request_id.slice(0, 12) + '…' : tx('后台任务', 'Background') }}</code></template></el-table-column>
          <el-table-column width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="selected = row; drawer = true">{{ tx('详情', 'Details') }}</el-button></template></el-table-column>
        </el-table>
        <div class="pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" @current-change="load" @size-change="search" /></div>
      </el-card>
    </el-main>
    <el-drawer v-model="drawer" :title="tx('记录详情', 'Record details')" size="min(760px, 100vw)">
      <template v-if="selected">
        <dl class="metadata"><dt>Request ID</dt><dd>{{ selected.request_id || tx('后台任务', 'Background') }}</dd><dt>{{ tx('时间', 'Time') }}</dt><dd>{{ formatTime(selected.created_at) }}</dd><dt>{{ tx('来源', 'Source') }}</dt><dd>{{ selected.module || selected.path || '—' }}</dd></dl>
        <p>{{ tx('事件类型：', 'Category: ') }}{{ categoryLabel(selected.category) }}<span v-if="selected.category_inferred">{{ tx('（历史记录，按已有信息推断）', ' (inferred from legacy fields)') }}</span></p>
        <dl v-if="selected.task_id" class="metadata"><dt>Task ID</dt><dd>{{ selected.task_id }}</dd><dt>{{ tx('任务状态', 'Task status') }}</dt><dd>{{ selected.task_status }} · {{ tx('尝试次数', 'Attempt') }} {{ selected.attempt }}</dd><dt>{{ tx('排队耗时', 'Queue wait') }}</dt><dd>{{ duration(selected.queue_wait_ms) }}</dd><dt>{{ tx('锁等待', 'Lock wait') }}</dt><dd>{{ duration(selected.lock_wait_ms) }}</dd></dl>
        <el-button v-if="selected.request_id" @click="showRelated">{{ kind === 'routing' ? tx('查看关联运行日志', 'Related runtime logs') : tx('查看关联路由记录', 'Related routing records') }}</el-button>
        <template v-if="kind === 'routing'">
          <h3>{{ tx('输入全文', 'Full input') }}</h3><pre>{{ selected.input_text }}</pre>
          <h3>{{ tx('阶段耗时', 'Stage timings') }}</h3>
          <p class="timing-note">{{ tx('服务端总耗时：', 'Server duration: ') }}{{ duration(selected.elapsed_ms) }}{{ tx('；不含最终日志落库和网络传输。正负例可能并行；其他耗时按区间并集计算，各阶段占比不可直接相加。', '; excludes final log persistence and transport. Search stages can overlap; other work uses interval union. Stage shares are not additive.') }}</p>
          <el-empty v-if="!selected.timings?.length" :description="tx('此记录未采集阶段耗时', 'Stage timings were not captured')" :image-size="60" />
          <template v-else>
            <el-table :data="selected.timings" size="small">
              <el-table-column :label="tx('阶段', 'Stage')" min-width="150"><template #default="{ row }">{{ stageLabel(row.stage) }}</template></el-table-column>
              <el-table-column :label="tx('开始偏移', 'Start offset')" width="110"><template #default="{ row }">{{ duration(row.offset_ms) }}</template></el-table-column>
              <el-table-column :label="tx('耗时', 'Duration')" width="110"><template #default="{ row }">{{ duration(row.elapsed_ms) }}</template></el-table-column>
              <el-table-column :label="tx('占总耗时', 'Share')" width="100"><template #default="{ row }">{{ selected.elapsed_ms ? (row.elapsed_ms / selected.elapsed_ms * 100).toFixed(1) + '%' : '—' }}</template></el-table-column>
              <el-table-column :label="tx('状态', 'Status')" min-width="100"><template #default="{ row }"><span :class="{ 'timing-failed': row.status === 'failed' }">{{ row.status === 'failed' ? row.error_type || tx('失败', 'Failed') : tx('完成', 'Completed') }}</span></template></el-table-column>
            </el-table>
            <p class="timing-note">{{ tx('其他处理／未单独计时：', 'Other / uninstrumented work: ') }}{{ duration(otherDuration(selected)) }}</p>
          </template>
          <h3>{{ tx('路由过程', 'Routing trace') }}</h3>
          <el-empty v-if="!selected.events?.length" :description="tx('此记录未采集过程信息', 'No trace captured for this record')" :image-size="60" />
          <ol v-else class="events"><li v-for="(event, index) in selected.events" :key="index"><strong>{{ stageLabel(event.stage) }}</strong><pre>{{ JSON.stringify(event, null, 2) }}</pre></li></ol>
          <h3>{{ tx('最终响应', 'Final response') }}</h3><pre>{{ JSON.stringify(selected.result, null, 2) }}</pre>
        </template>
        <template v-else><h3>{{ tx('完整消息', 'Full message') }}</h3><pre>{{ selected.message }}</pre><template v-if="selected.exception"><h3>{{ tx('异常堆栈', 'Exception stack') }}</h3><pre class="exception">{{ selected.exception }}</pre></template></template>
      </template>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';
import ServiceHealthIndicators from '../components/ServiceHealthIndicators.vue';
import { clearSession, getLogs, type LogKind, type LogRecord, type LogCategory } from '../api';

const router = useRouter();
const { t, locale } = useI18n();
const tx = (zh: string, en: string) => locale.value.startsWith('zh') ? zh : en;
const navigation = [{ name: 'list', path: '/' }, { name: 'test', path: '/test' }, { name: 'diagnostics', path: '/diagnostics' }, { name: 'settings', path: '/settings' }, { name: 'logs', path: '/logs' }];
const navigate = (name: string | number) => { const item = navigation.find(item => item.name === name); if (item) router.push(item.path); };
const logout = () => { clearSession(); router.push('/login'); };
const kind = ref<LogKind>('runtime');
const category = ref<LogCategory | ''>('');
const categories: LogCategory[] = ['routing', 'sync', 'diagnostics', 'management', 'system'];
const categoryLabel = (value?: string) => ({ routing: tx('路由', 'Routing'), sync: tx('同步', 'Sync'), diagnostics: tx('诊断', 'Diagnostics'), management: tx('管理', 'Management'), system: tx('系统', 'System') }[value || 'system'] || value);
const duration = (value?: number) => value == null ? '—' : `${value.toFixed(2)} ms`;
const otherDuration = (row: LogRecord) => {
  if (row.elapsed_ms == null) return undefined;
  const intervals = (row.timings || []).map((item): [number, number] => [item.offset_ms, item.offset_ms + item.elapsed_ms]).sort((a, b) => a[0] - b[0]);
  let covered = 0, end = 0;
  for (const [start, stop] of intervals) {
    const clipped = Math.min(stop, row.elapsed_ms);
    covered += Math.max(0, clipped - Math.max(start, end));
    end = Math.max(end, clipped);
  }
  return Math.max(0, row.elapsed_ms - covered);
};
const requestId = ref(''); const keyword = ref(''); const level = ref('');
const range = ref<[Date, Date] | null>(null);
const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
const items = ref<LogRecord[]>([]); const total = ref(0); const page = ref(1); const pageSize = ref(20);
const loading = ref(false); const error = ref(''); const drawer = ref(false); const selected = ref<LogRecord | null>(null);
let generation = 0;
const formatTime = (value: number) => new Date(value * 1000).toLocaleString(locale.value === 'zh' ? 'zh-CN' : locale.value, { hour12: false });
const preview = (value: string) => value.length > 180 ? value.slice(0, 180) + '…' : value;
function resultSummary(row: LogRecord) {
  if (row.status === 'failed') return tx('请求失败', 'Request failed');
  if (Array.isArray(row.result)) return row.result.map(item => item.name || item.route_key || item.id).join(', ') || '—';
  return [...(row.events || [])].reverse().find(event => event.stage === 'fallback_result')?.status?.toString() || tx('查看详情', 'See details');
}
function stageLabel(stage: string) {
  const names: Record<string, string> = { preparing: '准备路由', encoding: '输入向量化', negative_search: '负例检索', negative_candidate: '负例判断', positive_search: '正例检索', candidate: '候选判断', vector_result: '向量匹配结果', fallback_entered: '进入兜底', fallback_candidate: '兜底候选', llm_call_started: '开始调用 LLM', llm_decision: 'LLM 判断', fallback_error: '兜底异常', fallback_result: '兜底结果' };
  Object.assign(names, { remote_call: '远程调用耗时', embedding_cache: '向量缓存', llm_client: 'LLM 客户端复用', negative_filter: '负例排除判断', candidate_filter: '候选过滤与排序', fallback_prepare: '兜底路由快照', description_search: '职责描述检索', fallback_candidates: '兜底候选校验', llm_prompt: '构建提示词', llm_client_init: 'LLM 客户端初始化', llm_call: 'LLM 请求与响应', llm_parse: '解析模型响应', route_revalidate: '最终路由复核' });
  return locale.value.startsWith('zh') ? names[stage] || stage : stage.replace(/_/g, ' ');
}
function fallbackSummary(row: LogRecord) {
  const event = [...(row.events || [])].reverse().find(event => event.stage === 'fallback_result');
  if (event) return String(event.status);
  if (row.events?.some(event => event.stage === 'fallback_entered')) return tx('未完成', 'Incomplete');
  return row.events?.some(event => event.stage === 'vector_result') ? tx('未触发', 'Not triggered') : tx('未记录', 'Not recorded');
}
async function load() {
  const current = ++generation;
  loading.value = true; error.value = ''; items.value = [];
  try {
    const response = await getLogs(kind.value, { page: page.value, page_size: pageSize.value,
      request_id: requestId.value.trim() || undefined, keyword: keyword.value || undefined,
      level: kind.value === 'runtime' ? level.value || undefined : undefined,
      category: kind.value === 'runtime' ? category.value || undefined : undefined,
      start: range.value?.[0] ? range.value[0].getTime() / 1000 : undefined,
      end: range.value?.[1] ? range.value[1].getTime() / 1000 : undefined });
    if (current !== generation) return;
    items.value = response.data.items; total.value = response.data.total;
  } catch {
    if (current === generation) { total.value = 0; error.value = tx('无法加载日志，请检查服务后重试。', 'Unable to load logs. Check the service and retry.'); }
  } finally { if (current === generation) loading.value = false; }
}
function search() { page.value = 1; void load(); }
function reset() { requestId.value = ''; keyword.value = ''; level.value = ''; category.value = ''; range.value = null; search(); }
function changeKind() { drawer.value = false; keyword.value = ''; level.value = ''; category.value = ''; search(); }
function showRelated() {
  requestId.value = selected.value?.request_id || '';
  range.value = null; keyword.value = ''; level.value = ''; category.value = ''; drawer.value = false;
  kind.value = kind.value === 'runtime' ? 'routing' : 'runtime';
  search();
}
onMounted(load);
onBeforeUnmount(() => { generation++; });
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

.user-info { display: flex; align-items: center; gap: 16px; }
.retention-note { float: right; margin-left: 16px; }
.filters { display:flex; flex-wrap:wrap; gap:12px 16px; align-items:flex-end; margin:16px 0; }
.filters .el-form-item { margin:0; flex:1 1 180px; } .filters .time-filter { flex:2 1 360px; } .time-filter :deep(.el-date-editor) { width:100%; }
.filters .level-filter { flex:0 1 140px; } .filter-actions { display:flex; padding-bottom:1px; }
.error { margin:16px 0; } .preview { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; overflow-wrap:anywhere; }
.category-filter { display:flex; flex-wrap:wrap; margin:8px 0 16px; } .timing-note { color:#697586; font-size:13px; line-height:1.6; } .timing-failed { color:#c45656; }
.pagination { display:flex; justify-content:flex-end; overflow:auto; margin-top:24px; }
code, pre, .metadata dd { font-family:Consolas, monospace; } pre { white-space:pre-wrap; overflow-wrap:anywhere; background:#f5f7fa; border:1px solid #e4e7ed; padding:14px; line-height:1.65; border-radius:5px; font-size:13px; }
.metadata { display:grid; grid-template-columns:100px 1fr; gap:12px; margin:0 0 20px; } .metadata dt { color:#697586; } .metadata dd { margin:0; overflow-wrap:anywhere; }
h3 { font-size:15px; margin-top:28px; } .events { padding-left:25px; } .events li { margin-bottom:18px; padding-left:5px; } .events strong { font-size:14px; } .exception { border-left:3px solid #f56c6c; }
@media(max-width:680px) { .filters .time-filter { flex-basis:100%; min-width:0; } }
</style>
