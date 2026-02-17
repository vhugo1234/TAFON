import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  TextField,
  List,
  ListItem,
  ListItemAvatar,
  ListItemButton,
  Avatar,
  ListItemText,
  IconButton,
  Typography,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Paper,
  Stack,
  Chip,
  CircularProgress,
} from "@mui/material";
import { Delete, Edit, Save, Cancel } from "@mui/icons-material";
import api from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

type Props = { eventId: number; onChange?: () => void };

// Local fallback mapping (keeps compatibility if no roles endpoint exists)
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

export default function EventWorkersManager({ eventId, onChange }: Props) {
  const { token } = useAuth();
  const [workers, setWorkers] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  // Instead of a free-text role_name we store selected role_id in the form
  const [selectedRoleId, setSelectedRoleId] = useState<number | "">("");
  const [daysAssigned, setDaysAssigned] = useState<number | undefined>();
  const [loadingWorkers, setLoadingWorkers] = useState(false);
  const [editingDaysId, setEditingDaysId] = useState<number | null>(null);
  const [editingDaysValue, setEditingDaysValue] = useState<number | "">("");
  const [roles, setRoles] = useState<{ id: number; name: string }[]>([]);

  // New states for editing role on existing worker
  const [editingRoleWorkerId, setEditingRoleWorkerId] = useState<number | null>(null);
  const [editingRoleValue, setEditingRoleValue] = useState<number | "">("");
  const [editingRoleLoading, setEditingRoleLoading] = useState(false);

  const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

  useEffect(() => {
    fetchWorkers();
    fetchRoles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId]);

  // helper to build absolute avatar url (backend returns /uploads/...)
  function avatarSrc(url?: string) {
    if (!url) return undefined;
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
    const raw = (import.meta.env.VITE_API_URL || "http://localhost:8000") as string;
    const apiBase = raw.replace(/\/api(\/.*)?$/, "").replace(/\/+$/, "");
    if (url.startsWith("/")) return `${apiBase}${url}`;
    return `${apiBase}/${url.replace(/^\/+/, "")}`;
  }

  // Resolve role label from several places: worker.role_name > role lookup > fallback map
  function resolveRoleLabel(workerOrRoleId: any): string | null {
    if (!workerOrRoleId) return null;
    // worker object
    if (typeof workerOrRoleId === "object") {
      const w = workerOrRoleId;
      if (w.role_name) return String(w.role_name);
      if (w.user?.role_name) return String(w.user.role_name);
      const rid = Number(w.role_id ?? w.user?.role_id);
      if (rid) {
        const r = roles.find((x) => Number(x.id) === rid);
        if (r) return r.name;
        if (ROLE_MAP[rid]) return ROLE_MAP[rid];
      }
      return null;
    }
    // numeric role id
    const rid = Number(workerOrRoleId);
    if (!rid) return null;
    const r = roles.find((x) => Number(x.id) === rid);
    if (r) return r.name;
    if (ROLE_MAP[rid]) return ROLE_MAP[rid];
    return null;
  }

  // Try to fetch roles from a single configurable endpoint, fallback to ROLE_MAP.
  async function fetchRoles() {
    const urlParams = new URLSearchParams(window.location.search);
    const schemaName = urlParams.get("schema_name") || (window.__TENANT && window.__TENANT.schema) || null;

    if (!schemaName) {
      setRoles(Object.entries(ROLE_MAP).map(([k, v]) => ({ id: Number(k), name: v })));
      return;
    }

    const endpoint = `/api/v1/tenants/${encodeURIComponent(schemaName)}/roles/`;
    try {
      const res = await api.get(endpoint, { headers });
      const list = res.data?.items ?? res.data ?? res;
      if (Array.isArray(list) && list.length > 0) {
        const normalized = list.map((r: any) => ({ id: Number(r.id), name: r.nome ?? r.name ?? r.label ?? String(r.id) }));
        setRoles(normalized);
        return;
      }
    } catch (err) {
      console.debug("roles endpoint not available for tenant", schemaName, err?.response?.status ?? err?.message);
    }

    // fallback
    setRoles(Object.entries(ROLE_MAP).map(([k, v]) => ({ id: Number(k), name: v })));
  }

  async function fetchWorkers() {
    setLoadingWorkers(true);
    try {
      const res = await api.get(`/event/${eventId}/workers`, { headers });
      const items: any[] = res.data?.items ?? res.data ?? res;
      const normalized = items.map((it: any) => ({ ...it, user: it.user ?? null }));
      setWorkers(normalized);

      // complete missing user info (batch)
      const missingIds = Array.from(
        new Set(normalized.filter((w: any) => (!w.user || !w.user.nome) && w.user_id).map((w: any) => Number(w.user_id)))
      ).filter(Boolean);

      if (missingIds.length > 0) {
        try {
          const r2 = await api.get("/users", { params: { ids: missingIds.join(",") }, headers });
          const list = r2.data?.items ?? r2.data ?? r2;
          const map = new Map((list || []).map((u: any) => [Number(u.id), u]));
          setWorkers((prev) => prev.map((w) => ((!w.user || !w.user.nome) && map.has(Number(w.user_id))) ? { ...w, user: map.get(Number(w.user_id)) } : w));
        } catch {
          try {
            const promises = missingIds.map((id) => api.get(`/users/${id}`, { headers }).then((r) => r.data));
            const users = await Promise.all(promises);
            const map = new Map((users || []).map((u: any) => [Number(u.id), u]));
            setWorkers((prev) => prev.map((w) => ((!w.user || !w.user.nome) && map.has(Number(w.user_id))) ? { ...w, user: map.get(Number(w.user_id)) } : w));
          } catch (ignore) {
            console.debug("Falha ao completar dados dos usuários:", ignore);
          }
        }
      }
    } catch (err) {
      console.error("Erro ao buscar workers", err);
      setWorkers([]);
    } finally {
      setLoadingWorkers(false);
    }
  }

  // Robust search: trim query, call backend and then filter client-side to avoid back-end differences
  async function searchUsers() {
    const q = query.trim();
    if (!q) return setSearchResults([]);

    try {
      const res = await api.get(`/users`, { params: { q }, headers });
      const list = res.data.items ?? res.data ?? res;

      const normalized = Array.isArray(list) ? list : [];
      const lower = q.toLowerCase();

      // client-side filter by nome, username or email (case-insensitive)
      const filtered = normalized.filter((u: any) => {
        const hay = `${u.nome ?? u.username ?? u.email ?? ""}`.toLowerCase();
        return hay.includes(lower);
      });

      setSearchResults(filtered);
    } catch (e) {
      console.error("Erro buscar users", e);
      setSearchResults([]);
    }
  }

  // When adding: prefer sending role_id. If role_name is needed, derive it from roles lookup.
  async function handleAdd() {
    if (!selectedUserId) return;

    try {
      // ensure we have fresh user details (role_id may be on user record)
      let selUser = searchResults.find((u) => Number(u.id) === Number(selectedUserId));
      if (!selUser) {
        const r = await api.get(`/users/${selectedUserId}`, { headers });
        selUser = r.data;
      }

      const role_id_payload = selectedRoleId === "" ? (selUser ? (selUser.role_id ?? selUser.roleId ?? null) : null) : Number(selectedRoleId);
      const role_name_payload = role_id_payload ? resolveRoleLabel(role_id_payload) : (selectedRoleId === "" ? null : null);

      await api.post(
        `/event/${eventId}/workers`,
        {
          user_id: selectedUserId,
          role_id: role_id_payload,
          role_name: role_name_payload,
          days_assigned: daysAssigned ?? null,
        },
        { headers }
      );

      setSelectedUserId(null);
      setSelectedRoleId("");
      setDaysAssigned(undefined);
      setQuery("");
      setSearchResults([]);
      fetchWorkers();
      onChange?.();
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.response?.data?.message ?? err?.message ?? "Erro ao vincular usuário";
      alert(String(msg));
    }
  }

  async function handleRemove(workerId: number) {
    if (!confirm("Remover este usuário do evento?")) return;
    try {
      await api.delete(`/event/${eventId}/workers/${workerId}`, { headers });
      fetchWorkers();
      onChange?.();
    } catch (err) {
      console.error("Erro ao remover vínculo:", err);
      alert("Erro ao remover vínculo");
    }
  }

  // Edit days inline
  function startEditDays(worker: any) {
    setEditingDaysId(worker.id);
    setEditingDaysValue(worker.days_assigned ?? "");
  }
  function cancelEditDays() {
    setEditingDaysId(null);
    setEditingDaysValue("");
  }

  async function saveEditDays(workerId: number) {
    const value = editingDaysValue === "" ? null : Number(editingDaysValue);
    try {
      await api.patch(`/event/${eventId}/workers/${workerId}`, { days_assigned: value }, { headers });
      setEditingDaysId(null);
      setEditingDaysValue("");
      fetchWorkers();
      onChange?.();
    } catch (err) {
      console.error("Erro ao atualizar dias:", err);
      alert("Erro ao atualizar dias");
    }
  }

  // Role edit handlers
  function startEditRole(worker: any) {
    setEditingRoleWorkerId(worker.id);
    // prefer current role_id, fallback to "" so select shows placeholder
    setEditingRoleValue(worker.role_id ? Number(worker.role_id) : "");
  }

  function cancelEditRole() {
    setEditingRoleWorkerId(null);
    setEditingRoleValue("");
  }

  async function saveEditRole(workerId: number) {
    setEditingRoleLoading(true);
    try {
      const role_id_payload = editingRoleValue === "" ? null : Number(editingRoleValue);
      const role_name_payload = role_id_payload ? resolveRoleLabel(role_id_payload) : null;

      await api.patch(
        `/event/${eventId}/workers/${workerId}`,
        { role_id: role_id_payload, role_name: role_name_payload },
        { headers }
      );

      setEditingRoleWorkerId(null);
      setEditingRoleValue("");
      fetchWorkers();
      onChange?.();
    } catch (err) {
      console.error("Erro ao atualizar função:", err);
      alert("Erro ao atualizar função");
    } finally {
      setEditingRoleLoading(false);
    }
  }

  return (
    <Paper sx={{ p: 3, borderRadius: 3 }}>
      <Typography variant="h6" gutterBottom>
        Gerenciar equipe
      </Typography>

      {/* BUSCA */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Buscar usuário
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <TextField
            fullWidth
            label="Nome ou e-mail"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") searchUsers();
            }}
          />
          <Button variant="contained" onClick={searchUsers}>
            Buscar
          </Button>
        </Stack>
      </Paper>

      {/* RESULTADOS */}
      {searchResults.length > 0 && (
        <Paper variant="outlined" sx={{ borderRadius: 2, mb: 2, maxHeight: 260, overflow: "auto" }}>
          <List dense>
            {searchResults.map((u) => (
              <ListItem key={u.id}>
                <ListItemButton selected={selectedUserId === u.id} onClick={() => setSelectedUserId(u.id)}>
                  <ListItemAvatar>
                    <Avatar src={avatarSrc(u.avatar_url)}>{(u.nome || u.username || u.email || "U").slice(0, 2)}</Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={u.nome ?? u.username ?? u.email}
                    secondary={u.email ?? (u.role_name ?? resolveRoleLabel(u.role_id ?? u.roleId ?? u.role))}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Paper>
      )}

      {/* VINCULAR */}
      <Paper sx={{ p: 2, mb: 3, borderRadius: 2, bgcolor: "grey.50" }}>
        <Typography variant="subtitle2" gutterBottom>
          Vincular ao evento
        </Typography>

        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <FormControl fullWidth>
            <InputLabel>Função</InputLabel>
            <Select
              value={selectedRoleId}
              label="Função"
              onChange={(e) => setSelectedRoleId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <MenuItem value="">— (usar role do usuário)</MenuItem>
              {roles.map((r) => (
                <MenuItem key={r.id} value={r.id}>
                  {r.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            label="Dias"
            type="number"
            value={daysAssigned ?? ""}
            onChange={(e) => setDaysAssigned(e.target.value ? Number(e.target.value) : undefined)}
            sx={{ maxWidth: 120 }}
          />

          <Button variant="contained" size="large" disabled={!selectedUserId} onClick={handleAdd}>
            Vincular
          </Button>
        </Stack>
      </Paper>

      {/* LISTA */}
      <Typography variant="subtitle1" gutterBottom>
        Usuários vinculados
      </Typography>

      {loadingWorkers ? (
        <Box display="flex" alignItems="center" gap={1}>
          <CircularProgress size={20} /> <Typography>Carregando vínculos...</Typography>
        </Box>
      ) : workers.length === 0 ? (
        <Typography color="text.secondary">Nenhum usuário vinculado ainda.</Typography>
      ) : (
        <List>
          {workers.map((w) => {
            const roleLabel = resolveRoleLabel(w);
            const isEditingRole = editingRoleWorkerId === w.id;

            return (
              <ListItem
                key={w.id}
                sx={{ mb: 1, border: "1px solid", borderColor: "divider", borderRadius: 2 }}
                secondaryAction={
                  <Box display="flex" alignItems="center" gap={1}>
                    {/* Days edit */}
                    {editingDaysId === w.id ? (
                      <>
                        <IconButton onClick={() => saveEditDays(w.id)} color="primary">
                          <Save />
                        </IconButton>
                        <IconButton onClick={cancelEditDays}>
                          <Cancel />
                        </IconButton>
                      </>
                    ) : (
                      <IconButton onClick={() => startEditDays(w)}>
                        <Edit />
                      </IconButton>
                    )}

                    {/* Role edit controls (save/cancel while editing) */}
                    {isEditingRole ? (
                      <>
                        <IconButton onClick={() => saveEditRole(w.id)} color="primary" disabled={editingRoleLoading}>
                          <Save />
                        </IconButton>
                        <IconButton onClick={cancelEditRole} disabled={editingRoleLoading}>
                          <Cancel />
                        </IconButton>
                      </>
                    ) : (
                      <IconButton onClick={() => startEditRole(w)} title={roleLabel ? "Editar função" : "Atribuir função"}>
                        <Edit />
                      </IconButton>
                    )}

                    <IconButton onClick={() => handleRemove(w.id)} color="error">
                      <Delete />
                    </IconButton>
                  </Box>
                }
              >
                <ListItemAvatar>
                  <Avatar src={avatarSrc(w.user?.avatar_url)}>
                    {((w.user?.nome ?? w.user?.username) as string)
                      ?.split(" ")
                      .map((s) => s[0])
                      .slice(0, 2)
                      .join("") || String(w.user_id || "").slice(0, 2)}
                  </Avatar>
                </ListItemAvatar>

                <ListItemText
                  primary={
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography fontWeight={600}>
                        {w.user?.nome ?? w.user?.username ?? `Usuário #${w.user_id}`}
                      </Typography>

                      {/* Role display / edit area */}
                      {isEditingRole ? (
                        <FormControl size="small" sx={{ minWidth: 180 }}>
                          <InputLabel id={`editing-role-label-${w.id}`}>Função</InputLabel>
                          <Select
                            labelId={`editing-role-label-${w.id}`}
                            value={editingRoleValue}
                            label="Função"
                            onChange={(e) => setEditingRoleValue(e.target.value === "" ? "" : Number(e.target.value))}
                          >
                            <MenuItem value="">
                              <em>Sem função</em>
                            </MenuItem>
                            {roles.map((r) => (
                              <MenuItem key={r.id} value={r.id}>
                                {r.name}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      ) : roleLabel ? (
                        <Chip size="small" label={roleLabel} />
                      ) : (
                        // no role: show a clickable Chip-like button to assign
                        <Button size="small" variant="outlined" onClick={() => startEditRole(w)}>
                          Sem função — atribuir
                        </Button>
                      )}
                    </Stack>
                  }
                  secondary={
                    editingDaysId === w.id ? (
                      <TextField
                        value={editingDaysValue}
                        onChange={(e) => setEditingDaysValue(e.target.value ? Number(e.target.value) : "")}
                        type="number"
                        sx={{ width: 120 }}
                      />
                    ) : (
                      `Dias atribuídos: ${w.days_assigned ?? "-"}`
                    )
                  }
                />
              </ListItem>
            );
          })}
        </List>
      )}
    </Paper>
  );
}
