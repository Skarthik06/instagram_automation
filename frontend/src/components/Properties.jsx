import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const TABS = ['Overview', 'Knowledge', 'Media', 'Campaigns', 'Versions'];

export default function Properties({ notify }) {
  const [list, setList] = useState([]);
  const [sel, setSel] = useState(null);       // property_id
  const [ws, setWs] = useState(null);         // workspace payload
  const [tab, setTab] = useState('Overview');
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.bizProperties().then((r) => setList(r.properties || [])).finally(() => setLoading(false)); }, []);

  const open = async (pid) => {
    setSel(pid); setWs(null); setTab('Overview');
    try { setWs(await api.bizWorkspace(pid)); } catch { notify?.('Cannot load workspace', 'error'); }
  };

  if (loading) return <div className="panel p-16 text-center"><Spinner size={26} /></div>;

  // list view
  if (!sel) {
    return (
      <div className="fade-up accent-business">
        <p className="eyebrow mb-2">Source of truth</p>
        <h1 className="font-display text-4xl md:text-5xl mb-6" style={{ fontWeight: 600, lineHeight: 1 }}>Properties.</h1>
        {list.length === 0 && <div className="panel p-10 text-center" style={{ color: 'var(--muted)' }}>No properties yet — extract a document in Business.</div>}
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px,1fr))' }}>
          {list.map((p) => (
            <button key={p.id} className="panel p-4 text-left" style={{ cursor: 'pointer' }} onClick={() => open(p.id)}>
              <div className="flex items-center justify-between mb-1">
                <div style={{ fontWeight: 600 }}>{p.project_name}</div>
                <span className={cx('pill', p.verdict?.status === 'PASS' ? 'pill-ok' : 'pill-warn')}>{p.verdict?.status || '—'}</span>
              </div>
              <div className="text-xs font-mono" style={{ color: 'var(--faint)' }}>{p.campaigns} campaign(s) · updated {p.updated_at}</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  // workspace view
  const km = ws?.knowledge;
  return (
    <div className="fade-up accent-business">
      <button className="btn btn-sm btn-ghost mb-4" onClick={() => { setSel(null); setWs(null); }}><Icon name="chevL" size={14} /> All properties</button>
      {!ws ? <div className="panel p-16 text-center"><Spinner size={24} /></div> : (
        <>
          <div className="flex items-end justify-between flex-wrap gap-3 mb-4">
            <div>
              <p className="eyebrow mb-1">Property workspace</p>
              <h1 className="font-display text-3xl" style={{ fontWeight: 600 }}>{ws.property.project_name}</h1>
            </div>
            <div className="flex gap-3 text-xs font-mono" style={{ color: 'var(--muted)' }}>
              <span className="chip">{ws.overview.verified_facts} facts</span>
              <span className="chip">{ws.overview.media_assets} media</span>
              <span className="chip">{ws.overview.campaigns} campaigns</span>
              <span className="chip">{ws.overview.versions} versions</span>
            </div>
          </div>

          <div className="seg mb-5">
            {TABS.map((t) => <button key={t} className={cx(tab === t && 'on')} onClick={() => setTab(t)}>{t}</button>)}
          </div>

          {tab === 'Overview' && km && (
            <div className="panel p-5">
              <dl className="kv">
                <dt>Project</dt><dd>{km.property.project_name}</dd>
                <dt>Builder</dt><dd>{km.property.builder}</dd>
                <dt>Type</dt><dd>{km.property.property_type} · {km.property.category}</dd>
                <dt>Units / Land</dt><dd>{km.project.total_units ?? '—'} · {km.project.land_area}</dd>
                <dt>Location</dt><dd>{[km.location.locality, km.location.city].filter(Boolean).join(', ')}</dd>
                <dt>Price</dt><dd>{km.pricing.price === 'NOT_AVAILABLE' ? <span className="pill pill-warn">NOT_AVAILABLE</span> : km.pricing.price}</dd>
                <dt>Approvals</dt><dd>{(km.approvals || []).join(', ') || '—'}</dd>
              </dl>
            </div>
          )}

          {tab === 'Knowledge' && km && (
            <div className="panel p-5 space-y-2 max-h-[70vh] overflow-auto">
              {(km.claims || []).map((c, i) => (
                <div key={i}>
                  <div className="text-sm"><b>{c.field}</b> = {String(c.value)} <span className="chip ml-2">p{c.source?.page} · {Math.round((c.confidence || 0) * 100)}%</span></div>
                  {c.source?.text && <div className="evidence mt-1">“{c.source.text}”</div>}
                </div>
              ))}
            </div>
          )}

          {tab === 'Media' && (
            <div className="slidegrid">
              {(km?.media || []).filter((m) => m.cdn_url).map((m, i) => (
                <div key={i} className="panel p-2" style={{ background: 'var(--panel-2)' }}>
                  <a href={m.cdn_url} target="_blank" rel="noreferrer"><img src={m.cdn_url} alt={m.asset_type} /></a>
                  <div className="text-xs font-mono mt-1" style={{ color: 'var(--faint)' }}>{m.asset_type}</div>
                </div>
              ))}
              {(km?.media || []).filter((m) => m.cdn_url).length === 0 && <p className="text-sm" style={{ color: 'var(--faint)' }}>No extracted media.</p>}
            </div>
          )}

          {tab === 'Campaigns' && (
            <div className="space-y-2">
              {(ws.campaigns || []).map((c) => (
                <div key={c.id} className="panel p-3 flex items-center justify-between" style={{ background: 'var(--panel-2)' }}>
                  <div><b>#{c.id}</b> · {hum(c.goal)} · {hum(c.angle)}</div>
                  <span className={cx('pill', c.status === 'PUBLISHED' || c.status === 'AUTO_APPROVED' ? 'pill-ok' : 'pill-warn')}>{hum(c.status)}</span>
                </div>
              ))}
              {(ws.campaigns || []).length === 0 && <p className="text-sm" style={{ color: 'var(--faint)' }}>No campaigns yet.</p>}
            </div>
          )}

          {tab === 'Versions' && (
            <div className="space-y-2">
              {(ws.versions || []).map((v) => (
                <div key={v.id} className="panel p-3 flex items-center justify-between" style={{ background: 'var(--panel-2)' }}>
                  <b>Version {v.version_no}</b><span className="text-xs font-mono" style={{ color: 'var(--faint)' }}>{v.created_at}</span>
                </div>
              ))}
              {(ws.versions || []).length === 0 && <p className="text-sm" style={{ color: 'var(--faint)' }}>No versions.</p>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
