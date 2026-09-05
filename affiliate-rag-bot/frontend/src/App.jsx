import React, { useEffect, useMemo, useRef, useState } from "react";

// ── tiny JSON syntax highlighter ────────────────────────────────────────────
function highlight(obj) {
  const json = JSON.stringify(obj, null, 2)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g,
    (m) => {
      let c = "n";
      if (/^"/.test(m)) c = /:$/.test(m) ? "k" : "s";
      else if (/true|false/.test(m)) c = "b";
      else if (/null/.test(m)) c = "nu";
      return `<span class="${c}">${m}</span>`;
    }
  );
}

const DEFAULT_CATS = [
  { name: "fashion", rate: 9 }, { name: "home", rate: 8 }, { name: "kitchen", rate: 7 },
  { name: "beauty", rate: 6 }, { name: "fitness", rate: 5 }, { name: "toys", rate: 5 },
  { name: "books", rate: 4 }, { name: "electronics", rate: 4 },
];

export default function App() {
  const [cats, setCats] = useState(DEFAULT_CATS);
  const [selected, setSelected] = useState(["home"]);
  const [count, setCount] = useState(3);
  const [dryRun, setDryRun] = useState(true);

  const [reqText, setReqText] = useState("");
  const [dirty, setDirty] = useState(false);          // user manually edited the JSON
  const [resp, setResp] = useState(null);
  const [httpStatus, setHttpStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [ready, setReady] = useState("checking config…");
  const [showRaw, setShowRaw] = useState(false);
  const timer = useRef(null);

  // Build the request object from the control panel.
  const built = useMemo(
    () => ({ categories: selected, products_per_run: count, dry_run: dryRun }),
    [selected, count, dryRun]
  );

  // Keep the JSON textarea in sync with the controls (unless the user edited it).
  useEffect(() => {
    if (!dirty) setReqText(JSON.stringify(built, null, 2));
  }, [built, dirty]);

  // Load categories + readiness from the backend.
  useEffect(() => {
    fetch("/api/categories").then((r) => r.json())
      .then((d) => { if (d?.categories?.length) setCats(d.categories); }).catch(() => {});
    fetch("/api/config").then((r) => r.json()).then((c) => {
      const todo = (c.setup || []).filter((s) => s.required && !s.ok).map((s) => s.label);
      setReady(c.ready ? `ready ✓ · ${c.model}` : `setup needed: ${todo.join(", ") || "—"}`);
    }).catch(() => setReady(""));
  }, []);

  function toggleCat(name) {
    setDirty(false);
    setSelected((cur) => (cur.includes(name) ? cur.filter((c) => c !== name) : [...cur, name]));
  }

  function startTimer() {
    const t0 = Date.now();
    setElapsed(0);
    timer.current = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100);
  }
  function stopTimer() { if (timer.current) { clearInterval(timer.current); timer.current = null; } }

  async function run() {
    let payload;
    try { payload = JSON.parse(reqText); }
    catch (e) { setHttpStatus("bad-json"); setResp({ error: "Invalid JSON in request: " + e.message }); return; }

    setRunning(true); setHttpStatus(null); setShowRaw(false); startTimer();
    try {
      const r = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      setHttpStatus(r.status);
      setResp(data);
    } catch (e) {
      setHttpStatus("net"); setResp({ ok: false, error: String(e) });
    } finally { stopTimer(); setRunning(false); }
  }

  // status pill for the response header
  const pill = (() => {
    if (running) return { t: `running… ${elapsed.toFixed(1)}s`, c: "run" };
    if (httpStatus === null) return { t: "idle", c: "" };
    if (httpStatus === "bad-json") return { t: "invalid JSON", c: "bad" };
    if (httpStatus === "net") return { t: "network error", c: "bad" };
    if (httpStatus === 409) return { t: "busy (409)", c: "warn" };
    if (httpStatus === 422) return { t: "invalid input (422)", c: "bad" };
    if (resp?.ok) return { t: `done (200)`, c: "ok" };
    if (resp?.status === "partial") return { t: "partial (200)", c: "warn" };
    return { t: `${resp?.status || "error"} (${httpStatus})`, c: "bad" };
  })();

  return (
    <>
      <header>
        <h1>Affiliate Bot</h1>
        <span className="tag">JSON API · gpt-5-nano</span>
        <span className="ready">{ready}</span>
        <span className="spacer" />
        <a href="/docs" target="_blank" rel="noopener">OpenAPI /docs</a>
      </header>

      <main>
        {/* ── REQUEST ─────────────────────────────────────────── */}
        <section className="col">
          <div className="head">
            <h2>Request · POST /api/run</h2>
            <span className="spacer" />
            <button onClick={() => { setDirty(false); }}>Reset JSON</button>
            <button className="primary" onClick={run} disabled={running}>
              {running ? "Running…" : "Run ▷"}
            </button>
          </div>

          <div className="panel">
            <div className="field">
              <label>Categories · multi-select ({selected.length})</label>
              <div className="chips">
                {cats.map((c) => (
                  <span key={c.name}
                        className={"chip" + (selected.includes(c.name) ? " on" : "")}
                        onClick={() => toggleCat(c.name)}>
                    {c.name}<span className="rate">{c.rate}%</span>
                  </span>
                ))}
              </div>
            </div>

            <div className="row">
              <div className="field" style={{ margin: 0 }}>
                <label>Products per category</label>
                <div className="count">
                  <input type="range" min="1" max="25" value={count}
                         onChange={(e) => { setDirty(false); setCount(Number(e.target.value)); }} />
                  <span className="num">{count}</span>
                </div>
              </div>
              <div className="field" style={{ margin: 0 }}>
                <label>Mode</label>
                <label className="toggle">
                  <input type="checkbox" checked={dryRun}
                         onChange={(e) => { setDirty(false); setDryRun(e.target.checked); }} />
                  dry_run (post nothing)
                </label>
              </div>
            </div>
            <div className="muted">
              Editing the JSON below overrides the controls. Ctrl/⌘+Enter to run.
            </div>
          </div>

          <textarea
            value={reqText}
            spellCheck={false}
            onChange={(e) => { setDirty(true); setReqText(e.target.value); }}
            onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run(); }}
          />
        </section>

        {/* ── RESPONSE ────────────────────────────────────────── */}
        <section className="col">
          <div className="head">
            <h2>Response</h2>
            <span className="spacer" />
            <span className={"pill " + pill.c}>{pill.t}</span>
            <button onClick={() => setShowRaw((v) => !v)}>{showRaw ? "Cards" : "Raw JSON"}</button>
          </div>

          {resp && !showRaw && resp.runs ? (
            <div className="scroll">
              <div className="summary">
                <div className="stat"><b>{resp.status}</b><span>status</span></div>
                <div className="stat"><b>{resp.run_count ?? resp.runs.length}</b><span>categories</span></div>
                <div className="stat"><b>{resp.posted_count ?? 0}</b><span>posted</span></div>
                <div className="stat"><b>{resp.elapsed_seconds ?? "–"}s</b><span>elapsed</span></div>
              </div>
              {resp.runs.map((r, i) => <RunCard key={i} run={r} />)}
            </div>
          ) : (
            <pre className="scroll"
                 dangerouslySetInnerHTML={{ __html: resp ? highlight(resp) : "// The JSON response appears here." }} />
          )}

          <div className="hint">
            {resp?.runs
              ? `${resp.run_count} categor${resp.run_count === 1 ? "y" : "ies"} · ${resp.posted_count} posted · toggle Raw JSON for the full contract.`
              : "Pick categories, set the count, hit Run. dry_run=true posts nothing."}
          </div>
        </section>
      </main>
    </>
  );
}

// ── one category's result ───────────────────────────────────────────────────
function RunCard({ run }) {
  const [open, setOpen] = useState(true);
  const cat = run?.input?.category ?? "?";
  const cls = run.ok ? "ok" : run.status === "aborted" ? "warn" : "bad";
  return (
    <div className="runcard">
      <div className="rc-head" onClick={() => setOpen((v) => !v)}>
        <b>{cat}</b>
        <span className={"pill " + cls}>{run.status}</span>
        <span className="muted">{(run.pins || []).length} pins · {run.posted_count} posted · {run.elapsed_seconds}s</span>
        <span className="spacer" />
        <span className="muted">{open ? "▾" : "▸"}</span>
      </div>
      {open && (
        <div className="rc-body">
          {(run.pins || []).map((p, i) => (
            <div className="pin" key={i}>
              <div className="pt">{p.pin_title || "(no title)"} {p.posted ? "✅" : ""}</div>
              <div className="pd">{p.pin_description}</div>
              <div className="tags">{(p.hashtags || []).map((h) => "#" + h).join(" ")}</div>
            </div>
          ))}
          {(run.errors || []).length > 0 && (
            <ul className="errlist">{run.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
          )}
          {(run.pins || []).length === 0 && (run.errors || []).length === 0 && (
            <div className="muted">No pins produced.</div>
          )}
        </div>
      )}
    </div>
  );
}
