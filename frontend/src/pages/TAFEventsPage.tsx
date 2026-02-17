import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Container, Typography, Box, Button, Grid, Card, CardContent, CardActions,
  Chip, IconButton, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Stack, Alert, CircularProgress, InputAdornment, MenuItem,
  Pagination, Tooltip, useTheme, Paper, Divider
} from '@mui/material';
import {
  Add, Edit, Delete, Visibility, Search, FilterList, Event as EventIcon,
  People, FitnessCenter, CalendarToday, LocationOn, CheckCircle, Cancel, Assessment
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import LogoutButton from '../components/LogoutButton';

interface TAFEvent {
  id: number;
  name: string;
  date_start: string;
  date_end: string;
  location: string;
  is_active: boolean;
  total_candidates: number;
  total_exercises: number;
  event_dates?: string[]; // opcional, quando disponível (YYYY-MM-DD)
  // opcional: campo para exibir nome do coordenador caso API retorne
  coordinator_name?: string;
  coordinator?: { id?: number; full_name?: string };
}

interface FormState {
  name: string;
  date_start: string;
  date_end: string;
  location: string;
  is_active: boolean;
  coordinator_id?: number | null; // ID do Coordenador de Educação Física (opcional)
}

const initialFormState: FormState = {
  name: '',
  date_start: new Date().toISOString().split('T')[0],
  date_end: new Date().toISOString().split('T')[0],
  location: '',
  is_active: true,
  coordinator_id: null
};

export default function TAFEventsPage() {
  const theme = useTheme();
  const { token, logout, user } = useAuth();
  const navigate = useNavigate();

  // --- determina se o usuário é avaliador limitado (muito restrito) ---
  const isEvaluatorLimited = useMemo(() => {
    if (!user) return false;
    const asFlag = !!(user as any).evaluator_limited_view;
    const byRole = (user.roles || []).some((r: string) => String(r).toUpperCase() === 'AVALIADOR_EF') ||
                   (user.role && String(user.role).toUpperCase() === 'AVALIADOR_EF') ||
                   (user.role_id !== undefined && Number(user.role_id) === 4);
    return asFlag || byRole;
  }, [user]);

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

  // Event_dates UI
  const [eventDates, setEventDates] = useState<string[]>([]);
  const [newEventDate, setNewEventDate] = useState<string>('');

  // Filtros e Paginação
  const [search, setSearch] = useState('');
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 9;

  // Funções utilitárias para lidar com datas sem timezone issues
  const pad = (n: number) => String(n).padStart(2, '0');

  const formatDateYMD = (d: Date) => {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  };

  // recebe "YYYY-MM-DD" -> formata para "DD/MM/YYYY" para exibição (sem criar Date direto)
  const formatYMDToDisplay = (ymd?: string) => {
    if (!ymd) return '';
    const parts = ymd.split('-');
    if (parts.length !== 3) return ymd;
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  };

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

  // --- NEW: coordenadores (para vincular ao evento) ---
  const [coordinators, setCoordinators] = useState<Array<{ id: number; full_name: string }>>([]);
  const [loadingCoordinators, setLoadingCoordinators] = useState(false);

  const loadCoordinators = useCallback(async () => {
    try {
      setLoadingCoordinators(true);
      // Chama o endpoint correto que será exposto em events_taf.py
      // Ajuste a URL se sua API expõe o router em outro prefixo
      const resp = await api.get('/taf/events/coordinators', {
        headers: { Authorization: `Bearer ${token}` }
      });
      // o backend retorna lista direta [{id, nome, email}, ...]
      const items = resp.data || [];
      const mapped = items.map((u: any) => ({
        id: u.id,
        full_name: u.nome ?? u.name ?? u.full_name ?? `${u.first_name || ''} ${u.last_name || ''}`.trim()
      })).filter((x: any) => x.id !== undefined && x.full_name);
      setCoordinators(mapped);
    } catch (err) {
      console.warn('Não foi possível carregar coordenadores (verifique endpoint):', err);
      setCoordinators([]);
    } finally {
      setLoadingCoordinators(false);
    }
  }, [token]);

  useEffect(() => {
    loadCoordinators();
  }, [loadCoordinators]);

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
    setEventDates([]);
    setNewEventDate('');
    setOpenModal(true);
    loadCoordinators();
  };

  // Ao editar, buscar o evento completo (incluindo event_dates)
  const handleOpenEdit = async (event: TAFEvent) => {
    try {
      setLoading(true);
      const response = await api.get(`/taf/events/${event.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const ev = response.data;
      setForm({
        name: ev.name,
        date_start: ev.date_start,
        date_end: ev.date_end,
        location: ev.location,
        is_active: ev.is_active,
        coordinator_id: ev.coordinator_id ?? ev.coordinator_user_id ?? ev.coordinator?.id ?? null
      });
      setEditingEvent(ev);

      // preenche eventDates se retornado pelo backend; senao tenta gerar a partir do intervalo
      if (ev.event_dates && Array.isArray(ev.event_dates) && ev.event_dates.length > 0) {
        // assume backend returns array of "YYYY-MM-DD"
        setEventDates(ev.event_dates.map((d: string) => d));
      } else {
        // gera intervalo a partir de date_start..date_end usando componentes (sem timezone)
        try {
          const [ys, ms, ds] = ev.date_start.split('-').map(Number);
          const [ye, me, de] = ev.date_end.split('-').map(Number);
          const dates: string[] = [];
          for (let dt = new Date(ys, ms - 1, ds); ; dt.setDate(dt.getDate() + 1)) {
            dates.push(formatDateYMD(new Date(dt)));
            const curY = dt.getFullYear();
            const curM = dt.getMonth() + 1;
            const curD = dt.getDate();
            if (curY === ye && curM === me && curD === de) break;
          }
          setEventDates(dates);
        } catch {
          setEventDates([]);
        }
      }
      setNewEventDate('');

      // Carrega coordenadores atualizados antes de abrir o modal
      try {
        await loadCoordinators();
      } catch (err) {
        console.warn('Falha ao recarregar coordenadores (mas abrindo modal mesmo assim):', err);
      }

      setOpenModal(true);
    } catch (err: any) {
      console.error('Erro ao buscar evento para edição', err);
      setError('Erro ao carregar evento para edição');
    } finally {
      setLoading(false);
    }
  };

  const handleCloseModal = () => {
    setOpenModal(false);
    setEditingEvent(null);
    setForm(initialFormState);
    setEventDates([]);
    setNewEventDate('');
    setError(null);
  };

  const addEventDate = () => {
    if (!newEventDate) return;
    if (eventDates.includes(newEventDate)) {
      setNewEventDate('');
      return;
    }
    const updated = [...eventDates, newEventDate].sort();
    setEventDates(updated);
    setNewEventDate('');
  };

  const removeEventDate = (d: string) => {
    setEventDates(prev => prev.filter(x => x !== d));
  };

  // Gera dates a partir do intervalo usando componentes (evita timezone shift)
  const generateDatesFromInterval = () => {
    try {
      // parse form.date_start and form.date_end which are "YYYY-MM-DD"
      const [ys, ms, ds] = form.date_start.split('-').map(Number);
      const [ye, me, de] = form.date_end.split('-').map(Number);
      const start = new Date(ys, ms - 1, ds);
      const end = new Date(ye, me - 1, de);

      if (start > end) {
        setError('Data de início deve ser anterior ou igual à data de término para gerar as datas.');
        return;
      }
      const dates: string[] = [];
      for (let dt = new Date(start); dt.getTime() <= end.getTime(); dt.setDate(dt.getDate() + 1)) {
        dates.push(formatDateYMD(new Date(dt))); // usa getters locais para formatar YYYY-MM-DD
      }
      setEventDates(dates);
    } catch (e) {
      setError('Erro ao gerar datas a partir do intervalo.');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    // payload: incluir event_dates se user adicionou datas explícitas
    const payload: any = {
      name: form.name,
      date_start: form.date_start,
      date_end: form.date_end,
      location: form.location,
      is_active: form.is_active
    };
    if (eventDates && eventDates.length > 0) {
      payload.event_dates = eventDates;
    }
    // incluir coordinator_id se selecionado (ajuste o nome do campo se backend esperar outro)
    if (form.coordinator_id !== undefined && form.coordinator_id !== null && form.coordinator_id !== '') {
      payload.coordinator_id = form.coordinator_id;
    }

    try {
      if (editingEvent) {
        await api.patch(`/taf/events/${editingEvent.id}`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccess('Evento atualizado com sucesso!');
      } else {
        await api.post('/taf/events/', payload, {
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
          <Stack direction="row" spacing={2} alignItems="center">
            {/* Novo Evento só para não-gerentes/avaliadores */}
            {!isEvaluatorLimited && (
              <Button
                variant="contained"
                size="large"
                startIcon={<Add />}
                onClick={handleOpenCreate}
              >
                Novo Evento
              </Button>
            )}

            {/* Botão Sair sempre visível (padronizado) */}
            <LogoutButton variant="outlined" size="small" color="error" showText />
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
                          {formatYMDToDisplay(event.date_start)} até {formatYMDToDisplay(event.date_end)}
                        </Typography>
                      </Stack>

                      <Stack direction="row" alignItems="center" spacing={1}>
                        <LocationOn fontSize="small" color="action" />
                        <Typography variant="body2" color="text.secondary" noWrap>
                          {event.location}
                        </Typography>
                      </Stack>

                      {/* Coordenador (se disponível) */}
                      {(event.coordinator_name || event.coordinator?.full_name) && (
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <People fontSize="small" color="action" />
                          <Typography variant="body2" color="text.secondary" noWrap>
                            Coordenador: {event.coordinator_name ?? event.coordinator?.full_name}
                          </Typography>
                        </Stack>
                      )}

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
                      {/* Ações: se avaliador limitado, mostrar apenas "Exercícios" */}
                      {isEvaluatorLimited ? (
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<FitnessCenter />}
                          onClick={() => navigate(`/taf/events/${event.id}/exercises`)}
                        >
                          Exercícios
                        </Button>
                      ) : (
                        <>
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
                        </>
                      )}
                    </Stack>
                    {/* Controles de edição/exclusão apenas para não avaliadores */}
                    {!isEvaluatorLimited ? (
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
                    ) : (
                      <Box /> /* placeholder para manter layout */
                    )}
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
              {!isEvaluatorLimited && (
                <Button variant="contained" startIcon={<Add />} onClick={handleOpenCreate}>
                  Criar Primeiro Evento
                </Button>
              )}
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

              {/* === NEW: Seleção do Coordenador de Educação Física === */}
              <TextField
                select
                label="Coordenador (Educação Física)"
                name="coordinator_id"
                value={form.coordinator_id ?? ''}
                onChange={(e) => setForm(prev => ({ ...prev, coordinator_id: e.target.value === '' ? null : Number(e.target.value) }))}
                fullWidth
                size="small"
                helperText={loadingCoordinators ? 'Carregando coordenadores...' : 'Selecione o coordenador responsável pelo evento (opcional)'}
                sx={{ mt: 2 }}
              >
                <MenuItem value="">— Nenhum —</MenuItem>
                {loadingCoordinators ? (
                  <MenuItem disabled>Carregando...</MenuItem>
                ) : (
                  coordinators.map(c => (
                    <MenuItem key={c.id} value={c.id}>{c.full_name}</MenuItem>
                  ))
                )}
              </TextField>
              {/* === END NEW === */}

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

              {/* Novas datas explícitas do evento */}
              <Divider />
              <Typography variant="subtitle1">Datas do Evento (opcional)</Typography>
              <Typography variant="caption" color="text.secondary">
                Adicione as datas específicas em que o evento ocorrerá (ex.: finais de semana não-consecutivos).
              </Typography>

              <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 1 }}>
                <TextField
                  type="date"
                  value={newEventDate}
                  onChange={(e) => setNewEventDate(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  fullWidth
                />
                <Button variant="outlined" onClick={addEventDate}>Adicionar data</Button>
                <Button variant="text" onClick={generateDatesFromInterval}>Gerar a partir do intervalo</Button>
              </Stack>

              <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>
                {eventDates.map((d) => (
                  <Chip
                    key={d}
                    label={formatYMDToDisplay(d)}
                    onDelete={() => removeEventDate(d)}
                    sx={{ mr: 1, mb: 1 }}
                  />
                ))}
                {eventDates.length === 0 && (
                  <Typography variant="caption" color="text.secondary">Nenhuma data adicionada — será usado o intervalo start..end por padrão.</Typography>
                )}
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
