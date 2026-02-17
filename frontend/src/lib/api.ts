// frontend/src/lib/api.ts

import axios from "axios";

/**
 * Resolve a baseURL a partir das variÃ¡veis de ambiente do Vite
 * - Vite: import.meta.env.VITE_API_URL
 * Fallback: "http://localhost:8000" (backend local)
 */
function getBaseUrl(): string {
  // Usar variÃ¡vel de ambiente do Vite
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  
  // Fallback: backend local COM /api/v1
  return "http://localhost:8000/api/v1";
}

const api = axios.create({
  baseURL: getBaseUrl(),
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper para aplicar/remover Authorization de forma explÃ­cita (use no login/logout)
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    try {
      if (typeof window !== "undefined") localStorage.setItem("token", token);
    } catch (error) {
      console.error('Erro ao salvar token:', error);
    }
  } else {
    delete api.defaults.headers.common["Authorization"];
    try {
      if (typeof window !== "undefined") localStorage.removeItem("token");
    } catch (error) {
      console.error('Erro ao remover token:', error);
    }
  }
}

// Request interceptor â€” adiciona token automaticamente
api.interceptors.request.use(
  (config) => {
    try {
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("token");
        if (token && !config.headers["Authorization"]) {
          config.headers["Authorization"] = `Bearer ${token}`;
        }
      }
    } catch (err) {
      console.warn("[api] request interceptor error", err);
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
  (resp) => resp,
  (error) => {
    const status = error?.response?.status;
    if (status === 401 || status === 403) {
      console.warn('[api] Unauthorized (401/403) - executando callback');
      if (onUnauthorized) {
        onUnauthorized();
      }
    }
    return Promise.reject(error);
  }
);

export default api;

