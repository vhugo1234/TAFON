// frontend/src/pages/AdminDasheboard.tsx

import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Box, Typography, Container, Tabs, Tab } from '@mui/material';

// Função para mapear o path para o valor da Tab
function a11yProps(index: number) {
  return {
    id: `admin-tab-${index}`,
    'aria-controls': `admin-tabpanel-${index}`,
  };
}

const AdminDasheboard: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Mapeia o caminho atual para o índice da aba
  const currentPath = location.pathname;
  const tabValue = currentPath.startsWith('/admin/clients') ? 'clients' : 'dashboard'; 
  
  // Função que muda a rota ao clicar na aba
  const handleChange = (event: React.SyntheticEvent, newValue: string) => {
    navigate(`/admin/${newValue}`);
  };

  return (
    <Container maxWidth="xl">
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Dashboard Central de Administração
        </Typography>
        
        {/* Navegação entre abas do Admin */}
        <Tabs value={tabValue} onChange={handleChange} aria-label="Navegação do Administrador">
          <Tab label="Clientes/Tenants" value="clients" {...a11yProps(0)} />
          <Tab label="Visão Geral" value="dashboard" {...a11yProps(1)} />
          {/* Adicione outras abas, como "Usuários Centrais", "Logs", etc. */}
        </Tabs>
      </Box>

      {/* Conteúdo específico da rota aninhada é renderizado aqui */}
      <Box sx={{ pt: 2 }}>
        <Outlet />
      </Box>
    </Container>
  );
};

export default AdminDasheboard;