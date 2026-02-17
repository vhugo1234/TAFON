// frontend/src/pages/TAFExercisesPage.tsx

import React, { useEffect, useState, useMemo } from 'react';
import {
  Container, Typography, Box, Button, Grid, Card, CardContent, CardActions,
  Chip, IconButton, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Stack, Alert, CircularProgress, MenuItem, Divider,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Tooltip, useTheme
} from '@mui/material';
import {
  Add, Edit, Delete, ArrowBack, FitnessCenter, Rule, Male, Female, PersonAdd
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../lib/api';
import LogoutButton from '../components/LogoutButton';

// Exercícios pré-definidos comuns em TAF
const PREDEFINED_EXERCISES = [
  { name: 'Corrida 12 minutos', unit: 'metros', attempts: 1 },
  { name: 'Corrida 2.400 metros', unit: 'segundos', attempts: 1 },
  { name: 'Flexão de Braço', unit: 'repetições', attempts: 2 },
  { name: 'Abdominal (1 minuto)', unit: 'repetições', attempts: 2 },
  { name: 'Barra Fixa', unit: 'repetições', attempts: 2 },
  { name: 'Natação 50m', unit: 'segundos', attempts: 2 },
  { name: 'Natação 100m', unit: 'segundos', attempts: 2 },
  { name: 'Salto em Distância', unit: 'metros', attempts: 3 },
  { name: 'Impulsão Horizontal', unit: 'centímetros', attempts: 3 },
  { name: 'Shuttle Run', unit: 'segundos', attempts: 2 },
  { name: 'Burpees (1 minuto)', unit: 'repetições', attempts: 2 },
  { name: 'Outro (personalizar)', unit: '', attempts: 1 }
];

// Unidades de medida pré-definidas
const UNITS_OF_MEASURE = [
  'metros',
  'centímetros',
  'quilômetros',
  'segundos',
  'minutos',
  'repetições',
  'pontos',
  'kg',
  'outro'
];

interface Exercise {
  id: number;
  name: string;
  unit_of_measure: string;
  max_attempts: number;
  event_id: number;
  total_criteria: number;
}

interface PassCriteria {
  id: number;
  exercise_id: number;
  gender: 'M' | 'F';
  min_value: number;
  max_time_s: number | null;
}

interface ExerciseForm {
  name: string;
  unit_of_measure: string;
  max_attempts: number;
  execution_mode?: string;
  measurement_type?: string;
  predefined?: string;
}

const initialExerciseForm: ExerciseForm = {
  name: '',
  unit_of_measure: '',
  max_attempts: 1,
  execution_mode: 'individual',
  measurement_type: 'repetitions',
  predefined: ''
};

interface CriteriaForm {
  gender: 'M' | 'F';
  min_value: number;
  max_time_s: number | null;
}

const initialCriteriaForm: CriteriaForm = {
  gender: 'M',
  min_value: 0,
  max_time_s: null
};

export default function TAFExercisesPage() {
  const theme = useTheme();
  // Pega token, user e logout do contexto
  const { token, user, logout } = useAuth();
  const navigate = useNavigate();
  const { eventId } = useParams<{ eventId: string }>();

  // Estados
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);
  const [criteria, setCriteria] = useState<PassCriteria[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [eventName, setEventName] = useState<string>('');

  // Modais
  const [openExerciseModal, setOpenExerciseModal] = useState(false);
  const [openCriteriaModal, setOpenCriteriaModal] = useState(false);
  const [editingExercise, setEditingExercise] = useState<Exercise | null>(null);
  const [editingCriteria, setEditingCriteria] = useState<PassCriteria | null>(null);

  // Formulários
  const [exerciseForm, setExerciseForm] = useState<ExerciseForm>(initialExerciseForm);
  const [criteriaForm, setCriteriaForm] = useState<CriteriaForm>(initialCriteriaForm);

  // Carregar dados
  useEffect(() => {
    if (eventId) {
      loadEventData();
      loadExercises();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, token]);

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

  const loadExercises = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get(`/taf/exercises/by-event/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setExercises(response.data || []);
    } catch (err: any) {
      console.error('Erro ao carregar exercícios:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao carregar exercícios'));
    } finally {
      setLoading(false);
    }
  };

  const loadCriteria = async (exerciseId: number) => {
    try {
      const response = await api.get(`/taf/exercises/${exerciseId}/criteria`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setCriteria(response.data || []);
    } catch (err: any) {
      console.error('Erro ao carregar critérios:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao carregar critérios'));
    }
  };

  // Handlers de Exercícios
  const handleOpenCreateExercise = () => {
    setExerciseForm(initialExerciseForm);
    setEditingExercise(null);
    setOpenExerciseModal(true);
  };

  const handleOpenEditExercise = (exercise: Exercise) => {
    setExerciseForm({
      name: exercise.name,
      unit_of_measure: exercise.unit_of_measure,
      max_attempts: exercise.max_attempts,
      predefined: ''
    });
    setEditingExercise(exercise);
    setOpenExerciseModal(true);
  };

  // Novo: Handler para selecionar exercício pré-definido
  const handleSelectPredefined = (predefinedName: string) => {
    const exercise = PREDEFINED_EXERCISES.find(ex => ex.name === predefinedName);
    if (exercise) {
      setExerciseForm({
        name: exercise.name === 'Outro (personalizar)' ? '' : exercise.name,
        unit_of_measure: exercise.unit,
        max_attempts: exercise.attempts,
        predefined: predefinedName
      });
    }
  };

  // Handler para selecionar exercício e carregar critérios
  const handleSelectExercise = (exercise: Exercise) => {
    setSelectedExercise(exercise);
    loadCriteria(exercise.id);
  };

  const handleSubmitExercise = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      if (editingExercise) {
        await api.patch(`/taf/exercises/${editingExercise.id}`, exerciseForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccess('Exercício atualizado com sucesso!');
      } else {
        await api.post('/taf/exercises/', {
          ...exerciseForm,
          event_id: Number(eventId),
          execution_mode: exerciseForm.execution_mode,
          measurement_type: exerciseForm.measurement_type
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccess('Exercício criado com sucesso!');
      }

      setOpenExerciseModal(false);
      loadExercises();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao salvar exercício:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao salvar exercício'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteExercise = async (exercise: Exercise) => {
    if (!window.confirm(`Tem certeza que deseja excluir o exercício "${exercise.name}"?\n\nISSO TAMBÉM DELETARÁ TODOS OS CRITÉRIOS E RESULTADOS RELACIONADOS!`)) {
      return;
    }

    try {
      await api.delete(`/taf/exercises/${exercise.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuccess('Exercício deletado com sucesso!');
      loadExercises();
      if (selectedExercise?.id === exercise.id) {
        setSelectedExercise(null);
        setCriteria([]);
      }
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao deletar exercício:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao deletar exercício'));
    }
  };

  // Handlers de Critérios
  const handleOpenCreateCriteria = () => {
    setCriteriaForm(initialCriteriaForm);
    setEditingCriteria(null);
    setOpenCriteriaModal(true);
  };

  const handleOpenEditCriteria = (criterion: PassCriteria) => {
    setCriteriaForm({
      gender: criterion.gender,
      min_value: criterion.min_value,
      max_time_s: criterion.max_time_s
    });
    setEditingCriteria(criterion);
    setOpenCriteriaModal(true);
  };

  const handleSubmitCriteria = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExercise) return;

    setSaving(true);
    setError(null);

    try {
      if (editingCriteria) {
        await api.patch(`/taf/exercises/criteria/${editingCriteria.id}`, criteriaForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccess('Critério atualizado com sucesso!');
      } else {
        const payload = {
          ...criteriaForm,
          exercise_id: selectedExercise.id
        };
        await api.post(`/taf/exercises/${selectedExercise.id}/criteria`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccess('Critério criado com sucesso!');
      }

      setOpenCriteriaModal(false);
      loadCriteria(selectedExercise.id);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao salvar critério:', err);

      const respData = err?.response?.data;
      let message = err?.message ?? 'Erro ao salvar critério';
      if (respData) {
        if (Array.isArray(respData.detail)) {
          message = respData.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        } else if (typeof respData.detail === 'string') {
          message = respData.detail;
        } else {
          message = JSON.stringify(respData);
        }
      }

      setError(String(message));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCriteria = async (criterion: PassCriteria) => {
    if (!window.confirm('Tem certeza que deseja excluir este critério?')) {
      return;
    }

    try {
      await api.delete(`/taf/exercises/criteria/${criterion.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuccess('Critério deletado com sucesso!');
      if (selectedExercise) {
        loadCriteria(selectedExercise.id);
      }
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao deletar critério:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao deletar critério'));
    }
  };

  // --- NOVA LÓGICA: determinar se o usuário é avaliador limitado ---
  const isEvaluatorLimited = useMemo(() => {
    if (!user) return false;
    // prefer flag set by AuthContext, ou roles detection
    const asFlag = !!(user as any).evaluator_limited_view;
    const byRole = (user.roles || []).some((r: string) => String(r).toUpperCase() === 'AVALIADOR_EF') ||
                   (user.role && String(user.role).toUpperCase() === 'AVALIADOR_EF') ||
                   (user.role_id !== undefined && Number(user.role_id) === 4);
    return asFlag || byRole;
  }, [user]);

  // --- robust visibleExercises: usa assigned_exercises OR assigned_exercise_id fallback ---
  const visibleExercises = useMemo(() => {
    if (!isEvaluatorLimited) return exercises;

    const assignedArray: any[] = (user as any)?.assigned_exercises || [];
    const singleAssignedId: number | null = (user as any)?.assigned_exercise_id ? Number((user as any).assigned_exercise_id) : null;

    // se existirem assigned_exercises completos, usa-os (preferindo os que pertencem ao eventId atual)
    if (Array.isArray(assignedArray) && assignedArray.length > 0) {
      const fromAssigned = assignedArray.map(a => ({
        id: Number(a.exercise_id),
        name: a.exercise_name ?? a.name ?? `Exercício ${a.exercise_id}`,
        unit_of_measure: a.unit_of_measure ?? '',
        max_attempts: a.max_attempts ?? 1,
        event_id: Number(a.event_id),
        total_criteria: a.total_criteria ?? 0
      })) as Exercise[];

      // prefira aqueles do mesmo eventId atual
      const byEvent = fromAssigned.filter(a => String(a.event_id) === String(eventId));
      if (byEvent.length > 0) return byEvent;
      return fromAssigned;
    }

    // se não houver array, mas houver assigned_exercise_id (login antigo), constrói 1 item com assigned_event_id
    if (singleAssignedId) {
      const assignedEventId = (user as any)?.assigned_event_id ? Number((user as any).assigned_event_id) : Number(eventId);
      const fallback: Exercise[] = [{
        id: singleAssignedId,
        name: `Exercício ${singleAssignedId}`,
        unit_of_measure: '',
        max_attempts: 1,
        event_id: assignedEventId,
        total_criteria: 0
      }];
      return fallback;
    }

    // caso contrário, tenta filtrar a lista by-event (se by-event tem itens)
    const filteredByEvent = (exercises || []).filter(e => String(e.event_id) === String(eventId));
    if (filteredByEvent.length > 0) return filteredByEvent;

    // vazio final
    return [];
  }, [exercises, isEvaluatorLimited, user, eventId]);

  // Automatizar redirect caso haja exatamente 1 vínculo conhecido (array ou single id)
  useEffect(() => {
    if (!isEvaluatorLimited) return;

    const assignedArray: any[] = (user as any)?.assigned_exercises || [];
    const singleAssignedId: number | null = (user as any)?.assigned_exercise_id ? Number((user as any).assigned_exercise_id) : null;
    const assignedEventId = (user as any)?.assigned_event_id ? Number((user as any).assigned_event_id) : null;

    if (Array.isArray(assignedArray) && assignedArray.length === 1) {
      const ae = assignedArray[0];
      if (ae?.event_id && ae?.exercise_id) {
        const route = `/taf/events/${ae.event_id}/exercises/${ae.exercise_id}/field`;
        try { navigate(route, { replace: true }); } catch { window.location.replace(route); }
        return;
      }
    }

    if (!Array.isArray(assignedArray) || assignedArray.length === 0) {
      // fallback: se existir apenas assigned_exercise_id, navega para esse exercício
      if (singleAssignedId && assignedEventId) {
        const route = `/taf/events/${assignedEventId}/exercises/${singleAssignedId}/field`;
        try { navigate(route, { replace: true }); } catch { window.location.replace(route); }
        return;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEvaluatorLimited, user]);

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabeçalho */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Box display="flex" alignItems="center">
            {/* seta voltar apenas para não-avaliadores */}
            {!isEvaluatorLimited && (
              <IconButton onClick={() => navigate('/taf/events')} sx={{ mr: 1 }}>
                <ArrowBack />
              </IconButton>
            )}
            <Box>
              <Typography variant="h3" component="h1" fontWeight={700}>
                <FitnessCenter sx={{ verticalAlign: 'middle', mr: 1 }} /> Exercícios TAF
              </Typography>
              <Typography variant="body1" color="text.secondary">
                {eventName ? `Evento: ${eventName}` : 'Carregando...'}
              </Typography>
            </Box>
          </Box>

          {/* Coluna direita: botões admin (quando aplicável) + logout para TODOS */}
          <Box>
            <Stack direction="row" spacing={1} alignItems="center">
              {!isEvaluatorLimited && (
                <>
                  <Button
                    variant="contained"
                    size="large"
                    startIcon={<Add />}
                    onClick={handleOpenCreateExercise}
                  >
                    Novo Exercício
                  </Button>

                  <Button
                    variant="outlined"
                    size="large"
                    startIcon={<PersonAdd />}
                    onClick={() => navigate(`/taf/events/${eventId}/evaluators`)}
                  >
                    Vincular Avaliadores
                  </Button>
                </>
              )}

              <LogoutButton variant="outlined" size="small" color="error" showText />
            </Stack>
          </Box>
        </Stack>
      </Box>

      {/* Alertas */}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}

      {/* Loading */}
      {loading && (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={60} />
        </Box>
      )}

      {/* Layout Principal: 2 Colunas */}
      {!loading && (
        <Grid container spacing={3}>
          {/* COLUNA ESQUERDA: Lista de Exercícios */}
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom fontWeight={600}>
                Lista de Exercícios
              </Typography>
              <Divider sx={{ mb: 2 }} />

              {visibleExercises.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <FitnessCenter sx={{ fontSize: 60, color: 'text.disabled', mb: 2 }} />
                  <Typography variant="body2" color="text.secondary">
                    Nenhum exercício disponível
                  </Typography>
                </Box>
              ) : (
                <Stack spacing={1}>
                  {visibleExercises.map((exercise) => (
                    <Card
                      key={exercise.id}
                      sx={{
                        cursor: 'pointer',
                        border: selectedExercise?.id === exercise.id ? 2 : 1,
                        borderColor: selectedExercise?.id === exercise.id ? 'primary.main' : 'divider',
                        '&:hover': {
                          boxShadow: 3
                        }
                      }}
                      onClick={() => handleSelectExercise(exercise)}
                    >
                      <CardContent>
                        <Stack direction="row" justifyContent="space-between" alignItems="start">
                          <Box>
                            <Typography variant="subtitle1" fontWeight={600}>
                              {exercise.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {exercise.unit_of_measure} • {exercise.max_attempts} tentativa(s)
                            </Typography>
                            <Box sx={{ mt: 1 }}>
                              <Stack direction="row" spacing={1} flexWrap="wrap">
                                <Chip
                                  size="small"
                                  icon={<Rule />}
                                  label={`${exercise.total_criteria} critérios`}
                                  variant="outlined"
                                />
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    navigate(`/taf/events/${exercise.event_id}/exercises/${exercise.id}/field`);
                                  }}
                                  startIcon={<FitnessCenter />}
                                >
                                  Avaliar em Campo
                                </Button>

                                {/* Esconde Lançar Notas para avaliador limitado */}
                                {!isEvaluatorLimited && (
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      navigate(`/taf/events/${eventId}/exercises/${exercise.id}/execution`);
                                    }}
                                  >
                                    Lançar Notas
                                  </Button>
                                )}
                              </Stack>
                            </Box>
                          </Box>
                          <Stack direction="row" spacing={0.5}>
                            {/* Esconde controles de edição/exclusão para avaliador limitado */}
                            {!isEvaluatorLimited && (
                              <>
                                <IconButton
                                  size="small"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenEditExercise(exercise);
                                  }}
                                >
                                  <Edit fontSize="small" />
                                </IconButton>
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteExercise(exercise);
                                  }}
                                >
                                  <Delete fontSize="small" />
                                </IconButton>
                              </>
                            )}
                          </Stack>
                        </Stack>
                      </CardContent>
                    </Card>
                  ))}
                </Stack>
              )}
            </Paper>
          </Grid>

          {/* COLUNA DIREITA: Critérios de Aprovação */}
          <Grid item xs={12} md={8}>
            {selectedExercise ? (
              <Paper sx={{ p: 3 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
                  <Typography variant="h6" fontWeight={600}>
                    Critérios de Aprovação - {selectedExercise.name}
                  </Typography>

                  {/* Se avaliador limitado, esconde botão de adicionar critério */}
                  {!isEvaluatorLimited ? (
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<Add />}
                      onClick={handleOpenCreateCriteria}
                    >
                      Adicionar Critério
                    </Button>
                  ) : null}
                </Stack>

                {criteria.length === 0 ? (
                  <Box sx={{ textAlign: 'center', py: 8 }}>
                    <Rule sx={{ fontSize: 60, color: 'text.disabled', mb: 2 }} />
                    <Typography variant="body1" color="text.secondary" gutterBottom>
                      Nenhum critério cadastrado
                    </Typography>
                    {!isEvaluatorLimited && (
                      <>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                          Adicione critérios de aprovação por sexo
                        </Typography>
                        <Button variant="contained" startIcon={<Add />} onClick={handleOpenCreateCriteria}>
                          Adicionar Primeiro Critério
                        </Button>
                      </>
                    )}
                  </Box>
                ) : (
                  <TableContainer>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Sexo</TableCell>
                          <TableCell>Valor Mínimo</TableCell>
                          <TableCell>Tempo Máximo (s)</TableCell>
                          <TableCell align="right">Ações</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {criteria.map((criterion) => (
                          <TableRow key={criterion.id}>
                            <TableCell>
                              <Chip
                                icon={criterion.gender === 'M' ? <Male /> : <Female />}
                                label={criterion.gender === 'M' ? 'Masculino' : 'Feminino'}
                                color={criterion.gender === 'M' ? 'primary' : 'secondary'}
                                size="small"
                              />
                            </TableCell>
                            <TableCell>{criterion.min_value}</TableCell>
                            <TableCell>{criterion.max_time_s ?? '-'}</TableCell>
                            <TableCell align="right">
                              {/* Esconde ações de editar/deletar para avaliador limitado */}
                              {!isEvaluatorLimited ? (
                                <>
                                  <IconButton size="small" onClick={() => handleOpenEditCriteria(criterion)}>
                                    <Edit fontSize="small" />
                                  </IconButton>
                                  <IconButton size="small" color="error" onClick={() => handleDeleteCriteria(criterion)}>
                                    <Delete fontSize="small" />
                                  </IconButton>
                                </>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        ))} 
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Paper>
            ) : (
              <Paper sx={{ p: 8, textAlign: 'center' }}>
                <FitnessCenter sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
                <Typography variant="h6" color="text.secondary">
                  Selecione um exercício
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Clique em um exercício à esquerda para gerenciar seus critérios de aprovação
                </Typography>
              </Paper>
            )}
          </Grid>
        </Grid>
      )}

      {/* Modal de Exercício */}
      <Dialog open={openExerciseModal} onClose={() => setOpenExerciseModal(false)} maxWidth="md" fullWidth>
        <form onSubmit={handleSubmitExercise}>
          <DialogTitle>
            {editingExercise ? 'Editar Exercício' : 'Novo Exercício'}
          </DialogTitle>
          <DialogContent>
            <Stack spacing={3} sx={{ mt: 1 }}>
              {/* Seletor de Exercício Pré-definido */}
              {!editingExercise && (
                <>
                  <Typography variant="subtitle2" color="primary" fontWeight={600}>
                    📋 Selecione um exercício pré-definido (opcional)
                  </Typography>
                  <Grid container spacing={1}>
                    {PREDEFINED_EXERCISES.map((exercise) => (
                      <Grid item xs={12} sm={6} md={4} key={exercise.name}>
                        <Tooltip title={`${exercise.unit} • ${exercise.attempts} tentativa(s)`}>
                          <Card
                            sx={{
                              cursor: 'pointer',
                              border: exerciseForm.predefined === exercise.name ? 2 : 1,
                              borderColor: exerciseForm.predefined === exercise.name ? 'primary.main' : 'divider',
                              transition: 'all 0.2s',
                              '&:hover': {
                                boxShadow: 3,
                                transform: 'translateY(-2px)'
                              }
                            }}
                            onClick={() => handleSelectPredefined(exercise.name)}
                          >
                            <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                              <Stack direction="row" alignItems="center" spacing={1}>
                                <FitnessCenter
                                  fontSize="small"
                                  color={exerciseForm.predefined === exercise.name ? 'primary' : 'action'}
                                />
                                <Typography
                                  variant="body2"
                                  fontWeight={exerciseForm.predefined === exercise.name ? 600 : 400}
                                  sx={{ fontSize: '0.8rem' }}
                                >
                                  {exercise.name}
                                </Typography>
                              </Stack>
                            </CardContent>
                          </Card>
                        </Tooltip>
                      </Grid>
                    ))}
                  </Grid>

                  <Divider sx={{ my: 2 }}>
                    <Chip label="OU PERSONALIZE ABAIXO" size="small" />
                  </Divider>
                </>
              )}

              {/* Campos do Formulário */}
              <TextField
                label="Nome do Exercício *"
                value={exerciseForm.name}
                onChange={(e) => setExerciseForm({ ...exerciseForm, name: e.target.value, predefined: '' })}
                fullWidth
                required
                placeholder="Ex: Corrida 12 minutos"
                helperText={exerciseForm.predefined ? 'Você pode editar o nome selecionado' : ''}
              />

              <TextField
                label="Modo de Execução *"
                select
                value={exerciseForm.execution_mode || ''}
                onChange={e => setExerciseForm({ ...exerciseForm, execution_mode: e.target.value })}
                fullWidth
                required
                helperText="Individual (um por vez) ou Coletivo (vários juntos)"
              >
                <MenuItem value="individual">Individual</MenuItem>
                <MenuItem value="collective">Coletivo</MenuItem>
              </TextField>

              <TextField
                label="Tipo de Medição *"
                select
                value={exerciseForm.measurement_type || ''}
                onChange={e => setExerciseForm({ ...exerciseForm, measurement_type: e.target.value })}
                fullWidth
                required
                helperText="Tempo, Distância ou Repetições"
              >
                <MenuItem value="time">Tempo</MenuItem>
                <MenuItem value="distance">Distância</MenuItem>
                <MenuItem value="repetitions">Repetições</MenuItem>
              </TextField>

              <TextField
                label="Unidade de Medida *"
                select
                value={exerciseForm.unit_of_measure}
                onChange={(e) => setExerciseForm({ ...exerciseForm, unit_of_measure: e.target.value })}
                fullWidth
                required
                helperText="Selecione ou digite uma unidade personalizada"
              >
                {UNITS_OF_MEASURE.map((unit) => (
                  <MenuItem key={unit} value={unit}>
                    {unit}
                  </MenuItem>
                ))}
              </TextField>

              {/* Campo alternativo para unidade personalizada */}
              {exerciseForm.unit_of_measure === 'outro' && (
                <TextField
                  label="Unidade Personalizada *"
                  value={exerciseForm.unit_of_measure === 'outro' ? '' : exerciseForm.unit_of_measure}
                  onChange={(e) => setExerciseForm({ ...exerciseForm, unit_of_measure: e.target.value })}
                  fullWidth
                  required
                  placeholder="Digite a unidade de medida"
                />
              )}

              <TextField
                label="Máximo de Tentativas *"
                type="number"
                value={exerciseForm.max_attempts}
                onChange={(e) => setExerciseForm({ ...exerciseForm, max_attempts: parseInt(e.target.value) || 1 })}
                fullWidth
                required
                inputProps={{ min: 1, max: 5 }}
                helperText="Quantas tentativas o candidato terá"
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 3 }}>
            <Button onClick={() => setOpenExerciseModal(false)} disabled={saving}>
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={saving}
              startIcon={saving ? <CircularProgress size={20} /> : null}
            >
              {editingExercise ? 'Atualizar' : 'Criar'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* Modal de Critério */}
      <Dialog open={openCriteriaModal} onClose={() => setOpenCriteriaModal(false)} maxWidth="sm" fullWidth>
        <form onSubmit={handleSubmitCriteria}>
          <DialogTitle>
            {editingCriteria ? 'Editar Critério' : 'Novo Critério de Aprovação'}
          </DialogTitle>
          <DialogContent>
            <Stack spacing={3} sx={{ mt: 1 }}>
              <TextField
                label="Sexo *"
                select
                value={criteriaForm.gender}
                onChange={(e) => setCriteriaForm({ ...criteriaForm, gender: e.target.value as 'M' | 'F' })}
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

              <TextField
                label="Valor Mínimo para Aprovação *"
                type="number"
                value={criteriaForm.min_value || ''}
                onChange={(e) => setCriteriaForm({ ...criteriaForm, min_value: parseFloat(e.target.value) || 0 })}
                fullWidth
                required
                inputProps={{ step: 0.01 }}
                helperText={selectedExercise ? `Em ${selectedExercise.unit_of_measure}` : ''}
              />

              <TextField
                label="Tempo Máximo (segundos)"
                type="number"
                value={criteriaForm.max_time_s || ''}
                onChange={(e) => setCriteriaForm({ ...criteriaForm, max_time_s: e.target.value ? parseInt(e.target.value) : null })}
                fullWidth
                helperText="Opcional - Para exercícios com limite de tempo"
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 3 }}>
            <Button onClick={() => setOpenCriteriaModal(false)} disabled={saving}>
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={saving}
              startIcon={saving ? <CircularProgress size={20} /> : null}
            >
              {editingCriteria ? 'Atualizar' : 'Criar'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Container>
  );
}