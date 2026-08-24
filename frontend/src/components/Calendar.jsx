import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function Calendar({ notify }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.v1Schedules().then((r) => setRows(r || [])).catch(() => notify?.('Cannot load schedule', 'error')).finally(() => setLoading(false)); }, [notify]);

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Scheduling</p>
      <h1 className="font-display text-4xl md:text-5xl mb-5" style={{ fontWeight: 600, lineHeight: 1 }}>Calendar.</h1>

      {loading ? <div className="panel p-16 text-center"><Spinner size={24} /></div>
        : rows.length === 0
          ? <div className="panel p-10 text-center" style={{ color: 'var(--muted)' }}>
              No scheduled campaigns. Schedule an approved campaign (Business → Publish → Schedule) and it appears here.
            </div>
          : <div className="panel p-0" style={{ overflow: 'hidden' }}>
              {rows.map((s) => (
                <div key={s.campaign_id} className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                  <div className="flex items-center gap-3">
                    <Icon name="news" size={16} style={{ color: 'var(--accent)' }} />
                    <div>
                      <div style={{ fontWeight: 600 }}>Campaign #{s.campaign_id} · {hum(s.goal)} · {hum(s.angle)}</div>
                      <div className="text-xs font-mono" style={{ color: 'var(--faint)' }}>{s.property_id}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="tag">{s.scheduled_at}</div>
                    <div className="text-xs font-mono mt-1"><span className={cx('pill', s.status === 'PUBLISHED' ? 'pill-ok' : 'pill-warn')}>{hum(s.status)}</span></div>
                  </div>
                </div>
              ))}
            </div>}
    </div>
  );
}
