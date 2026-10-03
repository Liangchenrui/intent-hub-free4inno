<template>
  <section v-loading="loading" class="upstreams">
    <div class="upstream-heading">
      <div>
        <strong>上游数据源</strong>
        <p class="hint">配置应用数据来源，保存后可拉取。</p>
      </div>
      <el-button @click="addSource">新增上游</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <el-empty v-if="!loading && !sources.length" description="尚未配置上游，点击新增上游开始" :image-size="60" />
    <div v-for="(source, index) in sources" :key="source.id" class="upstream-card">
      <div class="upstream-heading">
        <strong>{{ source.name || '新上游' }}</strong>
        <div class="actions">
          <el-tag v-if="source.name_locked" type="info" size="small">名称已锁定</el-tag>
          <el-button type="primary" plain :loading="isRunning(source.id) || submitting === source.id"
            :disabled="dirty(source) || saving" @click="pull(source)">拉取数据</el-button>
          <el-button type="danger" text :disabled="isRunning(source.id) || saving" @click="sources.splice(index, 1)">移除配置</el-button>
        </div>
      </div>
      <div class="source-fields">
        <el-form-item label="上游名称">
          <el-input v-model="source.name" :disabled="source.name_locked || isRunning(source.id)" placeholder="例如 bupt" />
          <div class="hint">用于路由标识；不含点号或空白，拉取后锁定。</div>
        </el-form-item>
        <el-form-item label="接口 URL">
          <el-input v-model="source.url" placeholder="https://example.com/ac/api" />
        </el-form-item>
        <el-form-item label="标签 ID">
          <el-input v-model="source.label_ids" placeholder="87,88,89" />
        </el-form-item>
      </div>
      <p v-if="dirty(source)" class="hint">保存上游配置后可拉取。</p>
      <div class="pull-result" aria-live="polite">
        <span>{{ taskLabel(source.id) }}</span>
        <span v-if="source.last_result?.last_pulled_at">最近拉取：{{ new Date(source.last_result.last_pulled_at).toLocaleString() }}</span>
        <span v-if="source.last_result">新增 {{ source.last_result.created ?? 0 }} · 更新 {{ source.last_result.updated ?? 0 }} · 未变 {{ source.last_result.unchanged ?? 0 }} · 缺失 {{ source.last_result.upstream_missing ?? 0 }} · 失败 {{ source.last_result.failed ?? 0 }}</span>
      </div>
      <el-alert v-if="latest(source.id)?.error || source.last_result?.warning"
        :title="latest(source.id)?.error || source.last_result?.warning" type="warning" :closable="false" />
    </div>
    <div class="upstream-heading">
      <span class="hint">移除配置会保留已拉取的数据。上游配置单独保存。</span>
      <el-button type="primary" :loading="saving" :disabled="loading" @click="save">保存上游配置</el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { ElMessage } from 'element-plus';
import { getSettings, updateSettings, getSyncTasks, pullUpstreamAgents, type UpstreamConfig, type SyncTask } from '../api';

const sources = ref<UpstreamConfig[]>([]);
const saved = ref<Record<string, string>>({});
const tasks = ref<SyncTask[]>([]);
const loading = ref(true);
const saving = ref(false);
const submitting = ref('');
const error = ref('');
let timer: ReturnType<typeof setTimeout> | undefined;
let disposed = false;
let initialized = false;
const definition = (s: UpstreamConfig) => ({ id: s.id, name: s.name, url: s.url, label_ids: s.label_ids });
const dirty = (s: UpstreamConfig) => saved.value[s.id] !== JSON.stringify(definition(s));
const latest = (id: string) => [...tasks.value].reverse().find(t => t.kind === 'upstream_pull' && t.source_config?.SOURCE_INSTANCE === id);
const isRunning = (id: string) => tasks.value.some(t => t.kind === 'upstream_pull' && t.source_config?.SOURCE_INSTANCE === id && ['queued', 'running'].includes(t.status));
const taskLabel = (id: string) => {
  const task = latest(id);
  if (!task) return '尚无拉取任务';
  const labels: Record<string, string> = { queued: '等待拉取', running: '正在拉取', error: '拉取失败', superseded: '配置已变更，请重新拉取', succeeded: '数据已保存' };
  const index = tasks.value.find(t => t.id === task.result?.sync_task_id);
  return `${labels[task.status] || task.status}${index ? ` · 索引${({ queued: '等待同步', running: '同步中', succeeded: '已同步', error: '同步失败', superseded: '任务已替换' } as Record<string, string>)[index.status] || index.status}` : ''}`;
};
const apply = (items: UpstreamConfig[]) => {
  sources.value = items;
  saved.value = Object.fromEntries(items.map(s => [s.id, JSON.stringify(definition(s))]));
};
const addSource = () => sources.value.push({ id: crypto.randomUUID(), name: '', url: '', label_ids: '87,88,89' });
const save = async () => {
  saving.value = true;
  error.value = '';
  try {
    const response = await updateSettings({ UPSTREAMS: sources.value.map(definition) });
    apply(response.data.settings.UPSTREAMS || []);
    ElMessage.success('上游配置已保存');
  } catch (e: any) { error.value = e?.response?.data?.detail || '保存上游配置失败'; }
  finally { saving.value = false; }
};
const pull = async (source: UpstreamConfig) => {
  submitting.value = source.id;
  error.value = '';
  try {
    const { data } = await pullUpstreamAgents(source.id);
    tasks.value = [...tasks.value.filter(t => t.id !== data.id), data];
    ElMessage.success(`${source.name} 已加入拉取队列`);
  } catch (e: any) { error.value = e?.response?.data?.detail || '提交拉取失败'; }
  finally { submitting.value = ''; }
};
const refresh = async () => {
  try {
    const [config, taskResponse] = await Promise.all([getSettings(), getSyncTasks()]);
    if (disposed) return;
    tasks.value = taskResponse.data;
    if (!initialized) { apply(config.data.UPSTREAMS || []); initialized = true; }
    else for (const source of sources.value) {
      const remote = config.data.UPSTREAMS?.find(s => s.id === source.id);
      if (remote) {
        source.name_locked = remote.name_locked;
        source.last_result = remote.last_result;
        if (remote.name_locked) source.name = remote.name;
      }
    }
  } catch (e: any) { error.value = e?.response?.data?.detail || '获取上游状态失败，将自动重试'; }
  finally {
    loading.value = false;
    if (!disposed) timer = setTimeout(refresh, 2500);
  }
};
onMounted(refresh);
onBeforeUnmount(() => { disposed = true; clearTimeout(timer); });
</script>

<style scoped>
.upstreams { margin: 0; }
.upstream-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.hint { color: #737985; font-size: 12px; margin: 8px 0; }
.upstream-card { border: 1px solid #dcdfe6; border-radius: 8px; padding: 16px; margin: 16px 0; }
.actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.source-fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr) minmax(0, 1fr); gap: 16px; margin-top: 16px; }
.pull-result { display: flex; gap: 12px; flex-wrap: wrap; font-size: 13px; color: #606266; margin-bottom: 8px; }
@media (max-width: 760px) { .source-fields { grid-template-columns: 1fr; gap: 0; } }
</style>
