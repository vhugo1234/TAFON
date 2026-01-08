import React, { useState } from "react";
import {
  Box,
  TextField,
  Button,
  Alert,
  InputAdornment,
  IconButton,
  Typography,
  CircularProgress,
  Link as MuiLink,
  Avatar,
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";
import ReCAPTCHA from "react-google-recaptcha";
import FitnessCenterIcon from "@mui/icons-material/FitnessCenter";

// Logo será servido do public folder ou usaremos um ícone
const logoSrc = "/logo.png";

type Props = {
  username: string;
  setUsername: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  recaptchaRef: React.RefObject<ReCAPTCHA>;
  setRecaptchaToken: (t: string | null) => void;
  error?: string | null;
  loading?: boolean;
  handleSubmit: (e: React.FormEvent) => Promise<void> | void;
};

const ENV_SITE_KEY = (import.meta.env.VITE_RECAPTCHA_SITE_KEY as string) || "";
const TEST_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI";
const SITE_KEY_TO_USE =
  ENV_SITE_KEY || (import.meta.env.MODE === "development" ? TEST_SITE_KEY : "");

export default function LoginForm({
  username,
  setUsername,
  password,
  setPassword,
  recaptchaRef,
  setRecaptchaToken,
  error,
  loading,
  handleSubmit,
}: Props) {
  const [showPwd, setShowPwd] = useState(false);
  const [logoError, setLogoError] = useState(false);

  return (
    <Box component="form" onSubmit={handleSubmit} noValidate sx={{ px: 3 }}>
      {/* Top area: logo + product title */}
      <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1, mb: 3 }}>
        {/* Logo - usar ícone como fallback */}
        {!logoError ? (
          <Box
            component="img"
            src={logoSrc}
            alt="TAFON - logotipo"
            onError={() => setLogoError(true)}
            aria-label="Logotipo TAFON"
            sx={{
              width: { xs: 110, sm: 160, md: 220 },
              height: "auto",
              objectFit: "contain",
              display: "block",
              mt: 0,
            }}
          />
        ) : (
          <Avatar
            sx={{
              width: 80,
              height: 80,
              bgcolor: 'primary.main',
              mb: 1,
            }}
          >
            <FitnessCenterIcon sx={{ fontSize: 40 }} />
          </Avatar>
        )}

        {/* Product name */}
        <Typography variant="h4" sx={{ fontWeight: 800, mt: 0.5, color: 'primary.main' }}>
          TAFON
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ textAlign: "center", maxWidth: 360 }}>
          Entre com suas credenciais para gerenciar testes de aptidão física.
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
        Acessar conta
      </Typography>

      <TextField
        label="E-mail ou usuário"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        fullWidth
        required
        variant="outlined"
        margin="dense"
        autoComplete="username"
        sx={{
          "& .MuiOutlinedInput-root": {
            borderRadius: 2,
            backgroundColor: (t) => (t.palette.mode === "light" ? "#f7fbff" : "rgba(255,255,255,0.03)"),
          },
        }}
      />

      <TextField
        label="Senha"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        fullWidth
        required
        variant="outlined"
        margin="dense"
        type={showPwd ? "text" : "password"}
        autoComplete="current-password"
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                aria-label={showPwd ? "Ocultar senha" : "Mostrar senha"}
                onClick={() => setShowPwd((s) => !s)}
                edge="end"
              >
                {showPwd ? <VisibilityOff /> : <Visibility />}
              </IconButton>
            </InputAdornment>
          ),
        }}
        sx={{
          mb: 1,
          "& .MuiOutlinedInput-root": {
            borderRadius: 2,
            backgroundColor: (t) => (t.palette.mode === "light" ? "#f7fbff" : "rgba(255,255,255,0.03)"),
          },
        }}
      />

      <Box sx={{ my: 2, display: "flex", justifyContent: "center" }}>
        {SITE_KEY_TO_USE ? (
          <Box sx={{ display: "flex", justifyContent: "center" }}>
            <ReCAPTCHA
              ref={recaptchaRef}
              sitekey={SITE_KEY_TO_USE}
              onChange={(token) => setRecaptchaToken(token)}
              onExpired={() => setRecaptchaToken(null)}
              theme={typeof document !== "undefined" && document.body.dataset.theme === "dark" ? "dark" : "light"}
            />
          </Box>
        ) : (
          <Alert severity="info" sx={{ fontSize: '0.75rem' }}>
            reCAPTCHA em modo de desenvolvimento
          </Alert>
        )}
      </Box>

      <Button
        type="submit"
        variant="contained"
        fullWidth
        disabled={loading}
        size="large"
        sx={{
          mt: 1,
          py: 1.25,
          borderRadius: 2,
          background: (t) => `linear-gradient(180deg, ${t.palette.primary.main}, ${t.palette.primary.dark})`,
          boxShadow: (t) => `0 8px 18px ${t.palette.primary.main}33`,
          "&:hover": {
            transform: "translateY(-1px)",
            boxShadow: (t) => `0 14px 30px ${t.palette.primary.main}44`,
          },
        }}
      >
        {loading ? <CircularProgress size={22} color="inherit" /> : "Entrar"}
      </Button>

      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mt: 2 }}>
        <MuiLink component={RouterLink} to="/forgot-password" variant="body2">
          Esqueceu a senha?
        </MuiLink>
        <Typography variant="caption" color="text.secondary">
          Precisa de ajuda? <MuiLink component={RouterLink} to="/support">Contato</MuiLink>
        </Typography>
      </Box>
    </Box>
  );
}

