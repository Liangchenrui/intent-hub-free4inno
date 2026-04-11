<template>
  <el-container class="layout-container">
    <el-header class="header-wrapper">
      <div class="header-content">
        <div class="brand">
          <img src="@/assets/logo.png" alt="Intent Hub" class="logo-img" />
        </div>
        <div class="user-info">
          <LanguageSwitcher />
          <el-button type="danger" @click="handleLogout">{{ $t('common.logout') }}</el-button>
        </div>
      </div>
    </el-header>

    <el-main class="main-wrapper" v-loading="fullPageLoading">
      <div class="page-header">
        <el-tabs v-model="activeTab" class="nav-tabs" @tab-change="handleTabChange">
          <el-tab-pane :label="$t('nav.list')" name="list"></el-tab-pane>
          <el-tab-pane :label="$t('nav.test')" name="test"></el-tab-pane>
          <el-tab-pane :label="$t('nav.diagnostics')" name="diagnostics"></el-tab-pane>
          <el-tab-pane :label="$t('nav.settings')" name="settings"></el-tab-pane>
        </el-tabs>
      </div>

      <el-card shadow="never" class="content-card">
        <div class="diagnostic-header">
          <div class="title-section">
            <h2>{{ $t('diagnostics.title') }}</h2>
            <p class="description">{{ $t('diagnostics.description') }}</p>
          </div>
          <div class="action-section">
            <div class="view-mode-tabs">
              <el-tabs v-model="viewMode" class="mode-tabs">
                <el-tab-pane :label="$t('diagnostics.listView')" name="list"></el-tab-pane>
                <el-tab-pane :label="$t('diagnostics.mapView')" name="map"></el-tab-pane>
              </el-tabs>
            </div>
            <el-button 
              type="primary" 
              :icon="Search" 
              @click="handleStartScan" 
              :loading="loading || fullPageLoading"
            >
              {{ $t('diagnostics.refresh') }}
            </el-button>
          </div>
        </div>

        <div v-if="viewMode === 'map'" class="map-panel">
          <div class="map-toolbar">
            <div class="search-box">
              <el-input
                v-model="mapSearchQuery"
                placeholder=""
                class="search-input"
                clearable
                @input="handleMapSearch"
                @clear="handleMapSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
            <el-button :loading="mapLoading" @click="loadUmap" type="primary">
              {{ $t('diagnostics.loadMap') }}
            </el-button>
          </div>

          <div class="map-chart-wrap" v-loading="mapLoading" element-loading-background="rgba(255, 255, 255, 0.4)">
            <div ref="chartRef" class="map-chart" :class="{ 'chart-blur': mapLoading }"></div>
          </div>
        </div>

        <div v-else-if="!loading && results.length === 0" class="empty-state">
          <el-empty :description="$t('diagnostics.noOverlap')">
            <template #image>
              <el-icon :size="60" color="#67C23A"><CircleCheckFilled /></el-icon>
            </template>
          </el-empty>
        </div>

        <div v-else class="results-container" v-loading="loading">
          <div v-for="(result, index) in results" :key="index" class="conflict-group">
            <h3 class="source-route">
              <el-icon><Warning /></el-icon>
              {{ result.route_name }}
            </h3>
            
            <el-table :data="result.overlaps" style="width: 100%" class="overlap-table">
              <el-table-column :label="$t('diagnostics.conflictType')" width="120">
                <template #default="{ row }">
                  <div class="type-tags">
                    <el-tag v-if="row.region_similarity >= regionThreshold" size="small" type="warning" effect="dark">
                      {{ $t('diagnostics.regionOverlap') }}
                    </el-tag>
                    <el-tag v-if="row.instance_conflicts.length > 0" size="small" type="danger" effect="dark" style="margin-top: 4px">
                      {{ $t('diagnostics.instanceConflict') }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="target_route_name" :label="$t('diagnostics.targetRoute')" min-width="120" />
              <el-table-column :label="$t('diagnostics.score')" width="180">
                <template #default="{ row }">
                  <div class="score-display">
                    <div class="score-header">
                      <span class="score-val">{{ (row.region_similarity * 100).toFixed(1) }}%</span>
                    </div>
                    <el-progress 
                      :percentage="Math.round(row.region_similarity * 100)" 
                      :status="row.region_similarity > Math.max(0.95, regionThreshold) ? 'exception' : 'warning'"
                      :stroke-width="8"
                      :show-text="false"
                    />
                  </div>
                </template>
              </el-table-column>
              <el-table-column :label="$t('diagnostics.conflictingUtterances')" min-width="450">
                <template #default="{ row }">
                  <div class="conflicting-utterances">
                    <div 
                      v-for="(conflict, cIdx) in row.instance_conflicts" 
                      :key="cIdx"
                      class="conflict-pair-card"
                    >
                      <div class="pair-content">
                        <div class="source-wrapper">
                          <el-tag size="small" effect="plain" class="route-tag">{{ result.route_name }}</el-tag>
                          <span class="utt-source">{{ conflict.source_utterance }}</span>
                        </div>
                        <div class="similarity-divider">
                          <div class="line"></div>
                          <span class="sim-val">{{ Math.round(conflict.similarity * 100) }}%</span>
                          <div class="line"></div>
                        </div>
                        <div class="target-wrapper">
                          <span class="utt-target">{{ conflict.target_utterance }}</span>
                          <el-tag size="small" effect="plain" type="danger" class="route-tag">{{ row.target_route_name }}</el-tag>
                        </div>
                      </div>
                    </div>
                    <div v-if="row.total_conflicts > row.instance_conflicts.length" class="more-conflicts-tip">
                      <el-link type="info" :underline="false" @click="handleStartRepair(result, row)">
                        <el-icon><InfoFilled /></el-icon>
                        {{ $t('diagnostics.moreConflicts', { count: row.total_conflicts - row.instance_conflicts.length }) }}
                      </el-link>
                    </div>
                    <div v-if="row.instance_conflicts.length === 0" class="no-instance-conflict">
                      <el-icon><InfoFilled /></el-icon> {{ $t('diagnostics.noOverlap') }}
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column width="150">
                <template #default="{ row }">
                  <el-button 
                    size="small" 
                    type="primary" 
                    plain
                    @click="handleStartRepair(result, row)"
                  >
                    {{ $t('diagnostics.details') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-card>

      <!-- 冲突详情对话框 -->
      <el-dialog
        v-model="repairDialogVisible"
        :title="$t('diagnostics.repairTitle')"
        width="900px"
        class="repair-dialog"
      >
        <div class="repair-container">
          <!-- 第一部分：可视化分析 (点云图 + 合并按钮) -->
          <div class="repair-section">
            <h4 class="section-title">
              <el-icon><DataAnalysis /></el-icon>
              {{ $t('diagnostics.visualAnalysis') }}
            </h4>
            <div class="visual-content">
              <!-- 可视化分析：UMAP 降维图 -->
              <div class="umap-analysis">
                <div class="umap-header">
                  <p class="sub-title">{{ $t('diagnostics.pointCloudOverlap') }}</p>
                </div>
                <div v-loading="mapLoading" element-loading-background="rgba(248, 249, 250, 0.6)">
                  <div ref="repairChartRef" class="repair-umap-chart" :class="{ 'chart-blur': mapLoading }"></div>
                </div>
              </div>

              <!-- 语料冲突对比：左右语料池 -->
              <div class="conflict-comparison">
                <p class="sub-title">{{ $t('diagnostics.conflictComparison') }}</p>
                <div v-loading="poolsLoading" class="comparison-container">
                  <!-- 左侧：源路由语料池 -->
                  <div 
                    class="route-pool source-pool" 
                    :class="{ 'drop-active': dragOverId === currentSourceRoute?.route_id }"
                    @dragover.prevent="handleDragOver(currentSourceRoute?.route_id!)"
                    @dragleave="handleDragLeave"
                    @drop="handleDrop(currentSourceRoute?.route_id!)"
                  >
                    <div class="pool-header" :style="{ backgroundColor: getColorForRoute(currentSourceRoute?.route_id!) + '1a' }">
                      <el-tag size="small" :color="getColorForRoute(currentSourceRoute?.route_id!)" effect="dark" style="border:none"></el-tag>
                      {{ currentSourceRoute?.route_name }}
                      <span class="count">({{ sourceUtterances.length }})</span>
                      <el-button 
                        :icon="Plus" 
                        size="small" 
                        circle 
                        style="margin-left: auto"
                        @click="handleAddUtterance(currentSourceRoute?.route_id!)"
                      />
                    </div>
                    <div class="pool-list">
                      <div 
                        v-for="(u, idx) in sourceUtterances" 
                        :key="'s-'+idx"
                        class="pool-item"
                        :class="{ 
                          'is-conflict': isUtteranceInConflict(u, 'source'),
                          'is-negative': isUtteranceNegative(u, 'source')
                        }"
                        draggable="true"
                        @dragstart="handleDragStart(u, currentSourceRoute?.route_id!)"
                      >
                        <div class="item-content">
                          <span class="utt-text">
                            <el-tag 
                              v-if="isUtteranceNegative(u, 'source')" 
                              size="small" 
                              type="warning" 
                              effect="plain"
                              style="margin-right: 6px;"
                            >
                              负例
                            </el-tag>
                            {{ u }}
                          </span>
                          <div class="item-actions">
                             <el-button :icon="Edit" size="small" link @click="handleModifyUtterance(u, currentSourceRoute?.route_id!)" />
                             <el-button :icon="Delete" size="small" link @click="handleDeleteUtterance(u, currentSourceRoute?.route_id!)" />
                             <el-button 
                               :icon="Close" 
                               size="small" 
                               link 
                               :type="isUtteranceNegative(u, 'source') ? 'warning' : 'default'"
                               @click="handleSetAsNegative(u, currentSourceRoute?.route_id!)" 
                               :title="isUtteranceNegative(u, 'source') ? '移除负例' : '添加为负例'"
                             />
                             <el-button :icon="Rank" size="small" link class="drag-handle" />
                          </div>
                        </div>
                      </div>
                      <el-empty v-if="sourceUtterances.length === 0" :image-size="40" description="暂无语料" />
                    </div>
                  </div>

                  <div class="pool-divider">
                    <div class="divider-line"></div>
                    <el-icon><Switch /></el-icon>
                    <div class="divider-line"></div>
                  </div>

                  <!-- 右侧：目标路由语料池 -->
                  <div 
                    class="route-pool target-pool" 
                    :class="{ 'drop-active': dragOverId === currentOverlap?.target_route_id }"
                    @dragover.prevent="handleDragOver(currentOverlap?.target_route_id!)"
                    @dragleave="handleDragLeave"
                    @drop="handleDrop(currentOverlap?.target_route_id!)"
                  >
                    <div class="pool-header" :style="{ backgroundColor: getColorForRoute(currentOverlap?.target_route_id!) + '1a' }">
                      <el-tag size="small" :color="getColorForRoute(currentOverlap?.target_route_id!)" effect="dark" style="border:none"></el-tag>
                      {{ currentOverlap?.target_route_name }}
                      <span class="count">({{ targetUtterances.length }})</span>
                      <el-button 
                        :icon="Plus" 
                        size="small" 
                        circle 
                        style="margin-left: auto"
                        @click="handleAddUtterance(currentOverlap?.target_route_id!)"
                      />
                    </div>
                    <div class="pool-list">
                      <div 
                        v-for="(u, idx) in targetUtterances" 
                        :key="'t-'+idx"
                        class="pool-item"
                        :class="{ 
                          'is-conflict': isUtteranceInConflict(u, 'target'),
                          'is-negative': isUtteranceNegative(u, 'target')
                        }"
                        draggable="true"
                        @dragstart="handleDragStart(u, currentOverlap?.target_route_id!)"
                      >
                        <div class="item-content">
                          <span class="utt-text">
                            <el-tag 
                              v-if="isUtteranceNegative(u, 'target')" 
                              size="small" 
                              type="warning" 
                              effect="plain"
                              style="margin-right: 6px;"
                            >
                              负例
                            </el-tag>
                            {{ u }}
                          </span>
                          <div class="item-actions">
                             <el-button :icon="Rank" size="small" link class="drag-handle" />
                             <el-button 
                               :icon="Close" 
                               size="small" 
                               link 
                               :type="isUtteranceNegative(u, 'target') ? 'warning' : 'default'"
                               @click="handleSetAsNegative(u, currentOverlap?.target_route_id!)" 
                               :title="isUtteranceNegative(u, 'target') ? '移除负例' : '添加为负例'"
                             />
                             <el-button :icon="Edit" size="small" link @click="handleModifyUtterance(u, currentOverlap?.target_route_id!)" />
                             <el-button :icon="Delete" size="small" link @click="handleDeleteUtterance(u, currentOverlap?.target_route_id!)" />
                          </div>
                        </div>
                      </div>
                      <el-empty v-if="targetUtterances.length === 0" :image-size="40" description="暂无语料" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 第二部分：LLM 修复建议 -->
          <div class="repair-section suggestion-section">
            <h4 class="section-title">
              <el-icon><MagicStick /></el-icon>
              {{ $t('diagnostics.repairSuggestion') }}
              <el-button 
                v-if="!suggestion" 
                type="primary" 
                size="small" 
                plain 
                style="margin-left: auto"
                @click="triggerRepairSuggestions"
                :loading="repairLoading"
              >
                {{ $t('diagnostics.getEnhancedSuggestions') }}
              </el-button>
            </h4>
            <div v-loading="repairLoading" :element-loading-text="repairLoading ? t('diagnostics.repairLoading') : ''" class="suggestion-content">
              <div v-if="suggestion" class="suggestion-box">
                <div class="rationalization-card">
                  <el-icon><InfoFilled /></el-icon>
                  <p class="rationalization">{{ processedRationalization }}</p>
                </div>
                
                  <div class="suggestion-lists" v-if="suggestion">
                    <div class="s-list" v-if="suggestion.conflicting_utterances.length">
                      <span class="s-label">
                        {{ $t('diagnostics.conflictingUtterancesToDelete') }}
                        <el-tag size="small" type="danger" effect="plain" round>{{ suggestion.conflicting_utterances.length }}</el-tag>
                      </span>
                      <div class="suggestion-card-list">
                        <div 
                          v-for="(u, idx) in suggestion.conflicting_utterances" 
                          :key="'del-'+idx" 
                          class="suggestion-card-item delete-type"
                          :class="{ 'is-selected': selectedConflictingUtterances[idx] }"
                          @click="selectedConflictingUtterances[idx] = !selectedConflictingUtterances[idx]"
                        >
                          <div class="card-checkbox">
                            <el-checkbox v-model="selectedConflictingUtterances[idx]" @click.stop />
                          </div>
                          <span class="suggestion-text">{{ u }}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div class="s-list" v-if="suggestion.new_utterances.length">
                      <span class="s-label">{{ $t('diagnostics.suggestedNewUtterancesFor', { name: currentSourceRoute?.route_name }) }}</span>
                      <div class="suggestion-card-list">
                        <div 
                          v-for="(_, idx) in suggestion.new_utterances" 
                          :key="'add-'+idx" 
                          class="suggestion-card-item add-type"
                          :class="{ 'is-selected': selectedNewUtterances[idx] }"
                        >
                          <div class="card-checkbox">
                            <el-checkbox v-model="selectedNewUtterances[idx]" @click.stop />
                          </div>
                          <el-input 
                            v-model="suggestion.new_utterances[idx]" 
                            size="small"
                            class="suggestion-input"
                            @click.stop
                          />
                        </div>
                      </div>
                    </div>
                    
                    <div class="s-list" v-if="suggestion.negative_samples.length">
                      <span class="s-label">{{ $t('diagnostics.suggestedNegativeSamplesFor', { name: currentSourceRoute?.route_name }) }}</span>
                      <div class="suggestion-card-list">
                        <div 
                          v-for="(_, idx) in suggestion.negative_samples" 
                          :key="'neg-'+idx" 
                          class="suggestion-card-item negative-type"
                          :class="{ 'is-selected': selectedNegativeSamples[idx] }"
                        >
                          <div class="card-checkbox">
                            <el-checkbox v-model="selectedNegativeSamples[idx]" @click.stop />
                          </div>
                          <el-input 
                            v-model="suggestion.negative_samples[idx]" 
                            size="small"
                            class="suggestion-input"
                            @click.stop
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else-if="!repairLoading" class="empty-text">
                  {{ $t('diagnostics.noOverlap') }}
                </div>
              </div>
            </div>
          </div>
        <template #footer>
          <div class="dialog-footer">
            <el-button 
              type="info" 
              plain
              @click="handleOpenMergeDialog" 
              class="footer-btn merge-btn"
            >
              <el-icon><Switch /></el-icon>
              {{ $t('diagnostics.mergeRoutes') }}
            </el-button>
            <el-button 
              type="primary" 
              plain
              @click="handleSyncAndRedetect" 
              :loading="redetectLoading"
              class="footer-btn redetect-btn"
            >
              <el-icon><Refresh /></el-icon>
              {{ $t('diagnostics.redetect') }}
            </el-button>
            <el-button 
              v-if="suggestion && (suggestion.conflicting_utterances.length || suggestion.new_utterances.length || suggestion.negative_samples.length)"
              type="primary" 
              @click="applyRepairAction" 
              :loading="applyingRepair"
              class="footer-btn apply-btn"
            >
              <el-icon><CircleCheckFilled /></el-icon>
              {{ $t('diagnostics.applyRepair') }}
            </el-button>
          </div>
        </template>
      </el-dialog>

      <!-- 合并路由对话框 -->
      <el-dialog
        v-model="mergeDialogVisible"
        :title="$t('diagnostics.mergeRoutes')"
        width="800px"
        append-to-body
        class="merge-dialog"
      >
        <div v-if="currentSourceRoute && currentOverlap" class="merge-container">
          <el-form label-position="top" label-width="120px">
            <el-form-item :label="$t('agent.nameLabel')" required>
              <el-input 
                v-model="mergeForm.name" 
                :placeholder="$t('agent.namePlaceholder')"
                clearable
              />
            </el-form-item>
            
            <el-form-item :label="$t('agent.descLabel')">
              <el-input 
                v-model="mergeForm.description" 
                type="textarea" 
                :rows="3"
                :placeholder="$t('agent.descPlaceholder')"
                clearable
              />
            </el-form-item>
            
            <el-form-item :label="$t('agent.utteranceLabel')">
              <div class="merge-utterances">
                <div class="merge-source-info">
                  <el-tag size="small" type="warning" effect="plain">
                    {{ currentSourceRoute.route_name }}
                  </el-tag>
                  <span class="info-text">({{ sourceUtterances.length }} 条)</span>
                </div>
                <div class="merge-source-info" style="margin-top: 8px;">
                  <el-tag size="small" type="danger" effect="plain">
                    {{ currentOverlap.target_route_name }}
                  </el-tag>
                  <span class="info-text">({{ targetUtterances.length }} 条)</span>
                </div>
                <el-input 
                  v-model="mergeForm.utterancesText" 
                  type="textarea" 
                  :rows="8"
                  :placeholder="$t('diagnostics.mergedUtterancesPlaceholder', { count: mergeForm.utterances.length })"
                  style="margin-top: 12px;"
                />
              </div>
            </el-form-item>
            
            <el-form-item :label="$t('agent.negativeSamplesLabel')">
              <div class="merge-utterances">
                <div class="merge-source-info">
                  <el-tag size="small" type="warning" effect="plain">
                    {{ currentSourceRoute.route_name }}
                  </el-tag>
                  <span class="info-text">({{ sourceNegativeSamples.length }} 条)</span>
                </div>
                <div class="merge-source-info" style="margin-top: 8px;">
                  <el-tag size="small" type="danger" effect="plain">
                    {{ currentOverlap.target_route_name }}
                  </el-tag>
                  <span class="info-text">({{ targetNegativeSamples.length }} 条)</span>
                </div>
                <el-input 
                  v-model="mergeForm.negativeSamplesText" 
                  type="textarea" 
                  :rows="6"
                  :placeholder="$t('diagnostics.mergedNegativeSamplesPlaceholder', { count: mergeForm.negative_samples.length })"
                  style="margin-top: 12px;"
                />
              </div>
            </el-form-item>
          </el-form>
        </div>
        <template #footer>
          <div class="merge-dialog-footer">
            <el-button @click="mergeDialogVisible = false">{{ $t('common.cancel') }}</el-button>
            <el-button 
              type="primary" 
              @click="handleMergeRoutes" 
              :loading="mergingRoutes"
              :disabled="!mergeForm.name.trim()"
            >
              {{ $t('diagnostics.confirmMerge') }}
            </el-button>
          </div>
        </template>
      </el-dialog>

      <!-- 语料点编辑对话框 -->
      <el-dialog
        v-model="pointEditDialogVisible"
        :title="$t('diagnostics.pointInfo')"
        width="460px"
        append-to-body
        class="point-edit-dialog"
      >
        <div v-if="editingPoint" class="point-edit-form">
          <el-form label-position="top">
            <el-form-item :label="$t('diagnostics.utteranceText')">
              <el-input 
                v-model="editingPoint.newUtterance" 
                type="textarea" 
                :rows="4"
                :placeholder="$t('diagnostics.inputNewUtterancePlaceholder')"
              />
            </el-form-item>
          </el-form>
          <div class="point-meta" v-if="editingPoint.routeId">
             <el-tag size="small" :color="getColorForRoute(editingPoint.routeId)" effect="dark" style="border: none">
               {{ routeNames[editingPoint.routeId] }}
             </el-tag>
          </div>
        </div>
        <template #footer>
          <div class="point-edit-footer">
            <el-button type="danger" plain @click="handleDeletePoint" :loading="deletingPoint">
              {{ $t('common.delete') }}
            </el-button>
            <div class="footer-right">
              <el-button @click="pointEditDialogVisible = false">{{ $t('common.cancel') }}</el-button>
              <el-button type="primary" @click="handleApplyPointEdit" :loading="updatingPoint">
                {{ $t('common.confirm') }}
              </el-button>
            </div>
          </div>
        </template>
      </el-dialog>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick, onBeforeUnmount, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Warning, CircleCheckFilled, InfoFilled, MagicStick, DataAnalysis, Delete, Edit, Rank, Close, Switch, Refresh, Plus } from '@element-plus/icons-vue';
import * as echarts from 'echarts';
import { 
  getOverlaps, 
  getRouteOverlap,
  getUmapPoints, 
  getRepairSuggestions, 
  applyRepair,
  getRoutes,
  deleteRoute,
  createRoute,
  reindex,
  getSettings,
  addNegativeSamples,
  syncRoutes,
  type DiagnosticResult, 
  type UmapPoint2D, 
  type RouteOverlap,
  type RepairSuggestion
} from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';

const { t } = useI18n();
const router = useRouter();

const activeTab = ref('diagnostics');
const loading = ref(false);
const fullPageLoading = ref(false);
const results = ref<DiagnosticResult[]>([]);

const viewMode = ref<'list' | 'map'>('list');

const mapLoading = ref(false);
const umapNeighbors = ref(15);
const umapMinDist = ref(0.1);
const chartRef = ref<HTMLDivElement | null>(null);
const umapPoints = ref<UmapPoint2D[]>([]);
const chartInstance = ref<echarts.ECharts | null>(null);
const mapSearchQuery = ref('');
const currentSymbolSize = ref(10);

// 颜色映射：为每个路由分配稳定颜色
const colorByRoute = ref<Record<number, string>>({});
const routeNames = ref<Record<number, string>>({});

const regionThreshold = ref(0.85);

// 修复相关状态
const repairDialogVisible = ref(false);
const repairLoading = ref(false);
const poolsLoading = ref(false);
const applyingRepair = ref(false);
const redetectLoading = ref(false);
const isDirty = ref(false);
const suggestion = ref<RepairSuggestion | null>(null);
const currentSourceRoute = ref<DiagnosticResult | null>(null);
const currentOverlap = ref<RouteOverlap | null>(null);
const selectedNewUtterances = ref<boolean[]>([]);
const selectedConflictingUtterances = ref<boolean[]>([]);
const selectedNegativeSamples = ref<boolean[]>([]);

// 合并路由相关状态
const mergeDialogVisible = ref(false);
const mergingRoutes = ref(false);
const mergeForm = ref({
  name: '',
  description: '',
  utterances: [] as string[],
  negative_samples: [] as string[],
  utterancesText: '',
  negativeSamplesText: ''
});

// 语料列表缓存
const sourceUtterances = ref<string[]>([]);
const targetUtterances = ref<string[]>([]);
// 负例列表缓存
const sourceNegativeSamples = ref<string[]>([]);
const targetNegativeSamples = ref<string[]>([]);

const isUtteranceInConflict = (u: string, type: 'source' | 'target') => {
  if (!currentOverlap.value) return false;
  return currentOverlap.value.instance_conflicts.some(c => 
    type === 'source' ? c.source_utterance === u : c.target_utterance === u
  );
};

const isUtteranceNegative = (u: string, type: 'source' | 'target') => {
  if (type === 'source') {
    return sourceNegativeSamples.value.includes(u);
  } else {
    return targetNegativeSamples.value.includes(u);
  }
};

const fetchRouteUtterances = async () => {
  if (!currentSourceRoute.value || !currentOverlap.value) return;
  poolsLoading.value = true;
  try {
    const allRoutesRes = await getRoutes();
    const source = allRoutesRes.data.find(r => r.id === currentSourceRoute.value?.route_id);
    const target = allRoutesRes.data.find(r => r.id === currentOverlap.value?.target_route_id);
    sourceUtterances.value = source?.utterances || [];
    targetUtterances.value = target?.utterances || [];
    sourceNegativeSamples.value = source?.negative_samples || [];
    targetNegativeSamples.value = target?.negative_samples || [];
  } catch (error) {
    console.error('Failed to fetch utterances:', error);
  } finally {
    poolsLoading.value = false;
  }
};

// 点位编辑状态
const pointEditDialogVisible = ref(false);
const editingPoint = ref<{ routeId: number; originalUtterance: string; newUtterance: string } | null>(null);
const updatingPoint = ref(false);
const deletingPoint = ref(false);

const processedRationalization = computed(() => {
  if (!suggestion.value || !currentSourceRoute.value || !currentOverlap.value) return '';
  let text = suggestion.value.rationalization;
  const nameA = currentSourceRoute.value.route_name;
  const nameB = currentOverlap.value.target_route_name;
  
  // 更全方位的替换，处理各种可能的 A/B 引用
  return text
    .replace(/(?:意图|Intent)\s*[A1]/gi, `“${nameA}”`)
    .replace(/(?:意图|Intent)\s*[B2]/gi, `“${nameB}”`)
    .replace(/(?:意图实体|Intent\s+Entity)\s*[A1]/gi, `“${nameA}”`)
    .replace(/(?:意图实体|Intent\s+Entity)\s*[B2]/gi, `“${nameB}”`)
    .replace(/Agent\s*[A1]/gi, `“${nameA}”`)
    .replace(/Agent\s*[B2]/gi, `“${nameB}”`)
    .replace(/Route\s*[A1]/gi, `“${nameA}”`)
    .replace(/Route\s*[B2]/gi, `“${nameB}”`)
    .replace(/\bA\b/g, nameA)
    .replace(/\bB\b/g, nameB);
});

// 操作界面状态
const repairChartRef = ref<HTMLDivElement | null>(null);
const repairChartInstance = ref<echarts.ECharts | null>(null);

const handleStartRepair = async (sourceRoute: DiagnosticResult, overlap: RouteOverlap) => {
  currentSourceRoute.value = sourceRoute;
  currentOverlap.value = overlap;
  repairDialogVisible.value = true;
  repairLoading.value = false;
  suggestion.value = null;
  selectedNewUtterances.value = [];
  selectedConflictingUtterances.value = [];
  selectedNegativeSamples.value = [];
  
  // 重置负例列表
  sourceNegativeSamples.value = [];
  targetNegativeSamples.value = [];

  // 如果当前冲突数量被截断了，则异步加载完整冲突数据以保证详情页显示正确
  if (overlap.total_conflicts && overlap.total_conflicts > overlap.instance_conflicts.length) {
    poolsLoading.value = true;
    try {
      const res = await getRouteOverlap(sourceRoute.route_id);
      const fullOverlap = res.data.overlaps.find((o: RouteOverlap) => o.target_route_id === overlap.target_route_id);
      if (fullOverlap) {
        currentOverlap.value = fullOverlap;
      }
    } catch (e) {
      console.error('Failed to fetch full overlap details:', e);
    } finally {
      poolsLoading.value = false;
    }
  }

  // 获取完整语料列表
  fetchRouteUtterances();

  // 始终加载 UMAP 点云图
  nextTick(async () => {
    await initRepairChart();
  });
};

const triggerRepairSuggestions = async () => {
  if (!currentSourceRoute.value || !currentOverlap.value) return;
  
  repairLoading.value = true;
  try {
    const response = await getRepairSuggestions(
      currentSourceRoute.value.route_id, 
      currentOverlap.value.target_route_id,
      true // Request Negative Utterances
    );
    suggestion.value = response.data;
    selectedNewUtterances.value = new Array(suggestion.value.new_utterances.length).fill(true);
    selectedConflictingUtterances.value = new Array(suggestion.value.conflicting_utterances.length).fill(true);
    selectedNegativeSamples.value = new Array(suggestion.value.negative_samples.length).fill(true);
  } catch (error: any) {
    console.error('Failed to get repair suggestions:', error);
    // 检查是否是超时错误
    if (error.response?.status === 504 || error.isTimeout || error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error(t('diagnostics.repairTimeout'));
    } else {
      ElMessage.warning(t('diagnostics.repairError'));
    }
  } finally {
    repairLoading.value = false;
  }
};

const handleAddUtterance = (routeId: number) => {
  ElMessageBox.prompt(t('diagnostics.inputNewUtterancePrompt'), t('diagnostics.inputNewUtteranceTitle'), {
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
    inputPattern: /.+/,
    inputErrorMessage: t('diagnostics.inputNewUtteranceError')
  }).then(({ value }) => {
    if (routeId === currentSourceRoute.value?.route_id) {
      sourceUtterances.value = [...sourceUtterances.value, value];
    } else if (routeId === currentOverlap.value?.target_route_id) {
      targetUtterances.value = [...targetUtterances.value, value];
    }
    isDirty.value = true;
    ElMessage.success(t('diagnostics.utteranceAdded'));
  }).catch(() => {});
};

const initRepairChart = async () => {
  await nextTick();
  if (!repairChartRef.value) return;

  if (repairChartInstance.value) {
    repairChartInstance.value.dispose();
  }

  repairChartInstance.value = echarts.init(repairChartRef.value);
  
  // 注册点击事件
  repairChartInstance.value.on('click', (params: any) => {
    if (params.data && params.data.utterance) {
      const data = params.data;
      const routeId = params.seriesName === currentSourceRoute.value?.route_name 
        ? currentSourceRoute.value?.route_id 
        : currentOverlap.value?.target_route_id;
      
      if (routeId) {
        editingPoint.value = {
          routeId,
          originalUtterance: data.utterance,
          newUtterance: data.utterance
        };
        pointEditDialogVisible.value = true;
      }
    }
  });

  // 如果没有全局 UMAP 数据，先加载一次
  if (umapPoints.value.length === 0) {
    await loadUmap();
  }

  updateRepairChart();
};

const updateRepairChart = () => {
  if (!repairChartInstance.value || !umapPoints.value.length || !currentOverlap.value || !currentSourceRoute.value) return;

  const sourceId = currentSourceRoute.value.route_id;
  const targetId = currentOverlap.value.target_route_id;

  // 过滤出这两个路由的点
  const sourcePoints = umapPoints.value.filter(p => p.route_id === sourceId);
  const targetPoints = umapPoints.value.filter(p => p.route_id === targetId);

  const series = [
    {
      name: currentSourceRoute.value.route_name,
      type: 'scatter' as const,
      data: sourcePoints.map(p => ({ value: [p.x, p.y], utterance: p.utterance })),
      symbolSize: 14,
      itemStyle: { 
        color: getColorForRoute(sourceId),
        opacity: 0.7,
        borderWidth: 0
      },
      emphasis: { 
        focus: 'series' as const,
        blurScope: 'coordinateSystem' as const,
        itemStyle: { 
          borderWidth: 0, 
          shadowBlur: 0,
          opacity: 1
        } 
      }
    },
    {
      name: currentOverlap.value.target_route_name,
      type: 'scatter' as const,
      data: targetPoints.map(p => ({ value: [p.x, p.y], utterance: p.utterance })),
      symbolSize: 14,
      itemStyle: { 
        color: getColorForRoute(targetId),
        opacity: 0.7,
        borderWidth: 0
      },
      emphasis: { 
        focus: 'series' as const,
        blurScope: 'coordinateSystem' as const,
        itemStyle: { 
          borderWidth: 0, 
          shadowBlur: 0,
          opacity: 1
        } 
      }
    }
  ];

  const option: echarts.EChartsOption = {
    animationDuration: 1500,
    animationEasing: 'cubicOut',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#eee',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#333', fontSize: 13 },
      extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.12); border-radius: 8px;',
      formatter: (params: any) => {
        if (params.seriesName === (t('common.other') || 'Other')) return '';
        return `<div>
          <div style="margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
            <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${params.color};"></span>
            <strong style="color: #1a1a1a; font-size: 14px;">${params.seriesName}</strong>
          </div>
          <div style="max-width: 240px; white-space: normal; line-height: 1.6; color: #666;">${params.data.utterance}</div>
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #f0f0f0; font-size: 11px; color: #409EFF; font-weight: 500;">
            ${t('diagnostics.clickToEdit')}
          </div>
        </div>`;
      }
    },
    legend: { 
      bottom: 5,
      itemWidth: 10,
      itemHeight: 10,
      selectedMode: false,
      textStyle: { color: '#909399', fontSize: 12 }
    },
    grid: { top: 30, left: 30, right: 30, bottom: 50 },
    xAxis: { 
      scale: true, 
      splitLine: { show: true, lineStyle: { type: 'dashed', color: '#f0f0f0' } },
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false }
    },
    yAxis: { 
      scale: true, 
      splitLine: { show: true, lineStyle: { type: 'dashed', color: '#f0f0f0' } },
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false }
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        yAxisIndex: [0],
      }
    ],
    series
  };

  repairChartInstance.value.setOption(option);
};

// 操作处理逻辑
const handleApplyPointEdit = async () => {
  if (!editingPoint.value) return;
  
  const { routeId, originalUtterance, newUtterance } = editingPoint.value;

  if (routeId === currentSourceRoute.value?.route_id) {
    sourceUtterances.value = sourceUtterances.value.map(u => u === originalUtterance ? newUtterance : u);
  } else if (routeId === currentOverlap.value?.target_route_id) {
    targetUtterances.value = targetUtterances.value.map(u => u === originalUtterance ? newUtterance : u);
  }

  isDirty.value = true;
  pointEditDialogVisible.value = false;
  ElMessage.success(t('diagnostics.utteranceUpdated'));
};

const handleDeletePoint = async () => {
  if (!editingPoint.value) return;

  try {
    await ElMessageBox.confirm(t('diagnostics.deleteUtteranceConfirm'), t('common.warning'), { type: 'warning' });
    
    const { routeId, originalUtterance } = editingPoint.value;

    if (routeId === currentSourceRoute.value?.route_id) {
      sourceUtterances.value = sourceUtterances.value.filter(u => u !== originalUtterance);
    } else if (routeId === currentOverlap.value?.target_route_id) {
      targetUtterances.value = targetUtterances.value.filter(u => u !== originalUtterance);
    }

    isDirty.value = true;
    pointEditDialogVisible.value = false;
    ElMessage.success(t('diagnostics.utteranceRemoved'));
  } catch (error) {
    // ignore
  }
};

const handleDeleteUtterance = async (utterance: string, routeId: number) => {
  if (!utterance || !routeId) return;
  
  try {
    await ElMessageBox.confirm(t('diagnostics.deleteUtteranceConfirm'), t('common.warning'), { type: 'warning' });
    
    if (routeId === currentSourceRoute.value?.route_id) {
      sourceUtterances.value = sourceUtterances.value.filter(u => u !== utterance);
    } else if (routeId === currentOverlap.value?.target_route_id) {
      targetUtterances.value = targetUtterances.value.filter(u => u !== utterance);
    }
    isDirty.value = true;
    ElMessage.success(t('diagnostics.utteranceRemoved'));
  } catch (error) {
    // ignore
  }
};

const handleModifyUtterance = (utterance: string, routeId: number) => {
  if (!utterance || !routeId) return;
  editingPoint.value = {
    routeId,
    originalUtterance: utterance,
    newUtterance: utterance
  };
  pointEditDialogVisible.value = true;
};

const handleSetAsNegative = async (utterance: string, routeId: number) => {
  if (!utterance || !routeId) return;
  
  const isSource = routeId === currentSourceRoute.value?.route_id;
  const isTarget = routeId === currentOverlap.value?.target_route_id;
  
  if (!isSource && !isTarget) return;
  
  const currentNegatives = isSource ? sourceNegativeSamples.value : targetNegativeSamples.value;
  const isAlreadyNegative = currentNegatives.includes(utterance);
  
  try {
    if (isAlreadyNegative) {
      // 移除负例
      await ElMessageBox.confirm(
        t('diagnostics.removeNegativeConfirm', { utterance }),
        t('common.warning'),
        { type: 'warning' }
      );
      
      const updatedNegatives = currentNegatives.filter(u => u !== utterance);
      await addNegativeSamples(routeId, { negative_samples: updatedNegatives });
      
      if (isSource) {
        sourceNegativeSamples.value = updatedNegatives;
      } else {
        targetNegativeSamples.value = updatedNegatives;
      }
      
      ElMessage.success(t('diagnostics.negativeRemoved'));
    } else {
      // 添加负例
      await ElMessageBox.confirm(
        t('diagnostics.addNegativeConfirm', { utterance }),
        t('diagnostics.addNegativeTitle'),
        { type: 'info' }
      );
      
      // 1. 从正向例子中移除
      let updatedUtterances: string[];
      if (isSource) {
        updatedUtterances = sourceUtterances.value.filter(u => u !== utterance);
        sourceUtterances.value = updatedUtterances;
      } else {
        updatedUtterances = targetUtterances.value.filter(u => u !== utterance);
        targetUtterances.value = updatedUtterances;
      }
      
      // 2. 更新后端的 utterances（移除正例）
      await applyRepair(routeId, updatedUtterances);
      
      // 3. 添加到负例列表
      const updatedNegatives = [...currentNegatives, utterance];
      await addNegativeSamples(routeId, { negative_samples: updatedNegatives });
      
      if (isSource) {
        sourceNegativeSamples.value = updatedNegatives;
      } else {
        targetNegativeSamples.value = updatedNegatives;
      }
      
      ElMessage.success(t('diagnostics.negativeAdded'));
    }
    
    // 标记为已修改，提示用户重新检测
    isDirty.value = true;
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('Failed to update Negative Utterances:', error);
      ElMessage.error(t('diagnostics.negativeUpdateError'));
    }
  }
};

// 拖拽移动语料逻辑
const draggingUtterance = ref<{ text: string; fromRouteId: number } | null>(null);
const dragOverId = ref<number | null>(null);

const handleDragStart = (utterance: string, fromRouteId: number) => {
  draggingUtterance.value = { text: utterance, fromRouteId };
};

const handleDragOver = (routeId: number) => {
  if (draggingUtterance.value && draggingUtterance.value.fromRouteId !== routeId) {
    dragOverId.value = routeId;
  }
};

const handleDragLeave = () => {
  dragOverId.value = null;
};

const handleDrop = async (toRouteId: number) => {
  const { text, fromRouteId } = draggingUtterance.value || {};
  draggingUtterance.value = null;
  dragOverId.value = null;

  if (!text || !fromRouteId || fromRouteId === toRouteId) return;

  // 本地移动
  if (fromRouteId === currentSourceRoute.value?.route_id) {
    sourceUtterances.value = sourceUtterances.value.filter(u => u !== text);
  } else if (fromRouteId === currentOverlap.value?.target_route_id) {
    targetUtterances.value = targetUtterances.value.filter(u => u !== text);
  }

  if (toRouteId === currentSourceRoute.value?.route_id) {
    sourceUtterances.value = [...sourceUtterances.value, text];
  } else if (toRouteId === currentOverlap.value?.target_route_id) {
    targetUtterances.value = [...targetUtterances.value, text];
  }

  isDirty.value = true;
  ElMessage.info(t('diagnostics.utteranceMoved'));
};

const applyRepairAction = async () => {
  if (!suggestion.value || !currentSourceRoute.value || !currentOverlap.value) return;

  applyingRepair.value = true;
  try {
    // 1. 获取现有路由的所有 utterances
    const allRoutesRes = await getRoutes();
    const currentRoute = allRoutesRes.data.find(r => r.id === currentSourceRoute.value?.route_id);
    
    if (!currentRoute) throw new Error('Route not found');

    // 2. 结合选中的新例句，并删除选中的冲突例句
    const toDelete = suggestion.value.conflicting_utterances.filter((_, idx) => selectedConflictingUtterances.value[idx]);
    let finalUtterances = currentRoute.utterances.filter(u => !toDelete.includes(u));
    
    const newUtterancesToAdd = suggestion.value.new_utterances.filter((_, idx) => selectedNewUtterances.value[idx]);
    finalUtterances = [...finalUtterances, ...newUtterancesToAdd];

    // 3. 应用修复（更新路由配置）
    await applyRepair(currentSourceRoute.value.route_id, finalUtterances);
    
    // 4. 处理负向语料（如果有选中的）
    const negativeSamplesToAdd = suggestion.value.negative_samples.filter((_, idx) => selectedNegativeSamples.value[idx]);
    if (negativeSamplesToAdd.length > 0) {
      // 获取当前路由的负例列表
      const currentNegativeSamples = currentRoute.negative_samples || [];
      // 合并新的负例（去重）
      const updatedNegativeSamples = Array.from(new Set([...currentNegativeSamples, ...negativeSamplesToAdd]));
      await addNegativeSamples(currentSourceRoute.value.route_id, { negative_samples: updatedNegativeSamples });
    }
    
    ElMessage.success(t('diagnostics.repairApplied'));
    repairDialogVisible.value = false;
  } catch (error: any) {
    ElMessage.error(t('diagnostics.applyError'));
  } finally {
    applyingRepair.value = false;
  }
};

/** 开始扫描：先全量同步向量库，再执行诊断（修改路由后点一次即可看到最新诊断） */
const handleStartScan = async () => {
  fullPageLoading.value = true;
  loading.value = true;
  try {
    await reindex(true); // 全量同步向量库
    await runDiagnostics(true); // 再执行诊断并刷新结果
  } catch (error) {
    ElMessage.error(t('agent.fetchError'));
  } finally {
    loading.value = false;
    fullPageLoading.value = false;
  }
};

const runDiagnostics = async (refresh: boolean = false): Promise<number | undefined> => {
  if (refresh) {
    fullPageLoading.value = true;
  }
  loading.value = true;
  
  try {
    // 注意：进入诊断页或点击"刷新"时，不自动触发全量同步
    // 只有点击"重新检测"按钮时才会同步向量数据库
    const response = await getOverlaps(refresh);
    results.value = response.data;
    if (results.value.length > 0) {
      ElMessage.warning(t('diagnostics.overlapDetected', { count: results.value.length }));
    } else {
      ElMessage.success(t('diagnostics.noOverlap'));
    }
    return response.status;
  } catch (error) {
    ElMessage.error(t('agent.fetchError'));
  } finally {
    loading.value = false;
    fullPageLoading.value = false;
  }
};

const getColorForRoute = (routeId: number): string => {
  const cached = colorByRoute.value[routeId];
  if (cached) return cached;
  // 稳定哈希到色相，生成鲜艳但易区分的颜色
  const hue = (routeId * 137.508) % 360; // 使用黄金角度确保分布均匀
  const saturation = 65 + (routeId % 3) * 10; // 65-85%
  const lightness = 45 + (routeId % 2) * 10; // 45-55%
  const color = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  colorByRoute.value[routeId] = color;
  return color;
};

const initChart = async () => {
  await nextTick();
  const chartDom = chartRef.value;
  if (!chartDom) return;

  // 如果已存在实例，先销毁
  if (chartInstance.value) {
    chartInstance.value.dispose();
  }

  chartInstance.value = echarts.init(chartDom);
  
  // 注册点击事件，支持编辑点
  chartInstance.value.on('click', (params: any) => {
    if (params.data && params.data.utterance) {
      const data = params.data;
      if (data.routeId) {
        editingPoint.value = {
          routeId: data.routeId,
          originalUtterance: data.utterance,
          newUtterance: data.utterance
        };
        pointEditDialogVisible.value = true;
      }
    }
  });

  // 监听缩放事件，实现动态点大小
  chartInstance.value.on('dataZoom', () => {
    const option = chartInstance.value?.getOption() as any;
    if (option && option.dataZoom && option.dataZoom[0]) {
      const zoomLevel = option.dataZoom[0].end - option.dataZoom[0].start; 
      // 缩放越小（zoomLevel越小），点越大
      const newSize = Math.max(6, Math.min(24, 25 - (zoomLevel / 100) * 18));
      
      if (Math.abs(newSize - currentSymbolSize.value) > 0.5) {
        currentSymbolSize.value = newSize;
        updateChart();
      }
    }
  });

  // 监听窗口大小变化
  const resizeHandler = () => {
    chartInstance.value?.resize();
  };
  window.addEventListener('resize', resizeHandler);
  
  // 在组件卸载时清理
  onBeforeUnmount(() => {
    window.removeEventListener('resize', resizeHandler);
    if (chartInstance.value) {
      chartInstance.value.dispose();
      chartInstance.value = null;
    }
  });

  updateChart();
};

const updateChart = () => {
  if (!chartInstance.value || !umapPoints.value.length) return;

  // 按路由分组数据
  const routeGroups: Record<number, Array<[number, number, UmapPoint2D]>> = {};
  const routeIdSet = new Set<number>();

  umapPoints.value.forEach(point => {
    const routeId = point.route_id;
    routeIdSet.add(routeId);
    if (!routeGroups[routeId]) {
      routeGroups[routeId] = [];
      routeNames.value[routeId] = point.route_name || `Route ${routeId}`;
    }
    const group = routeGroups[routeId];
    if (group) {
      group.push([point.x, point.y, point]);
    }
  });

  // 构建 ECharts series 数据
  const series = Array.from(routeIdSet).map(routeId => {
    const group = routeGroups[routeId] || [];
    const routeColor = getColorForRoute(routeId);
    return {
      name: routeNames.value[routeId] || `Route ${routeId}`,
      type: 'scatter' as const,
      data: group.map(([x, y, point]) => {
        const isMatch = mapSearchQuery.value && point.utterance.toLowerCase().includes(mapSearchQuery.value.toLowerCase());
        return {
          value: [x, y],
          routeId: point.route_id,
          routeName: point.route_name,
          utterance: point.utterance,
          symbolSize: isMatch ? currentSymbolSize.value * 2.8 : currentSymbolSize.value,
          itemStyle: isMatch ? {
            color: routeColor,
            opacity: 1,
            shadowBlur: 20,
            shadowColor: routeColor,
            borderColor: '#fff',
            borderWidth: 2
          } : undefined,
          label: isMatch ? {
            show: true,
            formatter: '{b}',
            position: 'top' as const,
            color: '#333',
            backgroundColor: 'rgba(255,255,255,0.9)',
            padding: [4, 8],
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 'bold' as const
          } : undefined
        };
      }),
      symbolSize: currentSymbolSize.value,
      itemStyle: {
        color: routeColor,
        opacity: 0.6,
        borderWidth: 0,
      },
      emphasis: {
        focus: 'series' as const,
        blurScope: 'coordinateSystem' as const,
        itemStyle: {
          opacity: 1,
          borderWidth: 0,
          shadowBlur: 0,
        },
      },
    };
  });

  const option: echarts.EChartsOption = {
    animationDuration: 1500,
    animationEasing: 'cubicOut',
    title: {
      text: t('diagnostics.mapTitle'),
      left: 20,
      top: 20,
      textStyle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#303133',
      },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#eee',
      borderWidth: 1,
      padding: [12, 16],
      textStyle: { color: '#333', fontSize: 13 },
      extraCssText: 'box-shadow: 0 4px 20px rgba(0,0,0,0.12); border-radius: 12px;',
      formatter: (params: any) => {
        const data = params.data;
        const color = params.color;
        return `<div style="min-width: 180px;">
          <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
            <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${color};"></span>
            <strong style="color: #1a1a1a; font-size: 15px;">${data.routeName || `Route ${data.routeId}`}</strong>
          </div>
          <div style="line-height: 1.6; color: #666; word-break: break-all;">${data.utterance}</div>
          <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #f0f0f0; font-size: 11px; color: #409EFF; font-weight: 500; display: flex; align-items: center; gap: 4px;">
            <i class="el-icon-edit"></i> ${t('diagnostics.clickToEdit')}
          </div>
        </div>`;
      },
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 25,
      top: 70,
      bottom: 25,
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 12,
      textStyle: {
        fontSize: 12,
        color: '#606266',
      },
      selectedMode: false,
    },
    grid: {
      left: 40,
      right: '18%',
      top: 80,
      bottom: 60,
      containLabel: false,
    },
    xAxis: {
      type: 'value',
      scale: true,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#f5f7fa',
          type: 'solid',
        },
      },
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#eee' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#f5f7fa',
          type: 'solid',
        },
      },
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#eee' } },
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        yAxisIndex: [0],
      },
    ],
    series,
  };

  chartInstance.value.setOption(option, true);
};

const handleMapSearch = () => {
  if (!mapSearchQuery.value) {
    updateChart();
    return;
  }

  const query = mapSearchQuery.value.toLowerCase();
  const matches = umapPoints.value.filter(p => p.utterance.toLowerCase().includes(query));
  
  if (matches.length > 0 && chartInstance.value) {
    const avgX = matches.reduce((sum, p) => sum + p.x, 0) / matches.length;
    const avgY = matches.reduce((sum, p) => sum + p.y, 0) / matches.length;

    chartInstance.value.dispatchAction({
      type: 'dataZoom',
      startValue: avgX - 5,
      endValue: avgX + 5,
      xAxisIndex: 0
    });
    chartInstance.value.dispatchAction({
      type: 'dataZoom',
      startValue: avgY - 5,
      endValue: avgY + 5,
      yAxisIndex: 0
    });
  }
  updateChart();
};

const loadUmap = async () => {
  mapLoading.value = true;
  try {
    const response = await getUmapPoints({ 
      n_neighbors: umapNeighbors.value, 
      min_dist: umapMinDist.value, 
      seed: 42 
    });
    umapPoints.value = response.data.points || [];
    if (!umapPoints.value.length) {
      ElMessage.info(t('diagnostics.noData'));
      return;
    }
    
    // 初始化图表（如果尚未初始化）
    if (!chartInstance.value) {
      await initChart();
    } else {
      updateChart();
    }
    
    ElMessage.success(t('diagnostics.mapLoaded', { count: umapPoints.value.length }));
  } catch (e) {
    ElMessage.error(t('agent.fetchError'));
  } finally {
    mapLoading.value = false;
  }
};

// 监听视图模式切换，切换到 map 时自动加载点云图
watch(viewMode, async (newMode) => {
  if (newMode === 'map') {
    await nextTick();
    // 如果还没有加载过点云图，则自动加载
    if (umapPoints.value.length === 0) {
      await loadUmap();
    } else {
      // 如果已经加载过，只需初始化图表
      await initChart();
    }
  }
});

const handleTabChange = (tabName: any) => {
  if (tabName === 'list') {
    router.push('/');
  } else if (tabName === 'test') {
    router.push('/test');
  } else if (tabName === 'diagnostics') {
    router.push('/diagnostics');
  } else if (tabName === 'settings') {
    router.push('/settings');
  }
};

const handleSyncAndRedetect = async () => {
  if (!currentSourceRoute.value || !currentOverlap.value) return;

  redetectLoading.value = true;
  try {
    // 1. 更新路由配置到后端 (源路由和目标路由)
    await applyRepair(currentSourceRoute.value.route_id, sourceUtterances.value);
    await applyRepair(currentOverlap.value.target_route_id, targetUtterances.value);
    
    // 2. 只同步这两个路由的向量数据库（不进行全量同步）
    const routeIds = [
      currentSourceRoute.value.route_id,
      currentOverlap.value.target_route_id
    ];
    await syncRoutes(routeIds);
    
    // 3. 实时重新检测冲突 (使用全页面 loading)
    fullPageLoading.value = true;
    const response = await getOverlaps(true); // 强制刷新
    
    results.value = response.data;

    // 4. 计算当前特定的冲突是否已被解决
    const updatedSource = results.value.find(r => r.route_id === currentSourceRoute.value?.route_id);
    const updatedOverlap = updatedSource?.overlaps.find(o => o.target_route_id === currentOverlap.value?.target_route_id);
    
    if (!updatedOverlap) {
      // 冲突已解决，退出浮窗
      ElMessage.success(t('diagnostics.noOverlap'));
      repairDialogVisible.value = false;
      
      // 如果此时所有冲突都解决了，额外提示
      if (results.value.length === 0) {
        ElMessage.success(t('diagnostics.allConflictsResolved'));
      }
    } else {
      // 冲突仍然存在，更新数据并继续提示用户
      currentOverlap.value = updatedOverlap;
      ElMessage.warning(t('diagnostics.conflictNotResolved'));
      
      // 重新加载相关视图以反映最新状态
      await loadUmap();
      await fetchRouteUtterances();
      updateRepairChart();
    }
    
    isDirty.value = false;
  } catch (error) {
    console.error('Failed to sync and redetect:', error);
    ElMessage.error(t('diagnostics.syncFailed'));
  } finally {
    redetectLoading.value = false;
    fullPageLoading.value = false;
  }
};

const handleOpenMergeDialog = async () => {
  if (!currentSourceRoute.value || !currentOverlap.value) return;
  
  // 确保已加载语料数据
  if (sourceUtterances.value.length === 0 || targetUtterances.value.length === 0) {
    await fetchRouteUtterances();
  }
  
  // 合并语料（去重）
  const mergedUtterances = Array.from(new Set([
    ...sourceUtterances.value,
    ...targetUtterances.value
  ]));
  
  // 合并负例（去重）
  const mergedNegativeSamples = Array.from(new Set([
    ...sourceNegativeSamples.value,
    ...targetNegativeSamples.value
  ]));
  
  // 设置表单默认值
  mergeForm.value = {
    name: `${currentSourceRoute.value.route_name} + ${currentOverlap.value.target_route_name}`,
    description: t('diagnostics.mergedDescription', {
      source: currentSourceRoute.value.route_name,
      target: currentOverlap.value.target_route_name
    }),
    utterances: mergedUtterances,
    negative_samples: mergedNegativeSamples,
    utterancesText: mergedUtterances.join('\n'),
    negativeSamplesText: mergedNegativeSamples.join('\n')
  };
  
  mergeDialogVisible.value = true;
};

// 监听文本变化，同步到数组
watch(() => mergeForm.value.utterancesText, (newVal) => {
  mergeForm.value.utterances = newVal
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0);
});

watch(() => mergeForm.value.negativeSamplesText, (newVal) => {
  mergeForm.value.negative_samples = newVal
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0);
});

const handleMergeRoutes = async () => {
  if (!currentSourceRoute.value || !currentOverlap.value) return;
  
  if (!mergeForm.value.name.trim()) {
    ElMessage.warning(t('diagnostics.inputRouteName'));
    return;
  }
  
  try {
    await ElMessageBox.confirm(
      t('diagnostics.mergeConfirm', {
        source: currentSourceRoute.value.route_name,
        target: currentOverlap.value.target_route_name
      }),
      t('common.warning'),
      { type: 'warning' }
    );
    
    mergingRoutes.value = true;
    fullPageLoading.value = true;
    
    // 1. 获取两个路由的完整信息（包括 score_threshold）
    const allRoutesRes = await getRoutes();
    const sourceRoute = allRoutesRes.data.find(r => r.id === currentSourceRoute.value?.route_id);
    const targetRoute = allRoutesRes.data.find(r => r.id === currentOverlap.value?.target_route_id);
    
    if (!sourceRoute || !targetRoute) {
      throw new Error(t('diagnostics.routeNotFound'));
    }
    
    // 2. 创建新路由（使用两个路由中较高的阈值）
    const newRoute = {
      id: 0, // 新建路由，id 由后端分配
      name: mergeForm.value.name.trim(),
      route_key: `${sourceRoute.route_key}.${targetRoute.route_key}.merged`,
      description: mergeForm.value.description.trim() || '',
      utterances: mergeForm.value.utterances,
      negative_samples: mergeForm.value.negative_samples,
      score_threshold: Math.max(sourceRoute.score_threshold, targetRoute.score_threshold),
      negative_threshold: sourceRoute.negative_threshold || targetRoute.negative_threshold
    };
    
    const createRes = await createRoute(newRoute);
    const newRouteId = createRes.data.id;
    
    // 3. 删除旧路由（先删除目标路由，再删除源路由）
    await deleteRoute(currentOverlap.value.target_route_id);
    await deleteRoute(currentSourceRoute.value.route_id);
    
    // 4. 重新索引
    await reindex(true);
    
    // 5. 刷新诊断结果
    await runDiagnostics(true);
    
    // 6. 关闭对话框
    mergeDialogVisible.value = false;
    repairDialogVisible.value = false;
    
    ElMessage.success(t('diagnostics.mergeSuccess', { id: newRouteId }));
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('Failed to merge routes:', error);
      ElMessage.error(t('diagnostics.mergeFailed', { error: error.message || t('diagnostics.unknownError') }));
    }
  } finally {
    mergingRoutes.value = false;
    fullPageLoading.value = false;
  }
};

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm(t('agent.logoutConfirm'), t('agent.logoutTitle'), { type: 'warning' });
    localStorage.removeItem('api_key');
    router.push('/login');
  } catch (e) {}
};

const fetchThresholds = async () => {
  try {
    const res = await getSettings();
    if (res.data) {
      regionThreshold.value = res.data.REGION_THRESHOLD_SIGNIFICANT ?? 0.85;
    }
  } catch (err) {
    console.error('Failed to fetch settings thresholds:', err);
  }
};

onMounted(() => {
  fetchThresholds();
  // 进入诊断页时只加载现有诊断结果，不触发全量同步
  // 只有点击"更新"或"开始扫描"按钮时才会触发同步
  runDiagnostics(false);
  // 如果初始视图是 map，自动加载点云图
  if (viewMode.value === 'map') {
    nextTick(async () => {
      await loadUmap();
    });
  }
});
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
}

.header-content {
  width: 95%;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo-img {
  height: 40px;
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

.nav-tabs :deep(.el-tabs__item) {
  min-width: 120px;
  font-size: 15px;
}

.content-card {
  border-radius: 12px;
}

.diagnostic-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f0f0f0;
}

.title-section h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
}

.description {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.action-section {
  display: flex;
  align-items: center;
  gap: 30px;
}

.view-mode-tabs {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mode-tabs :deep(.el-tabs__header) {
  margin: 0;
  border-bottom: none;
}

.mode-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.mode-tabs :deep(.el-tabs__item) {
  height: 32px;
  line-height: 32px;
  padding: 0 16px;
  font-size: 14px;
}

.conflict-group {
  margin-bottom: 40px;
}

.score-display {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.score-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-val {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.source-wrapper, .target-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.route-tag {
  font-weight: 500;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-route {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 15px;
  font-size: 18px;
  color: #E6A23C;
}

.conflicting-utterances {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.type-tags {
  display: flex;
  flex-direction: column;
}

.conflict-pair-card {
  background: #fcfcfc;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 10px 15px;
  margin-bottom: 8px;
  transition: all 0.3s;
  width: 100%;
}

.conflict-pair-card:hover {
  border-color: #f56c6c;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.suggestion-input {
  flex: 1;
}

.suggestion-input :deep(.el-input__inner) {
  font-size: 13px;
}

.pair-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}

.utt-source, .utt-target {
  flex: 1;
  font-size: 13px;
  line-height: 1.4;
}

.utt-source {
  color: #303133;
  text-align: right;
}

.utt-target {
  color: #606266;
  text-align: left;
}

.similarity-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 80px;
}

.similarity-divider .line {
  height: 1px;
  background: #dcdfe6;
  flex: 1;
}

.sim-val {
  font-size: 11px;
  color: #f56c6c;
  font-weight: bold;
}

.more-conflicts-tip {
  width: 100%;
  text-align: center;
  padding: 8px;
  background: #f8f9fa;
  border-radius: 4px;
  margin-top: 4px;
}

.more-conflicts-tip :deep(.el-link) {
  font-size: 13px;
}

.no-instance-conflict {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}

.empty-state {
  padding: 60px 0;
}

.map-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.map-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 320px;
}

.search-input {
  width: 100%;
}

.map-chart-wrap {
  width: 100%;
  height: 600px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
}

.map-chart {
  width: 100%;
  height: 100%;
}

.repair-dialog :deep(.el-dialog__body) {
  padding: 0 20px 40px 20px; /* Increased bottom padding to prevent overlap with footer */
}

.repair-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 8px;
}

.section-title .el-icon {
  color: #409EFF;
}

.suggestion-box {
  background: #fff;
  border-radius: 12px;
  padding: 0;
  border: none;
}

.suggestion-content {
  min-height: 150px; /* Give it enough space for the loading text */
  display: flex;
  flex-direction: column;
  justify-content: center; /* Center the loading text vertically */
  align-items: center; /* Center the loading text horizontally */
  padding-bottom: 80px; /* Add enough padding to prevent overlap with footer */
  margin-bottom: 20px; /* Space between content and footer */
  position: relative; /* Ensure proper positioning context */
}

.suggestion-section {
  margin-bottom: 20px; /* Add margin to prevent overlap with footer */
  padding-bottom: 10px; /* Additional padding for safety */
}

.rationalization-card {
  background: #f0f7ff;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  border: 1px solid #d9ecff;
}

.rationalization-card .el-icon {
  font-size: 20px;
  color: #409EFF;
  margin-top: 2px;
}

.rationalization {
  margin: 0;
  line-height: 1.6;
  color: #409EFF;
  font-weight: 500;
  font-size: 14px;
}

.suggestion-lists {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.s-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  display: block;
}

.suggestion-card-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin-top: 8px;
}

.suggestion-card-item {
  background: #f8f9fa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  gap: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  align-items: flex-start;
}

.suggestion-card-item:hover {
  background: #fff;
  border-color: #409EFF;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.suggestion-card-item.is-selected {
  border-color: #409EFF;
  background: #ecf5ff;
}

.suggestion-card-item.delete-type.is-selected {
  border-color: #f56c6c;
  background: #fef0f0;
}

.suggestion-card-item.delete-type .card-checkbox :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: #f56c6c;
  border-color: #f56c6c;
}

.suggestion-card-item.negative-type {
  border-left: 4px solid #e6a23c;
}

.suggestion-card-item.negative-type.is-selected {
  border-color: #e6a23c;
  background: #fef8f0;
}

.suggestion-card-item.negative-type .card-checkbox :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: #e6a23c;
  border-color: #e6a23c;
}

.suggestion-text {
  font-size: 13px;
  line-height: 1.5;
  color: #606266;
  word-break: break-all;
}

.card-checkbox {
  padding-top: 2px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 10px 0;
}

.footer-btn {
  padding: 10px 24px;
  font-weight: 500;
  height: 40px;
}

.redetect-btn {
  min-width: 120px;
}

.apply-btn {
  min-width: 140px;
}

.sub-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 12px;
}

.umap-analysis {
  margin-bottom: 24px;
}

.umap-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.umap-header .sub-title {
  margin-bottom: 0;
}

.repair-umap-chart {
  width: 100%;
  height: 300px;
  background: #f8f9fa;
  border-radius: 8px;
}

.comparison-container {
  display: flex;
  align-items: stretch;
  gap: 12px;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.route-pool {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 200px;
  max-height: 400px;
  background: #fcfcfc;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  transition: all 0.3s;
}

.route-pool.drop-active {
  background: #ecf5ff;
  border: 1px dashed #409eff;
  transform: scale(1.01);
}

.pool-header {
  padding: 8px 12px;
  background: #f5f7fa;
  font-weight: bold;
  font-size: 13px;
  color: #303133;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.pool-header .count {
  font-weight: normal;
  color: #909399;
  font-size: 12px;
}

.pool-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pool-item {
  position: relative;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
  transition: all 0.2s cubic-bezier(.645,.045,.355,1);
  cursor: default;
}

.pool-item.is-conflict {
  border: 1.5px solid #f56c6c;
  border-left: 4px solid #f56c6c;
  background: #fff8f7;
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.15);
}

.pool-item.is-conflict .utt-text {
  color: #c45656;
  font-weight: 500;
}

.pool-item.is-negative {
  border-left: 4px solid #e6a23c;
  background: #fef8f0;
}

.pool-item.is-negative .utt-text {
  color: #b88230;
}

.pool-item.is-conflict.is-negative {
  border-left: 4px solid #f56c6c;
  background: linear-gradient(to right, #fff8f7 0%, #fef8f0 100%);
}

.pool-item:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: translateY(-1px);
}

.item-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.item-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s;
}

.pool-item:hover .item-actions {
  opacity: 1;
}

.pool-divider {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #dcdfe6;
  width: 40px;
}

.divider-line {
  flex: 1;
  width: 1px;
  background: #f0f0f0;
}

.pool-divider .el-icon {
  font-size: 24px;
  margin: 10px 0;
  color: #909399;
}

.drag-handle {
  cursor: grab;
}

.pool-item[draggable="true"]:active {
  cursor: grabbing;
  opacity: 0.5;
}

.utt-text {
  flex: 1;
  line-height: 1.4;
  font-size: 13px;
  word-break: break-all;
  user-select: none;
}

.empty-text {
  text-align: center;
  color: #909399;
  padding: 20px 0;
}

.chart-blur {
  filter: blur(5px);
  opacity: 0.6;
  transition: all 0.3s ease;
}

.point-edit-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
}

.point-edit-form {
  padding: 0 10px;
}

.point-meta {
  margin-top: -10px;
  margin-bottom: 20px;
}

.point-edit-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-right {
  display: flex;
  gap: 12px;
}

.merge-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.merge-container {
  padding: 0 10px;
}

.merge-utterances {
  width: 100%;
}

.merge-source-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.info-text {
  font-size: 12px;
  color: #909399;
}

.merge-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.merge-btn {
  min-width: 120px;
}
</style>
