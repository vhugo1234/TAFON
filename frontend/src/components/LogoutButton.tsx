// frontend/src/components/LogoutButton.tsx
import React from 'react';
import { Button, Tooltip } from '@mui/material';
import { Logout } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

interface LogoutButtonProps {
  variant?: 'text' | 'outlined' | 'contained';
  size?: 'small' | 'medium' | 'large';
  color?: 'inherit' | 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning';
  showText?: boolean;
}

export default function LogoutButton({ 
  variant = 'outlined', 
  size = 'large',
  color = 'error',
  showText = true 
}: LogoutButtonProps) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    if (window.confirm('Deseja realmente sair do sistema?')) {
      logout();
      navigate('/login');
    }
  };

  return (
    <Tooltip title="Sair do sistema">
      <Button
        variant={variant}
        color={color}
        size={size}
        startIcon={<Logout />}
        onClick={handleLogout}
      >
        {showText && 'Sair'}
      </Button>
    </Tooltip>
  );
}
