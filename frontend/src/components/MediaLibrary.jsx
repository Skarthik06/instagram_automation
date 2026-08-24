import { useEffect, useState } from 'react';
import api from '../services/api';
import { Spinner, cx } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function MediaLibrary({ notify }) {
  const [data, setData] = useState(null);
  const [cat, setCat] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.bizMedia(cat || undefined).then(setData).catch(() => notify?.('Cannot load media', 'error')).finally(() => setLoading(false));
  }, [cat, notify]);

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Visual assets</p>
      <h1 className="font-display text-4xl md:text-5xl mb-5" style={{ fontWeight: 600, lineHeight: 1 }}>Media Library.</h1>

      <div className="flex flex-wrap gap-2 mb-5">
        <button className={cx('chip', cat === '' && 'on')} style={{ cursor: 'pointer', ...(cat === '' ? { borderColor: 'var(--accent)', color: 'var(--text)' } : {}) }} onClick={() => setCat('')}>All</button>
        {(data?.categories || []).map((c) => (
          <button key={c} className={cx('chip')} style={{ cursor: 'pointer', ...(cat === c ? { borderColor: 'var(--accent)', color: 'var(--text)' } : {}) }} onClick={() => setCat(c)}>{hum(c)}</button>
        ))}
      </div>

      {loading ? <div className="panel p-16 text-center"><Spinner size={24} /></div>
        : (data?.count || 0) === 0
          ? <div className="panel p-10 text-center" style={{ color: 'var(--muted)' }}>No media yet — extracted images from your documents appear here.</div>
          : <div className="slidegrid">
              {data.media.map((m, i) => (
                <div key={i} className="panel p-2" style={{ background: 'var(--panel-2)' }}>
                  <a href={m.cdn_url} target="_blank" rel="noreferrer"><img src={m.cdn_url} alt={m.asset_type} /></a>
                  <div className="text-xs font-mono mt-1" style={{ color: 'var(--faint)' }}>{hum(m.asset_type)}</div>
                  <div className="text-xs" style={{ color: 'var(--muted)' }}>{m.project_name}</div>
                </div>
              ))}
            </div>}
    </div>
  );
}
