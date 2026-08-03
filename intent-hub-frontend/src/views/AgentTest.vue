<template>
  <el-card shadow="never" class="panel-card test-card">
    <div class="query-row">
      <el-input
        v-model="query"
        clearable
        placeholder="输入用户问题，按 Enter 直接测试"
        class="query-input"
        @keyup.enter="submit"
      />
      <el-button type="primary" :loading="loading" @click="submit">测试</el-button>
    </div>

    <div v-if="result" class="result-section">
      <div class="section-title"><span>RESULT</span><strong>路由结果</strong></div>
      <div v-if="!result.matched" class="fallback">
        <strong>未命中 Agent</strong>
        <p>{{ result.text }}</p>
      </div>
      <template v-else>
      <el-card
        v-for="(match, index) in result.agents"
        :key="match.agent.id"
        shadow="never"
        class="match-card"
      >
        <div class="result-info">
          <div class="match-main">
            <el-tag type="success" :effect="index === 0 ? 'dark' : 'plain'" size="small">
              {{ index === 0 ? '最佳匹配' : `匹配 ${index + 1}` }}
            </el-tag>
            <div>
              <strong>{{ match.agent.title }}</strong>
              <span>Agent ID: {{ match.agent.id }}</span>
            </div>
          </div>
          <el-tag type="success" effect="plain">已通过阈值</el-tag>
        </div>
        <div class="score-row">
          <span>相关分数</span>
          <el-progress
            :percentage="scorePercentage(match.score)"
            :stroke-width="12"
            :show-text="false"
            status="success"
          />
          <strong>{{ match.score.toFixed(4) }}</strong>
        </div>
        <div class="feedback-actions">
          <span>将本次问题加入该 Agent 的语料</span>
          <el-button
            circle
            title="加入正向语料"
            aria-label="加入正向语料"
            class="feedback-button"
            :class="{ 'is-active': feedbackStates[match.agent.id] === 'positive' }"
            :loading="feedbackPendingAgent === match.agent.id && feedbackStates[match.agent.id] === 'positive'"
            :disabled="feedbackPendingAgent !== undefined"
            @click="handleFeedback(match.agent.id, 'positive')"
          >
            <span class="thumb-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none"><path d="M7 21V9M14.7 4.2 11.9 9H19a2 2 0 0 1 1.94 2.5l-1.4 5A2 2 0 0 1 17.62 18H7V9.8a2 2 0 0 1 .58-1.4l4.83-4.95a1.15 1.15 0 0 1 1.93 1.11Z" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" /></svg>
            </span>
          </el-button>
          <el-button
            circle
            title="加入负向语料"
            aria-label="加入负向语料"
            class="feedback-button"
            :class="{ 'is-active': feedbackStates[match.agent.id] === 'negative' }"
            :loading="feedbackPendingAgent === match.agent.id && feedbackStates[match.agent.id] === 'negative'"
            :disabled="feedbackPendingAgent !== undefined"
            @click="handleFeedback(match.agent.id, 'negative')"
          >
            <span class="thumb-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none"><path d="M17 3v12M9.3 19.8 12.1 15H5a2 2 0 0 1-1.94-2.5l1.4-5A2 2 0 0 1 6.38 6H17v8.2a2 2 0 0 1-.58 1.4l-4.83 4.95a1.15 1.15 0 0 1-1.93-1.11Z" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" /></svg>
            </span>
          </el-button>
        </div>
      </el-card>
      </template>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { getAgents, route, updateAgent, type RouteData } from '../api';

type Feedback = 'positive' | 'negative';

const query = ref('');
const submittedQuery = ref('');
const loading = ref(false);
const result = ref<RouteData>();
const feedbackStates = ref<Record<number, Feedback | undefined>>({});
const feedbackPendingAgent = ref<number>();
const scorePercentage = (score: number) => Math.min(100, Math.max(0, Math.round(score * 100)));

const submit = async () => {
  const text = query.value.trim();
  if (!text || loading.value) return !text && ElMessage.warning('请输入用户问题');
  loading.value = true;
  try {
    const response = (await route(text)).data;
    result.value = response.data || undefined;
    submittedQuery.value = text;
    feedbackStates.value = {};
  }
  catch (error: any) { ElMessage.error(error.response?.data?.error?.detail || '查询失败'); }
  finally { loading.value = false; }
};

const handleFeedback = async (agentId: number, type: Feedback) => {
  const text = submittedQuery.value;
  if (!agentId || !text || feedbackPendingAgent.value !== undefined) return;

  const previous = feedbackStates.value[agentId];
  const next = previous === type ? undefined : type;
  feedbackStates.value = { ...feedbackStates.value, [agentId]: next };
  feedbackPendingAgent.value = agentId;
  try {
    const agent = (await getAgents()).data.find(item => item.id === agentId);
    if (!agent) throw new Error('Agent 不存在');
    const utterances = agent.utterances.filter(item => item !== text);
    const negativeSamples = agent.negative_samples.filter(item => item !== text);
    if (next === 'positive') utterances.push(text);
    if (next === 'negative') negativeSamples.push(text);
    await updateAgent(agentId, { utterances, negative_samples: negativeSamples });
    const action = next === 'positive' ? '加入正向语料' : next === 'negative' ? '加入负向语料' : '从语料中移除';
    ElMessage.success(`已${action}，向量数据需单独同步`);
  }
  catch (error: any) {
    feedbackStates.value = { ...feedbackStates.value, [agentId]: previous };
    ElMessage.error(error.response?.data?.error?.detail || error.message || '反馈失败');
  }
  finally { feedbackPendingAgent.value = undefined; }
};
</script>

<style scoped>
.test-card :deep(.el-card__body) { padding: 24px 28px; }
.query-row { display: flex; gap: 12px; }
.query-input { flex: 1; }
.query-row .el-button { min-width: 88px; }
.result-section { margin-top: 26px; padding-top: 24px; border-top: 1px solid #ebeef5; }
.section-title { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
.section-title span { color: #337ff2; font-size: 11px; font-weight: 700; letter-spacing: .14em; }
.section-title strong { font-size: 17px; }
.fallback strong { display: block; margin-bottom: 6px; }
.fallback p { margin: 0; font-size: 13px; line-height: 1.6; }
.match-card { border: 1px solid #d9ecff; border-left: 4px solid #67c23a; background: #f5fbf2; }
.match-card + .match-card { margin-top: 12px; }
.match-card :deep(.el-card__body) { padding: 20px 22px; }
.result-info, .match-main, .score-row, .feedback-actions { display: flex; align-items: center; }
.result-info { justify-content: space-between; gap: 20px; }
.match-main { gap: 14px; }
.match-main > div { display: flex; flex-direction: column; gap: 5px; }
.match-main strong { color: #303133; font-size: 17px; }
.match-main span { color: #909399; font-family: Consolas, monospace; font-size: 12px; }
.score-row { gap: 14px; margin-top: 20px; }
.score-row > span { color: #606266; font-size: 13px; white-space: nowrap; }
.score-row .el-progress { flex: 1; }
.score-row > strong { min-width: 58px; color: #303133; font-family: Consolas, monospace; font-size: 13px; text-align: right; }
.feedback-actions { justify-content: flex-end; gap: 10px; margin-top: 18px; padding-top: 16px; border-top: 1px solid #dfeee0; }
.feedback-actions > span { margin-right: 2px; color: #909399; font-size: 12px; }
.feedback-button { width: 36px; height: 36px; color: #606266; background: #fff; border-color: #dcdfe6; }
.feedback-button.is-active { color: #fff; background: #337ff2; border-color: #337ff2; }
.thumb-icon, .thumb-icon svg { width: 20px; height: 20px; }
.thumb-icon { display: inline-flex; align-items: center; justify-content: center; }

@media (max-width: 600px) {
  .test-card :deep(.el-card__body) { padding: 18px 16px; }
  .result-info { align-items: flex-start; flex-direction: column; }
  .feedback-actions > span { display: none; }
}
</style>
