import type { Editor } from "@tiptap/react";
import {
  AlignCenter, AlignLeft, AlignRight, Bold, Glasses, Highlighter, Italic, List, ListOrdered, Loader2, PanelRight,
  Quote, Redo2, RefreshCw, RemoveFormatting, Sparkles, Strikethrough, Type, Underline, Undo2,
} from "lucide-react";
import type { Prefs } from "./EditorApp";

type Props = {
  editor: Editor;
  prefs: Prefs;
  setPrefs: (p: Prefs) => void;
  checking: "" | "rules" | "ai";
  onCheck: () => void;
};

export default function Toolbar({ editor, prefs, setPrefs, checking, onCheck }: Props) {
  const c = () => editor.chain().focus();
  const B = ({ on, title, onClick, children, disabled }: { on?: boolean; title: string; onClick: () => void; children: React.ReactNode; disabled?: boolean }) => (
    <button className={"icon-btn" + (on ? " on" : "")} title={title} aria-pressed={on} disabled={disabled}
      onMouseDown={(e) => e.preventDefault()} onClick={onClick}>{children}</button>
  );
  const block = editor.isActive("heading", { level: 1 }) ? "h1" : editor.isActive("heading", { level: 2 }) ? "h2"
    : editor.isActive("heading", { level: 3 }) ? "h3" : "p";
  const setBlock = (v: string) => {
    if (v === "p") c().setParagraph().run();
    else c().toggleHeading({ level: Number(v[1]) as 1 | 2 | 3 }).run();
  };
  const toggle = (k: keyof Prefs) => setPrefs({ ...prefs, [k]: !prefs[k] });

  return (
    <div className="toolbar" role="toolbar" aria-label="Formatting">
      <B title="Undo (Ctrl+Z)" onClick={() => c().undo().run()} disabled={!editor.can().undo()}><Undo2 size={17} /></B>
      <B title="Redo (Ctrl+Y)" onClick={() => c().redo().run()} disabled={!editor.can().redo()}><Redo2 size={17} /></B>
      <span className="sep" />
      <select className="tb-select" value={block} onChange={(e) => setBlock(e.target.value)} aria-label="Text style">
        <option value="p">Normal text</option>
        <option value="h1">Title</option>
        <option value="h2">Heading</option>
        <option value="h3">Subheading</option>
      </select>
      <span className="sep" />
      <B title="Bold (Ctrl+B)" on={editor.isActive("bold")} onClick={() => c().toggleBold().run()}><Bold size={17} /></B>
      <B title="Italic (Ctrl+I)" on={editor.isActive("italic")} onClick={() => c().toggleItalic().run()}><Italic size={17} /></B>
      <B title="Underline (Ctrl+U)" on={editor.isActive("underline")} onClick={() => c().toggleUnderline().run()}><Underline size={17} /></B>
      <B title="Strikethrough" on={editor.isActive("strike")} onClick={() => c().toggleStrike().run()}><Strikethrough size={17} /></B>
      <B title="Highlight" on={editor.isActive("highlight")} onClick={() => c().toggleHighlight().run()}><Highlighter size={17} /></B>
      <span className="sep" />
      <B title="Bulleted list" on={editor.isActive("bulletList")} onClick={() => c().toggleBulletList().run()}><List size={17} /></B>
      <B title="Numbered list" on={editor.isActive("orderedList")} onClick={() => c().toggleOrderedList().run()}><ListOrdered size={17} /></B>
      <B title="Quote" on={editor.isActive("blockquote")} onClick={() => c().toggleBlockquote().run()}><Quote size={17} /></B>
      <span className="sep" />
      <B title="Align left" on={editor.isActive({ textAlign: "left" })} onClick={() => c().setTextAlign("left").run()}><AlignLeft size={17} /></B>
      <B title="Align center" on={editor.isActive({ textAlign: "center" })} onClick={() => c().setTextAlign("center").run()}><AlignCenter size={17} /></B>
      <B title="Align right" on={editor.isActive({ textAlign: "right" })} onClick={() => c().setTextAlign("right").run()}><AlignRight size={17} /></B>
      <B title="Clear formatting" onClick={() => c().unsetAllMarks().clearNodes().run()}><RemoveFormatting size={17} /></B>
      <span className="grow" />
      <B title={prefs.serif ? "Font: serif (click for sans)" : "Font: sans (click for serif)"} on={prefs.serif} onClick={() => toggle("serif")}><Type size={17} /></B>
      <B title="Readability highlights (passive voice, wordy phrases, long sentences)" on={prefs.readability} onClick={() => toggle("readability")}><Glasses size={17} /></B>
      <B title="AI suggestions (uses the local AI model)" on={prefs.aiCheck} onClick={() => toggle("aiCheck")}><Sparkles size={17} /></B>
      <button className="btn sm" onMouseDown={(e) => e.preventDefault()} onClick={onCheck} disabled={!!checking} title="Check now">
        {checking ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}{checking ? "Checking" : "Check"}
      </button>
      <B title="Show or hide the side panel" on={prefs.side} onClick={() => toggle("side")}><PanelRight size={17} /></B>
    </div>
  );
}
