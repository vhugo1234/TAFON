// frontend/src/pages/TenantHome.tsx

import React from 'react';
import { Box, Typography, Container } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
// Importe seus componentes TAF CORE aqui (ex: Menu lateral do TAF)

const TenantHome: React.FC = () => {
  const { user } = useAuth();
  
  // Exemplo de extração do nome do tenant (se estiver disponível no user object)
  const tenantName = user?.schemaName || 'Seu Sistema TAF'; 

  return (
    <Container maxWidth="xl" sx={{ mt: 4 }}>
      <Box sx={{ py: 4, px: 3, border: '1px dashed grey' }}>
        <Typography variant="h3" component="h1" gutterBottom>
          Bem-vindo, {user?.email || 'Usuário'}!
        </Typography>
        <Typography variant="h5" color="text.secondary" paragraph>
          Você está no ambiente do tenant: **{tenantName}**
        </Typography>

        <Typography variant="body1" sx={{ mt: 3 }}>
          Este é o painel principal do sistema TAF para o seu tenant. 
          Aqui você verá os links para Eventos, Candidatos, Lançamento de Desempenho e Resultados.
        </Typography>
        
        {/* Você pode substituir este Box pelo componente de layout do Tenant (Sidebar, etc.) */}
      </Box>
      
      {/* Aqui é onde a navegação principal do TAF CORE começará (TAFEventsPage, etc.) */}
      {/* Por enquanto, ele apenas exibe a mensagem de boas-vindas */}
    </Container>
  );
};

export default TenantHome;