import { useCallback, useEffect, useState } from 'react';
import api from './services/api';
import { Icon, Toast, cx } from './components/ui';
import Studio from './components/Studio';
import Settings from './components/Settings';
import History from './components/History';

const NAV = [
  { id: 'studio', label: 'Studio', icon: 'studio' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
  { id: 'history', label: 'History', icon: 'history' },
];

export default function App() {
  const [view, setView] = useState('studio');
  const [accounts, setAccounts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [health, setHealth] = useState(null);
  const [toast, setToast] = useState(null);

  const notify = useCallback((text, type = 'ok') => {
    setToast({ text, type });
    setTimeout(() => setToast(null), 3200);
  }, []);

  const reload = useCallback(async () => {
    const [acc, set] = await Promise.all([api.listAccounts(), api.getSettings()]);
    setAccounts(acc.accounts);
    setSettings(set);
  }, []);

  useEffect(() => {
    reload().catch(() => notify('Cannot reach backend on :8000', 'error'));
    api.health().then(setHealth).catch(() => {});
  }, [reload, notify]);

  return (
    <div className="min-h-screen flex">
      {/* nav rail */}
      <aside className="hidden md:flex flex-col w-64 shrink-0 p-5 sticky top-0 h-screen"
        style={{ borderRight: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2.5 px-1 mb-9">
          <div className="w-9 h-9 rounded-xl grid place-items-center"
            style={{ background: 'linear-gradient(135deg, var(--amber-2), var(--amber))', color: '#1a1206' }}>
            <Icon name="spark" size={20} />
          </div>
          <div>
            <div className="font-display text-xl leading-none" style={{ fontWeight: 600 }}>Studio</div>
            <div className="eyebrow" style={{ fontSize: '0.56rem' }}>Instagram autopilot</div>
          </div>
        </div>

        <nav className="space-y-1.5 flex-1">
          {NAV.map((n) => (
            <div key={n.id} className={cx('nav-item', view === n.id && 'active')} onClick={() => setView(n.id)}>
              <Icon name={n.icon} size={18} /> {n.label}
              <span className="nav-dot" />
            </div>
          ))}
        </nav>

        <div className="panel p-3.5 mt-4 text-xs space-y-2 font-mono" style={{ color: 'var(--muted)' }}>
          <div className="flex items-center gap-2">
            <span className={health?.openai_key_set ? 'live-dot' : ''}
              style={!health?.openai_key_set ? { width: 7, height: 7, borderRadius: 99, background: 'var(--danger)' } : {}} />
            {health?.openai_key_set ? 'OpenAI connected' : 'OpenAI key missing'}
          </div>
          <div style={{ color: 'var(--faint)' }}>{health?.model || 'gpt-4o-mini'}</div>
          <div style={{ color: 'var(--faint)' }}>{accounts.length} account{accounts.length !== 1 ? 's' : ''} linked</div>
        </div>
      </aside>

      {/* mobile top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 z-40 flex gap-1 p-2"
        style={{ background: 'var(--bg-2)', borderBottom: '1px solid var(--border)' }}>
        {NAV.map((n) => (
          <button key={n.id} className={cx('nav-item flex-1 justify-center', view === n.id && 'active')} onClick={() => setView(n.id)}>
            <Icon name={n.icon} size={18} />
          </button>
        ))}
      </div>

      {/* main */}
      <main className="flex-1 min-w-0 px-5 md:px-10 py-8 md:py-10 mt-14 md:mt-0">
        <div className="max-w-6xl mx-auto">
          {view === 'studio' && <Studio accounts={accounts} settings={settings} notify={notify} />}
          {view === 'settings' && <Settings accounts={accounts} settings={settings} reload={reload} notify={notify} />}
          {view === 'history' && <History />}
        </div>
      </main>

      <Toast toast={toast} />
    </div>
  );
}
