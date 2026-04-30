import { useEffect, useState } from "react";

import { api, streamExtractPage } from "../api";
import { useApp } from "../store";
import type { Citation, FieldDef, FieldValue } from "../types";

function valuesEqual(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => x === b[i]);
  }
  return a === b;
}

interface Props {
  showReExtract?: boolean;
}

export function FieldsPane({ showReExtract = true }: Props = {}) {
  const session = useApp((s) => s.session)!;
  const currentPage = useApp((s) => s.currentPage);
  const setFieldValue = useApp((s) => s.setFieldValue);
  const removeFieldValue = useApp((s) => s.removeFieldValue);
  const revertField = useApp((s) => s.revertField);
  const deleteFieldStore = useApp((s) => s.deleteField);
  const applyCitations = useApp((s) => s.applyCitations);
  const applyConfidences = useApp((s) => s.applyConfidences);
  const setHighlightedField = useApp((s) => s.setHighlightedField);
  const highlightedField = useApp((s) => s.highlightedField);
  const liveFields = useApp((s) => s.liveFields);
  const markLive = useApp((s) => s.markLive);
  const clearLive = useApp((s) => s.clearLive);
  const setPage = useApp((s) => s.setPage);
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

  function handleReExtract() {
    if (busy) return;
    setBusy(true);
    const provider = useApp.getState().selectedProvider ?? undefined;
    streamExtractPage(session.session_id, currentPage, provider, {
      onField: (name, value) => {
        // Only fill empty scalars; for lists, replace with the streamed list.
        const cur = useApp.getState().session;
        if (!cur) return;
        const def = cur.schema.find((f) => f.name === name);
        if (!def) return;
        if (def.type === "string") {
          if (typeof value === "string" && value.trim() && !cur.values[name]) {
            setFieldValue(name, value);
            markLive(name);
            window.setTimeout(() => clearLive(name), 1400);
          }
        } else if (Array.isArray(value)) {
          // Merge dedupe-preserving: append new items only.
          const existing = Array.isArray(cur.values[name]) ? (cur.values[name] as string[]) : [];
          const seen = new Set(existing);
          const merged = [...existing];
          for (const item of value) {
            if (typeof item === "string" && !seen.has(item)) {
              seen.add(item);
              merged.push(item);
            }
          }
          if (merged.length > existing.length) {
            setFieldValue(name, merged);
            markLive(name);
            window.setTimeout(() => clearLive(name), 1400);
          }
        }
      },
      onCitations: (cits) => applyCitations(cits),
      onConfidences: (cs) => applyConfidences(cs),
      onDone: () => setBusy(false),
      onError: (msg) => {
        alert(`Re-extract failed: ${msg}`);
        setBusy(false);
      },
    });
  }

  function handleCitationClick(field: string) {
    const cit: Citation | undefined = session.citations?.[field];
    if (!cit) return;
    setPage(cit.page);
    setHighlightedField(field);
  }

  // Auto-clear highlight after a while
  useEffect(() => {
    if (!highlightedField) return;
    const t = window.setTimeout(() => setHighlightedField(null), 3500);
    return () => window.clearTimeout(t);
  }, [highlightedField, setHighlightedField]);

  return (
    <div className="fields-pane">
      <p className="fields-section-label">Extracted fields</p>
      {showReExtract && (
        <div className="fields-toolbar">
          <button onClick={handleReExtract} disabled={busy}>
            {busy ? "Streaming…" : `↻ Re-extract page ${currentPage}`}
          </button>
          {busy && <span className="stream-indicator" aria-hidden />}
        </div>
      )}
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
          citation={session.citations?.[f.name]}
          confidence={session.confidences?.[f.name]}
          live={liveFields.has(f.name)}
          highlighted={highlightedField === f.name}
          onScalarChange={handleScalarChange}
          onRevert={handleRevert}
          onRemoveItem={handleRemoveListItem}
          onDelete={handleDeleteField}
          onCitation={handleCitationClick}
        />
      ))}
    </div>
  );
}

interface RowProps {
  field: FieldDef;
  value: FieldValue;
  original: FieldValue | undefined;
  citation?: Citation;
  confidence?: number;
  live: boolean;
  highlighted: boolean;
  onScalarChange: (field: string, value: string) => Promise<void>;
  onRevert: (field: string) => Promise<void>;
  onRemoveItem: (field: string, index: number) => Promise<void>;
  onDelete: (field: FieldDef) => Promise<void>;
  onCitation: (field: string) => void;
}

function FieldRow({
  field,
  value,
  original,
  citation,
  confidence,
  live,
  highlighted,
  onScalarChange,
  onRevert,
  onRemoveItem,
  onDelete,
  onCitation,
}: RowProps) {
  const dirty = !valuesEqual(value, original);
  const showRevert = original !== undefined && dirty;
  const showConfidence = confidence !== undefined && confidence > 0;
  const pct = showConfidence ? Math.round((confidence as number) * 100) : 0;
  const confClass =
    confidence !== undefined && confidence >= 0.85
      ? "conf-high"
      : confidence !== undefined && confidence >= 0.7
        ? "conf-med"
        : "conf-low";
  return (
    <div
      className="field-row"
      data-dirty={dirty}
      data-live={live}
      data-highlighted={highlighted}
    >
      <div className="field-header">
        <label className="field-name">{field.name}</label>
        <span className="field-actions">
          {showConfidence && (
            <span
              className={`conf-badge ${confClass}`}
              title={`Confidence: ${pct}% (model self-report × evidence match)`}
            >
              {pct}%
            </span>
          )}
          {citation && (
            <button
              className="link source"
              onClick={() => onCitation(field.name)}
              title={`Source: page ${citation.page} — "${citation.quote}"`}
            >
              ¶ p.{citation.page}
            </button>
          )}
          {showRevert && (
            <button className="link" onClick={() => onRevert(field.name)}>revert</button>
          )}
          {field.removable && (
            <button className="link danger" onClick={() => onDelete(field)}>delete</button>
          )}
        </span>
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
