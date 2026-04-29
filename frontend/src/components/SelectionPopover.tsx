import { useState } from "react";

import { api } from "../api";
import { useApp } from "../store";
import { AddFieldModal } from "./AddFieldModal";

interface Props {
  text: string;
  rect: DOMRect;
  onClose: () => void;
}

const NEW_FIELD_VALUE = "__new__";

export function SelectionPopover({ text, rect, onClose }: Props) {
  const session = useApp((s) => s.session)!;
  const setFieldValue = useApp((s) => s.setFieldValue);
  const appendFieldValue = useApp((s) => s.appendFieldValue);
  const addField = useApp((s) => s.addField);
  const [showModal, setShowModal] = useState(false);

  async function assign(fieldName: string) {
    const def = session.schema.find((f) => f.name === fieldName);
    if (!def) return;
    if (def.type === "string") {
      await api.patchValues(session.session_id, { op: "set", field: fieldName, value: text });
      setFieldValue(fieldName, text);
    } else {
      await api.patchValues(session.session_id, { op: "append", field: fieldName, value: text });
      appendFieldValue(fieldName, text);
    }
    onClose();
  }

  async function handleSelect(value: string) {
    if (value === NEW_FIELD_VALUE) {
      setShowModal(true);
      return;
    }
    await assign(value);
  }

  async function handleCreate(name: string) {
    const { schema } = await api.addField(session.session_id, name);
    const newField = schema.find((f) => f.name === name);
    if (newField) addField(newField);
    setShowModal(false);
    await assign(name);
  }

  const top = rect.bottom + window.scrollY + 4;
  const left = rect.left + window.scrollX;

  return (
    <>
      <div
        className="popover"
        style={{ top, left }}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.preventDefault()} // don't clear selection
      >
        <span className="popover-label">Assign to…</span>
        <select defaultValue="" onChange={(e) => handleSelect(e.target.value)}>
          <option value="" disabled>
            choose field
          </option>
          {session.schema.map((f) => (
            <option key={f.name} value={f.name}>
              {f.name}
            </option>
          ))}
          <option value={NEW_FIELD_VALUE}>+ Create new field…</option>
        </select>
        <button className="popover-close" onClick={onClose}>✕</button>
      </div>
      {showModal && <AddFieldModal onConfirm={handleCreate} onCancel={() => setShowModal(false)} />}
    </>
  );
}
