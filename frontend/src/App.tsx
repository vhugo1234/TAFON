import React from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { CircularProgress, Box } from '@mui/material';

import { useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
// ImportaÃ§Ã£o do Dashboard Principal
import AdminDasheboard from './pages/AdminDashboard'; 
import PublicRegisterPage from './pages/PublicRegisterPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import TenantHome from './pages/TenantHome';
import AdminClientsTab from './components/Admin/AdminClientsTab';
import SettingsPage from './pages/SettingsPage';

// MÃ³dulos TAF
import TAFEventsPage from './pages/TAFEventsPage';
import TAFExercisesPage from './pages/TAFExercisesPage';
import TAFCandidatesPage from './pages/TAFCandidatesPage';
import TAFGroupingPage from './pages/TAFGroupingPage';
import TAFBatchViewPage from './pages/TAFBatchViewPage';
import TAFEvaluatorsPage from './pages/TAFEvaluatorsPage';
import TAFExecutionPage from './pages/TAFExecutionPage';
import TAFFieldEvaluationPage from './pages/TAFFieldEvaluationPage';
import TAFResultsPage from './pages/TAFResultsPage';

// --- Componentes de Guarda (Sem AlteraÃ§Ã£o na LÃ³gica) ---

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
// APP PRINCIPAL: Define as rotas usando o padrÃ£o de Layouts
// ------------------------------------------------------------------
const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginRouteGuard />} />

      {/* Rotas PÃºblicas */}
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/cadastro" element={<PublicRegisterPage />} />
      
      {/* Rota Protegida do SuperusuÃ¡rio (Admin Layout) */}
      <Route
        path="/admin"
        element={
          <RequireSuperuser>
            {/* O AdminDashboard Ã© o layout pai. Ele contÃ©m o <Outlet /> */}
            <AdminDasheboard /> 
          </RequireSuperuser>
        }
      >
        {/* Rotas FILHAS do Admin. O *AdminDasheboard* renderiza o conteÃºdo aqui. */}
        <Route index element={<Navigate to="clients" replace />} /> {/* /admin -> /admin/clients */}
        <Route path="clients" element={<AdminClientsTab />} /> {/* /admin/clients */}
        {/* Adicione outras sub-rotas: <Route path="users" element={<AdminUsersTab />} /> */}
      </Route>

      {/* Rota Protegida do UsuÃ¡rio Comum (Tenant) */}
      <Route
        path="/home"
        element={
          <RequireAuth>
            <TenantHome />
          </RequireAuth>
        }
      />

      {/* ConfiguraÃ§Ãµes do Sistema */}
      <Route
        path="/settings"
        element={
          <RequireAuth>
            <SettingsPage />
          </RequireAuth>
        }
      />

      {/* MÃ³dulos TAF - Rotas Protegidas */}
      <Route
        path="/taf/events"
        element={
          <RequireAuth>
            <TAFEventsPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/exercises"
        element={
          <RequireAuth>
            <TAFExercisesPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/evaluators"
        element={
          <RequireAuth>
            <TAFEvaluatorsPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/candidates"
        element={
          <RequireAuth>
            <TAFCandidatesPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/grouping"
        element={
          <RequireAuth>
            <TAFGroupingPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/batch/:batchName"
        element={
          <RequireAuth>
            <TAFBatchViewPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/exercises/:exerciseId/launch"
        element={
          <RequireAuth>
            <TAFExecutionPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/exercises/:exerciseId/execution"
        element={
          <RequireAuth>
            <TAFExecutionPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/exercises/:exerciseId/field"
        element={
          <RequireAuth>
            <TAFFieldEvaluationPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/results"
        element={
          <RequireAuth>
            <TAFResultsPage />
          </RequireAuth>
        }
      />

      <Route
        path="/taf/events/:eventId/batches"
        element={
          <RequireAuth>
            <TAFBatchViewPage />
          </RequireAuth>
        }
      />

      {/* Catch-all: send to home logic */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;

