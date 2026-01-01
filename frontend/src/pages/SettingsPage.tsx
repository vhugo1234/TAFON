import React, { useState } from 'react';
import { Box, Paper, Tabs, Tab, Typography } from '@mui/material';
import UserManagementTab from '../components/SettingsTabs/UserManagementTab';
import AppearanceTab from '../components/SettingsTabs/AppearanceTab';
import CompanyDataTab from '../components/SettingsTabs/CompanyDataTab';
// Adicione outras abas conforme necessário

export default function SettingsPage() {
  const [currentTab, setCurrentTab] = useState(0);
  return (
    <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3, minHeight: '80vh' }}>
      <Typography variant="h4" fontWeight="bold" gutterBottom>
        Configurações e Gerenciamento
      </Typography>
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
        {/* Adicione abas extras conforme necessidade */}
      </Tabs>
      <Box>
        {currentTab === 0 && <UserManagementTab />}
        {currentTab === 1 && <AppearanceTab />}
        {currentTab === 2 && <CompanyDataTab />}
      </Box>
    </Paper>
  );
}