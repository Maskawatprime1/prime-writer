import { useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { BookOpen, Bold, ChevronDown, Italic, Loader2, Repeat2, Scissors, Sparkles, SpellCheck, Underline, X } from "lucide-react";
import { MODES, local, paraphrase } from "./api";
import { fitToSelection, wordDiff } from "./text";

export type AiState = {
  label: string; mode: string; from: number; to: number; source: string;
  status: "loading" | "done" | "error"; out?: string; error?: string;
};

/** Notion/Plate-style menu that appears over selected text. */
export function SelectionMenu({ editor, onAi, onSynonyms }: { editor: Editor; onAi: (s: AiState) => void; onSynonyms: () => void }) {
  const [menu, setMenu] = useState(false);
  const { from, to } = editor.state.selection;
  const selected = editor.state.doc.textBetween(from, to, "\n");
  const oneWord = /^[\p{L}'’-]{2,30}$/u.test(selected.trim());
  useEffect(() => setMenu(false), [from, to]);

  const run = (mode: string, label: string) => {
    setMenu(false);
    onAi({ label, mode, from, to, source: selected, status: "loading" });
  };
  const keep = (e: React.MouseEvent) => e.preventDefault();

  return (
    <BubbleMenu editor={editor} options={{ placement: "top-start", offset: 8 }}
      shouldShow={({ state }) => !state.selection.empty && state.doc.textBetween(state.selection.from, state.selection.to).trim().length > 1}>
      <div className="bubble" onMouseDown={keep}>
        <button className="btn ghost ai" onClick={() => run("fluent", "Improve")}><Sparkles size={15} />Improve</button>
        <button className="btn ghost" onClick={() => run("fix", "Fix grammar")}><SpellCheck size={15} />Fix</button>
        <button className="btn ghost" onClick={() => run("concise", "Shorten")}><Scissors size={15} />Shorten</button>
        <div style={{ position: "relative" }}>
          <button className="btn ghost" onClick={() => setMenu(!menu)}><Repeat2 size={15} />Paraphrase<ChevronDown size={14} /></button>
          {menu && (
            <div className="menu">
              {Object.entries(MODES).filter(([m]) => m !== "fix").map(([m, l]) => (
                <button key={m} onClick={() => run(m, l)}>{l}</button>
              ))}
            </div>
          )}
        </div>
        {oneWord && <button className="btn ghost" onClick={onSynonyms}><BookOpen size={15} />Synonyms</button>}
        <span className="sep" />
        <button className={"icon-btn" + (editor.isActive("bold") ? " on" : "")} onClick={() => editor.chain().focus().toggleBold().run()}><Bold size={15} /></button>
        <button className={"icon-btn" + (editor.isActive("italic") ? " on" : "")} onClick={() => editor.chain().focus().toggleItalic().run()}><Italic size={15} /></button>
        <button className={"icon-btn" + (editor.isActive("underline") ? " on" : "")} onClick={() => editor.chain().focus().toggleUnderline().run()}><Underline size={15} /></button>
      </div>
    </BubbleMenu>
  );
}

type ResultProps = {
  editor: Editor;
  state: AiState;
  setState: (s: AiState | null) => void;
  anchorFor: (from: number, to: number) => { left: number; top: number } | null;
  replaceRange: (from: number, to: number, expected: string, text: string) => boolean;
};

/** Result panel for an AI action on the selection: Replace / Insert below / Try again. */
export function AiResult({ editor, state, setState, anchorFor, replaceRange }: ResultProps) {
  const req = useRef(0);
  const at = anchorFor(state.from, state.to);
  useEffect(() => {
    if (state.status !== "loading") return;
    const my = ++req.current;
    paraphrase(state.source, state.mode, { strength: local("pw-strength", 3), freeze: local("pw-freeze", [] as string[]) })
      .then((r) => my === req.current && setState({ ...state, status: "done", out: fitToSelection(state.source, r.text) }))
      .catch((e) => my === req.current && setState({ ...state, status: "error", error: e.message }));
  }, [state, setState]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setState(null); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [setState]);
  if (!at) return null;

  const insertBelow = () => {
    const $to = editor.state.doc.resolve(state.to);
    const after = $to.after(1);
    editor.chain().focus().insertContentAt(after, { type: "paragraph", content: [{ type: "text", text: state.out! }] }).run();
    setState(null);
  };

  return (
    <div className="float ai-result" style={{ left: at.left, top: at.top }} onMouseDown={(e) => e.preventDefault()}>
      <div className="icard-head"><Sparkles size={14} color="var(--accent)" /> {state.label}
        <button className="icon-btn x" style={{ width: 24, height: 24 }} onClick={() => setState(null)}><X size={14} /></button>
      </div>
      {state.status === "loading" && <div className="muted"><Loader2 size={14} className="spin" /> Writing…</div>}
      {state.status === "error" && <div className="errors">{state.error}</div>}
      {state.status === "done" && (
        <>
          <div className="out">{wordDiff(state.source, state.out!).map((p, i) => p.added ? <ins key={i} className="add">{p.text}</ins> : <span key={i}>{p.text}</span>)}</div>
          <div className="row" style={{ justifyContent: "flex-start" }}>
            <button className="btn primary sm" onClick={() => { if (replaceRange(state.from, state.to, state.source, state.out!)) setState(null); }}>Replace</button>
            <button className="btn sm" onClick={insertBelow}>Insert below</button>
            <button className="btn sm" onClick={() => setState({ ...state, status: "loading", out: undefined })}>Try again</button>
            <button className="btn ghost sm" onClick={() => setState(null)}>Discard</button>
          </div>
        </>
      )}
    </div>
  );
}
