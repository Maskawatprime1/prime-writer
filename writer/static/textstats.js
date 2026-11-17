"use strict";
/* Word count, reading/speaking time and readability scores (Flesch, Flesch-Kincaid). Shared by all pages. */
function countSyllables(word) {
  let w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!w) return 0;
  if (w.length <= 3) return 1;
  w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, "").replace(/^y/, "");
  const groups = w.match(/[aeiouy]{1,2}/g);
  return Math.max(1, groups ? groups.length : 1);
}

function textStats(text) {
  const words = text.match(/[A-Za-z0-9À-ɏ]+(?:['’-][A-Za-z0-9À-ɏ]+)*/g) || [];
  const sentences = (text.match(/[^.!?\n]+[.!?]*/g) || []).filter((s) => /\w/.test(s));
  const nW = words.length, nS = Math.max(sentences.length, nW ? 1 : 0);
  const syl = words.reduce((a, w) => a + countSyllables(w), 0);
  const complex = words.filter((w) => countSyllables(w) >= 3).length;
  const flesch = nW ? 206.835 - 1.015 * (nW / nS) - 84.6 * (syl / nW) : 0;
  const grade = nW ? 0.39 * (nW / nS) + 11.8 * (syl / nW) - 15.59 : 0;
  const label = flesch >= 80 ? "Very easy" : flesch >= 70 ? "Easy" : flesch >= 60 ? "Plain English"
    : flesch >= 50 ? "Fairly difficult" : flesch >= 30 ? "Difficult" : "Very difficult";
  const fmt = (min) => (min < 1 ? `${Math.max(1, Math.round(min * 60))} sec` : `${Math.round(min)} min`);
  return {
    words: nW, characters: text.length, charsNoSpaces: text.replace(/\s/g, "").length, sentences: nS,
    paragraphs: text.split(/\n\s*\n|\n/).filter((p) => p.trim()).length,
    avgSentence: nS ? nW / nS : 0, complexPct: nW ? (100 * complex) / nW : 0,
    reading: fmt(nW / 238), speaking: fmt(nW / 150),
    flesch: Math.max(0, Math.min(100, flesch)), grade: Math.max(0, grade), label,
  };
}
