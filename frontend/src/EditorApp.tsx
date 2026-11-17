import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Highlight from "@tiptap/extension-highlight";
import TextAlign from "@tiptap/extension-text-align";
import { Placeholder } from "@tiptap/extensions";
import { Check, Copy, Download, FilePlus2, Moon, Settings as Gear, Sun, SunMoon } from "lucide-react";
import { check, getConfig, getStatus, local, saveLocal, type Config, type Issue, type Status } from "./api";
import { IssueHighlights, Snippets, getActive, getIssues, issueKey, type DocIssue } from "./extensions";
import { category, docToText, rangeFor, textStats, writingScore, type TextMap } from "./text";
import Toolbar from "./Toolbar";
import Sidebar from "./Sidebar";
import { IssueCard, SynonymCard } from "./Cards";
import { AiResult, SelectionMenu, type AiState } from "./AiMenu";
import { navigate } from "./main";
import { Logo, useToast } from "./ui";

export type Prefs = { readability: boolean; aiCheck: boolean; serif: boolean; side: boolean };
type Theme = "system" | "light" | "dark";
type Anchor = { left: number; top: number };

const DEFAULT_DOC = "<p></p>";

/** Saved document, or the plain-text draft from the old Local Writer UI. */
function initialDoc(): string {
  const saved = local<string | null>("pw-doc", null);
  if (saved) return saved;
  try {
    const old = localStorage.getItem("lw-draft");
    if (old && old.trim()) {
      const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]!));
      return old.split("\n").map((l) => `<p>${esc(l)}</p>`).join("");
    }
  } catch { /* storage unavailable */ }
  return DEFAULT_DOC;
}

export default function EditorApp() {
  const [, rerender] = useReducer((x: number) => x + 1, 0);
  const [status, setStatus] = useState<Status | null>(null);
  const [cfg, setCfg] = useState<Config | null>(null);
  const [prefs, setPrefs] = useState<Prefs>(() => local("pw-prefs", { readability: true, aiCheck: true, serif: false, side: true }));
  const [theme, setTheme] = useState<Theme>(() => local("pw-theme-pref", "system" as Theme));
  const [title, setTitle] = useState<string>(() => local("pw-title", "Untitled document"));
  const [checking, setChecking] = useState<"" | "rules" | "ai">("");
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState(true);
  const [card, setCard] = useState<{ id: number; at: Anchor } | null>(null);
  const [syn, setSyn] = useState<{ word: string; from: number; to: number; context: string; at: Anchor } | null>(null);
  const [ai, setAi] = useState<AiState | null>(null);
  const [toast, showToast] = useToast();
  const canvasRef = useRef<HTMLDivElement>(null);
  const snippetsRef = useRef<Record<string, string>>({});
  const ignored = useRef(new Set<string>());
  const seq = useRef(0), idSeq = useRef(0), timer = useRef(0), saveTimer = useRef(0);
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;
  // editor callbacks are created once; route them through a ref so they always call the latest code
  const h = useRef<{ openCard: (id: number) => void; openSynonyms: () => void; runCheck: () => void }>(null!);

  /* ---------- editor ---------- */
  const editor = useEditor({
    extensions: [
      StarterKit,
      Highlight,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({ placeholder: "Start writing, or paste your text here…" }),
      IssueHighlights,
      Snippets.configure({ get: () => snippetsRef.current }),
    ],
    content: initialDoc(),
    editorProps: {
      attributes: { spellcheck: "false" },
      handleClick: (view, pos, event) => {
        const hit = getIssues(view.state).find((i) => i.scope !== "sentence" && pos >= i.from && pos <= i.to);
        setSyn(null);
        void event;
        if (hit) { h.current.openCard(hit.id); return false; }
        setCard(null);
        if (getActive(view.state) !== null) view.dispatch(view.state.tr.setMeta(issueKey, { active: null }));
        return false;
      },
      handleDoubleClick: () => { window.setTimeout(() => h.current.openSynonyms(), 80); return false; },
    },
    onUpdate: () => {
      setSaved(false);
      setCard(null); setSyn(null);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => h.current.runCheck(), 1100);
      window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => { if (editor) { saveLocal("pw-doc", editor.getHTML()); setSaved(true); } }, 500);
    },
  });

  useEffect(() => {
    if (!editor) return;
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(rerender); };
    editor.on("transaction", on);
    return () => { editor.off("transaction", on); cancelAnimationFrame(raf); };
  }, [editor]);

  /* ---------- status, settings, theme ---------- */
  const refreshConfig = useCallback(() => getConfig().then((c) => { setCfg(c); snippetsRef.current = c.snippets || {}; }).catch(() => {}), []);
  useEffect(() => {
    getStatus().then(setStatus).catch(() => setStatus(null));
    refreshConfig();
    const t = window.setInterval(() => getStatus().then(setStatus).catch(() => setStatus(null)), 15000);
    window.addEventListener("focus", refreshConfig);
    window.addEventListener("popstate", refreshConfig);
    return () => { window.clearInterval(t); window.removeEventListener("focus", refreshConfig); window.removeEventListener("popstate", refreshConfig); };
  }, [refreshConfig]);
  useEffect(() => {
    saveLocal("pw-theme-pref", theme);
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("pw-theme", theme); } catch { /* ignore */ }
  }, [theme]);
  useEffect(() => { saveLocal("pw-prefs", prefs); }, [prefs]);
  useEffect(() => { saveLocal("pw-title", title); document.title = `${title} · Prime Writer`; }, [title]);

  /* ---------- checking ---------- */
  const place = useCallback((issues: Issue[], map: TextMap): DocIssue[] => {
    const out: DocIssue[] = [];
    for (const it of issues) {
      const original = map.text.slice(it.offset, it.offset + it.length);
      if (!original.trim() || ignored.current.has(it.message + "|" + original)) continue;
      const r = rangeFor(map, it.offset, it.length);
      if (r) out.push({ ...it, id: ++idSeq.current, from: r.from, to: r.to, original });
    }
    return out;
  }, []);

  const runCheck = useCallback(async () => {
    if (!editor) return;
    const map = docToText(editor.state.doc), my = ++seq.current;
    const stale = () => my !== seq.current || docToText(editor.state.doc).text !== map.text;
    if (!map.text.trim()) { editor.view.dispatch(editor.state.tr.setMeta(issueKey, { issues: [] })); return; }
    const { readability, aiCheck } = prefsRef.current;
    try {
      setChecking("rules");
      const quick = await check(map.text, { useLlm: false, readability });
      if (stale()) return;
      editor.view.dispatch(editor.state.tr.setMeta(issueKey, { issues: place(quick.issues, map) }));
      setErrors(quick.errors);
      if (aiCheck) {
        setChecking("ai");
        const full = await check(map.text, { useLlm: true, readability });
        if (stale()) return;
        editor.view.dispatch(editor.state.tr.setMeta(issueKey, { issues: place(full.issues, map) }));
        setErrors(full.errors);
      }
    } catch (e) {
      setErrors([(e as Error).message]);
    } finally {
      if (my === seq.current) setChecking("");
    }
  }, [editor, place]);

  useEffect(() => { if (editor) runCheck(); }, [editor, prefs.readability, prefs.aiCheck, runCheck]);

  /* ---------- cards ---------- */
  const anchorFor = useCallback((from: number, to: number): Anchor | null => {
    const canvas = canvasRef.current;
    if (!editor || !canvas) return null;
    const a = editor.view.coordsAtPos(from), b = editor.view.coordsAtPos(to);
    const c = canvas.getBoundingClientRect();
    const left = Math.min(Math.max(12, a.left - c.left), c.width - 360);
    return { left, top: Math.max(a.bottom, b.bottom) - c.top + canvas.scrollTop + 8 };
  }, [editor]);

  function openCard(id: number) {
    if (!editor) return;
    const it = getIssues(editor.state).find((i) => i.id === id);
    if (!it) return;
    editor.view.dispatch(editor.state.tr.setMeta(issueKey, { active: id }));
    const at = anchorFor(it.from, it.to);
    if (at) setCard({ id, at });
  }

  function openSynonyms() {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    const word = editor.state.doc.textBetween(from, to).trim();
    if (!/^[\p{L}'’-]{2,30}$/u.test(word)) return;
    // a word with a mistake keeps its suggestion card; synonyms are for correct words
    if (getIssues(editor.state).some((i) => i.scope !== "sentence" && from < i.to && to > i.from && i.kind !== "clarity")) return;
    const map = docToText(editor.state.doc);
    const idx = map.pos.indexOf(from);
    const start = idx >= 0 ? map.text.lastIndexOf("\n", idx) + 1 : 0;
    const end = idx >= 0 ? (map.text.indexOf("\n", idx) + 1 || map.text.length + 1) - 1 : map.text.length;
    const at = anchorFor(from, to);
    if (at) { setCard(null); setSyn({ word, from, to: from + word.length, context: map.text.slice(start, end).slice(0, 500), at }); }
  }

  function focusIssue(id: number) {
    if (!editor) return;
    const it = getIssues(editor.state).find((i) => i.id === id);
    if (!it) return;
    editor.view.dispatch(editor.state.tr.setMeta(issueKey, { active: id }));
    const canvas = canvasRef.current, at = anchorFor(it.from, it.to);
    if (canvas && at) canvas.scrollTo({ top: Math.max(0, at.top - canvas.clientHeight / 3), behavior: "smooth" });
  }

  function applyFix(it: DocIssue, rep: string) {
    if (!editor) return;
    const doc = editor.state.doc;
    if (doc.textBetween(it.from, it.to, "\n") !== it.original) return;
    let { from, to } = it;
    if (rep === "") {
      if (doc.textBetween(to, Math.min(to + 1, doc.content.size)) === " ") to++;
      else if (doc.textBetween(Math.max(from - 1, 0), from) === " ") from--;
    }
    editor.chain().focus().command(({ tr }) => { tr.insertText(rep, from, to); return true; }).run();
    setCard(null);
  }

  function replaceRange(from: number, to: number, expected: string, text: string) {
    if (!editor) return false;
    if (editor.state.doc.textBetween(from, to, "\n") !== expected) { showToast("The text changed. Try again.", true); return false; }
    editor.chain().focus().command(({ tr }) => { tr.insertText(text, from, to); return true; }).run();
    return true;
  }

  function ignoreIssue(it: DocIssue) {
    if (!editor) return;
    ignored.current.add(it.message + "|" + it.original);
    const rest = getIssues(editor.state).filter((i) => i.id !== it.id);
    editor.view.dispatch(editor.state.tr.setMeta(issueKey, { issues: rest, active: null }));
    setCard(null);
  }

  function dropWord(word: string) {
    if (!editor) return;
    const rest = getIssues(editor.state).filter((i) => !(i.kind === "spelling" && i.original.toLowerCase() === word.toLowerCase()));
    editor.view.dispatch(editor.state.tr.setMeta(issueKey, { issues: rest, active: null }));
    setCard(null);
    showToast(`Added “${word}” to your dictionary`);
    refreshConfig();
  }

  h.current = { openCard, openSynonyms, runCheck };

  /* ---------- derived ---------- */
  const issues = editor ? getIssues(editor.state) : [];
  const active = editor ? getActive(editor.state) : null;
  const text = editor ? editor.getText({ blockSeparator: "\n" }) : "";
  const stats = useMemo(() => textStats(text), [text]);
  const counts = useMemo(() => {
    const c = { correctness: 0, clarity: 0, style: 0 };
    for (const i of issues) c[category(i.kind, i.scope)]++;
    return c;
  }, [issues]);
  const score = writingScore(counts, stats.words);
  const cardIssue = card ? issues.find((i) => i.id === card.id) : undefined;

  /* ---------- document actions ---------- */
  function newDoc() {
    if (!editor) return;
    if (stats.words && !confirm("Start a new document? The current one will be cleared.")) return;
    editor.commands.setContent(DEFAULT_DOC);
    setTitle("Untitled document");
    ignored.current.clear();
  }
  async function copyAll() {
    await navigator.clipboard.writeText(text);
    showToast("Copied the whole text");
  }
  function download() {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (title.trim() || "document").replace(/[\\/:*?"<>|]/g, "_") + ".txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const themeIcon = theme === "system" ? <SunMoon size={18} /> : theme === "light" ? <Sun size={18} /> : <Moon size={18} />;
  const nextTheme: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><Logo />Prime Writer</div>
        <input className="doc-title" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Document title" />
        <div className="top-right">
          <div className="status-pills">
            <span className="pill" title="Local AI model"><span className={"dot " + (status?.ollama ? "ok" : "bad")} />AI {status?.ollama ? "ready" : "offline"}</span>
            <span className="pill" title="LanguageTool grammar engine"><span className={"dot " + (status?.languagetool ? "ok" : "bad")} />LanguageTool</span>
          </div>
          <button className="icon-btn" title="New document" onClick={newDoc}><FilePlus2 size={18} /></button>
          <button className="icon-btn" title="Copy all text" onClick={copyAll}><Copy size={18} /></button>
          <button className="icon-btn" title="Download as .txt" onClick={download}><Download size={18} /></button>
          <span className="sep" />
          <button className="icon-btn" title={`Theme: ${theme}`} onClick={() => setTheme(nextTheme[theme])}>{themeIcon}</button>
          <button className="btn ghost" onClick={() => navigate("/settings")}><Gear size={16} />Settings</button>
        </div>
      </header>

      {editor && <Toolbar editor={editor} prefs={prefs} setPrefs={setPrefs} checking={checking} onCheck={runCheck} />}

      <div className={"workspace" + (prefs.side ? "" : " no-side")}>
        <div className={"canvas" + (prefs.serif ? " serif" : "")} ref={canvasRef}>
          <div className="page"><EditorContent editor={editor} /></div>
          {editor && !ai && <SelectionMenu editor={editor} onAi={setAi} onSynonyms={openSynonyms} />}
          {editor && ai && <AiResult editor={editor} state={ai} setState={setAi} anchorFor={anchorFor} replaceRange={replaceRange} />}
          {cardIssue && card && (
            <IssueCard issue={cardIssue} at={card.at} text={text} onApply={applyFix} onIgnore={ignoreIssue}
              onAddWord={dropWord} onClose={() => { setCard(null); editor?.view.dispatch(editor.state.tr.setMeta(issueKey, { active: null })); }}
              replaceRange={replaceRange} map={() => docToText(editor!.state.doc)} />
          )}
          {syn && (
            <SynonymCard {...syn} onPick={(w) => { replaceRange(syn.from, syn.to, syn.word, w); setSyn(null); }} onClose={() => setSyn(null)} />
          )}
        </div>
        {prefs.side && editor && (
          <Sidebar editor={editor} issues={issues} active={active} counts={counts} score={score} stats={stats}
            errors={errors} checking={checking} onFocus={focusIssue} onApply={applyFix} onIgnore={ignoreIssue}
            onAddWord={dropWord} replaceRange={replaceRange} showToast={showToast} text={text} />
        )}
      </div>

      <footer className="statusbar">
        <span>{stats.words.toLocaleString()} words</span>
        <span>{stats.characters.toLocaleString()} characters</span>
        <span>{stats.reading} read</span>
        <span>Readability: {stats.words ? stats.label : "–"}</span>
        <span className="grow" />
        <span>{checking === "rules" ? "Checking…" : checking === "ai" ? "AI is reviewing…" : issues.length ? `${issues.length} suggestions` : stats.words ? <><Check size={13} /> No issues</> : ""}</span>
        <span>{saved ? "Saved" : "Saving…"}</span>
        <span>{cfg ? { "en-US": "English (US)", "en-GB": "English (UK)", "en-CA": "English (CA)", "en-AU": "English (AU)" }[cfg.language] : ""}</span>
        <span>{status?.check_model || ""}</span>
      </footer>
      {toast}
    </div>
  );
}
