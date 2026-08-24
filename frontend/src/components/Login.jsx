import { useState } from 'react';
import api, { TOKEN_KEY, REFRESH_KEY } from '../services/api';
import { Icon, Spinner } from './ui';

export default function Login({ onAuthed }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const r = await api.adminLogin(username.trim(), password);
      localStorage.setItem(TOKEN_KEY, r.access_token);
      if (r.refresh_token) localStorage.setItem(REFRESH_KEY, r.refresh_token);
      onAuthed(r.admin);
    } catch (err) {
      setError(err?.response?.data?.error?.message || err?.response?.data?.detail || 'Invalid credentials');
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid place-items-center px-5" style={{ position: 'relative', zIndex: 2 }}>
      <div className="w-full" style={{ maxWidth: 400 }}>
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-10 h-10 rounded-xl grid place-items-center"
            style={{ background: 'linear-gradient(135deg, var(--amber-2), var(--amber))', color: '#1a1206' }}>
            <Icon name="spark" size={22} />
          </div>
          <div>
            <div className="font-display text-2xl leading-none" style={{ fontWeight: 600 }}>Studio</div>
            <div className="eyebrow" style={{ fontSize: '0.56rem' }}>Instagram autopilot</div>
          </div>
        </div>

        <form onSubmit={submit} className="panel p-6">
          <p className="eyebrow mb-1">Private admin</p>
          <h1 className="font-display text-2xl mb-5" style={{ fontWeight: 600 }}>Sign in</h1>

          <label className="block mb-3">
            <span className="label">Username</span>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
          </label>
          <label className="block mb-4">
            <span className="label">Password</span>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>

          {error && <div className="mb-3 text-sm" style={{ color: 'var(--danger)' }}>{error}</div>}

          <button className="btn btn-accent w-full justify-center" type="submit" disabled={busy}>
            {busy ? <><Spinner size={16} /> Signing in…</> : 'Sign in'}
          </button>
          <p className="mt-4 text-xs font-mono text-center" style={{ color: 'var(--faint)' }}>
            One administrator · private business workspace
          </p>
        </form>
      </div>
    </div>
  );
}
