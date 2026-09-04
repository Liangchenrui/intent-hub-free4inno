import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

const API_KEY = 'api_key';
const PREDICT_AUTH_KEY = 'predict_auth_key';

export const clearSession = () => {
  localStorage.removeItem(API_KEY);
  localStorage.removeItem(PREDICT_AUTH_KEY);
};

const setBearer = (config: any, token?: string | null) => {
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
    config.headers['X-API-Key'] = token;
  }
};

const setRawAuthorization = (config: any, token?: string | null) => {
  if (token) {
    config.headers['Authorization'] = token;
  }
};

api.interceptors.request.use((config) => {
  const url = config.url || '';
  if (url === '/auth/login') {
    return config;
  }

  const apiKey = localStorage.getItem(API_KEY);
  const predictKey = localStorage.getItem(PREDICT_AUTH_KEY);

  if (url === '/predict') {
    if (predictKey) {
      setRawAuthorization(config, predictKey);
      return config;
    }
  }
  setBearer(config, apiKey);

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || '';
    if (error.response?.status === 401 && !url.includes('/auth/login')) {
      clearSession();
      window.location.href = '/login';
    }
    if (error.response?.status === 504 || error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      error.isTimeout = true;
    }
    return Promise.reject(error);
  }
);

export interface RouteSourceMeta {
  type?: string;
  source_id?: string | null;
  import_origin?: string | null;
  managed_fields?: string[];
  source_snapshot?: Record<string, unknown>;
  upstream_present?: boolean | null;
  last_pulled_at?: string | null;
}

export interface RouteComparison {
  status: 'local_only' | 'upstream_missing' | 'snapshot_unknown' | 'local_modified' | 'locked_equal' | 'same';
  diff_fields: string[];
  diff_count: number;
  override_fields: string[];
}

export interface RouteSyncMeta {
  status?: string;
  last_synced_at?: string | null;
  version?: number;
  synced_version?: number;
  task_id?: string | null;
  error?: string | null;
  manual_overrides?: string[];
}

export interface SyncTask {
  id: string;
  kind: 'route_sync' | 'full_reindex';
  route_ids: number[];
  status: string;
  attempts: number;
  error?: string | null;
}

export interface RouteConfig {
  id: number;
  name: string;
  route_key: string;
  description: string;
  utterances: string[];
  negative_samples?: string[];
  score_threshold: number;
  negative_threshold?: number;
  source?: RouteSourceMeta;
  sync?: RouteSyncMeta;
  lifecycle_status?: string;
  comparison?: RouteComparison;
}

export interface UpstreamDiffField {
  kind: 'scalar' | 'corpus';
  changed: boolean;
  overridden: boolean;
  local_value?: string;
  upstream_value?: string;
  local_count?: number;
  upstream_count?: number;
  added?: string[];
  removed?: string[];
  unchanged_count?: number;
}

export interface UpstreamRouteDiff {
  route_id: number;
  compared_at: string | null;
  comparison: RouteComparison;
  fields: Record<string, UpstreamDiffField>;
}

export interface UpstreamPullResult {
  created: number;
  updated: number;
  unchanged: number;
  preserved_overrides: number;
  upstream_missing: number;
  routes_count: number;
  last_pulled_at?: string;
  warning?: string;
}

export interface GenerateUtterancesRequest {
  id: number;
  name: string;
  route_key: string;
  description?: string;
  count?: number;
  utterances?: string[];
}

export interface ImportSkillRouteRequest {
  skill_content: string;
}

export interface SkillRouteDraft {
  name: string;
  route_key: string;
  description: string;
  utterances: string[];
}

export interface PredictResult {
  id: number;
  name: string;
  route_key: string;
  score?: number;
}

export interface RouteFeedbackResponse {
  message: string;
  route_id: number;
  total_utterances?: number;
  total_negative_samples?: number;
}

export interface ServiceHealthResult {
  healthy: boolean;
  status_code: number | null;
  latency_ms: number;
  message: string;
}

export interface ServiceHealthResponse {
  status: 'ok' | 'degraded';
  services: Record<'embedding' | 'qdrant', ServiceHealthResult>;
}

export const getServiceHealth = () =>
  api.get<ServiceHealthResponse>('/health/services', { timeout: 15000 });

export const getRoutes = () => api.get<RouteConfig[]>('/routes');
export const pullUpstreamAgents = () =>
  api.post<UpstreamPullResult>('/routes/upstream-pull', {}, { timeout: 120000 });
export const getUpstreamRouteDiff = (id: number) =>
  api.get<UpstreamRouteDiff>(`/routes/${id}/upstream-diff`);
export const restoreUpstreamRouteFields = (id: number, fields: string[]) =>
  api.post<RouteConfig>(`/routes/${id}/restore-upstream-fields`, { fields });
export const searchRoutes = (query: string = '') =>
  api.get<RouteConfig[]>('/routes/search', { params: { q: query } });
export const createRoute = (data: RouteConfig) => api.post<RouteConfig>('/routes', data);
export const updateRoute = (id: number, data: Partial<RouteConfig>) =>
  api.put<RouteConfig>(`/routes/${id}`, data);
export const deleteRoute = (id: number) => api.delete<{ message: string }>(`/routes/${id}`);
export const getSyncTasks = (activeOnly: boolean = false) =>
  api.get<SyncTask[]>('/sync-tasks', { params: { active: activeOnly } });
export const retrySyncTask = (taskId: string) =>
  api.post<SyncTask>(`/sync-tasks/${taskId}/retry`);
export const generateUtterances = (data: GenerateUtterancesRequest) =>
  api.post<RouteConfig>('/routes/generate-utterances', data);
export const importRouteFromSkill = (data: ImportSkillRouteRequest) =>
  api.post<SkillRouteDraft>('/routes/import-skill', data, { timeout: 300000 });

export interface ImportRoutesRequest {
  routes: RouteConfig[];
  mode?: 'merge' | 'replace';
}

export interface ImportRoutesResponse {
  message: string;
  mode: 'merge' | 'replace';
  created: number;
  updated: number;
  removed: number;
  total: number;
}

export const importRoutes = (data: ImportRoutesRequest) =>
  api.post<ImportRoutesResponse>('/routes/import', data);

export interface ConflictPoint {
  source_utterance: string;
  target_utterance: string;
  similarity: number;
}

export interface RouteOverlap {
  target_route_id: number;
  target_route_name: string;
  region_similarity: number;
  instance_conflicts: ConflictPoint[];
  total_conflicts?: number;
}

export interface DiagnosticResult {
  route_id: number;
  route_name: string;
  overlaps: RouteOverlap[];
}

export interface RepairSuggestion {
  route_id: number;
  route_name: string;
  new_utterances: string[];
  negative_samples: string[];
  conflicting_utterances: string[];
  rationalization: string;
}

export const getOverlaps = (refresh: boolean = false) =>
  api.get<DiagnosticResult[]>('/diagnostics/overlap', { params: { refresh } });
export const getRouteOverlap = (routeId: number) =>
  api.get<DiagnosticResult>(`/diagnostics/overlap/${routeId}`);
export const getRepairSuggestions = (
  sourceRouteId: number,
  targetRouteId: number,
  includeNegativeSamples: boolean = false
) =>
  api.post<RepairSuggestion>(
    '/diagnostics/repair',
    { source_route_id: sourceRouteId, target_route_id: targetRouteId, include_negative_samples: includeNegativeSamples, language: localStorage.getItem('locale') || 'zh' },
    { timeout: 300000 }
  );
export const applyRepair = (routeId: number, utterances: string[]) =>
  api.post<{ success: boolean }>('/diagnostics/apply-repair', { route_id: routeId, utterances });
export const syncRoutes = (routeIds: number[]) =>
  api.post<{ message: string; results: any[] }>('/reindex/sync-route', { route_ids: routeIds });

export interface UmapPoint2D {
  x: number;
  y: number;
  route_id: number;
  route_name: string;
  utterance: string;
}

export interface UmapResponse {
  points: UmapPoint2D[];
  meta: {
    n_points: number;
    n_neighbors: number;
    min_dist: number;
  };
}

export const getUmapPoints = (params?: { n_neighbors?: number; min_dist?: number; seed?: number }) =>
  api.get<UmapResponse>('/diagnostics/umap', { params });

export interface ReindexResponse {
  message: string;
  mode: string;
  routes_count: number;
  total_points: number;
}

export const reindex = (forceFull: boolean = false) =>
  api.post<ReindexResponse>('/reindex', { force_full: forceFull });

export const predict = (text: string) => api.post<PredictResult[]>('/predict', { text });
export const submitPositiveRouteFeedback = (routeId: number, text: string) =>
  api.post<RouteFeedbackResponse>(`/routes/${routeId}/feedback/positive`, { text });
export const submitNegativeRouteFeedback = (routeId: number, text: string) =>
  api.post<RouteFeedbackResponse>(`/routes/${routeId}/feedback/negative`, { text });
export const deletePositiveRouteFeedback = (routeId: number, text: string) =>
  api.delete<RouteFeedbackResponse>(`/routes/${routeId}/feedback/positive`, {
    params: { text },
    data: { text },
  });
export const deleteNegativeRouteFeedback = (routeId: number, text: string) =>
  api.delete<RouteFeedbackResponse>(`/routes/${routeId}/feedback/negative`, {
    params: { text },
    data: { text },
  });

export type LlmProvider = 'deepseek' | 'openrouter' | 'doubao' | 'qwen' | 'gemini';

export interface SharedLlmSettings {
  LLM_PROVIDER: LlmProvider;
  LLM_API_KEY?: string | null;
  LLM_BASE_URL?: string | null;
  LLM_MODEL?: string | null;
  LLM_TEMPERATURE: number;

  UTTERANCE_GENERATION_PROMPT: string;
  AGENT_REPAIR_PROMPT: string;
  SKILL_ROUTE_IMPORT_PROMPT: string;

  REGION_THRESHOLD_SIGNIFICANT?: number;
  INSTANCE_THRESHOLD_AMBIGUOUS?: number;
}

export interface SystemSettings extends SharedLlmSettings {
  QDRANT_URL?: string;
  QDRANT_COLLECTION?: string;
  QDRANT_API_KEY?: string | null;

  EMBEDDING_SERVICE_URL: string;
  EMBEDDING_MODEL_NAME?: string;
  EMBEDDING_DEVICE?: string;
  EMBEDDING_API_FORMAT?: 'qwen' | 'tei';
  AGENT_API_URL?: string | null;
  AGENT_API_TOKEN?: string | null;
  AGENT_API_LABEL_IDS?: string;

  BATCH_SIZE?: number;

  AUTH_ENABLED?: boolean;
  API_KEYS?: string | null;
  DEFAULT_USERNAME?: string;
  DEFAULT_PASSWORD?: string;
  PREDICT_AUTH_KEY?: string | null;
  DEFAULT_ROUTE_ID?: number;
  DEFAULT_ROUTE_NAME?: string;
  DEFAULT_ROUTE_KEY?: string;
}

export const getSettings = () => api.get<SystemSettings>('/settings');
export interface CollectionOption {
  name: string;
  kind: 'collection' | 'alias';
  target: string | null;
}
export const getQdrantCollections = () =>
  api.get<{ current: string; items: string[]; collections: CollectionOption[] }>('/settings/qdrant-collections', { timeout: 15000 });
export const createQdrantCollection = (name: string) =>
  api.post<CollectionOption>('/settings/qdrant-collections', { name }, { timeout: 30000 });
export const importRoutesFromQdrant = (collection: string) =>
  api.post<{ message: string; collection: string; routes_count: number }>(
    '/settings/qdrant-import',
    { collection },
    { timeout: 120000 }
  );
export const updateSettings = (data: Partial<SystemSettings>) =>
  api.post<{ message: string; settings: SystemSettings }>('/settings', data);
export const getSystemSettings = () => api.get<SystemSettings>('/settings');
export const updateSystemSettings = (data: Partial<SystemSettings>) =>
  api.post<{ message: string; settings: SystemSettings }>('/settings', data);

export interface AddNegativeSamplesRequest {
  negative_samples: string[];
  negative_threshold?: number;
}

export const addNegativeSamples = (routeId: number, data: AddNegativeSamplesRequest) =>
  api.post<{ message: string; route_id: number; total_negative_samples: number }>(
    `/routes/${routeId}/negative-samples`,
    data
  );

export default api;
