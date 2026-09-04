import axios from 'axios';

const api = axios.create({ baseURL: '/api' });
const AUTH_CODE = 'telestar';

api.interceptors.request.use((config) => {
  config.headers.Authorization = `Bearer ${AUTH_CODE}`;
  return config;
});

export interface Agent {
  id: number;
  title: string;
  text: string;
  utterances: string[];
  negative_samples: string[];
  score_threshold: number;
  negative_threshold: number;
  details: Record<string, unknown>;
  source_type: 'upstream' | 'local';
  upstream_id: number | null;
  upstream_present: boolean | null;
  manual_overrides: string[];
  lifecycle_status: 'active' | 'inactive' | 'deleted';
  source_snapshot: Record<string, unknown>;
  updated_at: string | null;
  comparison: AgentComparisonSummary;
}

export type AgentComparisonStatus = 'same' | 'local_modified' | 'locked_equal' | 'upstream_missing' | 'local_only' | 'snapshot_unknown';
export type ComparableAgentField = 'title' | 'text' | 'utterances' | 'negative_samples';
export interface AgentComparisonSummary {
  status: AgentComparisonStatus;
  diff_fields: ComparableAgentField[];
  diff_count: number;
  override_fields: string[];
  locked_equal_fields: ComparableAgentField[];
}
export interface ScalarFieldDiff {
  kind: 'scalar'; changed: boolean; overridden: boolean;
  local_value: string; upstream_value: string;
}
export interface CorpusFieldDiff {
  kind: 'corpus'; changed: boolean; overridden: boolean;
  local_count: number; upstream_count: number;
  added: string[]; removed: string[]; unchanged_count: number;
}
export interface AgentDiffDetail {
  agent_id: number;
  comparison: AgentComparisonSummary;
  compared_at: string | null;
  fields: Partial<Record<ComparableAgentField, ScalarFieldDiff | CorpusFieldDiff>>;
}

export interface RouteData {
  matched: boolean;
  agents: Array<{
    agent: { id: number; title: string };
    score: number;
  }>;
  text: string | null;
}

export interface RouteResult {
  success: boolean;
  data: RouteData | null;
  error: { code: string; message: string; detail: string | null } | null;
}

export interface SyncStatus {
  agents_count: number;
  active_agents_count: number;
  pending_changes: number;
  collection: string;
  expected_points: number;
  points_count: number;
  synced: boolean;
  last_pull_at: string | null;
  last_vector_sync_at: string | null;
}

export interface Settings {
  QDRANT_URL: string;
  QDRANT_COLLECTION: string;
  QDRANT_API_KEY: string | null;
  EMBEDDING_SERVICE_URL: string;
  EMBEDDING_MODEL_NAME: string;
  BATCH_SIZE: number;
  LLM_PROVIDER: 'deepseek' | 'openrouter' | 'doubao' | 'qwen' | 'gemini';
  LLM_API_KEY: string | null;
  LLM_BASE_URL: string | null;
  LLM_MODEL: string | null;
  LLM_TEMPERATURE: number;
  UTTERANCE_GENERATION_PROMPT: string;
  NEGATIVE_SAMPLE_GENERATION_PROMPT: string;
  AGENT_REPAIR_PROMPT: string;
  REGION_THRESHOLD_SIGNIFICANT: number;
  INSTANCE_THRESHOLD_AMBIGUOUS: number;
}

export interface ServiceHealth {
  status: 'ok' | 'degraded';
  services: Record<'embedding' | 'qdrant', {
    healthy: boolean;
    status_code: number | null;
    latency_ms: number;
    message: string;
  }>;
}

export interface CollectionOption {
  name: string;
  kind: 'collection' | 'alias';
  target: string | null;
}

export interface CollectionsResponse {
  current: string;
  collections: CollectionOption[];
}

export interface CollectionRestoreResult {
  collection: string;
  restored_agents: number;
  positive_texts: number;
  negative_texts: number;
  points_count: number;
  skipped_points: number;
}

export const getAgents = () => api.get<Agent[]>('/agents');
export const getAgentDiff = (id: number) => api.get<AgentDiffDetail>(`/agents/${id}/diff`);
export const createAgent = (data: Partial<Agent>) => api.post<Agent>('/agents', data);
export const updateAgent = (id: number, data: Partial<Agent>) => api.patch<Agent>(`/agents/${id}`, data);
export const deleteAgent = (id: number) => api.delete<Agent>(`/agents/${id}`);
export const restoreAgentFields = (id: number, fields: string[]) => api.post<Agent>(`/agents/${id}/restore-fields`, { fields });
export const recommendCorpus = (id: number, data: { polarity: 'positive' | 'negative'; count: number; title?: string; text?: string; utterances?: string[]; negative_samples?: string[] }) =>
  api.post<{ items: string[]; polarity: string }>(`/agents/${id}/recommendations`, data, { timeout: 120000 });
export const pullAgents = () => api.post('/agents/pull', {}, { timeout: 120000 });
export const syncVectors = (mode: 'incremental' | 'full' = 'incremental', agent_ids?: number[]) => api.post('/vectors/sync', { mode, agent_ids }, { timeout: 600000 });
export const getSyncStatus = () => api.get<SyncStatus>('/sync/status');
export const route = (query: string) => api.post<RouteResult>('/route', { query });
export const getSettings = () => api.get<Settings>('/settings');
export const saveSettings = (settings: Partial<Settings>) => api.post<{ message: string; settings: Settings }>('/settings', settings);
export const getServiceHealth = () => api.get<ServiceHealth>('/health/services');
export const getCollections = () => api.get<CollectionsResponse>('/collections');
export const createCollection = (name: string) => api.post<CollectionOption>('/collections', { name });
export const restoreCollection = (name: string) => api.post<CollectionRestoreResult>('/collections/restore', { name }, { timeout: 120000 });

export interface ConflictPoint { source_utterance: string; target_utterance: string; similarity: number; }
export interface RouteOverlap { target_route_id: number; target_route_name: string; region_similarity: number; instance_conflicts: ConflictPoint[]; total_conflicts: number; }
export interface DiagnosticResult { route_id: number; route_name: string; overlaps: RouteOverlap[]; }
export interface RepairSuggestion { route_id: number; route_name: string; new_utterances: string[]; negative_samples: string[]; conflicting_utterances: string[]; rationalization: string; }
export interface UmapPoint { x: number; y: number; route_id: number; route_name: string; utterance: string; }
export const getOverlaps = (refresh = false) => api.get<DiagnosticResult[]>('/diagnostics/overlap', { params: { refresh } });
export const getUmapPoints = () => api.get<{ points: UmapPoint[]; meta: Record<string, number> }>('/diagnostics/umap');
export const getRepairSuggestions = (source_route_id: number, target_route_id: number) => api.post<RepairSuggestion>('/diagnostics/repair', { source_route_id, target_route_id }, { timeout: 120000 });
export const applyRepair = (route_id: number, utterances: string[], negative_samples?: string[]) => api.post<Agent>('/diagnostics/apply-repair', { route_id, utterances, negative_samples });
export const mergeAgents = (source_agent_id: number, target_agent_id: number, title: string, text = '') => api.post<Agent>('/diagnostics/merge', { source_agent_id, target_agent_id, title, text });

export default api;
