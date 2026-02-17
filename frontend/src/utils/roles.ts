// Utilitários de roles — mapeia valores usados no sistema para chaves canônicas
// e exporta grupos/ helpers para checagem de permissões.

export type RoleKey =
  | 'ADMIN'            // Administrador Geral
  | 'COORD_GERAL'      // Coordenador Geral
  | 'COORD_EF'         // Coordenador de Educação Física
  | 'AVALIADOR_EF'     // Avaliador de Educação Física
  | 'APOIO'
  | 'TEC_AV'
  | 'VOLANTES'
  | 'FISCAIS'
  | 'OUTROS'
  | string; // permite extensibilidade

// Mapeamento dos valores que você forneceu -> chaves canônicas
// Observe que keys para ids são strings ('1','2',...) porque role_id pode vir como número ou string.
export const ROLE_VALUE_TO_KEY: Record<string, RoleKey> = {
  // ids
  '1': 'ADMIN',
  '2': 'COORD_GERAL',
  '3': 'COORD_EF',
  '4': 'AVALIADOR_EF',
  '5': 'APOIO',
  '6': 'TEC_AV',
  '7': 'VOLANTES',
  '8': 'FISCAIS',
  'other': 'OUTROS',

  // labels (caso o backend retorne label em vez de id)
  'Administrador Geral': 'ADMIN',
  'Coordenador Geral': 'COORD_GERAL',
  'Coordenador de Educação Física': 'COORD_EF',
  'Avaliador de Educação Física': 'AVALIADOR_EF',
  'Apoio': 'APOIO',
  'Técnico de AudioVisual': 'TEC_AV',
  'Volantes': 'VOLANTES',
  'Fiscais': 'FISCAIS',
  'Outros': 'OUTROS',

  // Sinônimos / claims que o backend pode emitir
  'SUPERUSER': 'ADMIN',
  'ADMIN': 'ADMIN',
  'ADMINISTRADOR': 'ADMIN',
  'ADMINISTRADOR GERAL': 'ADMIN',
  'USER': 'OUTROS', // mapeamento genérico para usuários sem privilégios
};

// Labels amigáveis se precisar exibir em UI
export const ROLE_KEY_TO_LABEL: Record<string, string> = {
  ADMIN: 'Administrador Geral',
  COORD_GERAL: 'Coordenador Geral',
  COORD_EF: 'Coordenador de Educação Física',
  AVALIADOR_EF: 'Avaliador de Educação Física',
  APOIO: 'Apoio',
  TEC_AV: 'Técnico de AudioVisual',
  VOLANTES: 'Volantes',
  FISCAIS: 'Fiscais',
  OUTROS: 'Outros',
};

// Grupos/roles usados para checagens rápidas
export const FULL_ACCESS: RoleKey[] = ['ADMIN', 'COORD_GERAL', 'COORD_EF'];
export const FINANCIAL_ACCESS: RoleKey[] = ['ADMIN', 'COORD_GERAL'];
export const EVALUATOR_ROLES: RoleKey[] = ['AVALIADOR_EF'];

// Normaliza um único valor (pode ser '1', 1, 'Administrador Geral', 'ADMIN', etc.)
export function resolveRoleValueToKey(value?: string | number | null): RoleKey | null {
  if (value === undefined || value === null) return null;
  const vStr = String(value);

  // lookup direto por valor exato
  if (Object.prototype.hasOwnProperty.call(ROLE_VALUE_TO_KEY, vStr)) {
    return ROLE_VALUE_TO_KEY[vStr];
  }

  // tentar lookup por lowercase / uppercase (cobre variações)
  const lower = vStr.toLowerCase();
  const upper = vStr.toUpperCase();
  if (Object.prototype.hasOwnProperty.call(ROLE_VALUE_TO_KEY, lower)) {
    return ROLE_VALUE_TO_KEY[lower];
  }
  if (Object.prototype.hasOwnProperty.call(ROLE_VALUE_TO_KEY, upper)) {
    return ROLE_VALUE_TO_KEY[upper];
  }

  // se já for uma chave canônica conhecida (ROLE_KEY_TO_LABEL contém chaves)
  if (Object.prototype.hasOwnProperty.call(ROLE_KEY_TO_LABEL, vStr)) {
    return vStr as RoleKey;
  }
  if (Object.prototype.hasOwnProperty.call(ROLE_KEY_TO_LABEL, upper)) {
    return upper as RoleKey;
  }

  // fallback: retornar value em maiúsculas como key genérica
  return upper as RoleKey;
}

// Normaliza um array de roles vindas do backend/token para chaves canônicas e dedupe
export function normalizeRoles(input?: Array<string | number> | string | number | null): RoleKey[] {
  if (!input) return [];
  const arr = Array.isArray(input) ? input : [input];
  const mapped = arr
    .map(v => resolveRoleValueToKey(v))
    .filter((v): v is RoleKey => !!v);
  return Array.from(new Set(mapped));
}