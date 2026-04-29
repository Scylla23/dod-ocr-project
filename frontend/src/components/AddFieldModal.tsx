import { useState } from "react";

interface Props {
  onConfirm: (name: string) => Promise<void>;
  onCancel: () => void;
}

export function AddFieldModal({ onConfirm, onCancel }: Props) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function localValidate(value: string): string | null {
    const trimmed = value.trim();
    if (!trimmed) return "Name cannot be empty";
    if (trimmed.length > 40) return "Name must be 40 characters or fewer";
    if (!/^[A-Za-z0-9_\- ]+$/.test(trimmed))
      return "Only letters, digits, spaces, _ and - are allowed";
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const local = localValidate(name);
    if (local) {
      setError(local);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onConfirm(name.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h3>Name your field</h3>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. invoice_number"
        />
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Adding…" : "Add field"}</button>
        </div>
      </form>
    </div>
  );
}
