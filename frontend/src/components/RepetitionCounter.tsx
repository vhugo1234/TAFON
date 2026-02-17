// frontend/src/components/RepetitionCounter.tsx

import React, { useState, useEffect } from 'react';
import { Box, Typography, Stack, IconButton, Paper, Button } from '@mui/material';
import { Add, Remove } from '@mui/icons-material';

interface RepetitionCounterProps {
  initialValue?: number;
  onValueChange?: (value: number) => void;
  minValue?: number;
  maxValue?: number;
}

export default function RepetitionCounter({ 
  initialValue = 0,
  onValueChange,
  minValue = 0,
  maxValue = 9999
}: RepetitionCounterProps) {
  const [count, setCount] = useState(initialValue);

  useEffect(() => {
    if (onValueChange) {
      onValueChange(count);
    }
  }, [count, onValueChange]);

  // Atalhos de teclado
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowUp' || e.key === '+') {
        e.preventDefault();
        increment(1);
      } else if (e.key === 'ArrowDown' || e.key === '-') {
        e.preventDefault();
        decrement(1);
      } else if (e.key === 'PageUp') {
        e.preventDefault();
        increment(10);
      } else if (e.key === 'PageDown') {
        e.preventDefault();
        decrement(10);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [count]);

  const increment = (amount: number) => {
    setCount(prev => Math.min(prev + amount, maxValue));
  };

  const decrement = (amount: number) => {
    setCount(prev => Math.max(prev - amount, minValue));
  };

  const reset = () => {
    setCount(0);
  };

  return (
    <Paper elevation={3} sx={{ p: 3, textAlign: 'center', bgcolor: 'success.50' }}>
      <Typography variant="h6" gutterBottom color="success.main" fontWeight={600}>
        Contador de Repeticoes
      </Typography>
      
      <Box 
        sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          my: 3,
          p: 4,
          bgcolor: 'white',
          borderRadius: 2,
          boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.1)'
        }}
      >
        <Typography 
          variant="h1" 
          fontWeight={700}
          sx={{ 
            fontFamily: 'monospace',
            color: 'success.main',
            fontSize: { xs: '4rem', sm: '6rem', md: '8rem' }
          }}
        >
          {count}
        </Typography>
      </Box>

      {/* Botões rápidos */}
      <Stack direction="row" spacing={1} justifyContent="center" sx={{ mb: 2 }}>
        <Button
          variant="outlined"
          size="small"
          onClick={() => decrement(10)}
          disabled={count < 10}
        >
          -10
        </Button>
        <Button
          variant="outlined"
          size="small"
          onClick={() => decrement(1)}
          disabled={count === minValue}
        >
          -1
        </Button>
        <Button
          variant="contained"
          size="small"
          onClick={reset}
          sx={{ minWidth: 80 }}
        >
          Zerar
        </Button>
        <Button
          variant="outlined"
          size="small"
          onClick={() => increment(1)}
          disabled={count === maxValue}
        >
          +1
        </Button>
        <Button
          variant="outlined"
          size="small"
          onClick={() => increment(10)}
          disabled={count > maxValue - 10}
        >
          +10
        </Button>
      </Stack>

      {/* Botões principais */}
      <Stack direction="row" spacing={2} justifyContent="center">
        <IconButton 
          onClick={() => decrement(1)}
          color="error"
          disabled={count === minValue}
          sx={{ 
            bgcolor: 'white',
            '&:hover': { bgcolor: 'grey.100' },
            width: 80,
            height: 80
          }}
        >
          <Remove sx={{ fontSize: 48 }} />
        </IconButton>

        <IconButton 
          onClick={() => increment(1)}
          color="success"
          disabled={count === maxValue}
          sx={{ 
            bgcolor: 'white',
            '&:hover': { bgcolor: 'grey.100' },
            width: 80,
            height: 80
          }}
        >
          <Add sx={{ fontSize: 48 }} />
        </IconButton>
      </Stack>

      <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
        Use as setas do teclado ou + - para incrementar
      </Typography>
      <Typography variant="caption" color="text.secondary">
        Page Up/Down para +/-10
      </Typography>
    </Paper>
  );
}
