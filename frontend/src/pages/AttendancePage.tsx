import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Grid,
  Paper,
  Typography,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Stack,
  Chip,
} from "@mui/material";
import AttendanceList from "../components/AttendanceList";
import { useAuth } from "../contexts/AuthContext";
import api from "../lib/api";

/**
 * AttendancePage simplificada:
 * - remove o painel "Registrar Chegada" (quick dialog)
 * - mantém apenas o seletor de evento e AttendanceList (com ações individuais)
 */

const AttendancePage: React.FC = () => {
  const { eventId: paramEventId } = useParams<{ eventId?: string }>();
  const navigate = useNavigate();
  const { token, schemaName } = useAuth();

  const [events, setEvents] = useState<any[]>([]);
  const [eventId, setEventId] = useState<number | null>(paramEventId ? Number(paramEventId) : null);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [eventsError, setEventsError] = useState<string | null>(null);

  const getAuthHeaders = () => (token ? { Authorization: `Bearer ${token}` } : {});

  // carrega lista de eventos (tentativa simples com fallbacks)
  async function fetchEvents() {
    setLoadingEvents(true);
    setEventsError(null);
    setEvents([]);
    const candidates = [
      `/taf/events`,
      `/events`,
      `/api/v1/events`,
      `/taf/event`,
      `/event`,
      ...(schemaName ? [`/api/v1/tenants/${encodeURIComponent(schemaName)}/events`] : []),
    ];
    let lastErr: any = null;
    for (const ep of candidates) {
      try {
        const res = await api.get(ep, { headers: getAuthHeaders() });
        const data = res.data ?? res;
        let list: any[] = [];
        if (Array.isArray(data)) list = data;
        else if (Array.isArray(data.items)) list = data.items;
        else if (Array.isArray(data.events)) list = data.events;
        else list = [];
        if (Array.isArray(list)) {
          setEvents(list);
          setLoadingEvents(false);
          return;
        }
      } catch (err: any) {
        lastErr = err;
      }
    }
    setEventsError(String(lastErr?.message ?? "Não foi possível carregar eventos"));
    setLoadingEvents(false);
  }

  useEffect(() => {
    fetchEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // auto-select first event if none specified
  useEffect(() => {
    if (!eventId && events.length > 0) {
      const pick = events[0];
      const id = Number(pick.id ?? pick.event_id ?? pick.pk ?? NaN);
      if (!Number.isNaN(id)) setEventId(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events]);

  const currentEvent = events.find((e) => Number(e.id ?? e.event_id) === Number(eventId));

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Paper sx={{ p: 2, mb: 2, borderRadius: 3 }}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Box sx={{ display: "flex", gap: 2, alignItems: "center", minWidth: 0 }}>
            <Typography variant="h6" noWrap>
              Presenças
            </Typography>

            <FormControl size="small" sx={{ minWidth: 280 }}>
              <InputLabel id="select-event-label">Evento</InputLabel>
              <Select
                labelId="select-event-label"
                value={eventId ?? ""}
                label="Evento"
                onChange={(e) => {
                  const v = e.target.value;
                  setEventId(v === "" ? null : Number(v));
                }}
              >
                <MenuItem value="">
                  <em>Selecionar evento</em>
                </MenuItem>
                {events.map((ev) => {
                  const id = ev.id ?? ev.event_id ?? ev.pk;
                  const label = ev.name ?? ev.title ?? `Evento #${id}`;
                  return (
                    <MenuItem key={String(id)} value={Number(id)}>
                      {label}
                    </MenuItem>
                  );
                })}
              </Select>
            </FormControl>

            {loadingEvents ? (
              <Typography variant="body2" color="text.secondary">Carregando eventos...</Typography>
            ) : eventsError ? (
              <Typography variant="body2" color="error">{eventsError}</Typography>
            ) : null}
          </Box>

          {/* show event name/chip (no quick actions) */}
          {currentEvent && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="subtitle1" sx={{ whiteSpace: "nowrap", maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis" }}>
                {currentEvent.name ?? currentEvent.title ?? `Evento #${eventId}`}
              </Typography>
              <Chip label={schemaName ?? "tenant indefinido"} />
            </Box>
          )}
        </Stack>
      </Paper>

      {/* Main area: AttendanceList ocupa toda a área */}
      <Grid container spacing={2}>
        <Grid item xs={12}>
          {/* Passamos eventName explicitamente para garantir o nome correto (mais confiável) */}
          <AttendanceList
            eventId={eventId ?? undefined}
            eventName={currentEvent?.name ?? currentEvent?.title}
            getAuthHeaders={getAuthHeaders}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default AttendancePage;
