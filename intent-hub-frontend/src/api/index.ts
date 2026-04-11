import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  if (config.url === '/auth/login') {
    return config;
  }

  if (config.url === '/predict') {
    const predictKey = localStorage.getItem('predict_auth_key');
    if (predictKey) {
      config.headers['Authorization'] = predictKey;
      return config;
    }
  }

  const token = localStorage.getItem('api_key');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
    config.headers['X-API-Key'] = token;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('api_key');
      window.location.href = '/login';
    }
    if (error.response?.status === 504 || error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      error.isTimeout = true;
    }
    return Promise.reject(error);
  }
);

export interface RouteConfig {
  id: number;
  name: string;
  route_key: string;
  description: string;
  utterances: string[];
  negative_samples?: string[];
  score_threshold: number;
  negative_threshold?: number;
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

export const getRoutes = () => api.get<RouteConfig[]>('/routes');
export const searchRoutes = (query: string = '') => api.get<RouteConfig[]>('/routes/search', { params: { q: query } });
export const createRoute = (data: RouteConfig) => api.post<RouteConfig>('/routes', data);
export const updateRoute = (id: number, data: Partial<RouteConfig>) => api.put<RouteConfig>(`/routes/${id}`, data);
export const deleteRoute = (id: number) => api.delete<{ message: string }>(`/routes/${id}`);
export const generateUtterances = (data: GenerateUtterancesRequest) => api.post<RouteConfig>('/routes/generate-utterances', data);
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
export const getRouteOverlap = (routeId: number) => api.get<DiagnosticResult>(`/diagnostics/overlap/${routeId}`);
export const getRepairSuggestions = (sourceRouteId: number, targetRouteId: number, includeNegativeSamples: boolean = false) =>
  api.post<RepairSuggestion>('/diagnostics/repair',
    { source_route_id: sourceRouteId, target_route_id: targetRouteId, include_negative_samples: includeNegativeSamples },
    { timeout: 300000 } // 5分钟超时，LLM请求可能需要较长时间
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

export const reindex = (forceFull: boolean = false) => api.post<ReindexResponse>('/reindex', { force_full: forceFull });

export const predict = (text: string) => api.post<PredictResult[]>('/predict', { text });

export interface Settings {
  // Qdrant配置
  QDRANT_URL: string;
  QDRANT_COLLECTION: string;
  QDRANT_API_KEY?: string | null;

  // Embedding模型配置
  EMBEDDING_SERVICE_URL: string;
  EMBEDDING_MODEL_NAME?: string;
  EMBEDDING_DEVICE?: string;

  // LLM配置（通用）
  LLM_PROVIDER: 'deepseek' | 'openrouter' | 'doubao' | 'qwen' | 'gemini';
  LLM_API_KEY?: string | null;
  LLM_BASE_URL?: string | null;
  LLM_MODEL?: string | null;
  LLM_TEMPERATURE: number;

  // 提示词配置
  UTTERANCE_GENERATION_PROMPT: string;
  AGENT_REPAIR_PROMPT: string;
  SKILL_ROUTE_IMPORT_PROMPT: string;

  // 认证配置
  AUTH_ENABLED?: boolean;
  API_KEYS?: string;
  PREDICT_AUTH_KEY?: string | null;
  DEFAULT_USERNAME?: string;
  DEFAULT_PASSWORD?: string;

  // 其他配置
  BATCH_SIZE?: number;
  DEFAULT_ROUTE_ID?: number;
  DEFAULT_ROUTE_NAME?: string;
  DEFAULT_ROUTE_KEY?: string;

  // 诊断阈值配置
  REGION_THRESHOLD_SIGNIFICANT?: number;
  INSTANCE_THRESHOLD_AMBIGUOUS?: number;
}

export const getSettings = () => api.get<Settings>('/settings');
export const updateSettings = (data: Partial<Settings>) => api.post<{ message: string; settings: Settings }>('/settings', data);

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
