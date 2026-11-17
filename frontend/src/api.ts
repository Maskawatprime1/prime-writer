export type Issue = {
  offset: number;
  length: number;
  message: string;
  replacements: string[];
  kind: "spelling" | "grammar" | "style" | "clarity" | string;
  source: string;
  scope?: "word" | "sentence";
  sub?: string;
};

export type Status = {
  ollama: boolean;
  languagetool: boolean;
  models: string[];
  check_model: string;
  paraphrase_model: string;
  modes: string[];
};

export type Config = {
  enabled: boolean;
  live: boolean;
  live_ai: boolean;
  live_readability: boolean;
  synonyms_on_select: boolean;
  fallback_button: boolean;
  button_apps: string[];
  button_pos: Record<string, number[]>;
  start_with_windows: boolean;
  popup_mode: string;
  language: string;
  picky: boolean;
  dictionary: string[];
  snippets: Record<string, string>;
  hotkeys: Record<string, string>;
  hotkey_errors: string[];
  desktop: boolean;
};

export type AppRow = { exe: string; title: string; running: boolean; used: boolean; enabled: boolean };

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((data as { detail?: string }).detail || `HTTP ${r.status}`);
  return data as T;
}

export const getStatus = () => api<Status>("/api/status");
export const getConfig = () => api<Config>("/api/config");
export const setConfig = (c: Partial<Config>) => api<Config>("/api/config", c);
export const check = (text: string, o: { useLt?: boolean; useLlm?: boolean; readability?: boolean; model?: string | null }) =>
  api<{ issues: Issue[]; errors: string[] }>("/api/check", {
    text, use_lt: o.useLt ?? true, use_llm: o.useLlm ?? true, readability: o.readability ?? true, model: o.model || null,
  });
export const paraphrase = (text: string, mode: string, o: { strength?: number; freeze?: string[]; model?: string | null } = {}) =>
  api<{ text: string; missing_frozen?: string[] }>("/api/paraphrase", {
    text, mode, strength: o.strength ?? 3, freeze: o.freeze ?? [], model: o.model || null,
  });
export const synonyms = (word: string, context: string) => api<{ synonyms: string[] }>("/api/synonyms", { word, context });
export const addWord = (word: string) => api<{ dictionary: string[] }>("/api/dictionary", { word });
export const removeWord = (word: string) => api<{ dictionary: string[] }>("/api/dictionary/remove", { word });
export const getApps = () => api<{ apps: AppRow[] }>("/api/apps");
export const toggleApp = (exe: string, enabled: boolean) => api("/api/apps", { exe, enabled });

export const MODES: Record<string, string> = {
  fix: "Fix grammar", standard: "Standard", fluent: "Fluent", formal: "Formal",
  concise: "Concise", casual: "Casual", academic: "Academic", simple: "Simple",
};

export function local<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); return v === null ? fallback : (JSON.parse(v) as T); } catch { return fallback; }
}
export function saveLocal(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}
