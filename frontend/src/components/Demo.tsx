import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import { useApp } from "../store";
import { Workspace } from "./Workspace";

type Phase = "loading" | "ready" | "error";

export function Demo() {
  const session = useApp((s) => s.session);
  const setSession = useApp((s) => s.setSession);
  const reset = useApp((s) => s.reset);
  const [phase, setPhase] = useState<Phase>(session ? "ready" : "loading");
  const [error, setError] = useState<string | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    if (session) {
      setPhase("ready");
      return;
    }
    void load();

    async function load() {
      try {
        const s = await api.loadDemo();
        setSession(s);
        setPhase("ready");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setPhase("error");
      }
    }
  }, [session, setSession]);

  if (phase === "loading") {
    return (
      <div className="demo-splash">
        <div className="demo-splash-card">
          <span className="demo-splash-glyph" aria-hidden>¶</span>
          <h1>Loading the demo</h1>
          <p>Preparing a pre-extracted USACE engineering circular for you to play with.</p>
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="demo-splash">
        <div className="demo-splash-card">
          <h1>Could not load the demo</h1>
          <p className="error">{error}</p>
          <button
            className="link"
            onClick={() => {
              loadedRef.current = false;
              setError(null);
              setPhase("loading");
            }}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="demo-shell">
      <div className="demo-banner">
        <span className="demo-banner-tag">Demo</span>
        <span className="demo-banner-text">
          Pre-extracted from <em>EC 1105-2-6</em> · 9 March 1973 · edits stay in your browser session.
        </span>
        <button
          className="link"
          onClick={() => {
            reset();
            window.history.pushState({}, "", "/");
            window.dispatchEvent(new PopStateEvent("popstate"));
          }}
        >
          Exit demo
        </button>
      </div>
      <Workspace />
    </div>
  );
}
