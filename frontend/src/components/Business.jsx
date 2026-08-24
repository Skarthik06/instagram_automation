import { useCallback, useEffect, useState } from 'react';
import api from '../services/api';
import { Icon, Spinner, cx } from './ui';
import SlideEditor from './SlideEditor';

const hum = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function Sel({ label, value, onChange, opts, ai }) {
  return (
    <label className="block">
      <span className="label flex items-center justify-between">
        {label}
        {ai && String(value).includes('ai_recommended') && <span style={{ color: 'var(--accent)' }}>✦✦</span>}
      </span>
      <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
        {(opts || []).map((o) => <option key={o} value={o}>{hum(o)}</option>)}
      </select>
    </label>
  );
}

function Section({ icon, title, right, children }) {
  return (
    <div className="panel p-5 mb-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <Icon name={icon} size={18} /> <h3 className="font-display text-lg" style={{ fontWeight: 600 }}>{title}</h3>
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value, ok }) {
  return (
    <div className="panel p-3">
      <div className="eyebrow mb-1">{label}</div>
      <div className="font-display text-xl" style={{ color: ok === false ? 'var(--danger)' : 'var(--text)' }}>{value}</div>
    </div>
  );
}

const STEPS = [
  { key: 'brief', title: 'Campaign Brief', sub: 'Goal, audience & angle' },
  { key: 'creative', title: 'Creative', sub: 'Design & tone' },
  { key: 'cta', title: 'CTA', sub: 'Call to action' },
  { key: 'data', title: 'Data & Rules', sub: 'Facts & enrichment' },
  { key: 'advanced', title: 'Advanced', sub: 'Versions & control' },
];

const DEFAULT_BRIEF = {
  goal: 'site_visit', target_audience: 'families', content_angle: 'location_first',
  carousel_type: 'property_showcase', slide_count: 10, language: 'english', tone: 'premium',
  content_density: 'balanced', image_policy: 'real_images_only', claim_policy: 'strict',
  cta_objective: 'site_visit', contact_method: 'whatsapp', cta_keyword: 'VISIT', cta_text: '',
  data_enrichment: ['source_document', 'map_location'], brand: '', template: 'premium',
  generation_mode: 'controlled',
};

// Step rail (left column) — the numbered wizard from the design.
function StepRail({ step, setStep, disabled }) {
  return (
    <div className="panel p-2" style={{ alignSelf: 'start' }}>
      {STEPS.map((s, i) => {
        const active = step === s.key;
        return (
          <button key={s.key} onClick={() => !disabled && setStep(s.key)} disabled={disabled}
            className="w-full flex items-center gap-3 px-3 py-3 text-left"
            style={{
              background: active ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'transparent',
              border: active ? '1px solid color-mix(in srgb, var(--accent) 40%, transparent)' : '1px solid transparent',
              borderRadius: 12, cursor: disabled ? 'not-allowed' : 'pointer', marginBottom: 4,
              opacity: disabled ? 0.5 : 1, color: 'var(--text)',
            }}>
            <span className="grid place-items-center shrink-0" style={{
              width: 26, height: 26, borderRadius: 99, fontSize: 13, fontWeight: 700,
              background: active ? 'var(--accent)' : 'var(--raise)',
              color: active ? '#1a1712' : 'var(--muted)',
            }}>{i + 1}</span>
            <span className="min-w-0">
              <span className="block text-sm" style={{ fontWeight: 600 }}>{s.title}</span>
              <span className="block text-xs" style={{ color: 'var(--faint)' }}>{s.sub}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

// Verified-data TABLE (panel 03) — Field · Value · Source · Page · Confidence · Type.
function VerifiedTable({ km, document }) {
  const claims = km?.claims || [];
  const typeOf = (v) => String(v) === 'NOT_AVAILABLE'
    ? { label: 'Not Available', color: 'var(--faint)' }
    : { label: 'Source Document', color: 'var(--ok)' };
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
            {['Field', 'Value', 'Source', 'Page', 'Confidence', 'Source Type'].map((h) => (
              <th key={h} style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {claims.map((c, i) => {
            const t = typeOf(c.value);
            return (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '8px 12px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>{hum(c.field)}</td>
                <td style={{ padding: '8px 12px', fontWeight: 600 }}>{String(c.value)}</td>
                <td style={{ padding: '8px 12px', color: 'var(--faint)', whiteSpace: 'nowrap' }}>{String(c.value) === 'NOT_AVAILABLE' ? '—' : document}</td>
                <td style={{ padding: '8px 12px', color: 'var(--faint)' }}>{c.source?.page ?? '—'}</td>
                <td style={{ padding: '8px 12px' }}>{c.confidence != null ? `${Math.round(c.confidence * 100)}%` : '—'}</td>
                <td style={{ padding: '8px 12px', color: t.color, whiteSpace: 'nowrap' }}>{t.label}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="flex flex-wrap gap-4 mt-3 text-xs" style={{ color: 'var(--muted)' }}>
        {[['Source Document', 'var(--ok)'], ['External Source', 'var(--cyan)'], ['Calculated', 'var(--accent)'], ['Not Available', 'var(--faint)']].map(([l, c]) => (
          <span key={l} className="flex items-center gap-1.5"><span style={{ width: 8, height: 8, borderRadius: 99, background: c }} /> {l}</span>
        ))}
      </div>
    </div>
  );
}

export default function Business({ notify, onGenerating }) {
  const [docs, setDocs] = useState([]);
  const [properties, setProperties] = useState([]);
  const [brands, setBrands] = useState([]);
  const [options, setOptions] = useState(null);
  const [document, setDocument] = useState('');
  const [brief, setBrief] = useState(DEFAULT_BRIEF);
  const [extracted, setExtracted] = useState(null);   // {property_id, knowledge_model, verdict}
  const [result, setResult] = useState(null);          // campaign
  const [busy, setBusy] = useState('');                // '', 'upload','extract','generate'
  const [dragOver, setDragOver] = useState(false);
  const [step, setStep] = useState('brief');
  const [dataView, setDataView] = useState('table');   // 'table' | 'evidence'
  const [blueprint, setBlueprint] = useState([]);
  const [campaignImages, setCampaignImages] = useState([]);
  const [slideBusy, setSlideBusy] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [pubAccount, setPubAccount] = useState('');
  const [pubBusy, setPubBusy] = useState('');
  const [pubResult, setPubResult] = useState(null);
  const [insights, setInsights] = useState(null);
  const [editIdx, setEditIdx] = useState(null);       // open Slide Editor at this index

  useEffect(() => {
    if (result) {
      setBlueprint(result.carousel?.slides || []);
      setCampaignImages(result.contract?.carousel?.images || []);
    }
  }, [result]);

  const cid = () => result?.persisted?.campaign_id;
  const refreshBlueprint = async () => {
    const b = await api.bizBlueprint(cid());
    setBlueprint(b.slides || []); setCampaignImages(b.images || []);
  };
  const slideLock = async (i, lock) => {
    setSlideBusy(i);
    try { lock ? await api.bizLockSlide(cid(), i) : await api.bizUnlockSlide(cid(), i); await refreshBlueprint(); }
    catch { notify('Lock failed', 'error'); } finally { setSlideBusy(null); }
  };
  const slideRegen = async (i, mode) => {
    setSlideBusy(i);
    try { const r = await api.bizRegenSlide(cid(), i, mode); if (r.images?.length) setCampaignImages(r.images); await refreshBlueprint(); notify(`Slide ${i + 1} regenerated (${mode})`); }
    catch (e) { notify(e?.response?.data?.detail || 'Regenerate failed', 'error'); } finally { setSlideBusy(null); }
  };
  const rerender = async () => {
    setSlideBusy(-1);
    try { const r = await api.bizRerender(cid()); setCampaignImages(r.images || []); notify('Re-rendered'); }
    catch { notify('Render failed', 'error'); } finally { setSlideBusy(null); }
  };

  const dryRun = async () => {
    if (!pubAccount) return notify('Pick an Instagram account', 'error');
    setPubBusy('dry'); setPubResult(null);
    try { setPubResult(await api.bizPublish(cid(), Number(pubAccount), true)); notify('Dry-run ready — review before publishing'); }
    catch (e) { notify(e?.response?.data?.detail || 'Dry-run failed', 'error'); } finally { setPubBusy(''); }
  };
  const publishReal = async () => {
    if (!pubAccount) return notify('Pick an Instagram account', 'error');
    if (!window.confirm('Publish this carousel to Instagram now? This is live and cannot be undone.')) return;
    setPubBusy('pub');
    try { const r = await api.bizPublish(cid(), Number(pubAccount), false); setPubResult(r); notify('Published to Instagram 🎉'); }
    catch (e) { notify(e?.response?.data?.detail || 'Publish failed', 'error'); } finally { setPubBusy(''); }
  };
  const syncAnalytics = async () => {
    if (!pubAccount) return;
    setPubBusy('an');
    try { setInsights(await api.bizSyncAnalytics(cid(), Number(pubAccount))); notify('Insights synced'); }
    catch (e) { notify(e?.response?.data?.detail || 'Insights failed', 'error'); } finally { setPubBusy(''); }
  };

  const set = (k, v) => setBrief((b) => ({ ...b, [k]: v }));
  const toggleEnrich = (key) => setBrief((b) => ({
    ...b, data_enrichment: b.data_enrichment.includes(key)
      ? b.data_enrichment.filter((x) => x !== key) : [...b.data_enrichment, key],
  }));

  const reload = useCallback(async () => {
    try {
      const [d, p, o, br, ac] = await Promise.all([api.bizDocuments(), api.bizProperties(), api.bizBriefOptions(), api.bizBrands(), api.bizAccounts()]);
      setDocs(d.documents); setProperties(p.properties); setOptions(o); setBrands(br.brands || []);
      setAccounts(ac.accounts || []); setPubAccount((c) => c || (ac.accounts?.[0]?.id ? String(ac.accounts[0].id) : ''));
      setDocument((cur) => cur || d.documents[0] || '');
    } catch { notify('Cannot reach business API', 'error'); }
  }, [notify]);
  useEffect(() => { reload(); }, [reload]);

  const upload = async (files) => {
    const list = files ? [...files] : [];
    if (list.length === 0) return;
    setBusy('upload');
    try {
      let picked;
      if (list.length === 1) {
        const r = await api.bizUpload(list[0]);
        picked = r.document;
        notify(r.extractable === false ? `Uploaded ${r.document} (needs review: ${r.reason})` : `Uploaded ${r.document}`);
      } else {
        const r = await api.bizUploadMulti(list);
        picked = r.documents?.[0];
        notify(`Uploaded ${r.count} of ${list.length} files`);
      }
      const d = await api.bizDocuments(); setDocs(d.documents);
      if (picked) setDocument(picked);
    } catch (e) { notify(e?.response?.data?.detail || 'Upload failed', 'error'); }
    finally { setBusy(''); }
  };

  const extract = async () => {
    if (!document) return notify('Pick a document', 'error');
    setBusy('extract'); setResult(null); setExtracted(null);
    try {
      const r = await api.bizExtract(document);
      setExtracted(r);
      notify(`Extracted ${r.knowledge_model.property.project_name} — ${r.verdict?.status}`);
      reload();
    } catch (e) { notify(e?.response?.data?.detail || 'Extraction failed', 'error'); }
    finally { setBusy(''); }
  };

  const loadProperty = async (pid) => {
    setBusy('extract'); setResult(null);
    try {
      const p = await api.bizProperty(pid);
      setExtracted({ property_id: p.id, knowledge_model: p.model, verdict: p.verdict });
      notify(`Loaded ${p.project_name}`);
    } catch { notify('Load failed', 'error'); }
    finally { setBusy(''); }
  };

  const generate = async () => {
    if (!extracted?.property_id) return notify('Extract a document first', 'error');
    setBusy('generate'); onGenerating?.(true);
    try {
      const r = await api.bizGenerateCampaign({ property_id: extracted.property_id, brief, render: true });
      setResult(r);
      notify(`Campaign generated — ${r.marketing?.angle}`);
      reload();
    } catch (e) { notify(e?.response?.data?.detail || 'Generation failed', 'error'); }
    finally { setBusy(''); onGenerating?.(false); }
  };

  const setStatus = async (status) => {
    const c = result?.persisted?.campaign_id;
    if (!c) return;
    try { await api.bizSetStatus(c, status); setResult((r) => ({ ...r, persisted: { ...r.persisted, status } })); notify(`Marked ${hum(status)}`); }
    catch { notify('Update failed', 'error'); }
  };

  const km = extracted?.knowledge_model;
  const conf = Math.round((extracted?.verdict?.confidence || 0) * 100);
  const propThumb = (km?.media || []).find((m) => m.usable && m.cdn_url && !['logo', 'builder_logo', 'document_scan', 'unknown'].includes(m.asset_type))?.cdn_url;

  return (
    <div className="fade-up accent-business">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <p className="eyebrow mb-2">Real-estate intelligence</p>
          <h1 className="font-display text-4xl md:text-5xl" style={{ fontWeight: 600, lineHeight: 1 }}>Business.</h1>
          <p className="text-sm mt-2" style={{ color: 'var(--muted)' }}>
            Documents → verified property knowledge → marketing → carousel. Evidence-first, no invented facts.
          </p>
        </div>
        {km && (
          <span className="pill pill-ok" style={{ whiteSpace: 'nowrap' }}>
            {conf}% verified · {extracted.verdict?.status}
          </span>
        )}
      </div>

      {/* ── Upload ─────────────────────────────────────────────── */}
      <label onDragOver={(e) => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); upload(e.dataTransfer?.files); }}
        className="panel mb-4 flex flex-col items-center text-center cursor-pointer"
        style={{ padding: '1.4rem', borderStyle: 'dashed', borderColor: dragOver ? 'var(--accent)' : 'var(--border-2)', transition: 'all .15s' }}>
        <input type="file" hidden multiple onChange={(e) => upload(e.target.files)} />
        {busy === 'upload'
          ? <div className="flex items-center gap-2" style={{ color: 'var(--muted)' }}><Spinner size={16} /> Uploading…</div>
          : <><Icon name="doc" size={20} /><div className="mt-1.5" style={{ fontWeight: 600 }}>Drop files, or click to upload (multiple allowed)</div>
            <div className="text-xs font-mono mt-1" style={{ color: 'var(--faint)' }}>Any file — PDF · images · DOCX · XLSX · CSV · TXT · ZIP · code files</div></>}
      </label>

      {/* ── Source document + Property row ─────────────────────── */}
      <div className="panel p-4 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <span className="label">Source document</span>
            <select className="select" value={document} onChange={(e) => setDocument(e.target.value)}>
              {docs.length === 0 && <option value="">No documents yet</option>}
              {docs.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <div className="flex items-center gap-2 mt-2">
              <button className="btn btn-sm h-[38px]" onClick={extract} disabled={busy === 'extract'}>
                {busy === 'extract' ? <><Spinner size={14} /> Extracting…</> : <><Icon name="doc" size={14} /> Extract &amp; Load</>}
              </button>
              <span className="text-xs font-mono" style={{ color: 'var(--faint)' }}>{document ? document.split('.').pop().toUpperCase() : ''}</span>
            </div>
          </div>
          <div>
            <span className="label">Property / Project</span>
            <div className="flex items-center gap-3 panel p-2" style={{ background: 'var(--panel-2)' }}>
              <div className="shrink-0 grid place-items-center" style={{ width: 46, height: 46, borderRadius: 10, overflow: 'hidden', background: 'var(--raise)' }}>
                {propThumb ? <img src={propThumb} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <Icon name="building" size={20} />}
              </div>
              <div className="min-w-0">
                <div className="text-sm truncate" style={{ fontWeight: 600 }}>{km?.property?.project_name || 'No property loaded'}</div>
                <div className="text-xs truncate" style={{ color: 'var(--faint)' }}>
                  {km ? [km.location?.locality, km.location?.city].filter(Boolean).join(', ') : 'Extract a document to begin'}
                </div>
              </div>
            </div>
          </div>
        </div>
        {properties.length > 0 && (
          <div className="mt-4">
            <div className="eyebrow mb-2">Saved properties (reuse — no re-extraction)</div>
            <div className="flex flex-wrap gap-2">
              {properties.map((p) => (
                <button key={p.id} className={cx('chip', extracted?.property_id === p.id && 'on')}
                  style={{ cursor: 'pointer', ...(extracted?.property_id === p.id ? { borderColor: 'var(--accent)', color: 'var(--text)' } : {}) }}
                  onClick={() => loadProperty(p.id)}>
                  {p.project_name} · {p.campaigns}★ · {p.verdict?.status || '—'}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Wizard (step rail + step content) ──────────────────── */}
      {km && options && (
        <div className="grid gap-4 mb-5" style={{ gridTemplateColumns: 'minmax(0,240px) 1fr' }}>
          <StepRail step={step} setStep={setStep} />
          <div className="panel p-5">
            {step === 'brief' && (
              <>
                <div className="eyebrow mb-4" style={{ color: 'var(--accent)' }}>1 · Campaign Brief</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Sel label="Campaign goal" value={brief.goal} onChange={(v) => set('goal', v)} opts={options.goal} />
                  <Sel label="Target audience" value={brief.target_audience} onChange={(v) => set('target_audience', v)} opts={options.target_audience} ai />
                  <Sel label="Content angle" value={brief.content_angle} onChange={(v) => set('content_angle', v)} opts={options.content_angle} ai />
                  <Sel label="Carousel type" value={brief.carousel_type} onChange={(v) => set('carousel_type', v)} opts={options.carousel_type} ai />
                  <Sel label="Slides" value={String(brief.slide_count)} onChange={(v) => set('slide_count', Number(v))} opts={options.slide_count.map(String)} />
                  <Sel label="Language" value={brief.language} onChange={(v) => set('language', v)} opts={options.language} />
                </div>
                <div className="panel p-3 mt-4 flex items-start gap-2 text-sm"
                  style={{ background: 'color-mix(in srgb, var(--accent) 8%, transparent)', borderColor: 'color-mix(in srgb, var(--accent) 30%, transparent)', color: 'var(--muted)' }}>
                  <span style={{ color: 'var(--accent)' }}>✦</span>
                  <span>Same verified facts, one brief → a predictable campaign shape. The AI writes copy <b>within</b> these controls — it never invents facts.</span>
                </div>
              </>
            )}
            {step === 'creative' && (
              <>
                <div className="eyebrow mb-4" style={{ color: 'var(--accent)' }}>2 · Creative</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Sel label="Template" value={brief.template} onChange={(v) => set('template', v)} opts={options.template} />
                  <Sel label="Tone" value={brief.tone} onChange={(v) => set('tone', v)} opts={options.tone} />
                  <Sel label="Content density" value={brief.content_density} onChange={(v) => set('content_density', v)} opts={options.content_density} />
                  <Sel label="Image strategy" value={brief.image_policy} onChange={(v) => set('image_policy', v)} opts={options.image_policy} />
                  <label className="block">
                    <span className="label">Brand preset</span>
                    <select className="select" value={brief.brand} onChange={(e) => set('brand', e.target.value)}>
                      <option value="">Default brand</option>
                      {brands.map((b) => <option key={b.id} value={String(b.id)}>{b.name}</option>)}
                    </select>
                  </label>
                </div>
              </>
            )}
            {step === 'cta' && (
              <>
                <div className="eyebrow mb-4" style={{ color: 'var(--accent)' }}>3 · Call to action</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Sel label="CTA objective" value={brief.cta_objective} onChange={(v) => set('cta_objective', v)} opts={options.cta_objective} />
                  <Sel label="Contact method" value={brief.contact_method} onChange={(v) => set('contact_method', v)} opts={options.contact_method} />
                  <label className="block"><span className="label">CTA keyword</span>
                    <input className="input" value={brief.cta_keyword} onChange={(e) => set('cta_keyword', e.target.value)} placeholder="VISIT" /></label>
                  <label className="block"><span className="label">CTA text (optional)</span>
                    <input className="input" value={brief.cta_text} onChange={(e) => set('cta_text', e.target.value)} placeholder="AI-generated if blank" /></label>
                </div>
                <div className="panel p-3 mt-4" style={{ background: 'var(--panel-2)' }}>
                  <div className="eyebrow mb-1">Preview CTA</div>
                  <span className="pill pill-ok">{brief.cta_text || `Book your ${hum(brief.cta_objective).toLowerCase()} — ${brief.cta_keyword}`}</span>
                </div>
              </>
            )}
            {step === 'data' && (
              <>
                <div className="eyebrow mb-4" style={{ color: 'var(--accent)' }}>4 · Data &amp; Rules</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <Sel label="Claim policy" value={brief.claim_policy} onChange={(v) => set('claim_policy', v)} opts={options.claim_policy} />
                  <div />
                </div>
                <div className="eyebrow mb-2">Data enrichment</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {(options.data_enrichment || []).map((e) => {
                    const on = brief.data_enrichment.includes(e);
                    return (
                      <button key={e} onClick={() => toggleEnrich(e)} className="flex items-center gap-2.5 px-3 py-2 text-left text-sm"
                        style={{ background: 'var(--panel-2)', border: '1px solid var(--border)', borderRadius: 10, cursor: 'pointer', color: 'var(--text)' }}>
                        <span className="grid place-items-center shrink-0" style={{ width: 18, height: 18, borderRadius: 5, background: on ? 'var(--ok)' : 'var(--raise)', color: '#12140f' }}>
                          {on && <Icon name="check" size={12} />}
                        </span>
                        {hum(e)}
                      </button>
                    );
                  })}
                </div>
                <p className="text-xs font-mono mt-3" style={{ color: 'var(--faint)' }}>
                  Strict claim policy rejects unsupported superlatives (e.g. “best investment”, “guaranteed returns”).
                </p>
              </>
            )}
            {step === 'advanced' && (
              <>
                <div className="eyebrow mb-4" style={{ color: 'var(--accent)' }}>5 · Advanced</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Sel label="Generation mode" value={brief.generation_mode} onChange={(v) => set('generation_mode', v)} opts={options.generation_mode} />
                  <label className="block"><span className="label">Campaign version</span>
                    <input className="input" value="brief-v1" readOnly style={{ opacity: 0.7 }} /></label>
                </div>
                <p className="text-xs font-mono mt-3" style={{ color: 'var(--faint)' }}>
                  Controlled mode = same input + same structure → reproducible campaigns. The renderer + strategy versions are pinned for auditability.
                </p>
              </>
            )}

            {/* Wizard footer: step nav + generate */}
            <div className="flex items-center justify-between mt-6 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
              <div className="flex gap-2">
                {STEPS.findIndex((s) => s.key === step) > 0 && (
                  <button className="btn btn-sm btn-ghost" onClick={() => setStep(STEPS[STEPS.findIndex((s) => s.key === step) - 1].key)}>← Back</button>
                )}
                {STEPS.findIndex((s) => s.key === step) < STEPS.length - 1 && (
                  <button className="btn btn-sm btn-ghost" onClick={() => setStep(STEPS[STEPS.findIndex((s) => s.key === step) + 1].key)}>Next →</button>
                )}
              </div>
              <button className="btn btn-accent" onClick={generate} disabled={busy === 'generate'}>
                {busy === 'generate' ? <><Spinner size={16} /> Generating…</> : <><Icon name="spark" size={16} /> Generate Campaign</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Verified property data (table) ─────────────────────── */}
      {km && (
        <Section icon="shield" title="Verified property data"
          right={
            <div className="flex gap-2">
              <button className={cx('btn btn-sm', dataView === 'table' ? 'btn-accent' : 'btn-ghost')} onClick={() => setDataView('table')}>Table</button>
              <button className={cx('btn btn-sm', dataView === 'evidence' ? 'btn-accent' : 'btn-ghost')} onClick={() => setDataView('evidence')}>Evidence</button>
            </div>
          }>
          {dataView === 'table'
            ? <VerifiedTable km={km} document={extracted.document || document} />
            : (
              <div className="space-y-2 max-h-96 overflow-auto">
                {(km.claims || []).map((c, i) => (
                  <div key={i}>
                    <div className="text-sm"><b>{hum(c.field)}</b> = {String(c.value)}
                      <span className="chip ml-2">p{c.source?.page} · {Math.round((c.confidence || 0) * 100)}%</span></div>
                    {c.source?.text && <div className="evidence mt-1">“{c.source.text}”</div>}
                  </div>
                ))}
              </div>
            )}
        </Section>
      )}

      {/* ── Result ─────────────────────────────────────────────── */}
      {result && (
        <>
          <div className="grid gap-3 mb-5" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px,1fr))' }}>
            <Stat label="Angle" value={hum(result.marketing?.angle)} />
            <Stat label="Audience" value={hum(result.brief?.target_audience)} />
            <Stat label="Slides" value={result.contract?.carousel?.images?.length || result.carousel?.slides?.length} />
            <Stat label="Claim guard" value={result.claim_violations?.length ? 'FLAGGED' : 'CLEAN'} ok={!result.claim_violations?.length} />
            <Stat label="Cost (USD)" value={result.usage?.est_cost_usd} />
            <Stat label="Review" value={hum(result.persisted?.status)} />
          </div>

          <div className="panel p-4 mb-5 flex flex-wrap items-center justify-between gap-3">
            <span className="eyebrow">Campaign #{result.persisted?.campaign_id} · {hum(result.brief?.goal)}</span>
            <div className="flex gap-2">
              <button className="btn btn-sm btn-danger" onClick={() => setStatus('REJECTED')}><Icon name="x" size={14} /> Reject</button>
              <button className="btn btn-sm btn-accent" onClick={() => setStatus('AUTO_APPROVED')}><Icon name="check" size={14} /> Approve</button>
            </div>
          </div>

          <Section icon="spark" title="Marketing & caption">
            <div className="text-sm mb-2" style={{ color: 'var(--muted)' }}>{result.marketing?.angle_rationale}</div>
            <div className="text-sm" style={{ whiteSpace: 'pre-wrap' }}>{result.contract?.caption}</div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {(result.contract?.hashtags || []).map((h) => <span key={h} className="chip">#{h}</span>)}
            </div>
          </Section>

          <Section icon="building" title={`Carousel — ${blueprint.length || result.carousel?.slides?.length || 0} slides`}
            right={<button className="btn btn-sm btn-ghost" onClick={rerender} disabled={slideBusy !== null}>Re-render all</button>}>
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(180px,1fr))' }}>
              {(blueprint.length ? blueprint : (result.carousel?.slides || [])).map((s, i) => {
                const img = campaignImages[i];
                return (
                  <div key={i} className="panel p-2" style={{ background: 'var(--panel-2)', borderColor: s.locked ? 'var(--accent)' : 'var(--border)' }}>
                    {img ? <a href={img} target="_blank" rel="noreferrer"><img src={img} alt={`slide ${i + 1}`} style={{ width: '100%', borderRadius: 8, display: 'block' }} /></a>
                      : <div style={{ aspectRatio: '4/5', background: 'var(--raise)', borderRadius: 8 }} />}
                    <div className="mt-1.5 text-xs font-mono" style={{ color: 'var(--faint)' }}>{i + 1}. {s.template} {s.locked && '🔒'}</div>
                    <div className="text-sm" style={{ fontWeight: 600, lineHeight: 1.15 }}>{s.headline}</div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      <button className="btn btn-sm btn-accent" onClick={() => setEditIdx(i)}><Icon name="edit" size={13} /> Edit</button>
                      <button className="btn btn-sm btn-ghost" disabled={slideBusy !== null} onClick={() => slideLock(i, !s.locked)}>{s.locked ? 'Unlock' : 'Lock'}</button>
                      <button className="btn btn-sm btn-ghost" disabled={slideBusy !== null || s.locked} onClick={() => slideRegen(i, 'image')}>{slideBusy === i ? '…' : 'Image'}</button>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="text-xs font-mono mt-3" style={{ color: 'var(--faint)' }}>
              Lock a slide to protect it from regeneration. Copy/Image regenerate that slide only, grounded in verified facts.
            </p>
          </Section>

          <Section icon="check" title="Publish & analytics"
            right={result.persisted?.status === 'PUBLISHED' ? <span className="pill pill-ok">published</span> : null}>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto] gap-3 items-end">
              <label className="block">
                <span className="label">Instagram account</span>
                <select className="select" value={pubAccount} onChange={(e) => setPubAccount(e.target.value)}>
                  {accounts.length === 0 && <option value="">No accounts (add in Settings)</option>}
                  {accounts.map((a) => <option key={a.id} value={String(a.id)}>{a.label}{a.has_token ? '' : ' (no token)'}</option>)}
                </select>
              </label>
              <button className="btn btn-sm btn-ghost" onClick={dryRun} disabled={pubBusy !== ''}>{pubBusy === 'dry' ? '…' : 'Dry-run'}</button>
              <button className="btn btn-sm btn-accent" onClick={publishReal} disabled={pubBusy !== '' || result.persisted?.status !== 'AUTO_APPROVED'}>
                {pubBusy === 'pub' ? 'Publishing…' : 'Publish to Instagram'}
              </button>
              <button className="btn btn-sm btn-ghost" onClick={syncAnalytics} disabled={pubBusy !== ''}>{pubBusy === 'an' ? '…' : 'Sync insights'}</button>
            </div>
            {result.persisted?.status !== 'AUTO_APPROVED' && (
              <p className="text-xs font-mono mt-2" style={{ color: 'var(--faint)' }}>Approve the campaign to enable live publishing. Dry-run works anytime.</p>
            )}
            {pubResult && (
              <div className="mt-3 text-sm">
                {pubResult.note && (
                  <div className="pill pill-warn mb-2" style={{ display: 'block', whiteSpace: 'normal', lineHeight: 1.4 }}>{pubResult.note}</div>
                )}
                {pubResult.dry_run
                  ? <>Dry-run · {pubResult.slides} slides{pubResult.posts > 1 ? ` → ${pubResult.posts} carousel posts` : ''} → <b>{pubResult.account}</b>. First public URL:
                    <div className="evidence mt-1">{(pubResult.public_images || [])[0]}</div></>
                  : <>Published ✓{pubResult.posts > 1 ? ` (${pubResult.posts} carousels)` : ''}
                    {(pubResult.permalinks || [pubResult.permalink]).filter(Boolean).map((u, k) => (
                      <div key={k}><a href={u} target="_blank" rel="noreferrer">{u}</a></div>
                    ))}</>}
              </div>
            )}
            {insights && (
              <div className="mt-3">
                <div className="eyebrow mb-1">Insights · score {insights.score}</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(insights.metrics || {}).map(([k, v]) => <span key={k} className="chip">{k}: {String(v)}</span>)}
                </div>
              </div>
            )}
          </Section>
        </>
      )}

      {editIdx !== null && cid() && (
        <SlideEditor cid={cid()} startIndex={editIdx} notify={notify}
          onClose={() => { setEditIdx(null); refreshBlueprint(); }} />
      )}
    </div>
  );
}
