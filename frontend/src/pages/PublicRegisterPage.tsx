import React, { useState, ChangeEvent, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box, TextField, Button, Typography, Alert, Checkbox, FormControlLabel, MenuItem, Paper, Stack, Avatar, Dialog, DialogTitle, DialogContent, DialogActions, CircularProgress
} from '@mui/material';
import PhotoCamera from '@mui/icons-material/PhotoCamera';
import api from '../lib/api';

// Modelo do usuário público cadastrado (frontend)
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
  // role stored as string (select returns strings). 'other' is literal.
  role: string;
  role_id?: number | null;    // numeric role id fallback (backend may expect)
  tenant_id: string;
  accepted_terms: boolean;
  // CREF (registro profissional) — requerido para algumas roles
  cref?: string;
  // banking fields (new)
  bank_name?: string;
  pix?: string;
  bank_account?: string;
  agency?: string;
};

const ROLES: Array<{ value: string; label: string; id?: number }> = [
  { value: '1', label: "Administrador Geral" },
  { value: '2', label: "Coordenador Geral" },
  { value: '3', label: "Coordenador de Educação Física" },
  { value: '4', label: "Avaliador de Educação Física" },
  { value: '5', label: "Apoio" },
  { value: '6', label: "Técnico de AudioVisual" },
  { value: '7', label: "Volantes" },
  { value: '8', label: "Fiscais" },
  { value: 'other', label: "Outros" },
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
  role: '1',
  role_id: 1,
  tenant_id: "",
  accepted_terms: false,
  cref: "",
  // banking defaults
  bank_name: "",
  pix: "",
  bank_account: "",
  agency: "",
};

const TERM_TEXT = `
Versão: 1.0
Vigência: [2026-01-09]

Resumo rápido
Ao aceitar este Termo você autoriza o tratamento dos seus dados cadastrais pela TAF ON, concorda em fornecer informações verdadeiras (incluindo CREF, quando aplicável), aceita as condições de uso da plataforma e reconhece que seu acesso poderá depender de aprovação do administrador.

1. Partes
Este Termo é celebrado entre o Usuário (pessoa natural que realiza o cadastro) e a Operadora da Plataforma TAF ON ("Plataforma", "Nós"), com finalidade de regular o uso da aplicação, serviços e funcionalidades disponibilizadas no ambiente.

2. Objeto
Este Termo regula:
- o cadastro de usuários por meio do formulário público;
- o tratamento, armazenamento e eventual publicação de dados e arquivos de avatar;
- as regras de segurança, responsabilidade e conduta na utilização da Plataforma.

3. Cadastro, dados e CREF
3.1. O Usuário concorda em fornecer dados verdadeiros e atualizados no cadastro (nome, username, e-mail, CPF, telefone, instituição, função, CREF quando aplicável, etc.).
3.2. Para as funções "Coordenador de Educação Física" e "Avaliador de Educação Física" (ou outras que venham a ser definidas), o Usuário deve informar seu registro profissional (CREF). A Plataforma poderá verificar ou validar esse dado conforme políticas internas.
3.3. O não fornecimento de informações exigidas pode resultar em impossibilidade de completar o cadastro ou uso restrito da conta.

4. Criação, ativação e aprovação de conta
4.1. Após o envio do cadastro, o Usuário poderá:
  a) Ser ativado automaticamente e receber acesso imediato; ou
  b) Ter a conta criada em estado pendente, aguardando aprovação do administrador.
  4.2. A política de ativação depende das regras do tenant e do endpoint utilizado. Quando a aprovação administrativa for exigida, o Usuário será notificado e não terá acesso total até a aprovação.

5. Avatar e conteúdos enviados
5.1. O Usuário pode enviar uma imagem de avatar. A imagem não deve violar direitos de terceiros, nem conter material ofensivo, discriminatório, pornográfico ou ilegal.
5.2. Ao enviar arquivos para a Plataforma, o Usuário concede à Operadora licença para armazenar, processar e exibir essas imagens, dentro do contexto da prestação de serviço ao tenant.
5.3. A Plataforma não é responsável por conteúdo que viole terceiros, mas pode remover ou bloquear conteúdo mediante notificação.

6. Tratamento de dados pessoais e privacidade
6.1. Os dados pessoais fornecidos serão tratados para execução do serviço (criação de conta, autenticação, administração do tenant) e conforme a Política de Privacidade da Plataforma.
6.2. As bases legais incluem: execução de contrato/serviço, consentimento do usuário e cumprimento de obrigações legais.
6.3. O Usuário pode, nos termos da legislação aplicável, solicitar acesso, retificação, exclusão ou portabilidade dos seus dados. Para exercer esses direitos, contate: [endereço de e-mail de contato].
6.4. Dados sensíveis ou de saúde não devem ser incluídos no cadastro público sem autorização específica.

7. Segurança
7.1. A Plataforma adota medidas técnicas e administrativas razoáveis para proteger os dados contra acesso não autorizado, perda ou alteração. Contudo, nenhum sistema é absolutamente seguro; o Usuário também deve:
  - usar senhas fortes,
  - não compartilhar credenciais,
  - notificar imediatamente qualquer uso não autorizado.
7.2. A Plataforma poderá impor requisitos adicionais (ex.: autenticação multifator) conforme política do tenant.

8. Proibições e uso adequado
8.1. É vedado ao Usuário:
  - usar a Plataforma para fins ilegais;
  - inserir conteúdo que viole direitos de propriedade intelectual ou direitos de terceiros;
  - tentar burlar mecanismos de segurança da Plataforma.
8.2. Violações podem resultar em suspensão ou exclusão de conta, sem prejuízo de responsabilidades civis e criminais.

9. Propriedade intelectual
9.1. A Plataforma e seus serviços, interfaces, marcas e materiais são de titularidade da Operadora, salvo conteúdos fornecidos pelos Usuários.
9.2. Ao utilizar a Plataforma o Usuário concede licença não exclusiva para exibir e processar o conteúdo enviado, quando necessário à prestação do serviço.

10. Limitação de responsabilidade
10.1. A Plataforma não garante disponibilidade contínua e ininterrupta; interrupções programadas ou por força maior podem ocorrer.
10.2. A Operadora não será responsável por danos indiretos, lucros cessantes ou consequências decorrentes do uso indevido da Plataforma, salvo disposição legal em contrário.

11. Retenção e exclusão de dados
11.1. Dados de cadastro serão mantidos enquanto a conta existir ou conforme obrigação legal.
11.2. O Usuário pode solicitar exclusão da conta; a exclusão pode ser sujeita a regras do tenant e retentiva legal (logs, obrigações fiscais).

12. Alterações do Termo
12.1. A Plataforma pode revisar este Termo. Alterações materiais serão comunicadas e, quando exigido, o consentimento do Usuário será solicitado.
12.2. A versão em vigor está indicada no cabeçalho (Versão / Vigência).

13. Contato
13.1. Para dúvidas, solicitações de direitos (acesso/retificação/exclusão) e denúncias sobre conteúdo, contate: [email@tafon.com] (substituir pelo contato real).
13.2. Informe em seu contato: nome completo, username, tenant (se aplicável) e descrição do pedido.

14. Disposições finais e foro
14.1. Este Termo será regido pela legislação do país aplicável (substituir conforme jurisdição). Qualquer disputa será submetida ao foro competente indicado pela Operadora, salvo disposição legal em contrário.

Declaro que li, compreendi e aceito os termos acima ao marcar a opção "Li e aceito o Termo de Uso e Segurança da Plataforma TAF ON".
`;

// util: cria URL absoluta para o arquivo estático no backend (static/logos)
function getStaticLogoUrl(filename?: string) {
  if (!filename) return "";
  const raw = (import.meta.env.VITE_API_URL || "http://localhost:8000") as string;
  const apiBase = raw.replace(/\/api(\/.*)?$/, '').replace(/\/+$/, '');
  if (filename.startsWith("http://") || filename.startsWith("https://")) return filename;
  if (filename.startsWith("/")) return `${apiBase}${filename}`;
  // arquivo esperado em: <backend_base>/static/logos/{filename}
  return `${apiBase}/static/logos/${filename}`;
}

export default function PublicRegisterPage() {
  const [searchParams] = useSearchParams();

  const schemaParam = searchParams.get('schema_name') ?? searchParams.get('schema');
  const paramCandidates = [
    searchParams.get('tenant_id'),
    schemaParam ? (schemaParam.split(':')[0] ?? schemaParam) : null,
    searchParams.get('tenant'),
    searchParams.get('t'),
  ];
  const initialTenantFromUrl = (paramCandidates.find(x => x && x.trim() !== "") ?? "") as string;

  const [tenantId] = useState<string>(initialTenantFromUrl);

  const [form, setForm] = useState<PublicUserForm>({ ...initialForm, tenant_id: tenantId });
  useEffect(() => {
    setForm(prev => ({ ...prev, tenant_id: tenantId }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [termoOpen, setTermoOpen] = useState(false);
  const [termoLido, setTermoLido] = useState(false);

  // helper: role ids that require CREF
  const rolesRequiringCref = new Set(['3', '4']);

  // compute tenant & default logo URLs and managed logo src (falls back if tenant logo 404s)
  const defaultLogoUrl = getStaticLogoUrl("logo.png");
  const tenantLogoUrl = tenantId ? getStaticLogoUrl(`${tenantId}.png`) : defaultLogoUrl;
  const [logoSrc, setLogoSrc] = useState<string>(tenantLogoUrl);
  const [imageFailed, setImageFailed] = useState<boolean>(false);

  // keep logoSrc in sync when tenantId changes
  useEffect(() => {
    setImageFailed(false);
    setLogoSrc(tenantId ? getStaticLogoUrl(`${tenantId}.png`) : defaultLogoUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

  // Accept change events from inputs and selects
  function handleChange(e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
    const target = e.target as HTMLInputElement & { files?: FileList };
    const { name, value, type, checked, files } = target;
    if (type === "checkbox") {
      setForm((f) => ({ ...f, [name]: checked }));
    } else if (type === "file" && files) {
      setForm((f) => ({ ...f, avatar_file: files[0] }));
      setAvatarPreview(URL.createObjectURL(files[0]));
    } else {
      if (name === "role") {
        const v = String(value);
        if (v === "other") {
          setForm((f) => ({ ...f, role: "other", role_id: null }));
        } else {
          const numeric = Number(v);
          setForm((f) => ({ ...f, role: v, role_id: Number.isNaN(numeric) ? null : numeric }));
        }
      } else {
        setForm((f) => ({ ...f, [name]: value }));
      }
    }
  }

  function handleAbrirTermo() { setTermoOpen(true); }
  function handleFecharTermo() { setTermoOpen(false); setTermoLido(true); }

  // Config to ensure axios does NOT set Content-Type header manually for FormData
  const multipartConfig = {
    headers: { /* intentionally no Content-Type here */ },
    transformRequest: [(data: any, headers: any) => {
      if (headers && headers['Content-Type']) delete headers['Content-Type'];
      return data;
    }]
  };

  // Tenant-aware POST that tries a small set of likely endpoints (relative to api.baseURL).
  async function postWithFallback(formData: FormData, tenantId?: string) {
    const candidates: string[] = [];

    if (tenantId && tenantId.trim() !== "") {
      candidates.push(`/tenants/${encodeURIComponent(tenantId)}/public/register`);
    }

    candidates.push('/public/register');
    candidates.push('/register');

    let lastErr: any = null;
    try {
      // @ts-ignore
      console.debug('[PublicRegister] api.baseURL =', api.defaults?.baseURL);
    } catch {}

    for (const path of candidates) {
      try {
        console.debug('[PublicRegister] Trying POST', path);
        const resp = await api.post(path, formData, multipartConfig);
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
      setError("Registro disponível somente via link institucional. Abra o link fornecido pela sua instituição.");
      return;
    }

    // basic client-side validation
    for (const [key, value] of Object.entries(form)) {
      if (
        key !== "avatar_file" &&
        key !== "notes" &&
        key !== "accepted_terms" &&
        key !== "cref" &&
        key !== "bank_name" &&
        key !== "pix" &&
        key !== "bank_account" &&
        key !== "agency" &&
        typeof value === "string" &&
        value.trim() === ""
      ) {
        setError("Preencha todos os campos obrigatórios.");
        return;
      }
    }

    // If role requires CREF, enforce it
    if (rolesRequiringCref.has(form.role) && (!form.cref || String(form.cref).trim() === "")) {
      setError("CREF é obrigatório para a função selecionada.");
      return;
    }

    if (!form.avatar_file) {
      setError("A foto é obrigatória.");
      return;
    }
    if (!form.accepted_terms) {
      setError("É obrigatório aceitar os Termos de Uso e Segurança para se cadastrar.");
      return;
    }

    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("username", form.username);
      formData.append("email", form.email);
      formData.append("password", form.password);
      formData.append("full_name", form.full_name);
      formData.append("nome", form.full_name || form.nome || form.username);
      formData.append("cpf", form.cpf);
      formData.append("phone", form.phone);
      formData.append("department", form.department);
      formData.append("institution", form.institution);
      formData.append("birth_date", form.birth_date);
      formData.append("notes", form.notes);
      formData.append("address", form.address);
      formData.append("specialty", form.specialty);

      // role + role_id handling
      formData.append("role", String(form.role));
      if (form.role === "other") {
        formData.append("role_id", "");
      } else if (form.role_id !== undefined && form.role_id !== null) {
        formData.append("role_id", String(form.role_id));
      }

      // append CREF when present (and required)
      if (form.cref) {
        formData.append("cref", String(form.cref));
      }

      // banking fields (optional)
      if (form.bank_name) formData.append("bank_name", String(form.bank_name));
      if (form.pix) formData.append("pix", String(form.pix));
      if (form.bank_account) formData.append("bank_account", String(form.bank_account));
      if (form.agency) formData.append("agency", String(form.agency));

      formData.append("accepted_terms", String(form.accepted_terms));
      formData.append("tenant_id", tenantId);
      if (form.avatar_file) formData.append("avatar_file", form.avatar_file);

      // debug: inspect FormData entries (File shows as File object in console)
      try {
        console.debug("[PublicRegister] formData avatar_file:", form.avatar_file);
        console.debug("[PublicRegister] formData fd.get('avatar_file'):", formData.get("avatar_file"));
      } catch (e) {
        console.debug("[PublicRegister] unable to debug FormData (browser limitation)");
      }

      const resp = await postWithFallback(formData, tenantId);
      const data = resp?.data;
      setSuccess(data?.message ?? 'Cadastro enviado! Aguarde a aprovação do administrador.');
      setForm({ ...initialForm, tenant_id: tenantId });
      setAvatarPreview(null);
      setTermoLido(false);
    } catch (err: any) {
      console.error("Erro ao enviar cadastro (postWithFallback):", err);
      if (err?.message && (err.message.includes('Network Error') || err.code === 'ERR_NETWORK')) {
        setError('Erro de rede ou CORS: verifique se o backend está rodando e permitindo requisições deste frontend (CORS). Confira o console do backend também.');
      } else if (err?.message && err.message.includes('Nenhum endpoint')) {
        setError(err.message);
      } else if (err?.response) {
        const data = err.response.data;
        if (!data) {
          setError(`Erro ${err.response.status} do servidor`);
        } else if (Array.isArray(data.detail)) {
          const msg = data.detail.map((d: any) => {
            if (typeof d === 'string') return d;
            if (d?.loc && d?.msg) return `${d.loc.join('.')}: ${d.msg}`;
            return JSON.stringify(d);
          }).join(' ; ');
          setError(msg);
        } else if (typeof data.detail === 'string') {
          setError(data.detail);
        } else if (data.message) {
          setError(String(data.message));
        } else {
          setError(JSON.stringify(data));
        }
      } else {
        setError('Erro ao enviar cadastro. Veja o console do navegador e do backend para detalhes.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  const tenantMissing = !tenantId || tenantId.trim() === "";

  // initials fallback for Avatar when no logo is available
  const initials = (form.full_name || form.nome || form.username || "U")
    .split(' ')
    .map(s => s ? s[0].toUpperCase() : '')
    .slice(0, 2)
    .join('');

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f5f6fa', display: 'flex', alignItems: 'center' }}>
      <Paper elevation={4} sx={{ p: { xs: 2, md: 4 }, maxWidth: 520, mx: 'auto', borderRadius: 5 }}>
        <Stack direction="column" alignItems="center" spacing={1} sx={{ mb: 2 }}>
          {/* Logo: tenta carregar arquivo estático backend -> fallback para global logo -> fallback para Avatar */}
          {avatarPreview ? (
            <Avatar src={avatarPreview} sx={{ width: 120, height: 120, mb: 1 }} />
          ) : (
            <>
              {!imageFailed ? (
                <img
                  src={logoSrc}
                  alt="Logo"
                  style={{ width: 300  , height: 120, objectFit: "contain", borderRadius: 12 }}
                  onError={(e) => {
                    const img = e.target as HTMLImageElement;
                    if (logoSrc !== defaultLogoUrl) {
                      // try global logo next
                      setLogoSrc(defaultLogoUrl);
                      img.src = defaultLogoUrl;
                    } else {
                      // no logo available -> show Avatar fallback
                      setImageFailed(true);
                    }
                  }}
                />
              ) : (
                <Avatar sx={{ width: 120, height: 120, mb: 1, bgcolor: "#e3e3e3", fontSize: 40 }}>
                  {initials}
                </Avatar>
              )}
            </>
          )}
        </Stack>

        <Typography color="text.secondary" align="center" gutterBottom>
          Preencha todos os campos obrigatórios para realizar seu cadastro.
        </Typography>

        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {tenantMissing && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Registro disponível somente via link institucional. Abra o link fornecido pela sua instituição. Se você recebeu um código, peça ao administrador o link completo.
          </Alert>
        )}

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
              Enviar Foto (obrigatório)
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
          <TextField label="Instituição" name="institution" value={form.institution} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Data de Nascimento" name="birth_date" type="date" value={form.birth_date} onChange={handleChange} fullWidth margin="normal" InputLabelProps={{ shrink: true }} required />
          <TextField label="Observações" name="notes" value={form.notes || ""} onChange={handleChange} fullWidth margin="normal" helperText="Observações (opcional)"/>
          <TextField label="Endereço" name="address" value={form.address} onChange={handleChange} fullWidth margin="normal" required />
          <TextField
            label="Função"
            name="role"
            select
            value={form.role}
            onChange={handleChange}
            fullWidth
            margin="normal"
            required
          >
            {ROLES.map(r => (
              <MenuItem key={String(r.value)} value={r.value}>{r.label}</MenuItem>
            ))}
          </TextField>

          {/* Mostrar CREF apenas quando role exigir */}
          {rolesRequiringCref.has(form.role) && (
            <TextField
              label="CREF (registro profissional)"
              name="cref"
              value={form.cref || ""}
              onChange={handleChange}
              fullWidth
              margin="normal"
              required
              helperText="Informe o número do CREF (ex.: 12345-G/UF)"
            />
          )}

          <TextField label="Especialidade" name="specialty" value={form.specialty} onChange={handleChange} fullWidth margin="normal" required />

          {/* Banking fields */}
          <TextField label="Nome do Banco" name="bank_name" value={form.bank_name || ""} onChange={handleChange} fullWidth margin="normal" helperText="Nome do banco (opcional)" />
          <TextField label="PIX" name="pix" value={form.pix || ""} onChange={handleChange} fullWidth margin="normal" helperText="Chave PIX (opcional)" />
          <TextField label="Conta corrente" name="bank_account" value={form.bank_account || ""} onChange={handleChange} fullWidth margin="normal" helperText="Número da conta (opcional)" />
          <TextField label="Agência" name="agency" value={form.agency || ""} onChange={handleChange} fullWidth margin="normal" helperText="Agência (opcional)" />

          <Box sx={{ mt: 2 }}>
            <Button variant="text" color="primary" onClick={handleAbrirTermo}>
              Ler Termo de Uso e Segurança
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
              label="Li e aceito o Termo de Uso e Segurança da Plataforma TAF ON"
            />
            <Dialog open={termoOpen} onClose={handleFecharTermo} maxWidth="md" fullWidth>
              <DialogTitle>Termo de Uso e Segurança da Plataforma TAF ON</DialogTitle>
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
            disabled={tenantMissing || submitting}
            startIcon={submitting ? <CircularProgress size={18} /> : undefined}
          >
            {submitting ? 'Enviando...' : 'Cadastrar'}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
