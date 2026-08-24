import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function Stat({ label, value, icon }) {
  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between">
        <div className="eyebrow">{label}</div>
        {icon && <Icon name={icon} size={16} style={{ color: 'var(--accent)' }} />}
      </div>
      <div className="font-display mt-2" style={{ fontSize: '2rem', fontWeight: 600 }}>{value}</div>
    </div>
  );
}

export default function Dashboard({ notify, go }) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.bizDashboard().then(setD).catch(() => notify?.('Cannot load dashboard', 'error')).finally(() => setLoading(false));
  }, [notify]);

  if (loading) return <div className="panel p-16 text-center"><Spinner size={26} /></div>;
  if (!d) return null;

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Real-estate intelligence</p>
      <h1 className="font-display text-4xl md:text-5xl mb-6" style={{ fontWeight: 600, lineHeight: 1 }}>Dashboard.</h1>

      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px,1fr))' }}>
        <Stat label="Properties" value={d.properties} icon="building" />
        <Stat label="Campaigns" value={d.campaigns} icon="spark" />
        <Stat label="Verified (PASS)" value={d.properties_passing} icon="shield" />
        <Stat label="Analytics tracked" value={d.campaigns_tracked} icon="history" />
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div className="panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display text-lg" style={{ fontWeight: 600 }}>Recent properties</h3>
            <button className="btn btn-sm btn-ghost" onClick={() => go?.('properties')}>Open Properties</button>
          </div>
          <div className="space-y-2">
            {(d.recent_properties || []).map((p) => (
              <div key={p.id} className="flex items-center justify-between panel p-3" style={{ background: 'var(--panel-2)' }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{p.project_name}</div>
                  <div className="text-xs font-mono" style={{ color: 'var(--faint)' }}>{p.campaigns} campaign(s) · {p.updated_at}</div>
                </div>
                <span className={cx('pill', p.verdict?.status === 'PASS' ? 'pill-ok' : 'pill-warn')}>{p.verdict?.status || '—'}</span>
              </div>
            ))}
            {(d.recent_properties || []).length === 0 && <p className="text-sm" style={{ color: 'var(--faint)' }}>No properties yet — extract a document in Business.</p>}
          </div>
        </div>

        <div className="panel p-5">
          <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>Performance by angle</h3>
          {(d.by_angle || []).length === 0
            ? <p className="text-sm" style={{ color: 'var(--faint)' }}>No analytics yet — publish a campaign and sync insights.</p>
            : <div className="space-y-2">
                {(d.by_angle || []).map((a) => (
                  <div key={a.angle} className="flex items-center justify-between text-sm">
                    <span>{hum(a.angle)}</span>
                    <span className="chip">{a.count} · avg {a.avg_score}</span>
                  </div>
                ))}
              </div>}
          {(d.top_campaigns || []).length > 0 && (
            <>
              <div className="eyebrow mt-4 mb-2">Top campaigns</div>
              {d.top_campaigns.map((c, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span>{hum(c.angle)} · {hum(c.goal)}</span><span className="tag">score {c.score}</span>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
