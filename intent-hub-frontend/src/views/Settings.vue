<template>
  <el-card v-loading="loading" shadow="never" class="panel-card settings-card">
    <el-form v-if="settings" label-position="top">
      <el-divider content-position="left">向量数据库</el-divider>
      <el-row :gutter="18"><el-col :md="12" :xs="24"><el-form-item label="Qdrant 地址"><el-input v-model="settings.QDRANT_URL" /></el-form-item></el-col><el-col :md="12" :xs="24"><el-form-item label="Collection"><el-input v-model="settings.QDRANT_COLLECTION" /></el-form-item></el-col><el-col :md="12" :xs="24"><el-form-item label="Qdrant API Key"><el-input v-model="settings.QDRANT_API_KEY" type="password" show-password /></el-form-item></el-col></el-row>
      <el-divider content-position="left">Embedding</el-divider>
      <el-row :gutter="18"><el-col :md="12" :xs="24"><el-form-item label="服务地址"><el-input v-model="settings.EMBEDDING_SERVICE_URL" /></el-form-item></el-col><el-col :md="8" :xs="24"><el-form-item label="模型名称"><el-input v-model="settings.EMBEDDING_MODEL_NAME" /></el-form-item></el-col><el-col :md="4" :xs="24"><el-form-item label="批大小"><el-input-number v-model="settings.BATCH_SIZE" :min="1" /></el-form-item></el-col></el-row>
      <el-divider content-position="left">LLM</el-divider>
      <el-row :gutter="18"><el-col :md="6" :xs="24"><el-form-item label="Provider"><el-select v-model="settings.LLM_PROVIDER" class="full"><el-option v-for="item in providers" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col><el-col :md="9" :xs="24"><el-form-item label="API Key"><el-input v-model="settings.LLM_API_KEY" type="password" show-password /></el-form-item></el-col><el-col :md="9" :xs="24"><el-form-item label="模型"><el-input v-model="settings.LLM_MODEL" /></el-form-item></el-col><el-col :md="18" :xs="24"><el-form-item label="Base URL"><el-input v-model="settings.LLM_BASE_URL" /></el-form-item></el-col><el-col :md="6" :xs="24"><el-form-item label="Temperature"><el-input-number v-model="settings.LLM_TEMPERATURE" :min="0" :max="2" :step="0.1" /></el-form-item></el-col></el-row>
      <el-divider content-position="left">提示词模板</el-divider>
      <el-form-item label="正向语料推荐"><el-input v-model="settings.UTTERANCE_GENERATION_PROMPT" type="textarea" :rows="5" /></el-form-item>
      <el-form-item label="负向语料推荐"><el-input v-model="settings.NEGATIVE_SAMPLE_GENERATION_PROMPT" type="textarea" :rows="5" /></el-form-item>
      <el-form-item label="Agent 冲突修复"><el-input v-model="settings.AGENT_REPAIR_PROMPT" type="textarea" :rows="5" /></el-form-item>
      <el-divider content-position="left">诊断阈值</el-divider>
      <el-row :gutter="18"><el-col :md="12" :xs="24"><el-form-item label="区域重叠阈值"><el-slider v-model="settings.REGION_THRESHOLD_SIGNIFICANT" :min="0" :max="1" :step="0.01" show-input /></el-form-item></el-col><el-col :md="12" :xs="24"><el-form-item label="语料冲突阈值"><el-slider v-model="settings.INSTANCE_THRESHOLD_AMBIGUOUS" :min="0" :max="1" :step="0.01" show-input /></el-form-item></el-col></el-row>
      <div class="form-actions"><el-button type="primary" size="large" :loading="saving" @click="save">保存并重新连接组件</el-button></div>
    </el-form>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'; import { ElMessage, ElMessageBox } from 'element-plus'; import { getSettings, saveSettings, type Settings } from '../api';
const providers = ['deepseek','openrouter','doubao','qwen','gemini']; const settings = ref<Settings>(); const loading=ref(false); const saving=ref(false);
const load=async()=>{loading.value=true;try{settings.value=(await getSettings()).data}catch(e:any){ElMessage.error(e.response?.data?.error?.detail||'加载设置失败')}finally{loading.value=false}};
const save=async()=>{if(!settings.value)return;try{await ElMessageBox.confirm('保存后相关客户端将在下次请求时重新连接，确认继续？','保存设置',{type:'warning'});saving.value=true;const response=await saveSettings(settings.value);settings.value=response.data.settings;ElMessage.success(response.data.message)}catch(e:any){if(e!=='cancel')ElMessage.error(e.response?.data?.error?.detail||'保存失败')}finally{saving.value=false}}; onMounted(load);
</script>
<style scoped>.settings-card :deep(.el-card__body){padding:28px 32px}.settings-card :deep(.el-divider__text){color:#337ff2;font-weight:700}.form-actions{display:flex;justify-content:flex-end;margin-top:30px}.form-actions .el-button{min-width:180px}@media(max-width:600px){.settings-card :deep(.el-card__body){padding:20px 16px}}</style>
