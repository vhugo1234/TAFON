import React, { useState, ChangeEvent, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box, TextField, Button, Typography, Alert, Checkbox, FormControlLabel, MenuItem, Paper, Stack, Avatar, Dialog, DialogTitle, DialogContent, DialogActions
} from '@mui/material';
import PhotoCamera from '@mui/icons-material/PhotoCamera';
import api from '../lib/api';

// Modelo do usuÃ¡rio pÃºblico cadastrado (frontend)
type PublicUserForm = {
  username: string;
  email: string;
  password: string;
  full_name: string;   // kept for compatibility
  nome?: string;       // also send 'nome' for backends expecting Portuguese field
  cpf: string;
  phone: string;
  department: string;
  institution: string;
  birth_date: string;
  notes: string;
  address: string;
  avatar_file: File | null;
  specialty: string;
  role: string;        // string role (frontend)
  role_id?: number;    // numeric role id fallback (backend may expect)
  tenant_id: string;
  accepted_terms: boolean;
};

const ROLES = [
  { value: 'professor', label: 'Professor', id: 3 },
  { value: 'revisor', label: 'Revisor', id: 4 },
  { value: 'diagramador', label: 'Diagramador', id: 5 }
];

const initialForm: PublicUserForm = {
  username: "",
  email: "",
  password: "",
  full_name: "",
  nome: undefined,
  cpf: "",
  phone: "",
  department: "",
  institution: "",
  birth_date: "",
  notes: "",
  address: "",
  avatar_file: null,
  specialty: "",
  role: "professor",
  role_id: ROLES.find(r => r.value === 'professor')?.id,
  tenant_id: "",
  accepted_terms: false,
};

const TERM_TEXT = `
Termo de Uso e SeguranÃ§a da Plataforma StockWise

... (omitido para brevidade) ...
`;

export default function PublicRegisterPage() {
  const [searchParams] = useSearchParams();

  // extraÃ§Ã£o flexÃ­vel do tenant a partir de query params
  const schemaParam = searchParams.get('schema_name') ?? searchParams.get('schema');
  const paramCandidates = [
    searchParams.get('tenant_id'),
    schemaParam ? (schemaParam.split(':')[0] ?? schemaParam) : null,
    searchParams.get('tenant'),
    searchParams.get('t'),
  ];
  const initialTenantFromUrl = (paramCandidates.find(x => x && x.trim() !== "") ?? "") as string;

  // tenantId virÃ¡ do link; nÃ£o exibimos campo manual ao usuÃ¡rio conforme solicitado
  const [tenantId] = useState<string>(initialTenantFromUrl);

  const [form, setForm] = useState<PublicUserForm>({ ...initialForm, tenant_id: tenantId });
  useEffect(() => {
    setForm(prev => ({ ...prev, tenant_id: tenantId }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Termo modal
  const [termoOpen, setTermoOpen] = useState(false);
  const [termoLido, setTermoLido] = useState(false);

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const { name, value, type, checked, files } = e.target;
    if (type === "checkbox") {
      setForm((f) => ({ ...f, [name]: checked }));
    } else if (type === "file" && files) {
      setForm((f) => ({ ...f, avatar_file: files[0] }));
      setAvatarPreview(URL.createObjectURL(files[0]));
    } else {
      // if role changed, also set role_id fallback
      if (name === "role") {
        const roleStr = String(value);
        const r = ROLES.find(rr => rr.value === roleStr);
        setForm((f) => ({ ...f, role: roleStr, role_id: r?.id }));
      } else {
        setForm((f) => ({ ...f, [name]: value }));
      }
    }
  }

  function handleAbrirTermo() { setTermoOpen(true); }
  function handleFecharTermo() { setTermoOpen(false); setTermoLido(true); }

  // Tenant-aware POST that tries a small set of likely endpoints (relative to api.baseURL).
  async function postWithFallback(formData: FormData, tenantId?: string) {
    const candidates: string[] = [];

    if (tenantId && tenantId.trim() !== "") {
      candidates.push(`/tenants/${encodeURIComponent(tenantId)}/public/register`);
      candidates.push(`/tenants/${encodeURIComponent(tenantId)}/register`);
      candidates.push(`/tenants/${encodeURIComponent(tenantId)}/users/`);
    }

    candidates.push('/users/register');
    candidates.push('/users/');
    candidates.push('/register');
    candidates.push('/public/register');

    let lastErr: any = null;
    try {
      // @ts-ignore
      console.debug('[PublicRegister] api.baseURL =', api.defaults?.baseURL);
    } catch {}

    for (const path of candidates) {
      try {
        console.debug('[PublicRegister] Trying POST', path);
        const resp = await api.post(path, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        console.debug('[PublicRegister] Success at', path, resp);
        return resp;
      } catch (err: any) {
        lastErr = err;
        const status = err?.response?.status;
        console.warn(`[PublicRegister] Failed ${path} =>`, status ?? err?.message);
        if (status === 404 || status === 405) continue;
        throw err;
      }
    }

    const msg = 'Nenhum endpoint aceitou o cadastro. Verifique a rota de registro no backend.';
    const wrapper = new Error(msg);
    (wrapper as any).inner = lastErr;
    throw wrapper;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSuccess(null);
    setError(null);

    if (!tenantId || tenantId.trim() === "") {
      setError("Registro disponÃ­vel somente via link institucional. Abra o link fornecido pela sua instituiÃ§Ã£o.");
      return;
    }

    // basic client-side validation
    for (const [key, value] of Object.entries(form)) {
      if (
        key !== "avatar_file" &&
        key !== "notes" &&
        key !== "accepted_terms" &&
        typeof value === "string" &&
        value.trim() === ""
      ) {
        setError("Preencha todos os campos obrigatÃ³rios.");
        return;
      }
    }
    if (!form.avatar_file) {
      setError("A foto Ã© obrigatÃ³ria.");
      return;
    }
    if (!form.accepted_terms) {
      setError("Ã‰ obrigatÃ³rio aceitar os Termos de Uso e SeguranÃ§a para se cadastrar.");
      return;
    }

    // build FormData: send both Portuguese and English name fields, and a role_id fallback
    const formData = new FormData();
    formData.append("username", form.username);
    formData.append("email", form.email);
    formData.append("password", form.password);
    formData.append("full_name", form.full_name);
    // also append 'nome' to support backends expecting Portuguese field
    formData.append("nome", form.full_name || form.nome || form.username);
    formData.append("cpf", form.cpf);
    formData.append("phone", form.phone);
    formData.append("department", form.department);
    formData.append("institution", form.institution);
    formData.append("birth_date", form.birth_date);
    formData.append("notes", form.notes);
    formData.append("address", form.address);
    formData.append("specialty", form.specialty);
    formData.append("role", form.role);
    if (form.role_id) formData.append("role_id", String(form.role_id));
    formData.append("accepted_terms", String(form.accepted_terms));
    formData.append("tenant_id", tenantId);
    if (form.avatar_file) formData.append("avatar_file", form.avatar_file);

    try {
      const resp = await postWithFallback(formData, tenantId);
      // If backend returned a body with message, show it
      const data = resp?.data;
      setSuccess(data?.message ?? 'Cadastro enviado! Aguarde a aprovaÃ§Ã£o do administrador.');
      setForm({ ...initialForm, tenant_id: tenantId });
      setAvatarPreview(null);
      setTermoLido(false);
    } catch (err: any) {
      console.error("Erro ao enviar cadastro (postWithFallback):", err);

      // network / CORS detection
      if (err?.message && (err.message.includes('Network Error') || err.code === 'ERR_NETWORK')) {
        setError('Erro de rede ou CORS: verifique se o backend estÃ¡ rodando e permitindo requisiÃ§Ãµes deste frontend (CORS). Confira o console do backend tambÃ©m.');
        return;
      }

      if (err?.message && err.message.includes('Nenhum endpoint')) {
        setError(err.message);
        return;
      }

      if (err?.response) {
        console.groupCollapsed(`Server responded ${err.response.status}`);
        console.log('headers:', err.response.headers);
        console.log('data:', err.response.data);
        console.groupEnd();

        const data = err.response.data;
        if (!data) {
          setError(`Erro ${err.response.status} do servidor`);
          return;
        }
        if (Array.isArray(data.detail)) {
          const msg = data.detail.map((d: any) => {
            if (typeof d === 'string') return d;
            if (d?.loc && d?.msg) return `${d.loc.join('.')}: ${d.msg}`;
            return JSON.stringify(d);
          }).join(' ; ');
          setError(msg);
          return;
        }
        if (typeof data.detail === 'string') {
          setError(data.detail);
          return;
        }
        if (data.message) {
          setError(String(data.message));
          return;
        }
        setError(JSON.stringify(data));
        return;
      }

      setError('Erro ao enviar cadastro. Veja o console do navegador e do backend para detalhes.');
    }
  }

  const tenantMissing = !tenantId || tenantId.trim() === "";

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f5f6fa', display: 'flex', alignItems: 'center' }}>
      <Paper elevation={4} sx={{ p: { xs: 2, md: 4 }, maxWidth: 520, mx: 'auto', borderRadius: 5 }}>
        <Stack direction="column" alignItems="center" spacing={1} sx={{ mb: 2 }}>
          <Avatar sx={{ width: 64, height: 64, mb: 1, bgcolor: "#1976d2", fontWeight: "bold" }}>S</Avatar>
          <Typography variant="h4" fontWeight="bold" color="primary">StockWise</Typography>
        </Stack>

        <Typography color="text.secondary" align="center" gutterBottom>
          Preencha todos os campos obrigatÃ³rios para realizar seu cadastro.
        </Typography>

        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

        {tenantMissing && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Registro disponÃ­vel somente via link institucional. Abra o link fornecido pela sua instituiÃ§Ã£o. Se vocÃª recebeu um cÃ³digo, peÃ§a ao administrador o link completo.
          </Alert>
        )}

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
          <Stack direction="column" alignItems="center" spacing={1} sx={{ mb: 2 }}>
            <Avatar
              src={avatarPreview || undefined}
              sx={{ width: 90, height: 90, fontSize: 40, bgcolor: "#e3e3e3" }}
            />
            <Button
              variant="contained"
              component="label"
              color="secondary"
              startIcon={<PhotoCamera />}
              sx={{ borderRadius: 3, fontWeight: 'bold' }}
            >
              Enviar Foto (obrigatÃ³rio)
              <input
                type="file"
                accept="image/*"
                capture="user"
                style={{ display: 'none' }}
                name="avatar_file"
                onChange={handleChange}
              />
            </Button>
          </Stack>

          <TextField label="Nome Completo" name="full_name" value={form.full_name} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Username" name="username" value={form.username} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Email" name="email" value={form.email} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Senha" name="password" type="password" value={form.password} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="CPF" name="cpf" value={form.cpf} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Telefone" name="phone" value={form.phone} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Departamento" name="department" value={form.department} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="InstituiÃ§Ã£o" name="institution" value={form.institution} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Data de Nascimento" name="birth_date" type="date" value={form.birth_date} onChange={handleChange} fullWidth margin="normal" InputLabelProps={{ shrink: true }} required />
          <TextField label="ObservaÃ§Ãµes" name="notes" value={form.notes} onChange={handleChange} fullWidth margin="normal" />
          <TextField label="EndereÃ§o" name="address" value={form.address} onChange={handleChange} fullWidth margin="normal" required />
          <TextField
            label="FunÃ§Ã£o"
            name="role"
            select
            value={form.role}
            onChange={handleChange}
            fullWidth
            margin="normal"
            required
          >
            {ROLES.map(r => (
              <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
            ))}
          </TextField>
          <TextField label="Especialidade" name="specialty" value={form.specialty} onChange={handleChange} fullWidth margin="normal" required />

          <Box sx={{ mt: 2 }}>
            <Button variant="text" color="primary" onClick={handleAbrirTermo}>
              Ler Termo de Uso e SeguranÃ§a
            </Button>
            <FormControlLabel
              control={
                <Checkbox
                  name="accepted_terms"
                  checked={form.accepted_terms}
                  onChange={handleChange}
                  disabled={!termoLido}
                />
              }
              label="Li e aceito o Termo de Uso e SeguranÃ§a da Plataforma StockWise"
            />
            <Dialog open={termoOpen} onClose={handleFecharTermo} maxWidth="md" fullWidth>
              <DialogTitle>Termo de Uso e SeguranÃ§a da Plataforma StockWise</DialogTitle>
              <DialogContent dividers>
                <Typography variant="body2" align="left" sx={{ whiteSpace: "pre-line" }}>
                  {TERM_TEXT}
                </Typography>
              </DialogContent>
              <DialogActions>
                <Button variant="contained" color="primary" onClick={handleFecharTermo}>
                  Fechar e prosseguir
                </Button>
              </DialogActions>
            </Dialog>
          </Box>

          <Button
            type="submit"
            variant="contained"
            color="primary"
            fullWidth
            sx={{ mt: 3, fontWeight: 'bold', borderRadius: 3 }}
            disabled={tenantMissing}
          >
            Cadastrar
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}

