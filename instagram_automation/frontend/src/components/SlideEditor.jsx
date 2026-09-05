import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

// A hotspot fact may be an object {name, distance}; show it as an editable string.
const factToStr = (f) => {
  if (f && typeof f === 'object') {
    const name = f.name || f.place || f.label || '';
    const dist = f.distance || f.dist || f.value || '';
    return [name, dist].filter(Boolean).join(' — ') || Object.values(f).filter(Boolean).join(', ');
  }
  return String(f ?? '');
};

const TABS = ['Content', 'Design', 'Image'];
const IMAGE_TYPES = ['building_exterior', 'building_interior', 'living_room', 'bedroom', 'kitchen',
  'bathroom', 'balcony', 'amenity', 'floor_plan', 'site_plan', 'context_photo', 'context_map'];

/**
 * Reusable per-slide editor (used by Business + Custom Poster panels).
 * Self-sufficient: loads the campaign blueprint, edits one slide at a time with a
 * live preview, and re-renders on save. Mirrors the design's Slide Editor panel.
 */
export default function SlideEditor({ cid, startIndex = 0, onClose, notify }) {
  const [bp, setBp] = useState(null);          // { slides, images }
  const [i, setI] = useState(startIndex);
  const [tab, setTab] = useState('Content');
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState('');

  const load = useCallback(async () => {
    try { setBp(await api.bizBlueprint(cid)); }
    catch { notify?.('Cannot load slides', 'error'); }
  }, [cid, notify]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!bp?.slides?.[i]) return;
    const s = bp.slides[i];
    // On the CTA slide, pre-fill contacts from the property so they can be edited/added/
    // removed directly (the preview shows the property contacts until you override them).
    let contacts = (s.contacts || []).map((c) => ({ name: c.name || '', phone: c.phone || '' }));
    if (contacts.length === 0 && s.template === 'cta') {
      contacts = (bp.property_contacts || []).map((c) => ({ name: c.name || '', phone: c.phone || '' }));
    }
    setDraft({
      headline: s.headline || '', subheadline: s.subheadline || '',
      facts: (s.facts || []).map(factToStr), cta: s.cta || '',
      template: s.template || '', image_asset_type: s.image_asset_type || '',
      badges: [...(s.badges || [])], contacts,
      brandname: s.brandname || '', locality: s.locality || '', footer: s.footer || '',
    });
  }, [bp, i]);

  const slide = bp?.slides?.[i];
  const total = bp?.slides?.length || 0;
  const setD = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
  const setFact = (idx, v) => setDraft((d) => ({ ...d, facts: d.facts.map((f, j) => (j === idx ? v : f)) }));
  const addFact = () => setDraft((d) => ({ ...d, facts: [...d.facts, ''] }));
  const rmFact = (idx) => setDraft((d) => ({ ...d, facts: d.facts.filter((_, j) => j !== idx) }));
  const setBadge = (idx, v) => setDraft((d) => ({ ...d, badges: d.badges.map((b, j) => (j === idx ? v : b)) }));
  const addBadge = () => setDraft((d) => ({ ...d, badges: [...d.badges, ''] }));
  const rmBadge = (idx) => setDraft((d) => ({ ...d, badges: d.badges.filter((_, j) => j !== idx) }));
  const setContact = (idx, k, v) => setDraft((d) => ({ ...d, contacts: (d.contacts || []).map((c, j) => (j === idx ? { ...c, [k]: v } : c)) }));
  const addContact = () => setDraft((d) => ({ ...d, contacts: [...(d.contacts || []), { name: '', phone: '' }] }));
  const rmContact = (idx) => setDraft((d) => ({ ...d, contacts: (d.contacts || []).filter((_, j) => j !== idx) }));

  const save = async () => {
    setBusy('save');
    try {
      const body = {
        headline: draft.headline, subheadline: draft.subheadline,
        facts: draft.facts.map((f) => f.trim()).filter(Boolean), cta: draft.cta,
        badges: draft.badges.map((b) => b.trim()).filter(Boolean),
        contacts: draft.contacts.filter((c) => (c.name || c.phone)),
        brandname: draft.brandname, locality: draft.locality, footer: draft.footer,
      };
      if (draft.image_asset_type) body.image_asset_type = draft.image_asset_type;
      await api.bizEditSlide(cid, i, body, true);
      await load();
      notify?.(`Slide ${i + 1} applied & re-rendered`);
    } catch (e) { notify?.(e?.response?.data?.detail || 'Apply failed', 'error'); }
    finally { setBusy(''); }
  };
  const regen = async (mode) => {
    setBusy(mode);
    try { await api.bizRegenSlide(cid, i, mode); await load(); notify?.(`Regenerated (${mode})`); }
    catch (e) { notify?.(e?.response?.data?.detail || 'Regenerate failed', 'error'); }
    finally { setBusy(''); }
  };
  const toggleLock = async () => {
    setBusy('lock');
    try { slide?.locked ? await api.bizUnlockSlide(cid, i) : await api.bizLockSlide(cid, i); await load(); }
    catch { notify?.('Lock failed', 'error'); } finally { setBusy(''); }
  };

  const img = bp?.images?.[i];

  // Rendered through a portal to document.body so the fixed overlay is relative to the
  // viewport (an ancestor's transform/animation would otherwise trap position:fixed).
  return createPortal((
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,.66)', padding: 20 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="panel" style={{ width: 'min(1100px, 96vw)', maxHeight: '92vh', overflow: 'auto', background: 'var(--bg-2)' }}>
        {/* header */}
        <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-3">
            <span className="eyebrow" style={{ color: 'var(--accent)' }}>Slide Editor</span>
            <span className="chip">Slide {i + 1} / {total} · {hum(slide?.template)}{slide?.locked ? ' 🔒' : ''}</span>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn btn-sm btn-ghost" disabled={i === 0} onClick={() => setI(i - 1)}><Icon name="chevL" size={14} /> Prev</button>
            <button className="btn btn-sm btn-ghost" disabled={i >= total - 1} onClick={() => setI(i + 1)}>Next <Icon name="chevR" size={14} /></button>
            <button className="btn btn-sm btn-ghost" onClick={onClose}><Icon name="x" size={14} /></button>
          </div>
        </div>

        {!bp ? <div className="p-16 grid place-items-center"><Spinner size={26} /></div> : (
          <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,420px)' }}>
            {/* left — editor */}
            <div className="p-5" style={{ borderRight: '1px solid var(--border)' }}>
              <div className="flex gap-1.5 mb-4">
                {TABS.map((t) => (
                  <button key={t} className={cx('btn btn-sm', tab === t ? 'btn-accent' : 'btn-ghost')} onClick={() => setTab(t)}>{t}</button>
                ))}
              </div>

              {tab === 'Content' && draft && (
                <div className="space-y-3.5">
                  <label className="block"><span className="label">Headline</span>
                    <input className="input" value={draft.headline} onChange={(e) => setD('headline', e.target.value)} /></label>
                  <label className="block"><span className="label">Subheadline</span>
                    <input className="input" value={draft.subheadline} onChange={(e) => setD('subheadline', e.target.value)} /></label>
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="label" style={{ margin: 0 }}>Bullet points</span>
                      <button className="btn btn-sm btn-ghost" onClick={addFact}><Icon name="plus" size={13} /> Add</button>
                    </div>
                    <div className="space-y-2">
                      {draft.facts.map((f, idx) => (
                        <div key={idx} className="flex gap-2">
                          <input className="input" value={f} onChange={(e) => setFact(idx, e.target.value)} placeholder="e.g. Metro Station — 0.5 Km" />
                          <button className="btn btn-sm btn-ghost" onClick={() => rmFact(idx)}><Icon name="trash" size={13} /></button>
                        </div>
                      ))}
                      {draft.facts.length === 0 && <div className="text-xs" style={{ color: 'var(--faint)' }}>No bullet points — add one.</div>}
                    </div>
                  </div>
                  {(draft.template === 'cta' || draft.cta) && (
                    <label className="block"><span className="label">CTA text</span>
                      <input className="input" value={draft.cta} onChange={(e) => setD('cta', e.target.value)} /></label>
                  )}

                  {/* Tags / badges (top of slide) */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="label" style={{ margin: 0 }}>Tags (top of slide)</span>
                      <button className="btn btn-sm btn-ghost" onClick={addBadge}><Icon name="plus" size={13} /> Add</button>
                    </div>
                    <div className="space-y-2">
                      {draft.badges.map((b, idx) => (
                        <div key={idx} className="flex gap-2">
                          <input className="input" value={b} onChange={(e) => setBadge(idx, e.target.value)} placeholder="e.g. Zero-violation project" />
                          <button className="btn btn-sm btn-ghost" onClick={() => rmBadge(idx)}><Icon name="trash" size={13} /></button>
                        </div>
                      ))}
                      {draft.badges.length === 0 && <div className="text-xs" style={{ color: 'var(--faint)' }}>No tags.</div>}
                    </div>
                  </div>

                  {/* Contacts (numbers) — shown on the CTA slide */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="label" style={{ margin: 0 }}>Contacts / numbers</span>
                      <button className="btn btn-sm btn-ghost" onClick={addContact}><Icon name="plus" size={13} /> Add</button>
                    </div>
                    <div className="space-y-2">
                      {draft.contacts.map((c, idx) => (
                        <div key={idx} className="flex gap-2">
                          <input className="input" style={{ maxWidth: 150 }} value={c.name} onChange={(e) => setContact(idx, 'name', e.target.value)} placeholder="Name" />
                          <input className="input" value={c.phone} onChange={(e) => setContact(idx, 'phone', e.target.value)} placeholder="Phone number" />
                          <button className="btn btn-sm btn-ghost" onClick={() => rmContact(idx)}><Icon name="trash" size={13} /></button>
                        </div>
                      ))}
                      {draft.contacts.length === 0 && <div className="text-xs" style={{ color: 'var(--faint)' }}>No contacts — add a name + number (appears on the CTA slide).</div>}
                    </div>
                  </div>

                  {/* Branding overrides */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 pt-1">
                    <label className="block"><span className="label">Brand name (top-left)</span>
                      <input className="input" value={draft.brandname} onChange={(e) => setD('brandname', e.target.value)} placeholder="Auto" /></label>
                    <label className="block"><span className="label">Locality (top-right)</span>
                      <input className="input" value={draft.locality} onChange={(e) => setD('locality', e.target.value)} placeholder="Auto" /></label>
                    <label className="block"><span className="label">Footer (bottom-right)</span>
                      <input className="input" value={draft.footer} onChange={(e) => setD('footer', e.target.value)} placeholder="Auto" /></label>
                  </div>
                </div>
              )}

              {tab === 'Design' && (
                <div className="text-sm space-y-2" style={{ color: 'var(--muted)' }}>
                  <p>Template / layout: <b style={{ color: 'var(--text)' }}>{hum(slide?.template)}</b></p>
                  <p>Brand theme, fonts and colours come from the campaign's <b style={{ color: 'var(--text)' }}>Brand preset</b> (set in the Creative step / Settings). Regenerate the layout below to reshuffle the design within the brand.</p>
                  <button className="btn btn-sm btn-ghost mt-1" disabled={busy !== ''} onClick={() => regen('layout')}>{busy === 'layout' ? '…' : 'Regenerate layout'}</button>
                </div>
              )}

              {tab === 'Image' && draft && (
                <div className="space-y-3">
                  <label className="block"><span className="label">Image type (rebinds to a matching real asset)</span>
                    <select className="select" value={draft.image_asset_type} onChange={(e) => setD('image_asset_type', e.target.value)}>
                      <option value="">Auto (by slot)</option>
                      {IMAGE_TYPES.map((t) => <option key={t} value={t}>{hum(t)}</option>)}
                    </select></label>
                  <button className="btn btn-sm btn-ghost" disabled={busy !== ''} onClick={() => regen('image')}>
                    {busy === 'image' ? '…' : <><Icon name="quote" size={13} /> Regenerate image</>}
                  </button>
                  <p className="text-xs" style={{ color: 'var(--faint)' }}>Property slides use real PDF images; context slides use fetched location photos. Save after changing the type to rebind + re-render.</p>
                </div>
              )}

              {/* actions */}
              <div className="flex flex-wrap gap-2 mt-5 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
                <button className="btn btn-accent btn-sm" disabled={busy !== '' || slide?.locked} onClick={save}>{busy === 'save' ? <><Spinner size={14} /> Applying &amp; rendering…</> : <><Icon name="check" size={14} /> Apply changes</>}</button>
                <button className="btn btn-sm btn-ghost" disabled={busy !== '' || slide?.locked} onClick={() => regen('copy')}>{busy === 'copy' ? '…' : 'Regenerate copy'}</button>
                <button className="btn btn-sm btn-ghost" onClick={toggleLock} disabled={busy !== ''}>{slide?.locked ? 'Unlock' : 'Lock'}</button>
                {i < total - 1 && <button className="btn btn-sm btn-ghost ml-auto" disabled={busy !== ''} onClick={async () => { await save(); setI(i + 1); }}>Save &amp; Next →</button>}
              </div>
              {slide?.locked && <p className="text-xs mt-2" style={{ color: 'var(--faint)' }}>Slide is locked — unlock to edit.</p>}
            </div>

            {/* right — live preview */}
            <div className="p-5" style={{ background: 'var(--bg)' }}>
              <div className="eyebrow mb-2">Live preview</div>
              {img ? <img src={`${img}?t=${Date.now()}`} alt="preview" style={{ width: '100%', borderRadius: 12, display: 'block', border: '1px solid var(--border)' }} />
                : <div style={{ aspectRatio: '4/5', background: 'var(--raise)', borderRadius: 12 }} className="grid place-items-center"><span className="text-xs" style={{ color: 'var(--faint)' }}>No render yet</span></div>}
              <p className="text-xs font-mono mt-2" style={{ color: 'var(--faint)' }}>Preview updates after each save / regenerate.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  ), document.body);
}
