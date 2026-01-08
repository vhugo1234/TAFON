import React, { useState } from 'react';
import { Box, TextField, Button, Alert, Typography } from '@mui/material';
import axios from 'axios';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const email = searchParams.get('email') || '';
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [status, setStatus] = useState<{ type: 'idle'|'success'|'error', message?: string}>({ type: 'idle' });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus({ type: 'idle' });
    if (password !== confirm) {
      setStatus({ type: 'error', message: 'As senhas nÃ£o coincidem' });
      return;
    }
    try {
      const res = await axios.post('/api/auth/reset-password', { token, email, password });
      setStatus({ type: 'success', message: 'Senha alterada com sucesso. VocÃª serÃ¡ redirecionado.' });
      setTimeout(() => navigate('/login'), 1500);
    } catch (err: any) {
      setStatus({ type: 'error', message: err.response?.data?.error || 'Erro ao redefinir senha' });
    }
  };

  return (
    <Box component="form" onSubmit={submit} sx={{ maxWidth: 480, mx: 'auto', p: 3 }}>
      <Typography variant="h5" mb={2}>Redefinir senha</Typography>
      {status.type === 'success' && <Alert severity="success" sx={{ mb: 2 }}>{status.message}</Alert>}
      {status.type === 'error' && <Alert severity="error" sx={{ mb: 2 }}>{status.message}</Alert>}
      <TextField label="Nova senha" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth required type="password" sx={{ mb: 2 }} />
      <TextField label="Confirme a senha" value={confirm} onChange={(e) => setConfirm(e.target.value)} fullWidth required type="password" />
      <Button type="submit" variant="contained" sx={{ mt: 2 }}>Alterar senha</Button>
    </Box>
  );
}

