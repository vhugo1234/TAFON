import React, { useEffect, useState } from 'react';
import {
  Container, Typography, Box, Button, Paper, Stack, Alert,
  TextField, MenuItem, FormControlLabel, Switch, Stepper, Step,
  StepLabel, Card, CardContent, Chip, IconButton, Divider, CircularProgress
} from '@mui/material';
import { Grid } from '@mui/material';
import {
  ArrowBack, People, Male, Female, Schedule, CheckCircle, Settings
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../lib/api';

interface Candidate {
  id: number;
  full_name: string;
  cpf: string;
  registration_number: string;
  gender: 'M' | 'F' | string;
  batch_name: string | null;
  batch_number?: number | null;
  batch_start_time?: string | null;
  batch_date?: string | null;
}

interface TurmaInfo {
  name: string;
  start_time: string | null;
  end_time?: string | null;
  date?: string | null | Date;
  candidates: Candidate[];
  total_candidates: number;
  gender_distribution: { M: number; F: number };
}

interface GroupingConfig {
  event_id: number;
  batch_size: number;
  slot_duration?: number | null;
  interval_between_batches?: number | null;
  morning_start?: string | null;
  morning_end_limit?: string | null;
  afternoon_start_min?: string | null;
  afternoon_end_limit?: string | null; // ADICIONADO
  ordering: string;
  batch_name_with_time: boolean;
  separate_by_gender: boolean;
  gender_priority?: string | null;
  allow_partial_groups: boolean;
  registration_order?: string;
  distribution_mode?: string;
  sort_by_registration?: boolean;
  // multi-day support
  start_date?: string | null;
  days_count?: number | null;
  // optional explicit days list (YYYY-MM-DD)
  days?: string[] | null;
  group_duration?: number | null;
}

export default function TAFGroupingPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { eventId } = useParams<{ eventId: string }>();

  const [eventName, setEventName] = useState('');
  const [eventDates, setEventDates] = useState<string[]>([]); // explicit event days from backend
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [turmas, setTurmas] = useState<TurmaInfo[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiErrors, setApiErrors] = useState<string[]>([]); // formatted validation errors
  const [success, setSuccess] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  // Configurações
  const [groupSize, setGroupSize] = useState(10); // batch_size
  const [separateByGender, setSeparateByGender] = useState(false);
  const [genderPriority, setGenderPriority] = useState<string>('mixed');
  const [sortByRegistration, setSortByRegistration] = useState(true);
  const [registrationOrder, setRegistrationOrder] = useState<string>('asc');
  const [distributionMode, setDistributionMode] = useState<string>('balanced');
  const [allowPartialGroups, setAllowPartialGroups] = useState(true);

  // Scheduling / new options
  const [useSchedule, setUseSchedule] = useState(false);
  const [slotDuration, setSlotDuration] = useState<number>(2); // minutes per candidate
  const [groupDuration, setGroupDuration] = useState<number | null>(12);
  const [morningStart, setMorningStart] = useState('08:00');
  const [morningEndLimit, setMorningEndLimit] = useState('10:30');
  const [afternoonStartMin, setAfternoonStartMin] = useState('14:00');
  const [afternoonEndLimit, setAfternoonEndLimit] = useState('17:30'); // ADICIONADO
  const [intervalMinutes, setIntervalMinutes] = useState(30);
  const [batchNameWithTime, setBatchNameWithTime] = useState(true);

  // Multi-day inputs (used when explicit eventDates not present)
  const [startDate, setStartDate] = useState<string>('');
  const [daysCount, setDaysCount] = useState<number>(1);

  // Passo atual
  const [activeStep, setActiveStep] = useState(0);
  const steps = ['Configurar', 'Visualizar', 'Confirmar'];

  // estilo reutilizável para todos os campos do formulário (altura e padding padronizados)
  const fieldSx = {
    '& .MuiOutlinedInput-root': { height: 48, borderRadius: 1 },
    '& .MuiOutlinedInput-input': { padding: '10px 12px' }
  };

  useEffect(() => {
    if (eventId) {
      loadEventData();
      loadCandidates();
    }
    // eslint-disable-next-line
  }, [eventId]);

  const loadEventData = async () => {
    try {
      const response = await api.get(`/taf/events/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEventName(response.data.name || '');
      // load explicit days if backend returns them (YYYY-MM-DD)
      if (response.data.event_dates && Array.isArray(response.data.event_dates)) {
        setEventDates(response.data.event_dates);
        // if there's at least one date, prefill startDate for compatibility
        if (response.data.event_dates.length > 0) {
          setStartDate(response.data.event_dates[0]);
        }
      } else {
        setEventDates([]);
        // optionally set startDate from date_start if backend returns it
        if (response.data.date_start) {
          setStartDate(response.data.date_start);
        }
      }
    } catch (err) {
      console.error('Erro ao carregar evento:', err);
    }
  };

  const loadCandidates = async () => {
  try {
    setLoading(true);
    const response = await api.get(`/taf/candidates/by-event/${eventId}`, {
      params: { page: 1, page_size: 2000 },
      headers: { Authorization: `Bearer ${token}` }
    });

    // Ordena localmente por nome ignorando acentos e caixa (pt-BR)
    const items = response.data.items || [];
    items.sort((a: any, b: any) =>
      (a.full_name || '').localeCompare(b.full_name || '', 'pt-BR', { sensitivity: 'base' })
    );

    setCandidates(items);
  } catch (err: any) {
    setError('Erro ao carregar candidatos');
  } finally {
    setLoading(false);
  }
};

  const padNumber = (n: number | null | undefined, width = 3) => {
    if (n === null || n === undefined) return '';
    return String(n).padStart(width, '0');
  };

  // Helper: format backend validation errors into strings
  const formatApiErrors = (detail: any): string[] => {
    if (!detail) return [];
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (typeof item === 'string') return item;
        // Pydantic error shape: { loc, msg, type, ... }
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : item.loc;
          const msg = item.msg || JSON.stringify(item);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      });
    }
    // fallback
    return [String(detail)];
  };

  // Helper: check if eventDates array is consecutive daily sequence
  const isConsecutiveDates = (dates: string[]) => {
    if (!dates || dates.length === 0) return false;
    // parse without timezone issues by splitting components
    const parsed = dates.map(d => {
      const [y, m, day] = d.split('-').map(Number);
      return new Date(y, (m || 1) - 1, day || 1);
    }).sort((a, b) => a.getTime() - b.getTime());
    for (let i = 1; i < parsed.length; i++) {
      const prev = parsed[i - 1];
      const cur = parsed[i];
      const diff = (cur.getTime() - prev.getTime()) / (1000 * 60 * 60 * 24);
      if (diff !== 1) return false;
    }
    return true;
  };

  // sanitize turmas before sending to backend (convert Date -> YYYY-MM-DD string, normalize numbers)
  // Substitua a função sanitizeTurmasForApi pela versão abaixo
const sanitizeTurmasForApi = (rawTurmas: TurmaInfo[], includeDate = true) => {
  return rawTurmas.map((t) => {
    let dateIso: string | null = null;
    if (t.date) {
      if (typeof t.date === 'string') {
        dateIso = t.date;
      } else {
        try {
          const dt = new Date(t.date as any);
          if (!Number.isNaN(dt.getTime())) {
            const yyyy = dt.getFullYear();
            const mm = String(dt.getMonth() + 1).padStart(2, '0');
            const dd = String(dt.getDate()).padStart(2, '0');
            dateIso = `${yyyy}-${mm}-${dd}`;
          }
        } catch {
          dateIso = String(t.date);
        }
      }
    }

    const sanitizedCandidates = (t.candidates || []).map((c) => ({
      id: Number(c.id),
      event_id: Number(eventId),
      full_name: c.full_name || '',
      cpf: (c.cpf || '').replace(/\D/g, ''),
      registration_number: c.registration_number || '',
      gender: c.gender || '',
      batch_name: c.batch_name ?? null,
      batch_number:
        c.batch_number !== undefined && c.batch_number !== null && c.batch_number !== ''
          ? Number(c.batch_number)
          : null,
      start_time: c.start_time ?? c.batch_start_time ?? null
    }));

    return {
      name: t.name,
      date: includeDate ? dateIso : null,
      start_time: t.start_time ?? null,
      end_time: t.end_time ?? null,
      total_candidates: Number(t.total_candidates ?? sanitizedCandidates.length),
      gender_distribution: t.gender_distribution ?? { M: 0, F: 0 },
      candidates: sanitizedCandidates
    };
  });
};


  const handleGenerateGroups = async () => {
    setGenerating(true);
    setError(null);
    setApiErrors([]);
    setWarnings([]);
    setTurmas([]);
    setSuccess(null);

    // basic client-side validation for schedule
    if (useSchedule && !startDate && (!eventDates || eventDates.length === 0)) {
      setError('Selecione a data inicial (Start date) para agendamento multi-dia, ou configure datas do evento.');
      setGenerating(false);
      return;
    }

    // estimate check (prevent absurd slot_duration * batch_size)
    if (useSchedule) {
      const estimated = slotDuration * groupSize;
      if (estimated > 24 * 60) {
        setError('Configuração inválida: duração estimada da turma excede 24 horas. Ajuste slot duration ou tamanho da turma.');
        setGenerating(false);
        return;
      }
    }

    // <<< INSERIR AQUI: validação / fallback para fim da tarde >>>
    if (useSchedule && afternoonStartMin && (!afternoonEndLimit || afternoonEndLimit === '')) {
      // Opção A (exigir preenchimento pelo usuário):
      setError('Quando o início da tarde está definido, preencha também o campo "Fim do dia".');
      setGenerating(false);
      return;

      // OU Opção B (auto-preencher com fallback 18:30 — menos intrusivo):
      // setAfternoonEndLimit('18:30');
      // (se usar o fallback, não faz o return)
    }
    // <<< FIM DA INSERÇÃO >>>

    const config: GroupingConfig = {
      event_id: Number(eventId),
      batch_size: groupSize,
      slot_duration: useSchedule ? slotDuration : undefined,
      group_duration: useSchedule ? (groupDuration ?? undefined) : undefined, // ADICIONADO
      interval_between_batches: useSchedule ? intervalMinutes : undefined,
      morning_start: useSchedule ? morningStart : undefined,
      morning_end_limit: useSchedule ? morningEndLimit : undefined,
      afternoon_start_min: useSchedule ? afternoonStartMin : undefined,
      afternoon_end_limit: useSchedule ? afternoonEndLimit : undefined,
      ordering: sortByRegistration ? 'registration_number' : 'full_name',
      batch_name_with_time: batchNameWithTime,
      separate_by_gender: separateByGender,
      gender_priority: genderPriority === 'mixed' ? null : genderPriority,
      allow_partial_groups: allowPartialGroups,
      registration_order: registrationOrder,

      // ADICADOS: envio explícito do modo de distribuição e flag de ordenação
      distribution_mode: distributionMode,
      sort_by_registration: sortByRegistration,

      // multi-day (we will decide in body whether to send explicit days or start_date/days_count)
      start_date: useSchedule ? (startDate || undefined) : undefined,
      days_count: useSchedule ? (daysCount || undefined) : undefined
    };

    // strip undefined fields (helps backend Pydantic validation)
    const baseBody: any = {};
    Object.keys(config).forEach((k) => {
      const key = k as keyof GroupingConfig;
      const v = (config as any)[key];
      if (v !== undefined && v !== null && v !== '') baseBody[key] = v;
    });

    // We'll attempt to send bodyWithDays first if we have explicit eventDates.
    // If backend rejects 'days' as extra field, we fallback to start_date/days_count when possible.
    const trySend = async (body: any) => {
      return api.post('/taf/candidates/group', body, {
        headers: { Authorization: `Bearer ${token}` }
      });
    };

    try {
      // 1) If eventDates exist, try sending them as 'days' (preferred)
      if (eventDates && eventDates.length > 0) {
        const bodyWithDays = { ...baseBody, days: eventDates };
        // remove start_date/days_count to avoid confusion
        delete bodyWithDays.start_date;
        delete bodyWithDays.days_count;

        try {
          const response = await trySend(bodyWithDays);
          setTurmas(response.data.groups || []);
          setWarnings(response.data.warnings || []);
          setActiveStep(1);
          setSuccess(response.data.warnings && response.data.warnings.length > 0 ? 'Agrupamento gerado com avisos.' : 'Agrupamento gerado com sucesso.');
          setGenerating(false);
          return;
        } catch (err: any) {
          // If validation error indicates 'days' is an extra field, try fallback
          const status = err?.response?.status;
          const detail = err?.response?.data?.detail;
          const formatted = formatApiErrors(detail);
          // determine if error is about 'days' being unexpected
          const isExtraDays = Array.isArray(detail) && detail.some((d: any) => {
            return d && d.type === 'value_error.extra' && Array.isArray(d.loc) && d.loc.includes('days');
          });
          if (status === 422 && isExtraDays) {
            // fallback: if eventDates are consecutive, compute start_date + days_count and retry
            if (isConsecutiveDates(eventDates)) {
              const start = eventDates.slice().sort()[0];
              const count = eventDates.length;
              const fallbackBody = { ...baseBody, start_date: start, days_count: count };
              try {
                const response2 = await trySend(fallbackBody);
                setTurmas(response2.data.groups || []);
                setWarnings(response2.data.warnings || []);
                setActiveStep(1);
                setSuccess(response2.data.warnings && response2.data.warnings.length > 0 ? 'Agrupamento gerado com avisos.' : 'Agrupamento gerado com sucesso.');
                setGenerating(false);
                return;
              } catch (err2: any) {
                const detail2 = err2?.response?.data?.detail;
                setApiErrors(formatApiErrors(detail2));
                setError('O backend rejeitou o fallback start_date/days_count. Verifique a configuração.');
                setGenerating(false);
                return;
              }
            } else {
              // cannot fallback automatically
              setApiErrors(formatted.length ? formatted : ['Campo "days" não é suportado pelo backend e as datas não são consecutivas para fallback automático.']);
              setError('O backend não aceita lista explícita de dias e as datas não são um intervalo contínuo. Atualize o backend ou ajuste manualmente.');
              setGenerating(false);
              return;
            }
          } else {
            // generic validation error or other error: show formatted messages
            setApiErrors(formatted.length ? formatted : [err?.response?.data?.detail || 'Erro desconhecido ao validar dados']);
            setError('Erro de validação no backend ao gerar agrupamento.');
            setGenerating(false);
            return;
          }
        }
      }

      // 2) No explicit eventDates or already handled: send base body (start_date/days_count as present)
      const response = await trySend(baseBody);
      setTurmas(response.data.groups || []);
      setWarnings(response.data.warnings || []);
      setActiveStep(1);
      setSuccess(response.data.warnings && response.data.warnings.length > 0 ? 'Agrupamento gerado com avisos.' : 'Agrupamento gerado com sucesso.');
    } catch (err: any) {
      console.error('Erro ao gerar agrupamento', err);
      const detail = err?.response?.data?.detail;
      const formatted = formatApiErrors(detail);
      setApiErrors(formatted.length ? formatted : [err?.response?.data?.detail || 'Erro ao gerar agrupamento']);
      setError(err?.response?.data?.detail ? 'Erro de validação' : 'Erro ao gerar agrupamento');
    } finally {
      setGenerating(false);
    }
  };

  const handleApplyGrouping = async () => {
  setApplying(true);
  setError(null);
  setSuccess(null);

  // sanitize turmas to ensure JSON-serializable types and expected shapes
  const sanitizedGroups = sanitizeTurmasForApi(turmas, true);

  // build minimal payload just for apply (avoid sending full candidate objects)
  const minimalGroups = sanitizedGroups.map((g) => ({
    name: g.name,
    date: g.date ?? null,
    start_time: g.start_time ?? null,
    end_time: g.end_time ?? null,
    total_candidates: g.total_candidates ?? (g.candidates?.length ?? 0),
    // only send minimal candidate refs required by backend
    candidates: (g.candidates || []).map((c) => ({
      id: Number(c.id),
      batch_number:
        c.batch_number !== undefined && c.batch_number !== null && c.batch_number !== ''
          ? Number(c.batch_number)
          : null
    }))
  }));

  const payloadForApply = {
    event_id: Number(eventId),
    total_candidates: candidates.length,
    total_groups: minimalGroups.length,
    groups: minimalGroups,
    config: {
      event_id: Number(eventId),
      batch_size: groupSize,
      slot_duration: useSchedule ? slotDuration : undefined,
      group_duration: useSchedule ? (groupDuration ?? undefined) : undefined,
      interval_between_batches: useSchedule ? intervalMinutes : undefined,
      morning_start: useSchedule ? morningStart : undefined,
      morning_end_limit: useSchedule ? morningEndLimit : undefined,
      afternoon_start_min: useSchedule ? afternoonStartMin : undefined,
      afternoon_end_limit: useSchedule ? afternoonEndLimit : undefined,
      ordering: sortByRegistration ? 'registration_number' : 'full_name',
      batch_name_with_time: batchNameWithTime,
      separate_by_gender: separateByGender,
      gender_priority: genderPriority === 'mixed' ? null : genderPriority,
      allow_partial_groups: allowPartialGroups,
      registration_order: registrationOrder,
      distribution_mode: distributionMode,
      sort_by_registration: sortByRegistration,
      start_date: useSchedule ? (startDate || undefined) : undefined,
      days_count: useSchedule ? (daysCount || undefined) : undefined,
      days: eventDates && eventDates.length > 0 ? eventDates : undefined
    }
  };

  try {
    // lightweight debug: only summary
    console.log('Applying grouping: event_id=', payloadForApply.event_id, 'groups=', payloadForApply.total_groups);

    await api.post(`/taf/candidates/apply-grouping/${eventId}`, payloadForApply, {
      headers: { Authorization: `Bearer ${token}` }
    });

    setSuccess(`Agrupamento aplicado com sucesso! ${minimalGroups.length} turmas criadas.`);
    setActiveStep(2);

    setTimeout(() => {
      navigate(`/taf/events/${eventId}/candidates`);
    }, 2000);
  } catch (err: any) {
    console.error('Erro ao aplicar agrupamento - response.data:', err?.response?.data);
    console.error('Erro ao aplicar agrupamento - response.status:', err?.response?.status);

    const detail = err?.response?.data?.detail;
    setApiErrors(formatApiErrors(detail));
    setError(err?.response?.data?.detail ? 'Erro ao aplicar agrupamento (validação)' : 'Erro ao aplicar agrupamento');
  } finally {
    setApplying(false);
  }
};

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
                Agrupar em Turmas
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {eventName}
              </Typography>
            </Box>
          </Box>
        </Stack>
        {/* Show explicit event dates if present */}
        {eventDates && eventDates.length > 0 && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Datas do evento:
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>
              {eventDates.map(d => (
                <Chip key={d} label={d} size="small" />
              ))}
            </Stack>
          </Box>
        )}
      </Box>

      {/* Alertas */}
      {apiErrors.length > 0 && apiErrors.map((msg, i) => (
        <Alert severity="error" sx={{ mb: 2 }} key={i} onClose={() => setApiErrors(prev => prev.filter((_, idx) => idx !== i))}>
          {msg}
        </Alert>
      ))}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity={warnings.length ? "warning" : "success"} sx={{ mb: 2 }} onClose={() => { setSuccess(null); setWarnings([]); }}>{success}</Alert>}
      {warnings.length > 0 && warnings.map((w, i) => <Alert key={i} severity="warning" sx={{ mb: 1 }}>{w}</Alert>)}

      {/* Stepper */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Stepper activeStep={activeStep}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
      </Paper>

      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Passo 1: Configuração */}
          {activeStep === 0 && (
            <Paper sx={{ p: 4 }}>
              <Typography variant="h5" gutterBottom fontWeight={600} sx={{ mb: 3 }}>
                <Settings sx={{ mr: 1, verticalAlign: 'middle' }} />
                Configuracoes do Agrupamento
              </Typography>

              {/* Resumo de Candidatos */}
              <Paper sx={{ p: 2, mb: 4, bgcolor: 'info.light' }}>
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

              <Stack spacing={3}>
                <TextField
                  label="Tamanho da Turma"
                  type="number"
                  value={groupSize}
                  onChange={(e) => setGroupSize(Number(e.target.value))}
                  fullWidth
                  helperText="Numero maximo de candidatos por turma"
                  InputProps={{ inputProps: { min: 1, max: 500 } }}
                />

                <FormControlLabel
                  control={
                    <Switch
                      checked={separateByGender}
                      onChange={(e) => setSeparateByGender(e.target.checked)}
                    />
                  }
                  label="Separar turmas por sexo (Masculino / Feminino)"
                />

                {/* Opcoes Avancadas */}
                <Divider>
                  <Chip label="Opcoes Avancadas" size="small" />
                </Divider>

                <TextField
                  select
                  label="Prioridade de Genero"
                  value={genderPriority}
                  onChange={(e) => setGenderPriority(e.target.value)}
                  fullWidth
                  helperText="Ordem de processamento das turmas"
                >
                  <MenuItem value="mixed">Misto (sem prioridade)</MenuItem>
                  <MenuItem value="F">Feminino primeiro</MenuItem>
                  <MenuItem value="M">Masculino primeiro</MenuItem>
                </TextField>

                <TextField
                  select
                  label="Modo de Distribuicao"
                  value={distributionMode}
                  onChange={(e) => setDistributionMode(e.target.value)}
                  fullWidth
                  helperText="Como os candidatos serao divididos"
                >
                  <MenuItem value="balanced">Balanceada (turmas com tamanhos similares)</MenuItem>
                  <MenuItem value="sequential">Sequencial (preenche turmas ate o limite)</MenuItem>
                </TextField>

                <Stack direction="row" spacing={2}>
                  <TextField
                    select
                    label="Ordenacao por Inscricao"
                    value={registrationOrder}
                    onChange={(e) => setRegistrationOrder(e.target.value)}
                    fullWidth
                    disabled={!sortByRegistration}
                  >
                    <MenuItem value="asc">Crescente (1, 2, 3...)</MenuItem>
                    <MenuItem value="desc">Decrescente (...3, 2, 1)</MenuItem>
                  </TextField>

                  <FormControlLabel
                    control={
                      <Switch
                        checked={sortByRegistration}
                        onChange={(e) => setSortByRegistration(e.target.checked)}
                      />
                    }
                    label="Ordenar"
                    sx={{ minWidth: 150 }}
                  />
                </Stack>

                <FormControlLabel
                  control={
                    <Switch
                      checked={allowPartialGroups}
                      onChange={(e) => setAllowPartialGroups(e.target.checked)}
                    />
                  }
                  label={
                    <Box>
                      <Typography>Permitir turmas incompletas</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Criar turma mesmo que nao atinja o tamanho definido
                      </Typography>
                    </Box>
                  }
                />

                {/* switch para habilitar schedule */}
                <Divider />
                <FormControlLabel
                  control={<Switch checked={useSchedule} onChange={(e) => setUseSchedule(e.target.checked)} />}
                  label={
                    <Box>
                      <Typography>Definir horários para as turmas</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Atribui horários de início e permite multi‑dia
                      </Typography>
                    </Box>
                  }
                />

                {useSchedule && (
                  <Card variant="outlined" sx={{ mt: 2, borderRadius: 2 }}>
                    <CardContent>

                      {/* 📅 Datas */}
                      <Typography variant="subtitle1" fontWeight={600} mb={2}>
                        📅 Datas do Evento
                      </Typography>

                      <Grid container spacing={3}>
                          <Grid item xs={12} sm={4}>
                            <TextField
                              label="Data inicial"
                              type="date"
                              value={startDate}
                              onChange={(e) => setStartDate(e.target.value)}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 200 }}
                            />
                          </Grid>

                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Quantidade de dias"
                              type="number"
                              value={daysCount}
                              onChange={(e) => setDaysCount(Number(e.target.value))}
                              InputProps={{ inputProps: { min: 1, max: 365 } }}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 180 }}
                            />
                          </Grid>
                        </Grid>

                      <Divider sx={{ my: 3 }} />

                      {/* 🕘 Horários */}
                      <Typography variant="subtitle1" fontWeight={600} mb={2}>
                        🕘 Horários
                      </Typography>

                      <Grid container spacing={3}>
                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Manhã (início)"
                              type="time"
                              value={morningStart}
                              onChange={(e) => setMorningStart(e.target.value)}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 180 }}
                            />
                          </Grid>

                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Última turma da manhã"
                              type="time"
                              value={morningEndLimit}
                              onChange={(e) => setMorningEndLimit(e.target.value)}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 220 }}
                            />
                          </Grid>

                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Tarde (início)"
                              type="time"
                              value={afternoonStartMin}
                              onChange={(e) => setAfternoonStartMin(e.target.value)}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 180 }}
                            />
                          </Grid>

                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Fim do dia"
                              type="time"
                              value={afternoonEndLimit}
                              onChange={(e) => setAfternoonEndLimit(e.target.value)}
                              InputLabelProps={{ shrink: true }}
                              helperText="Limite máximo para encerrar turmas"
                              fullWidth
                              sx={{ minWidth: 200 }}
                            />
                          </Grid>
                        </Grid>

                      <Divider sx={{ my: 3 }} />

                      {/* ⏱️ Duração */}
                      <Typography variant="subtitle1" fontWeight={600} mb={2}>
                        ⏱️ Duração e Intervalos
                      </Typography>

                      <Grid container spacing={3} alignItems="center">
                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Duração da turma (min)"
                              type="number"
                              value={groupDuration ?? ''}
                              onChange={(e) => setGroupDuration(Number(e.target.value))}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 220 }}
                            />
                          </Grid>

                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Minutos por candidato"
                              type="number"
                              value={slotDuration}
                              onChange={(e) => setSlotDuration(Number(e.target.value))}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 200 }}
                            />
                          </Grid>

                          <Grid item xs={12} sm={3}>
                            <TextField
                              label="Intervalo entre turmas"
                              type="number"
                              value={intervalMinutes}
                              onChange={(e) => setIntervalMinutes(Number(e.target.value))}
                              InputLabelProps={{ shrink: true }}
                              fullWidth
                              sx={{ minWidth: 220 }}
                            />
                          </Grid>
                        </Grid>

                        <Grid item xs={12} sm={3}>
                          <FormControlLabel
                            control={
                              <Switch
                                checked={batchNameWithTime}
                                onChange={(e) => setBatchNameWithTime(e.target.checked)}
                              />
                            }
                            label="Mostrar horário no nome"
                          />
                        </Grid>
                      

                      {/* Rodapé informativo */}
                      <Box
                        sx={{
                          mt: 3,
                          p: 2,
                          bgcolor: 'grey.100',
                          borderRadius: 1,
                          display: 'flex',
                          justifyContent: 'space-between',
                        }}
                      >
                        <Typography variant="caption">
                          ⏳ Duração calculada automaticamente
                        </Typography>

                        <Typography variant="caption" fontWeight={600}>
                          Total estimado: {groupDuration ?? slotDuration * groupSize} min
                        </Typography>
                      </Box>

                    </CardContent>
                  </Card>
                )}


                <Button
                  variant="contained"
                  size="large"
                  onClick={handleGenerateGroups}
                  disabled={generating || candidates.length === 0}
                  startIcon={generating ? <CircularProgress size={20} /> : <People />}
                  sx={{ mt: 2 }}
                >
                  {generating ? 'Gerando...' : 'Gerar Agrupamento'}
                </Button>
              </Stack>
            </Paper>
          )}

          {/* Passo 2: Visualização */}
          {activeStep === 1 && (
            <Box>
              <Paper sx={{ p: 3, mb: 3, bgcolor: 'success.light' }}>
                <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography variant="h6" fontWeight={600}>
                      Agrupamento Gerado com Sucesso!
                    </Typography>
                    <Typography variant="body2">
                      {turmas.length} turmas criadas para {candidates.length} candidatos
                    </Typography>
                  </Box>
                  <CheckCircle sx={{ fontSize: 48, color: 'success.dark' }} />
                </Stack>
              </Paper>

              <Stack spacing={2}>
                {turmas.map((turma, index) => (
                  <Card key={index} variant="outlined">
                    <CardContent>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                        <Typography variant="h6" fontWeight={600}>
                          {turma.name}
                        </Typography>
                        <Stack direction="row" spacing={1}>
                          {turma.start_time && (
                              <Chip
                                icon={<Schedule />}
                                label={
                                  turma.date
                                    ? `${turma.date} ${turma.start_time}${turma.end_time ? ` - ${turma.end_time}` : ''}`
                                    : `${turma.start_time}${turma.end_time ? ` - ${turma.end_time}` : ''}`
                                }
                                color="primary"
                                size="small"
                              />
                          )}
                          <Chip
                            label={`${turma.total_candidates} candidatos`}
                            size="small"
                          />
                          {turma.gender_distribution.M > 0 && (
                            <Chip
                              icon={<Male />}
                              label={turma.gender_distribution.M}
                              color="primary"
                              size="small"
                            />
                          )}
                          {turma.gender_distribution.F > 0 && (
                            <Chip
                              icon={<Female />}
                              label={turma.gender_distribution.F}
                              color="secondary"
                              size="small"
                            />
                          )}
                        </Stack>
                      </Stack>

                      <Box sx={{ maxHeight: 150, overflowY: 'auto' }}>
                        <Stack direction="row" flexWrap="wrap" gap={0.5}>
                          {turma.candidates.map((candidate) => (
                            <Chip
                              key={candidate.id}
                              label={`${candidate.registration_number || ''} • ${padNumber(candidate.batch_number)} ${candidate.batch_start_time ? `• ${candidate.batch_start_time}` : ''} - ${candidate.full_name}`}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                        </Stack>
                      </Box>
                    </CardContent>
                  </Card>
                ))}
              </Stack>

              <Stack direction="row" spacing={2} justifyContent="flex-end" sx={{ mt: 3 }}>
                <Button
                  variant="outlined"
                  onClick={() => setActiveStep(0)}
                >
                  Voltar e Reconfigurar
                </Button>
                <Button
                  variant="contained"
                  size="large"
                  onClick={handleApplyGrouping}
                  disabled={applying}
                  startIcon={applying ? <CircularProgress size={20} /> : <CheckCircle />}
                >
                  {applying ? 'Aplicando...' : 'Aplicar Agrupamento'}
                </Button>
              </Stack>
            </Box>
          )}

          {/* Passo 3: Confirmação */}
          {activeStep === 2 && (
            <Paper sx={{ p: 6, textAlign: 'center' }}>
              <CheckCircle sx={{ fontSize: 80, color: 'success.main', mb: 2 }} />
              <Typography variant="h4" gutterBottom fontWeight={700}>
                Agrupamento Aplicado!
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                Os candidatos foram distribuídos em {turmas.length} turmas.
                Redirecionando...
              </Typography>
              <CircularProgress />
            </Paper>
          )}
        </>
      )}
    </Container>
  );
}