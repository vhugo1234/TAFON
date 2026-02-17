import React, { useEffect, useMemo, useState } from 'react';
import {
  Box, Button, Typography, Table, TableBody, TableCell, TableHead, TableRow, Paper, Stack, Alert,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, MenuItem, IconButton, TableContainer, Switch, Avatar,
  Checkbox, FormControlLabel, InputAdornment
} from '@mui/material';
import { Edit, Delete, ContentCopy, Search, Clear } from '@mui/icons-material';
import api from "../../lib/api";
import { useAuth } from '../../contexts/AuthContext';

type UserForm = {
  id?: number;
  username?: string;
  full_name?: string;
  nome: string;
  email: string;
  password?: string;
  cpf?: string;
  phone?: string;
  department?: string;
  institution?: string;
  birth_date?: string;
  notes?: string;
  address?: string;
  avatar_url?: string;
  avatar_file?: File | null; // <-- new: holds chosen file before upload
  specialty?: string;
  role?: string;
  role_id?: number;
  custom_role?: string;
  accepted_terms?: boolean;
  is_active: boolean;
  is_admin?: boolean;
  // novo campo: registro profissional
  cref?: string;
  // novos campos bancários
  bank_name?: string;
  pix?: string;
  bank_account?: string;
  agency?: string;
};

const ROLES = [
  { value: 1, label: "Administrador Geral" },
  { value: 2, label: "Coordenador Geral" },
  { value: 3, label: "Coordenador de Educação Física" },
  { value: 4, label: "Avaliador de Educação Física" },
  { value: 5, label: "Apoio" },
  { value: 6, label: "Técnico de AudioVisual" },
  { value: 7, label: "Volantes" },
  { value: 8, label: "Fiscais" },
  { value: "other", label: "Outros" },
];

const initialForm: UserForm = {
  username: "",
  full_name: "",
  nome: "",
  email: "",
  password: "",
  cpf: "",
  phone: "",
  department: "",
  institution: "",
  birth_date: "",
  notes: "",
  address: "",
  avatar_url: "",
  avatar_file: null,
  specialty: "",
  role: undefined,
  role_id: 1,
  custom_role: undefined,
  accepted_terms: false,
  is_active: true,
  is_admin: false,
  cref: "",
  bank_name: "",
  pix: "",
  bank_account: "",
  agency: "",
};

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getAvatarSrc(url?: string) {
  if (!url) return "";

  if (url.startsWith('http://') || url.startsWith('https://')) return url;

  const raw = (import.meta.env.VITE_API_URL || "http://localhost:8000") as string;
  const apiBase = raw.replace(/\/api(\/.*)?$/, '').replace(/\/+$/, '');

  if (url.startsWith('/')) {
    return `${apiBase}${url}`;
  }

  const normalized = url.replace(/^\/+/, '');
  return `${apiBase}/${normalized}`;
}

function extractErrorMessage(err: any): string {
  try {
    if (!err) return 'Erro desconhecido';
    if (err.response && err.response.data) {
      const data = err.response.data;
      if (typeof data === 'string') return data;
      if (Array.isArray(data.detail)) {
        return data.detail.map((d: any) => {
          if (typeof d === 'string') return d;
          if (d?.loc && d?.msg) return `${d.loc.join('.')}: ${d.msg}`;
          return JSON.stringify(d);
        }).join('; ');
      }
      if (data.detail && typeof data.detail === 'string') return data.detail;
      if (data.message) return String(data.message);
      return JSON.stringify(data);
    }
    if (err.message) return String(err.message);
    return 'Erro inesperado';
  } catch (e) {
    return 'Erro ao processar mensagem de erro';
  }
}

export default function UserManagementTab() {
  const [users, setUsers] = useState<UserForm[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [form, setForm] = useState<UserForm>({ ...initialForm });
  const [editUser, setEditUser] = useState<UserForm | null>(null);

  const { token, schemaName } = useAuth();
  const [open, setOpen] = useState(false);

  const [openPhotoModal, setOpenPhotoModal] = useState(false);
  const [selectedPhotoUrl, setSelectedPhotoUrl] = useState<string | null>(null);

  // new: filter state
  const [filter, setFilter] = useState<string>("");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.get('/users/', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => setUsers(res.data))
      .catch((err: any) => {
        const m = extractErrorMessage(err);
        setError(m || "Falha ao buscar usuários.");
        console.error("Erro fetch users:", err);
      })
      .finally(() => setLoading(false));
  }, [message, token, open]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | { name?: string; value: unknown }>) {
    const target = e.target as HTMLInputElement;
    const { name, value, type, checked } = target;
    if (type === "checkbox") {
      setForm({ ...form, [name]: checked });
    } else if (name === "role_id") {
      setForm({ ...form, role_id: Number(value) });
    } else {
      setForm({ ...form, [name as string]: value });
    }
  }

  // New: file input handler (sets avatar_file and live preview)
  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files && e.target.files[0] ? e.target.files[0] : null;
    // update form file and preview URL
    setForm(prev => ({ ...prev, avatar_file: file }));
    if (file) {
      const url = URL.createObjectURL(file);
      setSelectedPhotoUrl(url);
      setOpenPhotoModal(true);
      // revoke object URL later when dialog closes or file replaced
    } else {
      setSelectedPhotoUrl(null);
    }
  }

  // substitua/certifique-se que exista apenas esta versão de handleSubmit
    async function handleSubmit(e: React.FormEvent) {
      e.preventDefault();
      setMessage(null);
      setError(null);

      // client-side validation for "other" role if you use custom_role
      // (ignore if your form does not have custom_role)
      // if (form.role === "other") {
      //   if (!(form.custom_role && form.custom_role.trim())) {
      //     setError("Descreva o papel quando selecionar 'Outros'.");
      //     return;
      //   }
      // }

      // build base payload used for JSON requests
      const payload: any = {
        nome: form.full_name || form.nome || form.username || "",
        username: form.username || undefined,
        email: form.email || undefined,
        password: form.password || undefined,
        cpf: form.cpf || undefined,
        phone: form.phone || undefined,
        department: form.department || undefined,
        institution: form.institution || undefined,
        birth_date: form.birth_date || undefined,
        notes: form.notes || undefined,
        address: form.address || undefined,
        specialty: form.specialty || undefined,
        role_id: (form as any).role_id ?? undefined,
        accepted_terms: Boolean((form as any).accepted_terms),
        is_active: Boolean(form.is_active),
        is_admin: Boolean((form as any).is_admin),
        cref: form.cref || undefined,
        bank_name: form.bank_name || undefined,
        pix: form.pix || undefined,
        bank_account: form.bank_account || undefined,
        agency: form.agency || undefined,
      };

      // include custom_role if your form uses it
      if ((form as any).custom_role !== undefined) {
        payload.custom_role = (form as any).custom_role ?? null;
      }

      const isEdit = Boolean(editUser && editUser.id);
      const url = isEdit ? `/users/${editUser!.id}` : "/users/";
      const method = isEdit ? api.patch : api.post;

      // If we have a file, send multipart/form-data
      if (form.avatar_file) {
        try {
          console.debug("DEBUG form.avatar_file:", form.avatar_file);
          const fd = new FormData();

          // append file
          fd.append("avatar_file", form.avatar_file as File);

          // append scalar fields we want to send (explicit list to avoid surprises)
          const keysToSend = [
            "nome", "username", "email", "password", "cpf", "phone", "department",
            "institution", "birth_date", "notes", "address", "specialty",
            "accepted_terms", "is_active", "is_admin", "role_id", "custom_role","cref",
            // banking fields
            "bank_name", "pix", "bank_account", "agency"
          ];

          keysToSend.forEach(k => {
            // prefer payload values (JSON path) but fallback to form state
            const v = (payload as any)[k] ?? (form as any)[k];
            if (v !== undefined && v !== null && v !== "") {
              fd.append(k, String(v));
            } else if (k === "custom_role") {
              // ensure custom_role is always sent (can be empty string to clear)
              fd.append("custom_role", ((form as any).custom_role ?? ""));
            } else if (k === "role_id") {
              // if role_id is null/undefined and you want to send empty to signal null
              if ((form as any).role === "other") {
                fd.append("role_id", ""); // backend may interpret as NULL
              }
            }
          });

          console.debug("DEBUG fd.get('avatar_file'):", fd.get("avatar_file"));

          // config: ensure axios does NOT force Content-Type header for FormData
          const config = {
            headers: { Authorization: `Bearer ${token}` },
            transformRequest: [(data: any, headers: any) => {
              if (headers && headers["Content-Type"]) {
                delete headers["Content-Type"];
              }
              return data;
            }]
          };

          await method(url, fd, config);

          setMessage(isEdit ? "Usuário atualizado com sucesso!" : "Usuário criado com sucesso!");
          setForm({ ...initialForm });
          setEditUser(null);
          setOpen(false);
          if (selectedPhotoUrl) {
            URL.revokeObjectURL(selectedPhotoUrl);
            setSelectedPhotoUrl(null);
          }
          return;
        } catch (err: any) {
          // handle 409 (existing_user_id) fallback if backend returns it
          if (err?.response?.status === 409) {
            const data = err.response.data || {};
            const existingId = data.existing_user_id;
            if (existingId && form.avatar_file) {
              // try patch avatar to existing id
              try {
                const afd = new FormData();
                afd.append("avatar_file", form.avatar_file as File);
                const config2 = {
                  headers: { Authorization: `Bearer ${token}` },
                  transformRequest: [(data: any, headers: any) => {
                    if (headers && headers["Content-Type"]) delete headers["Content-Type"];
                    return data;
                  }]
                };
                await api.patch(`/users/${existingId}`, afd, config2);
                setMessage("Avatar atualizado para usuário existente.");
                setOpen(false);
                return;
              } catch (patchErr) {
                console.error("Falha ao atualizar avatar do usuário existente:", patchErr);
                setError("Usuário já existe; falha ao atualizar avatar.");
                return;
              }
            }
            setError(data.detail || "Conflito ao salvar usuário.");
            return;
          }

          const detail = extractErrorMessage(err);
          setError(detail);
          console.error("Erro salvar usuário (multipart):", err);
          return;
        }
      }

      // No file -> send JSON
      try {
        // remove empty password when editing
        if (isEdit && !payload.password) delete payload.password;

        await method(url, payload, { headers: { Authorization: `Bearer ${token}` } });

        setMessage(isEdit ? "Usuário atualizado com sucesso!" : "Usuário criado com sucesso!");
        setForm({ ...initialForm });
        setEditUser(null);
        setOpen(false);
      } catch (err: any) {
        // handle 409 existing_user_id
        if (err?.response?.status === 409) {
          const data = err.response.data || {};
          const existingId = data.existing_user_id;
          if (existingId && (form.avatar_file)) {
            try {
              const afd = new FormData();
              afd.append("avatar_file", form.avatar_file as File);
              await api.patch(`/users/${existingId}`, afd, {
                headers: { Authorization: `Bearer ${token}` },
                transformRequest: [(data: any, headers: any) => {
                  if (headers && headers["Content-Type"]) delete headers["Content-Type"];
                  return data;
                }]
              });
              setMessage("Avatar atualizado para usuário existente.");
              setOpen(false);
              return;
            } catch (patchErr) {
              console.error("Falha ao atualizar avatar do usuário existente:", patchErr);
              setError("Usuário já existe; falha ao atualizar avatar.");
              return;
            }
          }
          setError(data.detail || "Conflito ao salvar usuário.");
          return;
        }

        const detail = extractErrorMessage(err);
        setError(detail);
        console.error("Erro salvar usuário (json):", err);
      }
    }

    // substitua/certifique-se que exista apenas esta versão de handleEdit
    function handleEdit(user: UserForm) {
      setForm({
        ...user,
        full_name: user.nome || user.full_name || "",
        password: "",
        avatar_file: null,
        // se o usuário tem custom_role e role_id está ausente/null, exibir "Outros"
        role: (user.custom_role && (user.role_id === null || user.role_id === undefined)) ? "other" : undefined,
        custom_role: user.custom_role ?? undefined,
        cref: user.cref ?? "",
        bank_name: user.bank_name ?? "",
        pix: user.pix ?? "",
        bank_account: user.bank_account ?? "",
        agency: user.agency ?? "",
      } as UserForm);
      setEditUser(user);
      setOpen(true);
      if (user.avatar_url) {
        setSelectedPhotoUrl(getAvatarSrc(user.avatar_url));
      } else {
        setSelectedPhotoUrl(null);
      }
    }

  function handleDelete(id?: number) {
    if (!id) return;
    if (window.confirm("Tem certeza que deseja excluir este usuário?")) {
      api.delete(`/users/${id}`, { headers: { Authorization: `Bearer ${token}` } })
        .then(() => {
          setMessage('Usuário excluído com sucesso!');
          setUsers(prev => prev.filter(u => u.id !== id));
        })
        .catch((err: any) => {
          const detail = extractErrorMessage(err);
          setError(detail || "Erro ao excluir usuário.");
          console.error("Erro delete user:", err);
        });
    }
  }

  async function handleToggleStatus(user: UserForm) {
    const newStatus = !user.is_active;
    setError(null);

    const payload: any = {
      is_active: Boolean(newStatus),
      role_id: user.role_id !== undefined ? Number(user.role_id) : undefined,
      nome: user.nome ?? user.full_name ?? user.username ?? undefined,
      email: user.email ?? undefined,
      cref: user.cref ?? undefined,
    };
    Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

    try {
      await api.patch(`/users/${user.id}`, payload, { headers: { Authorization: `Bearer ${token}` } });
      setMessage(`Usuário ${newStatus ? "ativado" : "desativado"} com sucesso!`);
      setUsers(prev => prev.map(u => u.id === user.id ? ({ ...u, is_active: newStatus }) : u));
    } catch (err: any) {
      const detail = extractErrorMessage(err);
      setError(detail || "Erro ao atualizar status do usuário.");
      console.error("Erro ao alternar status:", err);
      if ((err as any)?.response) console.debug("Server response:", (err as any).response.data);
    }
  }

  function handleCreate() {
    setForm({ ...initialForm });
    setEditUser(null);
    setSelectedPhotoUrl(null);
    setOpen(true);
  }

  function handleCopyInviteLink() {
    if (!schemaName) {
      setMessage("Schema do tenant não encontrado!");
      return;
    }
    const url = `${window.location.origin}/cadastro?schema_name=${schemaName}`;
    navigator.clipboard.writeText(url);
    setMessage("Link de cadastro copiado para a área de transferência!");
  }

  function handleOpenPhotoModal(url: string) {
    setSelectedPhotoUrl(url);
    setOpenPhotoModal(true);
  }

  // derived filtered list (name or email)
  const filteredUsers = useMemo(() => {
    const q = (filter || "").trim().toLowerCase();
    if (!q) return users;
    return users.filter(u => {
      const name = (u.full_name || u.nome || u.username || "").toString().toLowerCase();
      const email = (u.email || "").toString().toLowerCase();
      return name.includes(q) || email.includes(q);
    });
  }, [users, filter]);

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Usuários do Sistema</Typography>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }} alignItems="center">
        <TextField
          label="Pesquisar por nome ou e-mail"
          variant="outlined"
          size="small"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search fontSize="small" />
              </InputAdornment>
            ),
            endAdornment: filter ? (
              <InputAdornment position="end">
                <IconButton size="small" onClick={() => setFilter("")}>
                  <Clear fontSize="small" />
                </IconButton>
              </InputAdornment>
            ) : undefined
          }}
          sx={{ width: 360 }}
        />

        <Button
          variant="outlined"
          startIcon={<ContentCopy />}
          onClick={handleCopyInviteLink}
        >
          Copiar link para cadastro público
        </Button>

        <Box sx={{ flex: 1 }} />

        <Typography variant="body2" color="textSecondary">
          {filteredUsers.length} / {users.length} usuários
        </Typography>
      </Stack>

      {loading && <Typography>Carregando...</Typography>}
      {error && <Alert severity="error">{error}</Alert>}
      {message && <Alert severity="success">{message}</Alert>}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Foto</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Nome Completo</TableCell>
              <TableCell>Username</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Função</TableCell>
              <TableCell>CREF</TableCell>
              <TableCell>Departamento</TableCell>
              <TableCell>Instituição</TableCell>
              <TableCell>Banco</TableCell>
              <TableCell>PIX</TableCell>
              <TableCell>Conta</TableCell>
              <TableCell>Agência</TableCell>
              <TableCell>Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredUsers.map(u => (
              <TableRow key={u.id}>
                <TableCell>
                  {u.avatar_url && (
                    <Avatar
                      src={getAvatarSrc(u.avatar_url)}
                      alt={u.full_name || u.nome || u.username}
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleOpenPhotoModal(getAvatarSrc(u.avatar_url))}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Switch
                    checked={!!u.is_active}
                    onChange={() => handleToggleStatus(u)}
                    color="primary"
                  />
                </TableCell>
                <TableCell>{u.full_name || u.nome || '-'}</TableCell>
                <TableCell>{u.username}</TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>
                  {ROLES.find(r => r.value === u.role_id)?.label || u.role || "-"}
                </TableCell>
                <TableCell>{u.cref || '-'}</TableCell>
                <TableCell>{u.department || '-'}</TableCell>
                <TableCell>{u.institution || '-'}</TableCell>
                <TableCell>{u.bank_name || '-'}</TableCell>
                <TableCell>{u.pix || '-'}</TableCell>
                <TableCell>{u.bank_account || '-'}</TableCell>
                <TableCell>{u.agency || '-'}</TableCell>
                <TableCell>
                  <IconButton onClick={() => handleEdit(u)}><Edit /></IconButton>
                  <IconButton onClick={() => handleDelete(u.id)}><Delete /></IconButton>
                </TableCell>
              </TableRow>
            ))}
            {filteredUsers.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={14}>
                  <Typography textAlign="center" sx={{ py: 2 }}>Nenhum usuário encontrado.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
        <Button variant="contained" onClick={handleCreate}>Criar Usuário</Button>
        <Button variant="outlined" onClick={() => setForm({ ...initialForm })}>Limpar</Button>
      </Stack>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editUser ? "Editar Usuário" : "Criar Novo Usuário"}</DialogTitle>
        <DialogContent>
          <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1 }}>
            <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 2 }}>
              {selectedPhotoUrl ? (
                <Avatar src={selectedPhotoUrl} sx={{ width: 56, height: 56 }} />
              ) : (
                <Avatar sx={{ width: 56, height: 56 }}>
                  {(form.full_name || form.nome || form.username || '').split(' ').slice(0,2).map(n => n[0]).join('')}
                </Avatar>
              )}
              <Typography variant="subtitle1">
                {form.full_name || form.nome || form.username}
              </Typography>
            </Stack>

            {/* NEW: file input for avatar (create & edit) */}
            <input
              id="avatar_file"
              name="avatar_file"
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              style={{ marginBottom: 12 }}
            />

            <TextField label="Nome Completo" name="full_name" value={form.full_name || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Username" name="username" value={form.username || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Email" name="email" value={form.email || ""} onChange={handleChange} fullWidth margin="normal" required />
            {!editUser && (
              <TextField label="Senha" name="password" type="password" value={form.password || ""} onChange={handleChange} fullWidth margin="normal" required />
            )}
            {editUser && (
              <TextField label="Nova senha (se quiser trocar)" name="password" type="password" value={form.password || ""} onChange={handleChange} fullWidth margin="normal" />
            )}

            <TextField
              label="Função"
              name="role"
              select
              value={form.role ?? (form.role_id ?? 1)}
              onChange={(e) => {
                const v = e.target.value;
                if (v === "other") {
                  setForm({ ...form, role: "other", role_id: undefined });
                } else {
                  setForm({ ...form, role: undefined, role_id: Number(v), custom_role: undefined });
                }
              }}
              fullWidth
              margin="normal"
              required
            >
              {ROLES.map(r => (
                <MenuItem key={String(r.value)} value={r.value}>{r.label}</MenuItem>
              ))}
            </TextField>

            {form.role === "other" && (
              <TextField
                label="Descreva o papel (Outros)"
                name="custom_role"
                value={form.custom_role || ""}
                onChange={(e) => setForm({ ...form, custom_role: e.target.value })}
                fullWidth
                margin="normal"
                required
              />
            )}
            <TextField
              label="CREF (registro profissional)"
              name="cref"
              value={form.cref || ""}
              onChange={handleChange}
              fullWidth
              margin="normal"
              helperText="Número do registro (opcional)"
            />

            <TextField label="CPF" name="cpf" value={form.cpf || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Telefone" name="phone" value={form.phone || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Departamento" name="department" value={form.department || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Instituição" name="institution" value={form.institution || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Data de Nascimento" name="birth_date" value={form.birth_date || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Observações" name="notes" value={form.notes || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Endereço" name="address" value={form.address || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Especialidade" name="specialty" value={form.specialty || ""} onChange={handleChange} fullWidth margin="normal" />

            {/* Banking fields in admin form */}
            <TextField label="Nome do Banco" name="bank_name" value={form.bank_name || ""} onChange={handleChange} fullWidth margin="normal" helperText="Nome do banco (opcional)" />
            <TextField label="PIX" name="pix" value={form.pix || ""} onChange={handleChange} fullWidth margin="normal" helperText="Chave PIX (opcional)" />
            <TextField label="Conta corrente" name="bank_account" value={form.bank_account || ""} onChange={handleChange} fullWidth margin="normal" helperText="Número da conta (opcional)" />
            <TextField label="Agência" name="agency" value={form.agency || ""} onChange={handleChange} fullWidth margin="normal" helperText="Agência (opcional)" />

            <FormControlLabel
              control={
                <Checkbox
                  name="accepted_terms"
                  checked={!!form.accepted_terms}
                  onChange={handleChange}
                  sx={{ mt: 2 }}
                />
              }
              label="Aceitou Termos?"
            />
            <TextField
              label="Status"
              name="is_active"
              select
              value={form.is_active ? "ativo" : "inativo"}
              onChange={(e) => setForm({ ...form, is_active: e.target.value === "ativo" })}
              fullWidth
              margin="normal"
            >
              <MenuItem value="ativo">Ativo</MenuItem>
              <MenuItem value="inativo">Inativo</MenuItem>
            </TextField>
            <FormControlLabel
              control={
                <Checkbox
                  name="is_admin"
                  checked={!!form.is_admin}
                  onChange={handleChange}
                  sx={{ mt: 2 }}
                />
              }
              label="É admin?"
            />
            <DialogActions>
              <Button onClick={() => { setOpen(false); if (selectedPhotoUrl) { URL.revokeObjectURL(selectedPhotoUrl); setSelectedPhotoUrl(null); } }}>Cancelar</Button>
              <Button type="submit" variant="contained">{editUser ? "Salvar" : "Criar"}</Button>
            </DialogActions>
          </Box>
        </DialogContent>
      </Dialog>

      <Dialog open={openPhotoModal} onClose={() => { setOpenPhotoModal(false); /* do not revoke preview here if still used */ }} maxWidth="md">
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Foto do usuário
          </Typography>
          <img
            src={selectedPhotoUrl || ""}
            alt="Foto do usuário"
            style={{ maxWidth: 500, maxHeight: 500, borderRadius: 16, boxShadow: '0 0 12px #0002' }}
          />
          <Button onClick={() => setOpenPhotoModal(false)} sx={{ mt: 2 }}>
            Fechar
          </Button>
        </Box>
      </Dialog>
    </Box>
  );
}
