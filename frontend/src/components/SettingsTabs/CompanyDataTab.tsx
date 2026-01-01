import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, TextField, Button, Stack, Avatar } from '@mui/material';
import api from "../../lib/api";
import { useAuth } from '../../contexts/AuthContext'; // <-- ADICIONADO

function getPublicUrl(path?: string | null) {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const raw = (import.meta.env.VITE_API_URL as string) || "";
  const apiBase = raw ? raw.replace(/\/api(\/.*)?$/, "").replace(/\/+$/, "") : window.location.origin.replace(/\/+$/, "");
  if (path.startsWith("/")) return `${apiBase}${path}`;
  const normalized = path.replace(/^\/+/, "");
  return `${apiBase}/${normalized}`;
}


export default function CompanyDataTab() {
  const { token } = useAuth(); // <-- ADICIONADO

  const [company, setCompany] = useState({
    company_name: '',
    company_cnpj: '',
    company_address: '',
    company_phone: '',
    company_email: '',
    company_website: '',
    company_logo_path: ''
  });
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // include Authorization header when calling tenant-scoped endpoints
    api.get('/company/', { headers: { Authorization: `Bearer ${token}` } })
      .then(res => {
        setCompany(res.data);
        setLogoPreview(getPublicUrl(res.data.company_logo_path));
      })
      .catch(err => {
        console.error("Falha ao obter dados da empresa:", err);
      });
  }, [token]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setCompany({ ...company, [e.target.name]: e.target.value });
  }

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setLogoFile(file);
      setLogoPreview(URL.createObjectURL(file));
    }
  }

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleSave() {
    const formData = new FormData();
    formData.append('company_name', company.company_name);
    formData.append('company_cnpj', company.company_cnpj);
    formData.append('company_address', company.company_address);
    formData.append('company_phone', company.company_phone);
    formData.append('company_email', company.company_email);
    formData.append('company_website', company.company_website);
    if (logoFile) {
      formData.append('logo', logoFile);
    }

    // include Authorization header; DON'T set Content-Type (browser sets it for FormData)
    api.put('/company/', formData, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => {
        setCompany(res.data);
        setLogoPreview(getPublicUrl(res.data.company_logo_path));
        setLogoFile(null);
        alert('Dados salvos!');
      })
      .catch(err => {
        console.error('Erro ao salvar dados da empresa:', err);
        alert('Falha ao salvar dados da empresa. Veja console para detalhes.');
      });
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Dados da Empresa</Typography>
      <Stack spacing={2} sx={{ maxWidth: 400 }}>
        <TextField label="Nome da Empresa" name="company_name" value={company.company_name} onChange={handleChange} />
        <TextField label="CNPJ" name="company_cnpj" value={company.company_cnpj} onChange={handleChange} />
        <TextField label="Endereço" name="company_address" value={company.company_address} onChange={handleChange} />
        <TextField label="Telefone/Celular" name="company_phone" value={company.company_phone} onChange={handleChange} />
        <TextField label="Email de Contato" name="company_email" value={company.company_email} onChange={handleChange} />
        <TextField label="Website" name="company_website" value={company.company_website} onChange={handleChange} />
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Logo da empresa
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Avatar
              variant="square"
              src={logoPreview || undefined}
              sx={{ width: 80, height: 80, bgcolor: '#eee', border: '1px solid #ccc' }}
            >
              {(!logoPreview) && <span style={{ fontSize: 18, color: '#aaa' }}>Logo</span>}
            </Avatar>
            <Button variant="outlined" onClick={handleUploadClick}>
              {logoFile ? 'Alterar Logo' : (logoPreview ? 'Trocar Logo' : 'Escolher Logo')}
            </Button>
            <input
              type="file"
              accept="image/*"
              ref={fileInputRef}
              style={{ display: 'none' }}
              onChange={handleLogoChange}
            />
          </Stack>
          <Typography variant="caption" color="textSecondary">
            Imagem PNG ou JPG. O logo aparecerá nos relatórios.
          </Typography>
        </Box>
        <Button variant="contained" color="primary" onClick={handleSave}>Salvar Dados</Button>
      </Stack>
    </Box>
  );
}