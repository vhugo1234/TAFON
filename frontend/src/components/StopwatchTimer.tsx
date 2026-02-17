import React, { useState, useEffect, useRef, useCallback } from "react";
import { Box, Typography, Stack, IconButton, Paper } from "@mui/material";
import { PlayArrow, Pause, Stop, Refresh } from "@mui/icons-material";

interface StopwatchTimerProps {
  maxTime?: number; // em segundos (regressive)
  mode?: "progressive" | "regressive";
  onTimeUp?: () => void;
  autoStart?: boolean;
  running?: boolean; // controle externo
  onTimeChange?: (ms: number) => void;
  onStop?: (durationMs: number) => void;
  tickIntervalMs?: number;
}

export default function StopwatchTimer({
  maxTime,
  mode = "progressive",
  onTimeUp,
  autoStart = false,
  running = false,
  onTimeChange,
  onStop,
  tickIntervalMs = 200,
}: StopwatchTimerProps) {
  // display em ms
  const [displayMs, setDisplayMs] = useState<number>(() =>
    mode === "regressive" && maxTime ? Math.round((maxTime || 0) * 1000) : 0
  );

  // refs para cálculo
  const startRef = useRef<number | null>(null);
  const accRef = useRef<number>(0);
  const intervalRef = useRef<number | null>(null);

  const maxTimeMs = maxTime ? Math.round(maxTime * 1000) : undefined;

  const getElapsed = useCallback(() => {
    if (startRef.current === null) return accRef.current;
    return accRef.current + (performance.now() - startRef.current);
  }, []);

  const updateDisplay = useCallback(() => {
    const elapsed = getElapsed();
    const current = mode === "regressive" && maxTimeMs !== undefined ? Math.max(0, maxTimeMs - elapsed) : elapsed;
    setDisplayMs(Math.round(current));
    if (onTimeChange) onTimeChange(Math.round(current));
    if (mode === "regressive" && maxTimeMs !== undefined && elapsed >= maxTimeMs) {
      // time up
      if (onTimeUp) onTimeUp();
      // call onStop with 0 remaining (or duration)
      if (onStop) onStop(0);
      // stop loop
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      startRef.current = null;
      accRef.current = 0;
    }
  }, [getElapsed, mode, maxTimeMs, onTimeChange, onTimeUp, onStop]);

  const start = useCallback(() => {
    if (startRef.current !== null) return;
    startRef.current = performance.now();
    // guarantee an interval running only once
    if (!intervalRef.current) {
      intervalRef.current = window.setInterval(updateDisplay, tickIntervalMs);
    }
  }, [tickIntervalMs, updateDisplay]);

  const pause = useCallback(() => {
    if (startRef.current === null) return;
    accRef.current = getElapsed();
    startRef.current = null;
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    // one final update so UI reflects pause instant
    updateDisplay();
  }, [getElapsed, updateDisplay]);

  const stop = useCallback(() => {
    const duration = mode === "progressive" ? Math.round(getElapsed()) : Math.round((maxTimeMs || 0) - (getElapsed()));
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    startRef.current = null;
    accRef.current = 0;
    const initial = mode === "regressive" && maxTimeMs !== undefined ? maxTimeMs : 0;
    setDisplayMs(initial);
    if (onTimeChange) onTimeChange(initial);
    if (onStop) onStop(duration);
  }, [getElapsed, maxTimeMs, mode, onStop, onTimeChange]);

  const reset = useCallback(() => {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    startRef.current = null;
    accRef.current = 0;
    const initial = mode === "regressive" && maxTimeMs !== undefined ? maxTimeMs : 0;
    setDisplayMs(initial);
    if (onTimeChange) onTimeChange(initial);
  }, [mode, maxTimeMs, onTimeChange]);

  // React to external running/autoStart props
  useEffect(() => {
    if (running || autoStart) start();
    else pause();
    // do NOT include start/pause in deps to avoid re-creating intervals
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, autoStart]);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  const formatForDisplay = (ms: number) => {
    const abs = Math.abs(ms);
    const hours = Math.floor(abs / 3600000);
    const minutes = Math.floor((abs % 3600000) / 60000);
    const seconds = Math.floor((abs % 60000) / 1000);
    const mss = abs % 1000;
    if (hours === 0) return `${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}.${String(mss).padStart(3,'0')}`;
    return `${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}.${String(mss).padStart(3,'0')}`;
  };

  return (
    <Paper elevation={3} sx={{ p: 3, textAlign: "center", bgcolor: "primary.50" }}>
      <Typography variant="h6" gutterBottom color="primary" fontWeight={600}>
        {mode === "regressive" ? "Cronômetro Regressivo" : "Cronômetro"}
      </Typography>

      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", my: 3, p: 3, bgcolor: "white", borderRadius: 2 }}>
        <Typography variant="h1" fontWeight={700} sx={{ fontFamily: "monospace", color: "primary.main", fontSize: { xs: "2.25rem", sm: "3rem", md: "4rem" } }}>
          {formatForDisplay(displayMs)}
        </Typography>
      </Box>

      <Stack direction="row" spacing={2} justifyContent="center">
        <IconButton onClick={() => (startRef.current ? pause() : start())} color="primary" sx={{ bgcolor: "white", width: 64, height: 64 }}>
          {startRef.current ? <Pause fontSize="large" /> : <PlayArrow fontSize="large" />}
        </IconButton>

        <IconButton onClick={stop} color="error" sx={{ bgcolor: "white", width: 64, height: 64 }}>
          <Stop fontSize="large" />
        </IconButton>

        <IconButton onClick={reset} color="default" sx={{ bgcolor: "white", width: 64, height: 64 }}>
          <Refresh fontSize="large" />
        </IconButton>
      </Stack>
    </Paper>
  );
}
