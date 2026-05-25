import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner } from './ui';

function Stat({ label, value, accent }) {
  return (
    <div className="panel p-5">
      <p className="eyebrow mb-2">{label}</p>
      <p className="font-display" style={{ fontSize: '2.4rem', lineHeight: 1, color: accent || 'var(--text)' }}>{value}</p>
    </div>
  );
}

export default function History() {
  const [stats, setStats] = useState(null);
  const [posts, setPosts] = useState(null);

  useEffect(() => {
    Promise.all([api.getStats(), api.getPosts(50)])
      .then(([s, p]) => { setStats(s); setPosts(p.posts); })
      .catch(() => { setStats({ total_posts: 0, by_niche: { quotes: 0, news: 0 }, accounts: 0 }); setPosts([]); });
  }, []);

  if (!stats || !posts) {
    return <div className="fade-up flex items-center gap-3 py-20 justify-center" style={{ color: 'var(--muted)' }}><Spinner size={22} /> Loading history…</div>;
  }

  return (
    <div className="fade-up">
      <p className="eyebrow mb-2">Archive</p>
      <h1 className="font-display text-4xl md:text-5xl mb-8" style={{ fontWeight: 600 }}>Published history.</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
        <Stat label="Total posts" value={stats.total_posts} />
        <Stat label="Quotes" value={stats.by_niche.quotes} accent="var(--amber)" />
        <Stat label="News" value={stats.by_niche.news} accent="var(--cyan)" />
        <Stat label="Accounts" value={stats.accounts} />
      </div>

      {posts.length === 0 ? (
        <div className="panel p-16 text-center">
          <Icon name="history" size={30} className="mx-auto mb-3" style={{ color: 'var(--muted)' }} />
          <p className="font-display text-2xl mb-1">No posts published yet</p>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>Publish a carousel from the Studio and it will appear here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {posts.map((p) => (
            <div key={p.id} className="panel p-3 flex gap-4 items-center">
              {p.cover_url
                ? <img src={p.cover_url} alt="cover" className="w-16 h-20 rounded-lg object-cover shrink-0" style={{ background: '#000' }} />
                : <div className="w-16 h-20 rounded-lg grid place-items-center shrink-0" style={{ background: 'var(--raise)' }}><Icon name="quote" /></div>}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="chip" style={{ color: p.niche === 'news' ? 'var(--cyan)' : 'var(--amber)' }}>{p.niche}</span>
                  <span className="chip">{p.media_type}{p.slide_urls?.length ? ` · ${p.slide_urls.length}` : ''}</span>
                  <span className="text-xs ml-auto font-mono" style={{ color: 'var(--faint)' }}>{p.created_at}</span>
                </div>
                <p className="text-sm line-clamp-2" style={{ color: 'var(--muted)' }}>{p.caption}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs font-mono" style={{ color: 'var(--faint)' }}>@{p.account_label}</span>
                  {p.permalink && <a href={p.permalink} target="_blank" rel="noreferrer" className="text-xs flex items-center gap-1" style={{ color: 'var(--cyan)' }}>view <Icon name="ext" size={12} /></a>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
