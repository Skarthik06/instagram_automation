import { useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';
import SlideEditor from './SlideEditor';

const TEMPLATES = ['hero', 'feature', 'amenities', 'location', 'connectivity', 'floor_plan', 'gallery', 'cta'];
const BLANK_SLIDE = () => ({ template: 'feature', headline: '', subheadline: '', facts: [''], cta: '', image: null, imageUrl: null });

export default function CustomPoster({ notify }) {
  const [meta, setMeta] = useState({ title: '', location: '', builder: '', brand: '' });
  const [contacts, setContacts] = useState([{ name: '', phone: '' }]);
  const [slides, setSlides] = useState([{ ...BLANK_SLIDE(), template: 'hero' }]);
  const [brands, setBrands] = useState([]);
  const [busy, setBusy] = useState('');
  const [result, setResult] = useState(null);      // { campaign_id, images }
  const [editIdx, setEditIdx] = useState(null);

  useEffect(() => { api.bizBrands().then((b) => setBrands(b.brands || [])).catch(() => {}); }, []);

  const setS = (i, k, v) => setSlides((ss) => ss.map((s, j) => (j === i ? { ...s, [k]: v } : s)));
  const setFact = (i, fi, v) => setSlides((ss) => ss.map((s, j) => (j === i ? { ...s, facts: s.facts.map((f, k) => (k === fi ? v : f)) } : s)));
  const addFact = (i) => setSlides((ss) => ss.map((s, j) => (j === i ? { ...s, facts: [...s.facts, ''] } : s)));
  const rmFact = (i, fi) => setSlides((ss) => ss.map((s, j) => (j === i ? { ...s, facts: s.facts.filter((_, k) => k !== fi) } : s)));
  const addSlide = () => setSlides((ss) => [...ss, BLANK_SLIDE()]);
  const rmSlide = (i) => setSlides((ss) => ss.filter((_, j) => j !== i));
  const moveSlide = (i, d) => setSlides((ss) => {
    const j = i + d; if (j < 0 || j >= ss.length) return ss;
    const c = [...ss]; [c[i], c[j]] = [c[j], c[i]]; return c;
  });

  const uploadImage = async (i, files) => {
    if (!files?.length) return;
    setBusy(`img${i}`);
    try {
      const r = await api.bizCustomUpload([files[0]]);
      const up = r.uploaded?.[0];
      if (up) setSlides((ss) => ss.map((s, j) => (j === i ? { ...s, image: up.filename, imageUrl: up.cdn_url } : s)));
    } catch (e) { notify?.(e?.response?.data?.detail || 'Upload failed', 'error'); }
    finally { setBusy(''); }
  };

  const generate = async () => {
    if (!meta.title.trim()) return notify?.('Give your poster a title', 'error');
    setBusy('gen'); setResult(null);
    try {
      const body = {
        title: meta.title, location: meta.location, builder: meta.builder, brand: meta.brand,
        contacts: contacts.filter((c) => c.name || c.phone),
        slides: slides.map((s) => ({
          template: s.template, headline: s.headline, subheadline: s.subheadline,
          facts: s.facts.map((f) => f.trim()).filter(Boolean), cta: s.cta, image: s.image,
        })),
      };
      const r = await api.bizCustomGenerate(body);
      setResult(r);
      notify?.(`Poster generated — ${r.images?.length || 0} slides`);
    } catch (e) { notify?.(e?.response?.data?.detail || 'Generation failed', 'error'); }
    finally { setBusy(''); }
  };

  return (
    <div className="fade-up accent-business max-w-5xl">
      <p className="eyebrow mb-2">Design studio</p>
      <h1 className="font-display text-4xl md:text-5xl" style={{ fontWeight: 600, lineHeight: 1 }}>Custom Poster.</h1>
      <p className="text-sm mt-2 mb-6" style={{ color: 'var(--muted)' }}>
        Build a poster or carousel from your own images and details — full control, same elegant design system. Edit any slide after generating.
      </p>

      {/* meta */}
      <div className="panel p-5 mb-4">
        <div className="eyebrow mb-3" style={{ color: 'var(--accent)' }}>Poster details</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="block"><span className="label">Title *</span>
            <input className="input" value={meta.title} onChange={(e) => setMeta({ ...meta, title: e.target.value })} placeholder="e.g. Diwali Offer" /></label>
          <label className="block"><span className="label">Location / tagline</span>
            <input className="input" value={meta.location} onChange={(e) => setMeta({ ...meta, location: e.target.value })} placeholder="e.g. Whitefield, Bengaluru" /></label>
          <label className="block"><span className="label">Brand / footer name</span>
            <input className="input" value={meta.builder} onChange={(e) => setMeta({ ...meta, builder: e.target.value })} placeholder="e.g. Landmark Homes" /></label>
          <label className="block"><span className="label">Brand preset (theme)</span>
            <select className="select" value={meta.brand} onChange={(e) => setMeta({ ...meta, brand: e.target.value })}>
              <option value="">Default theme</option>
              {brands.map((b) => <option key={b.id} value={String(b.id)}>{b.name}</option>)}
            </select></label>
        </div>
        <div className="mt-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="label" style={{ margin: 0 }}>Contacts (shown on CTA slide)</span>
            <button className="btn btn-sm btn-ghost" onClick={() => setContacts([...contacts, { name: '', phone: '' }])}><Icon name="plus" size={13} /> Add</button>
          </div>
          <div className="space-y-2">
            {contacts.map((c, i) => (
              <div key={i} className="flex gap-2">
                <input className="input" value={c.name} onChange={(e) => setContacts(contacts.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} placeholder="Name" />
                <input className="input" value={c.phone} onChange={(e) => setContacts(contacts.map((x, j) => (j === i ? { ...x, phone: e.target.value } : x)))} placeholder="Phone" />
                <button className="btn btn-sm btn-ghost" onClick={() => setContacts(contacts.filter((_, j) => j !== i))}><Icon name="trash" size={13} /></button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* slides */}
      <div className="flex items-center justify-between mb-2">
        <div className="eyebrow" style={{ color: 'var(--accent)' }}>Slides ({slides.length})</div>
        <button className="btn btn-sm btn-ghost" onClick={addSlide}><Icon name="plus" size={14} /> Add slide</button>
      </div>
      <div className="space-y-3 mb-5">
        {slides.map((s, i) => (
          <div key={i} className="panel p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="chip">#{i + 1}</span>
              <select className="select" style={{ width: 180 }} value={s.template} onChange={(e) => setS(i, 'template', e.target.value)}>
                {TEMPLATES.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
              <div className="ml-auto flex gap-1">
                <button className="btn btn-sm btn-ghost" disabled={i === 0} onClick={() => moveSlide(i, -1)}>↑</button>
                <button className="btn btn-sm btn-ghost" disabled={i === slides.length - 1} onClick={() => moveSlide(i, 1)}>↓</button>
                <button className="btn btn-sm btn-ghost" disabled={slides.length === 1} onClick={() => rmSlide(i)}><Icon name="trash" size={13} /></button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_180px] gap-4">
              <div className="space-y-2.5">
                <input className="input" value={s.headline} onChange={(e) => setS(i, 'headline', e.target.value)} placeholder="Headline" />
                <input className="input" value={s.subheadline} onChange={(e) => setS(i, 'subheadline', e.target.value)} placeholder="Subheadline" />
                <div className="space-y-1.5">
                  {s.facts.map((f, fi) => (
                    <div key={fi} className="flex gap-2">
                      <input className="input" value={f} onChange={(e) => setFact(i, fi, e.target.value)} placeholder="Bullet point" />
                      <button className="btn btn-sm btn-ghost" onClick={() => rmFact(i, fi)}><Icon name="trash" size={12} /></button>
                    </div>
                  ))}
                  <button className="btn btn-sm btn-ghost" onClick={() => addFact(i)}><Icon name="plus" size={12} /> Bullet</button>
                </div>
                {s.template === 'cta' && <input className="input" value={s.cta} onChange={(e) => setS(i, 'cta', e.target.value)} placeholder="CTA button text" />}
              </div>
              <label className="block cursor-pointer">
                <span className="label">Image</span>
                <div className="panel grid place-items-center text-center" style={{ aspectRatio: '4/5', background: 'var(--panel-2)', borderStyle: 'dashed', overflow: 'hidden' }}>
                  {busy === `img${i}` ? <Spinner size={18} />
                    : s.imageUrl ? <img src={s.imageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      : <span className="text-xs" style={{ color: 'var(--faint)' }}><Icon name="doc" size={18} /><br />Click to upload</span>}
                </div>
                <input type="file" hidden accept="image/*" onChange={(e) => uploadImage(i, e.target.files)} />
              </label>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end mb-8">
        <button className="btn btn-accent" onClick={generate} disabled={busy === 'gen'}>
          {busy === 'gen' ? <><Spinner size={16} /> Generating…</> : <><Icon name="spark" size={16} /> Generate Poster</>}
        </button>
      </div>

      {/* result */}
      {result && (
        <div className="panel p-5 mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <Icon name="building" size={18} /><h3 className="font-display text-lg" style={{ fontWeight: 600 }}>Generated poster — {result.images?.length || 0} slides</h3>
            </div>
            <span className="chip">Campaign #{result.campaign_id}</span>
          </div>
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(180px,1fr))' }}>
            {(result.images || []).map((img, i) => (
              <div key={i} className="panel p-2" style={{ background: 'var(--panel-2)' }}>
                <a href={img} target="_blank" rel="noreferrer"><img src={img} alt={`slide ${i + 1}`} style={{ width: '100%', borderRadius: 8, display: 'block' }} /></a>
                <div className="flex gap-1 mt-2">
                  <button className="btn btn-sm btn-accent" onClick={() => setEditIdx(i)}><Icon name="edit" size={13} /> Edit</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {editIdx !== null && result?.campaign_id && (
        <SlideEditor cid={result.campaign_id} startIndex={editIdx} notify={notify}
          onClose={() => { setEditIdx(null); api.bizBlueprint(result.campaign_id).then((b) => setResult((r) => ({ ...r, images: b.images }))).catch(() => {}); }} />
      )}
    </div>
  );
}
