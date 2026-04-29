import { useState } from "react";

import { api } from "../api";
import { useApp } from "../store";
import { ProviderSelect } from "./ProviderSelect";

export function Upload() {
  const setSession = useApp((s) => s.setSession);
  const selectedProvider = useApp((s) => s.selectedProvider);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setError(null);
    setBusy(true);
    try {
      const session = await api.upload(file, selectedProvider ?? undefined);
      setSession(session);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const today = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).toUpperCase();

  return (
    <div className="upload">
      <header className="upload-masthead">
        <div className="masthead-mark">
          <span className="dot" aria-hidden />
          <span>Extract / Vol. 01</span>
          <span>—</span>
          <span>An atelier for structured PDF data</span>
        </div>
        <div className="masthead-meta">
          <div>{today}</div>
          <div>FOLIO Nº 0001</div>
        </div>
      </header>

      <section className="upload-stage">
        <div className="upload-lede">
          <p className="kicker">A document, decomposed</p>
          <h1>
            Lift the<br /> facts <em>from</em><br /> the page.
          </h1>
          <p className="lead">
            Drop a PDF and we&rsquo;ll read it like a careful editor —
            highlighting the fields that matter, then handing them back
            to you in a form built for review, refinement, and export.
          </p>
          <ol className="upload-rules">
            <li>Choose a model, or trust the house default.</li>
            <li>Upload a PDF — text-native or scanned.</li>
            <li>Edit, append, and curate the extraction.</li>
          </ol>
        </div>

        <div className="upload-panel">
          <div className="upload-controls">
            <ProviderSelect disabled={busy} />
          </div>
          <label className="upload-drop" data-busy={busy}>
            <input
              type="file"
              accept="application/pdf"
              disabled={busy}
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
            <span className="glyph" aria-hidden>{busy ? "⟳" : "¶"}</span>
            <span className="label">{busy ? "Reading the document" : "Choose a PDF"}</span>
            <span className="sub">{busy ? "do not close this window" : "or drop one here"}</span>
          </label>
          {error && <p className="error">{error}</p>}
        </div>
      </section>

      <footer className="upload-footer">
        <span>PDF · structured extraction</span>
        <span>
          <a
            href="/demo"
            onClick={(e) => {
              e.preventDefault();
              window.history.pushState({}, "", "/demo");
              window.dispatchEvent(new PopStateEvent("popstate"));
            }}
          >
            View pre-extracted demo →
          </a>
        </span>
      </footer>
    </div>
  );
}
