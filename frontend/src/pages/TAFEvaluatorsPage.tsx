// frontend/src/pages/TAFEvaluatorsPage.tsx

import React, { useEffect, useState } from 'react';
import {
  Container, Typography, Box, Button, Stack, Alert, CircularProgress,
  Card, CardContent, IconButton, Chip, Avatar, Dialog, DialogTitle,
  DialogContent, DialogActions, List, ListItem, ListItemAvatar,
  ListItemText, Checkbox, TextField, MenuItem, Paper, Divider
} from '@mui/material';
import {
  ArrowBack, Add, Delete, Star, StarBorder, FitnessCenter, PersonAdd
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../lib/api';

interface Exercise {
  id: number;
  name: string;
  unit_of_measure: string;
  event_id: number;
}

interface User {
  id: number;
  nome: string;
  email: string;
  department?: string;
}

interface Evaluator {
  id: number;
  exercise_id: number;
  evaluator_user_id: number;
  is_primary: boolean;
  evaluator_name?: string;
  evaluator_email?: string;
}

export default function TAFEvaluatorsPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { eventId } = useParams<{ eventId: string }>();

  // Estados
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [evaluatorsByExercise, setEvaluatorsByExercise] = useState<Record<number, Evaluator[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [eventName, setEventName] = useState<string>('');

  // Modal
  const [openModal, setOpenModal] = useState(false);
  const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([]);
  const [primaryUserId, setPrimaryUserId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  // Carregar dados
  useEffect(() => {
    if (eventId) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, token]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Carrega evento
      const eventResponse = await api.get(`/taf/events/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEventName(eventResponse.data.name);

      // Carrega exercícios
      const exercisesResponse = await api.get(`/taf/exercises/by-event/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setExercises(exercisesResponse.data || []);

      // Carrega usuários
      const usersResponse = await api.get('/users/', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUsers(usersResponse.data || []);

      // Carrega avaliadores de cada exercício
      const evaluatorsMap: Record<number, Evaluator[]> = {};
      for (const exercise of exercisesResponse.data || []) {
        try {
          const evalResponse = await api.get(`/taf/evaluators/exercise/${exercise.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          evaluatorsMap[exercise.id] = evalResponse.data.evaluators || [];
        } catch (err) {
          evaluatorsMap[exercise.id] = [];
        }
      }
      setEvaluatorsByExercise(evaluatorsMap);

    } catch (err: any) {
      console.error('Erro ao carregar dados:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao carregar dados'));
    } finally {
      setLoading(false);
    }
  };

  const handleOpenModal = (exercise: Exercise) => {
    setSelectedExercise(exercise);
    
    // Pré-seleciona avaliadores já vinculados
    const currentEvaluators = evaluatorsByExercise[exercise.id] || [];
    const userIds = currentEvaluators.map(e => e.evaluator_user_id);
    const primary = currentEvaluators.find(e => e.is_primary)?.evaluator_user_id || null;
    
    setSelectedUserIds(userIds);
    setPrimaryUserId(primary);
    setOpenModal(true);
  };

  const handleCloseModal = () => {
    setOpenModal(false);
    setSelectedExercise(null);
    setSelectedUserIds([]);
    setPrimaryUserId(null);
  };

  const handleToggleUser = (userId: number) => {
    setSelectedUserIds(prev => {
      if (prev.includes(userId)) {
        // Remove
        if (primaryUserId === userId) {
          setPrimaryUserId(null);
        }
        return prev.filter(id => id !== userId);
      } else {
        // Adiciona
        return [...prev, userId];
      }
    });
  };

  const handleSubmitEvaluators = async () => {
    if (!selectedExercise) return;

    setSaving(true);
    setError(null);

    try {
      // Usa endpoint bulk para substituir todos os avaliadores
      await api.post('/taf/evaluators/bulk', {
        exercise_id: selectedExercise.id,
        evaluator_ids: selectedUserIds,
        primary_evaluator_id: primaryUserId
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setSuccess('Avaliadores atualizados com sucesso!');
      handleCloseModal();
      loadData(); // Recarrega dados
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao salvar avaliadores:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao salvar avaliadores'));
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveEvaluator = async (evaluatorId: number) => {
    if (!window.confirm('Tem certeza que deseja remover este avaliador?')) {
      return;
    }

    try {
      await api.delete(`/taf/evaluators/${evaluatorId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuccess('Avaliador removido com sucesso!');
      loadData();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao remover avaliador:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao remover avaliador'));
    }
  };

  const handleSetPrimary = async (evaluatorId: number) => {
    try {
      await api.patch(`/taf/evaluators/${evaluatorId}/primary`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuccess('Avaliador primário definido!');
      loadData();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao definir avaliador primário:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao definir avaliador primário'));
    }
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabeçalho */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <IconButton onClick={() => navigate(`/taf/events/${eventId}/exercises`)}>
            <ArrowBack />
          </IconButton>
          <Box>
            <Typography variant="h3" component="h1" fontWeight={700}>
              <PersonAdd sx={{ verticalAlign: 'middle', mr: 1 }} /> Vincular Avaliadores
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {eventName ? `Evento: ${eventName}` : 'Carregando...'}
            </Typography>
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

      {/* Lista de Exercícios com Avaliadores */}
      {!loading && (
        <Stack spacing={3}>
          {exercises.length === 0 ? (
            <Paper sx={{ p: 8, textAlign: 'center' }}>
              <FitnessCenter sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
              <Typography variant="h6" color="text.secondary">
                Nenhum exercício cadastrado
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Adicione exercícios primeiro para poder vincular avaliadores
              </Typography>
            </Paper>
          ) : (
            exercises.map((exercise) => {
              const evaluators = evaluatorsByExercise[exercise.id] || [];
              const primaryEvaluator = evaluators.find(e => e.is_primary);

              return (
                <Card key={exercise.id} elevation={3}>
                  <CardContent>
                    <Stack direction="row" justifyContent="space-between" alignItems="start" sx={{ mb: 2 }}>
                      <Box>
                        <Typography variant="h6" fontWeight={600}>
                          <FitnessCenter sx={{ verticalAlign: 'middle', mr: 1, fontSize: 20 }} />
                          {exercise.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {exercise.unit_of_measure}
                        </Typography>
                      </Box>
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={<Add />}
                        onClick={() => handleOpenModal(exercise)}
                      >
                        {evaluators.length > 0 ? 'Editar Avaliadores' : 'Adicionar Avaliadores'}
                      </Button>
                    </Stack>

                    <Divider sx={{ mb: 2 }} />

                    {evaluators.length === 0 ? (
                      <Box sx={{ textAlign: 'center', py: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Nenhum avaliador vinculado
                        </Typography>
                        <Button
                          variant="text"
                          size="small"
                          startIcon={<Add />}
                          onClick={() => handleOpenModal(exercise)}
                          sx={{ mt: 1 }}
                        >
                          Adicionar Primeiro Avaliador
                        </Button>
                      </Box>
                    ) : (
                      <Box>
                        <Typography variant="subtitle2" gutterBottom>
                          Avaliadores ({evaluators.length}):
                        </Typography>
                        <Stack spacing={1}>
                          {evaluators.map((evaluator) => (
                            <Card key={evaluator.id} variant="outlined">
                              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                                <Stack direction="row" alignItems="center" justifyContent="space-between">
                                  <Stack direction="row" spacing={2} alignItems="center">
                                    <Avatar sx={{ width: 40, height: 40, bgcolor: evaluator.is_primary ? 'primary.main' : 'grey.400' }}>
                                      {evaluator.evaluator_name?.charAt(0).toUpperCase()}
                                    </Avatar>
                                    <Box>
                                      <Stack direction="row" spacing={1} alignItems="center">
                                        <Typography variant="body1" fontWeight={evaluator.is_primary ? 600 : 400}>
                                          {evaluator.evaluator_name}
                                        </Typography>
                                        {evaluator.is_primary && (
                                          <Chip
                                            icon={<Star />}
                                            label="Primário"
                                            size="small"
                                            color="primary"
                                          />
                                        )}
                                      </Stack>
                                      <Typography variant="caption" color="text.secondary">
                                        {evaluator.evaluator_email}
                                      </Typography>
                                    </Box>
                                  </Stack>

                                  <Stack direction="row" spacing={1}>
                                    {!evaluator.is_primary && (
                                      <IconButton
                                        size="small"
                                        onClick={() => handleSetPrimary(evaluator.id)}
                                        title="Definir como primário"
                                      >
                                        <StarBorder fontSize="small" />
                                      </IconButton>
                                    )}
                                    <IconButton
                                      size="small"
                                      color="error"
                                      onClick={() => handleRemoveEvaluator(evaluator.id)}
                                    >
                                      <Delete fontSize="small" />
                                    </IconButton>
                                  </Stack>
                                </Stack>
                              </CardContent>
                            </Card>
                          ))}
                        </Stack>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              );
            })
          )}
        </Stack>
      )}

      {/* Modal de Seleção de Avaliadores */}
      <Dialog open={openModal} onClose={handleCloseModal} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedExercise ? `Avaliadores - ${selectedExercise.name}` : 'Adicionar Avaliadores'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Selecione os avaliadores que irão lançar resultados neste exercício.
            </Typography>

            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Usuários Disponíveis:
              </Typography>
              <List sx={{ maxHeight: 400, overflow: 'auto' }}>
                {users.map((user) => {
                  const isSelected = selectedUserIds.includes(user.id);
                  const isPrimary = primaryUserId === user.id;

                  return (
                    <ListItem
                      key={user.id}
                      dense
                      button
                      onClick={() => handleToggleUser(user.id)}
                      sx={{
                        border: 1,
                        borderColor: isSelected ? 'primary.main' : 'divider',
                        borderRadius: 1,
                        mb: 1,
                        bgcolor: isSelected ? 'primary.50' : 'transparent'
                      }}
                    >
                      <Checkbox
                        checked={isSelected}
                        tabIndex={-1}
                        disableRipple
                      />
                      <ListItemAvatar>
                        <Avatar sx={{ bgcolor: isPrimary ? 'primary.main' : 'grey.400' }}>
                          {user.nome.charAt(0).toUpperCase()}
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={user.nome}
                        secondary={user.email}
                      />
                      {isPrimary && (
                        <Chip
                          icon={<Star />}
                          label="Primário"
                          size="small"
                          color="primary"
                        />
                      )}
                    </ListItem>
                  );
                })}
              </List>
            </Box>

            {selectedUserIds.length > 0 && (
              <TextField
                label="Avaliador Primário"
                select
                value={primaryUserId || ''}
                onChange={(e) => setPrimaryUserId(Number(e.target.value) || null)}
                fullWidth
                helperText="O avaliador primário é o responsável principal pelo exercício"
              >
                <MenuItem value="">
                  <em>Nenhum</em>
                </MenuItem>
                {selectedUserIds.map(userId => {
                  const user = users.find(u => u.id === userId);
                  return user ? (
                    <MenuItem key={userId} value={userId}>
                      {user.nome}
                    </MenuItem>
                  ) : null;
                })}
              </TextField>
            )}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={handleCloseModal} disabled={saving}>
            Cancelar
          </Button>
          <Button
            onClick={handleSubmitEvaluators}
            variant="contained"
            disabled={saving || selectedUserIds.length === 0}
            startIcon={saving ? <CircularProgress size={20} /> : <Add />}
          >
            {saving ? 'Salvando...' : 'Salvar Avaliadores'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
