<template>
  <div class="page-intro">
    <div>
      <h1>系统设置</h1>
      <p>管理当前服务允许调整的运行参数</p>
    </div>
  </div>

  <el-card v-loading="loading" shadow="never" class="panel-card settings-card">
    <div class="settings-heading">
      <div class="settings-icon">Q</div>
      <div>
        <h2>向量数据库</h2>
        <p>指定 Agent 向量索引使用的 Qdrant Collection</p>
      </div>
    </div>
    <el-divider />
    <el-form label-position="top" class="settings-form">
      <el-form-item label="Collection 名称">
        <el-input v-model="collection" size="large" placeholder="请输入 Qdrant Collection 名称" />
        <div class="field-hint">保存后将重新连接目标 Collection，其他连接参数由服务端固定配置。</div>
      </el-form-item>
      <div class="form-actions">
        <el-button type="primary" size="large" :loading="saving" @click="save">保存设置</el-button>
      </div>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { getSettings, saveSettings } from '../api';

const collection = ref('');
const loading = ref(false);
const saving = ref(false);
onMounted(async () => {
  loading.value = true;
  try { collection.value = (await getSettings()).data.QDRANT_COLLECTION; }
  finally { loading.value = false; }
});
const save = async () => {
  saving.value = true;
  try {
    collection.value = (await saveSettings(collection.value)).data.QDRANT_COLLECTION;
    ElMessage.success('保存成功');
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '保存失败'); }
  finally { saving.value = false; }
};
</script>

<style scoped>
.settings-card { min-height: 300px; }
.settings-card :deep(.el-card__body) { padding: 28px 32px; }
.settings-heading { display: flex; align-items: center; gap: 14px; }
.settings-icon { width: 42px; height: 42px; display: grid; place-items: center; color: #fff; background: #337ff2; border-radius: 10px; font-family: Georgia, serif; font-size: 20px; font-weight: 700; box-shadow: 0 6px 16px rgba(51, 127, 242, .22); }
.settings-heading h2 { margin: 0 0 5px; font-size: 18px; }
.settings-heading p { margin: 0; color: #909399; font-size: 12px; }
.settings-form { max-width: 760px; padding-top: 6px; }
.field-hint { margin-top: 8px; color: #909399; font-size: 12px; line-height: 1.5; }
.form-actions { display: flex; justify-content: flex-end; margin-top: 30px; }
.form-actions .el-button { min-width: 120px; }
@media (max-width: 600px) { .settings-card :deep(.el-card__body) { padding: 22px 18px; } }
</style>
