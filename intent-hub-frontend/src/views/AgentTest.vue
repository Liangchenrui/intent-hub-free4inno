<template>
  <div class="page-intro">
    <div>
      <h1>路由测试</h1>
      <p>输入真实用户问题，验证当前向量索引的 Agent 路由结果</p>
    </div>
  </div>

  <el-card shadow="never" class="panel-card test-card">
    <div class="test-heading">
      <div>
        <span class="step-label">QUERY</span>
        <h2>输入测试问题</h2>
      </div>
      <span class="threshold-note">仅返回超过 Agent 阈值的结果</span>
    </div>
    <el-input
      v-model="query"
      type="textarea"
      :rows="5"
      resize="none"
      placeholder="例如：帮我查询明天北京的天气"
      class="query-input"
      @keydown.ctrl.enter="submit"
    />
    <div class="submit-row">
      <span>Ctrl + Enter 快速提交</span>
      <el-button type="primary" size="large" :loading="loading" @click="submit">查询路由</el-button>
    </div>

    <div v-if="result" class="result-section">
      <div class="section-title"><span>RESULT</span><strong>路由结果</strong></div>
      <div v-if="!result.matched" class="fallback">
        <strong>未命中 Agent</strong>
        <p>{{ result.text }}</p>
      </div>
      <el-card v-else shadow="never" class="match-card">
        <div class="match-main">
          <el-tag type="success" effect="dark" size="small">最佳匹配</el-tag>
          <div>
            <strong>{{ result.agent?.title }}</strong>
            <span>Agent ID: {{ result.agent?.id }}</span>
          </div>
        </div>
        <el-tag type="success" effect="plain">已通过阈值</el-tag>
      </el-card>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { route, type RouteData } from '../api';

const query = ref('');
const loading = ref(false);
const result = ref<RouteData>();
const submit = async () => {
  if (!query.value.trim()) return ElMessage.warning('请输入用户问题');
  loading.value = true;
  try {
    const response = (await route(query.value.trim())).data;
    result.value = response.data || undefined;
  }
  catch (error: any) { ElMessage.error(error.response?.data?.error?.detail || '查询失败'); }
  finally { loading.value = false; }
};
</script>

<style scoped>
.test-card { padding: 8px; }
.test-card :deep(.el-card__body) { padding: 28px 32px; }
.test-heading, .submit-row, .match-card :deep(.el-card__body), .match-main { display: flex; align-items: center; }
.test-heading { justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.test-heading h2 { margin: 5px 0 0; color: #303133; font-size: 18px; }
.step-label, .section-title span { color: #337ff2; font-size: 11px; font-weight: 700; letter-spacing: .14em; }
.threshold-note { padding: 7px 11px; color: #7a828e; background: #f5f7fa; border-radius: 6px; font-size: 12px; }
.query-input :deep(.el-textarea__inner) { padding: 16px; line-height: 1.7; box-shadow: 0 0 0 1px #dcdfe6 inset; }
.query-input :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px #337ff2 inset; }
.submit-row { justify-content: space-between; margin-top: 16px; }
.submit-row > span { color: #a8abb2; font-size: 12px; }
.submit-row .el-button { min-width: 128px; }
.result-section { margin-top: 32px; padding-top: 28px; border-top: 1px solid #ebeef5; }
.section-title { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
.section-title strong { font-size: 17px; }
.fallback strong { display: block; margin-bottom: 6px; color: #7a5d18; }
.fallback p { margin: 0; font-size: 13px; line-height: 1.6; }
.match-card { border: 1px solid #d9ecff; border-left: 4px solid #67c23a; background: #f5fbf2; }
.match-card :deep(.el-card__body) { justify-content: space-between; gap: 20px; padding: 20px 22px; }
.match-main { gap: 14px; }
.match-main > div { display: flex; flex-direction: column; gap: 5px; }
.match-main strong { color: #303133; font-size: 17px; }
.match-main span { color: #909399; font-family: Consolas, monospace; font-size: 12px; }

@media (max-width: 600px) {
  .test-card :deep(.el-card__body) { padding: 20px 16px; }
  .test-heading, .match-card :deep(.el-card__body) { align-items: flex-start; flex-direction: column; }
  .threshold-note { align-self: flex-start; }
}
</style>
