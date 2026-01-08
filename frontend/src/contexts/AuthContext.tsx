import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import api, { setAuthToken, registerOnUnauthorized } from "../lib/api";

interface AuthResponse {
  access_token: string;
  token_type: string;
  schema_name: string | null;
  is_superuser: boolean;
  empresa?: string;
  logoUrl?: string;
  nome?: string;
  role?: string;
  is_admin?: boolean;
  email?: string;
}

interface LoginResult {
  success: boolean;
  error?: string;
}

export interface AuthUser {
  nome?: string;
  username?: string;
  empresa?: string;
  logoUrl?: string;
  email?: string;
  id?: number;
  role?: string;
  is_admin?: boolean;
  is_superuser?: boolean;
  schemaName?: string | null;
}

export interface AuthContextType {
  token: string | null;
  schemaName: string | null;
  loading: boolean;
  isSuperuser: boolean;
  login: (email: string, password: string, recaptchaToken?: string) => Promise<LoginResult>;
  logout: () => void;
  isAuthenticated: boolean;
  user: AuthUser | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};

function decodeJwtPayload(token: string): any | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = parts[1];
    const pad = payload.length % 4;
    const padded = payload + (pad ? "=".repeat(4 - pad) : "");
    const decoded = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload) return true;
  if (!payload.exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp <= now;
}

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [token, setTokenState] = useState<string | null>(null);
  const [schemaName, setSchemaName] = useState<string | null>(null);
  const [isSuperuser, setIsSuperuser] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    registerOnUnauthorized(() => {
      logout();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    try {
      // Read stored values (treat absent schema_name as null)
      const storedToken = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const storedSchemaNameRaw = typeof window !== "undefined" ? localStorage.getItem("schema_name") : null;
      const storedSchemaName = storedSchemaNameRaw && storedSchemaNameRaw !== "" ? storedSchemaNameRaw : null;
      const storedIsSuper = (typeof window !== "undefined" ? localStorage.getItem("is_superuser") : null) === "true";
      const storedUser = typeof window !== "undefined" ? localStorage.getItem("user") : null;

      // IMPORTANT: do NOT require storedSchemaName to be present.
      // A central/superuser token may have schema_name === null and must still be accepted.
      if (storedToken && !isTokenExpired(storedToken)) {
        setTokenState(storedToken);

        // Apply the token to axios immediately so any requests during init use it.
        setAuthToken(storedToken);

        // Restore optional schema name and superuser flag
        setSchemaName(storedSchemaName);
        setIsSuperuser(storedIsSuper);

        // Restore user info if present; otherwise decode from token
        if (storedUser) {
          try {
            setUser(JSON.parse(storedUser));
          } catch {
            // fallback to decode token
            const payload = decodeJwtPayload(storedToken);
            if (payload) {
              const userObj: AuthUser = {
                nome: payload.nome,
                username: payload.username,
                empresa: payload.empresa,
                logoUrl: payload.logoUrl,
                email: payload.email,
                id: payload.user_id || payload.id,
                role: payload.role,
                is_admin: payload.is_admin,
                is_superuser: payload.is_superuser,
              };
              setUser(userObj);
              localStorage.setItem("user", JSON.stringify(userObj));
            }
          }
        } else {
          const payload = decodeJwtPayload(storedToken);
          if (payload) {
            const userObj: AuthUser = {
              nome: payload.nome,
              username: payload.username,
              empresa: payload.empresa,
              logoUrl: payload.logoUrl,
              email: payload.email,
              id: payload.user_id || payload.id,
              role: payload.role,
              is_admin: payload.is_admin,
              is_superuser: payload.is_superuser,
            };
            setUser(userObj);
            if (typeof window !== "undefined") localStorage.setItem("user", JSON.stringify(userObj));
          }
        }
      } else {
        // No valid token: ensure axios and storage are clean
        setAuthToken(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("token");
          localStorage.removeItem("schema_name");
          localStorage.removeItem("is_superuser");
          localStorage.removeItem("user");
        }
        setTokenState(null);
        setSchemaName(null);
        setIsSuperuser(false);
        setUser(null);
      }
    } catch (err) {
      console.error("Erro ao inicializar auth:", err);
      setAuthToken(null);
      setTokenState(null);
      setSchemaName(null);
      setIsSuperuser(false);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const login = async (
    email: string,
    password: string,
    recaptchaToken?: string
  ): Promise<LoginResult> => {
    setLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      const baseURL = (api && (api.defaults as any)?.baseURL) || "";
      const url = baseURL.includes("/api/v1") ? "/auth/login" : "/api/v1/auth/login"

      const response = await api.post<AuthResponse>(url, formData.toString(), {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          ...(recaptchaToken ? { "X-Recaptcha-Token": recaptchaToken } : {}),
        },
      });

      const {
        access_token,
        schema_name,
        is_superuser,
        empresa,
        logoUrl,
        nome,
        role,
        is_admin,
        email: uemail,
      } = response.data;

      if (!access_token || isTokenExpired(access_token)) {
        setLoading(false);
        return { success: false, error: "Token invÃ¡lido/expirado recebido." };
      }

      setTokenState(access_token);
      setSchemaName(schema_name ?? null);
      setIsSuperuser(is_superuser);

      if (typeof window !== "undefined") {
        localStorage.setItem("token", access_token);

        // store schema_name only if present (avoid empty string)
        if (schema_name) {
          localStorage.setItem("schema_name", schema_name);
        } else {
          localStorage.removeItem("schema_name");
        }

        localStorage.setItem("is_superuser", is_superuser ? "true" : "false");
      }

      // Apply token to axios immediately
      setAuthToken(access_token);

      const payload = decodeJwtPayload(access_token);
      const userObj: AuthUser = {
        nome: payload?.nome || nome,
        username: payload?.username,
        empresa: payload?.empresa || empresa,
        logoUrl: payload?.logoUrl || logoUrl,
        email: payload?.email || uemail,
        id: payload?.user_id || payload?.id,
        role: payload?.role || role,
        is_admin: payload?.is_admin ?? is_admin,
        is_superuser: payload?.is_superuser ?? is_superuser,
      };

      setUser(userObj);
      if (typeof window !== "undefined") localStorage.setItem("user", JSON.stringify(userObj));

      setLoading(false);
      return { success: true };
    } catch (error: any) {
      console.error("Erro no login:", error);
      const errorDetail = error.response?.data?.detail || error.message || "Erro desconhecido no servidor";
      setLoading(false);
      return { success: false, error: errorDetail };
    }
  };

  const logout = () => {
    setTokenState(null);
    setSchemaName(null);
    setIsSuperuser(false);
    setUser(null);
    setAuthToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("schema_name");
      localStorage.removeItem("is_superuser");
      localStorage.removeItem("user");
    }
  };

  // auto-logout quando token expirar durante a sessÃ£o
  useEffect(() => {
    if (!token) return;
    const payload = decodeJwtPayload(token);
    if (!payload || !payload.exp) return;
    const now = Math.floor(Date.now() / 1000);
    const timeout = payload.exp - now;
    if (timeout <= 0) {
      logout();
      return;
    }
    const timer = setTimeout(() => {
      logout();
    }, timeout * 1000);
    return () => clearTimeout(timer);
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        token,
        schemaName,
        loading,
        isSuperuser,
        login,
        logout,
        isAuthenticated: !!token && !isTokenExpired(token),
        user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

