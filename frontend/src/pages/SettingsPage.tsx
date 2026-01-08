import React, { useState } from 'react';
import { Box, Paper, Tabs, Tab, Typography, Stack, IconButton, Tooltip } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import UserManagementTab from '../components/SettingsTabs/UserManagementTab';
import AppearanceTab from '../components/SettingsTabs/AppearanceTab';
import CompanyDataTab from '../components/SettingsTabs/CompanyDataTab';
import LogoutButton from '../components/LogoutButton';

export default function SettingsPage() {
  const [currentTab, setCurrentTab] = useState(0);
  const navigate = useNavigate();
  
  return (
    <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3, minHeight: '80vh' }}>
      {/* Cabeçalho com botões de navegação */}
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
        onChange={(_, v) => setCurrentTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 3 }}
      >
        <Tab label="Gerenciar Usuários" />
        <Tab label="Aparência" />
        <Tab label="Dados da Empresa" />
      </Tabs>
      
      <Box>
        {currentTab === 0 && <UserManagementTab />}
        {currentTab === 1 && <AppearanceTab />}
        {currentTab === 2 && <CompanyDataTab />}
      </Box>
    </Paper>
  );
}

