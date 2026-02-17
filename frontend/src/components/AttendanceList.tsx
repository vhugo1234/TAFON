import React, { useEffect, useMemo, useRef, useState } from "react";
import api from "../lib/api";
import {
  Paper,
  Box,
  Typography,
  Stack,
  IconButton,
  CircularProgress,
  List,
  ListItem,
  ListItemAvatar,
  Avatar,
  Button,
  TextField,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  useTheme,
  useMediaQuery,
  Chip,
  Tooltip,
  Snackbar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton as MuiIconButton,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import CheckIcon from "@mui/icons-material/Check";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import CloseIcon from "@mui/icons-material/Close";
import AttendanceCheckin from "../components/AttendanceCheckin";
import * as XLSX from "xlsx";

/**
 * AttendanceList.tsx
 *
 * - Mantive toda lógica existente.
 * - Removi blocos duplicados que estavam causando requisições para "undefined" e erros HMR.
 * - Adicionei proteção defensiva em fetchEventNameSafe (não faz requests com eventId inválido,
 *   bloqueia chamadas concorrentes e tenta apenas endpoints relativos via axios).
 *
 * Substitua apenas este arquivo. Não mexi no resto além do necessário.
 */

type Props = {
  eventId: number | string | undefined | null;
  getAuthHeaders?: () => Record<string, string>;
  eventName?: string; // optional: if parent passes the event name it will be used immediately
};

const ROLE_MAP: Record<number, string> = {
  1: "Administrador Geral",
  2: "Coordenador Geral",
  3: "Coordenador de Educação Física",
  4: "Avaliador de Educação Física",
  5: "Apoio",
  6: "Técnico de AudioVisual",
  7: "Volantes",
  8: "Fiscais",
};

const STATUS_COLOR: Record<string, "default" | "success" | "warning" | "error" | "info"> = {
  checked_in: "success",
  checked_out: "default",
  pending: "warning",
};

export default function AttendanceList({ eventId, getAuthHeaders, eventName: propEventName }: Props) {
  const [attendances, setAttendances] = useState<any[]>([]);
  const [participants, setParticipants] = useState<any[]>([]);
  const [roles, setRoles] = useState<{ id: number; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingParticipants, setLoadingParticipants] = useState(false);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawResponseSnippet, setRawResponseSnippet] = useState<string | null>(null);

  const [filter, setFilter] = useState<string>("");
  const [openCheckinForWorkerId, setOpenCheckinForWorkerId] = useState<number | null>(null);
  const [snack, setSnack] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const [exporting, setExporting] = useState(false);

  // ref para bloquear fetchs concorrentes
  const fetchingEventNameRef = useRef(false);

  // auto-fetched event name (if parent didn't pass prop)
  const [eventNameAuto, setEventNameAuto] = useState<string | null>(null);

  const theme = useTheme();
  const isXs = useMediaQuery(theme.breakpoints.down("sm"));

  const isDev = typeof import.meta !== "undefined" && !!(import.meta as any).env?.DEV;

  // helpers
  function authHeaders() {
    const headers: Record<string, string> = {};
    if (getAuthHeaders) Object.assign(headers, getAuthHeaders());
    return headers;
  }

  function avatarSrc(url?: string) {
    if (!url) return undefined;
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
    const raw = (import.meta.env.VITE_API_URL || "http://localhost:8000") as string;
    const apiBase = raw.replace(/\/api(\/.*)?$/, "").replace(/\/+$/, "");
    if (url.startsWith("/")) return `${apiBase}${url}`;
    return `${apiBase}/${url.replace(/^\/+/, "")}`;
  }

  function buildPreviewCandidates(path?: string): string[] {
    if (!path) return [];
    if (path.startsWith("http://") || path.startsWith("https://")) return [path];

    const raw = (import.meta.env.VITE_API_URL || "http://localhost:8000") as string;
    const base = raw.replace(/\/api(\/.*)?$/, "").replace(/\/+$/, "");

    const pNoSlash = path.replace(/^\/+/, "");
    const pWithLeading = path.startsWith("/") ? path : `/${pNoSlash}`;

    const candidates = [
      `/uploads${pWithLeading}`,
      `${base}/uploads${pWithLeading}`,
      `/static/uploads${pWithLeading}`,
      `${base}/static/uploads${pWithLeading}`,
      `${base}${pWithLeading}`,
      `${base}/${pNoSlash}`,
      `/static${pWithLeading}`,
      pWithLeading,
      path,
    ];

    const seen = new Set<string>();
    return candidates.filter((c) => {
      if (!c) return false;
      if (seen.has(c)) return false;
      seen.add(c);
      return true;
    });
  }

  function checkImage(url: string, timeout = 4000): Promise<boolean> {
    return new Promise((resolve) => {
      try {
        const img = new Image();
        let handled = false;
        const onDone = (ok: boolean) => {
          if (handled) return;
          handled = true;
          img.onload = null;
          img.onerror = null;
          resolve(ok);
        };
        img.onload = () => onDone(true);
        img.onerror = () => onDone(false);
        img.src = url;
        setTimeout(() => onDone(false), timeout);
      } catch {
        resolve(false);
      }
    });
  }

  // fetchers
  async function fetchRoles() {
    setLoadingRoles(true);
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const schemaName = urlParams.get("schema_name") || (window.__TENANT && window.__TENANT.schema) || null;
      if (!schemaName) {
        setRoles(Object.entries(ROLE_MAP).map(([k, v]) => ({ id: Number(k), name: v })));
        return;
      }
      const endpoint = `/api/v1/tenants/${encodeURIComponent(schemaName)}/roles/`;
      try {
        const res = await api.get(endpoint, { headers: authHeaders() });
        const list = res.data?.items ?? res.data ?? res;
        if (Array.isArray(list) && list.length > 0) {
          const normalized = list.map((r: any) => ({ id: Number(r.id), name: r.nome ?? r.name ?? r.label ?? String(r.id) }));
          setRoles(normalized);
          return;
        }
      } catch {
        // fallback
      }
      setRoles(Object.entries(ROLE_MAP).map(([k, v]) => ({ id: Number(k), name: v })));
    } finally {
      setLoadingRoles(false);
    }
  }

  const fetchAttendances = async () => {
    setLoading(true);
    setError(null);
    setRawResponseSnippet(null);
    try {
      const res = await api.get(`/event/${encodeURIComponent(eventId as any)}/attendance`, { headers: authHeaders() });
      const data = res.data ?? res;
      if (typeof data === "string") {
        setRawResponseSnippet(data.slice(0, 800));
        setError("Resposta do servidor não é JSON. Veja trecho abaixo.");
        setAttendances([]);
        return;
      }
      const list = Array.isArray(data) ? data : data.items ?? data.attendances ?? data.data ?? [];
      if (!Array.isArray(list)) {
        setRawResponseSnippet(JSON.stringify(data).slice(0, 800));
        setError("Formato inesperado na resposta (não é um array).");
        setAttendances([]);
        return;
      }
      setAttendances(list);
    } catch (err: any) {
      if (err?.response) {
        const st = err.response.status;
        const body = err.response.data;
        if (typeof body === "string" && body.trim().startsWith("<")) {
          setRawResponseSnippet(body.slice(0, 800));
          setError(`Erro ${st}: corpo HTML retornado.`);
        } else {
          setRawResponseSnippet(JSON.stringify(body).slice(0, 800));
          setError(`Erro ${st}: ${err.response.statusText || "Resposta inválida"}`);
        }
      } else {
        setError(err?.message ?? "Erro ao buscar presenças");
      }
      setAttendances([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchParticipants = async () => {
    setLoadingParticipants(true);
    try {
      const res = await api.get(`/event/${encodeURIComponent(eventId as any)}/workers`, { headers: authHeaders() });
      const data = res.data ?? res;
      const list = Array.isArray(data) ? data : data.items ?? data.workers ?? [];
      const normalized = (list || []).map((it: any) => ({ ...it, user: it.user ?? null }));
      setParticipants(normalized);

      const missingIds = Array.from(
        new Set(normalized.filter((w: any) => (!w.user || !w.user.nome) && w.user_id).map((w: any) => Number(w.user_id)))
      ).filter(Boolean);

      if (missingIds.length > 0) {
        try {
          const r2 = await api.get("/users", { params: { ids: missingIds.join(",") }, headers: authHeaders() });
          const listUsers = r2.data?.items ?? r2.data ?? r2;
          const map = new Map((listUsers || []).map((u: any) => [Number(u.id), u]));
          setParticipants((prev) =>
            prev.map((p) => ((!p.user || !p.user.nome) && map.has(Number(p.user_id))) ? { ...p, user: map.get(Number(p.user_id)) } : p)
          );
        } catch {
          try {
            const promises = missingIds.map((id) => api.get(`/users/${id}`, { headers: authHeaders() }).then((r) => r.data));
            const users = await Promise.all(promises);
            const map = new Map((users || []).map((u: any) => [Number(u.id), u]));
            setParticipants((prev) =>
              prev.map((p) => ((!p.user || !p.user.nome) && map.has(Number(p.user_id))) ? { ...p, user: map.get(Number(p.user_id)) } : p)
            );
          } catch {
            // ignore
          }
        }
      }
    } catch {
      try {
        const res2 = await api.get(`/taf/events/${encodeURIComponent(eventId as any)}/workers`, { headers: authHeaders() });
        const data2 = res2.data ?? res2;
        const list2 = Array.isArray(data2) ? data2 : data2.items ?? data2.workers ?? [];
        const normalized2 = (list2 || []).map((it: any) => ({ ...it, user: it.user ?? null }));
        setParticipants(normalized2);
      } catch {
        setParticipants([]);
      }
    } finally {
      setLoadingParticipants(false);
    }
  };

  useEffect(() => {
    if (!eventId) return;
    fetchRoles();
    fetchParticipants();
    fetchAttendances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId]);

  // --- NEW: fetch event name safely and minimally (REPLACED DUPLICATES) ---
  async function fetchEventNameSafe() {
    // 1) se o parent passou o nome, usamos direto
    if (propEventName) {
      setEventNameAuto(propEventName);
      return;
    }

    // 2) valida eventId — evita 'undefined', null, 0, NaN, strings vazias
    const idNum = Number(eventId);
    if (eventId === undefined || eventId === null || Number.isNaN(idNum) || idNum <= 0) {
      if (isDev) console.debug("fetchEventNameSafe: invalid eventId, skipping fetch:", eventId);
      setEventNameAuto(null);
      return;
    }

    // 3) evita chamadas concorrentes (React StrictMode pode chamar efeitos duas vezes)
    if (fetchingEventNameRef.current) {
      if (isDev) console.debug("fetchEventNameSafe: fetch already in progress, skipping duplicate call");
      return;
    }
    fetchingEventNameRef.current = true;

    try {
      // 4) checar attendances primeiro (sem rede)
      if (attendances && attendances.length > 0) {
        const cand = attendances.find((a: any) => a.event_name || a.event_title || a.event || a.nome);
        if (cand) {
          const name = cand.event_name ?? cand.event_title ?? cand.event ?? cand.nome ?? null;
          if (name) {
            setEventNameAuto(name);
            return;
          }
        }
      }

      // 5) tentar um pequeno conjunto de endpoints relativos via axios (usa api.defaults.baseURL)
      //    somente quando temos eventId válido (guard acima)
      const candidates = [`events/${encodeURIComponent(eventId as any)}`, `event/${encodeURIComponent(eventId as any)}`];

      for (const path of candidates) {
        try {
          const res = await api.get(path, { headers: authHeaders() });
          const d = res.data ?? res;
          const name = d?.name ?? d?.title ?? d?.titulo ?? d?.event_name ?? d?.nome ?? null;
          if (name) {
            setEventNameAuto(name);
            return;
          }
        } catch (err) {
          if (isDev) console.debug("fetchEventNameSafe: candidate failed", path, err?.response?.status ?? err?.message);
          // continua para o próximo
        }
      }

      // 6) nada encontrado
      setEventNameAuto(null);
    } finally {
      fetchingEventNameRef.current = false;
    }
  }

  useEffect(() => {
    // chama de forma segura; a função já checa eventId inválido
    fetchEventNameSafe().catch((e) => {
      if (isDev) console.error("fetchEventNameSafe error:", e);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, attendances, propEventName]);

  function resolveRoleLabel(w: any): string | null {
    if (!w) return null;
    if (w.role_name) return String(w.role_name);
    if (w.user?.role_name) return String(w.user.role_name);
    const rid = Number(w.role_id ?? w.user?.role_id ?? 0);
    if (!rid) return null;
    const found = roles.find((r) => Number(r.id) === rid);
    if (found) return found.name;
    if (ROLE_MAP[rid]) return ROLE_MAP[rid];
    return null;
  }

  const filteredParticipants = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return participants;
    return participants.filter((p) => {
      const name = (p.user?.nome ?? p.user?.username ?? p.user_name ?? "").toString().toLowerCase();
      const email = (p.user?.email ?? p.email ?? "").toString().toLowerCase();
      const role = (resolveRoleLabel(p) ?? "").toString().toLowerCase();
      return name.includes(q) || email.includes(q) || role.includes(q);
    });
  }, [participants, filter, roles]);

  const doCheckout = async (attendanceId: number, eventWorkerId?: number) => {
    setError(null);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (getAuthHeaders) Object.assign(headers, getAuthHeaders());
      const workerIdForUrl = eventWorkerId ?? 0;
      await api.post(`/event/${encodeURIComponent(eventId as any)}/worker/${encodeURIComponent(workerIdForUrl)}/attendance/${attendanceId}/checkout`, undefined, { headers });
      setSnack({ type: "success", message: "Checkout realizado." });
      await fetchAttendances();
    } catch (err: any) {
      setError(err?.message || "Erro ao dar checkout");
      setSnack({ type: "error", message: "Erro ao dar checkout" });
    }
  };

  // helpers for display & export formatting
  function participantLabel(p: any) {
    return p.user?.nome ?? p.user?.username ?? p.user_name ?? `Usuário #${p.user_id ?? p.id ?? "?"}`;
  }

  function attendanceParticipantLabel(it: any) {
    const candidate = it.user_nome ?? it.user_name ?? it.user?.nome ?? it.user?.username ?? null;
    if (candidate) return candidate;
    if (it.event_worker_id) {
      const found = participants.find((p) => Number(p.id) === Number(it.event_worker_id));
      if (found) return found.user?.nome ?? found.user?.username ?? `event_worker:${found.id}`;
    }
    if (it.user_id) return `Usuário #${it.user_id}`;
    return `#${it.id ?? "?"}`;
  }

  function attendanceAvatarSrc(it: any) {
    const avatar = it.user?.avatar_url ?? it.user_avatar ?? null;
    return avatar ? avatarSrc(avatar) : undefined;
  }

  function formatDate(d?: string | Date) {
    if (!d) return "";
    try {
      const dt = typeof d === "string" ? new Date(d) : d;
      return new Intl.DateTimeFormat(undefined, { dateStyle: "short" }).format(dt);
    } catch {
      return String(d);
    }
  }

  function formatDateTime(d?: string | Date) {
    if (!d) return "";
    try {
      const dt = typeof d === "string" ? new Date(d) : d;
      return new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(dt);
    } catch {
      return String(d);
    }
  }

  // Signature thumbnail component (less noisy logging)
  function SignatureThumbnail({ path, alt = "assinatura", size = 48 }: { path?: string; alt?: string; size?: number }) {
    const candidates = buildPreviewCandidates(path);
    const [idx, setIdx] = useState(0);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
      setIdx(0);
      setLoaded(false);
    }, [path]);

    if (!candidates || candidates.length === 0) {
      return <Typography variant="caption" color="text.secondary">—</Typography>;
    }

    const src = candidates[idx];

    return (
      <img
        src={src}
        alt={alt}
        style={{ height: size, borderRadius: 4, border: "1px solid #eee", objectFit: "contain", display: loaded ? "inline-block" : "inline-block", background: "#fff" }}
        onLoad={() => setLoaded(true)}
        onError={() => {
          if (isDev) console.debug("SignatureThumbnail: failed to load candidate:", src);
          if (idx + 1 < candidates.length) {
            setIdx(idx + 1);
          } else {
            if (isDev) console.warn("SignatureThumbnail: no candidate loaded for path:", path, candidates);
            setLoaded(false);
            setIdx(candidates.length);
          }
        }}
      />
    );
  }

  // signature modal state & open helper
  const [sigModalOpen, setSigModalOpen] = useState(false);
  const [sigModalSrc, setSigModalSrc] = useState<string | null>(null);

  async function openSignatureModal(path?: string) {
    const candidates = buildPreviewCandidates(path);
    if (!candidates || candidates.length === 0) {
      setSnack({ type: "error", message: "Assinatura não disponível" });
      return;
    }
    for (const c of candidates) {
      if (!c) continue;
      const ok = await checkImage(c);
      if (ok) {
        setSigModalSrc(c);
        setSigModalOpen(true);
        return;
      }
    }
    setSigModalSrc(candidates[0]);
    setSigModalOpen(true);
    setSnack({ type: "error", message: "Não foi possível carregar a assinatura (verifique servidor)." });
  }

  // --- EXPORT: grouped by participant (uses propEventName or fetched eventNameAuto) ---
  async function exportAttendancesToExcel() {
    try {
      setExporting(true);

      // ensure roles loaded (best-effort)
      if (!roles || roles.length === 0) {
        try { await fetchRoles(); } catch { /* ignore */ }
      }

      // determine event name: propEventName > eventNameAuto > attendances > fallback
      let eventName = propEventName ?? eventNameAuto ?? null;
      if (!eventName && attendances && attendances.length > 0) {
        const cand = attendances.find((a: any) => a.event_name || a.event_title || a.event || a.nome);
        if (cand) eventName = cand.event_name ?? cand.event_title ?? cand.event ?? cand.nome ?? null;
      }
      if (!eventName) eventName = `Evento #${eventId}`;

      // build maps from participants
      const byEventWorker = new Map<number, any>();
      const byUserId = new Map<number, any>();
      for (const p of participants || []) {
        try {
          if (p.id) byEventWorker.set(Number(p.id), p);
          if (p.user && p.user.id) byUserId.set(Number(p.user.id), p);
        } catch { /* ignore malformed */ }
      }

      function getRoleNameById(rid: number | string | undefined | null): string | null {
        if (!rid) return null;
        const num = Number(rid);
        const found = roles.find((r) => Number(r.id) === num);
        if (found) return found.name ?? String(found.id);
        return null;
      }

      // group attendances by participant key
      const byParticipant = new Map<string, any[]>();
      attendances.forEach((a: any) => {
        const key = a.user_id ? `u:${a.user_id}` : a.event_worker_id ? `w:${a.event_worker_id}` : `a:${a.id}`;
        if (!byParticipant.has(key)) byParticipant.set(key, []);
        byParticipant.get(key)!.push(a);
      });

      const rows: any[] = [];
      for (const [_key, list] of byParticipant.entries()) {
        const first = list[0] || {};
        const userId = first.user_id ?? first.user?.id ?? null;
        const eventWorkerId = first.event_worker_id ?? null;

        let participantName =
          first.user_nome ?? first.user?.nome ?? first.user_name ?? "";

        if (!participantName) {
          if (eventWorkerId && byEventWorker.has(Number(eventWorkerId))) {
            participantName = byEventWorker.get(Number(eventWorkerId))?.user?.nome ?? byEventWorker.get(Number(eventWorkerId))?.user_name ?? "";
          } else if (userId && byUserId.has(Number(userId))) {
            participantName = byUserId.get(Number(userId))?.user?.nome ?? byUserId.get(Number(userId))?.user_name ?? "";
          }
        }

        let participantEmail = first.user?.email ?? "";
        if (!participantEmail) {
          if (eventWorkerId && byEventWorker.has(Number(eventWorkerId))) {
            participantEmail = byEventWorker.get(Number(eventWorkerId))?.user?.email ?? "";
          } else if (userId && byUserId.has(Number(userId))) {
            participantEmail = byUserId.get(Number(userId))?.user?.email ?? "";
          }
        }

        let roleName =
          first.role_name ?? first.user?.role_name ?? getRoleNameById(first.role_id) ?? "";

        if (!roleName) {
          if (eventWorkerId && byEventWorker.has(Number(eventWorkerId))) {
            const p = byEventWorker.get(Number(eventWorkerId));
            roleName = p?.role_name ?? getRoleNameById(p?.role_id) ?? p?.user?.role_name ?? "";
          } else if (userId && byUserId.has(Number(userId))) {
            const p = byUserId.get(Number(userId));
            roleName = p?.role_name ?? getRoleNameById(p?.role_id) ?? p?.user?.role_name ?? "";
          }
        }

        const eventNameFromAttendance = first.event_name ?? first.event_title ?? first.event ?? null;
        const resolvedEventName = eventNameFromAttendance ?? eventName;

        list.sort((x: any, y: any) => {
          const a = x.check_in_at ? new Date(x.check_in_at).getTime() : 0;
          const b = y.check_in_at ? new Date(y.check_in_at).getTime() : 0;
          return a - b;
        });

        const checkins = list
          .map((r: any) => (r.check_in_at ? formatDateTime(r.check_in_at) : r.attendance_date ?? ""))
          .filter(Boolean)
          .join(" ; ");
        const checkouts = list
          .map((r: any) => (r.check_out_at ? formatDateTime(r.check_out_at) : ""))
          .filter(Boolean)
          .join(" ; ");

        rows.push({
          "Evento": resolvedEventName,
          "Participante": participantName || "",
          "E-mail": participantEmail || "",
          "Função": roleName || "",
          "Datas (check-in)": checkins,
          "Check-outs": checkouts,
          "Total de Presenças": list.length,
        });
      }

      // alphabetical order by participant (pt-BR)
      rows.sort((a, b) => {
        const na = (a["Participante"] || "").toString().toLowerCase();
        const nb = (b["Participante"] || "").toString().toLowerCase();
        return na.localeCompare(nb, "pt-BR", { sensitivity: "base" });
      });

      const ws = XLSX.utils.json_to_sheet(rows);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Presenças por participante");
      const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      const blob = new Blob([wbout], { type: "application/octet-stream" });
      const filename = `evento_${eventId}_presencas_${new Date().toISOString().slice(0, 10)}.xlsx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      setSnack({ type: "success", message: "Arquivo Excel gerado." });
    } catch (e) {
      if (isDev) console.error("Export error", e);
      setSnack({ type: "error", message: "Erro ao gerar Excel." });
    } finally {
      setExporting(false);
    }
  }

  // Render
  return (
    <Box>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="h6">Participantes</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <IconButton size="small" title="Atualizar participantes" onClick={() => fetchParticipants()}>
              <RefreshIcon />
            </IconButton>
            {loadingParticipants && <CircularProgress size={18} />}
          </Stack>
        </Box>

        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="center" sx={{ mb: 1 }}>
          <TextField
            label="Filtrar participantes (nome, e-mail, função)"
            placeholder="Digite nome, e-mail ou função"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            size="small"
            fullWidth
          />
          <Button variant="outlined" onClick={() => { setFilter(""); fetchParticipants(); }}>
            Limpar
          </Button>
        </Stack>

        {loadingParticipants ? (
          <Box sx={{ py: 3, display: "flex", alignItems: "center", gap: 1 }}>
            <CircularProgress size={20} /> <Typography>Carregando participantes...</Typography>
          </Box>
        ) : filteredParticipants.length === 0 ? (
          <Typography color="text.secondary">Nenhum participante encontrado.</Typography>
        ) : (
          <List>
            {filteredParticipants.map((p) => (
              <ListItem key={`participant-${p.id}`} disableGutters sx={{ py: 1 }}>
                <Box sx={{
                  display: "flex",
                  alignItems: "center",
                  width: "100%",
                  gap: 2,
                  flexDirection: isXs ? "column" : "row",
                }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 2, minWidth: 0, width: "100%" }}>
                    <ListItemAvatar>
                      <Avatar src={avatarSrc(p.user?.avatar_url)} sx={{ width: 44, height: 44 }}>
                        {!p.user?.avatar_url &&
                          String(participantLabel(p))
                            .split(" ")
                            .map((s) => s[0])
                            .slice(0, 2)
                            .join("")
                            .toUpperCase()}
                      </Avatar>
                    </ListItemAvatar>

                    <Box sx={{ minWidth: 0, flex: 1 }}>
                      <Typography variant="body1" sx={{
                        fontWeight: 600,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}>
                        {participantLabel(p)}
                      </Typography>

                      <Typography variant="body2" color="text.secondary" sx={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}>
                        {resolveRoleLabel(p) ?? "Sem função"}
                      </Typography>

                      {p.user?.email && (
                        <Typography variant="caption" color="text.secondary" sx={{
                          display: "block",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}>
                          {p.user.email}
                        </Typography>
                      )}
                    </Box>
                  </Box>

                  <Box sx={{
                    ml: isXs ? 0 : "auto",
                    mt: isXs ? 1 : 0,
                    width: isXs ? "100%" : 160,
                    display: "flex",
                    justifyContent: isXs ? "center" : "flex-end",
                  }}>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<PersonAddIcon />}
                      onClick={(e) => { e.stopPropagation(); e.preventDefault(); setOpenCheckinForWorkerId(Number(p.id)); }}
                      sx={{ width: isXs ? "100%" : "140px" }}
                    >
                      Registrar presença
                    </Button>
                  </Box>
                </Box>
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="h6">
            {propEventName || eventNameAuto ? `Presenças — ${propEventName ?? eventNameAuto}` : `Presenças do evento #${eventId}`}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button variant="outlined" size="small" onClick={exportAttendancesToExcel} disabled={attendances.length === 0 || exporting}>
              {exporting ? "Gerando..." : "Exportar Excel"}
            </Button>
            <IconButton size="small" title="Atualizar presenças" onClick={() => fetchAttendances()}>
              <RefreshIcon />
            </IconButton>
            {loading && <CircularProgress size={18} />}
          </Stack>
        </Box>

        {error && (
          <Box mb={2}>
            <Typography color="error" variant="body2" gutterBottom>
              {error}
            </Typography>
            {rawResponseSnippet && (
              <Box component="pre" sx={{ whiteSpace: "pre-wrap", maxHeight: 240, overflow: "auto", background: "#fff5f5", p: 1, borderRadius: 1 }}>
                {rawResponseSnippet}
              </Box>
            )}
          </Box>
        )}

        {!loading && attendances.length === 0 && !error && (
          <Box sx={{ py: 3 }}>
            <Typography color="text.secondary">Nenhuma presença registrada ainda.</Typography>
            <Box sx={{ mt: 1 }}>
              <Button variant="outlined" size="small" onClick={() => fetchAttendances()}>
                Recarregar
              </Button>
            </Box>
          </Box>
        )}

        {attendances.length > 0 && (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Participante</TableCell>
                  <TableCell>Data</TableCell>
                  <TableCell>Check‑in</TableCell>
                  <TableCell>Assinatura</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Ações</TableCell>
                </TableRow>
              </TableHead>

              <TableBody>
                {attendances.map((it: any) => (
                  <TableRow key={it.id}>
                    <TableCell sx={{ width: 80 }}>{it.id}</TableCell>

                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Avatar sx={{ width: 28, height: 28, fontSize: 12 }} src={attendanceAvatarSrc(it)}>
                          {!attendanceAvatarSrc(it) &&
                            String(it.user_nome ?? it.user_name ?? it.user?.nome ?? it.user?.username ?? `#${it.user_id ?? it.event_worker_id ?? it.id}`)
                              .split(" ")
                              .map((p) => p[0])
                              .slice(0, 2)
                              .join("")
                              .toUpperCase()}
                        </Avatar>
                        <Box>
                          <Typography variant="body2">{attendanceParticipantLabel(it)}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {it.event_worker_id ? `event_worker:${it.event_worker_id}` : (it.user_id ? `user:${it.user_id}` : "")}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>

                    <TableCell>{formatDate(it.attendance_date ?? it.created_at ?? "")}</TableCell>
                    <TableCell>{it.check_in_at ? formatDateTime(it.check_in_at) : ""}</TableCell>

                    <TableCell>
                      {it.check_in_signature_path ? (
                        <Tooltip title="Visualizar assinatura">
                          <Box
                            component="span"
                            sx={{ cursor: "pointer", display: "inline-block" }}
                            onClick={() => openSignatureModal(it.check_in_signature_path)}
                          >
                            <SignatureThumbnail path={it.check_in_signature_path} />
                          </Box>
                        </Tooltip>
                      ) : (
                        <Typography variant="caption" color="text.secondary">—</Typography>
                      )}
                    </TableCell>

                    <TableCell>
                      <Chip label={it.status ?? ""} color={STATUS_COLOR[it.status] ?? "default"} size="small" />
                    </TableCell>

                    <TableCell align="right">
                      {it.status !== "checked_out" ? (
                        <Button size="small" color="primary" startIcon={<CheckIcon />} onClick={() => doCheckout(it.id, it.event_worker_id)}>
                          Checkout
                        </Button>
                      ) : (
                        <Typography variant="caption" color="text.secondary">Concluído</Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Signature modal */}
      <Dialog open={sigModalOpen} onClose={() => setSigModalOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Typography variant="subtitle1" component="div">Assinatura</Typography>
          <MuiIconButton onClick={() => setSigModalOpen(false)}><CloseIcon /></MuiIconButton>
        </DialogTitle>
        <DialogContent dividers>
          {sigModalSrc ? (
            <Box sx={{ textAlign: "center" }}>
              <img src={sigModalSrc} alt="assinatura" style={{ maxWidth: "100%", maxHeight: "70vh" }} />
            </Box>
          ) : (
            <Typography color="text.secondary">Assinatura não disponível.</Typography>
          )}
        </DialogContent>
      </Dialog>

      {/* Controlled checkin modal for single participant */}
      {openCheckinForWorkerId !== null && (
        <AttendanceCheckin
          eventId={eventId}
          workerId={openCheckinForWorkerId}
          getAuthHeaders={getAuthHeaders}
          open={true}
          onClose={() => setOpenCheckinForWorkerId(null)}
          onSuccess={async () => {
            await fetchAttendances();
            await fetchParticipants();
            setOpenCheckinForWorkerId(null);
          }}
        />
      )}

      <Snackbar open={!!snack} autoHideDuration={4000} onClose={() => setSnack(null)}>
        {snack && <Alert severity={snack.type} onClose={() => setSnack(null)}>{snack.message}</Alert>}
      </Snackbar>
    </Box>
  );

  // --- Local helpers (kept below to avoid hoisting issues) ---
  function attendanceAvatarSrc(it: any) {
    const avatar = it.user?.avatar_url ?? it.user_avatar ?? null;
    return avatar ? avatarSrc(avatar) : undefined;
  }

  function SignatureThumbnail({ path, alt = "assinatura", size = 48 }: { path?: string; alt?: string; size?: number }) {
    const candidates = buildPreviewCandidates(path);
    const [idx, setIdx] = useState(0);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
      setIdx(0);
      setLoaded(false);
    }, [path]);

    if (!candidates || candidates.length === 0) {
      return <Typography variant="caption" color="text.secondary">—</Typography>;
    }

    const src = candidates[idx];

    return (
      <img
        src={src}
        alt={alt}
        style={{ height: size, borderRadius: 4, border: "1px solid #eee", objectFit: "contain", display: loaded ? "inline-block" : "inline-block", background: "#fff" }}
        onLoad={() => setLoaded(true)}
        onError={() => {
          if (isDev) console.debug("SignatureThumbnail failed to load candidate:", src);
          if (idx + 1 < candidates.length) {
            setIdx(idx + 1);
          } else {
            if (isDev) console.warn("SignatureThumbnail: could not load any candidate for path:", path, candidates);
            setLoaded(false);
            setIdx(candidates.length);
          }
        }}
      />
    );
  }

  function resolveRoleLabel(w: any): string | null {
    if (!w) return null;
    if (w.role_name) return String(w.role_name);
    if (w.user?.role_name) return String(w.user.role_name);
    const rid = Number(w.role_id ?? w.user?.role_id ?? 0);
    if (!rid) return null;
    const found = roles.find((r) => Number(r.id) === rid);
    if (found) return found.name;
    if (ROLE_MAP[rid]) return ROLE_MAP[rid];
    return null;
  }
}
