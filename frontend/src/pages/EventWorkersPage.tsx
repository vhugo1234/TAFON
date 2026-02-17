import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Tooltip,
  Snackbar,
  Alert,
  CircularProgress,
  Stack,
  Divider,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import EditIcon from "@mui/icons-material/Edit";
import AddIcon from "@mui/icons-material/Add";
import EventWorkersManager from "../components/EventWorkersManager";
import { useAuth } from "../contexts/AuthContext";
import api from "../lib/api";

const EventWorkersPage: React.FC = () => {
  const { eventId } = useParams<{ eventId?: string }>();
  const navigate = useNavigate();
  const { schemaName } = useAuth();

  const [tenantId, setTenantId] = useState<string | null>(schemaName ?? null);
  const [eventObj, setEventObj] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const [snackOpen, setSnackOpen] = useState(false);
  const [snackMsg, setSnackMsg] = useState("");
  const [snackSeverity, setSnackSeverity] =
    useState<"success" | "error">("success");

  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideValue, setOverrideValue] = useState("");

  useEffect(() => {
    async function fetchEvent() {
      if (!eventId) return;
      setLoading(true);
      try {
        const res = await api.get(`/taf/events/${eventId}`);
        setEventObj(res.data?.item ?? res.data);
      } finally {
        setLoading(false);
      }
    }
    fetchEvent();
  }, [eventId]);

  if (!eventId) return null;

  const buildRegisterUrl = () => {
    const base = `${window.location.origin}/taf/events/${eventId}/register`;
    return tenantId ? `${base}?schema_name=${tenantId}` : base;
  };

  const copyLink = async () => {
    await navigator.clipboard.writeText(buildRegisterUrl());
    setSnackMsg("Link copiado com sucesso");
    setSnackSeverity("success");
    setSnackOpen(true);
  };

  return (
    <Box p={3}>
      {/* HEADER */}
      <Paper sx={{ p: 2, mb: 2, borderRadius: 3 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <IconButton onClick={() => navigate(-1)}>
            <ArrowBackIcon />
          </IconButton>

          <Box flex={1}>
            <Typography variant="h6">Equipe do Evento</Typography>
            <Typography color="text.secondary">
              {eventObj?.name ?? `Evento #${eventId}`}
            </Typography>
          </Box>

          {loading ? (
            <CircularProgress size={20} />
          ) : (
            <Chip label={tenantId ?? "tenant indefinido"} />
          )}
        </Stack>
      </Paper>

      {/* LINK */}
      <Paper sx={{ p: 2, mb: 2, borderRadius: 3 }}>
        <Typography variant="subtitle2">Link de registro</Typography>

        <Stack direction="row" spacing={1} mt={1} alignItems="center">
          <Typography
            sx={{
              flex: 1,
              bgcolor: "grey.100",
              p: 1,
              borderRadius: 1,
              wordBreak: "break-all",
            }}
          >
            {buildRegisterUrl()}
          </Typography>

          <Button startIcon={<ContentCopyIcon />} onClick={copyLink}>
            Copiar
          </Button>

          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => window.open(buildRegisterUrl(), "_blank")}
          >
            Criar usuário
          </Button>

          <Tooltip title="Override tenant">
            <IconButton onClick={() => setOverrideOpen(true)}>
              <EditIcon />
            </IconButton>
          </Tooltip>
        </Stack>
      </Paper>

      {/* MANAGER */}
      <EventWorkersManager eventId={Number(eventId)} />

      {/* DIALOG */}
      <Dialog open={overrideOpen} onClose={() => setOverrideOpen(false)}>
        <DialogTitle>Override tenant</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="schema_name"
            value={overrideValue}
            onChange={(e) => setOverrideValue(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOverrideOpen(false)}>Cancelar</Button>
          <Button
            onClick={() => {
              setTenantId(overrideValue || null);
              setOverrideOpen(false);
            }}
          >
            Aplicar
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackOpen}
        autoHideDuration={2500}
        onClose={() => setSnackOpen(false)}
      >
        <Alert severity={snackSeverity}>{snackMsg}</Alert>
      </Snackbar>
    </Box>
  );
};

export default EventWorkersPage;
