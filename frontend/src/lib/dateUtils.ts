/**
 * Pequeno util de datas usado pela UI.
 * - Recebe string ISO (YYYY-MM-DD, YYYY-MM-DDTHH:mm:SSZ, etc.) ou Date.
 * - Retorna string no formato BR "DD/MM/YYYY" ou '' para entradas vazias/inválidas.
 *
 * Uso: import { formatDateBR } from 'src/lib/dateUtils'
 */

export const pad2 = (n: number) => String(n).padStart(2, '0');

/**
 * Formata uma data/ISO para "DD/MM/YYYY".
 * @param input string ISO (YYYY-MM-DD, 2026-01-17T14:00:00Z, etc.) ou Date
 * @returns string formatada "DD/MM/YYYY" ou '' se input falsy/inválido
 */
export function formatDateBR(input?: string | Date | null): string {
  if (!input) return '';

  // Se já for Date
  if (input instanceof Date) {
    if (Number.isNaN(input.getTime())) return '';
    const dd = pad2(input.getDate());
    const mm = pad2(input.getMonth() + 1);
    const yyyy = input.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
  }

  const s = String(input).trim();
  if (!s) return '';

  // 1) data pura YYYY-MM-DD
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (dateOnly) {
    const y = Number(dateOnly[1]);
    const m = Number(dateOnly[2]) - 1;
    const d = Number(dateOnly[3]);
    const dt = new Date(y, m, d);
    if (Number.isNaN(dt.getTime())) return s;
    return `${pad2(dt.getDate())}/${pad2(dt.getMonth() + 1)}/${dt.getFullYear()}`;
  }

  // 2) tenta parsear como Date (covers datetime with T and timezone)
  const parsed = new Date(s);
  if (!Number.isNaN(parsed.getTime())) {
    return `${pad2(parsed.getDate())}/${pad2(parsed.getMonth() + 1)}/${parsed.getFullYear()}`;
  }

  // 3) tentativa de fallback: split por '-' (ex.: "2026-1-7")
  const parts = s.split('-').map(Number);
  if (parts.length >= 3 && parts.every(p => !Number.isNaN(p))) {
    const dt = new Date(parts[0], (parts[1] || 1) - 1, parts[2] || 1);
    if (!Number.isNaN(dt.getTime())) {
      return `${pad2(dt.getDate())}/${pad2(dt.getMonth() + 1)}/${dt.getFullYear()}`;
    }
  }

  // fallback final: retorna original (evita quebrar UI)
  return s;
}