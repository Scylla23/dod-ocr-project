import { create } from "zustand";

import type { FieldDef, FieldValue, SessionData } from "./types";

interface AppState {
  session: SessionData | null;
  currentPage: number;

  setSession: (s: SessionData) => void;
  reset: () => void;
  setPage: (p: number) => void;

  setFieldValue: (field: string, value: FieldValue) => void;
  appendFieldValue: (field: string, value: string) => void;
  removeFieldValue: (field: string, index: number) => void;
  revertField: (field: string) => void;
  addField: (f: FieldDef) => void;
  deleteField: (name: string) => void;
  setSchema: (schema: FieldDef[]) => void;
  applyMergedValues: (values: Record<string, FieldValue>) => void;
}

const isList = (v: FieldValue | undefined): v is string[] => Array.isArray(v);

export const useApp = create<AppState>((set, get) => ({
  session: null,
  currentPage: 1,

  setSession: (s) => set({ session: s, currentPage: 1 }),
  reset: () => set({ session: null, currentPage: 1 }),
  setPage: (p) => set({ currentPage: p }),

  setFieldValue: (field, value) => {
    const s = get().session;
    if (!s) return;
    set({ session: { ...s, values: { ...s.values, [field]: value } } });
  },

  appendFieldValue: (field, value) => {
    const s = get().session;
    if (!s) return;
    const current = s.values[field];
    const list = isList(current) ? current : [];
    if (list.includes(value)) return;
    set({ session: { ...s, values: { ...s.values, [field]: [...list, value] } } });
  },

  removeFieldValue: (field, index) => {
    const s = get().session;
    if (!s) return;
    const current = s.values[field];
    if (!isList(current)) return;
    const next = current.filter((_, i) => i !== index);
    set({ session: { ...s, values: { ...s.values, [field]: next } } });
  },

  revertField: (field) => {
    const s = get().session;
    if (!s) return;
    const def = s.schema.find((f) => f.name === field);
    const orig = s.original_extracted[field];
    let restored: FieldValue;
    if (orig === undefined) {
      restored = def?.type === "list[string]" ? [] : "";
    } else {
      restored = isList(orig) ? [...orig] : orig;
    }
    set({ session: { ...s, values: { ...s.values, [field]: restored } } });
  },

  addField: (f) => {
    const s = get().session;
    if (!s) return;
    set({
      session: {
        ...s,
        schema: [...s.schema, f],
        values: { ...s.values, [f.name]: f.type === "list[string]" ? [] : "" },
      },
    });
  },

  deleteField: (name) => {
    const s = get().session;
    if (!s) return;
    const { [name]: _v, ...values } = s.values;
    const { [name]: _o, ...original_extracted } = s.original_extracted;
    set({
      session: {
        ...s,
        schema: s.schema.filter((f) => f.name !== name),
        values,
        original_extracted,
      },
    });
  },

  setSchema: (schema) => {
    const s = get().session;
    if (!s) return;
    set({ session: { ...s, schema } });
  },

  applyMergedValues: (values) => {
    const s = get().session;
    if (!s) return;
    const merged: Record<string, FieldValue> = { ...s.values };
    for (const [k, v] of Object.entries(values)) {
      merged[k] = v as FieldValue;
    }
    set({ session: { ...s, values: merged } });
  },
}));
