import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import type { EditorState, Transaction } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { Issue } from "./api";

/** An issue placed in the document (positions follow edits). */
export type DocIssue = Issue & { id: number; from: number; to: number; original: string };

type IssueState = { issues: DocIssue[]; active: number | null; deco: DecorationSet };
export const issueKey = new PluginKey<IssueState>("pw-issues");

function build(doc: EditorState["doc"], issues: DocIssue[], active: number | null) {
  const decos: Decoration[] = [];
  for (const it of issues) {
    if (it.scope === "sentence") {
      if (it.id === active) decos.push(Decoration.inline(it.from, it.to, { class: "pw-sentence" }));
      continue;
    }
    decos.push(Decoration.inline(it.from, it.to, {
      class: `pw-issue k-${it.kind}${it.id === active ? " is-active" : ""}`,
      "data-issue": String(it.id),
    }));
  }
  return DecorationSet.create(doc, decos);
}

export const IssueHighlights = Extension.create({
  name: "issueHighlights",
  addProseMirrorPlugins() {
    return [new Plugin<IssueState>({
      key: issueKey,
      state: {
        init: (_, state) => ({ issues: [], active: null, deco: DecorationSet.create(state.doc, []) }),
        apply(tr: Transaction, old, _o, state) {
          const meta = tr.getMeta(issueKey) as Partial<Pick<IssueState, "issues" | "active">> | undefined;
          let { issues, active } = old;
          if (tr.docChanged) {
            // move issues with the text; drop ones whose words were edited
            issues = issues.map((i) => ({ ...i, from: tr.mapping.map(i.from, 1), to: tr.mapping.map(i.to, -1) }))
              .filter((i) => i.to > i.from && state.doc.textBetween(i.from, i.to, "\n") === i.original);
          }
          if (meta?.issues) issues = meta.issues;
          if (meta && "active" in meta) active = meta.active ?? null;
          if (!tr.docChanged && !meta) return old;
          if (active !== null && !issues.some((i) => i.id === active)) active = null;
          return { issues, active, deco: build(state.doc, issues, active) };
        },
      },
      props: { decorations: (state) => issueKey.getState(state)?.deco },
    })];
  },
});

export const getIssues = (state: EditorState) => issueKey.getState(state)?.issues ?? [];
export const getActive = (state: EditorState) => issueKey.getState(state)?.active ?? null;

/** Snippets: type a trigger (e.g. ";addr") then a space or punctuation and it expands. */
export const Snippets = Extension.create<{ get: () => Record<string, string> }>({
  name: "snippets",
  addOptions() { return { get: () => ({}) }; },
  addProseMirrorPlugins() {
    const get = this.options.get;
    return [new Plugin({
      props: {
        handleTextInput(view, from, to, text) {
          if (!/^[\s.,!?;:)]$/.test(text)) return false;
          const snippets = get();
          const $from = view.state.doc.resolve(from);
          const before = $from.parent.textBetween(0, $from.parentOffset, undefined, "￼");
          for (const [trig, exp] of Object.entries(snippets)) {
            if (!before.endsWith(trig)) continue;
            const prev = before.slice(0, -trig.length);
            if (prev && !/\s$/.test(prev)) continue;
            view.dispatch(view.state.tr.insertText(exp + text, from - trig.length, to));
            return true;
          }
          return false;
        },
      },
    })];
  },
});
