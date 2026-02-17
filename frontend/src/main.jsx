import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import CssBaseline from '@mui/material/CssBaseline';

import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { TenantProvider } from './contexts/TenantContext';
import { ThemeProviderWrapper } from './contexts/ThemeContext';
import './index.css';

const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProviderWrapper>
        <AuthProvider>
          <TenantProvider>
            <CssBaseline />
            <App />
          </TenantProvider>
        </AuthProvider>
      </ThemeProviderWrapper>
    </BrowserRouter>
  </React.StrictMode>
);

