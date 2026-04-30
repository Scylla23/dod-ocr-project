import { useState } from "react";

import logoUrl from "../assets/bravent-logo.png";

const DEMO_PASSWORD = "bravent2026";

interface Props {
  onUnlock: () => void;
}

export function DemoGate({ onUnlock }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password === DEMO_PASSWORD) {
      sessionStorage.setItem("demo_auth", "1");
      onUnlock();
    } else {
      setError("Authentication failed. Verify credentials.");
    }
  }

  const today = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).toUpperCase();

  return (
    <div className="brief-page">
      <div className="brief-classification" aria-hidden>
        <span className="brief-classification-bar" />
        <span className="brief-classification-text">
          CONTROLLED · DEMONSTRATION ENVIRONMENT · BRAVENT × U.S. ARMY
        </span>
        <span className="brief-classification-bar" />
      </div>

      <header className="brief-header">
        <a className="brief-brand" href="/" aria-label="Bravent home">
          <img src={logoUrl} alt="Bravent" />
        </a>
        <div className="brief-meta">
          <div><span>SYS</span> PDF-EXTRACT v0.1</div>
          <div><span>DTG</span> {today}</div>
          <div><span>REF</span> USACE / EC 1105-2-6</div>
        </div>
      </header>

      <main className="brief-stage">
        <section className="brief-lede">
          <p className="brief-kicker">
            <span className="brief-kicker-dot" /> Restricted access
          </p>
          <h1 className="brief-headline">
            Authenticate<br />to access the<br /><em>field briefing.</em>
          </h1>
          <p className="brief-lead">
            This terminal hosts a pre-extracted U.S. Army Corps of Engineers
            circular for review by authorized personnel. Provide the issued
            passphrase to proceed.
          </p>
          <ul className="brief-stats">
            <li>
              <span className="brief-stat-num">17</span>
              <span className="brief-stat-label">Pre-extracted fields</span>
            </li>
            <li>
              <span className="brief-stat-num">42</span>
              <span className="brief-stat-label">PDF pages indexed</span>
            </li>
            <li>
              <span className="brief-stat-num">100%</span>
              <span className="brief-stat-label">In-browser session</span>
            </li>
          </ul>
        </section>

        <section className="brief-panel" aria-label="Authentication panel">
          <div className="brief-panel-frame">
            <span className="brief-panel-id">FORM · 01 / AUTH</span>
            <span className="brief-panel-status">
              <span className="brief-status-pulse" /> READY
            </span>
          </div>

          <form className="brief-form" onSubmit={handleSubmit}>
            <label className="brief-field">
              <span className="brief-field-label">Passphrase</span>
              <input
                type="password"
                value={password}
                autoFocus
                placeholder="•••••••••••"
                onChange={(e) => {
                  setPassword(e.target.value);
                  setError(null);
                }}
              />
              <span className="brief-field-hint">
                Provided by Bravent. Case-sensitive.
              </span>
            </label>

            <button type="submit" className="brief-submit">
              <span>Authenticate</span>
              <span className="brief-submit-arrow" aria-hidden>→</span>
            </button>

            {error && <p className="brief-error">{error}</p>}
          </form>

          <div className="brief-panel-footer">
            <span>NEED ACCESS?</span>
            <span>Contact your Bravent representative.</span>
          </div>
        </section>
      </main>

      <footer className="brief-footer">
        <span>Bravent · Document intelligence for defense workflows</span>
        <span>© {new Date().getFullYear()} Bravent. All rights reserved.</span>
      </footer>
    </div>
  );
}
