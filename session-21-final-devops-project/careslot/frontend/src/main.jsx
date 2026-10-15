import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api.js';
import './styles.css';

const STATUSES = ['SCHEDULED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED', 'NO_SHOW'];
const LABEL = { SCHEDULED: 'Scheduled', CHECKED_IN: 'Checked in', COMPLETED: 'Completed', CANCELLED: 'Cancelled', NO_SHOW: 'No-show' };
// Which actions the front desk can take from each status.
const NEXT = {
  SCHEDULED: [['CHECKED_IN', 'Check in'], ['CANCELLED', 'Cancel'], ['NO_SHOW', 'No-show']],
  CHECKED_IN: [['COMPLETED', 'Complete']],
  COMPLETED: [],
  CANCELLED: [['SCHEDULED', 'Restore']],
  NO_SHOW: [['SCHEDULED', 'Restore']],
};

const pad = (n) => String(n).padStart(2, '0');
const toLocalInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const nextSlot = () => { const d = new Date(); d.setMinutes(d.getMinutes() < 30 ? 30 : 60, 0, 0); return toLocalInput(d); };
const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const fmtDay = (iso) => new Date(iso).toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' });
const initials = (name) => name.replace(/^Dr\.?\s*/i, '').split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();

function Kpi({ label, value, hint, tone }) {
  return (
    <div className={`kpi ${tone || ''}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      <span className="kpi-hint">{hint}</span>
    </div>
  );
}

function Modal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
        </header>
        {children}
      </div>
    </div>
  );
}

function BookingForm({ doctors, onDone, onClose }) {
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setSaving(true); setError('');
    try {
      await api.book({
        doctor_id: Number(f.get('doctor_id')),
        patient_name: f.get('patient_name'),
        patient_phone: f.get('patient_phone'),
        reason: f.get('reason') || 'General consultation',
        scheduled_at: new Date(f.get('scheduled_at')).toISOString(),
        duration_minutes: Number(f.get('duration_minutes')),
      });
      onDone('Appointment booked');
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  };
  const active = doctors.filter((d) => d.active);
  return (
    <Modal title="Book appointment" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>Patient name<input name="patient_name" required minLength={2} placeholder="e.g. Riya Patil" autoFocus /></label>
        <label>Phone<input name="patient_phone" required placeholder="+91 98765 43210" pattern="\+?[0-9 \-]{7,20}" /></label>
        <label className="span-2">Doctor
          <select name="doctor_id" required>
            {active.map((d) => <option key={d.id} value={d.id}>{d.name} · {d.specialty}</option>)}
          </select>
        </label>
        <label>Date &amp; time<input name="scheduled_at" type="datetime-local" required defaultValue={nextSlot()} /></label>
        <label>Duration
          <select name="duration_minutes" defaultValue="20">
            {[10, 15, 20, 30, 45, 60].map((m) => <option key={m} value={m}>{m} min</option>)}
          </select>
        </label>
        <label className="span-2">Reason for visit<input name="reason" placeholder="General consultation" maxLength={200} /></label>
        {error && <p className="form-error span-2" role="alert">{error}</p>}
        <div className="form-actions span-2">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={saving || !active.length}>{saving ? 'Booking…' : 'Book slot'}</button>
        </div>
      </form>
    </Modal>
  );
}

function DoctorForm({ onDone, onClose }) {
  const [error, setError] = useState('');
  const submit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api.addDoctor({ name: f.get('name'), specialty: f.get('specialty'), room: f.get('room') });
      onDone('Doctor added');
    } catch (err) { setError(err.message); }
  };
  return (
    <Modal title="Add doctor" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label className="span-2">Full name<input name="name" required minLength={2} placeholder="Dr. Meera Joshi" autoFocus /></label>
        <label>Specialty<input name="specialty" required minLength={2} placeholder="Cardiology" /></label>
        <label>Room<input name="room" maxLength={20} placeholder="301" /></label>
        {error && <p className="form-error span-2" role="alert">{error}</p>}
        <div className="form-actions span-2">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary">Add doctor</button>
        </div>
      </form>
    </Modal>
  );
}

function AppointmentsView({ appointments, doctors, filters, setFilters, onAction, onDelete, loading }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Appointments</h2>
        <div className="filters">
          <select aria-label="Filter by doctor" value={filters.doctor_id} onChange={(e) => setFilters({ ...filters, doctor_id: e.target.value })}>
            <option value="">All doctors</option>
            {doctors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <input aria-label="Filter by day" type="date" value={filters.on} onChange={(e) => setFilters({ ...filters, on: e.target.value })} />
        </div>
      </div>
      <div className="chips" role="tablist">
        {['', ...STATUSES].map((s) => (
          <button key={s || 'ALL'} role="tab" aria-selected={filters.status === s}
            className={`chip ${filters.status === s ? 'on' : ''}`} onClick={() => setFilters({ ...filters, status: s })}>
            {s ? LABEL[s] : 'All'}
          </button>
        ))}
      </div>
      {loading ? <p className="empty">Loading appointments…</p> : appointments.length === 0 ? (
        <p className="empty">No appointments match these filters.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>When</th><th>Patient</th><th>Doctor</th><th>Reason</th><th>Status</th><th aria-label="Actions" /></tr></thead>
            <tbody>
              {appointments.map((a) => (
                <tr key={a.id}>
                  <td data-label="When"><strong>{fmtTime(a.scheduled_at)}</strong><span className="sub">{fmtDay(a.scheduled_at)} · {a.duration_minutes} min</span></td>
                  <td data-label="Patient">{a.patient_name}<span className="sub">{a.patient_phone}</span></td>
                  <td data-label="Doctor">{a.doctor_name}<span className="sub">{a.specialty}</span></td>
                  <td data-label="Reason">{a.reason}</td>
                  <td data-label="Status"><span className={`badge ${a.status.toLowerCase()}`}>{LABEL[a.status]}</span></td>
                  <td className="actions">
                    {NEXT[a.status].map(([to, text]) => (
                      <button key={to} className={`btn small ${to === 'CANCELLED' || to === 'NO_SHOW' ? 'ghost' : 'soft'}`} onClick={() => onAction(a, to)}>{text}</button>
                    ))}
                    <button className="icon-btn" title="Delete" aria-label={`Delete appointment for ${a.patient_name}`} onClick={() => onDelete(a)}>🗑</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function DoctorsView({ doctors, stats, onToggle }) {
  const load = Object.fromEntries((stats?.byDoctor || []).map((d) => [d.doctor_id, d.appointments]));
  const max = Math.max(1, ...Object.values(load));
  return (
    <section className="panel">
      <div className="panel-head"><h2>Doctors</h2><span className="muted">{doctors.length} on staff</span></div>
      <div className="doctor-grid">
        {doctors.map((d) => (
          <article key={d.id} className={`doctor ${d.active ? '' : 'off'}`}>
            <div className="avatar">{initials(d.name)}</div>
            <div className="doctor-body">
              <h3>{d.name}</h3>
              <p className="muted">{d.specialty}{d.room ? ` · Room ${d.room}` : ''}</p>
              <div className="bar" aria-label={`${load[d.id] || 0} appointments`}><span style={{ width: `${((load[d.id] || 0) / max) * 100}%` }} /></div>
              <p className="sub">{load[d.id] || 0} appointments</p>
            </div>
            <button className="btn small ghost" onClick={() => onToggle(d)}>{d.active ? 'Pause' : 'Resume'}</button>
          </article>
        ))}
      </div>
    </section>
  );
}

function App() {
  const [view, setView] = useState('appointments');
  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [stats, setStats] = useState(null);
  const [filters, setFilters] = useState({ status: '', doctor_id: '', on: '' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      const [docs, appts, s] = await Promise.all([api.doctors(), api.appointments(filters), api.stats()]);
      setDoctors(docs); setAppointments(appts); setStats(s);
    } catch (e) {
      setError(e.message === 'Failed to fetch' ? 'Cannot reach the CareSlot API' : e.message);
    } finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!toast) return undefined; const t = setTimeout(() => setToast(''), 2600); return () => clearTimeout(t); }, [toast]);

  const run = async (fn, message) => {
    try { await fn(); setToast(message); } catch (e) { setToast(e.message); }
    load();
  };
  const done = (message) => { setModal(null); setToast(message); load(); };

  const todayLabel = useMemo(() => new Date().toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' }), []);
  const upcoming = appointments.filter((a) => a.status === 'SCHEDULED' && new Date(a.scheduled_at) > new Date()).slice(0, 4);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">+</span><div><strong>CareSlot</strong><small>Clinic appointments</small></div></div>
        <nav>
          <button className={view === 'appointments' ? 'active' : ''} onClick={() => setView('appointments')}>📅 Appointments</button>
          <button className={view === 'doctors' ? 'active' : ''} onClick={() => setView('doctors')}>🩺 Doctors</button>
        </nav>
        <div className="pipeline">
          <span className="dot" /> <div><strong>Pipeline</strong><small>pytest → Trivy → GHCR → Helm</small></div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><p className="muted">{todayLabel}</p><h1>{view === 'appointments' ? 'Front desk' : 'Clinic staff'}</h1></div>
          <div className="top-actions">
            <button className="btn ghost" onClick={() => setModal('doctor')}>+ Doctor</button>
            <button className="btn primary" onClick={() => setModal('book')} disabled={!doctors.length}>+ Book appointment</button>
          </div>
        </header>

        {error && <div className="alert" role="alert"><strong>Backend unavailable.</strong> {error}. <button className="link" onClick={load}>Retry</button></div>}

        <section className="kpis">
          <Kpi label="Today" value={stats?.today ?? '–'} hint="appointments today" tone="teal" />
          <Kpi label="Upcoming" value={stats?.scheduled ?? '–'} hint="scheduled" />
          <Kpi label="In clinic" value={stats?.checkedIn ?? '–'} hint="checked in now" tone="amber" />
          <Kpi label="Completed" value={stats?.completed ?? '–'} hint={`${stats?.cancelled ?? 0} cancelled · ${stats?.noShow ?? 0} no-show`} tone="green" />
        </section>

        <div className="grid">
          {view === 'appointments' ? (
            <AppointmentsView appointments={appointments} doctors={doctors} filters={filters} setFilters={setFilters} loading={loading}
              onAction={(a, to) => run(() => api.updateAppointment(a.id, { status: to }), `${a.patient_name}: ${LABEL[to]}`)}
              onDelete={(a) => window.confirm(`Delete appointment for ${a.patient_name}?`) && run(() => api.deleteAppointment(a.id), 'Appointment deleted')} />
          ) : (
            <DoctorsView doctors={doctors} stats={stats}
              onToggle={(d) => run(() => api.updateDoctor(d.id, { active: !d.active }), `${d.name} ${d.active ? 'paused' : 'resumed'}`)} />
          )}
          <aside className="panel side">
            <h2>Next up</h2>
            {upcoming.length === 0 ? <p className="empty small">Nothing scheduled.</p> : (
              <ul className="feed">
                {upcoming.map((a) => (
                  <li key={a.id}><span className="time">{fmtTime(a.scheduled_at)}</span><div><strong>{a.patient_name}</strong><small>{a.doctor_name}</small></div></li>
                ))}
              </ul>
            )}
            <h2>Workload</h2>
            <ul className="load">
              {(stats?.byDoctor || []).map((d) => <li key={d.doctor_id}><span>{d.doctor_name.replace('Dr. ', '')}</span><b>{d.appointments}</b></li>)}
            </ul>
          </aside>
        </div>
      </main>

      {modal === 'book' && <BookingForm doctors={doctors} onDone={done} onClose={() => setModal(null)} />}
      {modal === 'doctor' && <DoctorForm onDone={done} onClose={() => setModal(null)} />}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
