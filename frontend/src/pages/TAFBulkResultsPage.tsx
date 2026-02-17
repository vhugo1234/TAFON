import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Container, Paper, Table, TableHead, TableRow, TableCell,
  TableBody, TextField, MenuItem, Button, Stack, Chip, IconButton, Alert,
  Checkbox
} from '@mui/material';
import { ArrowBack, Save } from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../lib/api';

interface Candidate {
  id: number;
  registration_number: string;
  full_name: string;
  gender: string;
  batch_name: string;
  batch_number: number | null;  // ? ADICIONADO
}

interface Exercise {
  id: number;
  name: string;
  unit_of_measure: string;
  max_attempts: number;
}

interface ResultEntry {
  candidate_id: number;
  attempt_1_value: number | null;
  attempt_1_valid: boolean;
  attempt_2_value: number | null;
  attempt_2_valid: boolean;
}

export default function TAFBulkResultsPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { eventId, exerciseId } = useParams<{ eventId: string; exerciseId: string }>();

  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [results, setResults] = useState<Map<number, ResultEntry>>(new Map());
  const [selectedBatch, setSelectedBatch] = useState<string>('');
  const [selectedGender, setSelectedGender] = useState<string>('');
  const [batches, setBatches] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadData();
    // eslint-disable-next-line
  }, [eventId, exerciseId, token]);

  useEffect(() => {
    if (selectedBatch) {
      filterCandidates();
    }
    // eslint-disable-next-line
  }, [selectedBatch, selectedGender]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Carrega exercicio
      const exerciseRes = await api.get(`/taf/exercises/${exerciseId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setExercise(exerciseRes.data);

      // Carrega candidatos do evento
      const candidatesRes = await api.get(`/taf/candidates/by-event/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const candidatesData = candidatesRes.data?.items || candidatesRes.data || [];
      setCandidates(candidatesData);

      // Extrai turmas unicas
      const uniqueBatches = Array.from(new Set(
        candidatesData.map((c: Candidate) => c.batch_name).filter(Boolean)
      )) as string[];
      setBatches(uniqueBatches);

      if (uniqueBatches.length > 0) {
        setSelectedBatch(uniqueBatches[0]);
      }

    } catch (err: any) {
      console.error('Erro ao carregar dados:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao carregar dados'));
    } finally {
      setLoading(false);
    }
  };

  const filterCandidates = () => {
    // Filtra candidatos pela turma e sexo selecionados
    const filtered = candidates.filter(c => {
      const matchesBatch = !selectedBatch || c.batch_name === selectedBatch;
      const matchesGender = !selectedGender || c.gender === selectedGender;
      return matchesBatch && matchesGender;
    });

    // Inicializa entradas de resultado se nao existirem
    const newResults = new Map(results);
    filtered.forEach(c => {
      if (!newResults.has(c.id)) {
        newResults.set(c.id, {
          candidate_id: c.id,
          attempt_1_value: null,
          attempt_1_valid: true,
          attempt_2_value: null,
          attempt_2_valid: true
        });
      }
    });
    setResults(newResults);
  };

  const handleValueChange = (candidateId: number, attempt: 1 | 2, value: string) => {
    const numValue = value === '' ? null : parseFloat(value);
    const newResults = new Map(results);
    const entry = newResults.get(candidateId);
    
    if (entry) {
      if (attempt === 1) {
        entry.attempt_1_value = numValue;
      } else {
        entry.attempt_2_value = numValue;
      }
      newResults.set(candidateId, entry);
      setResults(newResults);
    }
  };

  const handleValidChange = (candidateId: number, attempt: 1 | 2, valid: boolean) => {
    const newResults = new Map(results);
    const entry = newResults.get(candidateId);
    
    if (entry) {
      if (attempt === 1) {
        entry.attempt_1_valid = valid;
      } else {
        entry.attempt_2_valid = valid;
      }
      newResults.set(candidateId, entry);
      setResults(newResults);
    }
  };

  const handleSaveAll = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const resultsToSave = [];

      for (const [candidateId, entry] of results.entries()) {
        // Tentativa 1
        if (entry.attempt_1_value !== null) {
          resultsToSave.push({
            candidate_id: candidateId,
            exercise_id: Number(exerciseId),
            measured_value: entry.attempt_1_value,
            attempt_number: 1,
            is_valid: entry.attempt_1_valid
          });
        }

        // Tentativa 2
        if (entry.attempt_2_value !== null) {
          resultsToSave.push({
            candidate_id: candidateId,
            exercise_id: Number(exerciseId),
            measured_value: entry.attempt_2_value,
            attempt_number: 2,
            is_valid: entry.attempt_2_valid
          });
        }
      }

      if (resultsToSave.length === 0) {
        setError('Nenhum resultado para salvar');
        setSaving(false);
        return;
      }

      // Enviar em lote
      await api.post('/taf/execution/bulk', {
        results: resultsToSave
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setSuccess(`${resultsToSave.length} resultados salvos com sucesso!`);
      
      // Limpa resultados
      setResults(new Map());
      
      setTimeout(() => {
        navigate(`/taf/events/${eventId}/exercises`);
      }, 2000);

    } catch (err: any) {
      console.error('Erro ao salvar resultados:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao salvar resultados'));
    } finally {
      setSaving(false);
    }
  };

  const filteredCandidates = candidates.filter(c => {
    const matchesBatch = !selectedBatch || c.batch_name === selectedBatch;
    const matchesGender = !selectedGender || c.gender === selectedGender;
    return matchesBatch && matchesGender;
  });

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ mt: 4 }}>
        <Typography>Carregando...</Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabecalho */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <IconButton onClick={() => navigate(`/taf/events/${eventId}/exercises`)}>
            <ArrowBack />
          </IconButton>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h4" fontWeight={700}>
              Lancamento de Resultados
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Evento: PMDF 2025 • Exercicio: {exercise?.name || 'Abdominal'}
            </Typography>
          </Box>
          <Button
            variant="contained"
            color="primary"
            startIcon={<Save />}
            onClick={handleSaveAll}
            disabled={saving || filteredCandidates.length === 0}
          >
            Salvar Todos
          </Button>
        </Stack>
      </Box>

      {/* Alertas */}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}

      {/* Filtros */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction="row" spacing={2}>
          <TextField
            select
            label="Turma"
            value={selectedBatch}
            onChange={(e) => setSelectedBatch(e.target.value)}
            sx={{ minWidth: 200 }}
          >
            {batches.map(batch => (
              <MenuItem key={batch} value={batch}>{batch}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Sexo"
            value={selectedGender}
            onChange={(e) => setSelectedGender(e.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="M">Masculino</MenuItem>
            <MenuItem value="F">Feminino</MenuItem>
          </TextField>
        </Stack>
      </Paper>

      {/* Tabela de Resultados */}
      <Paper sx={{ p: 2 }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell>
              <TableCell>Candidato</TableCell>
              <TableCell>CPF</TableCell>
              <TableCell>Inscricao</TableCell>
              <TableCell>Turma</TableCell>
              <TableCell align="center">1a Tentativa</TableCell>
              <TableCell align="center">?</TableCell>
              <TableCell align="center">2a Tentativa</TableCell>
              <TableCell align="center">?</TableCell>
              <TableCell>Melhor</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredCandidates.map((candidate, index) => {
              const entry = results.get(candidate.id);
              const bestValue = entry
                ? Math.max(
                    entry.attempt_1_value || 0,
                    entry.attempt_2_value || 0
                  )
                : 0;

              return (
                <TableRow key={candidate.id}>
                  {/* ? CORRIGIDO: Exibe batch_number ou fallback para index+1 */}
                  <TableCell>
                    <Chip 
                      label={candidate.batch_number || (index + 1)} 
                      color="primary" 
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{candidate.full_name}</TableCell>
                  <TableCell>
                    {candidate.registration_number ? candidate.registration_number.slice(0, 11) : 'N/A'}
                  </TableCell>
                  <TableCell>
                    {candidate.registration_number || 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Chip label={candidate.batch_name} size="small" />
                  </TableCell>

                  {/* 1a Tentativa */}
                  <TableCell>
                    <TextField
                      type="number"
                      size="small"
                      placeholder="repeticoes"
                      value={entry?.attempt_1_value || ''}
                      onChange={(e) => handleValueChange(candidate.id, 1, e.target.value)}
                      sx={{ width: 120 }}
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Checkbox
                      checked={entry?.attempt_1_valid || false}
                      onChange={(e) => handleValidChange(candidate.id, 1, e.target.checked)}
                    />
                  </TableCell>

                  {/* 2a Tentativa */}
                  <TableCell>
                    <TextField
                      type="number"
                      size="small"
                      placeholder="repeticoes"
                      value={entry?.attempt_2_value || ''}
                      onChange={(e) => handleValueChange(candidate.id, 2, e.target.value)}
                      sx={{ width: 120 }}
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Checkbox
                      checked={entry?.attempt_2_valid || false}
                      onChange={(e) => handleValidChange(candidate.id, 2, e.target.checked)}
                    />
                  </TableCell>

                  <TableCell>
                    {bestValue > 0 ? (
                      <Chip label={`${bestValue} repeticoes`} color="primary" />
                    ) : (
                      '-'
                    )}
                  </TableCell>
                  <TableCell>
                    {bestValue > 0 ? (
                      <Chip label="Pendente" color="default" />
                    ) : (
                      <Chip label="Pendente" color="default" />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}

            {filteredCandidates.length === 0 && (
              <TableRow>
                <TableCell colSpan={11} align="center">
                  <Typography variant="body2" color="text.secondary">
                    Nenhum candidato encontrado para os filtros selecionados
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Container>
  );
}
