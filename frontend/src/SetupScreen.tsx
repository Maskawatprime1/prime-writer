import { useEffect, useState } from "react";
import { CheckCircle2, Cpu, Download, Loader2, Sparkles } from "lucide-react";
import { api } from "./api";
import { FullLogo } from "./ui";

type Setup = {
  ollama_installed: boolean;
  ollama_running: boolean;
  models: string[];
  ready: boolean;
  choices: { id: string; label: string; note: string; gb: number }[];
  task: { name: string; phase: string; done: number; total: number; error: string; running: boolean };
};

const gb = (n: number) => (n / 1e9).toFixed(n > 1e9 ? 1 : 2) + " GB";

/** First run on a new PC: install Ollama and download the AI model. */
export default function SetupScreen({ onDone, force = false }: { onDone: () => void; force?: boolean }) {
  const [s, setS] = useState<Setup | null>(null);
  const [model, setModel] = useState("qwen3:8b");
  const [err, setErr] = useState("");

  useEffect(() => {
    let live = true;
    const tick = () => api<Setup>("/api/setup").then((x) => { if (live) { setS(x); if (x.ready && !x.task.running && !force) onDone(); } }).catch(() => {});
    tick();
    const t = window.setInterval(tick, 1000);
    return () => { live = false; window.clearInterval(t); };
  }, [onDone, force]);

  async function start(path: string, body?: unknown) {
    setErr("");
    try { setS(await api<Setup>(path, body ?? {})); } catch (e) { setErr((e as Error).message); }
  }
  if (!s) return null;
  const t = s.task, busy = t.running;
  const step1 = s.ollama_running;
  const pct = t.total ? Math.min(100, (100 * t.done) / t.total) : 0;

  return (
    <div className="setup-wrap">
      <div className="setup">
        <div className="setup-head"><FullLogo height={92} /><div><h1>Welcome to Prime Writer</h1><p>Two quick steps to set up the offline AI on this PC.</p></div></div>

        <div className={"step" + (step1 ? " done" : "")}>
          <div className="step-ico">{step1 ? <CheckCircle2 size={22} /> : <Cpu size={22} />}</div>
          <div className="step-body">
            <b>1. Install Ollama</b>
            <span>The free engine that runs the AI on your PC, about 1 GB to download.</span>
            {!step1 && (
              <button className="btn primary" disabled={busy} onClick={() => start("/api/setup/ollama")}>
                <Download size={16} />{s.ollama_installed ? "Start Ollama" : "Install Ollama"}
              </button>
            )}
          </div>
        </div>

        <div className={"step" + (s.ready ? " done" : "") + (step1 ? "" : " off")}>
          <div className="step-ico">{s.ready ? <CheckCircle2 size={22} /> : <Sparkles size={22} />}</div>
          <div className="step-body">
            <b>2. Download the AI model</b>
            <span>Pick one. You can switch later.</span>
            <div className="choices">
              {s.choices.map((c) => (
                <label key={c.id} className={"choice" + (model === c.id ? " on" : "")}>
                  <input type="radio" name="model" checked={model === c.id} onChange={() => setModel(c.id)} disabled={!step1 || busy} />
                  <div><b>{c.label}</b> <span className="muted small">· {c.gb} GB</span><div className="muted small">{c.note}</div></div>
                </label>
              ))}
            </div>
            <button className="btn primary" disabled={!step1 || busy} onClick={() => start("/api/setup/model", { model })}>
              <Download size={16} />Download {model}
            </button>
          </div>
        </div>

        {(busy || t.error) && (
          <div className="progress-box">
            {busy && <div className="muted small"><Loader2 size={13} className="spin" /> {t.phase}{t.total ? ` · ${gb(t.done)} of ${gb(t.total)}` : ""}</div>}
            {busy && t.total > 0 && <div className="bar"><span style={{ width: pct + "%" }} /></div>}
            {t.error && <div className="errors">{t.error}</div>}
          </div>
        )}
        {err && <div className="errors">{err}</div>}
        <p className="muted small" style={{ margin: 0 }}>
          Grammar and spelling checks (LanguageTool) already work without the AI. <button className="link" onClick={onDone}>Skip for now</button>
        </p>
      </div>
    </div>
  );
}
