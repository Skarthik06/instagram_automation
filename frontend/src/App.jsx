import { useCallback, useEffect, useState } from 'react';
import api, { TOKEN_KEY, REFRESH_KEY } from './services/api';
import { Icon, Toast, Spinner, cx } from './components/ui';
import Studio from './components/Studio';
import Settings from './components/Settings';
import History from './components/History';
import Business from './components/Business';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import Properties from './components/Properties';
import Analytics from './components/Analytics';
import MediaLibrary from './components/MediaLibrary';
import Templates from './components/Templates';
import Integrations from './components/Integrations';
import AdminSettings from './components/AdminSettings';
import Leads from './components/Leads';
import Calendar from './components/Calendar';
import CustomPoster from './components/CustomPoster';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: 'studio' },
  { id: 'business', label: 'Business', icon: 'building' },
  { id: 'custom', label: 'Custom Poster', icon: 'edit' },
  { id: 'properties', label: 'Properties', icon: 'doc' },
  { id: 'media', label: 'Media Library', icon: 'quote' },
  { id: 'templates', label: 'Templates', icon: 'edit' },
  { id: 'analytics', label: 'Analytics', icon: 'history' },
  { id: 'leads', label: 'Leads', icon: 'bolt' },
  { id: 'calendar', label: 'Calendar', icon: 'news' },
  { id: 'integrations', label: 'Integrations', icon: 'ext' },
  { id: 'accounts', label: 'Accounts', icon: 'spark' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
  { id: 'studio', label: 'Personal', icon: 'quote' },
];

export default function App() {
  const [view, setView] = useState('dashboard');
  const [accounts, setAccounts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [health, setHealth] = useState(null);
  const [toast, setToast] = useState(null);
  const [generating, setGenerating] = useState(false);   // campaign generation in progress
  // auth: null = checking, false = login screen, true = authenticated
  const [authed, setAuthed] = useState(localStorage.getItem(TOKEN_KEY) ? null : false);

  const notify = useCallback((text, type = 'ok') => {
    setToast({ text, type });
    setTimeout(() => setToast(null), 3200);
  }, []);

  const reload = useCallback(async () => {
    const [acc, set] = await Promise.all([api.listAccounts(), api.getSettings()]);
    setAccounts(acc.accounts);
    setSettings(set);
  }, []);

  // Validate an existing token on mount before showing the app.
  useEffect(() => {
    if (localStorage.getItem(TOKEN_KEY)) {
      api.adminMe().then(() => setAuthed(true)).catch(() => setAuthed(false));
    }
  }, []);

  // Load data only once authenticated.
  useEffect(() => {
    if (authed !== true) return;
    reload().catch(() => notify('Cannot reach backend on :8000', 'error'));
    api.health().then(setHealth).catch(() => {});
  }, [authed, reload, notify]);

  const logout = async () => {
    await api.adminLogout();
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setAuthed(false);
  };

  if (authed === null) {
    return <div className="min-h-screen grid place-items-center" style={{ position: 'relative', zIndex: 2, color: 'var(--muted)' }}>Loading…</div>;
  }
  if (authed === false) {
    return <Login onAuthed={() => setAuthed(true)} />;
  }

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
        <button className="btn btn-sm btn-ghost mt-3 justify-center" onClick={logout}>
          <Icon name="x" size={14} /> Sign out
        </button>
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
          {/* Business stays MOUNTED (hidden when inactive) so an in-progress
              extraction / generated campaign / blueprint edits persist when you
              switch panels and come back — "leave it where I left it". */}
          <div style={{ display: view === 'business' ? 'block' : 'none' }}>
            <Business notify={notify} onGenerating={setGenerating} />
          </div>
          {view === 'dashboard' && <Dashboard notify={notify} go={setView} />}
          {view === 'custom' && <CustomPoster notify={notify} />}
          {view === 'properties' && <Properties notify={notify} />}
          {view === 'media' && <MediaLibrary notify={notify} />}
          {view === 'templates' && <Templates notify={notify} />}
          {view === 'analytics' && <Analytics notify={notify} />}
          {view === 'leads' && <Leads notify={notify} />}
          {view === 'calendar' && <Calendar notify={notify} />}
          {view === 'integrations' && <Integrations notify={notify} />}
          {view === 'accounts' && <Settings accounts={accounts} settings={settings} reload={reload} notify={notify} />}
          {view === 'settings' && <AdminSettings notify={notify} />}
          {view === 'studio' && <Studio accounts={accounts} settings={settings} notify={notify} />}
          {view === 'history' && <History />}
        </div>
      </main>

      <Toast toast={toast} />

      {/* Global generation indicator — stays visible on every panel so an in-progress
          campaign is obviously still running when you switch away (it never stops). */}
      {generating && view !== 'business' && (
        <button onClick={() => setView('business')}
          className="fixed z-50 flex items-center gap-2.5 px-4 py-3 rounded-2xl"
          style={{ right: 20, bottom: 20, background: 'var(--panel-2)', border: '1px solid var(--accent)', color: 'var(--text)', cursor: 'pointer', boxShadow: '0 8px 30px rgba(0,0,0,.45)' }}>
          <Spinner size={15} />
          <span className="text-sm" style={{ fontWeight: 600 }}>Generating campaign…</span>
          <span className="text-xs" style={{ color: 'var(--faint)' }}>tap to view</span>
        </button>
      )}
    </div>
  );
}
