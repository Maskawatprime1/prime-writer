import { useEffect, useState } from "react";
import { AppWindow, ArrowLeft, BookA, Keyboard, Languages, RefreshCw, Sparkles, TextCursorInput, Trash2, X } from "lucide-react";
import { MODES, addWord, api, getApps, getConfig, removeWord, setConfig, toggleApp, type AppRow, type Config } from "./api";
import { navigate } from "./main";
import { FullLogo, Logo, Switch, useToast } from "./ui";

const LANGS: Record<string, string> = { "en-US": "American English", "en-GB": "British English", "en-CA": "Canadian English", "en-AU": "Australian English" };

export default function Settings() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [apps, setApps] = useState<AppRow[]>([]);
  const [q, setQ] = useState("");
  const [word, setWord] = useState("");
  const [trig, setTrig] = useState("");
  const [snip, setSnip] = useState("");
  const [hk, setHk] = useState<Record<string, string>>({});
  const [about, setAbout] = useState<{ version: string; copyright: string; license: string } | null>(null);
  const [toast, show] = useToast();

  const load = () => getConfig().then((c) => { setCfg(c); setHk(c.hotkeys); }).catch((e) => show(e.message, true));
  const loadApps = () => getApps().then((r) => setApps(r.apps)).catch(() => {});
  useEffect(() => { load(); loadApps(); api<typeof about>("/api/about").then(setAbout).catch(() => {}); }, []);

  async function save(patch: Partial<Config>, msg: string) {
    try { const c = await setConfig(patch); setCfg(c); show(msg); if (c.hotkey_errors?.length) show(c.hotkey_errors.join(". "), true); }
    catch (e) { show((e as Error).message, true); load(); }
  }

  if (!cfg) return <div className="shell"><div className="settings"><div className="settings-inner muted">Loading settings…</div></div></div>;

  const Row = ({ title, desc, children }: { title: string; desc?: React.ReactNode; children: React.ReactNode }) => (
    <div className="setrow"><div className="txt"><b>{title}</b>{desc && <span>{desc}</span>}</div>{children}</div>
  );
  const toggle = (key: keyof Config, on: string, off: string) => (v: boolean) => save({ [key]: v } as Partial<Config>, v ? on : off);
  const shownApps = apps.filter((a) => !q || a.exe.includes(q.toLowerCase()) || a.title.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="shell" style={{ gridTemplateRows: "auto 1fr" }}>
      <header className="topbar">
        <button className="btn ghost" onClick={() => navigate("/")}><ArrowLeft size={16} />Back to editor</button>
        <div className="brand" style={{ marginLeft: 8 }}><Logo />Prime Writer</div>
      </header>
      <div className="settings">
        <div className="settings-inner">
          <h1>Settings</h1>

          <section className="section">
            <h2><Sparkles size={17} />Everywhere on your PC</h2>
            <p>Prime Writer underlines mistakes as you type in other apps (Chrome, Word, Notepad, chat apps…). Hover an underline for fixes, or click the round button in a text box for the full panel.</p>
            <Row title="On in all apps" desc="Master switch for live underlines and hotkeys in other apps.">
              <Switch checked={cfg.enabled} onChange={toggle("enabled", "On in all apps", "Off everywhere")} />
            </Row>
            <Row title="Underline mistakes while typing" desc="Live underlines in any app's text box.">
              <Switch checked={cfg.live} onChange={toggle("live", "Live underlines on", "Live underlines off")} />
            </Row>
            <Row title="AI suggestions while typing" desc="Adds AI checks after you pause (uses the GPU). Off = LanguageTool only.">
              <Switch checked={cfg.live_ai} onChange={toggle("live_ai", "AI while typing on", "LanguageTool only while typing")} />
            </Row>
            <Row title="Readability highlights in other apps" desc="Passive voice, wordy phrases, adverbs and long sentences.">
              <Switch checked={cfg.live_readability} onChange={toggle("live_readability", "Readability highlights on", "Readability highlights off")} />
            </Row>
            <Row title="Synonyms when you select a word" desc="Select or double-click one word in any app to see synonyms.">
              <Switch checked={cfg.synonyms_on_select} onChange={toggle("synonyms_on_select", "Synonyms on", "Synonyms off")} />
            </Row>
            <Row title="Prime Writer button in WeChat" desc={<>WeChat hides its message box from Windows, so it can't show underlines. A <b>P</b> button appears instead: click it to check or paraphrase what you've typed, then Replace.</>}>
              <Switch checked={cfg.fallback_button} onChange={toggle("fallback_button", "WeChat button on", "WeChat button off")} />
            </Row>
            <Row title="Floating button position" desc="Drag the round Prime Writer button anywhere; it remembers the spot for each app.">
              <button className="btn" disabled={!Object.keys(cfg.button_pos || {}).length} onClick={() => save({ button_pos: {} }, "Button positions reset")}>Reset</button>
            </Row>
            <Row title="Start with Windows" desc={cfg.desktop ? "Runs in the tray when you sign in." : "Available in the desktop app (PrimeWriter.exe)."}>
              <Switch checked={cfg.start_with_windows} disabled={!cfg.desktop} onChange={toggle("start_with_windows", "Will start with Windows", "Won't start with Windows")} />
            </Row>
          </section>

          <section className="section">
            <h2><Keyboard size={17} />Hotkeys</h2>
            <p>Select text in any app and press a hotkey to open the quick panel.</p>
            {(["check", "paraphrase"] as const).map((k) => (
              <Row key={k} title={k === "check" ? "Check grammar" : "Paraphrase"} desc={<>Current: <span className="kbd">{cfg.hotkeys[k]}</span></>}>
                <input className="input" style={{ width: 150, textAlign: "center" }} value={hk[k] || ""}
                  onChange={(e) => setHk({ ...hk, [k]: e.target.value })}
                  onBlur={() => hk[k] !== cfg.hotkeys[k] && save({ hotkeys: { [k]: hk[k] } }, "Hotkey saved")} />
              </Row>
            ))}
            <Row title="Default paraphrase mode" desc="Used when the quick panel opens.">
              <select className="input" value={cfg.popup_mode} onChange={(e) => save({ popup_mode: e.target.value }, "Saved")}>
                {Object.entries(MODES).map(([m, l]) => <option key={m} value={m}>{l}</option>)}
              </select>
            </Row>
          </section>

          <section className="section">
            <h2><Languages size={17} />Language</h2>
            <Row title="English variety" desc="Spelling and vocabulary for checks and rewrites (color / colour).">
              <select className="input" value={cfg.language} onChange={(e) => save({ language: e.target.value }, "Language saved")}>
                {Object.entries(LANGS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </Row>
            <Row title="Picky mode" desc="Stricter style and punctuation rules.">
              <Switch checked={cfg.picky} onChange={toggle("picky", "Picky mode on", "Picky mode off")} />
            </Row>
          </section>

          <section className="section">
            <h2><BookA size={17} />Personal dictionary</h2>
            <p>Words here are never marked as spelling mistakes. Add more from any suggestion with “Add to dictionary”.</p>
            <div className="setrow" style={{ borderTop: 0 }}>
              <input className="input" style={{ flex: 1 }} placeholder="Add a word…" value={word} onChange={(e) => setWord(e.target.value)}
                onKeyDown={async (e) => { if (e.key === "Enter" && word.trim()) { const r = await addWord(word.trim()); setCfg({ ...cfg, dictionary: r.dictionary }); setWord(""); show("Added"); } }} />
              <button className="btn" disabled={!word.trim()} onClick={async () => { const r = await addWord(word.trim()); setCfg({ ...cfg, dictionary: r.dictionary }); setWord(""); show("Added"); }}>Add</button>
            </div>
            <div className="freeze-chips" style={{ paddingBottom: 14 }}>
              {cfg.dictionary.length ? cfg.dictionary.map((w) => (
                <span key={w} className="fchip">{w}<button title="Remove" onClick={async () => { const r = await removeWord(w); setCfg({ ...cfg, dictionary: r.dictionary }); }}><X size={12} /></button></span>
              )) : <span className="muted small">No words yet.</span>}
            </div>
          </section>

          <section className="section">
            <h2><TextCursorInput size={17} />Snippets</h2>
            <p>Type a trigger, then a space or punctuation, and it expands, here and in any app. Example: <code className="kbd">;addr</code> → your address.</p>
            {Object.entries(cfg.snippets).map(([k, v]) => (
              <div key={k} className="snip">
                <code>{k}</code><div className="val">{v}</div>
                <button className="icon-btn" title="Delete" onClick={() => { const s = { ...cfg.snippets }; delete s[k]; save({ snippets: s }, "Snippet deleted"); }}><Trash2 size={16} /></button>
              </div>
            ))}
            <div className="snip" style={{ paddingBottom: 14 }}>
              <input className="input" style={{ width: 120 }} placeholder=";trigger" value={trig} onChange={(e) => setTrig(e.target.value)} />
              <textarea className="input" style={{ flex: 1 }} rows={2} placeholder="Text to insert" value={snip} onChange={(e) => setSnip(e.target.value)} />
              <button className="btn primary" disabled={!trig.trim() || !snip} onClick={() => { save({ snippets: { ...cfg.snippets, [trig.trim()]: snip } }, `Snippet ${trig.trim()} saved`); setTrig(""); setSnip(""); }}>Add</button>
            </div>
          </section>

          <section className="section">
            <h2><AppWindow size={17} />Apps
              <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                <input className="input" style={{ width: 180, fontWeight: 400 }} placeholder="Search apps…" value={q} onChange={(e) => setQ(e.target.value)} />
                <button className="btn" onClick={loadApps}><RefreshCw size={15} />Refresh</button>
              </span>
            </h2>
            <p>Turn Prime Writer off in specific apps. When it's off, nothing is shown there and the hotkeys go to the app untouched.</p>
            {shownApps.map((a) => (
              <div key={a.exe} className="setrow app-row">
                <div className="txt"><b>{a.exe.replace(/\.exe$/, "")}{a.running && <span className="tag">open</span>}</b><div className="ttl">{a.title || a.exe}</div></div>
                <Switch checked={a.enabled} onChange={async (v) => { await toggleApp(a.exe, v); setApps(apps.map((x) => x.exe === a.exe ? { ...x, enabled: v } : x)); show(`${v ? "On" : "Off"} in ${a.exe}`); }} />
              </div>
            ))}
            {!shownApps.length && <p className="muted small" style={{ padding: "8px 0 14px" }}>No apps found.</p>}
          </section>

          <section className="section about" id="about">
            <div className="about-head">
              <FullLogo height={64} />
              <div>
                <h2 style={{ margin: 0 }}>Prime Writer {about?.version}</h2>
                <div className="muted small">{about?.copyright}. Made by Maskawat Al Sium.</div>
              </div>
            </div>
            <p>Free for personal and non-commercial use under the <b>{about?.license}</b>. Selling it, or publishing it under another name, is not permitted.</p>
            <div className="about-links">
              <a className="btn sm" href="/license" target="_blank" rel="noreferrer">License</a>
              <a className="btn sm" href="/notices" target="_blank" rel="noreferrer">Third-party notices</a>
            </div>
          </section>
        </div>
      </div>
      {toast}
    </div>
  );
}
