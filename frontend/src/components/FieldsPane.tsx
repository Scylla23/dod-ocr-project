import { useState } from "react";

import { api } from "../api";
import { useApp } from "../store";
import type { FieldDef } from "../types";

function valuesEqual(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => x === b[i]);
  }
  return a === b;
}

export function FieldsPane() {
  const session = useApp((s) => s.session)!;
  const currentPage = useApp((s) => s.currentPage);
  const setFieldValue = useApp((s) => s.setFieldValue);
  const removeFieldValue = useApp((s) => s.removeFieldValue);
  const revertField = useApp((s) => s.revertField);
  const deleteFieldStore = useApp((s) => s.deleteField);
  const applyMergedValues = useApp((s) => s.applyMergedValues);
  const [busy, setBusy] = useState(false);

  async function handleRevert(field: string) {
    await api.patchValues(session.session_id, { op: "revert", field });
    revertField(field);
  }

  async function handleScalarChange(field: string, value: string) {
    await api.patchValues(session.session_id, { op: "set", field, value });
    setFieldValue(field, value);
  }

  async function handleRemoveListItem(field: string, index: number) {
    await api.patchValues(session.session_id, { op: "remove", field, index });
    removeFieldValue(field, index);
  }

  async function handleDeleteField(field: FieldDef) {
    if (!confirm(`Delete field "${field.name}" and its value?`)) return;
    await api.deleteField(session.session_id, field.name);
    deleteFieldStore(field.name);
  }

  async function handleReExtract() {
    setBusy(true);
    try {
      const { values } = await api.extractPage(session.session_id, currentPage);
      applyMergedValues(values as Record<string, string | string[]>);
    } catch (e) {
      alert(`Re-extract failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fields-pane">
      <div className="fields-toolbar">
        <button onClick={handleReExtract} disabled={busy}>
          {busy ? "Re-extracting…" : `Re-extract page ${currentPage}`}
        </button>
      </div>
      {session.extraction_errors.length > 0 && (
        <div className="banner">
          Initial extraction failed for page(s): {session.extraction_errors.join(", ")}
        </div>
      )}
      {session.schema.map((f) => (
        <FieldRow
          key={f.name}
          field={f}
          value={session.values[f.name] ?? (f.type === "list[string]" ? [] : "")}
          original={session.original_extracted[f.name]}
          onScalarChange={handleScalarChange}
          onRevert={handleRevert}
          onRemoveItem={handleRemoveListItem}
          onDelete={handleDeleteField}
        />
      ))}
    </div>
  );
}

interface RowProps {
  field: FieldDef;
  value: string | string[];
  original: string | string[] | undefined;
  onScalarChange: (field: string, value: string) => Promise<void>;
  onRevert: (field: string) => Promise<void>;
  onRemoveItem: (field: string, index: number) => Promise<void>;
  onDelete: (field: FieldDef) => Promise<void>;
}

function FieldRow({ field, value, original, onScalarChange, onRevert, onRemoveItem, onDelete }: RowProps) {
  const dirty = !valuesEqual(value, original);
  const showRevert = original !== undefined && dirty;
  return (
    <div className="field-row">
      <div className="field-header">
        <label className="field-name">{field.name}</label>
        {showRevert && (
          <button className="link" onClick={() => onRevert(field.name)}>revert</button>
        )}
        {field.removable && (
          <button className="link danger" onClick={() => onDelete(field)}>delete</button>
        )}
      </div>
      {field.type === "string" ? (
        <input
          value={value as string}
          onChange={(e) => onScalarChange(field.name, e.target.value)}
        />
      ) : (
        <div className="chips">
          {(value as string[]).map((item, i) => (
            <span key={`${item}-${i}`} className="chip">
              {item}
              <button onClick={() => onRemoveItem(field.name, i)}>×</button>
            </span>
          ))}
          {(value as string[]).length === 0 && <span className="placeholder">(empty)</span>}
        </div>
      )}
    </div>
  );
}
