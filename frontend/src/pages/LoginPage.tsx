import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import LoginForm from "../components/LoginForm";
import {
  CssBaseline,
  Box,
  Paper,
  Typography,
  Avatar,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import ReCAPTCHA from "react-google-recaptcha";

export default function LoginPage() {
  const theme = useTheme();
  const isSmDown = useMediaQuery(theme.breakpoints.down("sm"));
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const recaptchaRef = useRef<ReCAPTCHA>(null);
  const { login } = useAuth();

  const isMounted = React.useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recaptchaToken) {
      if (isMounted.current) setError("Por favor, complete a verificação 'Não sou um robô'.");
      return;
    }
    if (isMounted.current) {
      setError(null);
      setLoading(true);
    }
    try {
      const result = await login(username, password, recaptchaToken);
      if (result.success && isMounted.current) {
        navigate("/dashboard");
      } else if (isMounted.current) {
        setError(result.error || "Falha no login.");
      }
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || "Erro desconhecido. Verifique suas credenciais e o reCAPTCHA.";
      if (isMounted.current) setError(errorMsg);
      recaptchaRef.current?.reset();
      setRecaptchaToken(null);
    } finally {
      if (isMounted.current) setLoading(false);
    }
  };

  // full-page background (gradiente + image)
  const pageBackground = {
    backgroundImage: `linear-gradient(135deg, ${theme.palette.primary.dark}88 0%, ${theme.palette.secondary.main}33 100%), url('https://source.unsplash.com/collection/190727/1600x900')`,
    backgroundSize: "cover",
    backgroundPosition: "center",
  };

  return (
    <>
      <CssBaseline />
      <Box sx={{ minHeight: "100vh", display: "flex", ...pageBackground }}>
        {/* HERO - left side. On md+ it takes more space so the form moves toward center */}
        <Box
          sx={{
            flex: { xs: 0, md: 2 },
            display: { xs: "none", md: "flex" },
            alignItems: "center",
            justifyContent: "flex-start",
            p: { md: 8, lg: 12 },
            color: "common.white",
          }}
        >
          <Box sx={{ maxWidth: 640, ml: { md: 6, lg: 10 } }}>
            <Typography variant="h3" sx={{ fontWeight: 800, mb: 1, color: "rgba(255,255,255,0.95)" }}>
              Bem-vindo ao
            </Typography>
            <Typography variant="h2" sx={{ fontWeight: 900, mb: 2, color: "rgba(255,255,255,0.95)" }}>
              TAF ON
            </Typography>
            <Typography variant="h6" sx={{ color: "rgba(255,255,255,0.88)", maxWidth: 520 }}>
              Gerencie Testes de Avaliação Física e relatórios com facilidade. Faça login para acessar seu painel.
            </Typography>
          </Box>
        </Box>

        {/* FORM AREA - takes less space so it sits closer to center */}
        <Box
          sx={{
            flex: { xs: 1, md: 1 },
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            p: { xs: 3, md: 6 },
          }}
        >
          <Paper
            elevation={12}
            sx={{
              width: "100%",
              maxWidth: 420,
              borderRadius: 3,
              px: { xs: 3, sm: 4 },
              py: { xs: 4, sm: 6 },
              boxShadow: `0 20px 50px ${theme.palette.primary.dark}33`,
              bgcolor: "background.paper",
              transform: { md: "translateX(-30px)" }, // nudge left a bit toward center
            }}
          >
            
            <Box sx={{ mt: 3 }}>
              <LoginForm
                username={username}
                setUsername={setUsername}
                password={password}
                setPassword={setPassword}
                recaptchaRef={recaptchaRef}
                setRecaptchaToken={setRecaptchaToken}
                error={error}
                loading={loading}
                handleSubmit={handleSubmit}
              />
            </Box>

            <Box sx={{ mt: 3, textAlign: "center" }}>
              <Typography variant="caption" color="text.secondary">
                © {new Date().getFullYear()} StockWise - Todos os direitos reservados.
              </Typography>
            </Box>
          </Paper>
        </Box>
      </Box>
    </>
  );
}

