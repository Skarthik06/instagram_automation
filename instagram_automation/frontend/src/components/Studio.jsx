import { useState } from 'react';
import api from '../services/api';
import PostCard from './PostCard';
import { Icon, Spinner, cx } from './ui';

const PLACEHOLDER = {
  quotes: 'optional theme — e.g. discipline, self-belief',
  news: 'optional topic — e.g. technology, finance, world',
};

export default function Studio({ accounts, settings, notify }) {
  const [niche, setNiche] = useState('quotes');
  const [posts, setPosts] = useState(3);
  const [slides, setSlides] = useState(4);
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  // keep a separate batch per niche so switching tabs preserves results
  const [batches, setBatches] = useState({ quotes: null, news: null });

  const batch = batches[niche];
  const nicheAccounts = accounts.filter(
    (a) => a.is_active && (a.niche === niche || a.niche === 'both')
  );

  const generate = async () => {
    setLoading(true);
    try {
      const result = await api.generate({ niche, posts: Number(posts), slides: Number(slides), topic: topic.trim() || null });
      setBatches((b) => ({ ...b, [niche]: result }));
      notify(`Generated ${result.posts.length} ${niche} carousel${result.posts.length > 1 ? 's' : ''} in one LLM call`);
    } catch (e) {
      notify(e?.response?.data?.detail || 'Generation failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const publish = async (postIndex, accountId) => {
    try {
      const res = await api.publish({ batch_id: batch.batch_id, post_index: postIndex, account_id: accountId });
      setBatches((b) => {
        const copy = { ...b[niche], posts: b[niche].posts.map((p) => p.index === postIndex
          ? { ...p, published: true, result: { permalink: res.permalink, media_type: res.media_type, account: res.account } }
          : p) };
        return { ...b, [niche]: copy };
      });
      notify('Published to Instagram 🎉');
    } catch (e) {
      notify(e?.response?.data?.detail || 'Publish failed', 'error');
    }
  };

  return (
    <div className={cx('fade-up', `accent-${niche}`)}>
      {/* header */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <p className="eyebrow mb-2">Content studio</p>
          <h1 className="font-display text-4xl md:text-5xl" style={{ fontWeight: 600, lineHeight: 1 }}>
            Generate carousels.
          </h1>
        </div>
        <div className="seg">
          <button className={cx(niche === 'quotes' && 'on')} onClick={() => setNiche('quotes')}>
            <Icon name="quote" size={16} /> Quotes
          </button>
          <button className={cx(niche === 'news' && 'on')} onClick={() => setNiche('news')}>
            <Icon name="news" size={16} /> News
          </button>
        </div>
      </div>

      {/* controls */}
      <div className="panel p-5 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-[1fr_120px_120px_auto] gap-4 items-end">
          <label className="block">
            <span className="label">{niche === 'news' ? 'News topic' : 'Quote theme'}</span>
            <input className="input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={PLACEHOLDER[niche]} />
          </label>
          <label className="block">
            <span className="label">Posts</span>
            <input className="input" type="number" min="1" max="6" value={posts} onChange={(e) => setPosts(e.target.value)} />
          </label>
          <label className="block">
            <span className="label">Slides</span>
            <input className="input" type="number" min="1" max="6" value={slides} onChange={(e) => setSlides(e.target.value)} />
          </label>
          <button className="btn btn-accent h-[42px]" onClick={generate} disabled={loading}>
            {loading ? <><Spinner size={16} /> Working…</> : <><Icon name="spark" size={16} /> Generate</>}
          </button>
        </div>
        <p className="mt-3 text-xs font-mono" style={{ color: 'var(--faint)' }}>
          {niche === 'news'
            ? 'Fetches live headlines → 1 LLM call rewrites them into infographic carousels (facts stay grounded in the source).'
            : 'Scrapes aesthetic backgrounds → 1 LLM call writes every slide + caption + hashtags for the whole batch.'}
        </p>
      </div>

      {/* token usage console */}
      {batch?.usage && (
        <div className="panel p-4 mb-6 font-mono text-xs flex flex-wrap items-center gap-x-6 gap-y-2"
          style={{ color: 'var(--muted)' }}>
          <span style={{ color: 'var(--accent)' }}>◆ token report</span>
          <span>model <b style={{ color: 'var(--text)' }}>{batch.model}</b></span>
          <span>input <b style={{ color: 'var(--text)' }}>{batch.usage.prompt_tokens}</b></span>
          <span>output <b style={{ color: 'var(--text)' }}>{batch.usage.completion_tokens}</b></span>
          <span>total <b style={{ color: 'var(--text)' }}>{batch.usage.total_tokens}</b></span>
          <span title="input ÷ output. Output tokens cost ~4× input on gpt-4o-mini, so a higher ratio = cheaper batch.">
            in:out <b style={{ color: 'var(--accent)' }}>{batch.usage.io_ratio}:1</b>
          </span>
        </div>
      )}

      {/* results */}
      {loading && !batch && (
        <div className="panel p-16 text-center" style={{ color: 'var(--muted)' }}>
          <div className="inline-flex flex-col items-center gap-3">
            <Spinner size={28} />
            <p className="font-mono text-sm">Generating batch — one LLM call, then rendering slides…</p>
          </div>
        </div>
      )}

      {!loading && !batch && (
        <div className="panel p-16 text-center">
          <Icon name="spark" size={32} className="mx-auto mb-3" style={{ color: 'var(--accent)' }} />
          <p className="font-display text-2xl mb-1">Nothing generated yet</p>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            Set your counts and hit Generate to create {niche} carousels.
          </p>
        </div>
      )}

      {batch && (
        <div className="grid gap-6" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {batch.posts.map((post) => (
            <PostCard key={post.index} post={post} niche={niche}
              accounts={nicheAccounts} onPublish={(accId) => publish(post.index, accId)} />
          ))}
        </div>
      )}
    </div>
  );
}
