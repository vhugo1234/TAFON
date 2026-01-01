import React from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { CircularProgress, Box } from '@mui/material';

import { useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
// Importação do Dashboard Principal
import AdminDasheboard from './pages/AdminDashboard'; 
import PublicRegisterPage from './pages/PublicRegisterPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import TenantHome from './pages/TenantHome';
import AdminClientsTab from './components/Admin/AdminClientsTab';

// --- Componentes de Guarda (Sem Alteração na Lógica) ---

function LoadingScreen() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 12 }}>
      <CircularProgress />
    </Box>
  );
}

function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function RequireSuperuser({ children }: { children: JSX.Element }) {
  const { isAuthenticated, loading, isSuperuser } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!isSuperuser) return <Navigate to="/home" replace />;
  return children;
}

function HomeRedirect() {
  const { isAuthenticated, loading, isSuperuser } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (isSuperuser) return <Navigate to="/admin" replace />;
  return <Navigate to="/home" replace />;
}

function LoginRouteGuard() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <LoginPage />;
}

// ------------------------------------------------------------------
// APP PRINCIPAL: Define as rotas usando o padrão de Layouts
// ------------------------------------------------------------------
const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginRouteGuard />} />

      {/* Rotas Públicas */}
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/cadastro" element={<PublicRegisterPage />} />
      
      {/* Rota Protegida do Superusuário (Admin Layout) */}
      <Route
        path="/admin"
        element={
          <RequireSuperuser>
            {/* O AdminDashboard é o layout pai. Ele contém o <Outlet /> */}
            <AdminDasheboard /> 
          </RequireSuperuser>
        }
      >
        {/* Rotas FILHAS do Admin. O *AdminDasheboard* renderiza o conteúdo aqui. */}
        <Route index element={<Navigate to="clients" replace />} /> {/* /admin -> /admin/clients */}
        <Route path="clients" element={<AdminClientsTab />} /> {/* /admin/clients */}
        {/* Adicione outras sub-rotas: <Route path="users" element={<AdminUsersTab />} /> */}
      </Route>

      {/* Rota Protegida do Usuário Comum (Tenant) */}
      <Route
        path="/home"
        element={
          <RequireAuth>
            <TenantHome />
          </RequireAuth>
        }
      />

      {/* Catch-all: send to home logic */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;