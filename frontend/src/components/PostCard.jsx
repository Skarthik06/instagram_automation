import { useState } from 'react';
import { Icon, Spinner, cx } from './ui';

export default function PostCard({ post, niche, accounts, onPublish }) {
  const [slide, setSlide] = useState(0);
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? '');
  const [busy, setBusy] = useState(false);

  const slides = post.preview_urls || [];
  const total = slides.length;
  const go = (d) => setSlide((s) => (s + d + total) % total);

  const publish = async () => {
    if (!accountId) return;
    setBusy(true);
    try {
      await onPublish(Number(accountId));
    } finally {
      setBusy(false);
    }
  };

  const published = post.published && post.result;

  return (
    <div className={cx('panel overflow-hidden fade-up', `accent-${niche}`)}>
      {/* slide viewer */}
      <div className="relative bg-black" style={{ aspectRatio: '4 / 5' }}>
        {slides.map((url, i) => (
          <img
            key={i}
            src={url}
            alt={`Slide ${i + 1}`}
            className="absolute inset-0 w-full h-full object-cover transition-opacity duration-300"
            style={{ opacity: i === slide ? 1 : 0 }}
            draggable={false}
          />
        ))}

        {total > 1 && (
          <>
            <button onClick={() => go(-1)} className="absolute left-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full grid place-items-center"
              style={{ background: 'rgba(0,0,0,.5)', color: '#fff' }} aria-label="Previous slide">
              <Icon name="chevL" size={18} />
            </button>
            <button onClick={() => go(1)} className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full grid place-items-center"
              style={{ background: 'rgba(0,0,0,.5)', color: '#fff' }} aria-label="Next slide">
              <Icon name="chevR" size={18} />
            </button>
            <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5">
              {slides.map((_, i) => (
                <button key={i} onClick={() => setSlide(i)} aria-label={`Slide ${i + 1}`}
                  className="h-1.5 rounded-full transition-all"
                  style={{ width: i === slide ? 22 : 6, background: i === slide ? 'var(--accent)' : 'rgba(255,255,255,.4)' }} />
              ))}
            </div>
            <div className="absolute top-3 right-3 chip" style={{ background: 'rgba(0,0,0,.55)', color: '#fff' }}>
              {slide + 1}/{total}
            </div>
          </>
        )}
      </div>

      {/* body */}
      <div className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <Icon name={niche === 'news' ? 'news' : 'quote'} size={15} style={{ color: 'var(--accent)' }} />
          <span className="eyebrow" style={{ color: 'var(--accent)' }}>{post.title}</span>
          {post.source && <span className="chip ml-auto">{post.source}</span>}
        </div>

        <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text)' }}>{post.caption}</p>

        {post.hashtags?.length > 0 && (
          <div className="flex flex-wrap gap-x-2 gap-y-1 mb-4">
            {post.hashtags.map((h) => <span key={h} className="tag">{h}</span>)}
          </div>
        )}

        {/* publish row */}
        {published ? (
          <div className="flex items-center gap-3 rounded-xl px-3 py-2.5"
            style={{ background: 'color-mix(in srgb, var(--ok) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--ok) 40%, transparent)' }}>
            <Icon name="check" size={18} style={{ color: 'var(--ok)' }} />
            <span className="text-sm font-semibold" style={{ color: 'var(--ok)' }}>
              Posted to {post.result.account}
            </span>
            {post.result.permalink && (
              <a href={post.result.permalink} target="_blank" rel="noreferrer"
                className="btn btn-ghost btn-sm ml-auto">
                View <Icon name="ext" size={14} />
              </a>
            )}
          </div>
        ) : (
          <div className="flex gap-2">
            <select className="select" value={accountId} onChange={(e) => setAccountId(e.target.value)}
              disabled={accounts.length === 0}>
              {accounts.length === 0 && <option value="">No accounts — add one in Settings</option>}
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.label} · @{a.ig_business_id}</option>
              ))}
            </select>
            <button className="btn btn-accent whitespace-nowrap" onClick={publish}
              disabled={busy || accounts.length === 0}>
              {busy ? <><Spinner size={16} /> Posting</> : <><Icon name="bolt" size={16} /> Publish</>}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
