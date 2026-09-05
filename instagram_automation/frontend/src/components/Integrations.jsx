import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';

export default function Integrations({ notify }) {
  const [s, setS] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.bizIntegrations().then(setS).catch(() => notify?.('Cannot load integrations', 'error')).finally(() => setLoading(false)); }, [notify]);

  if (loading) return <div className="panel p-16 text-center"><Spinner size={24} /></div>;
  if (!s) return null;

  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">Connections</p>
      <h1 className="font-display text-4xl md:text-5xl mb-6" style={{ fontWeight: 600, lineHeight: 1 }}>Integrations.</h1>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg" style={{ fontWeight: 600 }}>LLM provider</h3>
            <span className={cx('pill', s.openai.connected ? 'pill-ok' : 'pill-warn')}>{s.openai.connected ? 'connected' : 'no key'}</span>
          </div>
          <div className="text-sm mt-2" style={{ color: 'var(--muted)' }}>Model: <b style={{ color: 'var(--text)' }}>{s.openai.model}</b></div>
        </div>

        <div className="panel p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg" style={{ fontWeight: 600 }}>Document extraction</h3>
            <span className="pill pill-ok">active</span>
          </div>
          <div className="text-sm mt-2" style={{ color: 'var(--muted)' }}>Docling: {String(s.docling) === '1' ? 'on (scanned)' : 'off'} · DB: {s.database}</div>
        </div>

        <div className="panel p-5 md:col-span-2">
          <h3 className="font-display text-lg mb-3" style={{ fontWeight: 600 }}>Instagram accounts</h3>
          {(s.instagram_accounts || []).length === 0
            ? <p className="text-sm" style={{ color: 'var(--faint)' }}>No accounts — add one in Settings.</p>
            : <div className="space-y-2">
                {s.instagram_accounts.map((a) => (
                  <div key={a.id} className="flex items-center justify-between panel p-3" style={{ background: 'var(--panel-2)' }}>
                    <div><b>{a.label}</b> <span className="text-xs font-mono" style={{ color: 'var(--faint)' }}>{a.handle ? '@' + a.handle : ''} · {a.niche}</span></div>
                    <span className={cx('pill', a.has_token ? 'pill-ok' : 'pill-warn')}>{a.has_token ? 'token set' : 'no token'}</span>
                  </div>
                ))}
              </div>}
          <p className="text-xs font-mono mt-3" style={{ color: 'var(--faint)' }}>
            Publishing runs on the Instagram Graph API. For the Meta MCP dev-assistant, see business/META_INTEGRATION.md.
          </p>
        </div>
      </div>
    </div>
  );
}
