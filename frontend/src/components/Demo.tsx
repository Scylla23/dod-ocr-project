import { useEffect, useRef, useState } from "react";

import logoUrl from "../assets/bravent-logo.png";
import { api } from "../api";
import { useApp } from "../store";
import { Workspace } from "./Workspace";

type Phase = "loading" | "ready" | "error";

export function Demo() {
  const session = useApp((s) => s.session);
  const setSession = useApp((s) => s.setSession);
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
      <div className="brief-splash">
        <div className="brief-splash-grid" aria-hidden />
        <div className="brief-splash-card">
          <img className="brief-splash-logo" src={logoUrl} alt="Bravent" />
          <span className="brief-splash-id">FETCHING · USACE · EC 1105-2-6</span>
          <h1>Standing up the briefing.</h1>
          <p>Loading a pre-extracted U.S. Army Corps of Engineers circular.</p>
          <div className="brief-splash-bar" aria-hidden>
            <span />
          </div>
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="brief-splash">
        <div className="brief-splash-card">
          <img className="brief-splash-logo" src={logoUrl} alt="Bravent" />
          <span className="brief-splash-id brief-splash-id--alert">
            ERR · DEMO LOAD FAILED
          </span>
          <h1>Could not stand up the briefing.</h1>
          <p className="brief-splash-error">{error}</p>
          <button
            className="brief-retry"
            onClick={() => {
              loadedRef.current = false;
              setError(null);
              setPhase("loading");
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="brief-shell">
      <div className="brief-classification" aria-hidden>
        <span className="brief-classification-bar" />
        <span className="brief-classification-text">
          CONTROLLED · DEMONSTRATION ENVIRONMENT · BRAVENT × U.S. ARMY
        </span>
        <span className="brief-classification-bar" />
      </div>

      <header className="brief-commandbar">
        <a className="brief-brand brief-brand--compact" href="/" aria-label="Bravent home">
          <img src={logoUrl} alt="Bravent" />
        </a>
        <div className="brief-commandbar-doc">
          <span className="brief-commandbar-tag">Active brief</span>
          <span className="brief-commandbar-title">EC 1105-2-6</span>
          <span className="brief-commandbar-sub">USACE Engineering Circular · 9 March 1973</span>
        </div>
        <div className="brief-commandbar-actions">
          <span className="brief-session">
            <span className="brief-status-pulse" />
            Session local · edits stay in this browser
          </span>
        </div>
      </header>

      <div className="brief-workspace">
        <Workspace showNewDocument={false} showReExtract={false} />
      </div>
    </div>
  );
}
