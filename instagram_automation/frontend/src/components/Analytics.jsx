import { useEffect, useState } from 'react';
import api from '../services/api';
import { Spinner } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function Analytics({ notify }) {
  const [o, setO] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.bizAnalyticsOverview().then(setO).catch(() => notify?.('Cannot load analytics', 'error')).finally(() => setLoading(false)); }, [notify]);

  if (loading) return <div className="panel p-16 text-center"><Spinner size={26} /></div>;

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Performance</p>
      <h1 className="font-display text-4xl md:text-5xl mb-6" style={{ fontWeight: 600, lineHeight: 1 }}>Analytics.</h1>

      {(o?.campaigns_tracked || 0) === 0 ? (
        <div className="panel p-10 text-center" style={{ color: 'var(--muted)' }}>
          No insights yet. Publish a campaign and hit <b>Sync insights</b> on it — engagement lands here, ranked by content angle.
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          <div className="panel p-5">
            <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>Average score by angle</h3>
            {(o.by_angle || []).map((a) => (
              <div key={a.angle} className="flex items-center justify-between text-sm mb-2">
                <span>{hum(a.angle)}</span><span className="chip">{a.count} campaigns · avg {a.avg_score}</span>
              </div>
            ))}
          </div>
          <div className="panel p-5">
            <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>Top campaigns</h3>
            {(o.top || []).map((c, i) => (
              <div key={i} className="flex items-center justify-between text-sm mb-2">
                <span>#{c.campaign_id} · {hum(c.angle)} · {hum(c.goal)}</span><span className="tag">score {c.score}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
