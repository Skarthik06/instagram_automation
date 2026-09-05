import { useEffect, useState } from 'react';
import api from '../services/api';
import { Spinner } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function Group({ title, items }) {
  return (
    <div className="panel p-5">
      <div className="eyebrow mb-3" style={{ color: 'var(--accent)' }}>{title}</div>
      <div className="flex flex-wrap gap-2">
        {(items || []).map((x) => <span key={x} className="chip">{hum(x)}</span>)}
      </div>
    </div>
  );
}

export default function Templates({ notify }) {
  const [o, setO] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.bizBriefOptions().then(setO).catch(() => notify?.('Cannot load templates', 'error')).finally(() => setLoading(false)); }, [notify]);

  if (loading) return <div className="panel p-16 text-center"><Spinner size={24} /></div>;
  if (!o) return null;

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Design system</p>
      <h1 className="font-display text-4xl md:text-5xl mb-2" style={{ fontWeight: 600, lineHeight: 1 }}>Templates.</h1>
      <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>The generation vocabulary every campaign draws from — design templates, tones, carousel structures and angles.</p>
      <div className="grid gap-4 md:grid-cols-2">
        <Group title="Design templates" items={o.template} />
        <Group title="Tones" items={o.tone} />
        <Group title="Carousel types" items={o.carousel_type} />
        <Group title="Content angles" items={o.content_angle} />
        <Group title="Campaign goals" items={o.goal} />
        <Group title="Target audiences" items={o.target_audience} />
        <Group title="Image strategies" items={o.image_policy} />
        <Group title="Languages" items={o.language} />
      </div>
    </div>
  );
}
