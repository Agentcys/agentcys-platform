const DEFAULT_API_URL = 'http://localhost:8000';

export type ApiCredential = {
  id: string;
  name?: string;
};

export type ApiProject = {
  id: string;
  name?: string;
};

export type ApiBlueprint = {
  id: string;
  name?: string;
  input_schema?: Record<string, unknown>;
};

export type ApiDeployment = {
  id: string;
  name?: string;
  status?: string;
  run_status?: string;
  blueprint_id?: string;
  project_id?: string;
  created_at?: string;
  updated_at?: string;
};

function baseUrl(): string {
  return import.meta.env.VITE_API_URL || DEFAULT_API_URL;
}

function parseJsonOrThrow(raw: string): unknown {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new Error('API returned invalid JSON');
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = localStorage.getItem('apiKey') || '';
  const headers = new Headers(init?.headers || {});
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('X-API-Key', apiKey);

  const response = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`Request failed (${response.status}): ${raw || response.statusText}`);
  }

  const raw = await response.text();
  return parseJsonOrThrow(raw) as T;
}

export const apiClient = {
  listCredentials: () => request<ApiCredential[]>('/credentials'),
  uploadCredential: (payload: Record<string, unknown>) =>
    request<ApiCredential>('/credentials', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  linkProject: (payload: Record<string, unknown>) =>
    request<ApiProject>('/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listProjects: () => request<ApiProject[]>('/projects'),
  listBlueprints: () => request<ApiBlueprint[]>('/blueprints'),
  getBlueprint: (blueprintId: string) => request<ApiBlueprint>(`/blueprints/${blueprintId}`),
  listDeployments: () => request<ApiDeployment[]>('/deployments'),
  getDeployment: (deploymentId: string) => request<ApiDeployment>(`/deployments/${deploymentId}`),
  createDeployment: (payload: Record<string, unknown>) =>
    request<ApiDeployment>('/deployments', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  destroyDeployment: (deploymentId: string) =>
    request<void>(`/deployments/${deploymentId}`, {
      method: 'DELETE',
    }),
};
