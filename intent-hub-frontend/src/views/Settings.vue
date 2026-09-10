<template>
  <el-card v-loading="loading" shadow="never" class="panel-card settings-card">
    <el-form v-if="settings" label-position="top">
      <el-divider content-position="left">向量数据库</el-divider>
      <el-row :gutter="18">
        <el-col :md="12" :xs="24"><el-form-item label="Qdrant 地址"><el-input v-model="settings.QDRANT_URL" /></el-form-item></el-col>
        <el-col :md="12" :xs="24">
          <el-form-item label="Collection">
            <div class="collection-control">
              <el-select v-model="settings.QDRANT_COLLECTION" filterable placeholder="请选择 Collection" :loading="collectionsLoading">
                <el-option v-for="item in collections" :key="item.name" :value="item.name" :label="item.kind === 'alias' ? `${item.name}（别名）` : item.name">
                  <span>{{ item.name }}</span><small v-if="item.kind === 'alias'">别名 → {{ item.target }}</small>
                </el-option>
              </el-select>
              <el-button @click="addCollection">新增</el-button>
              <el-button type="primary" plain :loading="restoring" @click="restoreFromCollection">恢复语料</el-button>
            </div>
            <div class="field-hint">从所选 Collection 的向量 payload 恢复 Agent 正向与负向语料。</div>
          </el-form-item>
        </el-col>
      </el-row>
      <el-alert title="服务凭据由部署环境安全注入，管理页面不读取或修改。" type="info" :closable="false" show-icon />
      <el-divider content-position="left">Embedding</el-divider>
      <el-row :gutter="18"><el-col :md="12" :xs="24"><el-form-item label="服务地址"><el-input v-model="settings.EMBEDDING_SERVICE_URL" placeholder="请输入完整的 Embedding 接口地址" /></el-form-item></el-col></el-row>
      <el-divider content-position="left">LLM</el-divider>
      <el-row :gutter="18"><el-col :md="6" :xs="24"><el-form-item label="Provider"><el-select v-model="settings.LLM_PROVIDER" class="full"><el-option v-for="item in providers" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col><el-col :md="9" :xs="24"><el-form-item label="模型"><el-input v-model="settings.LLM_MODEL" /></el-form-item></el-col><el-col :md="18" :xs="24"><el-form-item label="Base URL"><el-input v-model="settings.LLM_BASE_URL" /></el-form-item></el-col><el-col :md="6" :xs="24"><el-form-item label="Temperature"><el-input-number v-model="settings.LLM_TEMPERATURE" :min="0" :max="2" :step="0.1" /></el-form-item></el-col></el-row>
      <el-divider content-position="left">未命中时的大模型兜底</el-divider>
      <el-form-item label="启用兜底">
        <el-switch v-model="settings.LLM_FALLBACK_ENABLED" />
        <div class="field-hint">仅在现有路由未命中时使用上方模型，固定温度 0。启用前完成一次增量同步；模型可以拒绝匹配或提示补充信息。</div>
      </el-form-item>
      <el-row :gutter="18">
        <el-col :md="12" :xs="24"><el-form-item label="候选意图数量"><el-input-number v-model="settings.LLM_FALLBACK_TOP_K" :min="1" :max="20" :step="1" :precision="0" :disabled="!settings.LLM_FALLBACK_ENABLED" /></el-form-item></el-col>
        <el-col :md="12" :xs="24"><el-form-item label="模型调用超时（秒）"><el-input-number v-model="settings.LLM_FALLBACK_TIMEOUT_SECONDS" :min="1" :max="60" :step="1" :disabled="!settings.LLM_FALLBACK_ENABLED" /></el-form-item></el-col>
      </el-row>
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
import { onMounted, ref } from 'vue'; import { ElMessage, ElMessageBox } from 'element-plus'; import { createCollection, getCollections, getSettings, restoreCollection, saveSettings, type CollectionOption, type Settings } from '../api';
const providers = ['deepseek','openrouter','doubao','qwen','gemini']; const settings = ref<Settings>(); const collections=ref<CollectionOption[]>([]); const loading=ref(false); const saving=ref(false); const collectionsLoading=ref(false); const restoring=ref(false);
const errorDetail=(e:any,fallback:string)=>e.response?.data?.error?.detail||fallback;
const loadCollections=async()=>{collectionsLoading.value=true;try{collections.value=(await getCollections()).data.collections}catch(e:any){ElMessage.error(errorDetail(e,'加载 Collection 失败'))}finally{collectionsLoading.value=false}};
const load=async()=>{loading.value=true;try{const [settingsResponse]=await Promise.all([getSettings(),loadCollections()]);settings.value=settingsResponse.data}catch(e:any){ElMessage.error(errorDetail(e,'加载设置失败'))}finally{loading.value=false}};
const addCollection=async()=>{try{const {value}=await ElMessageBox.prompt('请输入新 Collection 名称，只能使用字母、数字、点、下划线和连字符。','新增 Collection',{confirmButtonText:'创建',cancelButtonText:'取消',inputPattern:/^[A-Za-z0-9._-]+$/,inputErrorMessage:'Collection 名称格式不正确'});collectionsLoading.value=true;const {data}=await createCollection(value.trim());await loadCollections();if(settings.value)settings.value.QDRANT_COLLECTION=data.name;ElMessage.success(`Collection ${data.name} 已创建并选中`)}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorDetail(e,'创建 Collection 失败'))}finally{collectionsLoading.value=false}};
const restoreFromCollection=async()=>{const name=settings.value?.QDRANT_COLLECTION;if(!name)return;try{await ElMessageBox.confirm(`将从 ${name} 的向量 payload 恢复语料；相同 Agent ID 的本地语料会被更新。确认继续？`,'恢复 Collection 语料',{type:'warning',confirmButtonText:'确认恢复'});restoring.value=true;const {data}=await restoreCollection(name);ElMessage.success(`已恢复 ${data.restored_agents} 个 Agent、${data.positive_texts} 条正向语料、${data.negative_texts} 条负向语料`)}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorDetail(e,'恢复语料失败'))}finally{restoring.value=false}};
const save=async()=>{if(!settings.value)return;try{await ElMessageBox.confirm('保存后相关客户端将在下次请求时重新连接，确认继续？','保存设置',{type:'warning'});saving.value=true;const response=await saveSettings(settings.value);settings.value=response.data.settings;ElMessage.success(response.data.message)}catch(e:any){if(e!=='cancel')ElMessage.error(e.response?.data?.error?.detail||'保存失败')}finally{saving.value=false}}; onMounted(load);
</script>
<style scoped>.settings-card :deep(.el-card__body){padding:28px 32px}.settings-card :deep(.el-divider__text){color:#337ff2;font-weight:700}.collection-control{display:flex;gap:8px;width:100%}.collection-control .el-select{flex:1}.collection-control small{float:right;margin-left:20px;color:#909399}.field-hint{margin-top:7px;color:#909399;font-size:12px;line-height:1.5}.form-actions{display:flex;justify-content:flex-end;margin-top:30px}.form-actions .el-button{min-width:180px}@media(max-width:600px){.settings-card :deep(.el-card__body){padding:20px 16px}.collection-control{align-items:stretch;flex-wrap:wrap}.collection-control .el-select{flex-basis:100%}}</style>
