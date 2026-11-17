import { useEffect, useState } from "react";
import { BookPlus, Loader2, Wand2, X } from "lucide-react";
import { addWord, paraphrase, synonyms } from "./api";
import type { DocIssue } from "./extensions";
import { rangeFor, sentenceAround, type TextMap } from "./text";

const LABEL: Record<string, string> = {
  spelling: "Spelling", grammar: "Grammar", style: "Style", clarity: "Clarity",
  passive: "Passive voice", wordy: "Wordy phrase", qualifier: "Weak word", adverb: "Adverb", long: "Long sentence", "very-long": "Very long sentence",
};
export const issueLabel = (it: { kind: string; sub?: string; scope?: string }) =>
  it.scope === "sentence" ? "Long sentence" : LABEL[it.sub || ""] || LABEL[it.kind] || it.kind;
export const canRewrite = (it: DocIssue) => it.scope === "sentence" || ["passive", "adverb", "qualifier", "wordy"].includes(it.sub || "") || it.source === "AI";
export const isWord = (s: string) => /^[\p{L}'’-]+$/u.test(s);

type Rewrite = { status: "loading" } | { status: "done"; text: string; from: number; to: number; source: string } | { status: "error"; msg: string };

/** Ask the AI for a clearer version of the sentence around an issue. */
export function useRewrite(issue: DocIssue, map: () => TextMap) {
  const [rw, setRw] = useState<Rewrite | null>(null);
  useEffect(() => setRw(null), [issue.id]);
  async function run() {
    const m = map();
    const off = m.pos.indexOf(issue.from);
    const [s, e] = issue.scope === "sentence" || off < 0 ? [off, off + issue.original.length] : sentenceAround(m.text, off);
    const r = rangeFor(m, s, e - s);
    if (s < 0 || !r) return setRw({ status: "error", msg: "Couldn't find the sentence." });
    setRw({ status: "loading" });
    try {
      const out = await paraphrase(m.text.slice(s, e), "clarity");
      setRw({ status: "done", text: out.text, from: r.from, to: r.to, source: m.text.slice(s, e) });
    } catch (err) { setRw({ status: "error", msg: (err as Error).message }); }
  }
  return [rw, run] as const;
}

export function RewriteBox({ rw, onUse }: { rw: Rewrite | null; onUse: (r: Extract<Rewrite, { status: "done" }>) => void }) {
  if (!rw) return null;
  if (rw.status === "loading") return <div className="rewrite muted"><span><Loader2 size={14} className="spin" /> Rewriting…</span></div>;
  if (rw.status === "error") return <div className="errors">{rw.msg}</div>;
  return (
    <div className="rewrite">
      <div>{rw.text}</div>
      <div><button className="rep" onClick={() => onUse(rw)}>Use this</button></div>
    </div>
  );
}

type IssueCardProps = {
  issue: DocIssue;
  at: { left: number; top: number };
  text: string;
  onApply: (it: DocIssue, rep: string) => void;
  onIgnore: (it: DocIssue) => void;
  onAddWord: (w: string) => void;
  onClose: () => void;
  replaceRange: (from: number, to: number, expected: string, text: string) => boolean;
  map: () => TextMap;
};

export function IssueCard({ issue, at, onApply, onIgnore, onAddWord, onClose, replaceRange, map }: IssueCardProps) {
  const [rw, runRewrite] = useRewrite(issue, map);
  const sentence = issue.scope === "sentence";
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className={"float icard k-" + (sentence ? "sentence" : issue.kind)} style={{ left: at.left, top: at.top }}
      onMouseDown={(e) => e.preventDefault()}>
      <div className="icard-head">
        <span className="dot" />{issueLabel(issue)} · {issue.source}
        <button className="icon-btn x" style={{ width: 24, height: 24 }} onClick={onClose} title="Close (Esc)"><X size={14} /></button>
      </div>
      <p className="icard-msg">{issue.message}</p>
      {!sentence && (
        <div className="reps">
          <span className="strike">{issue.original}</span>
          {issue.replacements.slice(0, 4).map((r, i) => (
            <button key={i} className="rep" onClick={() => onApply(issue, r)}>{r || "Remove"}</button>
          ))}
        </div>
      )}
      <RewriteBox rw={rw} onUse={(r) => { if (replaceRange(r.from, r.to, r.source, r.text)) onClose(); }} />
      <div className="icard-foot">
        {canRewrite(issue) && <button className="link" onClick={runRewrite}><Wand2 size={12} /> Rewrite sentence</button>}
        {issue.kind === "spelling" && isWord(issue.original) && (
          <button className="link" onClick={async () => { await addWord(issue.original); onAddWord(issue.original); }}><BookPlus size={12} /> Add to dictionary</button>
        )}
        <span className="spacer" />
        <button className="link" onClick={() => onIgnore(issue)}>Ignore</button>
      </div>
    </div>
  );
}

type SynProps = { word: string; context: string; at: { left: number; top: number }; onPick: (w: string) => void; onClose: () => void };

export function SynonymCard({ word, context, at, onPick, onClose }: SynProps) {
  const [list, setList] = useState<string[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    setList(null); setErr("");
    synonyms(word, context).then((r) => live && setList(r.synonyms)).catch((e) => live && setErr(e.message));
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => { live = false; window.removeEventListener("keydown", k); };
  }, [word, context, onClose]);
  return (
    <div className="float icard" style={{ left: at.left, top: at.top, width: 320 }} onMouseDown={(e) => e.preventDefault()}>
      <div className="icard-head">Synonyms for <b style={{ color: "var(--text)" }}>{word}</b>
        <button className="icon-btn x" style={{ width: 24, height: 24 }} onClick={onClose}><X size={14} /></button>
      </div>
      {err ? <div className="errors">{err}</div> : !list ? <div className="muted small"><Loader2 size={13} className="spin" /> Finding words that fit…</div> : (
        <div className="reps">
          {list.length ? list.map((w) => <button key={w} className="rep soft" onClick={() => onPick(w)}>{w}</button>) : <span className="muted small">No synonyms found</span>}
        </div>
      )}
    </div>
  );
}
