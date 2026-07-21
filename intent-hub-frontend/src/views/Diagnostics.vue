<template>
  <el-alert v-if="syncStatus && !syncStatus.synced" type="warning" :closable="false" show-icon title="本地存在未同步修改；诊断基于当前向量数据库，建议先同步后扫描。" class="sync-alert" />
  <el-card shadow="never" class="panel-card">
    <el-tabs v-model="view">
      <template #extra><el-button type="primary" :loading="scanning" @click="scan(true)">开始扫描</el-button></template>
      <el-tab-pane label="列表" name="list">
        <div v-loading="scanning">
          <el-empty v-if="!results.length" description="未发现语义冲突" />
          <section v-for="group in results" :key="group.route_id" class="conflict-group">
            <h3>{{ group.route_name }} <small>#{{ group.route_id }}</small></h3>
            <div v-for="overlap in group.overlaps" :key="overlap.target_route_id" class="overlap-row">
              <div><strong>{{ overlap.target_route_name }}</strong><span>区域相似度 {{ overlap.region_similarity.toFixed(4) }} · 冲突语料 {{ overlap.total_conflicts }}</span></div>
              <div class="conflict-samples"><el-tag v-for="point in overlap.instance_conflicts.slice(0,3)" :key="point.source_utterance+point.target_utterance" type="danger" effect="plain">{{ point.source_utterance }} ↔ {{ point.target_utterance }} ({{ point.similarity.toFixed(3) }})</el-tag></div>
              <el-button type="warning" plain @click="openRepair(group, overlap)">诊断修复</el-button>
            </div>
          </section>
        </div>
      </el-tab-pane>
      <el-tab-pane label="分布图" name="map">
        <div class="map-toolbar"><el-button :loading="mapLoading" @click="loadMap">刷新分布图</el-button><span>共 {{ points.length }} 个正向语料向量</span></div>
        <div v-loading="mapLoading" class="map-wrap">
          <svg v-if="points.length" viewBox="0 0 1000 560" class="map-svg">
            <g v-for="point in plottedPoints" :key="`${point.route_id}-${point.utterance}-${point.x}`"><circle :cx="point.sx" :cy="point.sy" r="5" :fill="color(point.route_id)" opacity=".78"><title>{{ point.route_name }}：{{ point.utterance }}</title></circle></g>
          </svg>
          <el-empty v-else description="暂无可视化数据" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-card>

  <el-dialog v-model="repairVisible" title="冲突修复" width="900px" destroy-on-close>
    <div v-if="source && target" v-loading="suggesting">
      <div class="route-columns">
        <div class="route-pool" @dragover.prevent @drop="dropTo('source')"><h4>{{ source.title }}（拖入此处）</h4><el-input v-model="sourceText" type="textarea" :rows="8" /><div class="drag-list"><span v-for="item in sourceItems" :key="item" draggable="true" @dragstart="drag(item,'source')">{{ item }}</span></div></div>
        <div class="route-pool" @dragover.prevent @drop="dropTo('target')"><h4>{{ target.title }}（拖入此处）</h4><el-input v-model="targetText" type="textarea" :rows="8" /><div class="drag-list"><span v-for="item in targetItems" :key="item" draggable="true" @dragstart="drag(item,'target')">{{ item }}</span></div></div>
      </div>
      <el-card v-if="suggestion" shadow="never" class="suggestion-card"><h4>AI 修复建议</h4><p>{{ suggestion.rationalization }}</p><div><el-checkbox-group v-model="selectedAdds"><el-checkbox v-for="item in suggestion.new_utterances" :key="item" :value="item">新增：{{ item }}</el-checkbox></el-checkbox-group><el-checkbox-group v-model="selectedNegatives"><el-checkbox v-for="item in suggestion.negative_samples" :key="item" :value="item">负例：{{ item }}</el-checkbox></el-checkbox-group><el-checkbox-group v-model="selectedDeletes"><el-checkbox v-for="item in suggestion.conflicting_utterances" :key="item" :value="item">删除：{{ item }}</el-checkbox></el-checkbox-group></div></el-card>
      <el-form label-position="top" class="merge-form"><el-form-item label="合并为本地 Agent（可选）"><el-input v-model="mergeTitle" placeholder="输入合并后的名称" /></el-form-item></el-form>
    </div>
    <template #footer><el-button :loading="suggesting" @click="generateRepair">AI 修复建议</el-button><el-button type="success" plain :disabled="!mergeTitle" :loading="merging" @click="merge">合并并同步</el-button><el-button type="primary" :loading="repairing" @click="saveAndRedetect">保存、同步并重检</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'; import { ElMessage, ElMessageBox } from 'element-plus';
import { applyRepair, getAgents, getOverlaps, getRepairSuggestions, getSyncStatus, getUmapPoints, mergeAgents, syncVectors, updateAgent, type Agent, type DiagnosticResult, type RepairSuggestion, type RouteOverlap, type SyncStatus, type UmapPoint } from '../api';
const results=ref<DiagnosticResult[]>([]), agents=ref<Agent[]>([]), syncStatus=ref<SyncStatus>(); const view=ref('list'), scanning=ref(false), mapLoading=ref(false), points=ref<UmapPoint[]>([]);
const repairVisible=ref(false), suggesting=ref(false), repairing=ref(false), merging=ref(false); const source=ref<Agent>(), target=ref<Agent>(), suggestion=ref<RepairSuggestion>(); const sourceText=ref(''),targetText=ref(''),mergeTitle=ref(''); const selectedAdds=ref<string[]>([]),selectedNegatives=ref<string[]>([]),selectedDeletes=ref<string[]>([]); let dragged:{item:string;from:'source'|'target'}|null=null;
const lines=(value:string)=>Array.from(new Set(value.split('\n').map(v=>v.trim()).filter(Boolean))); const sourceItems=computed(()=>lines(sourceText.value)), targetItems=computed(()=>lines(targetText.value));
const scan=async(refresh=false)=>{scanning.value=true;try{[results.value,agents.value,syncStatus.value]=[(await getOverlaps(refresh)).data,(await getAgents()).data,(await getSyncStatus()).data]}catch(e:any){ElMessage.error(e.response?.data?.error?.detail||'诊断失败')}finally{scanning.value=false}};
const openRepair=(group:DiagnosticResult,overlap:RouteOverlap)=>{source.value=agents.value.find(a=>a.id===group.route_id);target.value=agents.value.find(a=>a.id===overlap.target_route_id);if(!source.value||!target.value)return ElMessage.error('本地 Agent 数据不存在');sourceText.value=source.value.utterances.join('\n');targetText.value=target.value.utterances.join('\n');suggestion.value=undefined;selectedAdds.value=[];selectedNegatives.value=[];selectedDeletes.value=[];mergeTitle.value=`${source.value.title} + ${target.value.title}`;repairVisible.value=true};
const generateRepair=async()=>{if(!source.value||!target.value)return;suggesting.value=true;try{suggestion.value=(await getRepairSuggestions(source.value.id,target.value.id)).data;selectedAdds.value=[...suggestion.value.new_utterances];selectedNegatives.value=[...suggestion.value.negative_samples];selectedDeletes.value=[...suggestion.value.conflicting_utterances]}catch(e:any){ElMessage.error(e.response?.data?.error?.detail||'生成修复建议失败')}finally{suggesting.value=false}};
const saveLocal=async()=>{if(!source.value||!target.value)return;let src=lines(sourceText.value).filter(v=>!selectedDeletes.value.includes(v));src=Array.from(new Set([...src,...selectedAdds.value]));const negatives=Array.from(new Set([...source.value.negative_samples,...selectedNegatives.value]));await applyRepair(source.value.id,src,negatives);await updateAgent(target.value.id,{utterances:lines(targetText.value)});};
const saveAndRedetect=async()=>{if(!source.value||!target.value)return;repairing.value=true;try{await saveLocal();await syncVectors('incremental',[source.value.id,target.value.id]);repairVisible.value=false;await scan(true);ElMessage.success('已保存到本地、同步向量并重新诊断')}catch(e:any){ElMessage.error(e.response?.data?.error?.detail||'修复失败')}finally{repairing.value=false}};
const merge=async()=>{if(!source.value||!target.value||!mergeTitle.value.trim())return;try{await ElMessageBox.confirm('合并会创建本地 Agent 并停用两个原 Agent，确认继续？','合并 Agent',{type:'warning'});merging.value=true;const merged=(await mergeAgents(source.value.id,target.value.id,mergeTitle.value.trim())).data;await syncVectors('incremental',[source.value.id,target.value.id,merged.id]);repairVisible.value=false;await scan(true);ElMessage.success('Agent 已合并并同步')}catch(e:any){if(e!=='cancel')ElMessage.error(e.response?.data?.error?.detail||'合并失败')}finally{merging.value=false}};
const drag=(item:string,from:'source'|'target')=>{dragged={item,from}}; const dropTo=(to:'source'|'target')=>{if(!dragged||dragged.from===to)return;const fromRef=dragged.from==='source'?sourceText:targetText,toRef=to==='source'?sourceText:targetText;fromRef.value=lines(fromRef.value).filter(v=>v!==dragged!.item).join('\n');toRef.value=[...lines(toRef.value),dragged.item].join('\n');dragged=null};
const loadMap=async()=>{mapLoading.value=true;try{points.value=(await getUmapPoints()).data.points}catch(e:any){ElMessage.error(e.response?.data?.error?.detail||'点云加载失败')}finally{mapLoading.value=false}};
const plottedPoints=computed(()=>{if(!points.value.length)return[];const xs=points.value.map(p=>p.x),ys=points.value.map(p=>p.y),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);return points.value.map(p=>({...p,sx:30+(p.x-minX)/(maxX-minX||1)*940,sy:30+(p.y-minY)/(maxY-minY||1)*500}))}); const color=(id:number)=>`hsl(${Math.abs(id*67)%360} 68% 52%)`;
watch(view,value=>{if(value==='map'&&!points.value.length)loadMap()}); onMounted(()=>scan(false));
</script>
<style scoped>.sync-alert{margin-bottom:18px}.conflict-group{padding:8px 0 20px;border-bottom:1px solid #ebeef5}.conflict-group h3 small{color:#909399;font-weight:400}.overlap-row{display:grid;grid-template-columns:180px 1fr auto;align-items:center;gap:16px;padding:14px;margin:10px 0;background:#fafafa;border:1px solid #ebeef5;border-radius:9px}.overlap-row>div:first-child span{display:block;margin-top:5px;color:#909399;font-size:12px}.conflict-samples{display:flex;flex-wrap:wrap;gap:6px}.map-toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;color:#909399}.map-wrap{height:560px;background:#f8fafc;border:1px solid #ebeef5;border-radius:10px}.map-svg{width:100%;height:100%}.route-columns{display:grid;grid-template-columns:1fr 1fr;gap:18px}.route-pool{padding:14px;background:#fafafa;border:1px solid #ebeef5;border-radius:10px}.route-pool h4{margin-top:0}.drag-list{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.drag-list span{padding:4px 8px;color:#337ff2;background:#ecf5ff;border-radius:5px;font-size:12px;cursor:grab}.suggestion-card{margin-top:18px}.suggestion-card :deep(.el-checkbox-group){display:flex;flex-direction:column}.merge-form{margin-top:18px}@media(max-width:800px){.overlap-row{grid-template-columns:1fr}.route-columns{grid-template-columns:1fr}}</style>
