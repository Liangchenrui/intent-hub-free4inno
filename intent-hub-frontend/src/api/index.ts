import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

const MODE_KEY = 'active_mode';
const ADMIN_TOKEN_KEY = 'admin_token';
const TENANT_ACCESS_CODE_KEY = 'tenant_access_code';
const PREDICT_AUTH_KEY = 'predict_auth_key';

export type ActiveMode = 'tenant' | 'admin';

export const getActiveMode = (): ActiveMode =>
  (localStorage.getItem(MODE_KEY) as ActiveMode) || 'tenant';
export const setActiveMode = (mode: ActiveMode) => localStorage.setItem(MODE_KEY, mode);

export const clearAdminSession = () => localStorage.removeItem(ADMIN_TOKEN_KEY);
export const clearTenantSession = () => {
  localStorage.removeItem(TENANT_ACCESS_CODE_KEY);
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

const hasExplicitAuthHeaders = (config: any): boolean => {
  const headers = config?.headers;
  if (!headers) {
    return false;
  }
  return Boolean(headers['Authorization'] || headers['X-API-Key']);
};

api.interceptors.request.use((config) => {
  const url = config.url || '';
  if (url === '/auth/login') {
    return config;
  }

  if (hasExplicitAuthHeaders(config)) {
    return config;
  }

  const adminToken = localStorage.getItem(ADMIN_TOKEN_KEY);
  const tenantCode = localStorage.getItem(TENANT_ACCESS_CODE_KEY);
  const predictKey = localStorage.getItem(PREDICT_AUTH_KEY);
  const activeMode = getActiveMode();

  if (url === '/predict') {
    if (tenantCode) {
      setBearer(config, tenantCode);
      return config;
    }
    if (predictKey) {
      setRawAuthorization(config, predictKey);
      return config;
    }
    if (adminToken) {
      setBearer(config, adminToken);
    }
    return config;
  }

  if (url.startsWith('/admin/')) {
    setBearer(config, adminToken);
    return config;
  }

  if (url.startsWith('/tenant/') || url.startsWith('/v1/')) {
    setBearer(config, tenantCode);
    return config;
  }

  if (activeMode === 'tenant') {
    setBearer(config, tenantCode);
  } else {
    setBearer(config, adminToken);
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || '';
    if (error.response?.status === 401 && !url.includes('/auth/login')) {
      if (url.startsWith('/admin/')) {
        clearAdminSession();
      } else if (url.startsWith('/tenant/') || url.startsWith('/v1/') || url === '/predict') {
        clearTenantSession();
      } else {
        clearAdminSession();
        clearTenantSession();
      }
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
}

export interface RouteSyncMeta {
  status?: string;
  last_synced_at?: string | null;
  manual_overrides?: string[];
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

export const getRoutes = () => api.get<RouteConfig[]>('/tenant/routes');
export const searchRoutes = (query: string = '') =>
  api.get<RouteConfig[]>('/tenant/routes/search', { params: { q: query } });
export const createRoute = (data: RouteConfig) => api.post<RouteConfig>('/tenant/routes', data);
export const updateRoute = (id: number, data: Partial<RouteConfig>) =>
  api.put<RouteConfig>(`/tenant/routes/${id}`, data);
export const deleteRoute = (id: number) => api.delete<{ message: string }>(`/tenant/routes/${id}`);
export const generateUtterances = (data: GenerateUtterancesRequest) =>
  api.post<RouteConfig>('/tenant/routes/generate-utterances', data);
export const importRouteFromSkill = (data: ImportSkillRouteRequest) =>
  api.post<SkillRouteDraft>('/tenant/routes/import-skill', data, { timeout: 300000 });

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
  api.post<ImportRoutesResponse>('/tenant/routes/import', data);

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
  api.get<DiagnosticResult[]>('/tenant/diagnostics/overlap', { params: { refresh } });
export const getRouteOverlap = (routeId: number) =>
  api.get<DiagnosticResult>(`/tenant/diagnostics/overlap/${routeId}`);
export const getRepairSuggestions = (
  sourceRouteId: number,
  targetRouteId: number,
  includeNegativeSamples: boolean = false
) =>
  api.post<RepairSuggestion>(
    '/tenant/diagnostics/repair',
    { source_route_id: sourceRouteId, target_route_id: targetRouteId, include_negative_samples: includeNegativeSamples },
    { timeout: 300000 }
  );
export const applyRepair = (routeId: number, utterances: string[]) =>
  api.post<{ success: boolean }>('/tenant/diagnostics/apply-repair', { route_id: routeId, utterances });
export const syncRoutes = (routeIds: number[]) =>
  api.post<{ message: string; results: any[] }>('/tenant/reindex/sync-route', { route_ids: routeIds });

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
  api.get<UmapResponse>('/tenant/diagnostics/umap', { params });

export interface ReindexResponse {
  message: string;
  mode: string;
  routes_count: number;
  total_points: number;
}

export const reindex = (forceFull: boolean = false) =>
  api.post<ReindexResponse>('/tenant/reindex', { force_full: forceFull });

export const predict = (text: string) => api.post<PredictResult[]>('/predict', { text });

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

export interface TenantSettings extends SharedLlmSettings {
  EMBEDDING_SERVICE_URL: string;
  EMBEDDING_MODEL_NAME?: string;
  EMBEDDING_DEVICE?: string;

  BATCH_SIZE?: number;
  DEFAULT_ROUTE_ID?: number;
  DEFAULT_ROUTE_NAME?: string;
  DEFAULT_ROUTE_KEY?: string;
}

export interface SystemSettings extends SharedLlmSettings {
  QDRANT_URL?: string;
  QDRANT_COLLECTION?: string;
  QDRANT_API_KEY?: string | null;

  EMBEDDING_SERVICE_URL: string;
  EMBEDDING_MODEL_NAME?: string;
  EMBEDDING_DEVICE?: string;

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

export const getSettings = () => api.get<TenantSettings>('/tenant/settings');
export const updateSettings = (data: Partial<TenantSettings>) =>
  api.post<{ message: string; settings: TenantSettings }>('/tenant/settings', data);
export const getSystemSettings = () => api.get<SystemSettings>('/settings');
export const updateSystemSettings = (data: Partial<SystemSettings>) =>
  api.post<{ message: string; settings: SystemSettings }>('/settings', data);

export interface AddNegativeSamplesRequest {
  negative_samples: string[];
  negative_threshold?: number;
}

export const addNegativeSamples = (routeId: number, data: AddNegativeSamplesRequest) =>
  api.post<{ message: string; route_id: number; total_negative_samples: number }>(
    `/tenant/routes/${routeId}/negative-samples`,
    data
  );

export interface TenantAccessCode {
  code_id: string;
  label: string;
  status: string;
  created_at: string;
  last_used_at?: string | null;
  access_code?: string;
}

export interface SkillSourceRecord {
  source_id: string;
  path?: string;
  source_label: string;
  client_path_hint?: string | null;
  enabled: boolean;
  sync_mode: 'scan' | 'apply';
  last_scanned_at?: string | null;
}

export interface TenantRecord {
  tenant_id: string;
  name: string;
  status: string;
  qdrant_collection: string;
  access_codes: TenantAccessCode[];
  skill_sources: SkillSourceRecord[];
}

export interface TenantListResponse {
  items: TenantRecord[];
}

export interface TenantCreateRequest {
  tenant_id: string;
  name: string;
  qdrant_collection?: string;
  access_code_label?: string;
  access_code?: string;
}

export interface TenantCreateResponse {
  tenant: TenantRecord;
  access_code: TenantAccessCode;
}

export const listTenants = () => api.get<TenantListResponse>('/admin/tenants');
export const createTenant = (data: TenantCreateRequest) => api.post<TenantCreateResponse>('/admin/tenants', data);
export const createAccessCode = (tenantId: string, label: string, access_code?: string) =>
  api.post<TenantCreateResponse>(`/admin/tenants/${tenantId}/access-codes`, { label, access_code });
export const rotateAccessCode = (tenantId: string, codeId: string) =>
  api.post<TenantCreateResponse>(`/admin/tenants/${tenantId}/access-codes/${codeId}/rotate`);
export const disableAccessCode = (tenantId: string, codeId: string) =>
  api.post<TenantCreateResponse>(`/admin/tenants/${tenantId}/access-codes/${codeId}/disable`);

export interface SkillSourceResponse {
  items: SkillSourceRecord[];
}

export interface SkillSourceCreateRequest {
  path?: string;
  source_label?: string;
  client_path_hint?: string;
  sync_mode?: 'scan' | 'apply';
  enabled?: boolean;
}

export interface UploadedSkillPayload {
  relative_path: string;
  content: string;
}

export interface SkillSourceScanRequest {
  source_id?: string;
  source_label?: string;
  client_path_hint?: string;
  sync_mode?: 'scan' | 'apply';
  enabled?: boolean;
  skills: UploadedSkillPayload[];
}

export const listSkillSources = () => api.get<SkillSourceResponse>('/tenant/skill-sources');
export const createSkillSource = (data: SkillSourceCreateRequest) =>
  api.post<{ item: SkillSourceRecord }>('/tenant/skill-sources', data);
export const scanSkillSources = (data: SkillSourceScanRequest) => api.post('/tenant/skill-sources/scan', data);

export interface SkillDraftRecord {
  draft_file: string;
  skill_path: string;
  status: string;
  last_scanned_at?: string | null;
  route_id?: number | null;
  skill_hash?: string | null;
  json_hash?: string | null;
}

export interface SkillDraftListResponse {
  items: SkillDraftRecord[];
}

export const listSkillDrafts = () => api.get<SkillDraftListResponse>('/tenant/skill-drafts');
export const applySkillDraft = (draft_file: string) =>
  api.post('/tenant/skill-drafts/apply', { draft_file });

export default api;
