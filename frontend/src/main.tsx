import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import EditorApp from "./EditorApp";
import Settings from "./Settings";
import SetupScreen from "./SetupScreen";
import { api } from "./api";

export function navigate(path: string) {
  history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function Router() {
  const [path, setPath] = useState(location.pathname);
  // First run on a new PC: no AI model yet -> show the setup screen (?setup=1 forces it)
  const [setup, setSetup] = useState(new URLSearchParams(location.search).has("setup"));
  useEffect(() => {
    const on = () => setPath(location.pathname);
    window.addEventListener("popstate", on);
    if (!setup) api<{ ready: boolean }>("/api/setup").then((s) => { if (!s.ready) setSetup(true); }).catch(() => {});
    return () => window.removeEventListener("popstate", on);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const done = useCallback(() => setSetup(false), []);
  // keep the editor mounted (and its document) while Settings is open
  return (
    <>
      <div style={{ display: path.startsWith("/settings") ? "none" : "contents" }}><EditorApp /></div>
      {path.startsWith("/settings") && <Settings />}
      {setup && <SetupScreen onDone={done} force={new URLSearchParams(location.search).has("setup")} />}
    </>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><Router /></StrictMode>);
