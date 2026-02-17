import React, { useEffect, useRef, useState, useCallback } from "react";
import SignaturePad from "signature_pad";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  IconButton,
  Box,
  Typography,
  Stack,
  Snackbar,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
} from "@mui/material";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import CloseIcon from "@mui/icons-material/Close";
import api from "../lib/api";

/**
 * AttendanceCheckin.tsx (improved detection)
 *
 * Objetivo: detectar assinatura automaticamente e habilitar o botão salvar sem precisar do "Forçar envio".
 * Melhorias:
 * - mais formas de detectar tinta: onBegin, onEnd, pointer events no window e poll periódico (fallback)
 * - threshold reduzido e logs debug para investigar casos
 * - mantém compressão de foto, geolocalização e POST robusto
 *
 * Substitua o arquivo e faça Hard Reload (Empty Cache and Hard Reload).
 */

type Props = {
  eventId: number | string;
  workerId?: number | string;
  getAuthHeaders?: () => Record<string, string>;
  apiBase?: string;
  onSuccess?: (attendance: any) => void;
  open?: boolean;
  onClose?: () => void;
};

const MAX_PHOTO_DIM = 1280;
const MAX_SIG_BYTES = 2 * 1024 * 1024;
// Threshold para considerar que dataURL contém tinta. Ajustável.
const SIG_DETECT_THRESHOLD = 700;

export default function AttendanceCheckin({
  eventId,
  workerId,
  getAuthHeaders,
  apiBase = "/api/v1",
  onSuccess,
  open = false,
  onClose,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const sigPadRef = useRef<SignaturePad | null>(null);
  const signatureCacheRef = useRef<string | null>(null);
  const pollIntervalRef = useRef<number | null>(null);

  const [saving, setSaving] = useState(false);
  const [snack, setSnack] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [photoDataUrl, setPhotoDataUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [participants, setParticipants] = useState<any[]>([]);
  const [loadingParticipants, setLoadingParticipants] = useState(false);
  const [selectedWorkerId, setSelectedWorkerId] = useState<number | null>(null);

  // assinatura detectada (estado central)
  const [signaturePresent, setSignaturePresent] = useState(false);

  const effectiveWorkerId = selectedWorkerId ?? (workerId ? Number(workerId) : null);

  const isDev = typeof import.meta !== "undefined" && !!(import.meta as any).env?.DEV;

  const headersFor = () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (getAuthHeaders) Object.assign(headers, getAuthHeaders());
    return headers;
  };

  // --- Backend base detection (prefer VITE_API_URL, então api.defaults.baseURL, então window.location.origin)
  function getBackendBase(): string {
    const envUrl = (typeof import.meta !== "undefined" ? (import.meta as any).env?.VITE_API_URL : undefined) || "";
    let base = envUrl || (api && (api.defaults as any)?.baseURL) || "";
    if (!base) base = window.location.origin;
    return String(base).replace(/\/+$/, "");
  }

  function buildCheckinUrl() {
    const base = getBackendBase();
    const apiBaseNorm = (apiBase || "").toString().replace(/^\/+/, "").replace(/\/+$/, "");
    // if base already ends with apiBaseNorm, don't duplicate
    if (apiBaseNorm && base.endsWith("/" + apiBaseNorm)) {
      return `${base}/event/${encodeURIComponent(eventId)}/worker/${encodeURIComponent(effectiveWorkerId)}/attendance/checkin`;
    }
    if (apiBaseNorm) {
      return `${base}/${apiBaseNorm}/event/${encodeURIComponent(eventId)}/worker/${encodeURIComponent(effectiveWorkerId)}/attendance/checkin`;
    }
    return `${base}/event/${encodeURIComponent(eventId)}/worker/${encodeURIComponent(effectiveWorkerId)}/attendance/checkin`;
  }
  // --- end URL helpers

  // normalize signature detection from pad (central)
  const updateSignaturePresentFromPad = useCallback(() => {
    try {
      const pad = sigPadRef.current;
      if (!pad) {
        setSignaturePresent(false);
        return;
      }
      const dataUrl = pad.toDataURL();
      const len = dataUrl ? dataUrl.length : 0;
      const isEmpty = typeof pad.isEmpty === "function" ? pad.isEmpty() : false;
      const hasInk = !isEmpty || len > SIG_DETECT_THRESHOLD;
      signatureCacheRef.current = dataUrl || signatureCacheRef.current;
      setSignaturePresent(Boolean(hasInk));
      console.debug("CHECKIN DEBUG: updateSignaturePresentFromPad len=", len, "isEmpty=", isEmpty, "hasInk=", hasInk);
    } catch (e) {
      console.debug("CHECKIN DEBUG: updateSignaturePresentFromPad error", e);
      setSignaturePresent(false);
    }
  }, []);

  // init signature pad with hi-dpi handling
  const initSignaturePad = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== Math.floor(w * ratio) || canvas.height !== Math.floor(h * ratio)) {
      canvas.width = Math.floor(w * ratio);
      canvas.height = Math.floor(h * ratio);
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.scale(ratio, ratio);
    }

    if (!sigPadRef.current) {
      sigPadRef.current = new SignaturePad(canvas, {
        backgroundColor: "rgba(255,255,255,0)",
        penColor: "black",
        minWidth: 1,
        maxWidth: 2.5,
      });

      // usuário começou a desenhar -> consideramos presença imediatamente (reduz falsos-negativos)
      sigPadRef.current.onBegin = () => {
        setSignaturePresent(true);
        console.debug("CHECKIN DEBUG: onBegin -> setSignaturePresent(true)");
      };

      // fim do traço -> atualiza cache e faz checagens definitivas
      sigPadRef.current.onEnd = () => {
        try {
          const dataUrl = sigPadRef.current?.toDataURL() ?? "";
          signatureCacheRef.current = dataUrl;
          const len = dataUrl.length;
          const isEmpty = typeof sigPadRef.current?.isEmpty === "function" ? sigPadRef.current.isEmpty() : false;
          const hasInk = !isEmpty || len > SIG_DETECT_THRESHOLD;
          setSignaturePresent(Boolean(hasInk));
          console.debug("CHECKIN DEBUG: onEnd len=", len, "isEmpty=", isEmpty, "hasInk=", hasInk);
        } catch (e) {
          console.debug("CHECKIN DEBUG: onEnd error", e);
          setSignaturePresent(false);
        }
      };
    }

    // restore cached signature if present (when re-opening/resizing)
    if (signatureCacheRef.current && sigPadRef.current) {
      try {
        sigPadRef.current.clear();
        sigPadRef.current.fromDataURL(signatureCacheRef.current);
        const d = signatureCacheRef.current || "";
        setSignaturePresent(d.length > SIG_DETECT_THRESHOLD);
        console.debug("CHECKIN DEBUG: restored cached signature, len=", d.length);
      } catch {
        // ignore
      }
    }
  }, []);

  // attach pointer/mouse/touch listeners on window for robust detection (covers releases outside canvas)
  useEffect(() => {
    if (!open) return;

    const onPointerDown = () => {
      setSignaturePresent(true);
      console.debug("CHECKIN DEBUG: window pointerdown -> mark signaturePresent true");
    };
    const onPointerUp = () => updateSignaturePresentFromPad();
    const onTouchEnd = () => updateSignaturePresentFromPad();

    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("mouseup", onPointerUp);
    window.addEventListener("touchend", onTouchEnd);

    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("mouseup", onPointerUp);
      window.removeEventListener("touchend", onTouchEnd);
    };
  }, [open, updateSignaturePresentFromPad]);

  // polling fallback: periodically check pad content while modal open (covers platforms with weird event handling)
  useEffect(() => {
    if (!open) return;
    // start polling
    pollIntervalRef.current = window.setInterval(() => {
      try {
        const pad = sigPadRef.current;
        if (!pad) return;
        const dataUrl = pad.toDataURL();
        const len = dataUrl ? dataUrl.length : 0;
        const isEmpty = typeof pad.isEmpty === "function" ? pad.isEmpty() : false;
        const hasInk = !isEmpty || len > SIG_DETECT_THRESHOLD;
        if (hasInk !== signaturePresent) {
          console.debug("CHECKIN DEBUG: poll detected change -> hasInk=", hasInk, "len=", len);
          signatureCacheRef.current = dataUrl;
          setSignaturePresent(Boolean(hasInk));
        }
      } catch {
        // ignore
      }
    }, 500);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [open, signaturePresent]);

  useEffect(() => {
    if (!open) return;
    initSignaturePad();
    const onResize = () => {
      try {
        signatureCacheRef.current = sigPadRef.current?.toDataURL() ?? null;
      } catch {
        signatureCacheRef.current = null;
      }
      sigPadRef.current?.off();
      sigPadRef.current = null;
      initSignaturePad();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [open, initSignaturePad]);

  // participants fetch when modal opened without preselected worker
  useEffect(() => {
    if (!open) return;
    if (!workerId || Number(workerId) === 0) {
      (async () => {
        setLoadingParticipants(true);
        try {
          const res = await api.get(`/event/${encodeURIComponent(eventId)}/workers`, { headers: headersFor() });
          const data = res.data ?? res;
          const list = Array.isArray(data) ? data : data.items ?? data.workers ?? [];
          setParticipants((list || []).map((it: any) => ({ ...it, user: it.user ?? null })));
        } catch {
          setParticipants([]);
        } finally {
          setLoadingParticipants(false);
        }
      })();
    } else {
      setSelectedWorkerId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, workerId, eventId]);

  // photo handling (compress)
  const openFilePicker = (file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      const img = new Image();
      img.onload = () => {
        const iw = img.width;
        const ih = img.height;
        const scale = Math.min(1, MAX_PHOTO_DIM / iw, MAX_PHOTO_DIM / ih);
        const cw = Math.max(1, Math.floor(iw * scale));
        const ch = Math.max(1, Math.floor(ih * scale));
        const c = document.createElement("canvas");
        c.width = cw;
        c.height = ch;
        const ctx = c.getContext("2d");
        if (!ctx) return setPhotoDataUrl(dataUrl);
        ctx.drawImage(img, 0, 0, cw, ch);
        setPhotoDataUrl(c.toDataURL("image/jpeg", 0.85));
      };
      img.onerror = () => setPhotoDataUrl(dataUrl);
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files && e.target.files[0];
    openFilePicker(f || null);
  };

  const startCamera = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Navegador não suporta câmera.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraOn(true);
    } catch {
      setError("Não foi possível acessar a câmera.");
    }
  };

  const stopCamera = () => {
    setCameraOn(false);
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
      tracks.forEach((t) => t.stop());
      videoRef.current.srcObject = null;
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const v = videoRef.current;
    const scale = Math.min(1, MAX_PHOTO_DIM / (v.videoWidth || MAX_PHOTO_DIM), MAX_PHOTO_DIM / (v.videoHeight || MAX_PHOTO_DIM));
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor((v.videoWidth || MAX_PHOTO_DIM) * scale);
    canvas.height = Math.floor((v.videoHeight || MAX_PHOTO_DIM) * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
    setPhotoDataUrl(canvas.toDataURL("image/jpeg", 0.85));
    stopCamera();
  };

  async function getGeolocation(): Promise<{ lat?: number; lng?: number } | null> {
    if (!navigator.geolocation) return null;
    return new Promise((resolve) => {
      const t = setTimeout(() => resolve(null), 8000);
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          clearTimeout(t);
          resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        },
        () => {
          clearTimeout(t);
          resolve(null);
        },
        { enableHighAccuracy: true, maximumAge: 30000, timeout: 7000 }
      );
    });
  }

  async function normalizeSignature(sigDataUrl: string) {
    try {
      const header = "data:image/png;base64,";
      if (!sigDataUrl.startsWith(header)) return sigDataUrl;
      const b64 = sigDataUrl.slice(header.length);
      const byteLen = Math.round((b64.length * 3) / 4);
      if (byteLen <= MAX_SIG_BYTES) return sigDataUrl;
      return await new Promise<string>((resolve) => {
        const img = new Image();
        img.onload = () => {
          const MAX_W = 1200;
          const MAX_H = 400;
          const scale = Math.min(1, MAX_W / img.width, MAX_H / img.height);
          const c = document.createElement("canvas");
          c.width = Math.max(1, Math.floor(img.width * scale));
          c.height = Math.max(1, Math.floor(img.height * scale));
          const ctx = c.getContext("2d");
          if (!ctx) return resolve(sigDataUrl);
          ctx.clearRect(0, 0, c.width, c.height);
          ctx.drawImage(img, 0, 0, c.width, c.height);
          try {
            const out = c.toDataURL("image/png");
            resolve(out);
          } catch {
            resolve(sigDataUrl);
          }
        };
        img.onerror = () => resolve(sigDataUrl);
        img.src = sigDataUrl;
      });
    } catch {
      return sigDataUrl;
    }
  }

  const canSubmit = () => {
    if (saving) return false;
    if (!effectiveWorkerId || Number(effectiveWorkerId) === 0) return false;
    if (!sigPadRef.current) return false;
    if (!signaturePresent) return false;
    return true;
  };

  // main submit
  async function doSubmit() {
    setError(null);
    setSnack(null);

    if (!effectiveWorkerId || Number(effectiveWorkerId) === 0) {
      setError("Selecione um participante válido antes de salvar.");
      return;
    }

    if (!sigPadRef.current) {
      setError("Signature pad não pronto. Reabra o modal se persistir.");
      return;
    }

    if (!signaturePresent) {
      setError("Assine antes de salvar.");
      return;
    }

    setSaving(true);
    try {
      let signatureData = sigPadRef.current.toDataURL("image/png");
      signatureData = await normalizeSignature(signatureData);
      const geo = await getGeolocation();
      const payload: any = { signature_data: signatureData, date: undefined };
      if (photoDataUrl) payload.photo_data = photoDataUrl;
      if (geo) {
        payload.lat = geo.lat;
        payload.lng = geo.lng;
      }

      const headers = headersFor();
      const url = buildCheckinUrl();

      console.debug("CHECKIN DEBUG: POST", {
        url,
        effectiveWorkerId,
        signature_len: signatureData.length,
        hasPhoto: !!photoDataUrl,
        hasGeo: !!geo,
      });

      // ensure axios does not prefix a different baseURL automatically (we pass absolute URL)
      const resp = await api.post(url, payload, { headers, baseURL: "" });

      setSnack({ type: "success", message: "Check‑in registrado com sucesso." });
      signatureCacheRef.current = null;
      sigPadRef.current?.clear();
      setSignaturePresent(false);
      setPhotoDataUrl(null);
      if (onSuccess) onSuccess(resp.data);
      setTimeout(() => onClose && onClose(), 600);
    } catch (err: any) {
      console.error("CHECKIN DEBUG: submit error", err);
      if (err?.response) {
        const status = err.response.status;
        const body = err.response.data;
        if (typeof body === "string") setError(`Erro ${status}: ${body.slice(0, 400)}`);
        else setError(`Erro ${status}: ${JSON.stringify(body).slice(0, 400)}`);
      } else {
        setError(err?.message || "Erro ao salvar check‑in.");
      }
      setSnack({ type: "error", message: error ?? "Erro ao registrar presença." });
    } finally {
      setSaving(false);
    }
  }

  // keyboard shortcut: Ctrl/Cmd + Enter to send (only when modal open)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;
      if (isCtrl && e.key === "Enter") {
        e.preventDefault();
        if (canSubmit()) doSubmit();
      }
    };
    if (open) window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, signaturePresent, effectiveWorkerId, saving]);

  // cleanup / re-init when modal opens/closes
  useEffect(() => {
    if (!open) {
      stopCamera();
      sigPadRef.current?.off();
      sigPadRef.current = null;
      signatureCacheRef.current = null;
      setSignaturePresent(false);
      setPhotoDataUrl(null);
      setError(null);
      setSnack(null);
      setParticipants([]);
      setSelectedWorkerId(null);
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    } else {
      setTimeout(() => initSignaturePad(), 50);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <>
      <Dialog open={!!open} onClose={onClose} maxWidth="md" fullWidth aria-labelledby="attendance-checkin-title">
        <DialogTitle id="attendance-checkin-title" sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {/* Avoid nested headings: render as div */}
          <Typography variant="h6" component="div">
            Assine para confirmar presença
          </Typography>
          <IconButton aria-label="fechar" onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>

        <DialogContent dividers>
          {(!workerId || Number(workerId) === 0) && (
            <Box sx={{ mb: 2 }}>
              <FormControl fullWidth size="small">
                <InputLabel id="participant-select-label">Participante</InputLabel>
                <Select
                  labelId="participant-select-label"
                  value={selectedWorkerId ?? ""}
                  label="Participante"
                  onChange={(e) => setSelectedWorkerId(Number(e.target.value))}
                >
                  <MenuItem value="">
                    <em>Selecionar participante</em>
                  </MenuItem>
                  {loadingParticipants ? (
                    <MenuItem value="" disabled>
                      Carregando...
                    </MenuItem>
                  ) : (
                    participants.map((p: any) => {
                      const label = p.user?.nome ?? p.user?.username ?? `Usuário #${p.user_id ?? p.id}`;
                      return (
                        <MenuItem key={p.id} value={p.id}>
                          {label}
                          {p.role_name ? ` — ${p.role_name}` : ""}
                        </MenuItem>
                      );
                    })
                  )}
                </Select>
              </FormControl>
            </Box>
          )}

          <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", md: "row" } }}>
            <Box sx={{ flex: 1, minWidth: 300, border: "1px solid #e0e0e0", borderRadius: 1, p: 1, background: "#fff" }}>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <Typography variant="subtitle2">Assinatura</Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip label={signaturePresent ? "Assinatura detectada" : "Sem assinatura"} color={signaturePresent ? "success" : "default"} size="small" variant={signaturePresent ? "filled" : "outlined"} />
                  {isDev && (
                    <Button
                      size="small"
                      color="secondary"
                      onClick={() => {
                        const pad = sigPadRef.current;
                        const len = pad ? pad.toDataURL().length : 0;
                        console.debug("CHECKIN DEBUG: debug info", { effectiveWorkerId, signature_len: len, photo: !!photoDataUrl, signaturePresent });
                        alert(`DEBUG: effectiveWorkerId=${effectiveWorkerId}\nsignature_len=${len}\nsignaturePresent=${signaturePresent}\nphoto=${!!photoDataUrl}`);
                      }}
                    >
                      Debug
                    </Button>
                  )}
                </Stack>
              </Box>

              <Box sx={{ height: 300, width: "100%", background: "#fff", borderRadius: 1 }}>
                <canvas ref={canvasRef} style={{ width: "100%", height: "100%", touchAction: "none" }} />
              </Box>

              <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                <Button variant="outlined" onClick={() => { sigPadRef.current?.clear(); signatureCacheRef.current = null; setSignaturePresent(false); }} disabled={saving}>
                  Limpar
                </Button>

                <Button variant="contained" onClick={() => doSubmit()} disabled={!canSubmit()} startIcon={saving ? <CircularProgress size={16} /> : undefined}>
                  {saving ? "Enviando..." : "Salvar assinatura e registrar chegada"}
                </Button>
              </Stack>

              {error && (
                <Typography color="error" sx={{ mt: 1 }}>
                  {error}
                </Typography>
              )}
            </Box>

            <Box sx={{ width: { xs: "100%", md: 340 } }}>
              <Typography variant="subtitle2">Foto (opcional)</Typography>

              {photoDataUrl ? (
                <Box>
                  <img src={photoDataUrl} alt="preview" style={{ maxWidth: "100%", borderRadius: 6, border: "1px solid #eee" }} />
                  <Box sx={{ mt: 1, display: "flex", gap: 1 }}>
                    <Button onClick={() => setPhotoDataUrl(null)}>Remover foto</Button>
                  </Box>
                </Box>
              ) : (
                <>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
                    <input id="attendance-photo-input" type="file" accept="image/*" style={{ display: "none" }} onChange={handleFileInput} />
                    <label htmlFor="attendance-photo-input">
                      <Button component="span" startIcon={<PhotoCameraIcon />}>
                        Escolher arquivo
                      </Button>
                    </label>

                    <Button onClick={cameraOn ? stopCamera : startCamera}>{cameraOn ? "Desligar câmera" : "Abrir câmera"}</Button>
                  </Stack>

                  {cameraOn && (
                    <Box sx={{ mt: 1 }}>
                      <video ref={videoRef} style={{ width: "100%", borderRadius: 6 }} playsInline />
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        <Button variant="contained" onClick={capturePhoto}>
                          Capturar foto
                        </Button>
                        <Button onClick={stopCamera}>Cancelar</Button>
                      </Stack>
                    </Box>
                  )}
                </>
              )}

              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Dica: peça que o participante assine claramente no espaço à esquerda. Atalho: Ctrl/Cmd + Enter para enviar.
                </Typography>
              </Box>
            </Box>
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={() => onClose && onClose()}>Fechar</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!snack} autoHideDuration={5000} onClose={() => setSnack(null)}>
        {snack && <Alert onClose={() => setSnack(null)} severity={snack.type} sx={{ width: "100%" }}>{snack.message}</Alert>}
      </Snackbar>
    </>
  );
}
