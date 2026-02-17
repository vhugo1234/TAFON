import React, { useEffect, useRef, useState, useMemo } from 'react';
import {
  Container, Typography, Box, Button, Stack, Alert, CircularProgress,
  Card, CardContent, Chip, IconButton, TextField, MenuItem, Dialog,
  DialogTitle, DialogContent, DialogActions, Paper, Grid, Badge, Checkbox,
  FormControlLabel, Tooltip, InputAdornment
} from '@mui/material';
import {
  ArrowBack, FitnessCenter, CheckCircle, Cancel, Timer, Search,
  PlayArrow, Save, Replay, Add, Remove, Edit
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../lib/api';
import StopwatchTimer from '../components/StopwatchTimer';
import RepetitionCounter from '../components/RepetitionCounter';
import { padNumberByTotal } from '../lib/format';

interface Exercise {
  id: number;
  name: string;
  unit_of_measure: string;
  max_attempts: number;
  execution_mode: 'individual' | 'collective';
  measurement_type: 'time' | 'distance' | 'repetitions';
}

interface CandidateStatus {
  candidate_id: number;
  candidate_number: string;
  full_name: string;
  gender: string;
  status: 'pending' | 'in_progress' | 'completed' | 'awaiting_retry';
  evaluator_name?: string | null;
  current_attempt: number;
  max_attempts: number;
  results: any[];
  best_result?: number;
  is_approved?: boolean;
  batch_number?: number | string;
}

interface BatchStatus {
  exercise_id: number;
  exercise_name: string;
  execution_mode: string;
  measurement_type: string;
  batch_name: string;
  total_candidates: number;
  candidates: CandidateStatus[];
  pending_count: number;
  in_progress_count: number;
  completed_count: number;
  approved_count: number;
  failed_count: number;
}

interface PassCriteria {
  id: number;
  exercise_id: number;
  gender: 'M' | 'F';
  min_value?: number | null;      // distance or repetitions minimum
  max_time_s?: number | null;     // time maximum (seconds)
}

type CollectiveResult = {
  time_s?: number | null;
  distance_m?: number | null;
  laps?: number;
  valid: boolean;
  auto?: boolean;
};

export default function TAFFieldEvaluationPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { eventId, exerciseId } = useParams<{ eventId: string; exerciseId: string }>();

  // core state
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [eventName, setEventName] = useState('');

  // batches & selection
  const [batches, setBatches] = useState<string[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<string>('');
  const [batchLabels, setBatchLabels] = useState<Record<string, string>>({});
  const [batchMembers, setBatchMembers] = useState<Record<string, number[]>>({});

  // individual modal
  const [evaluationModal, setEvaluationModal] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateStatus | null>(null);
  const [measuredValue, setMeasuredValue] = useState<number>(0);
  const [isValid, setIsValid] = useState(true);
  const [saving, setSaving] = useState(false);

  // collective
  const [selectedCandidates, setSelectedCandidates] = useState<Set<number>>(new Set());
  const [collectiveModal, setCollectiveModal] = useState(false);
  const [collectiveResults, setCollectiveResults] = useState<Map<number, CollectiveResult>>(new Map());
  const [collectiveTimeMs, setCollectiveTimeMs] = useState<number>(0);
  const [trackLengthMeters, setTrackLengthMeters] = useState<number | ''>(400);
  const [lapsMode, setLapsMode] = useState<boolean>(true);
  const [applyDistanceValue, setApplyDistanceValue] = useState<number | ''>('');
  const [rangeStart, setRangeStart] = useState<string>('');
  const [rangeEnd, setRangeEnd] = useState<string>('');
  const [modalSearch, setModalSearch] = useState<string>('');
  // controla auto-start externo e controle run/stop do cronômetro global
  const [autoStartStopwatch, setAutoStartStopwatch] = useState<boolean>(false);
  const [stopwatchRunning, setStopwatchRunning] = useState<boolean>(false);
  const [stopwatchKey, setStopwatchKey] = useState<number>(0);

  // criteria
  const [criteriaMap, setCriteriaMap] = useState<Record<string, PassCriteria | undefined>>({});
  const [autoApplyCriteria, setAutoApplyCriteria] = useState<boolean>(true);

  // search
  const [searchNumber, setSearchNumber] = useState('');

  // refs
  const collectiveModalRef = useRef<HTMLDivElement | null>(null);
  const initialLoadRef = useRef(false); // avoids repeated initial loads

  // refs para evitar loops e lembrar quem já foi auto-registrado
  const lastElapsedRef = useRef<number>(-1);
  const autoRegisteredRef = useRef<Set<number>>(new Set());
  const stoppedByAutoRef = useRef<boolean>(false);
  const collectiveResultsRef = useRef<Map<number, CollectiveResult>>(new Map());
  const lastLiveUpdateAtRef = useRef<number>(0);

  // keep ref synchronized when state changes (defensive)
  useEffect(() => {
    collectiveResultsRef.current = collectiveResults;
  }, [collectiveResults]);


  // ref para saber se o componente está montado (evitar setState após unmount)
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // ---------- Effects ----------
  useEffect(() => {
    if (!eventId || !exerciseId) return;
    if (!initialLoadRef.current) {
      initialLoadRef.current = true;
      loadInitialData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, exerciseId]);

  useEffect(() => {
    // clear selections when batch changes
    setSelectedCandidates(new Set());
  }, [selectedBatch]);

  useEffect(() => {
    if (selectedBatch && exerciseId) loadBatchStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBatch, exerciseId]);

  // ---------- Helpers ----------
  const msToSecondsRounded = (ms: number) => Math.round((ms / 1000) * 1000) / 1000;

  const formatMsToDisplay = (ms: number) => {
    const total = Math.max(0, Math.round(ms));
    const minutes = Math.floor(total / 60000);
    const seconds = Math.floor((total % 60000) / 1000);
    const msRem = total % 1000;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(msRem).padStart(3, '0')}`;
  };

  const computeDistanceFromLaps = (laps?: number) => {
    if (!laps || !trackLengthMeters) return undefined;
    return Number((laps * Number(trackLengthMeters)).toFixed(3));
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'in_progress': return 'warning';
      case 'awaiting_retry': return 'info';
      default: return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'completed': return 'Concluído';
      case 'in_progress': return 'Em andamento';
      case 'awaiting_retry': return 'Aguardando nova tentativa';
      default: return 'Aguardando';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle />;
      case 'in_progress': return <Timer />;
      default: return <PlayArrow />;
    }
  };

  function parseBatchLabel(label: string) {
    const result: { batch_name: string; start_date?: string; start_time?: string } = { batch_name: (label || '').toString() };

    if (!label) return result;

    // remove count suffix "(NN)" if present
    const withoutCount = label.replace(/\(\d+\)\s*$/, '').trim();

    // try " • YYYY-MM-DD @ HH:MM"
    const mDateTime = withoutCount.match(/^(.*?)\s*•\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*@\s*([0-9]{2}:[0-9]{2})\s*$/);
    if (mDateTime) {
      result.batch_name = (mDateTime[1] || '').trim();
      result.start_date = mDateTime[2];
      result.start_time = mDateTime[3];
      return result;
    }

    const mDateOnly = withoutCount.match(/^(.*?)\s*•\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*$/);
    if (mDateOnly) {
      result.batch_name = (mDateOnly[1] || '').trim();
      result.start_date = mDateOnly[2];
      return result;
    }

    const mTimeOnly = withoutCount.match(/^(.*?)\s*@\s*([0-9]{2}:[0-9]{2})\s*$/);
    if (mTimeOnly) {
      result.batch_name = (mTimeOnly[1] || '').trim();
      result.start_time = mTimeOnly[2];
      return result;
    }

    result.batch_name = withoutCount.trim();
    return result;
  }

  // format candidate number with zero padding based on total candidates
  const formatCandidateNumber = (raw: any, totalCandidates: number) => {
    if (raw === undefined || raw === null || raw === '') return '';
    const n = Number(String(raw).replace(/\D/g, ''));
    if (!Number.isFinite(n)) return String(raw);

    // largura mínima 3 (=> 001..099). Se houver total maior (ex: 120), aumenta para 3 dígitos, se >999 usa mais dígitos
    const totalDigits = Math.max(3, String(Math.max(totalCandidates || 0, n)).length);
    return String(n).padStart(totalDigits, '0');
  };

  // ---------- Build batches from candidates (ensures start_date/start_time exist) ----------
  const loadBatchesFromCandidates = async (): Promise<boolean> => {
    try {
      const pageSize = 1000; // tamanho seguro (ajuste se necessário)
      let page = 1;
      let allItems: any[] = [];

      while (true) {
        const resp = await api.get(`/taf/candidates/by-event/${eventId}`, {
          params: { page, page_size: pageSize },
          headers: { Authorization: `Bearer ${token}` }
        });

        // resp.data pode ter formato { items: [], total, ... } ou array direto
        const itemsPage = resp.data?.items || (Array.isArray(resp.data) ? resp.data : []);
        if (!Array.isArray(itemsPage)) {
          console.warn('loadBatchesFromCandidates: resposta inesperada (não array), abortando paginação', resp.data);
          break;
        }

        allItems = allItems.concat(itemsPage);

        // se a página retornou menos que pageSize, chegamos ao fim
        if (itemsPage.length < pageSize) break;

        page += 1;

        // segurança: evita loop infinito (cap arbitrário)
        if (page > 1000) break;
      }

      // se não trouxemos nada, indica falha / ou endpoint restringe acesso
      if (!allItems || allItems.length === 0) {
        console.warn('loadBatchesFromCandidates: nenhum candidato retornado na paginação');
        return false;
      }

      const groups: Record<string, { count: number; start_date?: string; start_time?: string; batch_name: string; members: number[] }> = {};
      allItems.forEach((c: any) => {
        const bn = (c.batch_name ?? '').toString().trim() || '(sem turma)';
        const sd = c.start_date ?? c.batch_date ?? '';
        const st = c.start_time ?? c.batch_start_time ?? '';
        const key = `${bn}||${sd || ''}||${st || ''}`;
        groups[key] = groups[key] || { count: 0, start_date: sd, start_time: st, batch_name: bn, members: [] };
        groups[key].count++;
        if (c.candidate_id) groups[key].members.push(c.candidate_id);
      });

      const formatDateBR = (iso?: string) => {
        if (!iso) return '';
        const p = String(iso).split('-');
        if (p.length !== 3) return iso;
        return `${p[2]}/${p[1]}/${p[0]}`;
      };

      const processed = Object.entries(groups).map(([key, v]) => {
        let namePart = v.batch_name;
        let gender = '';
        if (namePart.includes(' - ')) {
          const parts = namePart.split(' - ');
          gender = (parts.slice(-1)[0] || '').toLowerCase();
          namePart = parts.slice(0, -1).join(' - ') || namePart;
        }
        const displayParts = [namePart];
        if (gender) displayParts.push(gender);
        const dateBR = v.start_date ? formatDateBR(v.start_date) : '';
        if (dateBR) displayParts.push(dateBR);
        if (v.start_time) displayParts.push(v.start_time);
        const display = displayParts.join(' - ');
        return { key, display, count: v.count, members: v.members, start_date: v.start_date, start_time: v.start_time };
      });

      processed.sort((a,b) => {
        if (a.start_date && !b.start_date) return -1;
        if (!a.start_date && b.start_date) return 1;
        if (a.start_date && b.start_date) {
          if (a.start_date !== b.start_date) return a.start_date.localeCompare(b.start_date);
          if (a.start_time && b.start_time && a.start_time !== b.start_time) return a.start_time.localeCompare(b.start_time);
          if (a.start_time && !b.start_time) return -1;
          if (!a.start_time && b.start_time) return 1;
        }
        return (a.display || '').localeCompare(b.display || '', undefined, { numeric: true });
      });

      setBatches(processed.map(p => p.key));
      setBatchLabels(Object.fromEntries(processed.map(p => [p.key, `${p.display}${p.count ? ' ('+p.count+')' : ''}`])));
      setBatchMembers(Object.fromEntries(processed.map(p => [p.key, p.members])));
      if (processed.length > 0) setSelectedBatch(prev => prev || processed[0].key);
      return true;
    } catch (e) {
      console.error('Erro ao construir batches a partir de candidates/by-event', e);
      return false;
    }
  };

  // ---------- Data loading ----------
  async function loadInitialData() {
    try {
      setLoading(true);
      setError(null);

      // load basic info
      const eventResponse = await api.get(`/taf/events/${eventId}`, { headers: { Authorization: `Bearer ${token}` } });
      setEventName(eventResponse.data.name);

      const exerciseResponse = await api.get(`/taf/exercises/${exerciseId}`, { headers: { Authorization: `Bearer ${token}` } });
      setExercise(exerciseResponse.data);

      await loadCriteria(Number(exerciseId));

      // prefer building batches from candidates (ensures start_date/start_time exists)
      const ok = await loadBatchesFromCandidates();
      if (ok) {
        setLoading(false);
        return;
      }

      // fallback: try batches endpoint
      try {
        const batchesResp = await api.get(`/taf/candidates/batches/${eventId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        const batchList: string[] = Array.isArray(batchesResp.data) ? batchesResp.data : [];

        const formatDateBR = (iso?: string | null) => {
          if (!iso) return '';
          const parts = String(iso).split('-');
          if (parts.length !== 3) return iso;
          return `${parts[2]}/${parts[1]}/${parts[0]}`;
        };

        const processed = batchList.map((raw) => {
          const rawStr = String(raw || '').trim();
          if (!rawStr.includes('||')) {
            const parsed = parseBatchLabel(rawStr);
            let namePart = parsed.batch_name || '';
            let genderPart = '';
            if (namePart.includes(' - ')) {
              const parts = namePart.split(' - ');
              genderPart = (parts.slice(-1)[0] || '').toString().toLowerCase();
              namePart = parts.slice(0, -1).join(' - ');
              if (!namePart) namePart = parsed.batch_name || '';
            } else {
              const match = namePart.match(/(.*?)\s*-\s*(Masculino|Feminino)$/i);
              if (match) {
                namePart = (match[1] || '').trim();
                genderPart = (match[2] || '').toLowerCase();
              }
            }
            const datePart = parsed.start_date || '';
            const timePart = parsed.start_time || '';
            const formattedDate = datePart ? formatDateBR(datePart) : '';
            const displayParts = [namePart];
            if (genderPart) displayParts.push(genderPart);
            if (formattedDate) displayParts.push(formattedDate);
            if (timePart) displayParts.push(timePart);
            const display = displayParts.join(' - ');
            return { raw: rawStr, display, batch_name: parsed.batch_name || '', start_date: datePart, start_time: timePart };
          }

          const parts = rawStr.split('||').map(p => p === undefined ? '' : p);
          const maybeName = (parts[0] || '').trim();
          const maybeDate = (parts[1] || '').trim();
          const maybeTime = (parts[2] || '').trim();

          let namePart = maybeName;
          let genderPart = '';
          if (namePart.includes(' - ')) {
            const p = namePart.split(' - ');
            genderPart = (p.slice(-1)[0] || '').toString().toLowerCase();
            namePart = p.slice(0, -1).join(' - ');
            if (!namePart) namePart = maybeName;
          } else {
            const match = namePart.match(/(.*?)\s*-\s*(Masculino|Feminino)$/i);
            if (match) {
              namePart = (match[1] || '').trim();
              genderPart = (match[2] || '').toLowerCase();
            }
          }

          const formattedDate = maybeDate ? formatDateBR(maybeDate) : '';
          const displayParts = [namePart];
          if (genderPart) displayParts.push(genderPart);
          if (formattedDate) displayParts.push(formattedDate);
          if (maybeTime) displayParts.push(maybeTime);
          const display = displayParts.join(' - ');
          return { raw: rawStr, display, batch_name: maybeName, start_date: maybeDate, start_time: maybeTime };
        });

        processed.sort((a, b) => {
          if (a.start_date && !b.start_date) return -1;
          if (!a.start_date && b.start_date) return 1;
          if (a.start_date && b.start_date) {
            if (a.start_date !== b.start_date) return a.start_date.localeCompare(b.start_date);
            if (a.start_time && b.start_time) {
              if (a.start_time !== b.start_time) return a.start_time.localeCompare(b.start_time);
            } else if (a.start_time && !b.start_time) return -1;
            else if (!a.start_time && b.start_time) return 1;
          }
          return (a.batch_name || '').localeCompare(b.batch_name || '', undefined, { numeric: true });
        });

        setBatches(processed.map(p => p.raw));
        setBatchLabels(Object.fromEntries(processed.map(p => [p.raw, p.display])));
        setBatchMembers({});
        if (processed.length > 0) {
          setSelectedBatch(prev => prev || processed[0].raw);
        }
      } catch (err) {
        console.warn('Erro ao carregar turmas via endpoint /taf/candidates/batches, e fallback por candidatos também falhou.', err);
      }
    } catch (err: any) {
      console.error('Erro ao carregar dados:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao carregar dados'));
    } finally {
      setLoading(false);
    }
  }

  // ---------- loadBatchStatus ----------
  async function loadBatchStatus() {
    try {
      if (!selectedBatch) { setBatchStatus(null); return; }

      // selectedBatch can be "key" (batch_name||YYYY-MM-DD||HH:MM) or human label
      let batch_name = '';
      let start_date: string | undefined = undefined;
      let start_time: string | undefined = undefined;

      if (selectedBatch.includes('||')) {
        const parts = selectedBatch.split('||');
        batch_name = (parts[0] || '').trim();
        start_date = (parts[1] || '').trim() || undefined;
        start_time = (parts[2] || '').trim() || undefined;
      } else {
        const parsed = parseBatchLabel(selectedBatch);
        batch_name = parsed.batch_name || '';
        start_date = parsed.start_date;
        start_time = parsed.start_time;
      }

      const params: any = { batch_name };
      if (start_date) params.start_date = start_date;
      if (start_time) params.start_time = start_time;

      const response = await api.get(`/taf/field/exercise/${exerciseId}/batch`, {
        params,
        headers: { Authorization: `Bearer ${token}` }
      });

      setBatchStatus(response.data);
    } catch (err: any) {
      console.error('Erro ao carregar status da turma:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao carregar status'));
    }
  }

  async function loadCriteria(exId: number) {
    try {
      const resp = await api.get(`/taf/exercises/${exId}/criteria`, { headers: { Authorization: `Bearer ${token}` } });
      const items: PassCriteria[] = resp.data || [];
      const map: Record<string, PassCriteria | undefined> = {};
      items.forEach((c) => {
        map[c.gender] = c;
      });
      setCriteriaMap(map);
    } catch (err: any) {
      console.warn('Não foi possível carregar critérios (pode não existir):', err);
      setCriteriaMap({});
    }
  }

  // ---------- Individual flow ----------
  const handleStartEvaluation = async (candidate: CandidateStatus) => {
    if (candidate.status === 'in_progress' && candidate.evaluator_name) {
      setError(`Candidato já está sendo avaliado por ${candidate.evaluator_name}`);
      return;
    }
    if (candidate.status === 'completed') {
      setError('Candidato já completou todas as tentativas');
      return;
    }
    try {
      await api.post('/taf/field/start', {
        candidate_id: candidate.candidate_id,
        exercise_id: Number(exerciseId),
        evaluator_user_id: 1
      }, { headers: { Authorization: `Bearer ${token}` } });

      setSelectedCandidate(candidate);
      setMeasuredValue(0);
      setIsValid(true);
      setEvaluationModal(true);
    } catch (err: any) {
      console.error('Erro ao iniciar avaliação:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao iniciar avaliação'));
    }
  };

  const handleSaveResult = async () => {
    if (!selectedCandidate) return;
    setSaving(true);
    setError(null);
    try {
      await api.post('/taf/field/finish', {
        candidate_id: selectedCandidate.candidate_id,
        exercise_id: Number(exerciseId),
        measured_value: measuredValue,
        attempt_number: selectedCandidate.current_attempt,
        is_valid: isValid
      }, { headers: { Authorization: `Bearer ${token}` } });

      setSuccess('Resultado salvo com sucesso!');
      setEvaluationModal(false);
      setSelectedCandidate(null);
      await loadBatchStatus();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao salvar resultado:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao salvar resultado'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEvaluation = async () => {
    if (selectedCandidate && exerciseId) {
      try {
        await api.delete(`/taf/field/cancel/${exerciseId}/${selectedCandidate.candidate_id}`, { headers: { Authorization: `Bearer ${token}` } });
      } catch (err) {
        console.error('Erro ao cancelar avaliação:', err);
      }
    }
    setEvaluationModal(false);
    setSelectedCandidate(null);
    await loadBatchStatus();
  };

  // ---------- Collective helpers ----------
  const handleToggleCandidateSelection = (candidateId: number) => {
    const next = new Set(selectedCandidates);
    if (next.has(candidateId)) next.delete(candidateId); else next.add(candidateId);
    setSelectedCandidates(next);
  };

  const parseNumberFromString = (s: any): number | null => {
    if (s === undefined || s === null) return null;
    const digits = String(s).replace(/\D/g, '');
    if (!digits) return null;
    const n = parseInt(digits, 10);
    return Number.isFinite(n) ? n : null;
  };

  const handleSelectRange = () => {
    const s = parseNumberFromString(rangeStart);
    const e = parseNumberFromString(rangeEnd);
    if (s === null || e === null) {
      setError('Informe um intervalo válido (ex: 001 a 009).');
      return;
    }
    const start = Math.min(s, e);
    const end = Math.max(s, e);
    const next = new Set(selectedCandidates);
    (batchStatus?.candidates || []).forEach(c => {
      const num = parseNumberFromString(c.candidate_number);
      if (num === null) return;
      if ((c.status === 'pending' || c.status === 'awaiting_retry') && num >= start && num <= end) {
        next.add(c.candidate_id);
      }
    });
    setSelectedCandidates(next);
  };

  const handleSelectVisible = () => {
    const next = new Set(selectedCandidates);
    filteredCandidates.forEach(c => {
      if (c && (c.status === 'pending' || c.status === 'awaiting_retry')) next.add(c.candidate_id);
    });
    setSelectedCandidates(next);
  };

  const handleClearSelection = () => setSelectedCandidates(new Set());

  const handleInvertSelection = () => {
    const next = new Set(selectedCandidates);
    filteredCandidates.forEach(c => {
      if (!(c.status === 'pending' || c.status === 'awaiting_retry')) return;
      if (next.has(c.candidate_id)) next.delete(c.candidate_id); else next.add(c.candidate_id);
    });
    setSelectedCandidates(next);
  };

  const handleStartCollectiveEvaluation = () => {
    if (selectedCandidates.size === 0) { setError('Selecione pelo menos um candidato'); return; }
    const initial = new Map<number, CollectiveResult>();
    selectedCandidates.forEach(id => initial.set(id, { valid: true, laps: 0 }));
    setCollectiveResults(initial);
    collectiveResultsRef.current = initial;
    setCollectiveTimeMs(0);
    setApplyDistanceValue('');
    setModalSearch('');
    setCollectiveModal(true);

    // flag que informa a StopwatchTimer para auto-start ao abrir
    setAutoStartStopwatch(true);
    setStopwatchRunning(true);

    // reset helpers
    autoRegisteredRef.current.clear();
    lastElapsedRef.current = -1;
    stoppedByAutoRef.current = false;
  };

  const handleRecordCollectiveTime = (candidateId: number, opts: { auto?: boolean } = {}) => {
    const isAuto = Boolean(opts.auto);
    const current = (typeof collectiveResultsRef !== 'undefined' && collectiveResultsRef.current) ? collectiveResultsRef.current : collectiveResults;
    const next = new Map(current);
    const prevEntry = next.get(candidateId) || { valid: true, laps: 0 };

    console.debug('handleRecordCollectiveTime called', { candidateId, isAuto, prevEntry, collectiveTimeMs, seconds: msToSecondsRounded(collectiveTimeMs) });

    // se já existe tempo auto e estamos tentando auto novamente, ignorar
    if (prevEntry.time_s !== undefined && prevEntry.time_s !== null && prevEntry.auto && isAuto) {
      return;
    }

    // preserve distance if exists, else compute from laps
    const preservedDistance = (prevEntry.distance_m !== undefined && prevEntry.distance_m !== null)
      ? prevEntry.distance_m
      : (prevEntry.laps ? computeDistanceFromLaps(prevEntry.laps) : undefined);

    const seconds = msToSecondsRounded(collectiveTimeMs);
    next.set(candidateId, {
      ...prevEntry,
      time_s: seconds,
      valid: true,
      auto: isAuto,
      distance_m: preservedDistance
    });

    setCollectiveResults(next);
    collectiveResultsRef.current = next;
    stoppedByAutoRef.current = false;
    console.debug('handleRecordCollectiveTime updated', { candidateId, newEntry: next.get(candidateId) });

    if (isAuto && autoRegisteredRef.current) autoRegisteredRef.current.add(candidateId);
  };

  const handleApplyStopwatchToAll = () => {
    const seconds = msToSecondsRounded(collectiveTimeMs);
    // use a ref se existir; caso contrário lê do state
    const current = (typeof collectiveResultsRef !== 'undefined' && collectiveResultsRef.current) ? collectiveResultsRef.current : collectiveResults;
    const next = new Map(current);

    for (const id of selectedCandidates) {
      const p = next.get(id) || { valid: true, laps: 0 };

      // preserve existing distance if present; otherwise compute from laps if possível
      const preservedDistance = (p.distance_m !== undefined && p.distance_m !== null)
        ? p.distance_m
        : (p.laps ? computeDistanceFromLaps(p.laps) : undefined);

      // operador está registrando "para todos" — isso é uma ação manual (auto=false)
      next.set(id, {
        ...p,
        time_s: seconds,
        valid: true,
        auto: false,
        // só sobrescreve distance_m se já houver valor calculado; caso contrário mantém undefined
        distance_m: preservedDistance
      });

      // se havia sido marcado como autoRegistered, removemos porque operador sobrescreveu manualmente
      if (autoRegisteredRef.current && autoRegisteredRef.current.has(id)) {
        autoRegisteredRef.current.delete(id);
      }
    }

    setCollectiveResults(next);
    collectiveResultsRef.current = next;
    stoppedByAutoRef.current = false;
  };

  const handleAddLap = (candidateId: number, delta = 1) => {
    const next = new Map(collectiveResults);
    const prev = next.get(candidateId) || { valid: true, laps: 0 };
    const newLaps = Math.max(0, (prev.laps ?? 0) + delta);
    const newDistance = trackLengthMeters ? computeDistanceFromLaps(newLaps) : prev.distance_m;
    next.set(candidateId, { ...prev, laps: newLaps, distance_m: newDistance });
    setCollectiveResults(next);
    collectiveResultsRef.current = next;
    stoppedByAutoRef.current = false;
  };

  const applyDistanceToSelected = (distanceMeters: number) => {
    const next = new Map(collectiveResults);
    selectedCandidates.forEach(id => {
      const prev = next.get(id) || { valid: true, laps: 0 };
      next.set(id, { ...prev, distance_m: distanceMeters });
    });
    setCollectiveResults(next);
    collectiveResultsRef.current = next;
    stoppedByAutoRef.current = false;
  };

  const handleUpdateCollectiveResult = (candidateId: number, patch: Partial<CollectiveResult & { auto?: boolean }>) => {
    const current = collectiveResultsRef.current ?? new Map<number, CollectiveResult>();
    const next = new Map(current);
    const prevEntry = next.get(candidateId) || { valid: true, laps: 0 };
    const merged: any = { ...prevEntry, ...patch };

    // se o usuário editou time_s manualmente, marque auto=false
    if (patch.time_s !== undefined && patch.time_s !== null) merged.auto = patch.auto ?? false;

    // se operador fez alteração manual, remova marcação autoRegistered
    if (merged.auto === false && autoRegisteredRef.current.has(candidateId)) {
      autoRegisteredRef.current.delete(candidateId);
    }

    next.set(candidateId, merged);
    setCollectiveResults(next);
    collectiveResultsRef.current = next;
    stoppedByAutoRef.current = false;
  };

  // Substitua a função handleSaveCollectiveResults por esta versão
  const handleSaveCollectiveResults = async () => {
    setSaving(true);
    setError(null);

    try {
      const resultsToSave: any[] = [];
      const exerciseType = exercise?.measurement_type;
      const unit = (exercise?.unit_of_measure || '').toString().toLowerCase();

      // decide se devemos priorizar distância (se o tipo for 'distance' OU a unidade indicar metros)
      const preferDistance = exerciseType === 'distance' || (unit.includes('metro') || unit.includes('metros'));

      // coletores para validar antes de enviar
      const missingDistanceCandidates: number[] = [];
      const debugRows: any[] = [];

      // iterar pelos selecionados para garantir inclusão de todos
      for (const candidateId of Array.from(selectedCandidates)) {
        const candidate = filteredCandidates.find(c => c.candidate_id === candidateId);
        if (!candidate) continue;

        const r = collectiveResults.get(candidateId) || { valid: true, laps: 0 };

        // calcula distância a partir de voltas quando aplicável
        const computedDistance =
          (r.distance_m !== undefined && r.distance_m !== null)
            ? r.distance_m
            : (r.laps ? computeDistanceFromLaps(r.laps) : null);

        const measured_time = r.time_s ?? null;
        const measured_distance = computedDistance ?? null;
        const measured_laps = (r.laps !== undefined && r.laps !== null) ? r.laps : null;

        // Se preferimos distância e não há distância disponível, registre para avisar
        if (preferDistance && (measured_distance === null || measured_distance === undefined)) {
          missingDistanceCandidates.push(candidate.candidate_number ? Number(String(candidate.candidate_number).replace(/\D/g, '')) : candidate.candidate_id);
        }

        // Decide qual valor colocar em measured_value dependendo do tipo efetivo (com fallback)
        let payloadMeasuredValue: number | null = null;
        if (preferDistance) {
          payloadMeasuredValue = measured_distance !== null && measured_distance !== undefined ? Number(Number(measured_distance).toFixed(3)) : null;
        } else if (exerciseType === 'time') {
          payloadMeasuredValue = measured_time !== null && measured_time !== undefined ? Number(measured_time) : null;
        } else if (exerciseType === 'repetitions') {
          payloadMeasuredValue = measured_laps !== null && measured_laps !== undefined ? Number(measured_laps) : (measured_distance ?? measured_time ?? null);
        } else {
          payloadMeasuredValue = measured_time ?? measured_distance ?? measured_laps ?? null;
        }

        debugRows.push({
          candidateId,
          candidateNumber: candidate.candidate_number,
          measured_time,
          measured_distance,
          measured_laps,
          payloadMeasuredValue
        });

        resultsToSave.push({
          candidate_id: candidateId,
          exercise_id: Number(exerciseId),
          measured_value: payloadMeasuredValue,
          measured_distance: measured_distance,
          measured_laps: measured_laps,
          attempt_number: candidate.current_attempt ?? 1,
          is_valid: r.valid ?? true
        });
      }

      // Se estamos tratando como distância mas alguns candidatos não têm distância, aborta e pede preenchimento.
      if (preferDistance && missingDistanceCandidates.length > 0) {
        // formata lista amigável (padrão 3 dígitos)
        const ids = missingDistanceCandidates.map(n => String(n).padStart(3, '0')).join(', ');
        setError(`Preencha a distância (m) para os candidatos: ${ids} antes de salvar. (Atualmente faltando em ${missingDistanceCandidates.length} candidatos)`);
        console.debug('handleSaveCollectiveResults - abortado por falta de distância. debugRows:', debugRows);
        setSaving(false);
        return;
      }

      if (resultsToSave.length === 0) {
        setError('Nenhuma alteração para salvar.');
        setSaving(false);
        return;
      }

      console.debug('handleSaveCollectiveResults payload', { exerciseType, unit, preferDistance, resultsToSave });

      const resp = await api.post('/taf/execution/bulk', { results: resultsToSave }, { headers: { Authorization: `Bearer ${token}` } });

      const updatedCount = resp?.data?.updated_results?.length ?? resultsToSave.length;
      setSuccess(`${updatedCount} resultados salvos com sucesso!`);

      // reset UI e recarrega estado
      setCollectiveModal(false);
      setSelectedCandidates(new Set());
      const cleared = new Map<number, CollectiveResult>();
      setCollectiveResults(cleared);
      collectiveResultsRef.current = cleared;
      setApplyDistanceValue('');
      await loadBatchStatus();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Erro ao salvar resultados:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao salvar resultados'));
    } finally {
      setSaving(false);
    }
  };

  // filter candidates
  const filteredCandidates = (() => {
    let list = (batchStatus?.candidates || []).slice();
    if (selectedBatch && selectedBatch.includes('||')) {
      const members = batchMembers[selectedBatch] || [];
      if (members.length > 0) {
        const membersSet = new Set(members.map(m => String(m)));
        list = list.filter(c => membersSet.has(String(c.candidate_id)));
      }
    }
    const q = (searchNumber || '').toString().trim().toLowerCase();
    if (!q) return list;
    const batchTotal = batchStatus?.total_candidates || (batchStatus?.candidates?.length || 0);
    return list.filter(c => {
      const candidateNumberStr = String(c?.candidate_number ?? '').toLowerCase();
      const fullNameStr = String(c?.full_name ?? '').toLowerCase();
      const padded = String(padNumberByTotal(c?.candidate_number, batchTotal)).toLowerCase();
      return candidateNumberStr.includes(q) || fullNameStr.includes(q) || padded.includes(q);
    });
  })();

  const totalCandidatesInBatch = batchStatus?.total_candidates || (batchStatus?.candidates?.length || 0);

  const filteredSelectedCandidates = useMemo(() => {
    const q = (modalSearch || '').toString().trim().toLowerCase();
    const selectedList = Array.from(selectedCandidates)
      .map(id => filteredCandidates.find(c => c.candidate_id === id))
      .filter(Boolean) as CandidateStatus[];
    if (!q) return selectedList;
    const batchTotal = totalCandidatesInBatch;
    return selectedList.filter(c => {
      const candidateNumberStr = String(c.candidate_number ?? '').toLowerCase();
      const fullNameStr = String(c.full_name ?? '').toLowerCase();
      const padded = String(padNumberByTotal(c.candidate_number, batchTotal)).toLowerCase();
      return candidateNumberStr.includes(q) || fullNameStr.includes(q) || padded.includes(q);
    });
  }, [modalSearch, selectedCandidates, filteredCandidates, totalCandidatesInBatch]);

  // keyboard shortcuts for collective modal
  useEffect(() => {
    if (!collectiveModal) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key >= '1' && e.key <= '9') {
        const idx = parseInt(e.key, 10) - 1;
        const sel = filteredSelectedCandidates.map(c => c.candidate_id);
        if (idx >= 0 && idx < sel.length) {
          const candidateId = sel[idx];
          if (e.shiftKey) handleAddLap(candidateId, 1);
          else handleRecordCollectiveTime(candidateId);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [collectiveModal, filteredSelectedCandidates]); // removidas deps pesadas

  // criteria helper
  const meetsCriteria = (gender: string | undefined, time_s?: number | null, distance_m?: number | null) => {
    if (!gender) return false;
    const crit = criteriaMap[gender];
    if (!crit) return false;
    const hasTime = crit.max_time_s !== undefined && crit.max_time_s !== null;
    const hasDist = crit.min_value !== undefined && crit.min_value !== null;
    if (!hasTime && !hasDist) return false;
    let timeOk = true;
    let distOk = true;
    if (hasTime) {
      if (time_s === undefined || time_s === null) timeOk = false;
      else timeOk = (time_s <= (crit.max_time_s ?? Infinity));
    }
    if (hasDist) {
      if (distance_m === undefined || distance_m === null) distOk = false;
      else distOk = (distance_m >= (crit.min_value ?? -Infinity));
    }
    if (hasTime && hasDist) return timeOk && distOk;
    if (hasTime) return timeOk;
    return distOk;
  };

  // auto-apply collective criteria — NÃO executa durante preview (stopwatchRunning)
  useEffect(() => {
    // não aplicar automaticamente enquanto o cronômetro estiver rodando (preview)
    if (!collectiveModal || !autoApplyCriteria || stopwatchRunning) return;

    try {
      const nowSec = msToSecondsRounded(collectiveTimeMs);
      let changed = false;
      const next = new Map(collectiveResults);

      for (const candidateId of selectedCandidates) {
        const candidate = filteredCandidates.find(c => c.candidate_id === candidateId);
        if (!candidate) continue;
        const r = next.get(candidateId) || { valid: true, laps: 0 };
        const currentDistance = r.distance_m ?? (r.laps ? computeDistanceFromLaps(r.laps) : undefined);
        const timeCandidate = r.time_s ?? undefined;

        // avalia apenas com valores confirmados (timeCandidate) ou com nowSec (parado)
        if (meetsCriteria(candidate.gender, timeCandidate ?? nowSec, currentDistance)) {
          const crit = criteriaMap[candidate.gender];
          const newEntry: CollectiveResult = { ...r, valid: true };

          if (crit?.max_time_s !== undefined && crit?.max_time_s !== null) {
            const t = timeCandidate ?? nowSec;
            newEntry.time_s = Math.min(t, crit.max_time_s ?? t);
          }

          if (crit?.min_value !== undefined && crit?.min_value !== null) {
            const d = currentDistance ?? (r.laps ? computeDistanceFromLaps(r.laps) : undefined);
            if (d !== undefined && d !== null) newEntry.distance_m = d;
          }

          next.set(candidateId, newEntry);
          changed = true;
        }
      }

      if (changed) {
        setCollectiveResults(next);
        collectiveResultsRef.current = next;
        // não altere stoppedByAutoRef aqui — essa flag deve permanecer até ação manual
        setSuccess('Alguns resultados foram preenchidos automaticamente conforme critérios.');
        const t = window.setTimeout(() => { if (mountedRef.current) setSuccess(null); }, 2500);
        return () => clearTimeout(t);
      }
    } catch (err) {
      console.error('Erro no efeito auto-apply collective criteria:', err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectiveTimeMs, collectiveModal, autoApplyCriteria, criteriaMap, selectedCandidates, stopwatchRunning]);

  // Auto‑registro em grupo (robusto): aplica O MESMO tempo atual a todos os selecionados e para o cronômetro.
  // Protegido com try/catch, validações e verifica mountedRef antes de setState.
  useEffect(() => {
    if (!collectiveModal) return;
    if (!criteriaMap) return;
    if (!selectedCandidates || selectedCandidates.size === 0) return;

    try {
      const nowElapsed = msToSecondsRounded(collectiveTimeMs);
      if (!Number.isFinite(nowElapsed)) {
        console.debug('auto-register (group): nowElapsed is not a finite number', nowElapsed);
        return;
      }

      // helper para achar crit por gênero (tolerante)
      const findCrit = (candidate: CandidateStatus | undefined) => {
        if (!candidate?.gender) return undefined;
        const gRaw = String(candidate.gender).trim();
        if (gRaw.length === 1) return criteriaMap[gRaw.toUpperCase()];
        const first = (gRaw[0] || '').toUpperCase();
        if (first === 'M') return criteriaMap['M'];
        if (first === 'F') return criteriaMap['F'];
        return criteriaMap[gRaw];
      };

      // monta lista de limites (em segundos) entre os selecionados
      const times: number[] = [];
      const candidatesList = batchStatus?.candidates ?? [];
      for (const id of Array.from(selectedCandidates)) {
        const cand = candidatesList.find(c => c.candidate_id === id);
        if (!cand) continue;
        const crit = findCrit(cand);
        if (!crit) continue;
        const rawMax = crit.max_time_s;
        if (rawMax === undefined || rawMax === null) continue;
        const maxTimeSec = (typeof rawMax === 'number') ? (rawMax > 1000 ? rawMax / 1000 : rawMax) : (Number(String(rawMax).replace(',', '.')) || 0);
        if (Number.isFinite(maxTimeSec) && maxTimeSec > 0) times.push(maxTimeSec);
      }

      if (times.length === 0) return;

      const minMax = Math.min(...times);
      console.debug('auto-register (group): nowElapsed, minMax', { nowElapsed, minMax });

      // só age quando cronômetro >= menor crit entre selecionados
      if (nowElapsed < minMax) return;

      // aplica o MESMO tempo atual a todos os selecionados que ainda não têm tempo manual
      const secondsToApply = nowElapsed;
      const current = collectiveResultsRef.current ?? collectiveResults;
      const next = new Map(current);
      let anyChanged = false;

      for (const id of Array.from(selectedCandidates)) {
        const prev = next.get(id) || { valid: true, laps: 0 };

        // não sobrescrever valores marcados manualmente
        if (prev.time_s !== undefined && prev.time_s !== null && prev.auto === false) continue;

        const preservedDistance = (prev.distance_m !== undefined && prev.distance_m !== null)
          ? prev.distance_m
          : (prev.laps ? computeDistanceFromLaps(prev.laps) : undefined);

        next.set(id, {
          ...prev,
          time_s: secondsToApply,
          valid: true,
          auto: true,
          distance_m: preservedDistance
        });

        anyChanged = true;
        autoRegisteredRef.current.add(id);
      }

      if (anyChanged) {
        // só setState se o componente continuar montado
        if (!mountedRef.current) return;
        setCollectiveResults(next);
        collectiveResultsRef.current = next;

        // mensagem temporária
        setSuccess('Resultados preenchidos automaticamente (mesmo tempo para todos).');
        const t = window.setTimeout(() => {
          if (mountedRef.current) setSuccess(null);
        }, 2500);

        // --- NOVO: freeze + parar o cronômetro de forma segura ---
        // marcar que foi parado automaticamente (para ignorar ticks subsequentes)
        stoppedByAutoRef.current = true;

        // garantir que a UI mostre exatamente o mesmo tempo (em ms)
        const msToApply = Math.round(secondsToApply * 1000);
        if (mountedRef.current) {
          setCollectiveTimeMs(msToApply);
          setStopwatchRunning(false);
        }
        // ----------------------------------------------------------------

        return () => { clearTimeout(t); };      
      }
    } catch (err) {
      console.error('Erro no efeito auto-register (group):', err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectiveTimeMs, collectiveModal, selectedCandidates, criteriaMap, lapsMode, trackLengthMeters, batchStatus]);


  // Pré‑visualização em tempo real (throttled, robusta) — atualiza time_s para todos os selecionados sem marcar como auto
  useEffect(() => {
    if (!collectiveModal) return;
    // opcional: apenas quando cronômetro rodando
    // if (!stopwatchRunning) return;

    try {
      const seconds = msToSecondsRounded(collectiveTimeMs);
      if (!Number.isFinite(seconds)) return;

      const minMsBetween = 200;
      const now = performance.now();
      if ((lastLiveUpdateAtRef.current || 0) + minMsBetween > now) return;
      lastLiveUpdateAtRef.current = now;

      setCollectiveResults(prev => {
        const next = new Map(prev);
        let changed = false;

        for (const id of Array.from(selectedCandidates)) {
          const prevEntry = next.get(id) || { valid: true, laps: 0 };

          // não sobrescrever tempos manuais
          if (prevEntry.time_s !== undefined && prevEntry.time_s !== null && prevEntry.auto === false) {
            continue;
          }

          // atualização de visualização: não altere prevEntry.auto
          if (prevEntry.time_s !== seconds) {
            next.set(id, { ...prevEntry, time_s: seconds, valid: true });
            changed = true;
          }
        }

        if (!changed) return prev;
        // sincroniza ref imediatamente
        collectiveResultsRef.current = next;
        return next;
      });
    } catch (err) {
      console.error('Erro no efeito live-preview:', err);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectiveTimeMs, collectiveModal, selectedCandidates, stopwatchRunning]);

  // auto-apply individual
  useEffect(() => {
    if (!evaluationModal || !autoApplyCriteria || !selectedCandidate) return;
    const crit = criteriaMap[selectedCandidate.gender];
    if (!crit) return;
    let meets = false;
    if (exercise?.measurement_type === 'time') {
      meets = meetsCriteria(selectedCandidate.gender, measuredValue, undefined);
    } else if (exercise?.measurement_type === 'distance') {
      meets = meetsCriteria(selectedCandidate.gender, undefined, measuredValue);
    } else if (exercise?.measurement_type === 'repetitions') {
      meets = meetsCriteria(selectedCandidate.gender, undefined, measuredValue);
    }
    if (meets) {
      setIsValid(true);
      setSuccess('Medida atende ao(s) critério(s) configurado(s).');
      setTimeout(() => setSuccess(null), 2000);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [measuredValue, evaluationModal, autoApplyCriteria, criteriaMap, selectedCandidate]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress size={60} />
      </Box>
    );
  }

  // ---------- Render (full JSX) ----------
  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <IconButton onClick={() => navigate(`/taf/events/${eventId}/exercises`)}>
            <ArrowBack />
          </IconButton>
          <Box>
            <Typography variant="h3" component="h1" fontWeight={700}>
              <FitnessCenter sx={{ verticalAlign: 'middle', mr: 1 }} /> Avaliação em Campo
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {eventName} • {exercise?.name}
            </Typography>
            <Chip label={exercise?.execution_mode === 'collective' ? '📋 Coletivo' : '📋 Individual'} color="primary" size="small" sx={{ mt: 0.5 }} />
          </Box>
        </Stack>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}

      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField select label="Turma" value={selectedBatch} onChange={(e) => setSelectedBatch(e.target.value)} fullWidth>
              {batches.map(key => <MenuItem key={key} value={key}>{batchLabels[key] ?? key}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              label="Buscar por número ou nome"
              value={searchNumber}
              onChange={(e) => setSearchNumber(e.target.value)}
              fullWidth
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search sx={{ color: 'text.secondary' }} />
                  </InputAdornment>
                )
              }}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            {batchStatus && <Stack direction="row" spacing={1}>
              <Chip label={`${batchStatus.total_candidates} total`} size="small" />
              <Chip label={`${batchStatus.pending_count} aguardando`} size="small" />
              <Chip label={`${batchStatus.in_progress_count} em andamento`} color="warning" size="small" />
              <Chip label={`${batchStatus.completed_count} concluídos`} color="success" size="small" />
            </Stack>}
          </Grid>
        </Grid>
      </Paper>

      {/* Individual / Collective rendering */}
      {/* Individual mode */}
      {exercise?.execution_mode === 'individual' && (
        <Box>
          <Typography variant="h6" gutterBottom>📋 Seleção Manual de Candidatos</Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom> Clique no cartão do candidato para iniciar a avaliação </Typography>
          <Grid container spacing={2} sx={{ mt: 1 }} alignItems="stretch">
            {filteredCandidates.map(candidate => {
              const isSelected = selectedCandidates.has(candidate.candidate_id);
              const canSelect = candidate.status === 'pending' || candidate.status === 'awaiting_retry';
              return (
                <Grid item xs={12} sm={6} md={4} lg={3} key={candidate.candidate_id} sx={{ display: 'flex' }}>
                  <Card
                    sx={{
                      cursor: canSelect ? 'pointer' : 'default',
                      border: 2,
                      borderColor: isSelected ? 'primary.main' : candidate.status === 'completed' ? 'success.main' : 'grey.300',
                      bgcolor: isSelected ? 'primary.50' : 'white',
                      position: 'relative',
                      '&:hover': canSelect ? { boxShadow: 4, borderColor: 'primary.main' } : {},
                      display: 'flex',
                      flexDirection: 'column',
                      width: '100%',
                      boxSizing: 'border-box',
                      height: '100%'
                    }}
                    onClick={() => { if (canSelect) handleStartEvaluation(candidate); }}
                  >
                    <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="start">
                        <Badge
                          badgeContent={`${formatCandidateNumber(candidate.candidate_number, totalCandidatesInBatch)}`}
                          max={9999}
                          color="primary"
                          sx={{ '& .MuiBadge-badge': { fontSize: '1.2rem', height: 32, minWidth: 32, borderRadius: '16px' } }}
                        >
                          <Box sx={{ width: 40 }} />
                        </Badge>
                        <Chip icon={getStatusIcon(candidate.status)} label={getStatusLabel(candidate.status)} color={getStatusColor(candidate.status)} size="small" />
                      </Stack>

                      <Box>
                        <Typography variant="subtitle1" fontWeight={600} sx={{ mt: 2 }}>{candidate.full_name}</Typography>
                        <Typography variant="caption" color="text.secondary">{candidate.gender === 'M' ? 'Masculino' : 'Feminino'}</Typography>

                        {candidate.status === 'in_progress' && candidate.evaluator_name && <Typography variant="caption" color="warning.main" display="block" sx={{ mt: 1 }}>👤 {candidate.evaluator_name}</Typography>}

                        {candidate.best_result !== undefined && <Stack direction="row" spacing={1} sx={{ mt: 1 }}><Chip label={`${candidate.best_result} ${exercise.unit_of_measure}`} size="small" color={candidate.is_approved ? 'success' : 'error'} /></Stack>}

                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>Tentativa {candidate.current_attempt}/{candidate.max_attempts}</Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        </Box>
      )}

      {/* Collective mode (trigger grid) */}
      {exercise?.execution_mode === 'collective' && (
        <Box sx={{ mt: 3 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Box>
              <Typography variant="h6">🏃‍♂️ Modo Coletivo - Seleção Múltipla</Typography>
              <Typography variant="body2" color="text.secondary">Selecione os candidatos que farão o exercício juntos</Typography>
            </Box>
            <Button variant="contained" color="primary" size="large" onClick={handleStartCollectiveEvaluation} disabled={selectedCandidates.size === 0} startIcon={<PlayArrow />}>
              Iniciar Avaliação ({selectedCandidates.size} selecionados)
            </Button>
          </Stack>

          {/* CONTROLES DE SELEÇÃO (fora do modal, antes dos cards) */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
            <TextField size="small" label="De (número)" placeholder="001" value={rangeStart} onChange={(e) => setRangeStart(e.target.value)} />
            <TextField size="small" label="Até (número)" placeholder="009" value={rangeEnd} onChange={(e) => setRangeEnd(e.target.value)} />
            <Button variant="contained" onClick={handleSelectRange}>Selecionar Intervalo</Button>

            <Button variant="outlined" onClick={handleSelectVisible}>Selecionar Visíveis</Button>
            <Button variant="outlined" onClick={handleInvertSelection}>Inverter Seleção</Button>
            <Button variant="text" color="inherit" onClick={handleClearSelection}>Limpar Seleção</Button>

            <Box sx={{ flex: 1 }} />
          </Box>

          <Grid container spacing={2} sx={{ mt: 1 }} alignItems="stretch">
            {filteredCandidates.map(candidate => {
              const isSelected = selectedCandidates.has(candidate.candidate_id);
              const canSelect = candidate.status === 'pending' || candidate.status === 'awaiting_retry';
              return (
                <Grid item xs={12} sm={6} md={4} lg={3} key={candidate.candidate_id} sx={{ display: 'flex' }}>
                  <Card sx={{ cursor: canSelect ? 'pointer' : 'default', border: 2, borderColor: isSelected ? 'primary.main' : candidate.status === 'completed' ? 'success.main' : 'grey.300', bgcolor: isSelected ? 'primary.50' : 'white', position: 'relative', '&:hover': canSelect ? { boxShadow: 4, borderColor: 'primary.main' } : {}, display: 'flex', flexDirection: 'column', width: '100%', boxSizing: 'border-box', height: '100%' }} onClick={() => { if (canSelect) handleToggleCandidateSelection(candidate.candidate_id); }}>
                    {canSelect && <Checkbox checked={isSelected} sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1 }} onClick={(e) => { e.stopPropagation(); handleToggleCandidateSelection(candidate.candidate_id); }} />}
                    <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="start">
                        <Badge
                          badgeContent={<span>{formatCandidateNumber(candidate.candidate_number, totalCandidatesInBatch)}</span>}
                          max={9999}
                          color="primary"
                          sx={{ '& .MuiBadge-badge': { fontSize: '1.2rem', height: 32, minWidth: 32, borderRadius: '16px' } }}
                        >
                          <Box sx={{ width: 40 }} />
                        </Badge>
                        <Chip icon={getStatusIcon(candidate.status)} label={getStatusLabel(candidate.status)} color={getStatusColor(candidate.status)} size="small" />
                      </Stack>

                      <Box>
                        <Typography variant="subtitle1" fontWeight={600} sx={{ mt: 2 }}>{candidate.full_name}</Typography>
                        <Typography variant="caption" color="text.secondary">{candidate.gender === 'M' ? 'Masculino' : 'Feminino'}</Typography>
                        {candidate.best_result !== undefined && <Stack direction="row" spacing={1} sx={{ mt: 1 }}><Chip label={`${candidate.best_result} ${exercise.unit_of_measure}`} size="small" color={candidate.is_approved ? 'success' : 'error'} /></Stack>}
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>Tentativa {candidate.current_attempt}/{candidate.max_attempts}</Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        </Box>
      )}

      {/* Individual modal */}
      <Dialog open={evaluationModal} onClose={handleCancelEvaluation} maxWidth="md" fullWidth>
        <DialogTitle>📋 Registrar Resultado</DialogTitle>
        <DialogContent>
          {selectedCandidate && exercise && (
            <Stack spacing={3} sx={{ mt: 1 }}>
              <Paper sx={{ p: 2, bgcolor: 'primary.50' }}>
                <Typography variant="h6">N° {formatCandidateNumber(selectedCandidate.candidate_number, totalCandidatesInBatch)}</Typography>
                <Typography variant="body1">{selectedCandidate.full_name}</Typography>
                <Typography variant="caption" color="text.secondary">{selectedCandidate.gender === 'M' ? 'Masculino' : 'Feminino'} • Tentativa {selectedCandidate.current_attempt} de {selectedCandidate.max_attempts}</Typography>
              </Paper>

              {/* === Bloco de critérios por gênero (insere aqui) === */}
              {(() => {
                // protege caso não haja candidato/criteria ainda
                if (!selectedCandidate) return null;

                const rawGender = String(selectedCandidate.gender || '').trim();
                // normaliza para 'M' ou 'F' quando possível
                let genderKey = '';
                if (rawGender.length === 1) genderKey = rawGender.toUpperCase();
                else {
                  const first = (rawGender[0] || '').toUpperCase();
                  if (first === 'M') genderKey = 'M';
                  else if (first === 'F') genderKey = 'F';
                  else genderKey = rawGender; // fallback
                }

                const crit = criteriaMap[genderKey];

                // helper para formatar tempo (segundos -> mm:ss)
                const formatTime = (s?: number | null) => {
                  if (s === undefined || s === null) return '-';
                  const minutes = Math.floor(s / 60);
                  const secs = Math.round(s % 60);
                  return `${minutes}:${String(secs).padStart(2, '0')} s`;
                };

                if (!crit) {
                  return (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="body2" color="text.secondary">Critérios: — (não configurado para este gênero)</Typography>
                    </Box>
                  );
                }

                const minValueLabel = crit.min_value !== undefined && crit.min_value !== null ? `${crit.min_value} ${exercise.unit_of_measure ?? ''}` : '—';
                const maxTimeLabel = crit.max_time_s !== undefined && crit.max_time_s !== null ? formatTime(crit.max_time_s) : '—';

                return (
                  <Box sx={{ mt: 1 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip label={`Critério (${genderKey === 'M' ? 'Masculino' : genderKey === 'F' ? 'Feminino' : genderKey})`} color="primary" size="small" />
                      <Chip label={`Min: ${minValueLabel}`} size="small" />
                      <Chip label={`Tempo ≤ ${maxTimeLabel}`} size="small" />
                    </Stack>
                  </Box>
                );
              })()}
              {/* === fim bloco critérios === */}

              {exercise.measurement_type === 'repetitions' && <RepetitionCounter initialValue={0} onValueChange={setMeasuredValue} minValue={0} maxValue={999} />}

              {exercise.measurement_type === 'time' && (
                <Box>
                  <StopwatchTimer
                    key={stopwatchKey}                     // força remount quando incrementarmos stopwatchKey
                    mode="progressive"
                    running={stopwatchRunning}
                    tickIntervalMs={250}
                    onTimeChange={(ms: number) => {
                      // se paramos automaticamente, ignorar ticks subsequentes
                      if (stoppedByAutoRef.current) return;
                      console.debug('stopwatch tick', { ms, s: msToSecondsRounded(ms) });
                      setCollectiveTimeMs(ms);
                    }}
                    onStop={() => setStopwatchRunning(false)}
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: 'center' }}>O tempo está sendo registrado automaticamente. Clique em "Parar" quando o candidato terminar.</Typography>
                </Box>
              )}

              {exercise.measurement_type === 'distance' && (
                <TextField label={`Distância Percorrida (${exercise.unit_of_measure})`} type="number" value={measuredValue} onChange={(e) => setMeasuredValue(parseFloat(e.target.value) || 0)} fullWidth autoFocus helperText="Digite a distância em metros" />
              )}

              <FormControlLabel control={<Checkbox checked={isValid} onChange={(e) => setIsValid(e.target.checked)} />} label="Tentativa válida" />
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={handleCancelEvaluation} color="inherit"><Cancel /> Cancelar</Button>
          <Button onClick={handleSaveResult} color="primary" variant="contained" disabled={saving}>{saving ? <CircularProgress size={20} /> : <><Save /> Salvar Resultado</>}</Button>
        </DialogActions>
      </Dialog>

      {/* Collective modal */}
      <Dialog open={collectiveModal} onClose={() => { setCollectiveModal(false); setModalSearch(''); }} maxWidth="lg" fullWidth PaperProps={{ sx: { minHeight: '80vh' } }} ref={collectiveModalRef}>
        <DialogTitle>🏃‍♂️ Avaliação Coletiva - {selectedCandidates.size} Candidatos</DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            {/* Top controls */}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
              <TextField size="small" label="Tamanho da pista (m)" type="number" value={trackLengthMeters} onChange={(e) => setTrackLengthMeters(e.target.value === '' ? '' : Number(e.target.value))} />
              <Button variant="outlined" onClick={() => {
                const next = new Map(collectiveResults);
                for (const [id, v] of next.entries()) {
                  if (v.laps && trackLengthMeters) next.set(id, { ...v, distance_m: computeDistanceFromLaps(v.laps) });
                }
                setCollectiveResults(next);
                collectiveResultsRef.current = next;
                stoppedByAutoRef.current = false;
              }}>Aplicar Pista → Distâncias (para quem já tem voltas)</Button>

              <Button variant="contained" onClick={handleApplyStopwatchToAll}>Registrar Cronômetro para TODOS</Button>

              <Button variant="outlined" onClick={() => setLapsMode(!lapsMode)}>{lapsMode ? 'Modo Voltas: ON' : 'Modo Voltas: OFF'}</Button>

              <FormControlLabel control={<Checkbox checked={autoApplyCriteria} onChange={(e) => setAutoApplyCriteria(e.target.checked)} />} label="Aplicar critérios automaticamente" />

              <Box sx={{ flex: 1 }} />
              <TextField size="small" label="Aplicar distância (m) a selecionados" type="number" value={applyDistanceValue} onChange={(e) => setApplyDistanceValue(e.target.value === '' ? '' : Number(e.target.value))} />
              <Button variant="outlined" onClick={() => { if (applyDistanceValue !== '' && !isNaN(Number(applyDistanceValue))) applyDistanceToSelected(Number(applyDistanceValue)); }}>Aplicar</Button>
            </Box>

            {/* EXIBIÇÃO DE CRITÉRIOS (M/F) */}
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
              {['M','F'].map(g => {
                const crit = criteriaMap[g];
                const label = g === 'M' ? 'Masculino' : 'Feminino';
                if (!crit) {
                  return (
                    <Chip
                      key={g}
                      label={`${label}: —`}
                      size="small"
                      variant="outlined"
                    />
                  );
                }
                const min = crit.min_value !== undefined && crit.min_value !== null ? `${crit.min_value}` : '-';
                const time = crit.max_time_s !== undefined && crit.max_time_s !== null ? `${crit.max_time_s}s` : '-';
                return (
                  <Chip
                    key={g}
                    label={`${label}: min ${min} ${exercise?.unit_of_measure || ''} • tempo ≤ ${time}`}
                    size="small"
                    color="primary"
                  />
                );
              })}
            </Box>

            {/* Stopwatch reference */}
            {exercise?.measurement_type === 'time' && (
              <Box sx={{ mb: 2 }}>
                <StopwatchTimer
                  key={stopwatchKey}                     // força remount quando incrementarmos stopwatchKey
                  mode="progressive"
                  running={stopwatchRunning}
                  tickIntervalMs={250}
                  onTimeChange={(ms: number) => {
                    // se paramos automaticamente, ignorar ticks subsequentes
                    if (stoppedByAutoRef.current) return;
                    console.debug('stopwatch tick', { ms, s: msToSecondsRounded(ms) });
                    setCollectiveTimeMs(ms);
                  }}
                  onStop={() => setStopwatchRunning(false)}
                />
                <Box sx={{ textAlign: 'center', mt: 1 }}>
                  <Typography variant="h6">Tempo atual: {formatMsToDisplay(collectiveTimeMs)}</Typography>
                  <Typography variant="caption" color="text.secondary">Atalhos: teclas 1..9 = gravar tempo para candidato n; Shift+1..9 = +1 volta</Typography>
                </Box>
              </Box>
            )}

            {/* FILTRO DENTRO DO MODAL */}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
              <TextField
                size="small"
                label="Filtrar candidatos (nº ou nome)"
                placeholder="Ex: 001 ou Silva"
                value={modalSearch}
                onChange={(e) => setModalSearch(e.target.value)}
                sx={{ minWidth: 280 }}
              />

              <Button size="small" variant="outlined" onClick={() => setModalSearch('')}>Limpar busca</Button>

              <Box sx={{ flex: 1 }} />
            </Box>

            <Typography variant="h6">Resultados Individuais:</Typography>

            <Grid container spacing={2} alignItems="stretch">
              {filteredSelectedCandidates.map(candidate => {
                const candidateId = candidate.candidate_id;
                const r = collectiveResults.get(candidateId) || { valid: true, laps: 0 };
                return (
                  <Grid item xs={12} md={6} key={candidateId} sx={{ display: 'flex' }}>
                    <Paper
                      sx={{
                        p: 2,
                        border: 1,
                        borderColor: 'grey.300',
                        width: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        boxSizing: 'border-box',
                        height: '100%'
                      }}
                    >
                      <Stack sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }} spacing={2}>
                        <Box display="flex" justifyContent="space-between" alignItems="center">
                          <Box>
                            <Typography variant="subtitle1" fontWeight={600}>N° {padNumberByTotal(candidate.candidate_number, totalCandidatesInBatch)} - {candidate.full_name}</Typography>
                            <Typography variant="caption" color="text.secondary">{candidate.gender === 'M' ? 'Masculino' : 'Feminino'}</Typography>
                          </Box>

                          <Stack direction="row" spacing={1}>
                            {lapsMode && <Tooltip title="Adicionar volta"><IconButton onClick={() => handleAddLap(candidateId, 1)}><Add /></IconButton></Tooltip>}
                            {lapsMode && <Tooltip title="Remover volta"><IconButton onClick={() => handleAddLap(candidateId, -1)}><Remove /></IconButton></Tooltip>}
                          </Stack>
                        </Box>

                        {exercise?.measurement_type !== 'distance' && (
                          <TextField
                            label="Tempo (s)"
                            type="number"
                            value={r.time_s ?? ''}
                            onChange={(e) => {
                              // permitir edição manual (desmarca auto se estava auto)
                              const v = e.target.value === '' ? undefined : parseFloat(e.target.value);
                              handleUpdateCollectiveResult(candidateId, { time_s: v, auto: false });
                            }}
                            fullWidth
                            size="small"
                            helperText={r.auto ? 'Preenchido automaticamente' : `Cronômetro: ${formatMsToDisplay(collectiveTimeMs)}`}
                            InputProps={{
                              endAdornment: (
                                <>
                                  {r.auto ? (
                                    // mostra ícone editar para permitir sobrescrever se o usuário desejar
                                    <IconButton size="small" onClick={(ev) => { ev.stopPropagation(); handleUpdateCollectiveResult(candidateId, { auto: false }); }}>
                                      <Edit fontSize="small" />
                                    </IconButton>
                                  ) : null}
                                </>
                              )
                            }}
                            disabled={r.auto === true} // se auto, bloqueia edição até usuário clicar no Edit (que seta auto:false)
                          />
                        )}

                        {lapsMode && (
                          <Stack direction="row" spacing={2} alignItems="center">
                            <Typography>Voltas: {r.laps ?? 0}</Typography>
                            <Typography>Distância: {r.distance_m !== undefined ? `${r.distance_m} m` : (trackLengthMeters ? `${(r.laps ?? 0) * Number(trackLengthMeters)} m` : '-')}</Typography>
                          </Stack>
                        )}

                        {exercise?.measurement_type !== 'repetitions' && (
                          <TextField label="Distância (m)" type="number" value={r.distance_m ?? ''} onChange={(e) => handleUpdateCollectiveResult(candidateId, { distance_m: e.target.value === '' ? undefined : parseFloat(e.target.value) })} fullWidth size="small" />
                        )}

                        <FormControlLabel control={<Checkbox checked={r.valid ?? true} onChange={(e) => handleUpdateCollectiveResult(candidateId, { valid: e.target.checked })} />} label="Tentativa válida" />
                      </Stack>
                    </Paper>
                  </Grid>
                );
              })}
            </Grid>
          </Stack>
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={() => { setCollectiveModal(false); setModalSearch(''); }} color="inherit"><Cancel /> Cancelar</Button>
          <Button onClick={handleSaveCollectiveResults} color="primary" variant="contained" disabled={saving}>{saving ? <CircularProgress size={20} /> : <><Save /> Salvar Todos os Resultados</>}</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
