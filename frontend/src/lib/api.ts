// frontend/src/lib/api.ts
import axios, { AxiosRequestConfig } from "axios";

/**
 * Versão compatível e estendida do seu api.ts original.
 * - Mantém getBaseUrl() e comportamento atual
 * - Adiciona helpers apiGet/apiPost/apiPut/apiPatch/apiDelete e upload()
 * - Adiciona flag ENABLE_LOG para ativar logs de request/response (false por padrão)
 */

// Ative para debug de requests/responses
const ENABLE_LOG = false;

function getBaseUrl(): string {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  return "http://localhost:8000/api/v1";
}

const api = axios.create({
  baseURL: getBaseUrl(),
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Helper para aplicar/remover Authorization de forma explícita (use no login/logout)
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    try {
      if (typeof window !== "undefined") localStorage.setItem("token", token);
    } catch (error) {
      console.error("Erro ao salvar token:", error);
    }
  } else {
    delete api.defaults.headers.common["Authorization"];
    try {
      if (typeof window !== "undefined") localStorage.removeItem("token");
    } catch (error) {
      console.error("Erro ao remover token:", error);
    }
  }
}

// Request interceptor — adiciona token automaticamente
api.interceptors.request.use(
  (config) => {
    try {
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("token");
        if (token && !config.headers?.["Authorization"]) {
          config.headers = config.headers || {};
          config.headers["Authorization"] = `Bearer ${token}`;
        }
      }
    } catch (err) {
      console.warn("[api] request interceptor error", err);
    }

    if (ENABLE_LOG) {
      try {
        console.debug("[api] request:", config.method?.toUpperCase(), config.url, config.params ?? config.data ?? {});
      } catch {}
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: captura 401 e permite callback externo para logout/redirecionamento
let onUnauthorized: (() => void) | null = null;
export function registerOnUnauthorized(cb: () => void) {
  onUnauthorized = cb;
}

api.interceptors.response.use(
  (resp) => {
    if (ENABLE_LOG) {
      try {
        console.debug("[api] response:", resp.status, resp.config.url, resp.data);
      } catch {}
    }
    return resp;
  },
  (error) => {
    const status = error?.response?.status;
    if (ENABLE_LOG) {
      try {
        console.debug("[api] response error:", status, error?.config?.url, error?.response?.data);
      } catch {}
    }
    if (status === 401 || status === 403) {
      console.warn("[api] Unauthorized (401/403) - executando callback");
      if (onUnauthorized) {
        onUnauthorized();
      }
    }
    return Promise.reject(error);
  }
);

// --- Small helpers that return resp.data directly (optional use) ---
export async function apiGet<T = any>(path: string, config?: AxiosRequestConfig) {
  const resp = await api.get<T>(path, config);
  return resp.data;
}
export async function apiPost<T = any>(path: string, data?: any, config?: AxiosRequestConfig) {
  // if sending FormData, ensure Content-Type is not forced
  if (data instanceof FormData && config?.headers) {
    delete (config.headers as any)["Content-Type"];
  }
  const resp = await api.post<T>(path, data, config);
  return resp.data;
}
export async function apiPut<T = any>(path: string, data?: any, config?: AxiosRequestConfig) {
  if (data instanceof FormData && config?.headers) delete (config.headers as any)["Content-Type"];
  const resp = await api.put<T>(path, data, config);
  return resp.data;
}
export async function apiPatch<T = any>(path: string, data?: any, config?: AxiosRequestConfig) {
  if (data instanceof FormData && config?.headers) delete (config.headers as any)["Content-Type"];
  const resp = await api.patch<T>(path, data, config);
  return resp.data;
}
export async function apiDelete<T = any>(path: string, config?: AxiosRequestConfig) {
  const resp = await api.delete<T>(path, config);
  return resp.data;
}

// upload helper: builds FormData and posts without forcing Content-Type
export async function upload(path: string, payload: Record<string, any>, config?: AxiosRequestConfig) {
  const fd = new FormData();
  Object.entries(payload || {}).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    if (Array.isArray(v)) {
      v.forEach((item) => fd.append(k, item));
    } else {
      fd.append(k, v);
    }
  });
  // don't set Content-Type; let browser/axios handle boundary
  const resp = await api.post(path, fd, {
    ...config,
    headers: { ...(config?.headers || {}) },
  });
  return resp.data;
}

export default api;