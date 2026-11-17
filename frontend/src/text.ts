import type { Node as PMNode } from "@tiptap/pm/model";

/** Plain text of the document plus, for every character, its ProseMirror position. Blocks are joined by "\n". */
export type TextMap = { text: string; pos: number[] };

export function docToText(doc: PMNode): TextMap {
  let text = "";
  const pos: number[] = [];
  let first = true;
  doc.descendants((node, p) => {
    if (node.isTextblock) {
      if (!first) { text += "\n"; pos.push(p); }
      first = false;
    } else if (node.isText && node.text) {
      for (let i = 0; i < node.text.length; i++) { text += node.text[i]; pos.push(p + i); }
    } else if (node.type.name === "hardBreak") {
      text += "\n"; pos.push(p);
    }
    return true;
  });
  return { text, pos };
}

/** ProseMirror range for a text offset/length, or null if it can't be mapped. */
export function rangeFor(map: TextMap, offset: number, length: number): { from: number; to: number } | null {
  if (length <= 0 || offset < 0 || offset + length > map.pos.length) return null;
  const from = map.pos[offset], to = map.pos[offset + length - 1] + 1;
  return to > from ? { from, to } : null;
}

/* ---------- stats (word count, reading time, Flesch) ---------- */
function syllables(word: string) {
  let w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!w) return 0;
  if (w.length <= 3) return 1;
  w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, "").replace(/^y/, "");
  const g = w.match(/[aeiouy]{1,2}/g);
  return Math.max(1, g ? g.length : 1);
}

export type Stats = ReturnType<typeof textStats>;

export function textStats(text: string) {
  const words = text.match(/[A-Za-z0-9À-ɏ]+(?:['’-][A-Za-z0-9À-ɏ]+)*/g) || [];
  const sentences = (text.match(/[^.!?\n]+[.!?]*/g) || []).filter((s) => /\w/.test(s));
  const nW = words.length, nS = Math.max(sentences.length, nW ? 1 : 0);
  const syl = words.reduce((a, w) => a + syllables(w), 0);
  const complex = words.filter((w) => syllables(w) >= 3).length;
  const flesch = nW ? 206.835 - 1.015 * (nW / nS) - 84.6 * (syl / nW) : 0;
  const grade = nW ? 0.39 * (nW / nS) + 11.8 * (syl / nW) - 15.59 : 0;
  const label = flesch >= 80 ? "Very easy" : flesch >= 70 ? "Easy" : flesch >= 60 ? "Plain English"
    : flesch >= 50 ? "Fairly difficult" : flesch >= 30 ? "Difficult" : "Very difficult";
  const fmt = (min: number) => (min < 1 ? `${Math.max(1, Math.round(min * 60))} sec` : `${Math.round(min)} min`);
  return {
    words: nW, characters: text.length, charsNoSpaces: text.replace(/\s/g, "").length, sentences: nS,
    paragraphs: text.split(/\n/).filter((p) => p.trim()).length,
    avgSentence: nS ? nW / nS : 0, complexPct: nW ? (100 * complex) / nW : 0,
    reading: fmt(nW / 238), speaking: fmt(nW / 150),
    flesch: Math.max(0, Math.min(100, flesch)), grade: Math.max(0, grade), label,
  };
}

/* ---------- word diff for paraphrase output ---------- */
export type DiffPart = { text: string; added: boolean };

export function wordDiff(a: string, b: string): DiffPart[] {
  const A = a.split(/(\s+)/), B = b.split(/(\s+)/);
  if (A.length * B.length > 4e6) return [{ text: b, added: false }];
  const n = A.length, m = B.length;
  const L = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out: DiffPart[] = [];
  let i = 0, j = 0;
  while (j < m) {
    if (i < n && A[i] === B[j]) { out.push({ text: B[j], added: false }); i++; j++; }
    else if (i < n && L[i + 1][j] >= L[i][j + 1]) i++;
    else { out.push({ text: B[j], added: !/^\s+$/.test(B[j]) }); j++; }
  }
  return out;
}

export function sentenceAround(text: string, offset: number): [number, number] {
  const re = /[^.!?\n]+(?:[.!?]+|$)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    let s = m.index, e = m.index + m[0].length;
    while (s < e && /\s/.test(text[s])) s++;
    while (e > s && /\s/.test(text[e - 1])) e--;
    if (offset >= s && offset <= e) return [s, e];
    if (!m[0].length) re.lastIndex++;
  }
  return [Math.max(0, offset - 80), Math.min(text.length, offset + 80)];
}

/** Make an AI rewrite fit the selected fragment: same ending punctuation and starting case. */
export function fitToSelection(source: string, out: string): string {
  let o = out.trim();
  const lead = source.match(/^\s*/)![0], trail = source.match(/\s*$/)![0];
  const src = source.trim();
  if (!/[.!?…]$/.test(src) && /[.!?]$/.test(o) && !/[.!?]\s/.test(src)) o = o.replace(/[.!?]+$/, "");
  if (/^[a-z]/.test(src) && /^[A-Z][a-z]/.test(o) && !/^I\b/.test(o)) o = o[0].toLowerCase() + o.slice(1);
  return lead + o + trail;
}

/** Category used by the side panel (Grammarly-style groups). */
export function category(kind: string, scope?: string): "correctness" | "clarity" | "style" {
  if (scope === "sentence" || kind === "clarity") return "clarity";
  if (kind === "style") return "style";
  return "correctness";
}

/** Writing score 0–100: fewer issues per word = higher. */
export function writingScore(counts: { correctness: number; clarity: number; style: number }, words: number) {
  if (!words) return 100;
  const penalty = counts.correctness * 3 + counts.clarity * 0.8 + counts.style * 1;
  return Math.round(100 * Math.exp(-(penalty * 100) / Math.max(words, 60) / 40));
}
