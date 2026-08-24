import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';

export default function AdminSettings({ notify }) {
  const [me, setMe] = useState(null);
  const [health, setHealth] = useState(null);
  const [brands, setBrands] = useState([]);
  const [audit, setAudit] = useState([]);
  const [nb, setNb] = useState({ name: '', primary_color: '#C79A3A', secondary_color: '#12233A', accent_color: '#E8C874', font: 'Poppins' });

  const reload = () => Promise.all([
    api.adminMe().then((r) => setMe(r.admin)).catch(() => {}),
    api.health().then(setHealth).catch(() => {}),
    api.bizBrands().then((r) => setBrands(r.brands || [])).catch(() => {}),
    api.adminAudit(20).then((r) => setAudit(r.events || [])).catch(() => {}),
  ]);
  useEffect(() => { reload(); }, []);

  const createBrand = async () => {
    if (!nb.name.trim()) return notify?.('Brand name required', 'error');
    try { await api.bizCreateBrand(nb); notify?.('Brand created'); setNb({ ...nb, name: '' }); reload(); }
    catch { notify?.('Create failed', 'error'); }
  };

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Administration</p>
      <h1 className="font-display text-4xl md:text-5xl mb-6" style={{ fontWeight: 600, lineHeight: 1 }}>Settings.</h1>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel p-5">
          <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>Admin profile</h3>
          <dl className="kv">
            <dt>Name</dt><dd>{me?.name || '—'}</dd>
            <dt>Username</dt><dd>{me?.username || '—'}</dd>
            <dt>Mode</dt><dd>Single administrator · private</dd>
          </dl>
        </div>

        <div className="panel p-5">
          <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>LLM / API</h3>
          <dl className="kv">
            <dt>Provider</dt><dd>{health?.openai_key_set ? 'OpenAI connected' : 'no key'}</dd>
            <dt>Model</dt><dd>{health?.model}</dd>
          </dl>
          <p className="text-xs font-mono mt-2" style={{ color: 'var(--faint)' }}>Secrets live in backend .env only — never sent to the frontend.</p>
        </div>

        <div className="panel p-5 md:col-span-2">
          <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>Brand presets</h3>
          <div className="flex flex-wrap gap-2 mb-4">
            {brands.map((b) => (
              <span key={b.id} className="chip" style={{ borderColor: b.primary_color }}>{b.name} · {b.font}</span>
            ))}
            {brands.length === 0 && <span className="text-sm" style={{ color: 'var(--faint)' }}>No brand presets yet.</span>}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 items-end">
            <label className="block"><span className="label">Name</span><input className="input" value={nb.name} onChange={(e) => setNb({ ...nb, name: e.target.value })} placeholder="Landmark Homes" /></label>
            <label className="block"><span className="label">Primary</span><input className="input" value={nb.primary_color} onChange={(e) => setNb({ ...nb, primary_color: e.target.value })} /></label>
            <label className="block"><span className="label">Secondary</span><input className="input" value={nb.secondary_color} onChange={(e) => setNb({ ...nb, secondary_color: e.target.value })} /></label>
            <label className="block"><span className="label">Font</span><input className="input" value={nb.font} onChange={(e) => setNb({ ...nb, font: e.target.value })} /></label>
            <button className="btn btn-accent" onClick={createBrand}><Icon name="plus" size={14} /> Add</button>
          </div>
        </div>

        <div className="panel p-5 md:col-span-2">
          <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>Audit log</h3>
          <div className="space-y-1.5 max-h-64 overflow-auto font-mono text-xs" style={{ color: 'var(--muted)' }}>
            {audit.map((e) => (
              <div key={e.id} className="flex items-center justify-between">
                <span><b style={{ color: 'var(--text)' }}>{e.action}</b> {e.entity} {e.entity_id}</span>
                <span style={{ color: 'var(--faint)' }}>{e.created_at}</span>
              </div>
            ))}
            {audit.length === 0 && <span style={{ color: 'var(--faint)' }}>No audit entries.</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
