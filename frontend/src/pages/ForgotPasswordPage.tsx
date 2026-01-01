import React, { useState } from 'react';
import { Box, TextField, Button, Alert, Typography } from '@mui/material';
import axios from 'axios';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<{ type: 'idle'|'success'|'error', message?: string}>({ type: 'idle' });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus({ type: 'idle' });
    try {
      // ROTA CORRETA no backend: /api/v1/auth/forgot-password
      const res = await axios.post('/api/v1/auth/forgot-password', { email });
      setStatus({ type: 'success', message: 'Se houver conta, você receberá um e-mail com instruções.' });
    } catch (err: any) {
      setStatus({ type: 'error', message: 'Erro ao enviar. Tente novamente.' });
    }
  };

  return (
    <Box component="form" onSubmit={submit} sx={{ maxWidth: 480, mx: 'auto', p: 3 }}>
      <Typography variant="h5" mb={2}>Esqueceu a senha?</Typography>
      <Typography variant="body2" mb={2}>Informe o e-mail da sua conta e enviaremos instruções.</Typography>
      {status.type === 'success' && <Alert severity="success" sx={{ mb: 2 }}>{status.message}</Alert>}
      {status.type === 'error' && <Alert severity="error" sx={{ mb: 2 }}>{status.message}</Alert>}
      <TextField label="E-mail" value={email} onChange={(e) => setEmail(e.target.value)} fullWidth required />
      <Button type="submit" variant="contained" sx={{ mt: 2 }}>Enviar instruções</Button>
    </Box>
  );
}