import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use((config) => {
  const key = localStorage.getItem('api_key');
  if (key && config.url !== '/auth/login') {
    config.headers.Authorization = `Bearer ${key}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && error.config?.url !== '/auth/login') {
      localStorage.removeItem('api_key');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export interface Agent {
  id: number;
  title: string;
  text: string;
  utterances: string[];
  negative_samples: string[];
  score_threshold: number;
  negative_threshold: number;
  details: Record<string, unknown>;
}

export interface RouteData {
  matched: boolean;
  agent: { id: number; title: string } | null;
  score: number | null;
  text: string | null;
}

export interface RouteResult {
  success: boolean;
  data: RouteData | null;
  error: { code: string; message: string; detail: string | null } | null;
}

export interface SyncStatus {
  agents_count: number;
  collection: string;
  expected_points: number;
  points_count: number;
  synced: boolean;
}

export const login = (username: string, password: string) =>
  api.post<{ api_key: string }>('/auth/login', { username, password });
export const getAgents = () => api.get<Agent[]>('/agents');
export const updateAgentThresholds = (
  id: number,
  score_threshold: number,
  negative_threshold: number,
) => api.patch<Agent>(`/agents/${id}/thresholds`, { score_threshold, negative_threshold });
export const syncAgents = () => api.post('/sync');
export const getSyncStatus = () => api.get<SyncStatus>('/sync/status');
export const route = (query: string) => api.post<RouteResult>('/route', { query });
export const getSettings = () => api.get<{ QDRANT_COLLECTION: string }>('/settings');
export const saveSettings = (QDRANT_COLLECTION: string) =>
  api.post<{ QDRANT_COLLECTION: string }>('/settings', { QDRANT_COLLECTION });

export default api;
