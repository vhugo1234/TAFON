import React, { useEffect, useState } from 'react';
import {
  Container, Typography, Box, Button, Grid, Dialog, DialogTitle,
  DialogContent, DialogActions, TextField, Stack, Alert, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Chip, IconButton, MenuItem, Pagination, InputAdornment, Tooltip, Checkbox
} from '@mui/material';
import {
  Add, Edit, Delete, Upload, CloudUpload, Download, People,
  Male, Female, Search, ArrowBack, Refresh, DeleteSweep, Logout
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../lib/api';
import { formatDateBR } from '../lib/dateUtils';

interface Candidate {
  id: number;
  full_name: string;
  cpf: string;
  registration_number: string;
  gender: 'M' | 'F';
  batch_name: string | null;

  // número dentro da turma (pode ser nulo)
  batch_number?: number | null;

  // nomes possíveis para horário da turma (compatibilidade)
  batch_start_time?: string | null;
  start_time?: string | null;

  // NOVOS: data da turma (YYYY-MM-DD) — backend pode enviar start_date ou batch_date
  start_date?: string | null;
  batch_date?: string | null;

  has_results: boolean;
}


interface CandidateForm {
  full_name: string;
  cpf: string;
  registration_number: string;
  gender: 'M' | 'F';
}

const initialCandidateForm: CandidateForm = {
  full_name: '',
  cpf: '',
  registration_number: '',
  gender: 'M'
};

export default function TAFCandidatesPage() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const { eventId } = useParams<{ eventId: string }>();

  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [eventName, setEventName] = useState('');

  // Filtros e Paginação
  const [search, setSearch] = useState('');
  const [genderFilter, setGenderFilter] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 50;

  // Selecao Multipla
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectAll, setSelectAll] = useState(false);

  // Lista de turmas
  const [batches, setBatches] = useState<string[]>([]);

  // Upload
  const [uploading, setUploading] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Cadastro individual
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [candidateForm, setCandidateForm] = useState<CandidateForm>(initialCandidateForm);
  const [saving, setSaving] = useState(false);

  // Edição
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingCandidate, setEditingCandidate] = useState<Candidate | null>(null);

  useEffect(() => {
    if (eventId) {
      loadEventData();
      loadCandidates();
      loadBatches();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, page, search, genderFilter]);

  const loadEventData = async () => {
    try {
      const response = await api.get(`/taf/events/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEventName(response.data.name);
    } catch (err) {
      console.error('Erro ao carregar evento:', err);
    }
  };

  const loadCandidates = async () => {
      try {
        setLoading(true);
        const params: any = { page, page_size: pageSize };
        if (search) params.search = search;
        if (genderFilter) params.gender = genderFilter;

        const response = await api.get(`/taf/candidates/by-event/${eventId}`, {
          params,
          headers: { Authorization: `Bearer ${token}` }
        });

        // Ordena localmente por nome ignorando acentos e caixa (pt-BR)
        const items = response.data.items || [];
        items.sort((a: any, b: any) =>
          (a.full_name || '').localeCompare(b.full_name || '', 'pt-BR', { sensitivity: 'base' })
        );

        setCandidates(items);
        setTotal(response.data.total || 0);
      } catch (err: any) {
        setError(normalizeError(err, 'Erro ao carregar candidatos'));
      } finally {
        setLoading(false);
      }
    };

  const loadBatches = async () => {
    try {
      const response = await api.get(`/taf/candidates/batches/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBatches(response.data || []);
    } catch (err) {
      console.error('Erro ao carregar turmas:', err);
    }
  };

  // ========== CADASTRO INDIVIDUAL ==========
  const handleOpenCreate = () => {
    setCandidateForm(initialCandidateForm);
    setCreateDialogOpen(true);
    setError(null);
  };

  const handleCloseCreate = () => {
    setCreateDialogOpen(false);
    setCandidateForm(initialCandidateForm);
    setError(null);
  };

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setCandidateForm(prev => ({ ...prev, [name]: value }));
  };

  const handleCreateCandidate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const payload = {
        ...candidateForm,
        event_id: Number(eventId),
        cpf: onlyDigits(candidateForm.cpf)
      };

      await api.post('/taf/candidates/', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setSuccess('Candidato criado com sucesso!');
      handleCloseCreate();
      loadCandidates();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(normalizeError(err, 'Erro ao criar candidato'));
    } finally {
      setSaving(false);
    }
  };

  // ========== EDIÇÃO INDIVIDUAL ==========
  const handleOpenEdit = (candidate: Candidate) => {
    setEditingCandidate(candidate);
    setCandidateForm({
      full_name: candidate.full_name,
      cpf: candidate.cpf,
      registration_number: candidate.registration_number,
      gender: candidate.gender
    });
    setEditDialogOpen(true);
    setError(null);
  };

  const handleCloseEdit = () => {
    setEditDialogOpen(false);
    setEditingCandidate(null);
    setCandidateForm(initialCandidateForm);
    setError(null);
  };

  const handleUpdateCandidate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCandidate) return;

    setSaving(true);
    setError(null);

    try {
      const payload = {
        full_name: candidateForm.full_name,
        registration_number: candidateForm.registration_number,
        gender: candidateForm.gender,
        // CPF não é editável (apenas informativo)
      };

      await api.patch(`/taf/candidates/${editingCandidate.id}`, payload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setSuccess('Candidato atualizado com sucesso!');
      handleCloseEdit();
      loadCandidates();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(normalizeError(err, 'Erro ao atualizar candidato'));
    } finally {
      setSaving(false);
    }
  };

  // ========== UPLOAD CSV ==========
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
    } else {
      setSelectedFile(null);
    }
  };

  // ---------- handleUpload (usa axios 'api' para multipart/form-data) ----------
  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);
    setSuccess(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      // 1) Preview
      console.log('📤 Enviando arquivo para preview:', selectedFile.name);
      const previewResp = await api.post(
        '/taf/candidates/upload-preview',
        formData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'multipart/form-data'
          }
        }
      );

      const preview = previewResp.data;
      console.log('📊 Preview recebidos:', preview);

      const invalidRows = preview.invalid_rows ?? 0;
      const validRows = preview.valid_rows ?? 0;

      // Log detalhado do preview
      console.log(`✅ Linhas válidas: ${validRows}`);
      console.log(`❌ Linhas inválidas: ${invalidRows}`);
      console.log(`📋 Sample data length: ${preview.sample_data?.length ?? 0}`);

      // 🔍 MOSTRAR ERROS DETALHADOS
      if (Array.isArray(preview.errors) && preview.errors.length > 0) {
        console.log('❌ Erros encontrados:', preview.errors);
        
        // Separar avisos de erros bloqueantes
        const warnings = preview.errors.filter((err: any) => 
          err.error && err.error.includes('⚠️ AVISO')
        );
        const blockingErrors = preview.errors.filter((err: any) => 
          !(err.error && err.error.includes('⚠️ AVISO'))
        );
        
        // Log detalhado de cada erro
        preview.errors.forEach((err: any) => {
          const type = err.error?.includes('⚠️ AVISO') ? '⚠️ AVISO' : '❌ ERRO';
          console.log(`   ${type} Linha ${err.row_number}: Campo "${err.field}" - ${err.error}`);
        });
        
        // Mensagem para avisos (não-bloqueantes)
        if (warnings.length > 0 && blockingErrors.length === 0) {
          const warningMessages = warnings.map((err: any) => 
            `Linha ${err.row_number}: ${err.error}`
          ).join('\n');
          
          const confirmMsg = `⚠️ Encontrados ${warnings.length} aviso(s):\n\n${warningMessages}\n\nTodos os ${validRows} candidatos serão importados normalmente.\n\nDeseja continuar?`;
          
          const continuar = window.confirm(confirmMsg);
          if (!continuar) {
            setUploading(false);
            return;
          }
        }
        
        // Mensagem para erros bloqueantes
        if (blockingErrors.length > 0) {
          const errorMessages = blockingErrors.map((err: any) => 
            `Linha ${err.row_number}: ${err.field} - ${err.error}`
          ).join('\n');
          
          const errorSummary = `❌ ${blockingErrors.length} linhas com erro bloqueante:\n\n${errorMessages}`;
          
          // Mostrar erros na interface
          setError(errorSummary);
          
          const fullErrorMsg = `❌ Arquivo CSV contém ${blockingErrors.length} erros bloqueantes:\n\n${errorMessages}\n\nApenas ${validRows} candidatos válidos serão importados.`;          
          if (validRows > 0) {
            const continuar = window.confirm(fullErrorMsg + '\n\nDeseja importar apenas os candidatos válidos?');
            if (!continuar) {
              setUploading(false);
              return;
            }
            setError(null);
          }
        }
      }

      if (invalidRows > 0 && validRows === 0) {
        setError(`Arquivo processado: ${invalidRows} linhas inválidas. Corrija o arquivo e tente novamente.`);
        setUploading(false);
        return;
      }

      // select candidates to import: prefer valid_candidates, fallback to sample_data
      let candidatesToImport: any[] = preview.valid_candidates ?? preview.valid_rows_list ?? preview.sample_data ?? [];

      console.log('📦 Candidatos para importar (antes da validação):', candidatesToImport.length);

      if ((!Array.isArray(candidatesToImport) || candidatesToImport.length === 0) && Array.isArray(preview.sample_data) && preview.sample_data.length > 0) {
        const confirmSample = window.confirm(
          `Foram encontradas ${validRows} linhas válidas, mas o servidor retornou apenas uma amostra de ${preview.sample_data.length} itens.\n` +
          `Deseja importar apenas a amostra mostrada?`
        );
        if (!confirmSample) {
          setUploading(false);
          return;
        }
        candidatesToImport = preview.sample_data;
      }

      // ⚠️ ATENÇÃO: NÃO VALIDAR CPF NO FRONTEND - DEIXAR O BACKEND VALIDAR
      // O backend já valida CPF e retorna apenas candidatos válidos
      console.log(`✅ Total de candidatos a importar: ${candidatesToImport.length}`);

      // Remove batch_name and helper fields before sending
      const cleanedCandidates = candidatesToImport.map(({ batch_name, __row_index, row_number, ...rest }: any) => rest);

      console.log('🧹 Candidatos limpos (sem batch_name):', cleanedCandidates.length);

      // 2) Bulk import
      const bulkPayload = {
        event_id: Number(eventId),
        candidates: cleanedCandidates,
        skip_duplicates: true
      };

      console.log('📤 Enviando para bulk-import:', bulkPayload);

      const importResponse = await api.post('/taf/candidates/bulk-import', bulkPayload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const result = importResponse.data;
      console.log('✅ Resultado da importação:', result);

      // Mensagem detalhada de sucesso
      const successMsg = `Importação concluída!\n\n` +
        `✅ Importados: ${result.rows_imported}\n` +
        `⏭️ Duplicados ignorados: ${result.rows_skipped}\n` +
        `❌ Erros: ${result.rows_failed}\n\n` +
        `Total processado: ${result.total_rows}`;

      setSuccess(successMsg);
      setUploadDialogOpen(false);
      setSelectedFile(null);
      loadCandidates();
      setTimeout(() => setSuccess(null), 8000);
    } catch (err: any) {
      console.error('❌ Erro no upload/import:', err);
      console.error('Response data:', err?.response?.data);
      setError(normalizeError(err, 'Erro ao importar candidatos'));
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadSample = async () => {
    try {
      const response = await api.get('/taf/candidates/sample-csv/download', {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'text'
      });

      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'modelo_candidatos.csv';
      link.click();
    } catch (err) {
      console.error('Erro ao baixar modelo:', err);
    }
  };

  const handleDelete = async (candidate: Candidate) => {
    if (!window.confirm(`Excluir candidato ${candidate.full_name}?`)) return;

    try {
      await api.delete(`/taf/candidates/${candidate.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuccess('Candidato excluído com sucesso!');
      loadCandidates();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(normalizeError(err, 'Erro ao excluir candidato'));
    }
  };

  // ========== SELEÇÃO MÚLTIPLA ==========
  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedIds([]);
      setSelectAll(false);
    } else {
      setSelectedIds(candidates.map(c => c.id));
      setSelectAll(true);
    }
  };

  const handleSelectOne = (id: number) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(selectedId => selectedId !== id));
      setSelectAll(false);
    } else {
      const newSelection = [...selectedIds, id];
      setSelectedIds(newSelection);
      if (newSelection.length === candidates.length) {
        setSelectAll(true);
      }
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) {
      setError('Nenhum candidato selecionado!');
      return;
    }

    const confirmMsg = `Deseja realmente excluir ${selectedIds.length} candidato(s) selecionado(s)?\n\n⚠️ Esta ação não pode ser desfeita!`;
    if (!window.confirm(confirmMsg)) return;

    try {
      const response = await api.post('/taf/candidates/bulk-delete', selectedIds, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setSuccess(`${response.data.deleted_count} candidato(s) excluído(s) com sucesso!`);
      setSelectedIds([]);
      setSelectAll(false);
      loadCandidates();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(normalizeError(err, 'Erro ao excluir candidatos'));
    }
  };

  // ---------- Helpers para CPF ----------
  function onlyDigits(s: string | null | undefined): string {
    return (s || '').replace(/\D/g, '');
  }

  // ---------- Helpers ----------
  function normalizeError(err: any, fallback = 'Erro inesperado') {
    try {
      const respData = err?.response?.data;
      if (!respData) return String(err?.message ?? fallback);

      if (Array.isArray(respData.detail)) {
        return respData.detail.map((d: any) => d.msg ?? JSON.stringify(d)).join('; ');
      }

      if (typeof respData.detail === 'string') {
        return respData.detail;
      }

      if (typeof respData === 'object') {
        if (respData.message) return String(respData.message);
        if (respData.error) return String(respData.error);
        return JSON.stringify(respData);
      }

      return String(respData);
    } catch (e) {
      return String(err?.message ?? fallback);
    }
  }

  // ---------- UI Helpers ----------
  const padNumber = (n?: number | null, width = 3) => {
    if (n === null || n === undefined || n === '') return '';
    return String(n).padStart(width, '0');
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabeçalho */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
          <Stack direction="row" spacing={2} alignItems="center">
            <IconButton onClick={() => navigate('/taf/events')}>
              <ArrowBack />
            </IconButton>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <People sx={{ fontSize: 40, color: 'primary.main' }} />
              <Box>
                <Typography variant="h3" fontWeight={700}>
                  Candidatos
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  {eventName}
                </Typography>
              </Box>
            </Box>
          </Stack>
          
          {/* Botão de Sair */}
          <Tooltip title="Sair do sistema">
            <Button
              variant="outlined"
              color="error"
              startIcon={<Logout />}
              onClick={() => {
                if (window.confirm('Deseja realmente sair do sistema?')) {
                  logout();
                  navigate('/login');
                }
              }}
            >
              Sair
            </Button>
          </Tooltip>
        </Stack>

        <Stack direction="row" spacing={2} flexWrap="wrap">
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleOpenCreate}
          >
            Novo Candidato
          </Button>
          <Button
            variant="outlined"
            startIcon={<CloudUpload />}
            onClick={() => setUploadDialogOpen(true)}
          >
            Importar CSV
          </Button>
          <Button
            variant="outlined"
            startIcon={<People />}
            onClick={() => navigate(`/taf/events/${eventId}/grouping`)}
          >
            Agrupar em Turmas
          </Button>
          {selectedIds.length > 0 && (
            <Button
              variant="contained"
              color="error"
              startIcon={<DeleteSweep />}
              onClick={handleBulkDelete}
            >
              Excluir Selecionados ({selectedIds.length})
            </Button>
          )}
        </Stack>
      </Box>

      {/* Alertas */}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{String(error)}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{String(success)}</Alert>}

      {/* Contador de Candidatos */}
      <Paper sx={{ p: 2, mb: 2, bgcolor: 'primary.light', color: 'primary.contrastText' }}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Typography variant="h6" fontWeight={600}>
            📋 Total de Candidatos: {total}
          </Typography>
          <Stack direction="row" spacing={2}>
            <Chip 
              icon={<Male />} 
              label={`${candidates.filter(c => c.gender === 'M').length} Masculino`}
              color="primary"
              variant="outlined"
            />
            <Chip 
              icon={<Female />} 
              label={`${candidates.filter(c => c.gender === 'F').length} Feminino`}
              color="secondary"
              variant="outlined"
            />
          </Stack>
        </Stack>
      </Paper>

      {/* Turmas Criadas */}
      {batches.length > 0 && (
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'success.light' }}>
          <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
            🎯 Turmas Criadas ({batches.length})
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
            {batches.map((batch) => (
              <Chip
                key={batch}
                label={batch}
                onClick={() => navigate(`/taf/events/${eventId}/batch/${encodeURIComponent(batch)}`)}
                color="success"
                variant="outlined"
                sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'success.main', color: 'white' } }}
              />
            ))}
          </Stack>
          
          {/* ✅ NOVOS BOTÕES: Gerar PDFs de todas as turmas */}
          <Stack direction="row" spacing={2} justifyContent="center" sx={{ mt: 2 }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<Download />}
              onClick={async () => {
                try {
                  const response = await api.get(
                    `/taf/candidates/event/${eventId}/all-attendance-pdf`,
                    { 
                      responseType: 'blob',
                      headers: { Authorization: `Bearer ${token}` }
                    }
                  );
                  
                  const url = window.URL.createObjectURL(new Blob([response.data]));
                  const link = document.createElement('a');
                  link.href = url;
                  link.setAttribute('download', `listas_presenca_todas_turmas_${eventName}.pdf`);
                  document.body.appendChild(link);
                  link.click();
                  link.remove();
                  
                  setSuccess('📋 Todas as listas de presença geradas com sucesso!');
                  setTimeout(() => setSuccess(null), 3000);
                } catch (err: any) {
                  setError(normalizeError(err, 'Erro ao gerar listas de presença'));
                }
              }}
            >
              📋 Baixar TODAS as Listas de Presença
            </Button>
            
            <Button
              variant="contained"
              color="secondary"
              startIcon={<Download />}
              onClick={async () => {
                try {
                  const response = await api.get(
                    `/taf/candidates/event/${eventId}/all-badges-pdf`,
                    { 
                      responseType: 'blob',
                      headers: { Authorization: `Bearer ${token}` }
                    }
                  );
                  
                  const url = window.URL.createObjectURL(new Blob([response.data]));
                  const link = document.createElement('a');
                  link.href = url;
                  link.setAttribute('download', `espelhos_todas_turmas_${eventName}.pdf`);
                  document.body.appendChild(link);
                  link.click();
                  link.remove();
                  
                  setSuccess('🏷️ Todos os espelhos gerados com sucesso!');
                  setTimeout(() => setSuccess(null), 3000);
                } catch (err: any) {
                  setError(normalizeError(err, 'Erro ao gerar espelhos'));
                }
              }}
            >
              🏷️ Baixar TODOS os Espelhos
            </Button>
          </Stack>
        </Paper>
      )}

      {/* Filtros */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction="row" spacing={2}>
          <TextField
            placeholder="Buscar por nome, CPF ou inscrição..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            size="small"
            fullWidth
            InputProps={{
              startAdornment: <InputAdornment position="start"><Search /></InputAdornment>
            }}
          />
          <TextField
            select
            label="Sexo"
            value={genderFilter ?? ''}
            onChange={(e) => setGenderFilter(e.target.value)}
            size="small"
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="M">Masculino</MenuItem>
            <MenuItem value="F">Feminino</MenuItem>
          </TextField>
          <IconButton onClick={loadCandidates}>
            <Refresh />
          </IconButton>
        </Stack>
      </Paper>

      {/* Tabela */}
      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectAll}
                      indeterminate={selectedIds.length > 0 && selectedIds.length < candidates.length}
                      onChange={handleSelectAll}
                    />
                  </TableCell>
                  <TableCell width={60}>#</TableCell>
                  <TableCell>Inscrição</TableCell>
                  <TableCell>Nome</TableCell>
                  <TableCell>CPF</TableCell>
                  <TableCell>Sexo</TableCell>
                  <TableCell>Turma</TableCell>
                  <TableCell align="right">Ações</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {candidates.map((candidate, index) => (
                  <TableRow 
                    key={candidate.id}
                    hover
                    selected={selectedIds.includes(candidate.id)}
                    sx={{ 
                      cursor: 'pointer',
                      '&.Mui-selected': {
                        backgroundColor: 'action.selected',
                        '&:hover': {
                          backgroundColor: 'action.hover',
                        }
                      }
                    }}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selectedIds.includes(candidate.id)}
                        onChange={() => handleSelectOne(candidate.id)}
                      />
                    </TableCell>

                    {/* Índice com pill (estilo imagem) */}
                    <TableCell>
                      <Chip 
                        label={(page - 1) * pageSize + index + 1} 
                        size="small" 
                        color="primary"
                        variant="filled"
                        sx={{ fontWeight: 700, minWidth: 40, bgcolor: 'primary.main', color: 'white', borderRadius: '16px' }}
                      />
                    </TableCell>

                    {/* Inscrição (destaque) */}
                    <TableCell>
                      <Typography variant="body2" fontWeight={700} sx={{ fontFamily: 'monospace' }}>
                        {candidate.registration_number}
                      </Typography>
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {candidate.full_name}
                      </Typography>
                    </TableCell>

                    <TableCell>{candidate.cpf.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4')}</TableCell>

                    <TableCell>
                      <Chip
                        icon={candidate.gender === 'M' ? <Male /> : <Female />}
                        label={candidate.gender === 'M' ? 'M' : 'F'}
                        size="small"
                        color={candidate.gender === 'M' ? 'primary' : 'secondary'}
                      />
                    </TableCell>

                    {/* Turma: mostra nome + batch_number em badge + horário (start_time) */}
                    <TableCell>
                      {candidate.batch_name ? (
                        <Box>
                          <Typography variant="body2" fontWeight={600}>{candidate.batch_name}</Typography>
                          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
                            {candidate.batch_number != null && (
                              <Chip
                                label={`#${padNumber(candidate.batch_number)}`}
                                size="small"
                                color="primary"
                                sx={{ bgcolor: 'primary.main', color: 'white', fontWeight: 700, borderRadius: '12px' }}
                              />
                            )}

                            {/* Horário (prioriza batch_start_time / start_time) */}
                            {(candidate.batch_start_time || candidate.start_time) && (
                              <Typography variant="caption" color="text.secondary">
                                {candidate.batch_start_time || candidate.start_time}
                              </Typography>
                            )}

                            {/* Data: prioriza start_date -> batch_date, formatada em DD/MM/YYYY */}
                            {(candidate.start_date || candidate.batch_date) && (
                              <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                                {formatDateBR(candidate.start_date || candidate.batch_date)}
                              </Typography>
                            )}
                          </Stack>
                        </Box>
                      ) : '-'}
                    </TableCell>

                    <TableCell align="right">
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Tooltip title="Editar">
                          <IconButton size="small" color="primary" onClick={() => handleOpenEdit(candidate)}>
                            <Edit />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Excluir">
                          <IconButton size="small" color="error" onClick={() => handleDelete(candidate)}>
                            <Delete />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {total > pageSize && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
              <Pagination
                count={Math.ceil(total / pageSize)}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
              />
            </Box>
          )}
        </>
      )}

      {/* Modal de Cadastro Individual */}
      <Dialog open={createDialogOpen} onClose={handleCloseCreate} maxWidth="sm" fullWidth>
        <form onSubmit={handleCreateCandidate}>
          <DialogTitle>Novo Candidato</DialogTitle>
          <DialogContent>
            <Stack spacing={3} sx={{ mt: 1 }}>
              <TextField
                label="Nome Completo *"
                name="full_name"
                value={candidateForm.full_name}
                onChange={handleFormChange}
                fullWidth
                required
                placeholder="Ex: João da Silva"
              />

              <TextField
                label="CPF *"
                name="cpf"
                value={candidateForm.cpf}
                onChange={handleFormChange}
                fullWidth
                required
                placeholder="000.000.000-00"
                inputProps={{ maxLength: 14 }}
              />

              <TextField
                label="Número de Inscrição *"
                name="registration_number"
                value={candidateForm.registration_number}
                onChange={handleFormChange}
                fullWidth
                required
                placeholder="Ex: 1001"
              />

              <TextField
                select
                label="Sexo *"
                name="gender"
                value={candidateForm.gender}
                onChange={handleFormChange}
                fullWidth
                required
              >
                <MenuItem value="M">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Male /> <span>Masculino</span>
                  </Stack>
                </MenuItem>
                <MenuItem value="F">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Female /> <span>Feminino</span>
                  </Stack>
                </MenuItem>
              </TextField>
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 3 }}>
            <Button onClick={handleCloseCreate} disabled={saving}>
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={saving}
              startIcon={saving ? <CircularProgress size={20} /> : null}
            >
              Criar Candidato
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* Modal de Edição Individual */}
      <Dialog open={editDialogOpen} onClose={handleCloseEdit} maxWidth="sm" fullWidth>
        <form onSubmit={handleUpdateCandidate}>
          <DialogTitle>Editar Candidato</DialogTitle>
          <DialogContent>
            <Stack spacing={3} sx={{ mt: 1 }}>
              <TextField
                label="Nome Completo *"
                name="full_name"
                value={candidateForm.full_name}
                onChange={handleFormChange}
                fullWidth
                required
                placeholder="Ex: João da Silva"
              />

              <TextField
                label="CPF"
                name="cpf"
                value={candidateForm.cpf}
                fullWidth
                disabled
                helperText="CPF não pode ser alterado"
                InputProps={{
                  readOnly: true,
                }}
              />

              <TextField
                label="Número de Inscrição *"
                name="registration_number"
                value={candidateForm.registration_number}
                onChange={handleFormChange}
                fullWidth
                required
                placeholder="Ex: 1001"
              />

              <TextField
                select
                label="Sexo *"
                name="gender"
                value={candidateForm.gender}
                onChange={handleFormChange}
                fullWidth
                required
              >
                <MenuItem value="M">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Male /> <span>Masculino</span>
                  </Stack>
                </MenuItem>
                <MenuItem value="F">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Female /> <span>Feminino</span>
                  </Stack>
                </MenuItem>
              </TextField>

              {editingCandidate?.has_results && (
                <Alert severity="warning">
                  ⚠️ Este candidato já possui resultados lançados. Alterações podem afetar relatórios existentes.
                </Alert>
              )}
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 3 }}>
            <Button onClick={handleCloseEdit} disabled={saving}>
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={saving}
              startIcon={saving ? <CircularProgress size={20} /> : null}
            >
              Salvar Alterações
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* Dialog de Upload CSV */}
      <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Importar Candidatos via CSV</DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            <Alert severity="info">
              Baixe o modelo CSV e preencha com os dados dos candidatos (nome completo, CPF, número de inscrição e sexo).
            </Alert>

            <Button
              variant="outlined"
              startIcon={<Download />}
              onClick={handleDownloadSample}
              fullWidth
            >
              Baixar Modelo CSV
            </Button>

            <Box>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
                id="csv-upload"
              />
              <label htmlFor="csv-upload">
                <Button
                  variant="contained"
                  component="span"
                  startIcon={<Upload />}
                  fullWidth
                >
                  {selectedFile ? selectedFile.name : 'Selecionar Arquivo CSV'}
                </Button>
              </label>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={() => setUploadDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            startIcon={uploading ? <CircularProgress size={20} /> : <CloudUpload />}
          >
            Importar
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}