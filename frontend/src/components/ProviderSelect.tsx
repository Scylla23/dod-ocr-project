import { useEffect, useState } from "react";

import { api } from "../api";
import { useApp } from "../store";

interface Props {
  disabled?: boolean;
}

export function ProviderSelect({ disabled }: Props) {
  const selectedProvider = useApp((s) => s.selectedProvider);
  const setSelectedProvider = useApp((s) => s.setSelectedProvider);
  const [available, setAvailable] = useState<string[] | null>(null);
  const [serverDefault, setServerDefault] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getProviders()
      .then((res) => {
        if (cancelled) return;
        setAvailable(res.providers);
        setServerDefault(res.default);
        // If nothing selected yet, default to server's default
        if (!selectedProvider && res.providers.length > 0) {
          setSelectedProvider(res.default);
        } else if (selectedProvider && !res.providers.includes(selectedProvider)) {
          // Saved selection no longer valid (server config changed); fall back
          setSelectedProvider(res.default);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedProvider, setSelectedProvider]);

  if (error) {
    return (
      <div className="provider-select error">
        Could not load providers: {error}
      </div>
    );
  }
  if (!available) {
    return <div className="provider-select">Loading providers…</div>;
  }

  return (
    <label className="provider-select">
      Model:{" "}
      <select
        value={selectedProvider ?? serverDefault ?? ""}
        onChange={(e) => setSelectedProvider(e.target.value)}
        disabled={disabled}
      >
        {available.map((name) => (
          <option key={name} value={name}>
            {name}
            {name === serverDefault ? " (default)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
