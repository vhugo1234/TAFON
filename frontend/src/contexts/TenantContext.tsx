import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface TenantContextType {
  tenantId: number | null;
  schemaName: string | null;
  tenantName: string | null;
  logoUrl: string | null;
  setTenantData: (data: {
    tenantId?: number | null;
    schemaName?: string | null;
    tenantName?: string | null;
    logoUrl?: string | null;
  }) => void;
  clearTenantData: () => void;
}

const TenantContext = createContext<TenantContextType>({
  tenantId: null,
  schemaName: null,
  tenantName: null,
  logoUrl: null,
  setTenantData: () => {},
  clearTenantData: () => {},
});

export function useTenant() {
  return useContext(TenantContext);
}

interface TenantProviderProps {
  children: ReactNode;
}

export function TenantProvider({ children }: TenantProviderProps) {
  const [tenantId, setTenantId] = useState<number | null>(null);
  const [schemaName, setSchemaName] = useState<string | null>(null);
  const [tenantName, setTenantName] = useState<string | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);

  // Carregar dados do tenant do localStorage na inicialização
  useEffect(() => {
    try {
      const storedTenantId = localStorage.getItem('tenant_id');
      const storedSchemaName = localStorage.getItem('schema_name');
      const storedTenantName = localStorage.getItem('tenant_name');
      const storedLogoUrl = localStorage.getItem('logo_url');

      if (storedTenantId) setTenantId(parseInt(storedTenantId, 10));
      if (storedSchemaName) setSchemaName(storedSchemaName);
      if (storedTenantName) setTenantName(storedTenantName);
      if (storedLogoUrl) setLogoUrl(storedLogoUrl);
    } catch (error) {
      console.error('Erro ao carregar dados do tenant do localStorage:', error);
    }
  }, []);

  const setTenantData = (data: {
    tenantId?: number | null;
    schemaName?: string | null;
    tenantName?: string | null;
    logoUrl?: string | null;
  }) => {
    try {
      if (data.tenantId !== undefined) {
        setTenantId(data.tenantId);
        if (data.tenantId !== null) {
          localStorage.setItem('tenant_id', data.tenantId.toString());
        } else {
          localStorage.removeItem('tenant_id');
        }
      }

      if (data.schemaName !== undefined) {
        setSchemaName(data.schemaName);
        if (data.schemaName) {
          localStorage.setItem('schema_name', data.schemaName);
        } else {
          localStorage.removeItem('schema_name');
        }
      }

      if (data.tenantName !== undefined) {
        setTenantName(data.tenantName);
        if (data.tenantName) {
          localStorage.setItem('tenant_name', data.tenantName);
        } else {
          localStorage.removeItem('tenant_name');
        }
      }

      if (data.logoUrl !== undefined) {
        setLogoUrl(data.logoUrl);
        if (data.logoUrl) {
          localStorage.setItem('logo_url', data.logoUrl);
        } else {
          localStorage.removeItem('logo_url');
        }
      }
    } catch (error) {
      console.error('Erro ao salvar dados do tenant no localStorage:', error);
    }
  };

  const clearTenantData = () => {
    setTenantId(null);
    setSchemaName(null);
    setTenantName(null);
    setLogoUrl(null);

    try {
      localStorage.removeItem('tenant_id');
      localStorage.removeItem('schema_name');
      localStorage.removeItem('tenant_name');
      localStorage.removeItem('logo_url');
    } catch (error) {
      console.error('Erro ao limpar dados do tenant do localStorage:', error);
    }
  };

  const value: TenantContextType = {
    tenantId,
    schemaName,
    tenantName,
    logoUrl,
    setTenantData,
    clearTenantData,
  };

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
}


