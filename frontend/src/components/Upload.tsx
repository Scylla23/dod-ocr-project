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

  return (
    <div className="upload">
      <h1>PDF Extract</h1>
      <p>Upload a PDF to extract structured data.</p>
      <div className="upload-controls">
        <ProviderSelect disabled={busy} />
      </div>
      <label className="upload-drop">
        <input
          type="file"
          accept="application/pdf"
          disabled={busy}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {busy ? "Extracting…" : "Choose PDF"}
      </label>
      {error && <p className="error">Error: {error}</p>}
    </div>
  );
}
