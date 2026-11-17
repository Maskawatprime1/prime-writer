import { useCallback, useRef, useState } from "react";

export function Switch({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <label className="switch">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span />
    </label>
  );
}

export function ScoreRing({ value, size = 58, color }: { value: number; size?: number; color?: string }) {
  const r = (size - 8) / 2, c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value));
  const col = color || (v >= 80 ? "var(--ok)" : v >= 60 ? "var(--c-sentence)" : "var(--c-spelling)");
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth="6" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} style={{ transition: "stroke-dashoffset .4s" }} />
      </svg>
      <b>{Math.round(v)}</b>
    </div>
  );
}

export function useToast() {
  const [toast, setToast] = useState<{ text: string; bad?: boolean } | null>(null);
  const timer = useRef<number>(0);
  const show = useCallback((text: string, bad = false) => {
    setToast({ text, bad });
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), 2600);
  }, []);
  const node = toast ? <div className={"toast" + (toast.bad ? " bad" : "")}>{toast.text}</div> : null;
  return [node, show] as const;
}

/** Prime Writer mark (same artwork as public/logo.svg and the tray icon). */
export function Logo({ size = 30 }: { size?: number }) {
  return <img src="/logo.svg" width={size} height={size} alt="" className="logo-img" draggable={false} />;
}

export const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
