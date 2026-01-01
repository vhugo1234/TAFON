// frontend/src/lib/api.ts

import axios from "axios";

// ------------------------------------------------------------------
// CORREÇÃO DEFINITIVA: Declarar 'process' para satisfazer o TypeScript
// ------------------------------------------------------------------
declare const process: {
  env: {
    REACT_APP_API_URL?: string;
    NEXT_PUBLIC_API_URL?: string;
    // Adicione outras variáveis process.env que você use aqui, se necessário.
  };
};
// ------------------------------------------------------------------

/**
 * Resolve a baseURL a partir das variáveis de ambiente mais comuns:
 * - Vite: import.meta.env.VITE_API_URL
 * - CRA: process.env.REACT_APP_API_URL
 * - Next: process.env.NEXT_PUBLIC_API_URL
 * Fallback: "/api/v1" (útil em dev com proxy)
 */
function getBaseUrl(): string {
  // 1. Prioridade: Variável de ambiente do Vite
  if (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) {
    return (import.meta as any).env.VITE_API_URL;
  }
  
  // 2. Fallback: Tenta usar a variável global 'process.env' (o TS agora a reconhece via 'declare const')
  //    Não é mais necessário usar 'typeof process !== "undefined"' ou 'as any' para process.env, 
  //    pois o TS já sabe que ele existe e qual a sua estrutura.
  if (process.env.REACT_APP_API_URL) return process.env.REACT_APP_API_URL;
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;

  // 3. Fallback: URL padrão
  return "/api/v1";
}

const api = axios.create({
  baseURL: getBaseUrl(),
  timeout: 15000,
});

// Helper para aplicar/remover Authorization de forma explícita (use no login/logout)
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    try {
      if (typeof window !== "undefined") localStorage.setItem("token", token);
    } catch {}
  } else {
    delete api.defaults.headers.common["Authorization"];
    try {
      if (typeof window !== "undefined") localStorage.removeItem("token");
    } catch {}
  }
}

// Request interceptor — fallback para casos onde o header ainda não foi aplicado
api.interceptors.request.use(
  (config) => {
    try {
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("token");
        // DEBUG LOG: confirma token + URL - remove após debug
        console.debug("[api] request ->", config.method, config.url, "hasLocalToken?", !!token);
        if (token) {
          config.headers = config.headers || {};
          if (!config.headers["Authorization"]) {
            config.headers["Authorization"] = `Bearer ${token}`;
          }
        }
      }
    } catch (err) {
      // não interrompe a request
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
      if (onUnauthorized) {
        onUnauthorized();
      }
    }
    return Promise.reject(error);
  }
);

export default api;