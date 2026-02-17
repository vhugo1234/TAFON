import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import api, { setAuthToken, registerOnUnauthorized } from "../lib/api";
import { normalizeRoles } from "../utils/roles";
import { useNavigate } from "react-router-dom";

interface AuthResponse {
  access_token: string;
  token_type: string;
  schema_name: string | null;
  is_superuser: boolean;
  empresa?: string;
  logoUrl?: string;
  nome?: string;
  role?: string;
  roles?: string[];
  role_id?: number | string;
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
  roles?: string[];
  role_id?: number | string;
  is_admin?: boolean;
  is_superuser?: boolean;
  schemaName?: string | null;
  assigned_exercise_id?: number | null;
  assigned_event_id?: number | null;
  evaluator_limited_view?: boolean;
  assigned_exercises?: any[];
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
  hasRole: (role: string) => boolean;
  hasAnyRole: (roles: string[]) => boolean;
  hasAllRoles: (roles: string[]) => boolean;
  refreshUser: () => Promise<void>;
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
  const navigate = useNavigate();
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

  const fetchUserProfile = async (currentToken?: string): Promise<AuthUser | null> => {
    try {
      const effectiveToken = currentToken || token;
      if (!effectiveToken) return null;
      setAuthToken(effectiveToken);

      const candidateUrls = ["/auth/me", "/api/v1/auth/me"];
      for (const candidate of candidateUrls) {
        try {
          const res = await api.get(candidate, {
            headers: { Authorization: `Bearer ${effectiveToken}` },
          });
          const data = res.data || {};
          const userObj: AuthUser = {
            nome: data.nome ?? data.name,
            username: data.username,
            empresa: data.empresa,
            logoUrl: data.logoUrl,
            email: data.email,
            id: data.id ?? data.user_id,
            role: data.role,
            roles: Array.isArray(data.roles) ? data.roles : data.role ? [data.role] : undefined,
            role_id: data.role_id ?? undefined,
            is_admin: data.is_admin,
            is_superuser: data.is_superuser,
          };

          const providedRoles = Array.isArray(data.roles)
            ? data.roles
            : (data.role_id !== undefined && data.role_id !== null)
            ? [String(data.role_id)]
            : data.role
            ? [data.role]
            : [];

          userObj.roles = normalizeRoles(providedRoles);
          setUser(userObj);
          if (typeof window !== "undefined") localStorage.setItem("user", JSON.stringify(userObj));
          return userObj;
        } catch (err: any) {
          const status = err?.response?.status;
          if (status === 404) continue;
          throw err;
        }
      }

      const payload = decodeJwtPayload(effectiveToken);
      if (!payload) return null;
      const fallbackUser: AuthUser = {
        nome: payload.nome || payload.name,
        username: payload.username,
        empresa: payload.empresa,
        logoUrl: payload.logoUrl,
        email: payload.email,
        id: payload.user_id || payload.id,
        role: payload.role,
        roles: Array.isArray(payload.roles) ? payload.roles : payload.role ? [payload.role] : undefined,
        role_id: payload.role_id ?? undefined,
        is_admin: payload.is_admin,
        is_superuser: payload.is_superuser,
      };

      const providedPayloadRoles = Array.isArray(payload.roles)
        ? payload.roles
        : (payload.role_id !== undefined && payload.role_id !== null)
        ? [String(payload.role_id)]
        : payload.role
        ? [payload.role]
        : [];

      fallbackUser.roles = normalizeRoles(providedPayloadRoles);
      setUser(fallbackUser);
      if (typeof window !== "undefined") localStorage.setItem("user", JSON.stringify(fallbackUser));
      return fallbackUser;
    } catch (err) {
      const status = err?.response?.status;
      if (status && status !== 404) {
        console.error("Erro ao buscar /me:", err);
      }
      return null;
    }
  };

  // Robust evaluator redirect that tries several fallbacks and logs progress.
  const handleEvaluatorRedirect = async (userObj: AuthUser, effectiveToken: string): Promise<boolean> => {
    try {
      if (!userObj || !userObj.id) return false;

      const looksLikeEvaluator =
        (userObj.roles || []).some((r: string) => String(r).toUpperCase() === "AVALIADOR_EF") ||
        (userObj.role && String(userObj.role).toUpperCase() === "AVALIADOR_EF") ||
        (userObj.role_id !== undefined && Number(userObj.role_id) === 4);

      if (!looksLikeEvaluator) return false;

      // Ensure axios has token
      setAuthToken(effectiveToken);

      console.debug("[Auth] handleEvaluatorRedirect: start for user", userObj.id);

      // 1) Try to fetch assignments from backend
      let assigned: any[] = [];
      try {
        const res = await api.get(`/taf/evaluators/user/${userObj.id}`, {
          headers: { Authorization: `Bearer ${effectiveToken}` },
        });
        assigned = res.data?.exercises || res.data || [];
        console.debug("[Auth] /taf/evaluators/user response:", assigned);
      } catch (err) {
        console.warn("[Auth] /taf/evaluators/user failed:", err);
        assigned = [];
      }

      // 2) Enrich assignments with event_id when possible
      const enriched: Array<any> = [];
      for (const item of assigned) {
        let exerciseId = item?.exercise_id ?? item?.id ?? null;
        let eventId = item?.event_id ?? item?.eventId ?? null;

        if (exerciseId && !eventId) {
          try {
            const exRes = await api.get(`/taf/exercises/${exerciseId}`, {
              headers: { Authorization: `Bearer ${effectiveToken}` },
            });
            const exObj = exRes.data || {};
            eventId = exObj.event_id ?? exObj.eventId ?? null;
          } catch (err) {
            console.warn(`[Auth] Failed to fetch exercise ${exerciseId}:`, err);
          }
        }

        enriched.push({
          assignment_id: item.id ?? null,
          exercise_id: exerciseId ? Number(exerciseId) : null,
          event_id: eventId ? Number(eventId) : null,
          is_primary: !!item.is_primary,
          exercise_name: item.exercise_name ?? item.name ?? null,
        });
      }

      console.debug("[Auth] enriched assignments:", enriched);

      // Persist assignments and evaluator flag
      const updatedUser: AuthUser = {
        ...userObj,
        assigned_exercises: enriched,
        evaluator_limited_view: true,
        assigned_exercise_id: enriched[0]?.exercise_id ?? (userObj as any)?.assigned_exercise_id ?? null,
        assigned_event_id: enriched[0]?.event_id ?? (userObj as any)?.assigned_event_id ?? null,
      } as any;

      setUser(updatedUser);
      if (typeof window !== "undefined") localStorage.setItem("user", JSON.stringify(updatedUser));

      // 3) Redirect preference:
      // primary with event_id
      const primary = enriched.find(e => e.is_primary && e.event_id && e.exercise_id);
      if (primary) {
        const route = `/taf/events/${primary.event_id}/exercises/${primary.exercise_id}/field`;
        console.debug("[Auth] redirect -> primary field:", route);
        try { navigate(route, { replace: true }); } catch { window.location.replace(route); }
        return true;
      }

      // first with event_id
      const anyWithEvent = enriched.find(e => e.event_id && e.exercise_id);
      if (anyWithEvent) {
        const route = `/taf/events/${anyWithEvent.event_id}/exercises/${anyWithEvent.exercise_id}/field`;
        console.debug("[Auth] redirect -> first-with-event field:", route);
        try { navigate(route, { replace: true }); } catch { window.location.replace(route); }
        return true;
      }

      // fallback: token/localStorage assigned ids
      const tokenAssignedExercise = (userObj as any)?.assigned_exercise_id ?? (updatedUser as any)?.assigned_exercise_id;
      const tokenAssignedEvent = (userObj as any)?.assigned_event_id ?? (updatedUser as any)?.assigned_event_id;
      if (tokenAssignedExercise && tokenAssignedEvent) {
        const route = `/taf/events/${tokenAssignedEvent}/exercises/${tokenAssignedExercise}/field`;
        console.debug("[Auth] redirect -> fallback token field:", route);
        try { navigate(route, { replace: true }); } catch { window.location.replace(route); }
        return true;
      }

      // if we have at least one event_id, go to exercises list of first event
      const firstEventId = enriched.find(e => e.event_id)?.event_id ?? tokenAssignedEvent ?? null;
      if (firstEventId) {
        const listRoute = `/taf/events/${firstEventId}/exercises`;
        console.debug("[Auth] redirect -> exercises list:", listRoute);
        try { navigate(listRoute, { replace: true }); } catch { window.location.replace(listRoute); }
        return true;
      }

      console.debug("[Auth] handleEvaluatorRedirect: no redirect (no assignments with event_id)");
      return false;
    } catch (err) {
      console.error("Erro no handleEvaluatorRedirect:", err);
      return false;
    }
  };

  // helper: detecta se um user representa um avaliador EF
  const _isEvaluatorRole = (u: AuthUser | null | undefined): boolean => {
    if (!u) return false;
    const byRoles = Array.isArray(u.roles) && u.roles.some(r => String(r).toUpperCase() === "AVALIADOR_EF");
    const byRole = u.role && String(u.role).toUpperCase() === "AVALIADOR_EF";
    const byRoleId = u.role_id !== undefined && u.role_id !== null && Number(u.role_id) === 4;
    return byRoles || byRole || byRoleId;
  };

  useEffect(() => {
    try {
      const storedToken = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const storedSchemaNameRaw = typeof window !== "undefined" ? localStorage.getItem("schema_name") : null;
      const storedSchemaName = storedSchemaNameRaw && storedSchemaNameRaw !== "" ? storedSchemaNameRaw : null;
      const storedIsSuper = (typeof window !== "undefined" ? localStorage.getItem("is_superuser") : null) === "true";
      const storedUser = typeof window !== "undefined" ? localStorage.getItem("user") : null;

      if (storedToken && !isTokenExpired(storedToken)) {
        setTokenState(storedToken);
        setAuthToken(storedToken);
        setSchemaName(storedSchemaName);
        setIsSuperuser(storedIsSuper);

        if (storedUser) {
          try {
            const parsed = JSON.parse(storedUser);
            if (parsed && parsed.role && !parsed.roles) {
              parsed.roles = Array.isArray(parsed.role) ? parsed.role : [parsed.role];
            }
            parsed.roles = normalizeRoles(parsed.roles ?? parsed.role ?? (parsed.role_id !== undefined ? [String(parsed.role_id)] : []));
            // ensure evaluator flag persisted is also normalized
            if (_isEvaluatorRole(parsed)) parsed.evaluator_limited_view = true;
            setUser(parsed);
            fetchUserProfile(storedToken).catch(() => {});
          } catch {
            fetchUserProfile(storedToken).catch(() => {});
          }
        } else {
          fetchUserProfile(storedToken).catch(() => {});
        }
      } else {
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
      const url = baseURL.includes("/api/v1") ? "/auth/login" : "/api/v1/auth/login";

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
        roles,
        role_id,
        is_admin,
        email: uemail,
      } = response.data;

      if (!access_token || isTokenExpired(access_token)) {
        setLoading(false);
        return { success: false, error: "Token inválido/expirado recebido." };
      }

      setTokenState(access_token);
      setSchemaName(schema_name ?? null);
      setIsSuperuser(is_superuser);

      if (typeof window !== "undefined") {
        localStorage.setItem("token", access_token);
        if (schema_name) {
          localStorage.setItem("schema_name", schema_name);
        } else {
          localStorage.removeItem("schema_name");
        }
        localStorage.setItem("is_superuser", is_superuser ? "true" : "false");
      }

      setAuthToken(access_token);

      const payload = decodeJwtPayload(access_token);
      const partialUser: AuthUser = {
        nome: payload?.nome || nome,
        username: payload?.username,
        empresa: payload?.empresa || empresa,
        logoUrl: payload?.logoUrl || logoUrl,
        email: payload?.email || uemail,
        id: payload?.user_id || payload?.id,
        role: payload?.role || role,
        roles: Array.isArray(payload?.roles)
          ? payload.roles
          : Array.isArray(roles)
          ? roles
          : payload?.role || role
          ? [payload?.role || role]
          : undefined,
        role_id: payload?.role_id ?? role_id ?? undefined,
        is_admin: payload?.is_admin ?? is_admin,
        is_superuser: payload?.is_superuser ?? is_superuser,
      };

      const providedRolesForPartial = Array.isArray(partialUser.roles)
        ? partialUser.roles
        : (partialUser.role_id !== undefined && partialUser.role_id !== null)
        ? [String(partialUser.role_id)]
        : partialUser.role
        ? [partialUser.role]
        : [];

      partialUser.roles = normalizeRoles(providedRolesForPartial);

      // mark evaluator flag early if role indicates it
      if (_isEvaluatorRole(partialUser)) {
        partialUser.evaluator_limited_view = true;
      }

      setUser(partialUser);
      if (typeof window !== "undefined") localStorage.setItem("user", JSON.stringify(partialUser));

      let finalUser: AuthUser | null = null;
      try {
        finalUser = await fetchUserProfile(access_token);
      } catch {
        finalUser = null;
      }

      const userToUse = finalUser || partialUser;

      // ensure evaluator flag even if fetchUserProfile returned incomplete info
      if (_isEvaluatorRole(userToUse)) {
        userToUse.evaluator_limited_view = true;
      }

      // persist updates before attempting redirect
      setUser(userToUse);
      if (typeof window !== "undefined") localStorage.setItem("user", JSON.stringify(userToUse));

      console.log("[DEBUG] login: calling handleEvaluatorRedirect for user", userToUse?.id);

      // Try robust evaluator redirect with fallbacks
      let redirected = false;
      try {
        redirected = await handleEvaluatorRedirect(userToUse, access_token);
      } catch (err) {
        console.warn("handleEvaluatorRedirect failed:", err);
      }

      if (redirected) {
        setLoading(false);
        return { success: true };
      }

      // fallback: use assigned ids from token/localStorage if present
      try {
        const ai = (userToUse as any)?.assigned_exercise_id;
        const ae = (userToUse as any)?.assigned_event_id;
        if (ai && ae) {
          const route = `/taf/events/${ae}/exercises/${ai}/field`;
          try { navigate(route, { replace: true }); } catch { window.location.replace(route); }
          setLoading(false);
          return { success: true };
        }
      } catch (err) {
        console.warn("Fallback redirect failed:", err);
      }

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

  // helper: retorna array normalizado de roles do usuário (strings)
  const getNormalizedUserRoles = (): string[] => {
    if (!user) return [];

    // Admins/superusers têm acesso total — retornamos um marker para permitir checagens diretas
    if (user.is_admin === true || user.is_superuser === true) {
      return ["__ADMIN__"];
    }

    // Prioriza user.roles (array), senão user.role, senão role_id
    const raw =
      Array.isArray(user.roles) && user.roles.length > 0
        ? user.roles
        : user.role
        ? [String(user.role)]
        : user.role_id !== undefined && user.role_id !== null
        ? [String(user.role_id)]
        : [];

    // normalizeRoles já existente: mantém para uniformizar strings (ex.: uppercase, trim)
    return normalizeRoles(raw || []);
  };

  const hasRole = (role: string): boolean => {
    if (!user) return false;

    // admin/superuser shortcut:
    const nr = getNormalizedUserRoles();
    if (nr.includes("__ADMIN__")) return true;

    const normalizedToCheck = normalizeRoles([role]);
    return normalizedToCheck.some(r => nr.includes(r));
  };

  const hasAnyRole = (rolesArr: string[]): boolean => {
    if (!user) return false;

    const nr = getNormalizedUserRoles();
    if (nr.includes("__ADMIN__")) return true;

    if (!Array.isArray(rolesArr) || rolesArr.length === 0) return false;

    const normalizedToCheck = normalizeRoles(rolesArr);
    return normalizedToCheck.some(r => nr.includes(r));
  };

  const hasAllRoles = (rolesArr: string[]): boolean => {
    if (!user) return false;

    const nr = getNormalizedUserRoles();
    if (nr.includes("__ADMIN__")) return true;

    if (!Array.isArray(rolesArr) || rolesArr.length === 0) return false;

    const normalizedToCheck = normalizeRoles(rolesArr);
    return normalizedToCheck.every(r => nr.includes(r));
  };

  const refreshUser = async () => {
    if (!token) return;
    await fetchUserProfile().catch(() => {});
  };

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
        hasRole,
        hasAnyRole,
        hasAllRoles,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};