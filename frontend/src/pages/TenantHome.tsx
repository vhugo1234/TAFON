import React, { useEffect, useState, useMemo } from 'react';
import { 
  Box, Typography, Container, Grid, Card, CardContent, CardActions,
  Button, Stack, Avatar, Chip, LinearProgress, Paper, Divider,
  List, ListItem, ListItemText, ListItemAvatar, IconButton, useTheme, Tooltip
} from '@mui/material';
import { 
  FitnessCenter, People, Event, Assessment, TrendingUp,
  Add, Visibility, ArrowForward, CalendarToday, PersonAdd,
  Edit, BarChart, CheckCircle, Schedule, Settings
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import { FULL_ACCESS, FINANCIAL_ACCESS } from '../utils/roles';
import LogoutButton from '../components/LogoutButton';

interface DashboardStats {
  totalEvents: number;
  activeEvents: number;
  totalCandidates: number;
  totalExercises: number;
  recentEvents: Array<{
    id: number;
    name: string;
    date_start: string;
    location: string;
    is_active: boolean;
  }>;
}

const TenantHome: React.FC = () => {
  const { user, token, logout, hasAnyRole } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  
  const [stats, setStats] = useState<DashboardStats>({
    totalEvents: 0,
    activeEvents: 0,
    totalCandidates: 0,
    totalExercises: 0,
    recentEvents: []
  });
  const [loading, setLoading] = useState(true);

  const tenantName = user?.empresa || user?.schemaName || 'Seu Sistema TAF';

  useEffect(() => {
    loadDashboardData();
  }, [token]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      
      // Carregar apenas eventos (candidatos são específicos por evento)
      const eventsRes = await api.get('/taf/events/', { 
        headers: { Authorization: `Bearer ${token}` } 
      });

      const events = eventsRes.data.items || eventsRes.data || [];

      // Calcular total de candidatos somando de todos os eventos
      const totalCandidates = events.reduce((sum: number, event: any) => {
        return sum + (event.total_candidates || 0);
      }, 0);

      setStats({
        totalEvents: events.length,
        activeEvents: events.filter((e: any) => e.is_active).length,
        totalCandidates: totalCandidates,
        totalExercises: 0,
        recentEvents: events.slice(0, 5)
      });
    } catch (error) {
      console.error('Erro ao carregar dados do dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  // Permissões
  const canFullAccess = hasAnyRole(FULL_ACCESS);
  const canAccessFinancial = hasAnyRole(FINANCIAL_ACCESS);

  const statCards = [
    {
      title: 'Eventos Totais',
      value: stats.totalEvents,
      icon: <Event sx={{ fontSize: 40 }} />,
      color: theme.palette.primary.main,
      action: () => navigate('/taf/events'),
      visible: true
    },
    {
      title: 'Eventos Ativos',
      value: stats.activeEvents,
      icon: <CheckCircle sx={{ fontSize: 40 }} />,
      color: theme.palette.success.main,
      action: () => navigate('/taf/events'),
      visible: true
    },
    {
      title: 'Candidatos',
      value: stats.totalCandidates,
      icon: <People sx={{ fontSize: 40 }} />,
      color: theme.palette.info.main,
      action: () => navigate('/taf/candidates'),
      visible: true
    },
    {
      title: 'Relatórios',
      value: 'Ver Todos',
      icon: <Assessment sx={{ fontSize: 40 }} />,
      color: theme.palette.warning.main,
      action: () => navigate('/taf/results'),
      visible: canFullAccess // só quem tem acesso total vê relatórios consolidados
    }
  ];

  const quickActions = [
    {
      title: 'Gerenciar Eventos',
      description: 'Ver e criar eventos TAF',
      icon: <Event />,
      color: 'primary',
      action: () => navigate('/taf/events'),
      visible: canFullAccess
    },
    {
      title: 'Ver Relatórios',
      description: 'Análise de resultados',
      icon: <BarChart />,
      color: 'warning',
      action: () => navigate('/taf/results'),
      visible: canFullAccess
    },
    {
      title: 'Configurações',
      description: 'Gerenciar usuários e sistema',
      icon: <Settings />,
      color: 'secondary',
      action: () => navigate('/settings'),
      visible: canFullAccess // ou ajustar para apenas ADMIN/COORD_GERAL se quiser
    },
    // NOVA AÇÃO: Página de Presenças (mantida entre ações rápidas, mas removida do cabeçalho)
    {
      title: 'Presenças',
      description: 'Registrar e visualizar presenças do evento',
      icon: <PersonAdd />,
      color: 'success',
      action: () => navigate('/attendance'),
      visible: canFullAccess || canAccessFinancial // ajuste conforme regras de visibilidade
    }
  ];

  // --- NOVA LÓGICA: detectar avaliador limitado e obter exercícios vinculados do user ---
  const isEvaluatorLimited = useMemo(() => {
    if (!user) return false;
    const asFlag = !!(user as any).evaluator_limited_view;
    const byRole = (user.roles || []).some((r: string) => String(r).toUpperCase() === 'AVALIADOR_EF') ||
                   (user.role && String(user.role).toUpperCase() === 'AVALIADOR_EF') ||
                   (user.role_id !== undefined && Number(user.role_id) === 4);
    return asFlag || byRole;
  }, [user]);

  const assignedExercises: Array<any> = useMemo(() => {
    const arr = (user as any)?.assigned_exercises || [];
    if (!Array.isArray(arr)) return [];
    return arr.map((a: any) => ({
      exercise_id: Number(a.exercise_id),
      event_id: Number(a.event_id),
      exercise_name: a.exercise_name ?? a.name ?? `Exercício ${a.exercise_id}`,
      is_primary: !!a.is_primary
    }));
  }, [user]);

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Cabeçalho de Boas-vindas */} 
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2}>
          <Box>
            <Typography variant="h3" component="h1" gutterBottom fontWeight={700}>
              Bem-vindo, {user?.nome || user?.email || 'Usuário'}! 👋
            </Typography>
            <Typography variant="h6" color="text.secondary">
              {tenantName} • Painel de Controle TAF
            </Typography>
          </Box>

          {/* Removido botão "Presenças" do cabeçalho; apenas Logout permanece */}
          <Stack direction="row" spacing={1} alignItems="center">
            <LogoutButton variant="outlined" size="small" color="error" showText />
          </Stack>
        </Stack>
      </Box>

      {/* Se o usuário for avaliador limitado, mostrar seus exercícios vinculados em destaque */}
      {isEvaluatorLimited && (
        <Box sx={{ mb: 3 }}>
          <Paper sx={{ p: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="h6" fontWeight={600}>Seus Exercícios Vinculados</Typography>
              <Typography variant="body2" color="text.secondary">
                {assignedExercises.length} vínculo(s)
              </Typography>
            </Stack>
            <Divider sx={{ mb: 2 }} />
            {assignedExercises.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 3 }}>
                <Typography variant="body2" color="text.secondary">Você não está vinculado a nenhum exercício.</Typography>
              </Box>
            ) : (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                {assignedExercises.map((ae) => (
                  <Card key={`${ae.event_id}-${ae.exercise_id}`} sx={{ minWidth: 240 }}>
                    <CardContent>
                      <Typography variant="subtitle1" fontWeight={600}>{ae.exercise_name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Evento: {ae.event_id}
                      </Typography>
                    </CardContent>
                    <CardActions>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<FitnessCenter />}
                        onClick={() => navigate(`/taf/events/${ae.event_id}/exercises/${ae.exercise_id}/field`)}
                      >
                        Avaliar em Campo
                      </Button>
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => { logout(); navigate('/login'); }}
                      >
                        Sair
                      </Button>
                    </CardActions>
                  </Card>
                ))}
              </Stack>
            )}
          </Paper>
        </Box>
      )}

      {/* Cards de Estatísticas */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {statCards.filter(c => c.visible).map((card, index) => (
          <Grid item xs={12} sm={6} md={3} key={index}>
            <Card 
              sx={{ 
                height: '100%',
                cursor: 'pointer',
                transition: 'all 0.3s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 6
                }
              }}
              onClick={card.action}
            >
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      {card.title}
                    </Typography>
                    <Typography variant="h3" fontWeight={700}>
                      {card.value}
                    </Typography>
                  </Box>
                  <Avatar 
                    sx={{ 
                      bgcolor: `${card.color}20`,
                      color: card.color,
                      width: 56,
                      height: 56
                    }}
                  >
                    {card.icon}
                  </Avatar>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3}>
        {/* Ações Rápidas */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h5" gutterBottom fontWeight={600} sx={{ mb: 3 }}>
              ⚡ Ações Rápidas
            </Typography>
            <Grid container spacing={2}>
              {quickActions.filter(a => a.visible).map((action, index) => (
                <Grid item xs={12} sm={6} key={index}>
                  <Card 
                    sx={{ 
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      '&:hover': {
                        boxShadow: 4,
                        transform: 'scale(1.02)'
                      }
                    }}
                    onClick={action.action}
                  >
                    <CardContent>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <Avatar sx={{ bgcolor: `${action.color}.main` }}>
                          {action.icon}
                        </Avatar>
                        <Box>
                          <Typography variant="subtitle1" fontWeight={600}>
                            {action.title}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {action.description}
                          </Typography>
                        </Box>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>

        {/* Eventos Recentes */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Typography variant="h5" fontWeight={600}>
                📅 Eventos Recentes
              </Typography>
              <Button 
                size="small" 
                endIcon={<ArrowForward />}
                onClick={() => navigate('/taf/events')}
              >
                Ver Todos
              </Button>
            </Stack>
            
            {loading ? (
              <LinearProgress />
            ) : stats.recentEvents.length > 0 ? (
              <List>
                {stats.recentEvents.map((event, index) => (
                  <React.Fragment key={event.id}>
                    <ListItem
                      sx={{ 
                        cursor: 'pointer',
                        borderRadius: 1,
                        '&:hover': { bgcolor: 'action.hover' },
                        py: 1.5
                      }}
                      onClick={() => navigate(`/taf/events/${event.id}`)}
                    >
                      <ListItemAvatar>
                        <Avatar sx={{ bgcolor: event.is_active ? 'success.main' : 'grey.400' }}>
                          <CalendarToday />
                        </Avatar>
                      </ListItemAvatar>

                      {/* Main content (left) */}
                      <Box sx={{ flex: 1, minWidth: 0, mr: 2 }}>
                        <ListItemText
                          primary={
                            <Stack direction="row" spacing={1} alignItems="center" sx={{ overflow: 'hidden' }}>
                              <Typography variant="subtitle1" fontWeight={600} noWrap>
                                {event.name}
                              </Typography>
                              <Chip 
                                label={event.is_active ? 'Ativo' : 'Inativo'} 
                                size="small"
                                color={event.is_active ? 'success' : 'default'}
                              />
                            </Stack>
                          }
                          secondary={
                            <Stack direction="row" spacing={2}>
                              <Typography variant="caption" color="text.secondary" noWrap>
                                📍 {event.location || 'Local não definido'}
                              </Typography>
                              <Typography variant="caption" noWrap>
                                📆 {event.date_start ? new Date(event.date_start).toLocaleDateString('pt-BR') : '—'}
                              </Typography>
                            </Stack>
                          }
                          primaryTypographyProps={{ component: 'div' }}
                          secondaryTypographyProps={{ component: 'div' }}
                        />
                      </Box>

                      {/* Actions (right) - kept outside text to avoid overlap */}
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, alignItems: 'flex-end' }}>
                        {(canFullAccess || canAccessFinancial) && (
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={(e) => { e.stopPropagation(); navigate(`/taf/events/${event.id}/workers`); }}
                          >
                            Equipe
                          </Button>
                        )}
                        <Tooltip title="Visualizar evento">
                          <IconButton size="small" onClick={(e) => { e.stopPropagation(); navigate(`/taf/events/${event.id}`); }}>
                            <Visibility />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </ListItem>
                    {index < stats.recentEvents.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            ) : (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <Typography variant="body2" color="text.secondary">
                  Nenhum evento cadastrado ainda.
                </Typography>
                <Button 
                  variant="contained" 
                  startIcon={<Add />}
                  sx={{ mt: 2 }}
                  onClick={() => navigate('/taf/events')}
                >
                  Criar Primeiro Evento
                </Button>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Banner de Ajuda */}
      <Paper 
        sx={{ 
          mt: 4, 
          p: 3, 
          background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
          color: 'white'
        }}
      >
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="h5" gutterBottom fontWeight={600}>
              🚀 Precisa de ajuda para começar?
            </Typography>
            <Typography variant="body1" component="div">
              Explore nossos guias e tutoriais para aproveitar ao máximo o Sistema TAF.
              Configure eventos, cadastre candidatos e acompanhe resultados em tempo real.
            </Typography>
          </Grid>
          <Grid item xs={12} md={4} sx={{ textAlign: { md: 'right' } }}>
            <Stack direction="row" spacing={2} justifyContent={{ xs: 'flex-start', md: 'flex-end' }}>
              <Button 
                variant="contained" 
                sx={{ 
                  bgcolor: 'white', 
                  color: 'primary.main',
                  '&:hover': { bgcolor: 'grey.100' }
                }}
              >
                Ver Guia
              </Button>
              <Button 
                variant="outlined" 
                sx={{ 
                  borderColor: 'white', 
                  color: 'white',
                  '&:hover': { borderColor: 'white', bgcolor: 'rgba(255,255,255,0.1)' }
                }}
              >
                Suporte
              </Button>
            </Stack>
          </Grid>
        </Grid>
      </Paper>
    </Container>
  );
};

export default TenantHome;
