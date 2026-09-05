import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const STATUSES = ['new', 'contacted', 'site_visit', 'converted', 'lost'];
const CHANNELS = ['manual', 'dm', 'whatsapp', 'call', 'website'];

export default function Leads({ notify }) {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nl, setNl] = useState({ name: '', contact: '', channel: 'whatsapp', message: '' });

  const reload = () => api.v1Leads().then((r) => setLeads(r || [])).finally(() => setLoading(false));
  useEffect(() => { reload(); }, []);

  const add = async () => {
    if (!nl.contact.trim() && !nl.name.trim()) return notify?.('Add a name or contact', 'error');
    try { await api.v1CreateLead(nl); notify?.('Lead captured'); setNl({ ...nl, name: '', contact: '', message: '' }); reload(); }
    catch { notify?.('Capture failed', 'error'); }
  };
  const setStatus = async (id, status) => {
    try { await api.v1LeadStatus(id, status); reload(); } catch { notify?.('Update failed', 'error'); }
  };

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Pipeline</p>
      <h1 className="font-display text-4xl md:text-5xl mb-5" style={{ fontWeight: 600, lineHeight: 1 }}>Leads.</h1>

      <div className="panel p-5 mb-5">
        <div className="eyebrow mb-3">Capture a lead</div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <label className="block"><span className="label">Name</span><input className="input" value={nl.name} onChange={(e) => setNl({ ...nl, name: e.target.value })} /></label>
          <label className="block"><span className="label">Contact</span><input className="input" value={nl.contact} onChange={(e) => setNl({ ...nl, contact: e.target.value })} placeholder="phone / handle" /></label>
          <label className="block"><span className="label">Channel</span>
            <select className="select" value={nl.channel} onChange={(e) => setNl({ ...nl, channel: e.target.value })}>{CHANNELS.map((c) => <option key={c} value={c}>{hum(c)}</option>)}</select></label>
          <label className="block"><span className="label">Note</span><input className="input" value={nl.message} onChange={(e) => setNl({ ...nl, message: e.target.value })} /></label>
          <button className="btn btn-accent" onClick={add}><Icon name="plus" size={14} /> Add</button>
        </div>
        <p className="text-xs font-mono mt-2" style={{ color: 'var(--faint)' }}>DM/WhatsApp leads auto-capture once Instagram webhooks are connected; add manually meanwhile.</p>
      </div>

      {loading ? <div className="panel p-16 text-center"><Spinner size={24} /></div>
        : leads.length === 0 ? <div className="panel p-10 text-center" style={{ color: 'var(--muted)' }}>No leads yet.</div>
        : <div className="panel p-0" style={{ overflow: 'hidden' }}>
            {leads.map((l) => (
              <div key={l.id} className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{l.name || l.contact || 'Lead'}</div>
                  <div className="text-xs font-mono" style={{ color: 'var(--faint)' }}>{hum(l.channel)} · {l.contact || '—'} · {l.created_at}</div>
                </div>
                <select className="select" style={{ width: 150 }} value={l.status} onChange={(e) => setStatus(l.id, e.target.value)}>
                  {STATUSES.map((s) => <option key={s} value={s}>{hum(s)}</option>)}
                </select>
              </div>
            ))}
          </div>}
    </div>
  );
}
