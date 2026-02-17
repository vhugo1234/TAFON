// frontend/src/lib/format.ts
export function padNumber(n: number | string | undefined | null, width: number): string {
  if (n === undefined || n === null) return ''.padStart(width, '0');
  const s = String(n);
  return s.padStart(width, '0');
}

// helper que decide a largura por total de itens (opcional)
export function padNumberByTotal(n: number | string | undefined | null, totalItems: number, minWidth = 3): string {
  const digits = Math.max(minWidth, String(totalItems).length);
  return padNumber(n, digits);
}