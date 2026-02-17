import React, { useEffect, useState } from 'react';
import {
  Container, Typography, Box, Button, Paper, Stack, Alert,
  Card, CardContent, Chip, IconButton, Divider, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow
} from '@mui/material';
import {
  ArrowBack, People, Male, Female, Download, Print, QrCode
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
  batch_number: number | null;

  // possible schedule fields returned by backend
  start_time?: string | null;
  batch_start_time?: string | null;
  start_date?: string | null; // YYYY-MM-DD
  batch_date?: string | null;
}

export default function TAFBatchViewPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { eventId, batchName } = useParams<{ eventId: string; batchName: string }>();

  const [eventName, setEventName] = useState('');
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    if (eventId && batchName) {
      loadEventData();
      loadBatchCandidates();
    }
    // eslint-disable-next-line
  }, [eventId, batchName]);

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

  const loadBatchCandidates = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/taf/candidates/batch/${eventId}/${encodeURIComponent(batchName || '')}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCandidates(response.data || []);
    } catch (err: any) {
      setError('Erro ao carregar candidatos da turma');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadAttendance = async () => {
    setDownloading('attendance');
    try {
      const response = await api.get(
        `/taf/candidates/batch/${eventId}/${encodeURIComponent(batchName || '')}/attendance-pdf`,
        {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `lista_presenca_${batchName}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError('Erro ao gerar lista de presenca');
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadBadges = async () => {
    setDownloading('badges');
    try {
      const response = await api.get(
        `/taf/candidates/batch/${eventId}/${encodeURIComponent(batchName || '')}/badges-pdf`,
        {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `espelhos_${batchName}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError('Erro ao gerar espelhos');
    } finally {
      setDownloading(null);
    }
  };

  // pick representative candidate to show batch date/time:
  // prefer candidate with lowest batch_number (first in the list)
  const batchStartCandidate = React.useMemo(() => {
    if (!candidates || candidates.length === 0) return null;
    // try to find candidate with smallest non-null batch_number
    const withNumber = candidates.filter(c => c.batch_number !== null && c.batch_number !== undefined);
    if (withNumber.length > 0) {
      withNumber.sort((a, b) => (Number(a.batch_number) || 0) - (Number(b.batch_number) || 0));
      return withNumber[0];
    }
    return candidates[0];
  }, [candidates]);

  const batchDateRaw = batchStartCandidate?.start_date ?? batchStartCandidate?.batch_date ?? null;
  const batchTimeRaw = batchStartCandidate?.start_time ?? batchStartCandidate?.batch_start_time ?? null;

  const batchDateLabel = batchDateRaw ? formatDateBR(batchDateRaw) : null;
  const batchTimeLabel = batchTimeRaw ? String(batchTimeRaw) : null;

  const totalMale = candidates.filter(c => c.gender === 'M').length;
  const totalFemale = candidates.filter(c => c.gender === 'F').length;

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabecalho */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <IconButton onClick={() => navigate(`/taf/events/${eventId}/candidates`)}>
            <ArrowBack />
          </IconButton>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <People sx={{ fontSize: 40, color: 'primary.main' }} />
            <Box>
              <Typography variant="h3" fontWeight={700}>
                {batchName}
              </Typography>
              <Typography variant="body1" color="text.secondary">
                {eventName}
              </Typography>
            </Box>
          </Box>
        </Stack>

        <Stack direction="row" spacing={2} flexWrap="wrap" alignItems="center">
          <Button
            variant="contained"
            startIcon={downloading === 'attendance' ? <CircularProgress size={20} /> : <Print />}
            onClick={handleDownloadAttendance}
            disabled={downloading !== null}
          >
            Lista de Presenca
          </Button>
          <Button
            variant="outlined"
            startIcon={downloading === 'badges' ? <CircularProgress size={20} /> : <QrCode />}
            onClick={handleDownloadBadges}
            disabled={downloading !== null}
          >
            Espelhos Numerados
          </Button>

          {/* spacer */}
          <Box sx={{ flex: 1 }} />

          {/* Exibir Data e Hora da Turma (se disponíveis) */}
          {(batchDateLabel || batchTimeLabel) && (
            <Stack direction="row" spacing={1} alignItems="center">
              {batchDateLabel && (
                <Chip
                  label={`📅 ${batchDateLabel}`}
                  size="small"
                  sx={{ bgcolor: 'grey.100' }}
                />
              )}
              {batchTimeLabel && (
                <Chip
                  label={`⏱ ${batchTimeLabel}`}
                  size="small"
                  sx={{ bgcolor: 'grey.100' }}
                />
              )}
            </Stack>
          )}
        </Stack>
      </Box>

      {/* Alertas */}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      {/* Resumo */}
      <Paper sx={{ p: 2, mb: 3, bgcolor: 'info.light' }}>
        <Stack direction="row" spacing={3} justifyContent="center">
          <Box textAlign="center">
            <Typography variant="h4" fontWeight={700}>
              {candidates.length}
            </Typography>
            <Typography variant="body2">Total de Candidatos</Typography>
          </Box>
          <Divider orientation="vertical" flexItem />
          <Box textAlign="center">
            <Typography variant="h4" fontWeight={700} color="primary.main">
              {totalMale}
            </Typography>
            <Typography variant="body2">
              <Male sx={{ fontSize: 16, verticalAlign: 'middle' }} /> Masculino
            </Typography>
          </Box>
          <Divider orientation="vertical" flexItem />
          <Box textAlign="center">
            <Typography variant="h4" fontWeight={700} color="secondary.main">
              {totalFemale}
            </Typography>
            <Typography variant="body2">
              <Female sx={{ fontSize: 16, verticalAlign: 'middle' }} /> Feminino
            </Typography>
          </Box>
        </Stack>
      </Paper>

      {/* Tabela */}
      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell width={80}>Numero</TableCell>
                <TableCell>Nome</TableCell>
                <TableCell>CPF</TableCell>
                <TableCell>Inscricao</TableCell>
                <TableCell>Sexo</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {candidates.map((candidate) => (
                <TableRow key={candidate.id}>
                  <TableCell>
                    <Chip 
                      label={String(candidate.batch_number || 0).padStart(3, '0')} 
                      size="medium" 
                      color="primary"
                      sx={{ fontWeight: 700, minWidth: 60, fontSize: 16 }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {candidate.full_name}
                    </Typography>
                  </TableCell>
                  <TableCell>{candidate.cpf.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4')}</TableCell>
                  <TableCell>{candidate.registration_number}</TableCell>
                  <TableCell>
                    <Chip
                      icon={candidate.gender === 'M' ? <Male /> : <Female />}
                      label={candidate.gender === 'M' ? 'M' : 'F'}
                      size="small"
                      color={candidate.gender === 'M' ? 'primary' : 'secondary'}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Container>
  );
}