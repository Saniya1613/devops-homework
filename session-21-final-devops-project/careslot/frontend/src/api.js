// Small fetch wrapper. All calls use relative /api paths: nginx (Compose) or the Ingress (Kubernetes)
// routes them to the backend, so the browser never needs the backend's internal hostname.
const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join(', ')
      : data.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  doctors: () => request('/doctors'),
  addDoctor: (body) => request('/doctors', { method: 'POST', body }),
  updateDoctor: (id, body) => request(`/doctors/${id}`, { method: 'PUT', body }),
  appointments: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
    return request(`/appointments${qs ? `?${qs}` : ''}`);
  },
  stats: () => request('/appointments/stats'),
  book: (body) => request('/appointments', { method: 'POST', body }),
  updateAppointment: (id, body) => request(`/appointments/${id}`, { method: 'PUT', body }),
  deleteAppointment: (id) => request(`/appointments/${id}`, { method: 'DELETE' }),
};
