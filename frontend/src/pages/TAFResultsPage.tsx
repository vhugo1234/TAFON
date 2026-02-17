// frontend/src/pages/TAFResultsPage.tsx
import React, { useEffect, useState, useRef, useMemo } from 'react';
import {
  Container, Typography, Box, Button, Grid, Card, CardContent,
  Chip, Stack, Alert, CircularProgress, Paper, useTheme,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  IconButton, MenuItem, TextField, Tooltip, TablePagination
} from '@mui/material';
import {
  ArrowBack, Download, PictureAsPdf, CheckCircle, Cancel,
  Timer, Male, Female, Assessment, TrendingUp, People
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../lib/api';

interface CandidateResult {
  candidate_id: number;
  candidate_name: string;
  registration_number: string;
  cpf: string;
  gender: string;
  overall_status: string;
  approved_exercises: number;
  failed_exercises: number;
  total_exercises: number;
  batch_name?: string | null;
  batch_number?: string | number | null;
  start_time?: string | null;
  start_date?: string | null;
}

interface Summary {
  total_candidates: number;
  total_exercises: number;
  candidates_approved: number;
  candidates_failed: number;
  candidates_in_progress: number;
  approval_rate: number;
  completion_rate: number;
}

export default function TAFResultsPage() {
  const theme = useTheme();
  const { token } = useAuth();
  const navigate = useNavigate();
  const { eventId } = useParams<{ eventId: string }>();

  const [results, setResults] = useState<CandidateResult[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingPage, setLoadingPage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [eventName, setEventName] = useState('');
  const [loadingAllFichas, setLoadingAllFichas] = useState(false);

  // Filters
  const [filterStatus, setFilterStatus] = useState('');
  const [filterGender, setFilterGender] = useState('');
  const [filterName, setFilterName] = useState('');
  const [filterNumber, setFilterNumber] = useState('');

  // Debounced filter values
  const [debouncedName, setDebouncedName] = useState(filterName);
  const [debouncedNumber, setDebouncedNumber] = useState(filterNumber);

  // Pagination (server-side)
  const [page, setPage] = useState(0); // zero-based for MUI
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  const abortRef = useRef<AbortController | null>(null);

  // debounce effects for name/number
  useEffect(() => {
    const id = setTimeout(() => setDebouncedName(filterName), 400);
    return () => clearTimeout(id);
  }, [filterName]);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedNumber(filterNumber), 400);
    return () => clearTimeout(id);
  }, [filterNumber]);

  // helpers for formatting dates/times
  const pad = (n: number) => String(n).padStart(2, '0');
  const formatDateYMD = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  const formatYMDToDisplay = (ymd?: string) => {
    if (!ymd) return '';
    const parts = String(ymd).split('-');
    if (parts.length !== 3) return String(ymd);
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  };

  const formatTimeToDisplay = (t?: string) => {
    if (!t) return '';
    const parts = String(t).split(':');
    if (parts.length >= 2) return `${parts[0]}:${parts[1]}`;
    return String(t);
  };

  // Utility to pick first available key (supports nested 'a.b' path)
  const pick = (obj: any, keys: string[]) => {
    if (!obj) return null;
    for (const k of keys) {
      if (k.includes('.')) {
        const parts = k.split('.');
        let cur = obj;
        let ok = true;
        for (const p of parts) {
          if (cur && Object.prototype.hasOwnProperty.call(cur, p)) cur = cur[p];
          else { ok = false; break; }
        }
        if (ok && cur !== undefined && cur !== null) return cur;
      } else {
        if (Object.prototype.hasOwnProperty.call(obj, k) && obj[k] !== undefined && obj[k] !== null && obj[k] !== '') {
          return obj[k];
        }
      }
    }
    return null;
  };

  const padBatchNumber = (val: any) => {
    if (val === null || val === undefined) return null;
    if (typeof val === 'string') {
      const cleaned = val.trim();
      if (cleaned === '') return null;
      if (/^\d+$/.test(cleaned)) return cleaned.padStart(3, '0');
      return cleaned;
    }
    if (typeof val === 'number') {
      return String(val).padStart(3, '0');
    }
    try {
      const s = String(val).trim();
      if (s === '') return null;
      return /^\d+$/.test(s) ? s.padStart(3, '0') : s;
    } catch {
      return null;
    }
  };

  // loadData does event + summary + results for the current page & filters
  const loadData = async (opts?: { keepLoadingFlag?: boolean }) => {
    if (!eventId) return;
    // cancel previous
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      if (!opts?.keepLoadingFlag) setLoading(true);
      setLoadingPage(true);
      setError(null);

      const params: any = {
        page: page + 1, // backend likely 1-based
        page_size: pageSize,
      };
      if (filterStatus) params.status = filterStatus;
      if (filterGender) params.gender = filterGender;
      if (debouncedName) params.name = debouncedName;
      if (debouncedNumber) params.number = debouncedNumber;

      // run event/summary/results in parallel
      const [eventRes, summaryRes, resultsRes] = await Promise.all([
        api.get(`/taf/events/${eventId}`, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal }),
        api.get(`/taf/results/event/${eventId}/summary`, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal }),
        api.get(`/taf/results/event/${eventId}/candidates`, { params, headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      ]);

      if (eventRes?.data) setEventName(eventRes.data.name ?? eventRes.data.title ?? '');

      if (summaryRes?.data) setSummary(summaryRes.data);

      // resultsRes: accept either { items: [...], total_count } or plain array
      let rawItems: any[] = [];
      let total = 0;
      if (resultsRes?.data) {
        if (Array.isArray(resultsRes.data)) {
          rawItems = resultsRes.data;
          total = rawItems.length;
        } else {
          rawItems = Array.isArray(resultsRes.data.items) ? resultsRes.data.items : (Array.isArray(resultsRes.data.results) ? resultsRes.data.results : []);
          total = Number(resultsRes.data.total_count ?? resultsRes.data.total ?? rawItems.length);
          // fallback: if items undefined but data has array-like props, try to detect
          if (!rawItems.length && typeof resultsRes.data === 'object') {
            // try to find first array prop
            for (const v of Object.values(resultsRes.data)) {
              if (Array.isArray(v)) { rawItems = v; break; }
            }
            if (!total) total = rawItems.length;
          }
        }
      }

      // normalize & map only the current page
      const mapped = (rawItems || []).map(item => {
        const batchName = pick(item, ['batch_name', 'batch', 'lote_nome', 'batchName', 'batch.name']) ?? null;
        const batchNumberRaw = pick(item, ['batch_number', 'batch_no', 'batchNumber', 'batch.number', 'batch_num', 'numero_lote']) ?? null;

        const startRaw = pick(item, ['start_time', 'start_at', 'start_time_local', 'start_datetime', 'startDateTime', 'start', 'time_start', 'start_date_time']) ?? null;
        const startDateRaw = pick(item, ['start_date', 'start_date_iso', 'date_start', 'startDate', 'start_date_time', 'date']) ?? null;

        let start_time: string | null = null;
        let start_date: string | null = null;

        if (startRaw && typeof startRaw === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(startRaw)) {
          const [d, t] = startRaw.split('T');
          start_date = d;
          start_time = t ? t.split('.')[0] : null;
        } else {
          if (startRaw) start_time = String(startRaw);
          if (startDateRaw) start_date = String(startDateRaw);
        }

        if ((!start_date || start_date === '') && startRaw && typeof startRaw === 'string' && startRaw.includes(' ')) {
          const parts = startRaw.split(' ');
          if (parts.length >= 2) {
            start_date = parts[0];
            start_time = parts[1].split('.')[0];
          }
        }

        const batch_number_clean = padBatchNumber(batchNumberRaw);

        return {
          ...item,
          batch_name: batchName ?? null,
          batch_number: batch_number_clean,
          start_time: start_time ?? null,
          start_date: start_date ?? null
        } as CandidateResult;
      });

      setResults(mapped);
      setTotalCount(total);
    } catch (err: any) {
      if (err?.name === 'CanceledError' || err?.name === 'AbortError') {
        // request canceled — ignore
        return;
      }
      console.error('loadData error', err);
      setError(err?.response?.data?.detail || 'Erro ao carregar resultados');
    } finally {
      setLoading(false);
      setLoadingPage(false);
    }
  };

  // initial load and whenever page/pageSize/filters (debounced) change
  useEffect(() => {
    if (!eventId) return;
    // reset to first page when filters change
    setPage(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedName, debouncedNumber, filterStatus, filterGender, eventId]);

  useEffect(() => {
    if (!eventId) return;
    loadData();
    // cleanup abort on unmount
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
    // include page/pageSize and debounced filters
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, page, pageSize, debouncedName, debouncedNumber, filterStatus, filterGender]);

  // handlers for pagination
  const handleChangePage = (_: any, newPage: number) => {
    setPage(newPage);
  };
  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPageSize(parseInt(e.target.value, 10));
    setPage(0);
  };

  // download individual PDF
  const handleDownloadPDF = async (candidateId: number, registrationNumber: string) => {
    try {
      const response = await api.post(`/taf/results/candidate/${candidateId}/pdf`, 
        { event_id: Number(eventId) },
        {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob',
          params: { event_id: eventId }
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `resultado_${registrationNumber}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Erro ao baixar PDF:', err);
    }
  };

  const handleDownloadConsolidated = async () => {
    try {
      const response = await api.get(`/taf/results/event/${eventId}/pdf-consolidated`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `resultado_consolidado.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Erro ao baixar PDF consolidado:', err);
    }
  };

  // download ALL fichas (single merged PDF)
  const handleDownloadAllFichas = async () => {
    if (!eventId) return;
    try {
      setLoadingAllFichas(true);
      // 1) create job
      const createResp = await api.post(`/taf/results/event/${eventId}/fichas/pdf`, null, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 60000
      });
      const { job_id, status_url, download_url } = createResp.data;

      // 2) poll status
      const start = Date.now();
      const MAX_WAIT = 1000 * 60 * 10; // 10 minutes max
      const POLL_INTERVAL = 2000;
      let finished = false;
      while (!finished) {
        await new Promise(res => setTimeout(res, POLL_INTERVAL));
        try {
          const statusResp = await api.get(status_url, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 });
          const status = statusResp.data.status;
          if (status === 'done') {
            finished = true;
            const dlResp = await api.get(download_url, { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob', timeout: 120000 });
            const url = window.URL.createObjectURL(new Blob([dlResp.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `fichas_event_${eventId}.pdf`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            break;
          } else if (status === 'failed') {
            alert('Geração falhou. Verifique os logs do servidor.');
            finished = true;
            break;
          } else {
            // opcional: mostrar progresso: statusResp.data.progress
          }
        } catch (err) {
          console.warn('Polling failed, will retry', err);
        }
        if (Date.now() - start > MAX_WAIT) {
          alert('Tempo máximo de espera excedido. Tente novamente mais tarde.');
          break;
        }
      }
    } catch (err) {
      console.error('Erro ao criar job de fichas:', err);
      alert('Não foi possível iniciar geração do PDF. Veja console.');
    } finally {
      setLoadingAllFichas(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved': return 'success';
      case 'failed': return 'error';
      default: return 'warning';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved': return <CheckCircle />;
      case 'failed': return <Cancel />;
      default: return <Timer />;
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'approved': return 'Aprovado';
      case 'failed': return 'Reprovado';
      default: return 'Em Andamento';
    }
  };

  // memoized row to avoid re-renders
  const CandidateRow = React.useMemo(() => React.memo(function Row({ candidate }: { candidate: CandidateResult }) {
    return (
      <TableRow key={candidate.candidate_id}>
        <TableCell>{candidate.registration_number}</TableCell>
        <TableCell style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{candidate.candidate_name}</TableCell>
        <TableCell>{candidate.cpf ? candidate.cpf.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4') : '—'}</TableCell>
        <TableCell>{candidate.batch_name ?? '—'}</TableCell>
        <TableCell>{candidate.batch_number !== null && candidate.batch_number !== undefined ? String(candidate.batch_number) : '—'}</TableCell>
        <TableCell>{formatTimeToDisplay(candidate.start_time) || '—'}</TableCell>
        <TableCell>{candidate.start_date ? formatYMDToDisplay(candidate.start_date) : '—'}</TableCell>
        <TableCell>
          <Chip
            icon={candidate.gender === 'M' ? <Male /> : <Female />}
            label={candidate.gender || '—'}
            size="small"
            color={candidate.gender === 'M' ? 'primary' : 'secondary'}
          />
        </TableCell>
        <TableCell align="center">
          <Typography variant="body2">
            {candidate.approved_exercises}/{candidate.total_exercises}
          </Typography>
        </TableCell>
        <TableCell>
          <Chip
            icon={getStatusIcon(candidate.overall_status)}
            label={getStatusLabel(candidate.overall_status)}
            color={getStatusColor(candidate.overall_status) as any}
            size="small"
          />
        </TableCell>
        <TableCell align="right">
          <Tooltip title="Baixar PDF">
            <IconButton
              size="small"
              color="primary"
              onClick={() => handleDownloadPDF(candidate.candidate_id, candidate.registration_number)}
            >
              <Download />
            </IconButton>
          </Tooltip>
        </TableCell>
      </TableRow>
    );
  }), []); // dependencias vazias: Row é puro

  if (loading && !loadingPage && results.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress size={60} />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabeçalho */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <IconButton onClick={() => navigate('/taf/events')}>
            <ArrowBack />
          </IconButton>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h3" fontWeight={700}>
              <Assessment sx={{ verticalAlign: 'middle', mr: 1 }} />
              Resultados TAF
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {eventName}
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<PictureAsPdf />}
            onClick={handleDownloadConsolidated}
            sx={{ mr: 1 }}
          >
            PDF Consolidado
          </Button>

          <Button
            variant="outlined"
            startIcon={loadingAllFichas ? <CircularProgress size={18} color="inherit" /> : <Download />}
            onClick={handleDownloadAllFichas}
            disabled={loadingAllFichas}
          >
            PDF — Todas as Fichas
          </Button>
        </Stack>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Cards de Resumo */}
      {summary && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between">
                  <Box>
                    <Typography color="text.secondary" variant="body2">Total Candidatos</Typography>
                    <Typography variant="h4" fontWeight={700}>{summary.total_candidates}</Typography>
                  </Box>
                  <People sx={{ fontSize: 40, color: 'primary.main' }} />
                </Stack>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between">
                  <Box>
                    <Typography color="text.secondary" variant="body2">Aprovados</Typography>
                    <Typography variant="h4" fontWeight={700} color="success.main">{summary.candidates_approved}</Typography>
                  </Box>
                  <CheckCircle sx={{ fontSize: 40, color: 'success.main' }} />
                </Stack>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between">
                  <Box>
                    <Typography color="text.secondary" variant="body2">Reprovados</Typography>
                    <Typography variant="h4" fontWeight={700} color="error.main">{summary.candidates_failed}</Typography>
                  </Box>
                  <Cancel sx={{ fontSize: 40, color: 'error.main' }} />
                </Stack>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between">
                  <Box>
                    <Typography color="text.secondary" variant="body2">Taxa de Aprovação</Typography>
                    <Typography variant="h4" fontWeight={700}>{summary.approval_rate.toFixed(1)}%</Typography>
                  </Box>
                  <TrendingUp sx={{ fontSize: 40, color: 'warning.main' }} />
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Filtros */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="center">
          <TextField select label="Status" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} size="small" sx={{ minWidth: 160 }}>
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="approved">Aprovados</MenuItem>
            <MenuItem value="failed">Reprovados</MenuItem>
            <MenuItem value="in_progress">Em Andamento</MenuItem>
          </TextField>

          <TextField select label="Sexo" value={filterGender} onChange={(e) => setFilterGender(e.target.value)} size="small" sx={{ minWidth: 140 }}>
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="M">Masculino</MenuItem>
            <MenuItem value="F">Feminino</MenuItem>
          </TextField>

          <TextField label="Nome" placeholder="Buscar por nome..." value={filterName} onChange={(e) => setFilterName(e.target.value)} size="small" sx={{ minWidth: 240 }} />
          <TextField label="Número" placeholder="Inscrição ou Nº turma..." value={filterNumber} onChange={(e) => setFilterNumber(e.target.value)} size="small" sx={{ minWidth: 180 }} />

          <Box sx={{ ml: 'auto' }}>
            <Typography variant="caption" color="text.secondary">Mostrando {results.length} de {totalCount}</Typography>
          </Box>
        </Stack>
      </Paper>

      {/* Tabela de Resultados */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Inscrição</TableCell>
              <TableCell>Nome</TableCell>
              <TableCell>CPF</TableCell>
              <TableCell>Grupo</TableCell>
              <TableCell>Número</TableCell>
              <TableCell>Hora Início</TableCell>
              <TableCell>Data Início</TableCell>
              <TableCell>Sexo</TableCell>
              <TableCell align="center">Exercícios</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {results.map(candidate => (
              // @ts-ignore - CandidateRow is memoized component factory
              <CandidateRow key={candidate.candidate_id} candidate={candidate} />
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
        <TablePagination
          component="div"
          count={totalCount}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={pageSize}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </Box>
    </Container>
  );
}
