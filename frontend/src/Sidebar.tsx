import { useEffect, useState } from "react";
import type { Editor } from "@tiptap/react";
import { BookPlus, CheckCircle2, ClipboardCopy, Loader2, Repeat2, Wand2, X } from "lucide-react";
import { MODES, addWord, local, paraphrase, saveLocal } from "./api";
import type { DocIssue } from "./extensions";
import { category, docToText, fitToSelection, wordDiff, type Stats } from "./text";
import { RewriteBox, canRewrite, isWord, issueLabel, useRewrite } from "./Cards";
import { ScoreRing } from "./ui";

type Tab = "suggest" | "para" | "stats";
type Filter = "all" | "correctness" | "clarity" | "style";
const STRENGTH = ["Minimal", "Light", "Medium", "Strong", "Max"];

type Props = {
  editor: Editor;
  issues: DocIssue[];
  active: number | null;
  counts: { correctness: number; clarity: number; style: number };
  score: number;
  stats: Stats;
  errors: string[];
  checking: "" | "rules" | "ai";
  text: string;
  onFocus: (id: number) => void;
  onApply: (it: DocIssue, rep: string) => void;
  onIgnore: (it: DocIssue) => void;
  onAddWord: (w: string) => void;
  replaceRange: (from: number, to: number, expected: string, text: string) => boolean;
  showToast: (t: string, bad?: boolean) => void;
};

export default function Sidebar(p: Props) {
  const [tab, setTab] = useState<Tab>(() => local("pw-tab", "suggest" as Tab));
  useEffect(() => saveLocal("pw-tab", tab), [tab]);
  return (
    <aside className="side">
      <div className="tabs" role="tablist">
        <button className={"tab" + (tab === "suggest" ? " on" : "")} onClick={() => setTab("suggest")}>Suggestions <span className="count">{p.issues.length}</span></button>
        <button className={"tab" + (tab === "para" ? " on" : "")} onClick={() => setTab("para")}>Paraphrase</button>
        <button className={"tab" + (tab === "stats" ? " on" : "")} onClick={() => setTab("stats")}>Stats</button>
      </div>
      {tab === "suggest" && <Suggestions {...p} />}
      {tab === "para" && <Paraphrase editor={p.editor} replaceRange={p.replaceRange} showToast={p.showToast} />}
      {tab === "stats" && <StatsPane stats={p.stats} issues={p.issues} score={p.score} />}
    </aside>
  );
}

/* ---------------- Suggestions ---------------- */
function Suggestions({ issues, active, counts, score, stats, errors, checking, onFocus, onApply, onIgnore, onAddWord, replaceRange, editor }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = issues.filter((i) => filter === "all" || category(i.kind, i.scope) === filter);
  const fixable = issues.filter((i) => category(i.kind, i.scope) === "correctness" && i.replacements.length);
  const fixAll = () => {
    // apply from the end so earlier positions stay valid
    [...fixable].sort((a, b) => b.from - a.from).forEach((it) => onApply(it, it.replacements[0]));
  };
  const headline = !stats.words ? "Start writing" : score >= 90 ? "Looking great" : score >= 75 ? "Good, a few fixes" : score >= 55 ? "Needs some work" : "Needs attention";
  return (
    <div className="pane">
      <div className="score-head">
        <ScoreRing value={stats.words ? score : 100} />
        <div style={{ flex: 1 }}>
          <h3>{headline}</h3>
          <div className="muted small">
            {checking === "rules" ? "Checking…" : checking === "ai" ? <><Loader2 size={12} className="spin" /> AI is reviewing your text…</> : `Overall writing score · ${issues.length} suggestion${issues.length === 1 ? "" : "s"}`}
          </div>
        </div>
      </div>
      <div className="filters">
        {([["all", "All", issues.length, ""], ["correctness", "Correctness", counts.correctness, "k-spelling"],
          ["clarity", "Clarity", counts.clarity, "k-clarity"], ["style", "Style", counts.style, "k-style"]] as const).map(([k, l, n, cls]) => (
          <button key={k} className={"chip " + cls + (filter === k ? " on" : "")} onClick={() => setFilter(k)}>
            {cls && <span className="dot" />}{l} <b>{n}</b>
          </button>
        ))}
      </div>
      {fixable.length > 1 && filter !== "clarity" && filter !== "style" && (
        <button className="btn sm" onClick={fixAll} style={{ alignSelf: "flex-start" }}><CheckCircle2 size={15} />Accept all {fixable.length} corrections</button>
      )}
      {errors.length > 0 && <div className="errors">{errors.join(" · ")}</div>}
      {shown.length === 0 ? (
        <div className="empty">
          <CheckCircle2 size={34} />
          <div>{stats.words ? (checking ? "Checking your writing…" : "No issues found. Nice work!") : "Your suggestions will appear here as you write."}</div>
        </div>
      ) : shown.map((it) => (
        <SuggestionCard key={it.id} it={it} open={it.id === active} onOpen={() => onFocus(it.id)} onApply={onApply}
          onIgnore={onIgnore} onAddWord={onAddWord} replaceRange={replaceRange} editor={editor} />
      ))}
    </div>
  );
}

function SuggestionCard({ it, open, onOpen, onApply, onIgnore, onAddWord, replaceRange, editor }: {
  it: DocIssue; open: boolean; onOpen: () => void; onApply: Props["onApply"]; onIgnore: Props["onIgnore"];
  onAddWord: Props["onAddWord"]; replaceRange: Props["replaceRange"]; editor: Editor;
}) {
  const [rw, runRewrite] = useRewrite(it, () => docToText(editor.state.doc));
  const sentence = it.scope === "sentence";
  const k = sentence ? "sentence" : it.kind;
  return (
    <div className={"scard k-" + k + (open ? " on" : "")}>
      <div className="scard-top" onClick={onOpen}>
        <span className="dot" />
        <div className="scard-line">
          {sentence ? <span className="muted">{it.original.slice(0, 70)}{it.original.length > 70 ? "…" : ""}</span> : (
            <><span className="strike">{it.original}</span>{it.replacements[0] !== undefined && <> → <span className="to">{it.replacements[0] || "remove"}</span></>}</>
          )}
        </div>
        <span className="scard-kind">{issueLabel(it)}</span>
      </div>
      {open && (
        <div className="scard-body">
          <div className="icard-msg">{it.message}</div>
          {!sentence && it.replacements.length > 0 && (
            <div className="reps">{it.replacements.slice(0, 4).map((r, i) => <button key={i} className="rep" onClick={() => onApply(it, r)}>{r || "Remove"}</button>)}</div>
          )}
          <RewriteBox rw={rw} onUse={(r) => replaceRange(r.from, r.to, r.source, r.text)} />
          <div className="icard-foot">
            {canRewrite(it) && <button className="link" onClick={runRewrite}><Wand2 size={12} /> Rewrite sentence</button>}
            {it.kind === "spelling" && isWord(it.original) && (
              <button className="link" onClick={async () => { await addWord(it.original); onAddWord(it.original); }}><BookPlus size={12} /> Add to dictionary</button>
            )}
            <span className="spacer" />
            <span className="muted small">{it.source}</span>
            <button className="link" onClick={() => onIgnore(it)}>Ignore</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Paraphrase ---------------- */
function Paraphrase({ editor, replaceRange, showToast }: { editor: Editor; replaceRange: Props["replaceRange"]; showToast: Props["showToast"] }) {
  const [mode, setMode] = useState<string>(() => local("pw-mode", "standard"));
  const [strength, setStrength] = useState<number>(() => local("pw-strength", 3));
  const [freeze, setFreeze] = useState<string[]>(() => local("pw-freeze", [] as string[]));
  const [freezeIn, setFreezeIn] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<{ source: string; out: string; from: number; to: number; whole: boolean; missing: string[] } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => saveLocal("pw-mode", mode), [mode]);
  useEffect(() => saveLocal("pw-strength", strength), [strength]);
  useEffect(() => saveLocal("pw-freeze", freeze), [freeze]);

  const { from, to, empty } = editor.state.selection;
  const selText = empty ? "" : editor.state.doc.textBetween(from, to, "\n");

  async function run() {
    const whole = !selText.trim();
    const source = whole ? editor.getText({ blockSeparator: "\n" }) : selText;
    if (!source.trim()) return;
    setBusy(true); setErr("");
    try {
      const r = await paraphrase(source, mode, { strength, freeze });
      setRes({ source, out: whole ? r.text : fitToSelection(source, r.text), from, to, whole, missing: r.missing_frozen || [] });
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  function replace() {
    if (!res) return;
    if (res.whole) {
      if (editor.getText({ blockSeparator: "\n" }) !== res.source) return showToast("The text changed. Paraphrase again.", true);
      editor.chain().focus().setContent({ type: "doc", content: res.out.split("\n").map((line) => ({ type: "paragraph", content: line ? [{ type: "text", text: line }] : [] })) }).run();
    } else if (!replaceRange(res.from, res.to, res.source, res.out)) return;
    setRes(null);
    showToast("Replaced");
  }
  const addFreeze = () => {
    const words = freezeIn.split(",").map((w) => w.trim()).filter((w) => w && !freeze.includes(w));
    if (words.length) setFreeze([...freeze, ...words]);
    setFreezeIn("");
  };

  return (
    <div className="pane">
      <div className="field-label">Mode</div>
      <div className="modes">{Object.entries(MODES).map(([m, l]) => <button key={m} className={"chip" + (mode === m ? " on" : "")} onClick={() => setMode(m)}>{l}</button>)}</div>
      <div className="field-label">How much to change</div>
      <div className="slider">
        <input type="range" min={1} max={5} value={strength} onChange={(e) => setStrength(Number(e.target.value))} aria-label="How much to change" />
        <b>{STRENGTH[strength - 1]}</b>
      </div>
      <div className="field-label">Freeze words</div>
      <input className="input" placeholder="Words to keep unchanged, then Enter" value={freezeIn}
        onChange={(e) => setFreezeIn(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") addFreeze(); }} />
      {freeze.length > 0 && (
        <div className="freeze-chips">{freeze.map((f) => (
          <span key={f} className="fchip">{f}<button title="Unfreeze" onClick={() => setFreeze(freeze.filter((x) => x !== f))}><X size={12} /></button></span>
        ))}</div>
      )}
      <div className="muted small">{selText.trim() ? `Rewrites your selection (${selText.length} characters).` : "Rewrites the whole document. Select text to rewrite just that part."}</div>
      <button className="btn primary block" onClick={run} disabled={busy}>
        {busy ? <><Loader2 size={16} className="spin" />Rewriting…</> : <><Repeat2 size={16} />Paraphrase</>}
      </button>
      {err && <div className="errors">{err}</div>}
      <div className={"para-out" + (res ? "" : " empty-out")}>
        {res ? wordDiff(res.source, res.out).map((d, i) => d.added ? <ins key={i} className="add">{d.text}</ins> : <span key={i}>{d.text}</span>)
          : "Your rewrite appears here. Changed words are highlighted."}
      </div>
      {res && res.missing.length > 0 && <div className="errors">Changed despite freeze: {res.missing.join(", ")}. Try again.</div>}
      {res && (
        <div className="row">
          <button className="btn primary" onClick={replace}>{res.whole ? "Replace document" : "Replace selection"}</button>
          <button className="btn" onClick={async () => { await navigator.clipboard.writeText(res.out); showToast("Copied"); }}><ClipboardCopy size={15} />Copy</button>
        </div>
      )}
    </div>
  );
}

/* ---------------- Stats ---------------- */
function StatsPane({ stats, issues, score }: { stats: Stats; issues: DocIssue[]; score: number }) {
  const n = (sub: string) => issues.filter((i) => i.sub === sub).length;
  const m: [string, string | number][] = [
    ["Words", stats.words.toLocaleString()], ["Characters", stats.characters.toLocaleString()],
    ["Sentences", stats.sentences], ["Paragraphs", stats.paragraphs],
    ["Reading time", stats.reading], ["Speaking time", stats.speaking],
    ["Avg. sentence", `${stats.avgSentence.toFixed(1)} words`], ["Grade level", stats.words ? stats.grade.toFixed(1) : "–"],
    ["Complex words", `${stats.complexPct.toFixed(0)}%`], ["Long sentences", issues.filter((i) => i.scope === "sentence").length],
    ["Passive voice", n("passive")], ["Adverbs", n("adverb")],
  ];
  return (
    <div className="pane">
      <div className="score-head">
        <ScoreRing value={stats.words ? stats.flesch : 0} color="var(--accent)" />
        <div><h3>{stats.words ? stats.label : "Readability"}</h3><div className="muted small">Flesch reading ease (higher = easier)</div></div>
      </div>
      <div className="score-head">
        <ScoreRing value={stats.words ? score : 100} />
        <div><h3>Writing score</h3><div className="muted small">Based on suggestions per 100 words</div></div>
      </div>
      <div className="metrics">{m.map(([k, v]) => <div key={k} className="metric"><b>{v}</b><span>{k}</span></div>)}</div>
    </div>
  );
}
