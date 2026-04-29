import { useState } from "react";

import { api } from "../api";
import { useApp } from "../store";
import type { FieldDef } from "../types";
import { AddFieldModal } from "./AddFieldModal";

interface Props {
  text: string;
  rect: DOMRect;
  onClose: () => void;
}

export function SelectionPopover({ text, rect, onClose }: Props) {
  const session = useApp((s) => s.session)!;
  const setFieldValue = useApp((s) => s.setFieldValue);
  const appendFieldValue = useApp((s) => s.appendFieldValue);
  const addField = useApp((s) => s.addField);
  const [showModal, setShowModal] = useState(false);

  async function assign(def: FieldDef) {
    if (def.type === "string") {
      await api.patchValues(session.session_id, { op: "set", field: def.name, value: text });
      setFieldValue(def.name, text);
    } else {
      await api.patchValues(session.session_id, { op: "append", field: def.name, value: text });
      appendFieldValue(def.name, text);
    }
    onClose();
  }

  async function handleSelect(value: string) {
    if (!value) return;
    const def = session.schema.find((f) => f.name === value);
    if (!def) return;
    await assign(def);
  }

  async function handleCreate(name: string) {
    const { schema } = await api.addField(session.session_id, name);
    const newField = schema.find((f) => f.name === name);
    if (!newField) return;
    addField(newField);
    setShowModal(false);
    await assign(newField);
  }

  const top = rect.bottom + window.scrollY + 4;
  const left = rect.left + window.scrollX;

  return (
    <>
      <div
        className="popover"
        style={{ top, left }}
        onClick={(e) => e.stopPropagation()}
      >
        <span
          className="popover-label"
          onMouseDown={(e) => e.preventDefault()} // label click shouldn't blur selection
        >
          Assign →
        </span>
        <select defaultValue="" onChange={(e) => handleSelect(e.target.value)}>
          <option value="" disabled>
            {session.schema.length ? "choose field" : "no fields yet"}
          </option>
          {session.schema.map((f) => (
            <option key={f.name} value={f.name}>
              {f.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="popover-new"
          onClick={() => setShowModal(true)}
          title="Create a new field with this text"
        >
          + new field
        </button>
        <button className="popover-close" onClick={onClose}>✕</button>
      </div>
      {showModal && <AddFieldModal onConfirm={handleCreate} onCancel={() => setShowModal(false)} />}
    </>
  );
}
