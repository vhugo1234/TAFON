// Complete admin clients panel component
// Includes: global search, filters, summary cards, dark mode, CSV export, actions, modals, logo preview, password copy, logs, responsiveness and premium UX.
// This file should be placed in src/AdminClientsTab.tsx

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import Grid from '@mui/material/Grid';
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell,
  TableBody, Dialog, TextField, Stack, MenuItem, Chip, Tooltip,
  CircularProgress, Alert, IconButton, Divider, Snackbar,
  TablePagination, TableContainer, Fade, useTheme,
  useMediaQuery, Paper, Zoom, Avatar, InputAdornment
} from '@mui/material';
import {
  Add, Edit, Delete, FormatListNumbered, PhotoCamera, Close, Public,
  ContentCopy, InfoOutlined, Search, FileDownload, LightMode, DarkMode
} from '@mui/icons-material';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../config';
import { useNavigate } from 'react-router-dom';


interface TenantClient {
  id: number;
  name: string;
  schema_name: string;
  status: 'active' | 'inactive' | 'pending' | 'suspended' | string;
  tenant_type: string;
  created_at: string;
  responsible_name: string;
  responsible_email: string;
  responsible_phone: string | null;
  plan_type: string;
  plan_expires_at: string | null;
  users_total: number;
  assets_total: number;
  last_access: string;
  logo_url: string | null;
  dominio_url: string | null;
}

type FormState = Omit<TenantClient, 'id' | 'created_at' | 'users_total' | 'assets_total' | 'last_access'> & {
  admin_name?: string;
  admin_email?: string;
  admin_password?: string;
};

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}
const MOCK_LOGS: LogEntry[] = [
  { timestamp: new Date(Date.now() - 3600000).toISOString(), level: 'INFO', message: 'User "admin" logged in successfully.' },
  { timestamp: new Date(Date.now() - 1800000).toISOString(), level: 'WARN', message: 'Asset lookup timed out for device 10.' },
  { timestamp: new Date(Date.now() - 600000).toISOString(), level: 'ERROR', message: 'Database connection failed. Retrying...' },
];

const PLAN_OPTIONS = ['free', 'premium', 'enterprise'];
const STATUS_OPTIONS = ['active', 'inactive', 'pending', 'suspended'];
const API_URL = '/admin/';
const UPLOAD_API_URL = '/admin/upload/logo';

const initialFormState: FormState = {
  name: '',
  schema_name: '',
  status: 'active',
  tenant_type: 'premium',
  responsible_name: '',
  responsible_email: '',
  responsible_phone: null,
  plan_type: '',
  plan_expires_at: new Date().toISOString().split('T')[0],
  logo_url: null,
  dominio_url: null,
  admin_name: '',
  admin_email: '',
  admin_password: '',
};

function slugifySchema(name: string) {
  return name.toLowerCase().trim().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
}

const formatDate = (isoString: string | null) => {
  if (!isoString) return 'N/A';
  try {
    const datePart = isoString.includes('T') ? isoString.split('T')[0] : isoString;
    return new Date(datePart).toLocaleDateString('pt-BR');
  } catch (e) {
    return 'Data Inválida';
  }
}

// Modal de Logs
const LogsModal: React.FC<{ open: boolean, onClose: () => void, client: TenantClient | null, loading: boolean }> = ({ open, onClose, client, loading }) => {
  const theme = useTheme();
  const logs = MOCK_LOGS;
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <Box sx={{ p: { xs: 2, sm: 4 } }}>
        <Typography variant="h6" gutterBottom>
          Logs do Cliente: {client?.name || 'N/A'}
        </Typography>
        <Divider sx={{ mb: 2 }} />
        {loading ? (
          <Box display="flex" justifyContent="center" py={4}><CircularProgress /></Box>
        ) : (
          <Box sx={{
            maxHeight: 400,
            overflowY: 'auto',
            p: 1,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 1,
            backgroundColor: theme.palette.grey[50],
          }}>
            {logs.length > 0 ? (
              <Stack spacing={1}>
                {logs.map((log, index) => (
                  <Box key={index} sx={{ borderBottom: '1px dotted #ddd', pb: 0.5 }}>
                    <Typography variant="caption" sx={{ display: 'block' }} color="text.secondary">
                      [{formatDate(log.timestamp)} - {new Date(log.timestamp).toLocaleTimeString('pt-BR')}]
                      <Chip label={log.level} size="small" color={log.level === 'ERROR' ? 'error' : log.level === 'WARN' ? 'warning' : 'info'} sx={{ ml: 1, height: 20 }} />
                    </Typography>
                    <Typography variant="body2" sx={{ ml: 0.5, whiteSpace: 'pre-wrap' }}>
                      {log.message}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary" textAlign="center" py={3}>
                Nenhum log encontrado para este cliente.
              </Typography>
            )}
          </Box>
        )}
        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
          <Button onClick={onClose} variant="outlined">Fechar</Button>
        </Box>
      </Box>
    </Dialog>
  );
};

export default function AdminClientsTab() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  // Auth context - ready for authentication integration
  const { token: _token, loading: _authLoading, isSuperuser: _isSuperuser, logout } = useAuth();
  const navigate = useNavigate();

  // States
  const [clients, setClients] = useState<TenantClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<React.ReactNode | null>(null);
  const [openModal, setOpenModal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [selectedClient, setSelectedClient] = useState<TenantClient | null>(null);
  const [selectedLogoFile, setSelectedLogoFile] = useState<File | null>(null);
  const [adminTempPassword, setAdminTempPassword] = useState<string | null>(null);
  const [copiedPwd, setCopiedPwd] = useState(false);
  const [openLogsModal, setOpenLogsModal] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [openLogoZoom, setOpenLogoZoom] = useState(false);
  const [logoZoomUrl, setLogoZoomUrl] = useState<string | null>(null);
  // Sorting states - ready for future table header sorting implementation
  const [order, _setOrder] = useState<'asc' | 'desc'>('asc');
  const [orderBy, _setOrderBy] = useState<keyof TenantClient | 'actions'>('id');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error' | 'warning' | 'info'>('success');
  const [search, setSearch] = useState('');
  const [darkMode, setDarkMode] = useState(false);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPlan, setFilterPlan] = useState('');

  // Cards de Totais
  const totalClients = clients.length;
  const totalUsers = clients.reduce((sum, c) => sum + c.users_total, 0);
  const totalAssets = clients.reduce((sum, c) => sum + c.assets_total, 0);

  // Tabela filtrada/buscada
  const filteredClients = useMemo(() => {
    return clients.filter(c => {
      const matchesSearch = search.trim() === '' || [
        c.name, c.schema_name, c.responsible_name, c.responsible_email, c.dominio_url
      ].some(f => f && f.toLowerCase().includes(search.toLowerCase()));
      const matchesStatus = !filterStatus || c.status === filterStatus;
      const matchesPlan = !filterPlan || c.plan_type === filterPlan;
      return matchesSearch && matchesStatus && matchesPlan;
    });
  }, [clients, search, filterStatus, filterPlan]);

  const visibleClients = useMemo(() => {
    const sorted = [...filteredClients].sort((a, b) => {
      const aValue = (a as any)[orderBy];
      const bValue = (b as any)[orderBy];
      if (order === 'asc') return aValue > bValue ? 1 : -1;
      return aValue < bValue ? 1 : -1;
    });
    return sorted.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
  }, [filteredClients, order, orderBy, page, rowsPerPage]);

  // API
  const fetchClients = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get(API_URL);
      setClients(resp.data.map((c: any) => ({
        id: c.id,
        name: c.nome_empresa || c.name || `Tenant ${c.id}`,
        schema_name: c.schema_name,
        status: c.status || 'active',
        tenant_type: c.tenant_type || c.plano || 'free',
        created_at: c.created_at || c.data_criacao || new Date().toISOString(),
        responsible_name: c.responsible_name || '',
        responsible_email: c.responsible_email || '',
        responsible_phone: c.responsible_phone ?? null,
        plan_type: c.plan_type || c.plano || '',
        plan_expires_at: c.plan_expires_at || null,
        users_total: c.users_total ?? 0,
        assets_total: c.assets_total ?? 0,
        last_access: c.last_access || new Date().toISOString(),
        logo_url: c.logo_url || null,
        dominio_url: c.dominio_url || null,
      })));
    } catch (err: any) {
      // Se 401 -> logout e redirecionar para login
      if (err?.response?.status === 401) {
        setError('Sessão inválida/expirada. Redirecionando para login...');
        setSnackbarMessage('Sessão inválida. Faça login novamente.');
        setSnackbarSeverity('warning');
        setSnackbarOpen(true);
        try { logout(); } catch {}
        navigate('/login');
        return;
      }

      setError(err?.response?.data?.detail || err.message || 'Falha ao carregar a lista de clientes.');
      setSnackbarMessage('Falha ao carregar a lista de clientes.');
      setSnackbarSeverity('error');
      setSnackbarOpen(true);
     } finally {
      setLoading(false);
    }
  }, []);

  // Guarded effect: only fetch when auth finished initializing and user is superuser
  useEffect(() => {
    // Wait for auth initialization
    if (_authLoading) return;

    // No token -> skip fetch and show message
    if (!_token) {
      setLoading(false);
      setError('Usuário não autenticado. Faça login para acessar esta área.');
      return;
    }

    // Not a superuser -> don't call /admin and show restricted message
    if (!_isSuperuser) {
      setLoading(false);
      setError('Acesso restrito: apenas superusuários podem ver a lista de clientes.');
      return;
    }

    // OK: token present and user is superuser -> fetch
    fetchClients();
  }, [_authLoading, _token, _isSuperuser, fetchClients]);

  const handleSnackbarClose = () => { setSnackbarOpen(false); setCopiedPwd(false); setAdminTempPassword(null); };
  const handleCloseModal = () => setOpenModal(false);
  const handleExited = () => {
    setForm(initialFormState);
    setIsEditing(false);
    setSelectedClient(null);
    setSelectedLogoFile(null);
    setAdminTempPassword(null);
    setCopiedPwd(false);
  };
  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => { setRowsPerPage(parseInt(event.target.value, 10)); setPage(0); };
  const [form, setForm] = useState<FormState>(initialFormState);
  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => { const { name, value } = e.target; setForm(prev => ({ ...prev, [name]: value })); };
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => { if (e.target.files && e.target.files.length > 0) { const file = e.target.files[0]; setSelectedLogoFile(file); setForm(prev => ({ ...prev, logo_url: URL.createObjectURL(file) })); } };
  const handleClearFile = () => { setSelectedLogoFile(null); setForm(prev => ({ ...prev, logo_url: selectedClient?.logo_url || null })); };
  const handleOpenAdd = () => { handleExited(); setOpenModal(true); };
  const handleOpenEdit = (client: TenantClient) => {
    setSelectedClient(client);
    setIsEditing(true);
    setSelectedLogoFile(null);
    setForm({
      ...client,
      logo_url: client.logo_url ? `${BACKEND_URL}${client.logo_url}` : null, // <-- ESSA LINHA GARANTE O PATH ABSOLUTO!
      plan_expires_at: client.plan_expires_at ? client.plan_expires_at.split('T')[0] : new Date().toISOString().split('T')[0],
      admin_name: '',
      admin_email: '',
      admin_password: '',
    });
    setOpenModal(true);
  };
  const handleDelete = async (client: TenantClient) => {
    if (!window.confirm(`Confirma remoção do cliente "${client.name}"? Esta ação é irreversível.`)) return;
    setError(null);
    try {
      await api.delete(`${API_URL}${client.id}`);
      await fetchClients();
      setSnackbarMessage(`Cliente "${client.name}" deletado com sucesso.`);
      setSnackbarSeverity('success');
      setSnackbarOpen(true);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message || 'Erro ao deletar cliente.';
      setError(msg); setSnackbarMessage(msg); setSnackbarSeverity('error'); setSnackbarOpen(true);
    }
  };
  const handleOpenLogs = (client: TenantClient) => { setSelectedClient(client); setOpenLogsModal(true); setLoadingLogs(true); setTimeout(() => setLoadingLogs(false), 800); };
  const handleOpenLogoZoom = (client: TenantClient) => { const fullLogoUrl = client.logo_url ? `${BACKEND_URL}${client.logo_url}` : null; setLogoZoomUrl(fullLogoUrl); setOpenLogoZoom(true); };
  const copyPwd = () => { if (adminTempPassword) { navigator.clipboard.writeText(adminTempPassword); setCopiedPwd(true); setSnackbarMessage("Senha copiada!"); setSnackbarSeverity("success"); setSnackbarOpen(true); } };
  

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    let finalLogoUrl = form.logo_url;
    try {
      if (selectedLogoFile) {
        const formData = new FormData();
        formData.append('logo', selectedLogoFile);
        formData.append('tenant_id', isEditing && selectedClient ? String(selectedClient.id) : 'new');
        setSnackbarMessage('Enviando logo...');
        setSnackbarSeverity('info');
        setSnackbarOpen(true);
        const uploadResp = await api.post(UPLOAD_API_URL, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        finalLogoUrl = uploadResp.data.logo_url;
      }
      // Prepara o payload garantindo que só envie o que o backend espera
      const payload: any = {
        name: form.name,
        schema_name: form.schema_name && form.schema_name.trim() !== '' ? form.schema_name.trim() : slugifySchema(form.name),
        plan_type: form.plan_type || form.tenant_type || undefined,
        status: form.status,
        responsible_name: form.responsible_name,
        responsible_email: form.responsible_email,
        responsible_phone: form.responsible_phone || null,
        plan_expires_at: form.plan_expires_at || null,
        logo_url: finalLogoUrl,
        dominio_url: form.dominio_url || null,
      };

      if (form.admin_name) payload.admin_name = form.admin_name;
      if (form.admin_email) payload.admin_email = form.admin_email;
      if (form.admin_password) payload.admin_password = form.admin_password;

      let resp;
      if (isEditing && selectedClient) {
        resp = await api.put(`${API_URL}${selectedClient.id}`, payload);
        setSnackbarMessage(`Cliente "${form.name}" atualizado com sucesso.`);
        setSnackbarSeverity('success');
      } else {
        resp = await api.post(API_URL, payload);
        if (resp.data.admin_temp_password) {
          setSnackbarMessage(`Cliente criado! Senha provisória do admin: ${resp.data.admin_temp_password}`);
          setAdminTempPassword(resp.data.admin_temp_password);
          setSnackbarSeverity('info');
        } else {
          setSnackbarMessage(`Cliente "${form.name}" criado com sucesso.`);
          setSnackbarSeverity('success');
        }
      }
      setOpenModal(false);
      fetchClients();
    } catch (err: any) {
      let errorNode: React.ReactNode = "Erro ao salvar cliente.";
      // FastAPI: geralmente detail é array ou string
      if (err?.response?.data?.detail) {
        const details = err.response.data.detail;
        if (Array.isArray(details)) {
          // Renderiza como lista fácil de ler
          errorNode = (
            <ul style={{ marginLeft: 10, paddingLeft: 10 }}>
              {details.map((d: any, idx: number) => (
                <li key={idx}>
                  {d.msg ? `${d.msg}${d.loc ? " (" + d.loc.join(".") + ")" : ""}` : JSON.stringify(d)}
                </li>
              ))}
            </ul>
          );
        } else if (typeof details === "string") {
          errorNode = details;
        } else if (typeof details === "object" && details.msg) {
          errorNode = details.msg;
        } else {
          errorNode = JSON.stringify(details);
        }
      } else if (err?.message) {
        errorNode = err.message;
      }
      setError(errorNode);
      setSnackbarMessage("Erro ao salvar cliente.");
      setSnackbarSeverity("error");
      setSnackbarOpen(true);
    } finally {
      setSaving(false);
    }
  };

  // Export to CSV functionality
  const handleExportCSV = () => {
    try {
      // Prepare CSV headers
      const headers = [
        'ID',
        'Nome',
        'Schema',
        'Status',
        'Plano',
        'Responsável',
        'Email Responsável',
        'Telefone',
        'Total Usuários',
        'Total Ativos',
        'Criado em',
        'Última Acesso',
        'Expiração do Plano',
        'Domínio'
      ];

      // Prepare CSV rows
      const rows = filteredClients.map(client => [
        client.id,
        client.name,
        client.schema_name,
        client.status,
        client.plan_type || client.tenant_type,
        client.responsible_name,
        client.responsible_email,
        client.responsible_phone || 'N/A',
        client.users_total,
        client.assets_total,
        formatDate(client.created_at),
        formatDate(client.last_access),
        formatDate(client.plan_expires_at),
        client.dominio_url || 'N/A'
      ]);

      // Build CSV content
      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => {
          // Escape cells that contain commas or quotes
          const cellStr = String(cell);
          if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
            return `"${cellStr.replace(/"/g, '""')}"`;
          }
          return cellStr;
        }).join(','))
      ].join('\n');

      // Create blob and download
      const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `clientes_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setSnackbarMessage(`${filteredClients.length} clientes exportados com sucesso!`);
      setSnackbarSeverity('success');
      setSnackbarOpen(true);
    } catch (error) {
      setSnackbarMessage('Erro ao exportar CSV.');
      setSnackbarSeverity('error');
      setSnackbarOpen(true);
    }
  };

  // === UI ===
  return (
    <Box sx={{ p: { xs: 1, sm: 3 }, bgcolor: darkMode ? '#171717' : 'background.default', minHeight: '100vh', transition: '.2s' }}>
      {/* TÍTULO DA PÁGINA */}
    <Typography
      variant="h3"
      component="h1"
      fontWeight={900}
      textAlign="center"
      sx={{ mb: 4, mt: 1 }}
    >
      Administração de Clientes
    </Typography>

      {/* Totais e filtros */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid item xs={6} sm={3}><Chip label={`Clientes: ${totalClients}`} color="primary" sx={{ fontWeight: 700, fontSize: '1.15rem', py: 1, px: 2 }}/></Grid>
        <Grid item xs={6} sm={3}><Chip label={`Usuários: ${totalUsers}`} color="info" sx={{ fontWeight: 700, fontSize: '1.15rem', py: 1, px: 2 }}/></Grid>
        <Grid item xs={6} sm={3}><Chip label={`Ativos: ${totalAssets}`} color="warning" sx={{ fontWeight: 700, fontSize: '1.15rem', py: 1, px: 2 }}/></Grid>
        <Grid item xs={6} sm={3} textAlign="right">
          <Tooltip title={darkMode ? "Modo Claro" : "Modo Escuro"}>
            <IconButton onClick={() => setDarkMode(m => !m)}>
              {darkMode ? <LightMode /> : <DarkMode />}
            </IconButton>
          </Tooltip>
          <Tooltip title="Exportar CSV">
            <IconButton onClick={handleExportCSV}><FileDownload /></IconButton>
          </Tooltip>
        </Grid>
      </Grid>
      {/* Busca/Filtros */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <TextField
          placeholder="Buscar por nome, schema, responsável, email, domínio..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          variant="outlined"
          size="small"
          sx={{ minWidth: 240 }}
          InputProps={{
            startAdornment: <InputAdornment position="start"><Search /></InputAdornment>
          }}
        />
        <TextField
          label="Status"
          select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          size="small"
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="">Todos</MenuItem>
          {STATUS_OPTIONS.map(o => <MenuItem key={o} value={o}>{o}</MenuItem>)}
        </TextField>
        <TextField
          label="Plano"
          select
          value={filterPlan}
          onChange={e => setFilterPlan(e.target.value)}
          size="small"
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="">Todos</MenuItem>
          {PLAN_OPTIONS.map(o => <MenuItem key={o} value={o}>{o}</MenuItem>)}
        </TextField>
        <Button
          variant="contained"
          color="primary"
          startIcon={<Add />}
          onClick={handleOpenAdd}
          size={isMobile ? "small" : "medium"}
          sx={{ textTransform: 'none', fontWeight: 700 }}
        >
          Adicionar Novo Cliente
        </Button>
      </Stack>
      {/* Tabela */}
      <Paper elevation={isMobile ? 0 : 3} sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, mb: 2, bgcolor: darkMode ? '#222' : 'background.paper' }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {loading ? (
          <Box display="flex" justifyContent="center" alignItems="center" py={8}>
            <CircularProgress size={60} />
          </Box>
        ) : (
        <>
        <TableContainer>
          <Table sx={{ minWidth: isMobile ? 360 : 1200 }}>
            <TableHead>
              <TableRow>
                <TableCell align="left" sx={{ fontWeight: 700 }}>Logo</TableCell>
                <TableCell align="left" sx={{ fontWeight: 700 }}>Nome/Schema</TableCell>
                <TableCell align="left" sx={{ fontWeight: 700 }}>Domínio</TableCell>
                <TableCell align="left" sx={{ fontWeight: 700 }}>Responsável</TableCell>
                <TableCell align="center" sx={{ fontWeight: 700 }}>Total Usuários</TableCell>
                <TableCell align="center" sx={{ fontWeight: 700 }}>Total Ativos</TableCell>
                <TableCell align="center" sx={{ fontWeight: 700 }}>Plano/Status</TableCell>
                <TableCell align="center" sx={{ fontWeight: 700 }}>Expiração</TableCell>
                <TableCell align="left" sx={{ fontWeight: 700 }}>Último Acesso</TableCell>
                <TableCell align="center" sx={{ fontWeight: 700 }}>Ações</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {visibleClients.map((client) => (
                <TableRow key={client.id} hover sx={{ transition: '.2s', '&:hover': { bgcolor: theme.palette.action.hover } }}>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      {client.logo_url ? (
                        <Tooltip title="Ver Logo Ampliada">
                          <Zoom in>
                            <IconButton 
                              onClick={() => handleOpenLogoZoom(client)}
                              size={isMobile ? "small" : "medium"}
                              sx={{ p: isMobile ? 0.5 : 1, mr: 1, border: `1px solid ${theme.palette.grey[200]}` }}
                            >
                              <Box
                                component="img"
                                src={`${BACKEND_URL}${client.logo_url}`}
                                alt={`${client.name} logo`}
                                sx={{
                                  width: isMobile ? 28 : 40,
                                  height: isMobile ? 28 : 40,
                                  objectFit: 'contain',
                                  borderRadius: 2,
                                  boxShadow: 2
                                }}
                              />
                            </IconButton>
                          </Zoom>
                        </Tooltip>
                      ) : (
                        <Tooltip title="Sem Logo">
                          <Avatar sx={{ bgcolor: theme.palette.grey[400], width: isMobile ? 28 : 40, height: isMobile ? 28 : 40, mr: 1 }}><PhotoCamera /></Avatar>
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.2}>
                      <Typography variant="body1" sx={{ fontWeight: 700 }}>{client.name}</Typography>
                      <Typography variant="caption" color="text.secondary">Schema: {client.schema_name}</Typography>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    {client.dominio_url ? (
                      <Tooltip title="Acessar Domínio">
                        <Button
                          variant="outlined"
                          size={isMobile ? "small" : "medium"}
                          startIcon={<Public fontSize="small" />}
                          href={client.dominio_url.startsWith('http') ? client.dominio_url : `https://${client.dominio_url}`}
                          target="_blank"
                          sx={{ textTransform: 'none' }}
                        >
                          {client.dominio_url.replace(/^(https?:\/\/)/, '').split('/')[0]}
                        </Button>
                      </Tooltip>
                    ) : (
                      <Typography variant="body2" color="text.disabled">N/A</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.3}>
                      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: isMobile ? '1rem' : '1.1rem' }}>
                        {client.responsible_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">{client.responsible_email}</Typography>
                      {client.responsible_phone && (
                        <Typography variant="caption" color="text.secondary">{client.responsible_phone}</Typography>
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell align="center">
                    <Chip label={client.users_total} color="info" size={isMobile ? "small" : "medium"} sx={{ fontWeight: 600 }}/>
                  </TableCell>
                  <TableCell align="center">
                    <Chip label={client.assets_total} color="warning" size={isMobile ? "small" : "medium"} sx={{ fontWeight: 600 }}/>
                  </TableCell>
                  <TableCell align="center">
                    <Stack spacing={0.5} direction={isMobile ? "column" : "row"} alignItems="center" justifyContent="center">
                      <Chip label={client.status} color={client.status === 'active' ? 'success' : 'error'} size={isMobile ? "small" : "medium"} sx={{ fontWeight: 600 }}/>
                      <Chip label={client.tenant_type} color="primary" size={isMobile ? "small" : "medium"} variant="outlined" />
                    </Stack>
                  </TableCell>
                  <TableCell align="center"><Typography variant="body2">{formatDate(client.plan_expires_at)}</Typography></TableCell>
                  <TableCell>
                    <Typography variant="body2">{formatDate(client.last_access)}</Typography>
                  </TableCell>
                  <TableCell align="center" sx={{ whiteSpace: 'nowrap' }}>
                    <Stack direction="row" spacing={1} justifyContent="center">
                      <Tooltip title="Ver Logs"><IconButton color="info" size={isMobile ? "small" : "medium"} onClick={() => handleOpenLogs(client)}><FormatListNumbered fontSize="inherit" /></IconButton></Tooltip>
                      <Tooltip title="Editar"><IconButton color="primary" size={isMobile ? "small" : "medium"} onClick={() => handleOpenEdit(client)}><Edit fontSize="inherit" /></IconButton></Tooltip>
                      <Tooltip title="Excluir"><IconButton color="error" size={isMobile ? "small" : "medium"} onClick={() => handleDelete(client)}><Delete fontSize="inherit" /></IconButton></Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
              {visibleClients.length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} align="center">
                    <Alert severity="info">Nenhum cliente encontrado.</Alert>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25]}
          component="div"
          count={filteredClients.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          labelRowsPerPage="Linhas por página:"
          labelDisplayedRows={({ from, to, count }) => `${from}-${to} de ${count}`}
          sx={{
            '.MuiTablePagination-toolbar': { px: isMobile ? 0.5 : 2, },
            '.MuiTablePagination-selectLabel, .MuiTablePagination-displayedRows': { fontSize: isMobile ? '0.85rem' : '1rem', },
          }}
        />
        </>
        )}
      </Paper>
      {/* Modal de Criação/Edição de Cliente */}
     <Dialog
        open={openModal}
        onClose={handleCloseModal}
        TransitionComponent={Fade}
        TransitionProps={{ onExited: handleExited }}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 5,
            boxShadow: 10,
            p: { xs: 2, sm: 4 },
            bgcolor: darkMode ? '#232323' : 'background.paper'
          }
        }}
      >
        <Paper
          elevation={0}
          sx={{
            p: { xs: 2, sm: 4 },
            mx: "auto",
            maxWidth: 700,
            bgcolor: darkMode ? '#232323' : 'background.paper',
            borderRadius: 5
          }}
        >
          <Typography variant="h4" fontWeight={800} textAlign="center" mt={1} mb={3}>
            {isEditing ? "Editar Cliente" : "Novo Cliente"}
          </Typography>
          <Grid container spacing={4} alignItems="stretch">
            {/* Inputs principais */}
            <Grid item xs={12} md={7}>
              <Stack spacing={2}>
                <TextField label="Nome da Empresa *" name="name" value={form.name} onChange={handleTextChange} required fullWidth variant="outlined" size="medium" />
                <TextField label="Schema (identificador)" name="schema_name" value={form.schema_name} onChange={handleTextChange} helperText="letras, números e underscore" fullWidth variant="outlined" size="medium" />
                <TextField label="Domínio URL" name="dominio_url" value={form.dominio_url || ''} onChange={handleTextChange} helperText="Ex: https://meudominio.com.br" fullWidth variant="outlined" size="medium" />
                <TextField label="Plano" name="plan_type" select value={form.plan_type} onChange={handleTextChange} fullWidth variant="outlined" size="medium">
                  {PLAN_OPTIONS.map(opt => <MenuItem key={opt} value={opt}>{opt}</MenuItem>)}
                  <MenuItem value="">(sem seleção)</MenuItem>
                </TextField>
                <TextField label="Status" name="status" select value={form.status} onChange={handleTextChange} fullWidth variant="outlined" size="medium">
                  <MenuItem value="active">Ativo</MenuItem>
                  <MenuItem value="inactive">Inativo</MenuItem>
                  <MenuItem value="pending">Pendente</MenuItem>
                  <MenuItem value="suspended">Suspenso</MenuItem>
                </TextField>
                <TextField label="Expira em" name="plan_expires_at" value={form.plan_expires_at} onChange={handleTextChange} type="date" InputLabelProps={{ shrink: true }} fullWidth variant="outlined" size="medium" />
              </Stack>
            </Grid>
            {/* Área da Logo */}
            <Grid item xs={12} md={5}>
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%' }}>
                <Divider sx={{ width: '100%', mb: 2 }}>Logo</Divider>
                <Button
                  variant={selectedLogoFile ? "contained" : "outlined"}
                  component="label"
                  startIcon={<PhotoCamera />}
                  size="medium"
                  fullWidth
                  sx={{ mb: 2 }}
                >
                  {selectedLogoFile
                    ? `Arquivo Selecionado: ${selectedLogoFile.name}`
                    : 'Escolher arquivo de Logo (.png, .jpg)'}
                  <input type="file" hidden accept="image/*" onChange={handleFileChange} />
                </Button>
                {form.logo_url && (
                  <Box sx={{
                    bgcolor: "#fff",
                    border: '1px solid #EEE',
                    boxShadow: 3,
                    borderRadius: 4,
                    p: 1,
                    mt: 1,
                    mb: 2,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    width: '100%',
                    minHeight: 90
                  }}>
                    <Box
                      component="img"
                      src={form.logo_url as string}
                      alt="Prévia da Logo"
                      sx={{
                        maxWidth: 170,
                        maxHeight: 72,
                        objectFit: 'contain',
                        borderRadius: 2,
                        mx: "auto"
                      }}
                    />
                    <Box sx={{ display: "flex", justifyContent: "center", mt: 1 }}>
                      {selectedLogoFile && (
                        <Chip label="Novo!" size="small" color="primary" sx={{ mr: 1 }} />
                      )}
                      <Tooltip title="Remover Logo">
                        <IconButton color="error" size="small" onClick={handleClearFile}>
                          <Close fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>
                )}
              </Box>
            </Grid>
            {/* Linha responsável/admin */}
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }}>Responsável / Admin</Divider>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Stack spacing={2}>
                    <TextField label="E-mail Responsável" name="responsible_email" value={form.responsible_email} onChange={handleTextChange} required variant="outlined" size="medium" fullWidth />
                    <TextField label="Nome Responsável" name="responsible_name" value={form.responsible_name} onChange={handleTextChange} variant="outlined" size="medium" fullWidth />
                    <TextField label="Telefone Resp." name="responsible_phone" value={form.responsible_phone || ''} onChange={handleTextChange} variant="outlined" size="medium" fullWidth />
                  </Stack>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Stack spacing={2}>
                    <TextField label="Nome do Admin" name="admin_name" value={form.admin_name} onChange={handleTextChange} required variant="outlined" size="medium" fullWidth />
                    <TextField label="Email do Admin" name="admin_email" value={form.admin_email} onChange={handleTextChange} required variant="outlined" size="medium" fullWidth />
                    <TextField label="Senha do Admin" name="admin_password" value={form.admin_password} onChange={handleTextChange} required variant="outlined" type="password" size="medium" fullWidth />
                    <Tooltip title="A senha será enviada para o admin e pode ser alterada depois." arrow>
                      <InfoOutlined color="action" fontSize="small" />
                    </Tooltip>
                  </Stack>
                </Grid>
              </Grid>
            </Grid>
            {/* Botões de ação */}
            <Grid item xs={12} sx={{ mt: 3 }}>
              <Stack direction="row" spacing={2} justifyContent="flex-end">
                <Button variant="contained" onClick={handleSave} disabled={saving} size="large" color="primary" sx={{ fontWeight: 700, minWidth: 120 }}>
                  {saving ? <CircularProgress size={20} color="inherit" /> : 'Salvar'}
                </Button>
                <Button variant="outlined" onClick={handleCloseModal} size="large">Cancelar</Button>
              </Stack>
              {error && <Alert severity="error" sx={{ width: '100%', mt: 2 }}>{error}</Alert>}
            </Grid>
          </Grid>
        </Paper>
      </Dialog>
      {/* Modal de Visualização de Logs */}
      <LogsModal 
        open={openLogsModal}
        onClose={() => setOpenLogsModal(false)}
        client={selectedClient}
        loading={loadingLogs}
      />
      {/* Modal de Zoom da Logo */}
      <Dialog open={openLogoZoom} onClose={() => setOpenLogoZoom(false)} maxWidth="sm" fullWidth>
        <Box sx={{ p: 2 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Logo de {selectedClient?.name || 'Cliente'}</Typography>
            <IconButton onClick={() => setOpenLogoZoom(false)}><Close /></IconButton>
          </Box>
          <Divider sx={{ my: 1 }} />
          {logoZoomUrl ? (
            <Box sx={{ p: 2, display: 'flex', justifyContent: 'center', maxHeight: '80vh' }}>
              <Box 
                component="img" 
                src={logoZoomUrl} 
                alt={`Logo ampliada de ${selectedClient?.name}`} 
                sx={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 2 }} 
              />
            </Box>
          ) : (
            <Alert severity="warning">Nenhuma logo disponível.</Alert>
          )}
        </Box>
      </Dialog>
      {/* Snackbar para feedback e senha provisória */}
      <Snackbar open={snackbarOpen} autoHideDuration={copiedPwd ? 2000 : 5000} onClose={handleSnackbarClose}>
        <Alert onClose={handleSnackbarClose} severity={snackbarSeverity} sx={{ width: "100%" }}>
          {snackbarMessage}
          {adminTempPassword && (
            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2">
                Senha provisória do admin: <b>{adminTempPassword}</b>
              </Typography>
              <IconButton color="primary" size="small" onClick={copyPwd}><ContentCopy /></IconButton>
              {copiedPwd && <Chip label="Copiado!" color="success" size="small"/>}
            </Box>
          )}
        </Alert>
      </Snackbar>
    </Box>
  );
}