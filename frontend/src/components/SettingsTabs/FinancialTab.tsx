import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box, Paper, Typography, Stack, Button, TextField, MenuItem, Table, TableHead,
  TableRow, TableCell, TableBody, IconButton, Divider, Alert, CircularProgress,
  Chip, Select, InputLabel, FormControl, Checkbox, FormControlLabel, LinearProgress,
  Grid, InputAdornment
} from '@mui/material';
import { Delete, Add } from '@mui/icons-material';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import * as XLSX from 'xlsx';

type RoleItem = { value: string | number; label: string };
const ROLES: RoleItem[] = [
  { value: 1, label: 'Administrador Geral' },
  { value: 2, label: 'Coordenador Geral' },
  { value: 3, label: 'Coordenador de Educação Física' },
  { value: 4, label: 'Avaliador de Educação Física' },
  { value: 5, label: 'Apoio' },
  { value: 6, label: 'Técnico de AudioVisual' },
  { value: 7, label: 'Volantes' },
  { value: 8, label: 'Fiscais' },
  { value: 'other', label: 'Outros' },
];

type Entry = {
  id: string;
  role: string | number;
  amount: number;
  days: number;
  quantity: number;
  event_id?: number | null;
  event_name?: string;
  notes?: string;
  participantId?: string | number | null;
  participantName?: string | null;
};

type EventItem = { id: number; name: string; date_start?: string | null; date_end?: string | null };

// localStorage key
const ROLE_VALUES_KEY = 'financial_role_values_v1';

export default function FinancialTab() {
  const { token } = useAuth();
  const cfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
  const isDev = typeof import.meta !== "undefined" && !!(import.meta as any).env?.DEV;

  // state
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [selectedEventId, setSelectedEventId] = useState<number | undefined>(undefined);

  const [eventUsersMap, setEventUsersMap] = useState<Record<number, any[]>>({});
  const [attendancesMap, setAttendancesMap] = useState<Record<number, any[]>>({});

  // attendance days caches: per event -> { workerId: daysCount } and { userId: daysCount }
  const [attendanceDaysByWorker, setAttendanceDaysByWorker] = useState<Record<string, Record<string, number>>>({});
  const [attendanceDaysByUser, setAttendanceDaysByUser] = useState<Record<string, Record<string, number>>>({});

  const [roleValues, setRoleValues] = useState<Record<string, number>>({});
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState<Omit<Entry, 'id'>>({
    role: 2,
    amount: 0,
    days: 1,
    quantity: 1,
    event_id: undefined,
    event_name: '',
    notes: '',
  });

  // auto generation UI controls
  const [autoOnlyPresent, setAutoOnlyPresent] = useState(true);
  const [autoRoleFilter, setAutoRoleFilter] = useState<string | 'all'>('all');
  const [useRoleValuesForAuto, setUseRoleValuesForAuto] = useState(true);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generateProgress, setGenerateProgress] = useState({ current: 0, total: 0 });

  // export options
  const [groupBeforeExport, setGroupBeforeExport] = useState(true);

  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // refs
  const mountedRef = useRef(true);
  const fetchingUsersRef = useRef<Record<number, boolean>>({});
  const fetchingAttendancesRef = useRef<Record<number, boolean>>({});
  const fetchedEventsRef = useRef<boolean>(false);

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, []);

  // load saved role values
  useEffect(() => {
    try {
      const raw = localStorage.getItem(ROLE_VALUES_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
          setRoleValues(parsed);
          return;
        }
      }
    } catch (e) {
      if (isDev) console.debug('Failed to load roleValues', e);
    }
    // init defaults
    const init: Record<string, number> = {};
    ROLES.forEach(r => init[String(r.value)] = 0);
    setRoleValues(init);
  }, []);

  function saveRoleValuesLocal() {
    try {
      localStorage.setItem(ROLE_VALUES_KEY, JSON.stringify(roleValues));
      setMessage('Valores por função salvos localmente.');
      setTimeout(() => setMessage(null), 2000);
    } catch (e) {
      setError('Erro ao salvar valores localmente.');
    }
  }

  function resetRoleValuesLocal() {
    const init: Record<string, number> = {};
    ROLES.forEach(r => init[String(r.value)] = 0);
    setRoleValues(init);
    localStorage.removeItem(ROLE_VALUES_KEY);
    setMessage('Valores restaurados para padrão.');
    setTimeout(() => setMessage(null), 2000);
  }

  // prefill draft.amount when role changes
  useEffect(() => {
    const key = String(draft.role);
    const v = roleValues?.[key];
    if (v !== undefined && v !== null) setDraft(prev => ({ ...prev, amount: Number(v) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.role, roleValues]);

  // load events (safe candidates)
  useEffect(() => {
    setLoadingEvents(true);
    async function load() {
      if (fetchedEventsRef.current) { setLoadingEvents(false); return; }
      const candidates = [
        '/taf/events?is_active=true&page=1&page_size=100',
        '/taf/events?page=1&page_size=100',
        '/api/v1/taf/events?is_active=true&page=1&page_size=100',
        '/api/v1/taf/events?page=1&page_size=100',
        '/events?is_active=true&page=1&page_size=100',
        '/events?page=1&page_size=100',
      ];
      for (const p of candidates) {
        try {
          const res = await api.get(p, cfg);
          if (!mountedRef.current) return;
          const data = res?.data ?? res;
          let list: any[] = [];
          if (Array.isArray(data)) list = data;
          else if (Array.isArray(data.items)) list = data.items;
          else if (Array.isArray(data.events)) list = data.events;
          if (Array.isArray(list) && list.length > 0) {
            const mapped = list.map((it: any) => ({ id: Number(it.id), name: it.name ?? it.title ?? String(it.id), date_start: it.date_start ?? null, date_end: it.date_end ?? null }));
            setEvents(mapped);
            fetchedEventsRef.current = true;
            setLoadingEvents(false);
            return;
          }
        } catch (err: any) {
          if (err?.response?.status === 401 || err?.response?.status === 403) {
            setError('Acesso negado ao buscar eventos.');
            setLoadingEvents(false);
            return;
          }
          if (isDev) console.debug('fetch events candidate failed', p, err?.message ?? err);
          continue;
        }
      }
      setError('Não foi possível localizar o endpoint de eventos.');
      setLoadingEvents(false);
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // helper to create a stable unique key per participant object
  const participantKey = (u: any) => {
    const prefix = String(u._source ?? 'u');
    const id = String(u.event_worker_id ?? u.user_id ?? u.id ?? '');
    return `${prefix}-${id}`;
  };

  // fetch and merge users/participants for event (read-only here)
  async function fetchUsersForEvent(eventId?: number, { force = false } = {}) {
    if (!eventId || Number.isNaN(Number(eventId))) return;
    const evId = Number(eventId);
    if (fetchingUsersRef.current[evId]) return;
    if (!force && eventUsersMap[evId] && eventUsersMap[evId].length > 0) return;
    fetchingUsersRef.current[evId] = true;

    const userPaths = [
      `/taf/events/${evId}/users`,
      `/api/v1/taf/events/${evId}/users`,
      `/events/${evId}/users`,
      `/event/${evId}/users`,
    ];
    const partPaths = [
      `/taf/events/${evId}/participants`,
      `/api/v1/taf/events/${evId}/participants`,
      `/events/${evId}/participants`,
      `/event/${evId}/participants`,
      `/event/${evId}/workers`,
      `/taf/events/${evId}/workers`,
    ];

    async function tryFirst(paths: string[]) {
      for (const p of paths) {
        try { return await api.get(p, cfg); } catch { continue; }
      }
      return { data: [] };
    }

    try {
      const [rUsers, rParts] = await Promise.all([tryFirst(userPaths), tryFirst(partPaths)]);
      if (!mountedRef.current) return;
      const usersFromExercises: any[] = Array.isArray(rUsers.data) ? rUsers.data : (Array.isArray(rUsers.data?.items) ? rUsers.data.items : []);
      const participants: any[] = Array.isArray(rParts.data) ? rParts.data : (Array.isArray(rParts.data?.items) ? rParts.data.items : []);

      const byUserId: Record<string, any> = {};
      usersFromExercises.forEach(u => { if (u && (u.id ?? u.user_id)) byUserId[String(u.id ?? u.user_id)] = { ...u, _source: 'exercise' }; });

      const merged: any[] = [];
      participants.forEach(p => {
        const key = String(p.user_id ?? p.id ?? '');
        if (p.user_id && byUserId[key]) {
          merged.push({ ...byUserId[key], ...p, _source: 'participant' });
          delete byUserId[key];
        } else merged.push({ ...p, _source: 'participant' });
      });
      Object.values(byUserId).forEach(v => merged.push(v));

      setEventUsersMap(prev => ({ ...prev, [evId]: merged }));
    } catch (err) {
      if (isDev) console.error('fetchUsersForEvent', err);
      setEventUsersMap(prev => ({ ...prev, [evId]: [] }));
    } finally {
      fetchingUsersRef.current[evId] = false;
      // also try attendances after users
      fetchAttendancesForEvent(evId).catch(() => {});
    }
  }

  // fetch attendances to detect who is present and which dates
  async function fetchAttendancesForEvent(eventId?: number, { force = false } = {}) {
    if (!eventId || Number.isNaN(Number(eventId))) return;
    const evId = Number(eventId);
    if (fetchingAttendancesRef.current[evId]) return;
    if (!force && attendancesMap[evId] && attendancesMap[evId].length > 0) return;
    fetchingAttendancesRef.current[evId] = true;

    const paths = [
      `/event/${evId}/attendance`,
      `/events/${evId}/attendance`,
      `/api/v1/event/${evId}/attendance`,
      `/api/v1/events/${evId}/attendance`,
    ];
    async function tryFirst(paths: string[]) {
      for (const p of paths) {
        try { return await api.get(p, cfg); } catch { continue; }
      }
      return { data: [] };
    }

    try {
      const res = await tryFirst(paths);
      if (!mountedRef.current) return;
      const list = Array.isArray(res.data) ? res.data : (Array.isArray(res.data?.items) ? res.data.items : []);
      setAttendancesMap(prev => {
        const next = { ...prev, [evId]: list };
        return next;
      });
      // build days maps from attendance rows
      buildAttendanceDaysMaps(evId);
    } catch (err) {
      if (isDev) console.error('fetchAttendancesForEvent', err);
      setAttendancesMap(prev => ({ ...prev, [evId]: [] }));
    } finally {
      fetchingAttendancesRef.current[evId] = false;
    }
  }

  // helpers for presence and attended days detection (robust)
  function normalizeDateKey(raw: any): string | null {
    if (!raw) return null;
    try {
      if (raw instanceof Date) return raw.toISOString().slice(0, 10);
      const s = String(raw);
      const d = new Date(s);
      if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10);
      const parts = s.split(/[T\s]/);
      if (parts[0] && parts[0].length >= 8) return parts[0];
      return null;
    } catch {
      return null;
    }
  }

  function extractDatesFromRecord(rec: any): string[] {
    const dates: string[] = [];
    if (!rec) return dates;

    const cand = [rec.attendance_date, rec.check_in_at, rec.check_out_at, rec.created_at, rec.date, rec.att_date];
    for (const c of cand) {
      const k = normalizeDateKey(c);
      if (k) dates.push(k);
    }

    if (typeof rec === 'string') {
      const k = normalizeDateKey(rec);
      if (k) dates.push(k);
    }

    const tryArray = (arr: any) => {
      if (!Array.isArray(arr)) return;
      for (const it of arr) {
        if (!it) continue;
        const k = normalizeDateKey(it.attendance_date ?? it.check_in_at ?? it.created_at ?? it.date);
        if (k) dates.push(k);
        if (Array.isArray(it.event_worker_attendance)) {
          tryArray(it.event_worker_attendance);
        }
      }
    };

    if (Array.isArray(rec.event_worker_attendance)) tryArray(rec.event_worker_attendance);
    if (rec.mb1 && Array.isArray(rec.mb1.event_worker_attendance)) tryArray(rec.mb1.event_worker_attendance);
    if (Array.isArray(rec.attendances)) tryArray(rec.attendances);
    if (Array.isArray(rec.presences)) tryArray(rec.presences);
    if (Array.isArray(rec.days)) tryArray(rec.days);

    return dates;
  }

  // Build maps of distinct attended days counts from attendancesMap[evId]
  function buildAttendanceDaysMaps(evId?: number) {
    if (!evId) return;
    const rows = attendancesMap[evId] ?? [];
    const byWorkerDates: Record<string, Set<string>> = {};
    const byUserDates: Record<string, Set<string>> = {};

    const dateKeyOf = (r: any) => normalizeDateKey(r?.attendance_date ?? r?.check_in_at ?? r?.created_at ?? r?.date ?? r?.att_date ?? null);

    for (const r of rows) {
      const key = dateKeyOf(r);
      if (key) {
        if (r?.event_worker_id) {
          const wk = String(r.event_worker_id);
          byWorkerDates[wk] = byWorkerDates[wk] || new Set();
          byWorkerDates[wk].add(key);
        }
        if (r?.user_id) {
          const uid = String(r.user_id);
          byUserDates[uid] = byUserDates[uid] || new Set();
          byUserDates[uid].add(key);
        }
      }
      // nested dates
      const nested = extractDatesFromRecord(r);
      for (const d of nested) {
        if (r?.event_worker_id) {
          const wk = String(r.event_worker_id);
          byWorkerDates[wk] = byWorkerDates[wk] || new Set();
          byWorkerDates[wk].add(d);
        }
        if (r?.user_id) {
          const uid = String(r.user_id);
          byUserDates[uid] = byUserDates[uid] || new Set();
          byUserDates[uid].add(d);
        }
      }
    }

    const workerCounts: Record<string, number> = {};
    Object.entries(byWorkerDates).forEach(([k, s]) => workerCounts[k] = s.size);
    const userCounts: Record<string, number> = {};
    Object.entries(byUserDates).forEach(([k, s]) => userCounts[k] = s.size);

    setAttendanceDaysByWorker(prev => ({ ...prev, [String(evId)]: workerCounts }));
    setAttendanceDaysByUser(prev => ({ ...prev, [String(evId)]: userCounts }));
  }

  function getAttendedDaysForUser(userObj: any, evId?: number): number {
    if (!evId) return 0;

    // 1) check precomputed maps
    const workerMapForEvent = attendanceDaysByWorker[String(evId)] ?? {};
    const userMapForEvent = attendanceDaysByUser[String(evId)] ?? {};

    const wkKey = String(userObj.event_worker_id ?? userObj.id ?? '');
    if (wkKey && workerMapForEvent[wkKey] && Number(workerMapForEvent[wkKey]) > 0) {
      return Number(workerMapForEvent[wkKey]);
    }
    const uidKey = String(userObj.user_id ?? userObj.id ?? '');
    if (uidKey && userMapForEvent[uidKey] && Number(userMapForEvent[uidKey]) > 0) {
      return Number(userMapForEvent[uidKey]);
    }

    // 2) check arrays attached to user object
    const localArrays = [
      userObj?.event_worker_attendance,
      userObj?.event_worker_attendance_array,
      userObj?.attendances,
      userObj?.mb1?.event_worker_attendance,
      userObj?.mb1?.attendances,
      userObj?.presences,
    ];
    const daySet = new Set<string>();

    for (const arr of localArrays) {
      if (Array.isArray(arr) && arr.length > 0) {
        for (const rec of arr) {
          const dates = extractDatesFromRecord(rec);
          dates.forEach(d => daySet.add(d));
        }
        if (daySet.size > 0) return daySet.size;
      }
    }

    // 3) fallback scan of attendancesMap
    const attendances = attendancesMap[evId] ?? [];
    if (!Array.isArray(attendances) || attendances.length === 0) return 0;

    for (const a of attendances) {
      if (userObj?.user_id && a?.user_id && Number(a.user_id) === Number(userObj.user_id)) {
        extractDatesFromRecord(a).forEach(d => daySet.add(d));
        continue;
      }
      if (userObj?.event_worker_id && a?.event_worker_id && Number(a.event_worker_id) === Number(userObj.event_worker_id)) {
        extractDatesFromRecord(a).forEach(d => daySet.add(d));
        continue;
      }
      if (userObj?.id && a?.user_id && Number(a.user_id) === Number(userObj.id)) {
        extractDatesFromRecord(a).forEach(d => daySet.add(d));
        continue;
      }
      if (userObj?.id && a?.event_worker_id && Number(a.event_worker_id) === Number(userObj.id)) {
        extractDatesFromRecord(a).forEach(d => daySet.add(d));
        continue;
      }
      if (userObj?.email && (a?.user_email || a?.email) && String(userObj.email).toLowerCase() === String(a.user_email ?? a.email).toLowerCase()) {
        extractDatesFromRecord(a).forEach(d => daySet.add(d));
        continue;
      }
    }

    return daySet.size;
  }

  function getPresentKeysForEvent(evId?: number): Set<string> {
    if (!evId) return new Set();
    const att = attendancesMap[evId] || [];
    const s = new Set<string>();
    att.forEach((a: any) => {
      if (a.user_id) s.add(`u:${String(a.user_id)}`);
      if (a.event_worker_id) s.add(`w:${String(a.event_worker_id)}`);
    });
    return s;
  }

  function isUserPresentForEvent(userObj: any, evId?: number): boolean {
    if (!evId) return false;
    const s = getPresentKeysForEvent(evId);
    const uid = userObj.user_id ?? userObj.id ?? null;
    if (uid && s.has(`u:${String(uid)}`)) return true;
    const wk = userObj.event_worker_id ?? userObj.id ?? null;
    if (wk && s.has(`w:${String(wk)}`)) return true;
    return false;
  }

  // Utilities: format CPF and phone (Brazilian)
  function formatCPF(raw?: string) {
    if (!raw) return '';
    const digits = String(raw).replace(/\D/g, '');
    if (digits.length !== 11) return raw;
    return digits.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
  }

  // Improved BR-centric phone formatter (adds +55 when reasonable)
  function formatPhone(raw?: string) {
    if (!raw) return '';
    let s = String(raw).trim();

    // remove common noise but keep leading + if present
    const hasPlus = s.startsWith('+');
    s = s.replace(/[^\d]/g, '');

    // if no country code and length is 10/11, assume BR (+55)
    if (!hasPlus && (s.length === 10 || s.length === 11)) {
      s = '55' + s;
    }

    // now s should start with country code
    if (s.length === 12 && s.startsWith('55')) {
      // BR with 10 digits: 55 + AA + 8
      const cc = '+55';
      const ddd = s.slice(2, 4);
      const rest = s.slice(4); // 8 digits
      return `${cc} (${ddd}) ${rest.slice(0,4)}-${rest.slice(4)}`;
    }

    if (s.length === 13 && s.startsWith('55')) {
      // BR with 11 digits: 55 + AA + 9
      const cc = '+55';
      const ddd = s.slice(2, 4);
      const rest = s.slice(4); // 9 digits
      return `${cc} (${ddd}) ${rest.slice(0,5)}-${rest.slice(5)}`;
    }

    // fallback: try to format 10/11-digit raw without country
    if (s.length === 11) { // assume DDD + 9xxxxxxxx
      const ddd = s.slice(0,2);
      const rest = s.slice(2);
      return `+55 (${ddd}) ${rest.slice(0,5)}-${rest.slice(5)}`;
    }
    if (s.length === 10) {
      const ddd = s.slice(0,2);
      const rest = s.slice(2);
      return `+55 (${ddd}) ${rest.slice(0,4)}-${rest.slice(4)}`;
    }

    // otherwise return original input
    return raw;
  }

  // Find participant extra fields from eventUsersMap
  function findParticipantData(eventId?: number, participantId?: any) {
    if (!eventId || participantId == null) return {};
    const list = eventUsersMap[eventId] ?? [];
    const found = list.find((u: any) =>
      String(u.event_worker_id ?? u.user_id ?? u.id ?? '') === String(participantId)
    );
    if (!found) return {};
    const email = found.user?.email ?? found.email ?? found.user_email ?? found.email_address ?? '';
    const cpf = found.cpf ?? found.cpf_number ?? found.cpf_formatted ?? '';
    const phone = found.phone ?? found.telefone ?? found.user?.phone ?? '';
    const pix = found.pix ?? found.payment_pix ?? '';
    const bank = found.bank_name ?? found.banco ?? found.bank ?? '';
    const agency = found.agency ?? found.agencia ?? found.bank_agency ?? '';
    const account = found.bank_account ?? found.conta ?? found.account ?? '';
    return { email, cpf, phone, pix, bank, agency, account };
  }

  // Group entries by participantId + role (summing days)
  function groupEntries(entriesToGroup: Entry[]) {
    const map = new Map<string, Entry>();
    for (const e of entriesToGroup) {
      const key = `${String(e.participantId ?? 'manual')}-${String(e.role)}`;
      if (!map.has(key)) {
        // clone but set quantity to 1 (we drop quantity visually)
        map.set(key, { ...e, quantity: 1 });
      } else {
        const cur = map.get(key)!;
        const newDays = Number(cur.days || 0) + Number(e.days || 0);
        map.set(key, { ...cur, days: newDays });
      }
    }
    return Array.from(map.values());
  }

  // Export to XLSX via backend (default route)
  async function exportToExcel() {
    setError(null);
    if (entries.length === 0) {
      setError('Nenhuma entrada para exportar.');
      return;
    }

    try {
      // preparar payload (agrupado se opção marcada)
      const entriesForExport = groupBeforeExport ? groupEntries(entries) : entries.slice();
      const payload = {
        event_id: selectedEventId,
        event_name: events.find(ev => ev.id === selectedEventId)?.name ?? '',
        entries: entriesForExport.map(e => {
          const p = findParticipantData(e.event_id, e.participantId);
          return {
            participant_id: e.participantId,
            participant_name: e.participantName,
            role: ROLES.find(r => r.value === e.role)?.label ?? String(e.role),
            role_id: e.role,
            email: p.email ?? '',
            cpf: formatCPF(p.cpf ?? ''),       // format CPF in payload
            phone: formatPhone(p.phone ?? ''), // format phone in payload
            pix: p.pix ?? '',
            bank: p.bank ?? '',
            agency: p.agency ?? '',
            account: p.account ?? '',
            unit_amount: e.amount,
            days: e.days,
            total_per_person: Number(e.amount || 0) * Number(e.days || 0),
            total_line: Number(e.amount || 0) * Number(e.days || 0), // quantity=1
            notes: e.notes ?? ''
          };
        }),
        options: { grouped: groupBeforeExport, include_bank_details: true }
      };

      // default request URL relative to axios baseURL
      const requestUrl = 'financials/export';

      // use your api wrapper (axios) and request blob
      const resp = await api.post(requestUrl, payload, {
        responseType: 'blob',
        headers: { 'Content-Type': 'application/json' },
      });

      // create download of blob
      const disposition = resp.headers && (resp.headers['content-disposition'] || resp.headers['Content-Disposition']);
      let filename = `financeiro_${(payload.event_name || 'export')}_${new Date().toISOString().slice(0,10)}.xlsx`;
      if (disposition) {
        const m = /filename="?([^";]+)"?/.exec(disposition);
        if (m) filename = m[1];
      }
      const blob = new Blob([resp.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const urlBlob = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = urlBlob;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(urlBlob);

      setMessage('Arquivo gerado e baixado.');
      setTimeout(() => setMessage(null), 2500);
    } catch (err: any) {
      console.error('exportToExcel error', err);
      setError('Erro ao gerar/baixar o arquivo. Veja console.');
    }
  }

  // Automatic generation for all linked participants (with options)
  function addAllParticipantsAsEntries() {
    if (!selectedEventId) {
      setError('Selecione um evento primeiro.');
      return;
    }
    const participants = eventUsersMap[selectedEventId] ?? [];
    if (!participants || participants.length === 0) {
      setError('Nenhum participante vinculado para este evento.');
      return;
    }

    setGeneratingAll(true);
    setGenerateProgress({ current: 0, total: participants.length });

    // Build entries according to filters
    const toAdd: Entry[] = [];
    for (let i = 0; i < participants.length; i++) {
      const u = participants[i];

      // filter by presence if requested
      if (autoOnlyPresent && !isUserPresentForEvent(u, selectedEventId)) {
        setGenerateProgress(p => ({ ...p, current: p.current + 1 }));
        continue;
      }

      // filter by role if requested
      if (autoRoleFilter !== 'all') {
        const roleName = (u.role_name ?? '').toString().toLowerCase();
        const roleId = u.role_id ?? u.user?.role_id ?? null;
        const roleIdStr = roleId ? String(roleId) : '';
        if (!(roleIdStr === String(autoRoleFilter) || roleName.includes(String(autoRoleFilter).toLowerCase()))) {
          setGenerateProgress(p => ({ ...p, current: p.current + 1 }));
          continue;
        }
      }

      // determine role
      const roleId = u.role_id ?? u.user?.role_id ?? draft.role;
      const role = roleId ?? draft.role;

      // determine amount
      const amountFromRole = roleValues[String(role)] ?? 0;
      const amount = useRoleValuesForAuto ? (amountFromRole || draft.amount) : draft.amount;

      // determine days worked
      const daysWorked = getAttendedDaysForUser(u, selectedEventId) || draft.days || 1;

      const entry: Entry = {
        id: String(Date.now()) + Math.random().toString(36).slice(2, 8) + '-' + i,
        role,
        amount: Number(amount),
        days: Number(daysWorked),
        quantity: 1,
        event_id: selectedEventId,
        event_name: events.find(ev => ev.id === selectedEventId)?.name ?? '',
        notes: `Participante: ${u.nome ?? u.name ?? u.username ?? ''}${u.cpf ? ' • CPF: ' + u.cpf : ''}`,
        participantId: u.event_worker_id ?? u.user_id ?? u.id ?? null,
        participantName: u.nome ?? u.name ?? u.username ?? null,
      };

      toAdd.push(entry);
      setGenerateProgress(p => ({ ...p, current: p.current + 1 }));
    }

    // append all at once (fast)
    setEntries(prev => [...prev, ...toAdd]);

    setGeneratingAll(false);
    setGenerateProgress({ current: 0, total: 0 });

    setMessage(`${toAdd.length} entradas geradas automaticamente.`);
    setTimeout(() => setMessage(null), 2500);
  }

  // Manual entry addition (defined to fix ReferenceError)
  function onAddEntryManual() {
    setError(null);
    if (!selectedEventId && (!draft.event_name || String(draft.event_name).trim() === '')) {
      setError('Selecione ou informe o evento.');
      return;
    }
    if (!draft.amount || Number(draft.amount) <= 0) { setError('Informe um valor maior que zero.'); return; }
    if (!draft.days || Number(draft.days) < 1) { setError('Dias devem ser ao menos 1.'); return; }
    if (!draft.quantity || Number(draft.quantity) < 1) { setError('Quantidade deve ser ao menos 1.'); return; }

    const newEntry: Entry = {
      id: String(Date.now()) + Math.random().toString(36).slice(2, 8),
      role: draft.role,
      amount: Number(draft.amount),
      days: Number(draft.days),
      quantity: Number(draft.quantity),
      event_id: selectedEventId ?? undefined,
      event_name: selectedEventId ? (events.find(ev => ev.id === selectedEventId)?.name ?? '') : draft.event_name ?? '',
      notes: draft.notes?.trim(),
      participantId: null,
      participantName: null,
    };

    setEntries(prev => [...prev, newEntry]);
    setDraft(prev => ({ ...prev, amount: 0, days: 1, quantity: 1, notes: '' }));
    setMessage('Entrada adicionada.');
    setTimeout(() => setMessage(null), 2000);
  }

  // when user selects an event: fetch users and attendances
  useEffect(() => {
    if (!selectedEventId) return;
    fetchUsersForEvent(selectedEventId).catch(() => {});
    fetchAttendancesForEvent(selectedEventId).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEventId]);

  // helper: compute displayed subtotal for an entry using attended days per matched participant
  function computeEntrySubtotal(e: Entry) {
    return Number(e.amount) * Number(e.days) * Number(e.quantity);
  }

  // format number to BRL
  function formatBRL(v: number) {
    return Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  // remove an entry
  function onDelete(id: string) {
    setEntries(prev => prev.filter(e => e.id !== id));
  }

  // total geral computed from entries
  const grandTotal = useMemo(
    () => entries.reduce((acc, e) => acc + (Number(e.amount || 0) * Number(e.days || 0) * Number(e.quantity || 0)), 0),
    [entries]
  );

  return (
    <Paper sx={{ p: 3, borderRadius: 2 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h6">Financeiro — relatório de pagamentos</Typography>
          <Typography variant="body2" color="text.secondary">Selecione o evento, ajuste valores por função e gere o relatório automaticamente para os participantes vinculados.</Typography>
        </Box>
      </Stack>

      {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* 1) Event selector */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 2, alignItems: 'center' }}>
        {loadingEvents ? (
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <CircularProgress size={18} />&nbsp;<Typography>Carregando eventos...</Typography>
          </Box>
        ) : (
          <TextField
            select
            label="Evento"
            value={selectedEventId ?? ''}
            onChange={(e) => setSelectedEventId(e.target.value === '' ? undefined : Number(e.target.value))}
            sx={{ minWidth: 360 }}
            size="small"
          >
            <MenuItem value="">-- selecione --</MenuItem>
            {events.map(ev => <MenuItem key={ev.id} value={ev.id}>{ev.name}{ev.date_start ? ` (${ev.date_start})` : ''}</MenuItem>)}
          </TextField>
        )}

        <Box sx={{ ml: 'auto' }}>
          <Button size="small" variant="contained" onClick={saveRoleValuesLocal} sx={{ mr: 1 }}>Salvar valores</Button>
          <Button size="small" variant="outlined" onClick={resetRoleValuesLocal}>Restaurar padrão</Button>
        </Box>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* 2) Role values */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>Valores por Função (padrões)</Typography>

        <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.paper' }}>
          <Grid container spacing={2} alignItems="center">
            {ROLES.map((r) => (
              <Grid item key={String(r.value)} xs={12} sm={6} md={4} lg={3} xl={2}>
                <TextField
                  fullWidth
                  label={r.label}
                  type="number"
                  size="small"
                  inputProps={{ step: '0.01', min: 0 }}
                  value={roleValues[String(r.value)] ?? 0}
                  onChange={(e) => setRoleValues(prev => ({ ...prev, [String(r.value)]: Number(e.target.value || 0) }))}
                  sx={{ '& .MuiInputBase-root': { borderRadius: 1.5 } }}
                />
              </Grid>
            ))}

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 0.5 }}>
                <Button size="small" variant="outlined" onClick={resetRoleValuesLocal}>Restaurar padrão</Button>
                <Button size="small" variant="contained" onClick={saveRoleValuesLocal}>Salvar valores</Button>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* 3) Auto generation controls */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle1">Gerar entradas automaticamente para participantes vinculados</Typography>
        {!selectedEventId ? (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Selecione um evento para listar participantes e gerar automaticamente.</Typography>
        ) : (
          <Box sx={{ mt: 1 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
              <FormControlLabel control={<Checkbox checked={autoOnlyPresent} onChange={(e) => setAutoOnlyPresent(e.target.checked)} />} label="Apenas participantes presentes" />
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel id="role-filter-label">Filtrar por função</InputLabel>
                <Select labelId="role-filter-label" value={autoRoleFilter} label="Filtrar por função" onChange={(e) => setAutoRoleFilter(e.target.value as any)}>
                  <MenuItem value="all">Todas</MenuItem>
                  {ROLES.map(r => <MenuItem key={String(r.value)} value={String(r.value)}>{r.label}</MenuItem>)}
                </Select>
              </FormControl>
              <FormControlLabel control={<Checkbox checked={useRoleValuesForAuto} onChange={(e) => setUseRoleValuesForAuto(e.target.checked)} />} label="Usar valores por função" />
              <Button variant="contained" startIcon={<Add />} onClick={addAllParticipantsAsEntries} disabled={generatingAll}>
                Gerar para vinculados
              </Button>

              <Button variant="outlined" onClick={() => {
                // convenience: generate only for present participants now
                setAutoOnlyPresent(true);
                setAutoRoleFilter('all');
                addAllParticipantsAsEntries();
              }} disabled={generatingAll}>
                Gerar apenas presentes
              </Button>
            </Stack>

            {generatingAll && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption">Gerando entradas... {generateProgress.current}/{generateProgress.total}</Typography>
                <LinearProgress variant="determinate" value={generateProgress.total ? (generateProgress.current / generateProgress.total) * 100 : 0} />
              </Box>
            )}

            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              O sistema calculará dias trabalhados por participante a partir das presenças e usará o valor configurado para a função.
            </Typography>
          </Box>
        )}
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* 4) Manual entry section */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 2 }}>
        <TextField
          select
          label="Função (para entrada)"
          value={draft.role}
          onChange={(e) => setDraft(prev => ({ ...prev, role: e.target.value as any }))}
          sx={{ minWidth: 220 }}
          size="small"
        >
          {ROLES.map(r => <MenuItem key={String(r.value)} value={r.value}>{r.label}</MenuItem>)}
        </TextField>

        <TextField
          label="Valor (R$)"
          type="number"
          inputProps={{ step: '0.01', min: 0 }}
          value={draft.amount}
          onChange={(e) => setDraft(prev => ({ ...prev, amount: Number(e.target.value) }))}
          sx={{ width: 160 }}
          size="small"
        />

        <TextField
          label="Dias (padrão)"
          type="number"
          inputProps={{ min: 1 }}
          value={draft.days}
          onChange={(e) => setDraft(prev => ({ ...prev, days: Number(e.target.value) }))}
          sx={{ width: 110 }}
          size="small"
        />

        <TextField
          label="Quantidade (opcional)"
          type="number"
          inputProps={{ min: 1 }}
          value={draft.quantity}
          onChange={(e) => setDraft(prev => ({ ...prev, quantity: Number(e.target.value) }))}
          sx={{ width: 140 }}
          size="small"
        />

        <Button variant="contained" startIcon={<Add />} onClick={onAddEntryManual} disabled={!selectedEventId}>
          Adicionar manual
        </Button>
      </Stack>

      {/* entries table (Quantidade removed visually) */}
      <Table size="small" sx={{ mb: 2 }}>
        <TableHead>
          <TableRow>
            <TableCell>Participante</TableCell>
            <TableCell>Função</TableCell>
            <TableCell align="right">Valor unit.</TableCell>
            <TableCell align="right">Dias</TableCell>
            <TableCell>Evento</TableCell>
            <TableCell>Observações</TableCell>
            <TableCell align="right">Subtotal</TableCell>
            <TableCell align="center">Ações</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {entries.map(e => {
            const roleLabel = ROLES.find(r => r.value === e.role)?.label || String(e.role);
            const subtotal = computeEntrySubtotal(e);
            return (
              <TableRow key={e.id}>
                <TableCell>{e.participantName ?? '-'}</TableCell>
                <TableCell>{roleLabel}</TableCell>
                <TableCell align="right">{formatBRL(e.amount)}</TableCell>
                <TableCell align="right">{e.days}</TableCell>
                <TableCell>{e.event_name}</TableCell>
                <TableCell>{e.notes || '-'}</TableCell>
                <TableCell align="right">{formatBRL(subtotal)}</TableCell>
                <TableCell align="center"><IconButton size="small" color="error" onClick={() => onDelete(e.id)}><Delete /></IconButton></TableCell>
              </TableRow>
            );
          })}
          {entries.length === 0 && (
            <TableRow><TableCell colSpan={8}><Typography variant="body2" color="text.secondary">Nenhuma entrada cadastrada.</Typography></TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
        <FormControlLabel control={<Checkbox checked={groupBeforeExport} onChange={(e) => setGroupBeforeExport(e.target.checked)} />} label="Agrupar por participante antes de exportar (soma dias)" />
        <Typography variant="caption" color="text.secondary">Exporta usando o exportador do servidor (formatação garantida).</Typography>
      </Box>

      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="subtitle1">Total Geral: <strong>{formatBRL(grandTotal)}</strong></Typography>
        <Stack direction="row" spacing={2}>
          <Button variant="outlined" onClick={() => { setEntries([]); setMessage('Limpo'); setTimeout(()=>setMessage(null),1500); }}>Limpar</Button>
          <Button variant="contained" onClick={exportToExcel} disabled={entries.length === 0}>Exportar Excel (XLSX)</Button>
        </Stack>
      </Stack>
    </Paper>
  );
}
