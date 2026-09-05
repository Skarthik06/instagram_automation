import { Icon } from './ui';

// Honest roadmap page for nav items whose backend isn't built yet (no fake API calls).
export default function Placeholder({ title, eyebrow, icon = 'spark', lines = [] }) {
  return (
    <div className="fade-up accent-business">
      <p className="eyebrow mb-2">{eyebrow}</p>
      <h1 className="font-display text-4xl md:text-5xl mb-6" style={{ fontWeight: 600, lineHeight: 1 }}>{title}</h1>
      <div className="panel p-10 text-center">
        <Icon name={icon} size={30} className="mx-auto mb-3" style={{ color: 'var(--accent)' }} />
        <p className="font-display text-xl mb-2">Coming in a later pass</p>
        <div className="text-sm" style={{ color: 'var(--muted)', maxWidth: 520, margin: '0 auto' }}>
          {lines.map((l, i) => <p key={i} className="mb-1">{l}</p>)}
        </div>
      </div>
    </div>
  );
}
