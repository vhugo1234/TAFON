import React, { useState, useMemo } from 'react';
import { Box, Paper, Tabs, Tab, Typography, Stack, IconButton, Tooltip } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useNavigate, useSearchParams } from 'react-router-dom';
import UserManagementTab from '../components/SettingsTabs/UserManagementTab';
import AppearanceTab from '../components/SettingsTabs/AppearanceTab';
import CompanyDataTab from '../components/SettingsTabs/CompanyDataTab';
import FinancialTab from '../components/SettingsTabs/FinancialTab';
import LogoutButton from '../components/LogoutButton';

export default function SettingsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Lê o tab da query param (ex: ?tab=2). Fallback para 0.
  const initialTab = useMemo(() => {
    const raw = searchParams.get('tab');
    const n = raw ? Number(raw) : NaN;
    return Number.isInteger(n) && n >= 0 ? n : 0;
  }, [searchParams]);

  const [currentTab, setCurrentTab] = useState<number>(initialTab);

  // Quando o usuário muda de aba, atualiza o estado e a query param
  const handleChange = (_: React.SyntheticEvent, v: number) => {
    setCurrentTab(v);
    const params = new URLSearchParams(searchParams);
    params.set('tab', String(v));
    setSearchParams(params, { replace: true }); // replace evita criar histórico extra
  };

  return (
    <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3, minHeight: '80vh' }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Tooltip title="Voltar ao Dashboard">
            <IconButton onClick={() => navigate('/dashboard')} color="primary">
              <ArrowBack />
            </IconButton>
          </Tooltip>
          <Typography variant="h4" fontWeight="bold">
            Configurações e Gerenciamento
          </Typography>
        </Stack>
        <LogoutButton />
      </Stack>

      <Tabs
        value={currentTab}
        onChange={handleChange}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 3 }}
      >
        <Tab label="Gerenciar Usuários" />
        <Tab label="Aparência" />
        <Tab label="Dados da Empresa" />
        <Tab label="Financeiro" />
      </Tabs>

      <Box>
        {currentTab === 0 && <UserManagementTab />}
        {currentTab === 1 && <AppearanceTab />}
        {currentTab === 2 && <CompanyDataTab />}
        {currentTab === 3 && <FinancialTab />}
      </Box>
    </Paper>
  );
}
