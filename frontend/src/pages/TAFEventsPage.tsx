// frontend/src/pages/TAFEventsPage.tsx

import React, { useEffect, useState, useCallback } from 'react';
import {
  Container, Typography, Box, Button, Grid, Card, CardContent, CardActions,
  Chip, IconButton, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Stack, Alert, CircularProgress, InputAdornment, MenuItem,
  Pagination, Tooltip, useTheme, Paper, Divider
} from '@mui/material';
import {
  Add, Edit, Delete, Visibility, Search, FilterList, Event as EventIcon,
  People, FitnessCenter, CalendarToday, LocationOn, CheckCircle, Cancel, Assessment, Logout
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';

interface TAFEvent {
  id: number;
  name: string;
  date_start: string;
  date_end: string;
  location: string;
  is_active: boolean;
  total_candidates: number;
  total_exercises: number;
}

interface FormState {
  name: string;
  date_start: string;
  date_end: string;
  location: string;
  is_active: boolean;
}

const initialFormState: FormState = {
  name: '',
  date_start: new Date().toISOString().split('T')[0],
  date_end: new Date().toISOString().split('T')[0],
  location: '',
  is_active: true
};

export default function TAFEventsPage() {
  const theme = useTheme();
  const { token, logout } = useAuth();
  const navigate = useNavigate();

  // Estados
  const [events, setEvents] = useState<TAFEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Modal
  const [openModal, setOpenModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<TAFEvent | null>(null);
  const [form, setForm] = useState<FormState>(initialFormState);

  // Filtros e Paginação
  const [search, setSearch] = useState('');
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 9;

  // Carregar eventos
  const loadEvents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params: any = {
        page,
        page_size: pageSize
      };

      if (search) params.search = search;
      if (filterActive !== 'all') params.is_active = filterActive === 'active';

      const response = await api.get('/taf/events/', {
        params,
        headers: { Authorization: `Bearer ${token}` }
      });

      setEvents(response.data.items || []);
      setTotal(response.data.total || 0);
    } catch (err: any) {
      console.error('Erro ao carregar eventos:', err);
      setError(err?.response?.data?.detail || 'Erro ao carregar eventos');
    } finally {
      setLoading(false);
    }
  }, [token, page, pageSize, search, filterActive]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  // Handlers do formulário
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleOpenCreate = () => {
    setForm(initialFormState);
    setEditingEvent(null);
    setOpenModal(true);
  };

  const handleOpenEdit = (event: TAFEvent) => {
    setForm({
      name: event.name,
      date_start: event.date_start,
      date_end: event.date_end,
      location: event.location,
      is_active: event.is_active
    });
    setEditingEvent(event);
    setOpenModal(true);
  };

  const handleCloseModal = () => {
    setOpenModal(false);
    setEditingEvent(null);
    setForm(initialFormState);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      if (editingEvent) {
        await api.patch(`/taf/events/${editingEvent.id}`, form, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccess('Evento atualizado com sucesso!');
      } else {
        await api.post('/taf/events/', form, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccess('Evento criado com sucesso!');
      }

      handleCloseModal();
      loadEvents();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao salvar evento:', err);
      setError(err?.response?.data?.detail || 'Erro ao salvar evento');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (event: TAFEvent) => {
    if (!window.confirm(`Tem certeza que deseja excluir o evento "${event.name}"?\n\nISSO TAMBÉM DELETARÁ TODOS OS DADOS RELACIONADOS (exercícios, candidatos, resultados)!`)) {
      return;
    }

    try {
      await api.delete(`/taf/events/${event.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuccess('Evento deletado com sucesso!');
      loadEvents();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao deletar evento:', err);
      setError(err?.response?.data?.detail || 'Erro ao deletar evento');
    }
  };

  const handleViewDetails = (eventId: number) => {
    navigate(`/taf/events/${eventId}`);
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabeçalho */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
          <Box>
            <Typography
              variant="h3"
              component="h1"
              fontWeight={700}
              gutterBottom
              sx={{ display: 'flex', alignItems: 'center' }}
            >
              <EventIcon sx={{ mr: 1 }} />
              Eventos TAF
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Gerencie os eventos e concursos de Teste de Aptidão Física
            </Typography>
          </Box>
          <Stack direction="row" spacing={2}>
            <Button
              variant="contained"
              size="large"
              startIcon={<Add />}
              onClick={handleOpenCreate}
            >
              Novo Evento
            </Button>
            <Tooltip title="Sair do sistema">
              <Button
                variant="outlined"
                color="error"
                size="large"
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
        </Stack>
      </Box>

      {/* Alertas */}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}

      {/* Filtros */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
          <TextField
            placeholder="Buscar por nome ou local..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            size="small"
            fullWidth
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              )
            }}
          />
          <TextField
            select
            label="Status"
            value={filterActive}
            onChange={(e) => setFilterActive(e.target.value as any)}
            size="small"
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="all">Todos</MenuItem>
            <MenuItem value="active">Ativos</MenuItem>
            <MenuItem value="inactive">Inativos</MenuItem>
          </TextField>
          <Button
            variant="outlined"
            startIcon={<FilterList />}
            onClick={loadEvents}
          >
            Filtrar
          </Button>
        </Stack>
      </Paper>

      {/* Loading */}
      {loading && (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={60} />
        </Box>
      )}

      {/* Lista de Eventos */}
      {!loading && (
        <>
          <Grid container spacing={3}>
            {events.map((event) => (
              <Grid item xs={12} sm={6} md={4} key={event.id}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'all 0.3s',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: 6
                    }
                  }}
                >
                  <CardContent sx={{ flexGrow: 1 }}>
                    {/* Status Badge */}
                    <Box sx={{ mb: 2 }}>
                      <Chip
                        label={event.is_active ? 'Ativo' : 'Inativo'}
                        color={event.is_active ? 'success' : 'default'}
                        size="small"
                        icon={event.is_active ? <CheckCircle /> : <Cancel />}
                      />
                    </Box>

                    {/* Nome do Evento */}
                    <Typography variant="h6" fontWeight={600} gutterBottom noWrap>
                      {event.name}
                    </Typography>

                    <Divider sx={{ my: 1 }} />

                    {/* Detalhes */}
                    <Stack spacing={1} sx={{ mt: 2 }}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <CalendarToday fontSize="small" color="action" />
                        <Typography variant="body2" color="text.secondary">
                          {new Date(event.date_start).toLocaleDateString('pt-BR')} até {new Date(event.date_end).toLocaleDateString('pt-BR')}
                        </Typography>
                      </Stack>

                      <Stack direction="row" alignItems="center" spacing={1}>
                        <LocationOn fontSize="small" color="action" />
                        <Typography variant="body2" color="text.secondary" noWrap>
                          {event.location}
                        </Typography>
                      </Stack>

                      <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
                        <Chip
                          icon={<FitnessCenter />}
                          label={`${event.total_exercises} exercícios`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          icon={<People />}
                          label={`${event.total_candidates} candidatos`}
                          size="small"
                          variant="outlined"
                        />
                      </Stack>
                    </Stack>
                  </CardContent>

                  <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
                    <Stack direction="row" spacing={1}>
                      <Button
                        size="small"
                        startIcon={<Visibility />}
                        onClick={() => handleViewDetails(event.id)}
                      >
                        Detalhes
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<FitnessCenter />}
                        onClick={() => navigate(`/taf/events/${event.id}/exercises`)}
                      >
                        Exercícios
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<People />}
                        onClick={() => navigate(`/taf/events/${event.id}/candidates`)}
                      >
                        Candidatos
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Assessment />}
                        onClick={() => navigate(`/taf/events/${event.id}/results`)}
                      >
                        Resultados
                      </Button>
                    </Stack>
                    <Stack direction="row" spacing={1}>
                      <Tooltip title="Editar">
                        <IconButton size="small" color="primary" onClick={() => handleOpenEdit(event)}>
                          <Edit />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Excluir">
                        <IconButton size="small" color="error" onClick={() => handleDelete(event)}>
                          <Delete />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>

          {/* Sem resultados */}
          {events.length === 0 && (
            <Paper sx={{ p: 8, textAlign: 'center' }}>
              <EventIcon sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Nenhum evento encontrado
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Crie seu primeiro evento para começar a gerenciar os TAFs
              </Typography>
              <Button variant="contained" startIcon={<Add />} onClick={handleOpenCreate}>
                Criar Primeiro Evento
              </Button>
            </Paper>
          )}

          {/* Paginação */}
          {total > pageSize && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Pagination
                count={Math.ceil(total / pageSize)}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
                size="large"
              />
            </Box>
          )}
        </>
      )}

      {/* Modal de Criação/Edição */}
      <Dialog open={openModal} onClose={handleCloseModal} maxWidth="sm" fullWidth>
        <form onSubmit={handleSubmit}>
          <DialogTitle>
            {editingEvent ? 'Editar Evento' : 'Novo Evento'}
          </DialogTitle>
          <DialogContent>
            <Stack spacing={3} sx={{ mt: 1 }}>
              <TextField
                label="Nome do Evento *"
                name="name"
                value={form.name}
                onChange={handleChange}
                fullWidth
                required
                placeholder="Ex: TAF PMDF 2024"
              />

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Data de Início *"
                    name="date_start"
                    type="date"
                    value={form.date_start}
                    onChange={handleChange}
                    fullWidth
                    required
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Data de Término *"
                    name="date_end"
                    type="date"
                    value={form.date_end}
                    onChange={handleChange}
                    fullWidth
                    required
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
              </Grid>

              <TextField
                label="Local *"
                name="location"
                value={form.location}
                onChange={handleChange}
                fullWidth
                required
                placeholder="Ex: Centro de Educação Física - Brasília/DF"
              />

              <Stack direction="row" alignItems="center" spacing={2}>
                <Typography variant="body2">Status do Evento:</Typography>
                <Stack direction="row" spacing={1}>
                  <Chip
                    label="Ativo"
                    color={form.is_active ? 'success' : 'default'}
                    onClick={() => setForm(prev => ({ ...prev, is_active: true }))}
                    icon={<CheckCircle />}
                  />
                  <Chip
                    label="Inativo"
                    color={!form.is_active ? 'error' : 'default'}
                    onClick={() => setForm(prev => ({ ...prev, is_active: false }))}
                    icon={<Cancel />}
                  />
                </Stack>
              </Stack>
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 3 }}>
            <Button onClick={handleCloseModal} disabled={saving}>
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={saving}
              startIcon={saving ? <CircularProgress size={20} /> : null}
            >
              {editingEvent ? 'Atualizar' : 'Criar'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Container>
  );
}






