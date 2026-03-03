import axios from 'axios';

// 根据环境变量设置 API 基础地址
// 开发环境使用 /api（通过 vite 代理）
// 生产环境直接使用完整 URL
const getBaseURL = () => {
  return '/api'
};

const api = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 API Key
api.interceptors.request.use((config) => {
  // 登录接口不需要携带 token
  if (config.url === '/auth/login') {
    return config;
  }

  // 预测接口鉴权处理
  if (config.url === '/predict') {
    const predictKey = localStorage.getItem('predict_auth_key');
    if (predictKey) {
      config.headers['Authorization'] = predictKey;
      return config;
    }
  }

  // 其他接口使用 API Key 认证
  const token = localStorage.getItem('api_key');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
    config.headers['X-API-Key'] = token;
  }
  return config;
});

// 响应拦截器：处理 401 和超时错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 如果是 401 且不是登录接口，则跳转到登录页
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('api_key');
      window.location.href = '/login';
    }
    // 处理超时错误（504 Gateway Timeout 或 timeout）
    if (error.response?.status === 504 || error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      error.isTimeout = true;
    }
    return Promise.reject(error);
  }
);

export interface RouteConfig {
  id: number;
  name: string;
  description: string;
  utterances: string[];
  negative_samples?: string[];
  score_threshold: number;
  negative_threshold?: number;
}

export interface GenerateUtterancesRequest {
  id: number;
  name: string;
  description?: string;
  count?: number;
  utterances?: string[];
}

export interface PredictResult {
  id: number;
  name: string;
  score?: number;
}

export const getRoutes = () => api.get<RouteConfig[]>('/routes');
export const searchRoutes = (query: string = '') => api.get<RouteConfig[]>('/routes/search', { params: { q: query } });
export const createRoute = (data: RouteConfig) => api.post<RouteConfig>('/routes', data);
export const updateRoute = (id: number, data: Partial<RouteConfig>) => api.put<RouteConfig>(`/routes/${id}`, data);
export const deleteRoute = (id: number) => api.delete<{ message: string }>(`/routes/${id}`);
export const generateUtterances = (data: GenerateUtterancesRequest) => api.post<RouteConfig>('/routes/generate-utterances', data);

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

  // LLM配置（通用）
  LLM_PROVIDER: 'deepseek' | 'openrouter' | 'doubao' | 'qwen' | 'gemini';
  LLM_API_KEY?: string | null;
  LLM_BASE_URL?: string | null;
  LLM_MODEL?: string | null;
  LLM_TEMPERATURE: number;

  // DeepSeek配置（向后兼容）
  DEEPSEEK_API_KEY?: string | null;
  DEEPSEEK_BASE_URL?: string;
  DEEPSEEK_MODEL?: string;

  // 提示词配置
  UTTERANCE_GENERATION_PROMPT: string;
  AGENT_REPAIR_PROMPT: string;

  // 认证配置
  PREDICT_AUTH_KEY?: string | null;
  DEFAULT_USERNAME?: string;
  DEFAULT_PASSWORD?: string;

  // 其他配置
  BATCH_SIZE?: number;
  DEFAULT_ROUTE_ID?: number;
  DEFAULT_ROUTE_NAME?: string;

  // 诊断阈值配置
  REGION_THRESHOLD_SIGNIFICANT?: number;
  INSTANCE_THRESHOLD_AMBIGUOUS?: number;
}

export const getSettings = () => api.get<Settings>('/settings');
export const updateSettings = (data: Partial<Settings>) => api.post<{ message: string; settings: Settings }>('/settings', data);

// 负例管理接口
export interface AddNegativeSamplesRequest {
  negative_samples: string[];
  negative_threshold?: number;
}

export const addNegativeSamples = (routeId: number, data: AddNegativeSamplesRequest) =>
  api.post<{ message: string; route_id: number; total_negative_samples: number }>(
    `/routes/${routeId}/negative-samples`,
    data
  );

export const deleteNegativeSamples = (routeId: number) =>
  api.delete<{ message: string; route_id: number }>(
    `/routes/${routeId}/negative-samples`
  );

export default api;

