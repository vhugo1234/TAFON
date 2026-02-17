import React, { useEffect, useState, useRef } from 'react';
import {
  Container, Typography, Box, Button, Stack, Alert, CircularProgress,
  TextField, MenuItem, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, IconButton, Chip, Checkbox, InputAdornment
} from '@mui/material';
import {
  ArrowBack, Save, CheckCircle, Cancel, Timer, FitnessCenter
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../lib/api';
import { padNumberByTotal } from '../lib/format';
import { formatDateBR } from '../lib/dateUtils';

interface Exercise {
  id: number;
  name: string;
  unit_of_measure: string;
  max_attempts: number;
}

interface Candidate {
  id: number;
  full_name: string;
  cpf: string;
  registration_number: string;
  gender: 'M' | 'F';
  batch_name?: string;
  batch_number?: string | number;
  start_time?: string | null;
  start_date?: string | null;
}

interface Criteria {
  id: number;
  gender: 'M' | 'F';
  min_value: number;
  max_time_s?: number;
}

// ADICIONEI result_id para podermos atualizar registros existentes no backend
interface AttemptData {
  attempt_number: number;
  measured_value: number | null;
  is_valid: boolean;
  is_approved?: boolean;
  result_id?: number | null;
}

interface CandidateExecution {
  candidate: Candidate;
  attempts: AttemptData[];
  best_value?: number;
  overall_status?: 'approved' | 'failed' | 'pending';
}

export default function TAFExecutionPage() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const { eventId, exerciseId } = useParams<{ eventId: string; exerciseId: string }>();

  // Estados
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [criteria, setCriteria] = useState<Criteria[]>([]);
  const [executions, setExecutions] = useState<CandidateExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [eventName, setEventName] = useState<string>('');

  // Filtros
  const [batchFilter, setBatchFilter] = useState<string>('');
  const [candidateFilter, setCandidateFilter] = useState<string>('');
  // agora batches é array de chaves; batchLabels guarda rótulos legíveis; batchMembers guarda ids
  const [batches, setBatches] = useState<string[]>([]);
  const [batchLabels, setBatchLabels] = useState<Record<string, string>>({});
  const [batchMembers, setBatchMembers] = useState<Record<string, number[]>>({});

  // track original snapshot and whether there are changes
  const originalExecutionsRef = useRef<CandidateExecution[] | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Carregar dados
  useEffect(() => {
    if (eventId && exerciseId) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, exerciseId, token]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Carrega evento
      const eventResponse = await api.get(`/taf/events/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEventName(eventResponse.data.name);

      // Carrega exercício
      const exerciseResponse = await api.get(`/taf/exercises/${exerciseId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setExercise(exerciseResponse.data);

      // Carrega critérios
      const criteriaResponse = await api.get(`/taf/exercises/${exerciseId}/criteria`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCriteria(criteriaResponse.data || []);

      // Carrega candidatos e resultados incrementalmente (UI responsiva)
      // Esta chamada substitui qualquer uso direto de `candidatesData`
      await fetchAndProcessCandidatesIncremental(eventId, exerciseResponse.data.max_attempts);

    } catch (err: any) {
      console.error('Erro ao carregar dados:', err);
      setError(String(err?.response?.data?.detail || err?.message || 'Erro ao carregar dados'));
    } finally {
      // Se o incremental for o responsável por esconder o loading após a 1ª página,
      // garantir que não forcemos reexibir o spinner aqui (mas manter para erro/finalização).
      setLoading(false);
    }
  };

  
  // replace the existing buildBatchesFromCandidates with this 
  const buildBatchesFromCandidates = async (evtId: string | undefined, providedItems?: any[]) => {
    if (!evtId) return;
    try {
      // se já temos lista completa (fornecida), use-a
      let allItems: any[] = Array.isArray(providedItems) && providedItems.length > 0 ? providedItems.slice() : [];

      // tentativa rápida: /detailed (se não tivermos items)
      if (allItems.length === 0) {
        try {
          const resp = await api.get(`/taf/candidates/batches/${evtId}/detailed`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          const items: any[] = resp.data || [];

          if (Array.isArray(items) && items.length > 0) {
            // normaliza para o mesmo formato que usamos no fallback e ordena por data/hora/numero da turma
            const processedDetailed = items.map((i: any) => ({
              key: i.key,
              display: i.label || i.key,
              count: i.count ?? (Array.isArray(i.members) ? i.members.length : 0),
              members: (i.members || []).map((m: any) => Number(m)).filter((n: number) => Number.isFinite(n)),
              start_date: i.start_date ?? i.batch_date ?? '',
              start_time: i.start_time ?? i.batch_start_time ?? ''
            }));

            // helpers locais
            const parseDateTimeToTs = (dateStr?: string, timeStr?: string) => {
              if (!dateStr) return Number.POSITIVE_INFINITY;
              let iso = '';
              if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                iso = dateStr;
              } else if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
                const [d, m, y] = dateStr.split('/');
                iso = `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
              } else {
                iso = dateStr;
              }
              const timePart = timeStr && /\d{1,2}:\d{2}/.test(timeStr) ? timeStr : '00:00';
              const ts = Date.parse(`${iso}T${timePart}:00`);
              if (Number.isFinite(ts)) return ts;
              const alt = Date.parse(`${dateStr} ${timeStr || ''}`);
              return Number.isFinite(alt) ? alt : Number.POSITIVE_INFINITY;
            };

            const extractTurmaNumber = (s: string) => {
              if (!s) return Number.POSITIVE_INFINITY;
              const m = s.match(/turma\s*#?\s*0*([0-9]+)/i) || s.match(/#\s*0*([0-9]+)/i);
              if (m && m[1]) return Number(m[1]);
              return Number.POSITIVE_INFINITY;
            };

            processedDetailed.sort((a: any, b: any) => {
              const tsa = parseDateTimeToTs(a.start_date, a.start_time);
              const tsb = parseDateTimeToTs(b.start_date, b.start_time);
              if (tsa !== tsb) return tsa - tsb;

              const na = extractTurmaNumber(a.display || a.key || '');
              const nb = extractTurmaNumber(b.display || b.key || '');
              if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) return na - nb;
              if (Number.isFinite(na) && !Number.isFinite(nb)) return -1;
              if (!Number.isFinite(na) && Number.isFinite(nb)) return 1;

              return (a.display || '').localeCompare(b.display || '', undefined, { numeric: true });
            });

            setBatches(processedDetailed.map((p: any) => p.key));
            setBatchLabels(Object.fromEntries(processedDetailed.map((p: any) => [p.key, `${p.display}${p.count ? ' (' + p.count + ')' : ''}`])));
            setBatchMembers(Object.fromEntries(processedDetailed.map((p: any) => [p.key, p.members])));
            if (processedDetailed.length > 0) setBatchFilter(prev => prev || processedDetailed[0].key);
            return;
          }
        } catch (err: any) {
          // se 404 ou outro erro, cai no fallback paginado abaixo
          // console.info('detailed unavailable, falling back', err?.response?.status);
        }
      }

      // fallback paginado (se ainda não temos allItems)
      if (allItems.length === 0) {
        const pageSize = 200;
        let page = 1;
        while (true) {
          const r = await api.get(`/taf/candidates/by-event/${evtId}`, {
            params: { page, page_size: pageSize },
            headers: { Authorization: `Bearer ${token}` }
          });
          const itemsPage = r.data?.items || (Array.isArray(r.data) ? r.data : []);
          if (!Array.isArray(itemsPage) || itemsPage.length === 0) break;
          allItems = allItems.concat(itemsPage);
          if (itemsPage.length < pageSize) break;
          page += 1;
          if (page > 1000) break;
        }
      }

      if (!allItems || allItems.length === 0) {
        setBatches([]);
        setBatchLabels({});
        setBatchMembers({});
        return;
      }

      // agrupa por batch_name + start_date + start_time
      const groups: Record<string, { count: number; start_date?: string; start_time?: string; batch_name: string; members: number[] }> = {};
      allItems.forEach((c: any) => {
        const bn = (c.batch_name ?? '').toString().trim() || '(sem turma)';
        const sd = c.start_date ?? c.batch_date ?? '';
        const st = c.start_time ?? c.batch_start_time ?? '';
        const key = `${bn}||${sd || ''}||${st || ''}`;
        groups[key] = groups[key] || { count: 0, start_date: sd, start_time: st, batch_name: bn, members: [] };
        groups[key].count++;

        const rawId = c.id ?? c.candidate_id ?? c.candidateId ?? c.candidate?.id ?? null;
        const memberId = rawId !== null && rawId !== undefined ? Number(rawId) : NaN;
        if (Number.isFinite(memberId)) groups[key].members.push(memberId);
      });

      const formatDateBRLocal = (iso?: string) => {
        if (!iso) return '';
        const p = String(iso).split('-');
        if (p.length !== 3) return iso;
        return `${p[2]}/${p[1]}/${p[0]}`;
      };

      const processed = Object.entries(groups).map(([key, v]) => {
        const displayParts = [v.batch_name];
        const dateBR = v.start_date ? formatDateBRLocal(v.start_date) : '';
        if (dateBR) displayParts.push(dateBR);
        if (v.start_time) displayParts.push(v.start_time);
        const display = displayParts.join(' • ');
        return { key, display, count: v.count, members: Array.from(new Set(v.members)), start_date: v.start_date, start_time: v.start_time };
      });

      // helpers de ordenação (flexível)
      const parseDateTimeToTs = (dateStr?: string, timeStr?: string) => {
        if (!dateStr) return Number.POSITIVE_INFINITY;
        let iso = '';
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
          iso = dateStr;
        } else if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
          const [d, m, y] = dateStr.split('/');
          iso = `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
        } else {
          iso = dateStr;
        }
        const timePart = timeStr && /\d{1,2}:\d{2}/.test(timeStr) ? timeStr : '00:00';
        const ts = Date.parse(`${iso}T${timePart}:00`);
        if (Number.isFinite(ts)) return ts;
        const alt = Date.parse(`${dateStr} ${timeStr || ''}`);
        return Number.isFinite(alt) ? alt : Number.POSITIVE_INFINITY;
      };

      const extractTurmaNumber = (s: string) => {
        if (!s) return Number.POSITIVE_INFINITY;
        const m = s.match(/turma\s*#?\s*0*([0-9]+)/i) || s.match(/#\s*0*([0-9]+)/i);
        if (m && m[1]) return Number(m[1]);
        return Number.POSITIVE_INFINITY;
      };

      // ordenação robusta
      processed.sort((a, b) => {
        const tsa = parseDateTimeToTs(a.start_date, a.start_time);
        const tsb = parseDateTimeToTs(b.start_date, b.start_time);
        if (tsa !== tsb) return tsa - tsb;

        const na = extractTurmaNumber(a.display || a.key || '');
        const nb = extractTurmaNumber(b.display || b.key || '');
        if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) return na - nb;
        if (Number.isFinite(na) && !Number.isFinite(nb)) return -1;
        if (!Number.isFinite(na) && Number.isFinite(nb)) return 1;

        return (a.display || '').localeCompare(b.display || '', undefined, { numeric: true });
      });

      setBatches(processed.map(p => p.key));
      setBatchLabels(Object.fromEntries(processed.map(p => [p.key, `${p.display}${p.count ? ' (' + p.count + ')' : ''}`])));
      setBatchMembers(Object.fromEntries(processed.map(p => [p.key, p.members])));
      if (processed.length > 0) setBatchFilter(prev => prev || processed[0].key);
    } catch (e) {
      console.error('Erro ao construir batches a partir de candidates/by-event', e);
      setBatches([]);
      setBatchLabels({});
      setBatchMembers({});
    }
  };

  // Reconstrói batches a partir de uma lista parcial/total de candidatos
  
  const buildBatchesFromList = (allItems: any[]) => {
    const groups: Record<string, { count: number; members: number[]; batch_name: string; start_date?: string; start_time?: string }> = {};
    allItems.forEach((c: any) => {
      const bn = (c.batch_name ?? '').toString().trim() || '(sem turma)';
      const sd = c.start_date ?? c.batch_date ?? '';
      const st = c.start_time ?? c.batch_start_time ?? '';
      const key = `${bn}||${sd || ''}||${st || ''}`;
      groups[key] = groups[key] || { count: 0, members: [], batch_name: bn, start_date: sd, start_time: st };
      groups[key].count++;
      const rawId = c.id ?? c.candidate_id ?? c.candidateId ?? c.candidate?.id ?? null;
      const memberId = rawId !== null && rawId !== undefined ? Number(rawId) : NaN;
      if (Number.isFinite(memberId)) groups[key].members.push(memberId);
    });

    const processed = Object.entries(groups).map(([key, v]) => {
      const displayParts = [v.batch_name];
      if (v.start_date) {
        const p = String(v.start_date).split('-');
        if (p.length === 3) displayParts.push(`${p[2]}/${p[1]}/${p[0]}`);
        else displayParts.push(String(v.start_date));
      }
      if (v.start_time) displayParts.push(v.start_time || '');
      const display = displayParts.filter(Boolean).join(' • ');
      return { key, display, count: v.count, members: Array.from(new Set(v.members)), start_date: v.start_date, start_time: v.start_time };
    });

    // helpers de ordenação (flexível)
    const parseDateTimeToTs = (dateStr?: string, timeStr?: string) => {
      if (!dateStr) return Number.POSITIVE_INFINITY;
      let iso = '';
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        iso = dateStr;
      } else if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
        const [d, m, y] = dateStr.split('/');
        iso = `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
      } else {
        iso = dateStr;
      }
      const timePart = timeStr && /\d{1,2}:\d{2}/.test(timeStr) ? timeStr : '00:00';
      const ts = Date.parse(`${iso}T${timePart}:00`);
      if (Number.isFinite(ts)) return ts;
      const alt = Date.parse(`${dateStr} ${timeStr || ''}`);
      return Number.isFinite(alt) ? alt : Number.POSITIVE_INFINITY;
    };

    const extractTurmaNumber = (s: string) => {
      if (!s) return Number.POSITIVE_INFINITY;
      const m = s.match(/turma\s*#?\s*0*([0-9]+)/i) || s.match(/#\s*0*([0-9]+)/i);
      if (m && m[1]) return Number(m[1]);
      return Number.POSITIVE_INFINITY;
    };

    // ordenação robusta: data+hora asc, depois número da turma, depois display
    processed.sort((a, b) => {
      const tsa = parseDateTimeToTs(a.start_date, a.start_time);
      const tsb = parseDateTimeToTs(b.start_date, b.start_time);
      if (tsa !== tsb) return tsa - tsb;

      const na = extractTurmaNumber(a.display || a.key || '');
      const nb = extractTurmaNumber(b.display || b.key || '');
      if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) return na - nb;
      if (Number.isFinite(na) && !Number.isFinite(nb)) return -1;
      if (!Number.isFinite(na) && Number.isFinite(nb)) return 1;

      return (a.display || '').localeCompare(b.display || '', undefined, { numeric: true });
    });

    setBatches(processed.map(p => p.key));
    setBatchLabels(Object.fromEntries(processed.map(p => [p.key, `${p.display}${p.count? ' ('+p.count+')':''}`])));
    setBatchMembers(Object.fromEntries(processed.map(p => [p.key, p.members])));
    if (processed.length > 0) setBatchFilter(prev => prev || processed[0].key);
  };

  // Converte resultados numéricos para Attempts e atualiza executions incrementalmente
  // Substitua a versão anterior por esta (usa `candidates` para preencher candidate info)
  const mergeExecForCandidate = (candidateId: number, resultsArray: any[], maxAttempts: number) => {
    setExecutions(prev => {
      // procura o objeto do candidato nos candidates já carregados (pode ser parcial)
      const candidateObj = (candidates || []).find(c => Number(c.id) === Number(candidateId)) || { id: candidateId, full_name: '', cpf: '', registration_number: '' } as any;

      // monta attempts a partir dos resultsArray
      const attempts: AttemptData[] = [];
      for (let i = 1; i <= maxAttempts; i++) {
        const r = (resultsArray || []).find((x: any) => Number(x.attempt_number) === i);
        attempts.push({
          attempt_number: i,
          measured_value: r?.measured_value ?? null,
          is_valid: r?.is_valid ?? true,
          is_approved: r?.is_approved_in_exercise,
          result_id: r?.id ?? null
        });
      }

      // calcula best_value e overall_status (mesma regra que você já usa)
      const validAttempts = attempts.filter(a => a.measured_value !== null && a.is_valid);
      let best_value: number | undefined;
      let overall_status: 'approved' | 'failed' | 'pending' = 'pending';

      if (validAttempts.length > 0) {
        const isTime = exercise?.unit_of_measure?.toLowerCase().includes('tempo') ||
                      exercise?.unit_of_measure?.toLowerCase().includes('segundo');
        if (isTime) {
          best_value = Math.min(...validAttempts.map(a => a.measured_value!));
        } else {
          best_value = Math.max(...validAttempts.map(a => a.measured_value!));
        }
        const bestAttempt = validAttempts.find(a => a.measured_value === best_value);
        overall_status = bestAttempt?.is_approved ? 'approved' : 'failed';
      }

      const newExec: CandidateExecution = {
        candidate: candidateObj,
        attempts,
        best_value,
        overall_status
      };

      // se já existe, substitui; se não, adiciona mas tenta manter ordem por candidates (melhora UX)
      const idx = prev.findIndex(p => Number(p.candidate.id) === Number(candidateId));
      if (idx >= 0) {
        const copy = prev.slice();
        copy[idx] = newExec;
        return copy;
      }

      // insere novo no final — depois podemos reordenar para acompanhar `candidates`
      return [...prev, newExec];
    });
  };

  // Garante que o merge use o objeto de candidato fornecido (se houver)
  // candidateObj pode ser null, aí a função tenta buscar no state `candidates`.
  const mergeExecForCandidateWithObj = (candidateObj: any | null, candidateId: number, resultsArray: any[], maxAttempts: number) => {
    // Preferir o objeto fornecido; fallback para procurar em `candidates`
    const candidateData = candidateObj || (candidates || []).find(c => Number(c.id) === Number(candidateId)) || { id: candidateId, full_name: '', cpf: '', registration_number: '', batch_name: undefined, batch_number: undefined, start_time: null, start_date: null };

    // monta attempts a partir dos resultsArray (mesma lógica do mergeExecForCandidate)
    const attempts: AttemptData[] = [];
    for (let i = 1; i <= maxAttempts; i++) {
      const r = (resultsArray || []).find((x: any) => Number(x.attempt_number) === i);
      attempts.push({
        attempt_number: i,
        measured_value: r?.measured_value ?? null,
        is_valid: r?.is_valid ?? true,
        is_approved: r?.is_approved_in_exercise,
        result_id: r?.id ?? null
      });
    }

    // calcula best_value e overall_status (mesma regra)
    const validAttempts = attempts.filter(a => a.measured_value !== null && a.is_valid);
    let best_value: number | undefined;
    let overall_status: 'approved' | 'failed' | 'pending' = 'pending';

    if (validAttempts.length > 0) {
      const isTime = exercise?.unit_of_measure?.toLowerCase().includes('tempo') ||
                      exercise?.unit_of_measure?.toLowerCase().includes('segundo');
      if (isTime) {
        best_value = Math.min(...validAttempts.map(a => a.measured_value!));
      } else {
        best_value = Math.max(...validAttempts.map(a => a.measured_value!));
      }
      const bestAttempt = validAttempts.find(a => a.measured_value === best_value);
      overall_status = bestAttempt?.is_approved ? 'approved' : 'failed';
    }

    const newExec: CandidateExecution = {
      candidate: candidateData,
      attempts,
      best_value,
      overall_status
    };

    setExecutions(prev => {
      const idx = prev.findIndex(p => Number(p.candidate.id) === Number(candidateId));
      if (idx >= 0) {
        const copy = prev.slice();
        copy[idx] = newExec;
        return copy;
      }
      return [...prev, newExec];
    });
  };

  // Busca resultados para um chunk (array) de candidatos com limite de concorrência (chunks simples)
  
  const fetchResultsForCandidatesBulk = async (candidatesChunk: any[], maxAttempts: number) => {
    const ids = (candidatesChunk || []).map(c => Number(c.id ?? c.candidate_id)).filter(n => Number.isFinite(n));
    if (!ids || ids.length === 0) return;

    try {
      const MAX_IDS_PER_REQUEST = 200;
      for (let i = 0; i < ids.length; i += MAX_IDS_PER_REQUEST) {
        const batchIds = ids.slice(i, i + MAX_IDS_PER_REQUEST);

        const resp = await api.post('/taf/execution/results/bulk', {
          exercise_id: Number(exerciseId),
          candidate_ids: batchIds
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });

        const grouped = resp.data?.results || {};

        // Para cada id do batch, procuramos também o objeto de candidato na lista da página (candidatesChunk)
        for (const cid of batchIds) {
          // encontrar candidateObj na página atual (candidatesChunk)
          const candidateObj = (candidatesChunk || []).find((c: any) => {
            const idVal = Number(c.id ?? c.candidate_id ?? c.candidate?.id);
            return Number(idVal) === Number(cid);
          }) || null;

          const arr = grouped[String(cid)] || grouped[cid] || [];
          // use a nova função que recebe o candidate object para garantir full_name, cpf etc.
          mergeExecForCandidateWithObj(candidateObj, Number(cid), arr, maxAttempts);
        }
      }
    } catch (err) {
      console.warn('fetchResultsForCandidatesBulk: erro no bulk, fallback não implementado', err);
      // opcional: implementar fallback para chamadas individuais aqui se desejar
    }
  };

  // Faz paginação e processa por página, atualizando candidates/batches/executions incrementalmente
  const nextPageRef = useRef<number>(1);
  const hasMoreRef = useRef<boolean>(true);
  const [loadingMore, setLoadingMore] = useState(false);

  const fetchAndProcessCandidatesIncremental = async (evtId: string | undefined, maxAttempts: number, pagesToFetch = 1) => {
    // pagesToFetch: quantas páginas buscar antes de retornar (padrão 1)
    if (!evtId || !hasMoreRef.current) return;
    const pageSize = 1999; // ajuste conforme necessário
    let fetched = 0;

    // inicializa accumulatedCandidates a partir do state current (pode estar vazio)
    let accumulatedCandidates: any[] = Array.isArray(candidates) ? [...candidates] : [];

    try {
      setLoading(true);
      while (fetched < pagesToFetch && hasMoreRef.current) {
        const page = nextPageRef.current;
        const r = await api.get(`/taf/candidates/by-event/${evtId}`, {
          params: { page, page_size: pageSize },
          headers: { Authorization: `Bearer ${token}` }
        });
        const items = r.data?.items || (Array.isArray(r.data) ? r.data : []);
        if (!items || items.length === 0) {
          hasMoreRef.current = false;
          break;
        }

        // append to accumulatedCandidates and update immediate UI
        accumulatedCandidates = accumulatedCandidates.concat(items);
        setCandidates([...accumulatedCandidates]);

        // rebuild batches for accumulated items using accumulatedCandidates
        buildBatchesFromList(accumulatedCandidates);

        // fetch results for this page using bulk (much faster than N calls)
        await fetchResultsForCandidatesBulk(items, maxAttempts);

        // update refs
        nextPageRef.current = page + 1;
        fetched += 1;

        // If fewer items than pageSize, no more pages
        if (items.length < pageSize) {
          hasMoreRef.current = false;
          break;
        }
      }
    } finally {
      // show UI as soon as we have at least one page
      if ((candidates && candidates.length) || nextPageRef.current > 2 || accumulatedCandidates.length > 0) {
        setLoading(false);
      }
    }
  };


  // Função pública para carregar a próxima página (chame de um botão ou automaticamente)
  const loadMoreCandidates = async (maxAttempts: number) => {
    if (!hasMoreRef.current || loadingMore) return;
    setLoadingMore(true);
    try {
      // carrega 1 página a mais quando o usuário pedir
      await fetchAndProcessCandidatesIncremental(eventId, maxAttempts, 1);
    } finally {
      setLoadingMore(false);
    }
  };



  const loadExistingResults = async (candidatesData: Candidate[], maxAttempts: number) => {
    try {
      const executionsData: CandidateExecution[] = [];

      for (const candidate of candidatesData) {
        // Busca resultados do candidato neste exercício
        try {
          const resultsResponse = await api.get(`/taf/execution/candidate/${candidate.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });

          const candidateResults = (resultsResponse.data || []).filter(
            (r: any) => r.exercise_id === Number(exerciseId)
          );

          // Cria array de tentativas
          const attempts: AttemptData[] = [];
          for (let i = 1; i <= maxAttempts; i++) {
            const existingResult = candidateResults.find((r: any) => r.attempt_number === i);
            attempts.push({
              attempt_number: i,
              measured_value: existingResult?.measured_value ?? null,
              is_valid: existingResult?.is_valid ?? true,
              is_approved: existingResult?.is_approved_in_exercise,
              // Guardamos o id do resultado para permitir update em vez de criação
              result_id: existingResult?.id ?? null
            });
          }

          // Calcula melhor resultado e status
          const validAttempts = attempts.filter(a => a.measured_value !== null && a.is_valid);
          let best_value: number | undefined;
          let overall_status: 'approved' | 'failed' | 'pending' = 'pending';

          if (validAttempts.length > 0) {
            // Para tempo: menor é melhor. Para repetições/distância: maior é melhor
            const isTime = exercise?.unit_of_measure.toLowerCase().includes('tempo') ||
                          exercise?.unit_of_measure.toLowerCase().includes('segundo');
            
            if (isTime) {
              best_value = Math.min(...validAttempts.map(a => a.measured_value!));
            } else {
              best_value = Math.max(...validAttempts.map(a => a.measured_value!));
            }

            // Verifica aprovação
            const bestAttempt = validAttempts.find(a => a.measured_value === best_value);
            overall_status = bestAttempt?.is_approved ? 'approved' : 'failed';
          }

          executionsData.push({
            candidate,
            attempts,
            best_value,
            overall_status
          });
        } catch (err) {
          // Se falhar ao buscar resultados de um candidato, adiciona com tentativas vazias
          const attempts: AttemptData[] = [];
          for (let i = 1; i <= maxAttempts; i++) {
            attempts.push({
              attempt_number: i,
              measured_value: null,
              is_valid: true,
              result_id: null
            });
          }
          executionsData.push({
            candidate,
            attempts,
            overall_status: 'pending'
          });
        }
      }

      setExecutions(executionsData);

      // guarda snapshot original para comparação futura (deep copy)
      try {
        originalExecutionsRef.current = JSON.parse(JSON.stringify(executionsData));
      } catch {
        // fallback raso
        originalExecutionsRef.current = executionsData.map(e => ({ ...e }));
      }
      setHasChanges(false);
    } catch (err) {
      console.error('Erro ao carregar resultados:', err);
    }
  };

  const checkApproval = (value: number, gender: 'M' | 'F'): boolean => {
    const criterion = criteria.find(c => c.gender === gender);
    if (!criterion) return false;

    const isTime = exercise?.unit_of_measure.toLowerCase().includes('tempo') ||
                  exercise?.unit_of_measure.toLowerCase().includes('segundo');

    if (isTime) {
      // Para tempo: deve ser <= max_time ou <= min_value
      return criterion.max_time_s ? value <= criterion.max_time_s : value <= criterion.min_value;
    } else {
      // Para repetições/distância: deve ser >= min_value
      return value >= criterion.min_value;
    }
  };

  const handleValueChange = (candidateId: number, attemptNumber: number, value: string) => {
    setExecutions(prev => {
      const next = prev.map(exec => {
        if (exec.candidate.id === candidateId) {
          const newAttempts = exec.attempts.map(att => {
            if (att.attempt_number === attemptNumber) {
              const numValue = value === '' ? null : parseFloat(value);
              const is_approved = numValue !== null ? checkApproval(numValue, exec.candidate.gender) : undefined;
              return { ...att, measured_value: numValue, is_approved };
            }
            return att;
          });

          // Recalcula melhor resultado
          const validAttempts = newAttempts.filter(a => a.measured_value !== null && a.is_valid);
          let best_value: number | undefined;
          let overall_status: 'approved' | 'failed' | 'pending' = 'pending';

          if (validAttempts.length > 0) {
            const isTime = exercise?.unit_of_measure.toLowerCase().includes('tempo') ||
                          exercise?.unit_of_measure.toLowerCase().includes('segundo');
            
            if (isTime) {
              best_value = Math.min(...validAttempts.map(a => a.measured_value!));
            } else {
              best_value = Math.max(...validAttempts.map(a => a.measured_value!));
            }

            const bestAttempt = validAttempts.find(a => a.measured_value === best_value);
            overall_status = bestAttempt?.is_approved ? 'approved' : 'failed';
          }

          return { ...exec, attempts: newAttempts, best_value, overall_status };
        }
        return exec;
      });

      // mark that there are changes
      setHasChanges(true);
      return next;
    });
  };

  const handleValidToggle = (candidateId: number, attemptNumber: number) => {
    setExecutions(prev => {
      const next = prev.map(exec => {
        if (exec.candidate.id === candidateId) {
          const newAttempts = exec.attempts.map(att => {
            if (att.attempt_number === attemptNumber) {
              return { ...att, is_valid: !att.is_valid };
            }
            return att;
          });
          // recalc best/status
          const validAttempts = newAttempts.filter(a => a.measured_value !== null && a.is_valid);
          let best_value: number | undefined;
          let overall_status: 'approved' | 'failed' | 'pending' = 'pending';

          if (validAttempts.length > 0) {
            const isTime = exercise?.unit_of_measure.toLowerCase().includes('tempo') ||
                          exercise?.unit_of_measure.toLowerCase().includes('segundo');
            
            if (isTime) {
              best_value = Math.min(...validAttempts.map(a => a.measured_value!));
            } else {
              best_value = Math.max(...validAttempts.map(a => a.measured_value!));
            }

            const bestAttempt = validAttempts.find(a => a.measured_value === best_value);
            overall_status = bestAttempt?.is_approved ? 'approved' : 'failed';
          }

          return { ...exec, attempts: newAttempts, best_value, overall_status };
        }
        return exec;
      });

      setHasChanges(true);
      return next;
    });
  };

  // monta somente as mudanças pontuais comparando com snapshot original
  const buildChangedResults = () => {
    const changed: any[] = [];
    const origAll = originalExecutionsRef.current || [];

    // Map original for faster access
    const origMap = new Map<number, CandidateExecution>();
    for (const oe of origAll) {
      origMap.set(oe.candidate.id, oe);
    }

    for (const exec of executions) {
      const origExec = origMap.get(exec.candidate.id);
      for (const att of exec.attempts) {
        const origAtt = origExec?.attempts?.find(a => a.attempt_number === att.attempt_number);
        const measuredDiff = (origAtt?.measured_value ?? null) !== (att.measured_value ?? null);
        const validDiff = (origAtt?.is_valid ?? true) !== (att.is_valid ?? true);

        // if there was no original attempt record (origAtt may be undefined) and new value is present -> create
        if (!origAtt) {
          if (att.measured_value !== null && att.measured_value !== undefined) {
            const row: any = {
              candidate_id: exec.candidate.id,
              exercise_id: Number(exerciseId),
              measured_value: att.measured_value,
              attempt_number: att.attempt_number,
              is_valid: att.is_valid ?? true,
              evaluator_user_id: user?.id ?? null
            };
            changed.push(row);
          }
        } else {
          // existing result: check if any relevant field changed
          if (measuredDiff || validDiff) {
            const row: any = {
              id: origAtt.result_id ?? undefined,
              candidate_id: exec.candidate.id,
              exercise_id: Number(exerciseId),
              measured_value: att.measured_value,
              attempt_number: att.attempt_number,
              is_valid: att.is_valid ?? true,
              evaluator_user_id: user?.id ?? null
            };
            // Only include id if we have it; backend will update by id
            if (!row.id) delete row.id;
            changed.push(row);
          }
        }
      }
    }

    return changed;
  };

  const handleSaveAll = async () => {
    setSaving(true);
    setError(null);

    try {
      const resultsToSave = buildChangedResults();
      if (!resultsToSave || resultsToSave.length === 0) {
        setError('Nenhuma alteração para salvar');
        setSaving(false);
        return;
      }

      // Envia somente as mudanças
      const resp = await api.post('/taf/execution/bulk', {
        results: resultsToSave
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Recarrega dados do servidor para garantir consistência e capturar novos ids
      if (exercise) {
        await loadExistingResults(candidates, exercise.max_attempts);
      }

      setSuccess(`${(resp?.data?.updated_results?.length ?? resultsToSave.length)} alteração(ões) salvas com sucesso!`);
      setTimeout(() => setSuccess(null), 3000);
      setHasChanges(false);
    } catch (err: any) {
      console.error('Erro ao salvar resultados:', err);
      setError(String(err?.response?.data?.detail || 'Erro ao salvar resultados'));
    } finally {
      setSaving(false);
    }
  };

  
  // agora com filtro por nome / número (candidateFilter) em vez de genderFilter
  const filteredExecutions = executions.filter(exec => {
    // filtro por turma (mantém comportamento anterior)
    if (batchFilter) {
      if (batchFilter.includes('||')) {
        const membersRaw = batchMembers[batchFilter] || [];
        const members = (membersRaw || []).map(m => Number(m)).filter(n => Number.isFinite(n));
        if (members.length > 0) {
          if (!members.includes(Number(exec.candidate.id))) return false;
        } else {
          if (exec.candidate.batch_name !== (batchFilter.split('||')[0] || '')) return false;
        }
      } else {
        if (exec.candidate.batch_name !== batchFilter) return false;
      }
    }

    // novo filtro por nome / número (substitui filtro por sexo)
    if (candidateFilter && String(candidateFilter).trim() !== '') {
      const q = String(candidateFilter).trim().toLowerCase();

      // candidate number cru (batch_number ou registration_number)
      const rawNumber = String(exec.candidate.batch_number ?? exec.candidate.registration_number ?? '');
      // padded: usa total de candidatos para padding (ajuste se preferir outro total)
      const paddingTotal = candidates.length || executions.length || 0;
      const padded = String(padNumberByTotal(rawNumber, paddingTotal)).toLowerCase();

      const fullName = String(exec.candidate.full_name ?? '').toLowerCase();

      if (!fullName.includes(q) && !String(rawNumber).toLowerCase().includes(q) && !padded.includes(q)) {
        return false;
      }
    }

    return true;
  });

  const totalForPadding = candidates.length || filteredExecutions.length || 0;

  const getStatusColor = (status?: 'approved' | 'failed' | 'pending') => {
    switch (status) {
      case 'approved': return 'success';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  const getStatusLabel = (status?: 'approved' | 'failed' | 'pending') => {
    switch (status) {
      case 'approved': return 'Aprovado';
      case 'failed': return 'Reprovado';
      default: return 'Pendente';
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
              <FitnessCenter sx={{ verticalAlign: 'middle', mr: 1 }} /> Lançamento de Resultados
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {eventName ? `Evento: ${eventName}` : 'Carregando...'}
              {exercise && ` • Exercício: ${exercise.name}`}
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

      {/* Conteúdo */}
      {!loading && exercise && (
        <>
          {/* Filtros */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Stack direction="row" spacing={2}>
              <TextField
                select
                label="Turma"
                value={batchFilter}
                onChange={(e) => setBatchFilter(e.target.value)}
                sx={{ minWidth: 200 }}
              >
                <MenuItem value="">Todas</MenuItem>
                {batches.map(key => (
                  <MenuItem key={key} value={key}>
                    {batchLabels[key] ?? key}
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                label="Buscar por número ou nome"
                value={candidateFilter}
                onChange={(e) => setCandidateFilter(e.target.value)}
                placeholder="Ex: 010 ou Silva"
                sx={{ minWidth: 300 }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      {/* opcional: ícone de busca */}
                    </InputAdornment>
                  )
                }}
              />

              <Box sx={{ flex: 1 }} />

              <Button
                variant="contained"
                size="large"
                startIcon={saving ? <CircularProgress size={20} /> : <Save />}
                onClick={handleSaveAll}
                disabled={saving || !hasChanges}
              >
                {saving ? 'Salvando...' : 'Salvar Todos'}
              </Button>
            </Stack>
          </Paper>

          {/* Tabela de Lançamento */}
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell>
                  <TableCell>Candidato</TableCell>
                  <TableCell>CPF</TableCell>
                  <TableCell>Inscrição</TableCell>
                  <TableCell>Turma</TableCell>
                  {Array.from({ length: exercise.max_attempts }, (_, i) => (
                    <React.Fragment key={i}>
                      <TableCell align="center">{i + 1}ª Tentativa</TableCell>
                      <TableCell align="center">?</TableCell>
                    </React.Fragment>
                  ))}
                  <TableCell align="center">Melhor</TableCell>
                  <TableCell align="center">Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredExecutions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6 + (exercise.max_attempts * 2)} align="center" sx={{ py: 4 }}>
                      <Typography variant="body2" color="text.secondary">
                        Nenhum candidato encontrado com os filtros aplicados
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredExecutions.map((exec, index) => {
                    const rawNumber = exec.candidate.batch_number ?? exec.candidate.registration_number ?? (index + 1);
                    const rawStr = String(rawNumber ?? (index + 1));
                    const minDigits = 3;
                    const visibleCount = filteredExecutions.length || 0;
                    const width = Math.max(minDigits, String(visibleCount).length);
                    const displayNumber = rawStr.padStart(width, '0');

                    // build turma display: batch_name + optional batch_number + start_time + start_date
                    const bn = exec.candidate.batch_number ? `#${String(exec.candidate.batch_number).toString().padStart(3, '0')}` : '';
                    const stime = exec.candidate.start_time ? exec.candidate.start_time : '';
                    const sdate = exec.candidate.start_date ? formatDateBR(exec.candidate.start_date) : '';

                    return (
                      <TableRow
                        key={exec.candidate.id}
                        sx={{
                          bgcolor: exec.overall_status === 'approved' ? 'success.50' :
                                  exec.overall_status === 'failed' ? 'error.50' : 'transparent'
                        }}
                      >
                        <TableCell>{displayNumber}</TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight={600}>
                            {exec.candidate.full_name}
                          </Typography>
                          <Chip
                            label={exec.candidate.gender === 'M' ? 'Masculino' : 'Feminino'}
                            size="small"
                            color={exec.candidate.gender === 'M' ? 'primary' : 'secondary'}
                            sx={{ mt: 0.5 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                            {exec.candidate.cpf}
                          </Typography>
                        </TableCell>
                        <TableCell>{exec.candidate.registration_number}</TableCell>
                        <TableCell>
                          {exec.candidate.batch_name ? (
                            <Box>
                              <Typography variant="body2" fontWeight={600}>
                                {exec.candidate.batch_name} {bn ? <Typography component="span" sx={{ fontWeight: 600, ml: 1 }}>{bn}</Typography> : null}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {stime ? `• ${stime}` : ''} {sdate ? `• ${sdate}` : ''}
                              </Typography>
                            </Box>
                          ) : '-'}
                        </TableCell>

                        {exec.attempts.map((attempt) => (
                          <React.Fragment key={attempt.attempt_number}>
                            <TableCell>
                              <TextField
                                type="number"
                                size="small"
                                value={attempt.measured_value ?? ''}
                                onChange={(e) => handleValueChange(exec.candidate.id, attempt.attempt_number, e.target.value)}
                                sx={{ width: 100 }}
                                placeholder={attempt.measured_value == null ? exercise.unit_of_measure.split(' ')[0] : undefined}
                                InputProps={{
                                  endAdornment: attempt.measured_value == null ? (
                                    <InputAdornment position="end">
                                      <Typography variant="caption" color="text.secondary">
                                        {exercise.unit_of_measure.split(' ')[0]}
                                      </Typography>
                                    </InputAdornment>
                                  ) : undefined
                                }}
                              />
                            </TableCell>
                            <TableCell align="center">
                              <Checkbox
                                checked={attempt.is_valid}
                                onChange={() => handleValidToggle(exec.candidate.id, attempt.attempt_number)}
                                disabled={attempt.measured_value === null}
                              />
                            </TableCell>
                          </React.Fragment>
                        ))}

                        <TableCell align="center">
                          {exec.best_value !== undefined && (
                            <Chip
                              label={`${exec.best_value} ${exercise.unit_of_measure}`}
                              color={exec.overall_status === 'approved' ? 'success' : 'error'}
                              size="small"
                            />
                          )}
                        </TableCell>

                        <TableCell align="center">
                          <Chip
                            icon={exec.overall_status === 'approved' ? <CheckCircle /> :
                                  exec.overall_status === 'failed' ? <Cancel /> : <Timer />}
                            label={getStatusLabel(exec.overall_status)}
                            color={getStatusColor(exec.overall_status)}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Container>
  );
}
