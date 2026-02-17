// Optional helper functions to call attendance endpoints (uses fetch)
export async function checkin(opts: {
  apiBase?: string;
  eventId: number | string;
  workerId: number | string;
  payload: any;
  getAuthHeaders?: () => Record<string, string>;
}) {
  const { apiBase = "/api/v1", eventId, workerId, payload, getAuthHeaders } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (getAuthHeaders) Object.assign(headers, getAuthHeaders());
  const url = `${apiBase}/event/${encodeURIComponent(eventId)}/worker/${encodeURIComponent(workerId)}/attendance/checkin`;
  const resp = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(txt || `HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function listAttendance(opts: { apiBase?: string; eventId: number | string; getAuthHeaders?: () => Record<string, string> }) {
  const { apiBase = "/api/v1", eventId, getAuthHeaders } = opts;
  const headers: Record<string, string> = {};
  if (getAuthHeaders) Object.assign(headers, getAuthHeaders());
  const resp = await fetch(`${apiBase}/event/${encodeURIComponent(eventId)}/attendance`, { headers });
  if (!resp.ok) throw new Error("Erro ao listar attendance");
  return resp.json();
}

export async function checkout(opts: { apiBase?: string; eventId: number | string; workerId: number | string; attendanceId: number; getAuthHeaders?: () => Record<string, string> }) {
  const { apiBase = "/api/v1", eventId, workerId, attendanceId, getAuthHeaders } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (getAuthHeaders) Object.assign(headers, getAuthHeaders());
  const resp = await fetch(`${apiBase}/event/${encodeURIComponent(eventId)}/worker/${encodeURIComponent(workerId)}/attendance/${attendanceId}/checkout`, { method: "POST", headers });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(txt || "Erro ao checkout");
  }
  return resp.json();
}
